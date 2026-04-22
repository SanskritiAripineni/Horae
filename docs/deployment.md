# Deployment Runbook — AutoLife / RIDE Backend

**Service:** FastAPI backend on Railway  
**URL:** `https://ride-backend-production-a1fc.up.railway.app`  
**Health check:** `GET /health` (300 s timeout, ON_FAILURE restart, max 3 retries)  
**Persistent volume:** `/app/data` (user memory, OAuth refresh tokens — must not be deleted)

---

## Table of contents
1. [Prerequisites](#1-prerequisites)
2. [Initial deploy from scratch](#2-initial-deploy-from-scratch)
3. [Routine redeploy](#3-routine-redeploy)
4. [Secret management](#4-secret-management)
5. [Calendar OAuth per-user setup](#5-calendar-oauth-per-user-setup)
6. [Database (Postgres)](#6-database-postgres)
7. [Metabase analytics dashboard](#7-metabase-analytics-dashboard)
8. [Persistent volume](#8-persistent-volume)
9. [Rollback](#9-rollback)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

Install the Railway CLI and log in once:
```bash
npm install -g @railway/cli
railway login
```

Confirm you're linked to the right project:
```bash
railway status          # should show project "ride-backend" or similar
railway environment     # should show "production"
```

---

## 2. Initial deploy from scratch

### 2.1 Create the Railway project
```bash
railway init
# Choose "Empty project", name it "ride-backend"
```

### 2.2 Add a Postgres database
In the Railway dashboard → **New Service → Database → PostgreSQL**. Railway auto-injects `DATABASE_URL` into all services in the same project.

### 2.3 Add the persistent volume
In the Railway dashboard → select the web service → **Volumes → Add Volume**:
- Mount path: `/app/data`
- This directory stores user memory files (`data/memory/`) and OAuth refresh tokens (`data/tokens/`). **Never delete this volume** — it would wipe all user preferences and force every user to re-authenticate calendar.

### 2.4 Set environment variables
See [§4 Secret management](#4-secret-management) for the full list.

### 2.5 First deploy
```bash
railway up --detach
```
Watch logs: `railway logs --tail`

### 2.6 Verify
```bash
curl https://ride-backend-production-a1fc.up.railway.app/health
# Expected: {"status": "ok"}
```

---

## 3. Routine redeploy

```bash
# From the project root (Multi-Agent-LLM/)
railway up --detach
```

After ~2 minutes:
```bash
curl https://ride-backend-production-a1fc.up.railway.app/health
```

The `/app/data` volume persists across redeploys — user memory and OAuth tokens survive automatically.

---

## 4. Secret management

Set each variable in the Railway dashboard (**Variables** tab) or with the CLI:
```bash
railway variables set KEY=value
```

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | ✅ | Gemini API key (Google AI Studio) |
| `DATABASE_URL` | ✅ | Injected automatically by Railway Postgres |
| `GOOGLE_CREDENTIALS_JSON` | ✅ | Full JSON of the Google OAuth2 web client credentials (from Cloud Console). `startup.sh` writes this to `credentials.json` at boot. |
| `CALENDAR_TOKEN_B64` | ⚠️ legacy | Base64-encoded OAuth token for the **default/service** user. Only needed if no users have completed per-user OAuth. Generate with: `base64 -w0 data/tokens/calendar_token.json` |
| `OAUTH_REDIRECT_URI` | ✅ for OAuth | The callback URL registered in Google Cloud Console. Example: `https://ride-backend-production-a1fc.up.railway.app/api/oauth/callback` |
| `MAPS_API_KEY` | optional | Google Static Maps (map image in journal UI) |

### Rotating GEMINI_API_KEY
1. Generate a new key in Google AI Studio
2. `railway variables set GEMINI_API_KEY=<new-key>`
3. `railway up --detach` (the service restarts automatically on variable change)

### Rotating GOOGLE_CREDENTIALS_JSON
1. Download fresh `credentials.json` from Google Cloud Console (OAuth 2.0 → Web application)
2. `railway variables set GOOGLE_CREDENTIALS_JSON="$(cat credentials.json)"`
3. Redeploy — `startup.sh` rewrites `/app/credentials.json` on boot

---

## 5. Calendar OAuth per-user setup

Each research participant needs to connect their Google Calendar once. The flow:

### 5.1 Google Cloud Console setup (one-time)
1. Go to [console.cloud.google.com](https://console.cloud.google.com) → **APIs & Services → Credentials**
2. Create an **OAuth 2.0 Client ID** → type: **Web application**
3. Add authorized redirect URI: `https://ride-backend-production-a1fc.up.railway.app/api/oauth/callback`
4. Download the JSON and set `GOOGLE_CREDENTIALS_JSON` (see §4)
5. Set `OAUTH_REDIRECT_URI=https://ride-backend-production-a1fc.up.railway.app/api/oauth/callback`

### 5.2 Per-user OAuth flow
Each user's `user_id` is their device-generated ID (UUID or similar).

**Step 1 — Get the authorization URL:**
```bash
curl "https://ride-backend-production-a1fc.up.railway.app/api/oauth/authorize?user_id=<USER_ID>"
# Returns: {"auth_url": "https://accounts.google.com/o/oauth2/...", "state": "<USER_ID>"}
```

**Step 2 — User visits the URL** in a browser and authorizes the RIDE Agent app.

**Step 3 — Google redirects** to `/api/oauth/callback?code=...&state=<USER_ID>`. The server:
- Exchanges the code for tokens
- Stores them at `/app/data/tokens/<USER_ID>/calendar_token.json`
- Returns `{"status": "connected", "user_id": "<USER_ID>"}`

Tokens auto-refresh and are persisted on the Railway volume. Users only need to re-authorize if they explicitly revoke access.

### 5.3 Verifying a user's calendar connection
```bash
# POST a minimal journal payload — if calendar reads succeed, the pipeline runs
curl -X POST https://ride-backend-production-a1fc.up.railway.app/api/process_journals \
  -H "Content-Type: application/json" \
  -d '{"journals": [], "user_id": "<USER_ID>"}'
```
Check `railway logs --tail` for `"Google Calendar & Tasks API connected"`.

---

## 6. Database (Postgres)

Railway manages the Postgres instance. `DATABASE_URL` is injected automatically.

### Schema migrations
The schema is created/migrated by `db.init_schema()` which runs at every startup via the `lifespan` hook in `api.py`. All `CREATE TABLE IF NOT EXISTS` — safe to re-run. **No separate migration tool needed.**

Tables:
| Table | Description |
|-------|-------------|
| `users` | Anonymised user registry (SHA-256 hashed IDs) |
| `enrollments` | Study consent audit trail |
| `journal_sessions` | Pipeline run records |
| `wellbeing_assessments` | Risk level + concerns per session |
| `recommendations` | Proposed schedule changes |
| `calendar_proposals` | Applied/rejected calendar changes |
| `raw_journals` | Deduped journal content |

### Connecting directly (for research queries)
```bash
railway connect postgres   # opens a psql shell
```

Or use the `DATABASE_URL` from `railway variables` with any Postgres client (e.g. Metabase, DataGrip).

---

## 7. Metabase analytics dashboard

Metabase is a separate Railway service in the same project, connected to the same Postgres instance.

- **URL:** Check the Railway dashboard for the Metabase service URL
- **DB connection:** Uses the same `DATABASE_URL` as the backend
- **Accessing dashboards:** Log in with the admin credentials stored in Railway variables for the Metabase service

To add a new chart: Questions → New Question → select the `ride-backend` database → query any table.

Key researcher dashboards:
- **Enrollment count** — `SELECT COUNT(*) FROM enrollments WHERE study_id = 'RIDE_2026'`
- **Daily active users** — `SELECT DATE(enrolled_at), COUNT(DISTINCT anon_id) FROM journal_sessions GROUP BY 1`
- **Risk distribution** — `SELECT risk_level, COUNT(*) FROM wellbeing_assessments GROUP BY 1`

---

## 8. Persistent volume

The `/app/data` volume on Railway holds:
```
/app/data/
├── memory/
│   ├── preferences/{user_id}.json      # User goal preferences
│   └── health_history/{user_id}.json   # Wellbeing trend history
├── tokens/
│   ├── calendar_token.json              # Legacy default-user token
│   └── {user_id}/
│       └── calendar_token.json          # Per-user OAuth tokens
└── wellbeing_feedback/
    └── default.jsonl                    # Suggestion accept/reject log
```

**Never delete the volume.** If you need to wipe a specific user:
```bash
railway run -- rm -rf /app/data/memory/preferences/<USER_ID>.json
railway run -- rm -rf /app/data/tokens/<USER_ID>/
```

---

## 9. Rollback

```bash
# List recent deployments
railway deployments list

# Redeploy a specific deployment ID
railway deployments rollback <DEPLOYMENT_ID>
```

Or revert the git commit and `railway up --detach`.

---

## 10. Troubleshooting

### API not responding
```bash
curl https://ride-backend-production-a1fc.up.railway.app/health
railway logs --tail
```

### Calendar OAuth fails for a user
1. Check `railway logs --tail` for `"Token refresh failed"` or `"credentials.json not found"`
2. Verify `GOOGLE_CREDENTIALS_JSON` is set and `OAUTH_REDIRECT_URI` matches the Cloud Console registered URI
3. If the token is expired and refresh fails, delete the user's token file and re-run OAuth:
   ```bash
   railway run -- rm /app/data/tokens/<USER_ID>/calendar_token.json
   ```

### Postgres connection errors
- `DATABASE_URL` is auto-injected — check that the Postgres service is running in Railway dashboard
- The API degrades gracefully if Postgres is down (DB functions no-op; pipeline still works)

### Gemini API errors
- Check `GEMINI_API_KEY` is valid: `railway variables`
- Model: `gemini-2.0-flash` (or as configured in `config.py`) — verify quota in Google AI Studio

### Container crashes on startup
```bash
railway logs --tail --since 10m
```
Common causes:
- Missing `GEMINI_API_KEY`
- `GOOGLE_CREDENTIALS_JSON` malformed (verify it's valid JSON before setting)
- ChromaDB collection missing (should be baked into image via `vectordb/chroma_db/`)

### Inspecting files on the volume
```bash
railway run -- ls /app/data/tokens/
railway run -- cat /app/data/memory/preferences/default.json
```
