#!/bin/sh
set -e

# ──────────────────────────────────────────────────────────────────────
# SECURITY NOTE (research-readiness audit, 2026-04-10):
#   - Secrets are written to files with 0600 permissions (owner-only read/write).
#   - No secrets are echoed or logged during injection.
#   - If a file already exists we skip re-creation to avoid overwriting
#     a persistent-volume copy with a stale env-var value.
# ──────────────────────────────────────────────────────────────────────

# Inject credentials.json from env var if file is absent
if [ -n "$GOOGLE_CREDENTIALS_JSON" ] && [ ! -f credentials.json ]; then
    printf '%s' "$GOOGLE_CREDENTIALS_JSON" > credentials.json
    chmod 600 credentials.json
fi

# Inject calendar OAuth token from base64 env var if file is absent
if [ -n "$CALENDAR_TOKEN_B64" ] && [ ! -f data/tokens/calendar_token.json ]; then
    mkdir -p data/tokens
    printf '%s' "$CALENDAR_TOKEN_B64" | base64 -d > data/tokens/calendar_token.json
    chmod 600 data/tokens/calendar_token.json
fi

exec uvicorn api:app --host 0.0.0.0 --port "${PORT:-8000}"
