"""PreToolUse hook: stop Claude's shell commands from touching raw mcPHASES data or secrets.

The Read deny rules in .claude/settings.json only cover Claude's file tools; this covers Bash.
It catches accidents, not a determined workaround. See D18/D19 in docs/decisions.md.
"""

import json
import re
import sys

BLOCKED = [
    (r"data/raw/mcphases", "raw mcPHASES files"),
    (r"MCPHASES_DIR", "the mcPHASES data path"),
    (r"notebooks/mcphases", "the mcPHASES notebook (its outputs may contain rows)"),
    (r"(python|jupyter|nbconvert|papermill)\b.*mcphases", "running mcPHASES analysis"),
    (r"(^|[\s/'\"=<])\.env(?![\w.])", ".env (holds credentials)"),
]

command = json.load(sys.stdin).get("tool_input", {}).get("command", "")
for pattern, what in BLOCKED:
    if re.search(pattern, command, re.IGNORECASE):
        print(
            f"Blocked: this command touches {what}. Claude never reads raw mcPHASES data or "
            "credentials. Write the script and ask the user to run it and share aggregates only.",
            file=sys.stderr,
        )
        sys.exit(2)
