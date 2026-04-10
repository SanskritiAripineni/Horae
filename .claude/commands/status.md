Give me a quick status overview of everything.

Steps:
1. `git status` — uncommitted changes
2. `git log --oneline -5` — recent commits
3. `git branch` — current branch
4. Check if backend is reachable: `curl -s --max-time 5 https://ride-backend-production-a1fc.up.railway.app/health || echo "Backend unreachable"`
5. Check if an Android device is connected: list devices via android-mcp
6. Summarize: branch, uncommitted files, last commit, backend health, device status
