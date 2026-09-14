from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from app import llm
from app.anthropic_auth import WIFTokenSource


def _source(transport: httpx.MockTransport) -> WIFTokenSource:
    return WIFTokenSource(
        federation_rule_id="fdrl_x",
        organization_id="org_x",
        service_account_id="svac_x",
        workspace_id="wrkspc_x",
        transport=transport,
    )


def _token_transport(payload: dict[str, Any], calls: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler)


def _patch_llm_client(monkeypatch: pytest.MonkeyPatch, transport: httpx.MockTransport) -> None:
    real = httpx.AsyncClient

    def factory(**kw):  # type: ignore[no-untyped-def]
        kw.setdefault("transport", transport)
        return real(**kw)

    monkeypatch.setattr("app.llm.httpx.AsyncClient", factory)


def _patch_mint(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mint(self: WIFTokenSource) -> str:
        return "jwt"

    monkeypatch.setattr(WIFTokenSource, "_mint_jwt", mint)


def test_token_cached_across_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_mint(monkeypatch)
    calls: list[httpx.Request] = []
    ts = _source(_token_transport({"access_token": "tok1", "expires_in": 118}, calls))

    async def run() -> tuple[str, str]:
        return await ts.token(), await ts.token()

    first, second = asyncio.run(run())
    assert first == second == "tok1"
    assert len(calls) == 1
    body = json.loads(calls[0].content)
    assert body["grant_type"] == "urn:ietf:params:oauth:grant-type:jwt-bearer"
    assert body["assertion"] == "jwt"
    assert body["federation_rule_id"] == "fdrl_x"


def test_token_refreshes_when_near_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_mint(monkeypatch)
    calls: list[httpx.Request] = []
    ts = _source(_token_transport({"access_token": "tok1", "expires_in": 10}, calls))

    async def run() -> tuple[str, str]:
        return await ts.token(), await ts.token()

    first, second = asyncio.run(run())
    assert first == second == "tok1"
    assert len(calls) == 2


def test_client_sends_bearer_and_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_mint(monkeypatch)
    exchange_calls: list[httpx.Request] = []
    ts = _source(_token_transport({"access_token": "tok1", "expires_in": 118}, exchange_calls))
    api_calls: list[httpx.Request] = []

    def api_handler(request: httpx.Request) -> httpx.Response:
        api_calls.append(request)
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "hi"}],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    _patch_llm_client(monkeypatch, httpx.MockTransport(api_handler))
    client = llm.AnthropicClient(token_source=ts)
    req = llm.LLMRequest(system="s", user="u", model="claude-haiku-4-5", max_tokens=5)

    resp = asyncio.run(client.complete(req))
    assert resp.text == "hi"
    assert len(api_calls) == 1
    assert api_calls[0].headers["authorization"] == "Bearer tok1"
    assert "x-api-key" not in api_calls[0].headers


def test_client_retries_once_with_fresh_token_on_401(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_mint(monkeypatch)
    tokens = iter(["tok1", "tok2"])

    def exchange_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": next(tokens), "expires_in": 118})

    ts = _source(httpx.MockTransport(exchange_handler))
    api_calls: list[httpx.Request] = []

    def api_handler(request: httpx.Request) -> httpx.Response:
        api_calls.append(request)
        if len(api_calls) == 1:
            return httpx.Response(401, json={"error": {"message": "bad token"}}, request=request)
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    _patch_llm_client(monkeypatch, httpx.MockTransport(api_handler))
    client = llm.AnthropicClient(token_source=ts)
    req = llm.LLMRequest(system="s", user="u", model="claude-haiku-4-5", max_tokens=5)

    resp = asyncio.run(client.complete(req))
    assert resp.text == "ok"
    assert len(api_calls) == 2
    assert api_calls[0].headers["authorization"] == "Bearer tok1"
    assert api_calls[1].headers["authorization"] == "Bearer tok2"


def test_client_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_FEDERATION_RULE_ID", raising=False)
    with pytest.raises(RuntimeError, match="no Anthropic credentials"):
        llm.AnthropicClient()
