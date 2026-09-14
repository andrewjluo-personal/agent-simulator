"""Tests for Anthropic workload-identity-federation auth."""

from __future__ import annotations

import json
import time

import httpx
import pytest

from app.anthropic_auth import WIFConfig, WIFTokenProvider
from app.llm import AnthropicClient, get_client, reset_client

REQUIRED_ENV = {
    "ANTHROPIC_FEDERATION_RULE_ID": "fdrl_test",
    "ANTHROPIC_ORGANIZATION_ID": "org-test",
    "ANTHROPIC_SERVICE_ACCOUNT_ID": "svac_test",
}


def _set_wif_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)


def test_wif_config_none_when_required_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    for missing in REQUIRED_ENV:
        for key in REQUIRED_ENV:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
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
    for key in REQUIRED_ENV:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError, match="workload identity"):
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
