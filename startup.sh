#!/bin/sh
set -e

# Inject credentials.json from env var if file is absent
if [ -n "$GOOGLE_CREDENTIALS_JSON" ] && [ ! -f credentials.json ]; then
    printf '%s' "$GOOGLE_CREDENTIALS_JSON" > credentials.json
fi

# Inject calendar OAuth token from base64 env var if file is absent
if [ -n "$CALENDAR_TOKEN_B64" ] && [ ! -f data/tokens/calendar_token.json ]; then
    mkdir -p data/tokens
    printf '%s' "$CALENDAR_TOKEN_B64" | base64 -d > data/tokens/calendar_token.json
fi

exec uvicorn api:app --host 0.0.0.0 --port "${PORT:-8000}"
