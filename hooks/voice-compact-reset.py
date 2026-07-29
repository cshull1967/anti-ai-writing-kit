#!/usr/bin/env python3
"""
PostCompact hook: forget that this session already loaded the Voice DNA rules.

Compaction summarizes the conversation, which can drop the injected rules out of
context. Deleting the session marker makes the next writing request re-inject the
full text instead of pointing back at rules that are no longer there.

Fails open and silent.
"""

import json
import re
import sys
from pathlib import Path

MARKERS = Path.home() / ".claude/hooks/.voice-sessions"


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        sid = payload.get("session_id", "")
        if not sid:
            return 0
        m = MARKERS / re.sub(r"[^A-Za-z0-9_-]", "", sid)[:120]
        m.unlink(missing_ok=True)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
