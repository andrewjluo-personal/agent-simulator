#!/usr/bin/env bash
# Mint a short-lived Anthropic access token via workload identity federation.
# Prints the token to stdout; errors go to stderr. Requires
# ANTHROPIC_FEDERATION_RULE_ID, ANTHROPIC_ORGANIZATION_ID, ANTHROPIC_SERVICE_ACCOUNT_ID.
set -euo pipefail

ANTHROPIC_AUDIENCE="https://api.anthropic.com"
DEVIN_EXCHANGE_URL="https://app.devin.ai/api/oidc/token"
ANTHROPIC_TOKEN_URL="https://api.anthropic.com/v1/oauth/token"
TOKEN_FILE="${DEVIN_OIDC_TOKEN_FILE:-/opt/.devin/oidc_token}"

if command -v devin-oidc >/dev/null 2>&1; then
    jwt="$(devin-oidc token --audience "$ANTHROPIC_AUDIENCE")"
elif [ -r "$TOKEN_FILE" ]; then
    jwt="$(curl -fsS -X POST "$DEVIN_EXCHANGE_URL" \
        --data-urlencode "grant_type=urn:ietf:params:oauth:grant-type:token-exchange" \
        --data-urlencode "subject_token=$(cat "$TOKEN_FILE")" \
        --data-urlencode "subject_token_type=urn:ietf:params:oauth:token-type:jwt" \
        --data-urlencode "audience=$ANTHROPIC_AUDIENCE" \
        --data-urlencode "subject_keys=org_id" \
        | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
else
    echo "error: devin-oidc not on PATH and $TOKEN_FILE unreadable; not in a Devin session" >&2
    exit 1
fi

http_resp="$(JWT="$jwt" python3 -c '
import json, os
body = {
    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
    "assertion": os.environ["JWT"],
    "federation_rule_id": os.environ["ANTHROPIC_FEDERATION_RULE_ID"],
    "organization_id": os.environ["ANTHROPIC_ORGANIZATION_ID"],
    "service_account_id": os.environ["ANTHROPIC_SERVICE_ACCOUNT_ID"],
}
ws = os.environ.get("ANTHROPIC_WORKSPACE_ID") or ""
if ws:
    body["workspace_id"] = ws
print(json.dumps(body))
' | curl -sS -w '\n%{http_code}' -X POST "$ANTHROPIC_TOKEN_URL" \
    -H 'content-type: application/json' -d @-)"

body="${http_resp%$'\n'*}"
code="${http_resp##*$'\n'}"
if [ "$code" != "200" ]; then
    echo "error: Anthropic token endpoint returned $code" >&2
    echo "$body" >&2
    exit 1
fi
printf '%s' "$body" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
