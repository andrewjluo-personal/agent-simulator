"""LLM boundary. AnthropicClient talks to the Messages API over plain httpx;
FakeClient is a deterministic stand-in for tests and local development."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from .anthropic_auth import WIFConfig, WIFTokenProvider
from .telemetry import emit
from .truth import UNDECIDED

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


@dataclass
class LLMRequest:
    system: str
    user: str
    model: str
    max_tokens: int = 600
    meta: dict[str, Any] = field(default_factory=dict)  # only the fake client reads this


@dataclass
class LLMResponse:
    text: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    model: str


class LLMClient(Protocol):
    provider: str

    async def complete(self, req: LLMRequest) -> LLMResponse: ...


class AnthropicClient:
    provider = "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        token_provider: WIFTokenProvider | None = None,
    ) -> None:
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._key: str | None = None
        self._token_provider: WIFTokenProvider | None = None
        if key:
            self._key = key
            self.auth_mode = "api_key"
        else:
            provider = token_provider
            config = WIFConfig.from_env()
            if provider is None and config is not None:
                provider = WIFTokenProvider(config)
            if provider is None:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is not set (set it for deployed/Vercel use) "
                    "and Devin workload identity federation is not enabled "
                    "(ANTHROPIC_AUTH=wif plus ANTHROPIC_FEDERATION_RULE_ID/"
                    "ANTHROPIC_ORGANIZATION_ID/ANTHROPIC_SERVICE_ACCOUNT_ID)"
                )
            self._token_provider = provider
            self.auth_mode = "wif"

    def _auth_headers(self) -> dict[str, str]:
        if self._token_provider is not None:
            return {"Authorization": f"Bearer {self._token_provider.token()}"}
        assert self._key is not None
        return {"x-api-key": self._key}

    async def complete(self, req: LLMRequest) -> LLMResponse:
        body = {
            "model": req.model,
            "max_tokens": req.max_tokens,
            "system": req.system,
            "messages": [{"role": "user", "content": req.user}],
            "temperature": 1.0,
        }
        last_exc: Exception | None = None
        saw_401 = False
        for attempt in range(3):
            headers = {
                **await asyncio.to_thread(self._auth_headers),
                "anthropic-version": API_VERSION,
                "content-type": "application/json",
            }
            started = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(API_URL, json=body, headers=headers)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"status {resp.status_code}", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                latency_ms = round((time.perf_counter() - started) * 1000)
                data = resp.json()
                text = "".join(
                    block.get("text", "")
                    for block in data.get("content", [])
                    if isinstance(block, dict) and block.get("type") == "text"
                )
                usage = data.get("usage") or {}
                input_tokens = usage.get("input_tokens")
                output_tokens = usage.get("output_tokens")
                emit(
                    "info",
                    "llm.call",
                    provider=self.provider,
                    model=req.model,
                    latencyMs=latency_ms,
                    inputTokens=input_tokens,
                    outputTokens=output_tokens,
                    kind=req.meta.get("kind"),
                )
                return LLMResponse(
                    text=text,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model=req.model,
                )
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                retryable = isinstance(exc, httpx.HTTPStatusError) and (
                    exc.response.status_code == 429 or exc.response.status_code >= 500
                )
                if not isinstance(exc, httpx.HTTPStatusError):
                    retryable = True
                if (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code == 401
                    and self._token_provider is not None
                    and not saw_401
                ):
                    saw_401 = True
                    self._token_provider.invalidate()
                    retryable = True
                if not retryable or attempt == 2:
                    raise
                await asyncio.sleep((2**attempt) * 0.5 + random.random() * 0.5)
        assert last_exc is not None
        raise last_exc


class FakeClient:
    """Deterministic seeded client: parrots held fact ids, biased toward shared facts."""

    provider = "fake"

    def __init__(self) -> None:
        self._turn_counts: dict[str, int] = {}

    def _rng(self, req: LLMRequest) -> random.Random:
        meta = req.meta
        key = "|".join(str(meta.get(k)) for k in ("kind", "seed", "run_nonce", "agent_id", "round"))
        return random.Random(int(hashlib.sha256(key.encode()).hexdigest(), 16) % (2**32))

    async def complete(self, req: LLMRequest) -> LLMResponse:
        meta = req.meta
        rng = self._rng(req)
        if meta.get("kind") == "vote":
            text = self._vote(meta, rng)
        else:
            text = self._turn(meta, rng)
        latency = rng.randint(5, 40)
        return LLMResponse(
            text=text,
            latency_ms=latency,
            input_tokens=rng.randint(100, 400),
            output_tokens=rng.randint(20, 120),
            model=req.model,
        )

    def _lean(self, meta: dict[str, Any], rng: random.Random) -> tuple[str, float]:
        fact_signed_weight: dict[str, int] = meta.get("fact_signed_weight", {})
        fact_candidate: dict[str, str] = meta.get("fact_candidate", {})
        known = set(meta.get("hand", [])) | set(meta.get("heard", []))
        totals: dict[str, int] = {c: 0 for c in meta.get("candidates", [])}
        for fact_id in known:
            if fact_id in fact_signed_weight:
                totals[fact_candidate[fact_id]] += fact_signed_weight[fact_id]
        best = max(totals.values()) if totals else 0
        winners = [c for c, t in totals.items() if t == best]
        if len(winners) == 1:
            lean = winners[0]
        elif meta.get("alone"):
            lean = winners[0] if winners else UNDECIDED  # alone ballots must pick one
        else:
            lean = UNDECIDED
        return lean, round(0.55 + rng.random() * 0.4, 2)

    def _turn(self, meta: dict[str, Any], rng: random.Random) -> str:
        hand: list[str] = list(meta.get("hand", []))
        shared = set(meta.get("shared", []))
        heard = set(meta.get("heard", []))
        fresh = [f for f in hand if f not in heard]
        shared_fresh = [f for f in fresh if f in shared]
        unique_fresh = [f for f in fresh if f not in shared]
        limit = int(meta.get("sentences_per_turn", 2))
        picked: list[str] = []
        if meta.get("share_first_round"):
            rng.shuffle(unique_fresh)
            picked = unique_fresh[:limit]
        if not picked:
            n = min(len(fresh), rng.randint(1, 3))
            for _ in range(n):
                pool = (
                    shared_fresh
                    if shared_fresh and (rng.random() < 0.75 or not unique_fresh)
                    else unique_fresh or shared_fresh
                )
                if not pool:
                    break
                choice = rng.choice(pool)
                picked.append(choice)
                (shared_fresh if choice in shared else unique_fresh).remove(choice)
        run_nonce = str(meta.get("run_nonce", ""))
        count = self._turn_counts.get(run_nonce, 0) + 1
        self._turn_counts[run_nonce] = count
        memo = meta.get("fact_style") == "memo"
        if memo:
            fact_text: dict[str, str] = meta.get("fact_text", {})
            sentences = [f"I noted that {fact_text[fid]}." for fid in picked if fid in fact_text]
        else:
            sentences = [f"I noted the point about {fid}." for fid in picked]
        if count % 3 == 0:
            sentences.append("There is more context here worth revisiting later.")
        if count % 5 == 0:
            sentences.append("I would also flag the point about X99.")
            picked.append("X99")
        lean, confidence = self._lean(meta, rng)
        payload = {
            "sentences": sentences,
            "current_lean": lean,
            "confidence": confidence,
        }
        if not memo:
            payload["items_referenced"] = picked
        return self._dump(payload, rng)

    def _vote(self, meta: dict[str, Any], rng: random.Random) -> str:
        lean, confidence = self._lean(meta, rng)
        payload = {
            "vote": lean,
            "confidence": confidence,
            "reason": "fake: weighted lean over hand plus heard",
        }
        return self._dump(payload, rng)

    @staticmethod
    def _dump(payload: dict[str, Any], rng: random.Random) -> str:
        text = json.dumps(payload)
        return f"```json\n{text}\n```" if rng.random() < 0.3 else text


_client: LLMClient | None = None


def get_client() -> LLMClient:
    global _client
    if _client is not None:
        return _client
    provider = os.getenv("LLM_PROVIDER")
    if provider == "fake":
        _client = FakeClient()
    elif provider == "anthropic" or (
        provider is None
        and (os.getenv("ANTHROPIC_API_KEY") or WIFConfig.from_env() is not None)
    ):
        _client = AnthropicClient()
    elif provider is None:
        _client = FakeClient()
    else:
        raise RuntimeError(f"unknown LLM_PROVIDER {provider!r}")
    auth_mode = _client.auth_mode if isinstance(_client, AnthropicClient) else None
    emit("info", "llm.provider", provider=_client.provider, authMode=auth_mode)
    return _client


def reset_client() -> None:
    """Test hook: drop the cached client so env changes take effect."""
    global _client
    _client = None
