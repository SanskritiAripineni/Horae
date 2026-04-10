Deploy the Python backend to Railway and verify it's healthy.

Steps:
1. Run `git status` to check for uncommitted changes — warn if there are any
2. Run `railway up --detach` to deploy
3. Wait ~30 seconds, then run `curl -s https://ride-backend-production-a1fc.up.railway.app/health`
4. Report success or failure
5. If the health check fails, check `railway logs --latest` for errors
