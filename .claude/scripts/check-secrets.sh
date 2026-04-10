#!/bin/bash
# PostToolUse hook: scan edited/written files for accidentally committed secrets
# Receives JSON on stdin with tool_input.file_path or tool_response.filePath

FILE=$(jq -r '.tool_input.file_path // .tool_response.filePath // empty' 2>/dev/null)
[ -z "$FILE" ] && exit 0
[ ! -f "$FILE" ] && exit 0

# Skip binary/non-text files
file --mime "$FILE" 2>/dev/null | grep -q 'text/' || exit 0

# Patterns that should never appear in committed code
PATTERNS=(
  'AIzaSy[A-Za-z0-9_-]{33}'          # Google API key
  'AKIA[0-9A-Z]{16}'                   # AWS access key
  'sk-[A-Za-z0-9]{32,}'               # OpenAI/Anthropic key
  'ghp_[A-Za-z0-9]{36}'               # GitHub PAT
  'password\s*[:=]\s*["\x27][^"\x27]'  # Hardcoded passwords
)

for pat in "${PATTERNS[@]}"; do
  if grep -qEi "$pat" "$FILE" 2>/dev/null; then
    # Don't block local.properties or .env (they're gitignored)
    case "$FILE" in
      *local.properties|*.env|*.env.*) exit 0 ;;
    esac
    echo "{\"decision\":\"block\",\"reason\":\"Possible secret/API key detected in $FILE. If intentional (test fixture, gitignored file), override manually.\"}"
    exit 0
  fi
done
exit 0
