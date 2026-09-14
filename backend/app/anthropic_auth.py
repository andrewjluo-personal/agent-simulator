"""Anthropic Workload Identity Federation: exchange an OIDC identity token for a
short-lived Anthropic access token (no static API keys). The identity token is the
Vercel OIDC token on Vercel (per-request header or VERCEL_OIDC_TOKEN), and the Devin
session OIDC token elsewhere."""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass

import httpx
from fastapi import Request, Response

ANTHROPIC_AUDIENCE = "https://api.anthropic.com"
DEVIN_OIDC_TOKEN_FILE = "/opt/.devin/oidc_token"
DEVIN_EXCHANGE_URL = "https://app.devin.ai/api/oidc/token"
ANTHROPIC_TOKEN_URL = "https://api.anthropic.com/v1/oauth/token"
REFRESH_MARGIN_S = 30
WIF_ENABLE_VAR = "ANTHROPIC_AUTH"
VERCEL_OIDC_HEADER = "x-vercel-oidc-token"

vercel_oidc_token: ContextVar[str | None] = ContextVar("vercel_oidc_token", default=None)


@dataclass(frozen=True)
class WIFConfig:
    federation_rule_id: str
    organization_id: str
    service_account_id: str
    workspace_id: str | None

    @classmethod
    def from_env(cls) -> WIFConfig | None:
        if os.getenv(WIF_ENABLE_VAR) != "wif":
            return None
        federation_rule_id = os.getenv("ANTHROPIC_FEDERATION_RULE_ID")
        organization_id = os.getenv("ANTHROPIC_ORGANIZATION_ID")
        service_account_id = os.getenv("ANTHROPIC_SERVICE_ACCOUNT_ID")
        if not (federation_rule_id and organization_id and service_account_id):
            return None
        return cls(
            federation_rule_id=federation_rule_id,
            organization_id=organization_id,
            service_account_id=service_account_id,
            workspace_id=os.getenv("ANTHROPIC_WORKSPACE_ID") or None,
        )


def devin_identity_token(audience: str = ANTHROPIC_AUDIENCE) -> str:
    """Mint an audience-scoped Devin OIDC JWT.

    Uses `devin-oidc token --audience <aud>` when the CLI is on PATH, else
    exchanges the session token at DEVIN_EXCHANGE_URL. Raises RuntimeError if
    neither path works (e.g. not running inside a Devin session).
    """
    cli = shutil.which("devin-oidc")
    if cli:
        try:
            out = subprocess.run(
                [cli, "token", "--audience", audience],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            raise RuntimeError(f"devin-oidc failed to mint an OIDC token: {exc}") from exc
        token = out.stdout.strip()
        if not token:
            raise RuntimeError("devin-oidc returned an empty OIDC token")
        return token

    token_file = os.getenv("DEVIN_OIDC_TOKEN_FILE", DEVIN_OIDC_TOKEN_FILE)
    try:
        with open(token_file) as f:
            subject_token = f.read().strip()
    except OSError as exc:
        raise RuntimeError(
            f"devin-oidc not on PATH and Devin OIDC token file {token_file} unreadable; "
            "not running inside a Devin session"
        ) from exc
    if not subject_token:
        raise RuntimeError(
            f"Devin OIDC token file {token_file} is empty; not running inside a Devin session"
        )

    resp = httpx.post(
        DEVIN_EXCHANGE_URL,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "subject_token": subject_token,
            "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
            "audience": audience,
            "subject_keys": "org_id",
        },
        timeout=30,
    )
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Devin OIDC token exchange failed with status {resp.status_code}: {resp.text}"
        ) from exc
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("Devin OIDC token exchange returned no access_token")
    return str(token)


def vercel_identity_token() -> str:
    token = vercel_oidc_token.get() or os.getenv("VERCEL_OIDC_TOKEN")
    if not token:
        raise RuntimeError(
            "no Vercel OIDC token: expected x-vercel-oidc-token request header or "
            "VERCEL_OIDC_TOKEN"
        )
    return token


def identity_token() -> str:
    """Pick the OIDC identity source: Vercel's token when running on Vercel
    (VERCEL=1), else the Devin session token."""
    if os.getenv("VERCEL") == "1":
        return vercel_identity_token()
    return devin_identity_token()


async def vercel_oidc_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Expose the per-request `x-vercel-oidc-token` header to vercel_identity_token."""
    token = vercel_oidc_token.set(request.headers.get(VERCEL_OIDC_HEADER))
    try:
        return await call_next(request)
    finally:
        vercel_oidc_token.reset(token)


class WIFTokenProvider:
    """Caches the Anthropic access token; refreshes REFRESH_MARGIN_S before expiry.
    Thread-safe."""

    def __init__(
        self,
        config: WIFConfig,
        identity_token: Callable[[], str] = identity_token,
        http: httpx.Client | None = None,
    ) -> None:
        self._config = config
        self._identity_token = identity_token
        self._http = http or httpx.Client(timeout=30)
        self._lock = threading.Lock()
        self._token: str | None = None
        self._expires_at = 0.0

    def token(self) -> str:
        with self._lock:
            now = time.monotonic()
            if self._token is not None and now < self._expires_at - REFRESH_MARGIN_S:
                return self._token
            jwt = self._identity_token()
            payload = {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": jwt,
                "federation_rule_id": self._config.federation_rule_id,
                "organization_id": self._config.organization_id,
                "service_account_id": self._config.service_account_id,
            }
            if self._config.workspace_id:
                payload["workspace_id"] = self._config.workspace_id
            resp = self._http.post(ANTHROPIC_TOKEN_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
            self._token = str(data["access_token"])
            self._expires_at = time.monotonic() + float(data.get("expires_in", 300))
            return self._token

    def invalidate(self) -> None:
        """Drop the cached token so the next token() re-exchanges."""
        with self._lock:
            self._token = None
            self._expires_at = 0.0
