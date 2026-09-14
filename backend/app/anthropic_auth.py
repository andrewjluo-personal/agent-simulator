"""Anthropic access tokens via Workload Identity Federation.

Exchanges a short-lived Devin OIDC JWT for a short-lived Anthropic OAuth
access token (sk-ant-oat01-…); used when no ANTHROPIC_API_KEY is available.
"""

from __future__ import annotations

import asyncio
import os
import time

import httpx

TOKEN_URL = "https://api.anthropic.com/v1/oauth/token"
GRANT_TYPE = "urn:ietf:params:oauth:grant-type:jwt-bearer"
DEFAULT_WORKSPACE_ID = "wrkspc_0177Z9yWkfwdtsNMKHVf7wHG"
REFRESH_MARGIN_S = 30.0


class WIFTokenSource:
    def __init__(
        self,
        *,
        federation_rule_id: str,
        organization_id: str,
        service_account_id: str,
        workspace_id: str,
        audience: str = "https://api.anthropic.com",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._federation_rule_id = federation_rule_id
        self._organization_id = organization_id
        self._service_account_id = service_account_id
        self._workspace_id = workspace_id
        self._audience = audience
        self._transport = transport
        self._lock = asyncio.Lock()
        self._token: str | None = None
        self._expires_at = 0.0

    @classmethod
    def from_env(cls) -> WIFTokenSource:
        federation_rule_id = os.getenv("ANTHROPIC_FEDERATION_RULE_ID")
        organization_id = os.getenv("ANTHROPIC_ORGANIZATION_ID")
        service_account_id = os.getenv("ANTHROPIC_SERVICE_ACCOUNT_ID")
        if not (federation_rule_id and organization_id and service_account_id):
            raise RuntimeError(
                "WIF env vars missing: need ANTHROPIC_FEDERATION_RULE_ID, "
                "ANTHROPIC_ORGANIZATION_ID and ANTHROPIC_SERVICE_ACCOUNT_ID"
            )
        return cls(
            federation_rule_id=federation_rule_id,
            organization_id=organization_id,
            service_account_id=service_account_id,
            workspace_id=os.getenv("ANTHROPIC_WORKSPACE_ID", DEFAULT_WORKSPACE_ID),
        )

    async def token(self) -> str:
        async with self._lock:
            if self._token is None or time.monotonic() >= self._expires_at - REFRESH_MARGIN_S:
                jwt = await self._mint_jwt()
                self._token, self._expires_at = await self._exchange(jwt)
            return self._token

    def invalidate(self) -> None:
        self._token = None
        self._expires_at = 0.0

    async def _mint_jwt(self) -> str:
        proc = await asyncio.create_subprocess_exec(
            "devin-oidc",
            "token",
            "--audience",
            self._audience,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"devin-oidc failed ({proc.returncode}): {stderr.decode().strip()}")
        return stdout.decode().strip()

    async def _exchange(self, jwt: str) -> tuple[str, float]:
        body = {
            "grant_type": GRANT_TYPE,
            "assertion": jwt,
            "federation_rule_id": self._federation_rule_id,
            "organization_id": self._organization_id,
            "service_account_id": self._service_account_id,
            "workspace_id": self._workspace_id,
        }
        async with httpx.AsyncClient(timeout=30, transport=self._transport) as client:
            resp = await client.post(TOKEN_URL, json=body)
        resp.raise_for_status()
        data = resp.json()
        return data["access_token"], time.monotonic() + float(data.get("expires_in", 118))
