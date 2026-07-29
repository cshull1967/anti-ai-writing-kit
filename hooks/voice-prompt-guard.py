#!/usr/bin/env python3
"""
UserPromptSubmit hook: when the user asks for prose, load the Voice DNA rules into
context and instruct an audit before replying.

The failure this fixes: the rules file is never in context, so following it
depends on the model deciding to go read 500 lines first. This puts the rules
in front of the model on every writing request, whether or not anyone remembers
to ask.

Fires only on writing requests. Skips code requests so a "write a python script"
prompt doesn't drag 30KB of prose rules along with it.

Fails open. Any error exits 0 with no output, because a broken hook must never
block a prompt.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

def rules_path():
    """Your rules file. Override with VOICE_DNA_RULES if you keep it elsewhere."""
    env = os.environ.get("VOICE_DNA_RULES")
    if env and Path(env).expanduser().exists():
        return Path(env).expanduser()
    return Path.home() / ".claude/voice/anti-ai-writing-style.md"


RULES = rules_path()

# One marker per session. First writing request gets the full rules; later ones
# get a short pointer, because the rules are already sitting in the context.
# A PostCompact hook deletes the marker, so the next writing request after a
# compaction re-injects the full text instead of pointing at rules that got
# summarized away.
MARKERS = Path.home() / ".claude/hooks/.voice-sessions"

# Asking for prose.
WRITING = re.compile(r"""(?ix)
    \b(
      write|writing|draft(ing|ed)?|rewrite|re-write|rewor(d|k)|revise|edit\ (this|that|the)
      |polish|tighten|punch\ up|clean\ up\ (this|the)\ (copy|text|draft|wording)
      |blog|article|post|linkedin|newsletter|email|e-mail|caption|carousel
      |headline|subject\ line|tagline|landing\ page|web\ copy|copy\ for
      |proposal|sow|scope\ of\ work|case\ study|memo|summary\ for|one.?pager
      |press\ release|bio|about\ page|testimonial|script\ for\ (a\ )?(video|reel)
      |sound(s)?\ like\ ai|de-?ai|voice\ check|audit\ this
    )\b
""")

# Asking for code. Only suppresses when no prose signal is present.
CODE = re.compile(r"""(?ix)
    \b(
      script|function|class|method|regex|json|yaml|sql|query|schema|api|endpoint
      |python|javascript|typescript|bash|shell|css|html|php|react|component
      |bug|error|traceback|stack\ trace|refactor|debug|install|deploy|commit
    )\b
""")

PROSE_ANCHOR = re.compile(r"""(?ix)
    \b(
      blog|article|post|linkedin|newsletter|email|caption|carousel|headline
      |tagline|copy|proposal|sow|case\ study|memo|press\ release|bio
      |voice|tone|sound(s)?\ like\ ai|audience|reader
      |video|reel|explainer|webinar|podcast|talk|slide|deck|narration|voiceover
    )\b
""")

INSTRUCTION = """\
<voice-dna-enforcement>
The user has asked for prose. Their Voice DNA rules are below, in full. They are not
optional and they are not a style suggestion; they audit against them and count
violations.

Before you show her anything you have written:

1. Write the draft.
2. Save it to a file and run:
   python3 ~/.claude/skills/voice-audit/check.py <file>
   That catches banned words and phrases (parsed live from the rules file),
   em dashes, emoji, and the literal negative-parallelism patterns. Fix every
   HARD FAIL. Judge each JUDGMENT CANDIDATE on context.
3. Do the judgment pass the script cannot do: negative parallelism in disguise,
   fake-profound closing lines, metronome rhythm, abstract nouns doing human
   work, premise payoff, validation statements. The voice-audit skill
   (~/.claude/skills/voice-audit/SKILL.md) has the full checklist.
4. Show them the corrected version only. Do not show a draft, then an audit,
   then a fix. One clean version, with a short note on what the audit changed.

If the request is short enough that a file feels like overkill, still apply the
rules and still do the judgment pass. The rules govern a single sentence in a
chat reply exactly as much as they govern a client blog post.

The rules follow.
</voice-dna-enforcement>

"""

REMINDER = """\
<voice-dna-enforcement>
The user has asked for prose again. The full Voice DNA rules were injected earlier
in this session, so they are not repeated here.

Same requirement as before: draft it, run
python3 ~/.claude/skills/voice-audit/check.py <file> and clear every HARD FAIL,
do the judgment pass for what the script cannot see, then show them the corrected
version only.

If you cannot actually see the rules anywhere in your current context, do not
guess at them. Read the rules file at ~/.claude/voice/anti-ai-writing-style.md
before you draft.
</voice-dna-enforcement>
"""


def mark(session_id):
    """Record that this session already got the full rules. Returns True if
    this is the first time. Fails toward injecting the full text."""
    if not session_id:
        return True
    try:
        MARKERS.mkdir(parents=True, exist_ok=True)
        cutoff = time.time() - 7 * 86400
        for old in MARKERS.iterdir():
            if old.stat().st_mtime < cutoff:
                old.unlink(missing_ok=True)
        m = MARKERS / re.sub(r"[^A-Za-z0-9_-]", "", session_id)[:120]
        if m.exists():
            return False
        m.touch()
        return True
    except Exception:
        return True


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        prompt = payload.get("prompt", "")
    except Exception:
        return 0

    if not prompt or not WRITING.search(prompt):
        return 0

    # Code request with no prose signal: stay out of the way.
    if CODE.search(prompt) and not PROSE_ANCHOR.search(prompt):
        return 0

    if mark(payload.get("session_id", "")):
        try:
            context = INSTRUCTION + RULES.read_text(encoding="utf-8")
        except Exception:
            return 0
    else:
        context = REMINDER

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        },
        "suppressOutput": True,
    }))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
