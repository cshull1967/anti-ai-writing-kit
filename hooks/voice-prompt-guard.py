#!/usr/bin/env python3
"""
UserPromptSubmit hook: when the user asks for prose, order the model to read the
Voice DNA rules and audit against them before replying.

The failure this fixes: the rules file is never in context, so following it
depends on the model deciding to go read 500 lines first. This puts the
instruction in front of the model on every writing request, whether or not
anyone remembers to ask.

Why it points at the file instead of pasting it: the rules run to tens of KB.
Claude Code caps injected additionalContext at ~2KB, spills the rest to a file,
and shows the model a preview. Section 3F and everything after it never arrived,
and the model drafted anyway because the top of the block looked like rules. A
short instruction always lands whole, and a Read of the live file puts every
line in context.

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

# One marker per session. First writing request gets the full read-the-file
# order; later ones get a short reminder, because by then the rules are already
# sitting in the context. A PostCompact hook deletes the marker, so the next
# writing request after a compaction orders a fresh read instead of trusting
# rules that got summarized away.
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
The user has asked for prose. Their Voice DNA rules govern it. The rules are not
optional and they are not a style suggestion; the user audits against them and
counts violations.

STEP 0, before you draft a single sentence: use the Read tool on
{rules}
and read the whole file. It runs to hundreds of lines. Read all of it, including
the negative-parallelism section (3F) and section 4, which sit near the end. Do
not work from memory, from a summary, or from a truncated preview of these rules.
If you have not read the file in this session, you do not know the rules.

Then:

1. Write the draft.
2. Save it to a file and run:
   python3 ~/.claude/skills/voice-audit/check.py <file>
   That catches banned words and phrases (parsed live from the rules file),
   em dashes, emoji, and the literal negative-parallelism patterns. Fix every
   HARD FAIL. Judge each JUDGMENT CANDIDATE on context.
3. A clean script run is half the audit. The script only matches literal
   patterns, so a 3F reframe in different words sails through it. Read your own
   draft line by line against the rules you just read: negative parallelism in
   disguise, contrast-flip pairs, fake-profound closers, punchy summary tags,
   metronome rhythm, gerund subjects, "gets [verbed]" passives, abstract nouns
   doing human work, premise payoff, validation statements. The voice-audit
   skill (~/.claude/skills/voice-audit/SKILL.md) has the full checklist.
4. Show them the corrected version only. Do not show a draft, then an audit,
   then a fix. One clean version, with a short note on what the audit changed.

If the request is short enough that a file feels like overkill, still read the
rules and still do the line-by-line pass. They govern a single sentence in a
chat reply exactly as much as they govern a client blog post.
</voice-dna-enforcement>
"""

REMINDER = """\
<voice-dna-enforcement>
The user has asked for prose again. Same requirement as earlier in this session.

If you have already read
{rules}
in this session and it is still in your context, work from it. If it is not, or
you are unsure, Read the whole file again now, before drafting. Never guess at
these rules or work from a summary of them.

Then: draft it, run python3 ~/.claude/skills/voice-audit/check.py <file> and
clear every HARD FAIL, do the line-by-line judgment pass for the patterns the
script cannot match, and show them the corrected version only.
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

    if not RULES.exists():
        return 0

    template = INSTRUCTION if mark(payload.get("session_id", "")) else REMINDER
    context = template.format(rules=RULES)

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
