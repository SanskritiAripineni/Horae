#!/bin/bash
# PreCompact hook: remind Claude to preserve critical context before compacting
cat <<'JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "PreCompact",
    "additionalContext": "BEFORE COMPACTING — preserve these in the summary:\n1. Current task and progress (what's done, what's remaining)\n2. Any build errors or test failures being debugged\n3. Which files were edited and why\n4. Cross-platform state: did Android build? Did iOS build? Both need to stay in sync.\n5. Backend state: is the local server running? Any DB migration in progress?\n6. If editing KMP shared code, note which platform actuals still need updating."
  }
}
JSON
