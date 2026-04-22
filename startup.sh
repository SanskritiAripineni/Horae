#!/bin/sh
set -e

# ──────────────────────────────────────────────────────────────────────
# SECURITY NOTE (research-readiness audit, 2026-04-10):
#   - Secrets are written to files with 0600 permissions (owner-only read/write).
#   - No secrets are echoed or logged during injection.
#   - If env vars are present, they are treated as the source of truth and
#     overwrite any stale persistent-volume copies on each boot.
# ──────────────────────────────────────────────────────────────────────

# Inject credentials.json from env var
if [ -n "$GOOGLE_CREDENTIALS_JSON" ]; then
    printf '%s' "$GOOGLE_CREDENTIALS_JSON" > credentials.json
    chmod 600 credentials.json
fi

# Inject calendar OAuth token from base64 env var
if [ -n "$CALENDAR_TOKEN_B64" ]; then
    mkdir -p data/tokens
    printf '%s' "$CALENDAR_TOKEN_B64" | base64 -d > data/tokens/calendar_token.json
    chmod 600 data/tokens/calendar_token.json
fi

exec uvicorn api:app --host 0.0.0.0 --port "${PORT:-8000}"
