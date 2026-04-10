#!/bin/bash
# PostToolUse hook: catch known-bad import patterns in Kotlin and Python files

FILE=$(jq -r '.tool_input.file_path // .tool_response.filePath // empty' 2>/dev/null)
[ -z "$FILE" ] && exit 0
[ ! -f "$FILE" ] && exit 0

WARNINGS=""

case "$FILE" in
  *.kt)
    # Ktor 2.x imports in a Ktor 3.x project
    if grep -q 'io.ktor.client.features' "$FILE" 2>/dev/null; then
      WARNINGS="$WARNINGS Ktor 2.x import detected (io.ktor.client.features). This project uses Ktor 3.x — use io.ktor.client.plugins instead."
    fi
    # Room in commonMain (should only be in androidMain)
    if echo "$FILE" | grep -q "commonMain" && grep -q 'androidx.room' "$FILE" 2>/dev/null; then
      WARNINGS="$WARNINGS Room import in commonMain — Room is Android-only. Use SQLDelight for shared DB code."
    fi
    # String.format in commonMain (not available in KMP)
    if echo "$FILE" | grep -q "commonMain" && grep -q 'String.format' "$FILE" 2>/dev/null; then
      WARNINGS="$WARNINGS String.format() is not available in KMP commonMain. Use DateFormat helpers or string templates."
    fi
    # google-generativeai in shared (conflicts with Ktor 3.x)
    if grep -q 'com.google.ai.client.generativeai' "$FILE" 2>/dev/null; then
      if echo "$FILE" | grep -qE "(shared|composeApp)"; then
        WARNINGS="$WARNINGS google-generativeai SDK detected in KMP module — it bundles Ktor 2.x and conflicts with Ktor 3.x. Use direct REST calls via Ktor instead."
      fi
    fi
    ;;
  *.py)
    # Old google-generativeai import in backend (should use google-genai)
    if grep -q 'import google.generativeai' "$FILE" 2>/dev/null; then
      WARNINGS="$WARNINGS Old google-generativeai import detected. This backend uses google-genai (from google import genai)."
    fi
    ;;
esac

if [ -n "$WARNINGS" ]; then
  # Escape for JSON
  ESCAPED=$(echo "$WARNINGS" | sed 's/"/\\"/g' | tr '\n' ' ')
  echo "{\"hookSpecificOutput\":{\"hookEventName\":\"PostToolUse\",\"additionalContext\":\"IMPORT WARNING:$ESCAPED\"}}"
fi
exit 0
