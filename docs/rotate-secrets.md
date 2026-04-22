# Secret Rotation Guide

## Secrets inventory

| Secret | Where to rotate | Local files affected |
|--------|----------------|----------------------|
| Gemini API Key | [GCP Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials) | `.env`, `local.properties`, `iosApp/AutoLife/Info.plist` |
| Maps API Key | Same GCP Console page (currently same key as Gemini) | same as above |
| Google OAuth client secret | Same GCP Console page → OAuth 2.0 Client IDs → Download JSON | `credentials.json` (local + Railway `GOOGLE_CREDENTIALS_JSON` env var) |
| Anthropic API Key | [Anthropic Console → API Keys](https://console.anthropic.com/settings/keys) | `.env` |
| Railway Postgres password | Railway dashboard → your Postgres service → Credentials → Rotate | `.env` (`DATABASE_URL`) |

---

## Rotation steps

### 1. Gemini / Maps API Key (GCP)
1. Open [GCP Credentials](https://console.cloud.google.com/apis/credentials)
2. Find the key → **Edit** → **Regenerate key** (or delete and create new)
3. Apply **API restrictions**: Gemini API + Maps Static API
4. Apply **App restrictions**: Android (your SHA-1 + package) and/or iOS bundle ID
5. Copy the new key value

### 2. Google OAuth client secret
1. Open [GCP Credentials](https://console.cloud.google.com/apis/credentials) → OAuth 2.0 Client IDs
2. Click the client → **Reset secret**
3. **Download JSON** → save as `credentials.json` locally
4. Base64-encode and update Railway: `base64 -i credentials.json | railway variables set GOOGLE_CREDENTIALS_JSON=-`
   > Or paste the raw JSON into Railway `GOOGLE_CREDENTIALS_JSON` env var directly.

### 3. Anthropic API Key
1. Open [Anthropic Console](https://console.anthropic.com/settings/keys)
2. Archive the old key, create a new one
3. Update `.env` and any CI/CD secrets

### 4. Railway Postgres password
1. Railway dashboard → your project → Postgres service → **Credentials** tab → **Rotate password**
2. Copy the new `DATABASE_URL` string

---

## Replace all local files in one command

After rotating, set the new values as shell variables and run the script below.
**Do not commit this command to git.**

```bash
# Fill in your NEW values here:
NEW_GEMINI_KEY="AIzaSy_NEW_KEY_HERE"
NEW_MAPS_KEY="AIzaSy_NEW_KEY_HERE"      # same as Gemini if sharing one key
NEW_ANTHROPIC_KEY="sk-ant-api03-NEW_KEY_HERE"
NEW_POSTGRES_URL="postgresql://user:NEW_PASS@host/db"

# ── .env ──────────────────────────────────────────────────────────────
sed -i '' \
  "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=${NEW_GEMINI_KEY}|" \
  "s|^MAPS_API_KEY=.*|MAPS_API_KEY=${NEW_MAPS_KEY}|" \
  "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=${NEW_ANTHROPIC_KEY}|" \
  "s|^DATABASE_URL=.*|DATABASE_URL=${NEW_POSTGRES_URL}|" \
  .env

# ── local.properties ──────────────────────────────────────────────────
sed -i '' \
  "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=${NEW_GEMINI_KEY}|" \
  "s|^MAPS_API_KEY=.*|MAPS_API_KEY=${NEW_MAPS_KEY}|" \
  autolife_android_client/local.properties

# ── iOS Info.plist (interim until H1 xcconfig fix lands) ──────────────
sed -i '' \
  "s|<string>AIzaSy[A-Za-z0-9_-]*</string>|<string>${NEW_GEMINI_KEY}</string>|g" \
  autolife_android_client/iosApp/AutoLife/Info.plist

echo "Done. Verify with: grep -n 'AIzaSy\|sk-ant\|GOCSPX' .env local.properties autolife_android_client/iosApp/AutoLife/Info.plist"
```

### Update Railway env vars

```bash
railway variables set \
  GEMINI_API_KEY="${NEW_GEMINI_KEY}" \
  MAPS_API_KEY="${NEW_MAPS_KEY}"
# GOOGLE_CREDENTIALS_JSON and CALENDAR_TOKEN_B64 are updated via the OAuth steps above.
# DATABASE_URL is managed by Railway's Postgres service — use the dashboard to rotate.
```

---

## After rotation checklist

- [ ] Old Gemini key revoked in GCP Console
- [ ] Old OAuth client secret reset in GCP Console
- [ ] Old Anthropic key archived
- [ ] `.env` updated and tested locally (`python -c "from api import app"`)
- [ ] `local.properties` updated and Android build succeeds
- [ ] `Info.plist` updated (new key value, until xcconfig fix)
- [ ] Railway env vars updated (`railway variables` to verify)
- [ ] `GOOGLE_CREDENTIALS_JSON` updated on Railway with new `credentials.json`
- [ ] Backend health check passes: `curl https://ride-backend-production-a1fc.up.railway.app/health`
