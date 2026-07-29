#!/usr/bin/env python3
"""
PostToolUse(Edit|Write) hook: block saves of prose that breaks your Voice DNA.

OFF BY DEFAULT. It does nothing until you list folders to watch in
~/.claude/voice/config.json. See the README section "Turning on the file guard".

Why it exists: the prompt hook only fires when your message contains a writing
word. Say "do the next batch for that client" and nothing trips. This is the
second net. It reads the same rules file, so there is one list to maintain.

Blocks (exit 2) on HARD fails only. Judgment candidates never block, because
rule-of-three and gerund-subject hits need a human read.

Fails OPEN. Any error exits 0, because a broken guard must never block writing.
"""

import fnmatch
import json
import subprocess
import sys
import tempfile
from pathlib import Path

CONFIG = Path.home() / ".claude/voice/config.json"
CHECKER = Path.home() / ".claude/skills/voice-audit/check.py"

DEFAULTS = {
    "watch": [],                       # empty = guard is off
    "exclude": [
        "**/reference/**", "**/raw/**", "**/archives/**", "**/node_modules/**",
        "**/.git/**", "**/skills/**", "**/prompts/**",
        "**/anti-ai-writing-style*", "**/banned-terms*", "**/allowed-terms*",
    ],
    "extensions": [".md", ".markdown", ".txt"],
    "allowed_terms": [],               # words the rules ban that are fine for you
    "banned_terms": [],                # extra words to ban beyond the rules file
}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        user = json.loads(CONFIG.read_text(encoding="utf-8"))
        for k, v in user.items():
            if k in cfg:
                cfg[k] = v
    except Exception:
        pass
    return cfg


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0

    ti = payload.get("tool_input") or {}
    fp = ti.get("file_path") or ""
    if not fp:
        return 0

    cfg = load_config()
    if not cfg["watch"]:
        return 0                                    # guard not turned on

    if Path(fp).suffix.lower() not in {e.lower() for e in cfg["extensions"]}:
        return 0
    if any(fnmatch.fnmatch(fp, pat) for pat in cfg["exclude"]):
        return 0
    if not any(fnmatch.fnmatch(fp, pat) for pat in cfg["watch"]):
        return 0

    text = ti.get("content") or ti.get("new_string") or ""
    if not text.strip() or not CHECKER.exists():
        return 0

    try:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                         encoding="utf-8") as tf:
            tf.write(text)
            tmp = tf.name
        proc = subprocess.run(["python3", str(CHECKER), tmp, "--json"],
                              capture_output=True, text=True, timeout=20)
        Path(tmp).unlink(missing_ok=True)
        findings = json.loads(proc.stdout).get("findings", [])
    except Exception:
        return 0

    allowed = {t.lower() for t in cfg["allowed_terms"]}
    hits = [f for f in findings
            if f.get("severity") == "HARD"
            and f.get("match", "").lower().strip() not in allowed]

    low = text.lower()
    for term in cfg["banned_terms"]:
        if term.lower() in low:
            hits.append({"rule": "your extra banned term", "match": term,
                         "line": "?", "context": ""})

    if not hits:
        return 0

    out = [f"VOICE-GUARD: {len(hits)} banned item(s) in {fp}",
           "Source: your rules file, read live.", ""]
    seen = set()
    for h in hits:
        key = (h.get("rule"), h.get("match"))
        if key in seen:
            continue
        seen.add(key)
        out.append(f"  L{h.get('line')} [{h.get('rule')}] -> {h.get('match')!r}")
        if h.get("context"):
            out.append(f"        {h['context']}")
    out += ["", "Rewrite to remove these, then save again.",
            'If a word is legitimate for your field, add it to "allowed_terms" '
            f"in {CONFIG}."]
    print("\n".join(out), file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
