"""Tests for Anthropic workload-identity-federation auth."""

from __future__ import annotations

import asyncio
import json
import time

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import anthropic_auth
from app.anthropic_auth import (
    WIFConfig,
    WIFTokenProvider,
    identity_token,
    vercel_identity_token,
    vercel_oidc_context,
    vercel_oidc_token,
)
from app.llm import AnthropicClient, LLMRequest, get_client, reset_client

REQUIRED_ENV = {
    "ANTHROPIC_FEDERATION_RULE_ID": "fdrl_test",
    "ANTHROPIC_ORGANIZATION_ID": "org-test",
    "ANTHROPIC_SERVICE_ACCOUNT_ID": "svac_test",
}


def _set_wif_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_AUTH", "wif")
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)


def test_wif_config_none_without_enable_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_AUTH", raising=False)
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    assert WIFConfig.from_env() is None


def test_wif_config_none_when_required_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    for missing in REQUIRED_ENV:
        for key in REQUIRED_ENV:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
        monkeypatch.delenv("ANTHROPIC_AUTH", raising=False)
        _set_wif_env(monkeypatch)
        monkeypatch.delenv(missing)
        assert WIFConfig.from_env() is None


def test_wif_config_parses_all(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_wif_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "wrkspc_test")
    cfg = WIFConfig.from_env()
    assert cfg is not None
    assert cfg.federation_rule_id == "fdrl_test"
    assert cfg.organization_id == "org-test"
    assert cfg.service_account_id == "svac_test"
    assert cfg.workspace_id == "wrkspc_test"


def _mock_provider(workspace: str | None = None) -> tuple[WIFTokenProvider, list[dict[str, object]]]:
    bodies: list[dict[str, object]] = []
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        calls["n"] += 1
        return httpx.Response(200, json={"access_token": f"tok{calls['n']}", "expires_in": 120})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    cfg = WIFConfig(
        federation_rule_id="fdrl_test",
        organization_id="org-test",
        service_account_id="svac_test",
        workspace_id=workspace,
    )
    return WIFTokenProvider(cfg, identity_token=lambda: "jwt", http=http), bodies


def test_token_provider_caches_and_refreshes(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, bodies = _mock_provider()
    assert provider.token() == "tok1"
    assert provider.token() == "tok1"
    assert len(bodies) == 1
    assert bodies[0]["grant_type"] == "urn:ietf:params:oauth:grant-type:jwt-bearer"
    assert bodies[0]["assertion"] == "jwt"
    assert bodies[0]["federation_rule_id"] == "fdrl_test"
    assert bodies[0]["organization_id"] == "org-test"
    assert bodies[0]["service_account_id"] == "svac_test"
    assert "workspace_id" not in bodies[0]

    real_monotonic = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: real_monotonic() + 100)
    assert provider.token() == "tok2"
    assert len(bodies) == 2


def test_token_provider_includes_workspace() -> None:
    provider, bodies = _mock_provider(workspace="wrkspc_test")
    provider.token()
    assert bodies[0]["workspace_id"] == "wrkspc_test"


class _StubProvider:
    def __init__(self, token: str = "stub-tok") -> None:
        self._token = token

    def token(self) -> str:
        return self._token

    def invalidate(self) -> None:
        pass


def test_client_wif_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _set_wif_env(monkeypatch)
    client = AnthropicClient(token_provider=_StubProvider())
    assert client.auth_mode == "wif"
    assert client._auth_headers() == {"Authorization": "Bearer stub-tok"}


def test_client_api_key_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    client = AnthropicClient()
    assert client.auth_mode == "api_key"
    assert client._auth_headers() == {"x-api-key": "sk-test"}


def test_client_requires_some_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH", raising=False)
    for key in REQUIRED_ENV:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError, match="workload identity federation is not enabled"):
        AnthropicClient()


def test_get_client_picks_anthropic_on_wif_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    _set_wif_env(monkeypatch)
    reset_client()
    try:
        client = get_client()
        assert isinstance(client, AnthropicClient)
        assert client.auth_mode == "wif"
    finally:
        reset_client()


def test_vercel_identity_token_prefers_contextvar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL_OIDC_TOKEN", "env-tok")
    token = vercel_oidc_token.set("hdr-tok")
    try:
        assert vercel_identity_token() == "hdr-tok"
    finally:
        vercel_oidc_token.reset(token)
    assert vercel_identity_token() == "env-tok"
    monkeypatch.delenv("VERCEL_OIDC_TOKEN")
    with pytest.raises(RuntimeError, match="no Vercel OIDC token"):
        vercel_identity_token()


def test_identity_token_dispatches_on_vercel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_OIDC_TOKEN", "vercel-tok")
    assert identity_token() == "vercel-tok"

    monkeypatch.delenv("VERCEL")
    monkeypatch.setattr(anthropic_auth, "devin_identity_token", lambda: "devin-tok")
    assert identity_token() == "devin-tok"


def test_middleware_sets_and_resets_contextvar() -> None:
    app = FastAPI()
    app.middleware("http")(vercel_oidc_context)

    @app.get("/")
    def index() -> dict[str, str | None]:
        return {"tok": vercel_oidc_token.get()}

    client = TestClient(app)
    assert client.get("/", headers={"x-vercel-oidc-token": "hdr-tok"}).json() == {
        "tok": "hdr-tok"
    }
    assert vercel_oidc_token.get() is None
    assert client.get("/").json() == {"tok": None}


def test_invalidate_forces_reexchange() -> None:
    provider, bodies = _mock_provider()
    assert provider.token() == "tok1"
    provider.invalidate()
    assert provider.token() == "tok2"
    assert len(bodies) == 2


class _CountingProvider:
    def __init__(self) -> None:
        self.invalidated = 0

    def token(self) -> str:
        return "stub-tok"

    def invalidate(self) -> None:
        self.invalidated += 1


def test_client_retries_once_on_401(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(401, json={"error": {"message": "expired"}})
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: real_async_client(transport=transport, **kw)
    )
    provider = _CountingProvider()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = AnthropicClient(token_provider=provider)
    resp = asyncio.run(
        client.complete(LLMRequest(system="s", user="u", model="m", max_tokens=5))
    )
    assert resp.text == "ok"
    assert len(calls) == 2
    assert provider.invalidated == 1
    assert calls[0].headers["Authorization"] == "Bearer stub-tok"
