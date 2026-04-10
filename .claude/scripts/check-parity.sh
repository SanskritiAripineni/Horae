#!/bin/bash
# PostToolUse hook: when editing KMP shared/composeApp files, remind about cross-platform parity
# Fires on Write|Edit of .kt files in shared/ or composeApp/

FILE=$(jq -r '.tool_input.file_path // .tool_response.filePath // empty' 2>/dev/null)
[ -z "$FILE" ] && exit 0

# Only care about Kotlin files in the KMP modules
case "$FILE" in
  */shared/src/androidMain/*|*/shared/src/iosMain/*)
    # Platform-specific expect/actual — check if the counterpart exists
    OTHER=""
    if echo "$FILE" | grep -q "androidMain"; then
      OTHER=$(echo "$FILE" | sed 's|androidMain|iosMain|')
    else
      OTHER=$(echo "$FILE" | sed 's|iosMain|androidMain|')
    fi
    # Only alert if the counterpart directory exists (the module has the other platform)
    OTHER_DIR=$(dirname "$OTHER")
    if [ -d "$OTHER_DIR" ] && [ ! -f "$OTHER" ]; then
      echo "{\"hookSpecificOutput\":{\"hookEventName\":\"PostToolUse\",\"additionalContext\":\"WARNING: Platform-specific file edited but counterpart missing. Check if $OTHER needs a matching actual implementation.\"}}"
    fi
    ;;
  */composeApp/src/commonMain/*/platform/*)
    # Editing platform expects — both actuals may need updating
    echo "{\"hookSpecificOutput\":{\"hookEventName\":\"PostToolUse\",\"additionalContext\":\"You edited a platform expect file. Verify both androidMain and iosMain actual implementations are updated to match.\"}}"
    ;;
esac
exit 0
