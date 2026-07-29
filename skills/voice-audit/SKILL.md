---
name: voice-audit
description: >
  Write anything in the user's voice, or audit existing writing against their
  Voice DNA file (anti-ai-writing-style.md). Runs a mechanical checker for banned
  words, phrases, em dashes and emoji, then a judgment pass for the patterns a
  script can't see (negative parallelism, fake-profound kickers, metronome
  rhythm, abstract nouns doing human work). Returns a corrected draft plus what
  changed.

  Trigger this skill whenever the user says anything like:
  "/voice-audit", "audit this", "does this sound like AI", "check this against the
  voice file", "run the voice check", "de-AI this", "rewrite this so it doesn't
  sound like AI", "make this sound like me".

  ALSO trigger it automatically, without being asked, whenever the user asks for
  any prose to be written or rewritten: blog post, email, LinkedIn post, social
  copy, landing page, proposal, case study, strategy doc, internal memo. They
  should never see a draft that has not been through the audit.
---

# Voice audit

## The rule this skill exists to enforce

The user should never be shown a draft that hasn't been audited. Not client copy,
not internal strategy docs, not a paragraph in a chat reply. If you wrote prose
for them, audit it before they read it.

Do not show them the draft, then the audit, then a revision. They read one
version: the corrected one.

## Where things live

```
~/.claude/skills/voice-audit/
├── SKILL.md      ← this file
└── check.py      ← mechanical checker

Rules file: ~/.claude/voice/anti-ai-writing-style.md
            (or wherever $VOICE_DNA_RULES points)
```

`check.py` parses the banned lists out of the rules file at runtime. When the
user adds a rule to that file in the existing format (`**Also banned: "x."**`, a
3B bullet, an entry in the 3A comma list), the checker picks it up with no code
change. Never hardcode banned words into the script.

---

## Mode A: they ask you to write something

1. **Draft it.** Write normally. Don't try to self-censor against 500 lines of
   rules while composing, it produces stiff copy. Get the thinking right first.
2. **Save the draft** to a temp file so the checker can read it.
3. **Run the checker** (Step 1 below).
4. **Run the judgment pass** (Step 2 below).
5. **Rewrite** against every finding.
6. **Re-run the checker** on the rewrite. Repeat until hard fails are 0.
7. **Show them the corrected draft only,** followed by a short list of what the
   audit changed. Keep that list to findings that changed meaning or structure.
   They don't need to see that you swapped one adjective.

## Mode B: they give you existing text to audit

Same steps, starting at 2. The text may be a file path, a pasted block, a
document, or something you wrote earlier in the conversation.

Report findings first in this mode, then the corrected version. They're
auditing, so they want to see what was wrong.

---

## STEP 1: mechanical pass

```bash
python3 ~/.claude/skills/voice-audit/check.py <draft.md>
python3 ~/.claude/skills/voice-audit/check.py <draft.md> --json   # for parsing
cat draft.md | python3 ~/.claude/skills/voice-audit/check.py --stdin
```

Output has two groups:

- **HARD FAILS.** Absolute rules. Em dashes, emoji, banned vocabulary, banned
  phrases, the literal negative-parallelism constructions, colon reveals. Fix
  every one. Exit code 1 means hard fails exist.
- **JUDGMENT CANDIDATES.** Pattern hits that need a human read. Rule of three,
  `gets [verbed]`, gerund-as-subject, title case headers, `serves as`, punchy
  summary tags, and construction-only words (`nobody`, `real`, `really`).
  Decide each on context. A rule-of-three flag on a genuine list of three things
  is fine. Don't mechanically rewrite these.

The checker is roughly half the doc. Passing it means nothing on its own.

## STEP 2: judgment pass

The script can't see any of the following. Read the draft against this list
every time. Quote the offending line, name the section, fix it.

**Structure**
- §3F disguised negative parallelism: "While X might seem right, Y is
  actually...", "Sure, X works. But Y is where...", "X gets all the attention,
  but Y is what actually..."
- §4R the AI mini-essay arc: vague setup, fake stakes, condescending negative
  claim, abstract solution, punchy closer.
- §4AA fake-profound kicker. Check the last line of every section. If it could
  be lifted out and posted on its own, delete it. Don't rewrite it into a better
  metaphor. End on the clearest concrete sentence already in the draft.
- §4X discovered-insight framing: "The biggest X is", "The real problem is",
  "The missing piece is".
- §4U bolded declarative opener followed by the explanation.

**Sentences**
- §6 agency rule. Any abstract noun doing human work ("clarity drives
  execution", "accountability builds trust"). Find the real actor and make it
  the subject. Concrete objects behaving observably ("the model drifts", "the
  dashboard broke") are fine.
- §4Z outcomes named with no action attached: "Every touchpoint ends in a date."
  Name who does what.
- §4V borrowed authority. Cite specifically or assert the claim plainly.
- §1 premise payoff. Cover the first sentence of each paragraph. If the rest
  still reads fine without it, nothing paid it off. Rewrite.
- §1 contrast through callback. Two sentences sitting next to each other with no
  grammatical link read as disconnected even when the logic is sound.

**Texture**
- §4I metronome rhythm. Count sentence lengths in each paragraph. If they're all
  within a few words of each other, break the pattern.
- §2 paragraph length. 1 to 2 sentences default, 3 maximum.
- §4D synonym cycling. If the agent is the agent, call it the agent every time.
- §1 validation statements. If a sentence could go on a motivational poster,
  cut it.
- §1 no colon-label openers, and §4N no "the play / the move / the angle".

**Then the litmus test from §5:** does this sound like something the user would
write, or like a model imitating them? If it feels forced, pull back. The doc
says spirit over letter. Over-applying the rules produces its own tell.

## STEP 3: report

For Mode A, after the corrected draft:

```
Audit: N hard fails, M judgment calls. Changed:
- [§3F] "The question isn't the model, it's the eval" → "The eval matters more than the model"
- [§4AA] cut the closing line, ends on the deployment sentence now
```

For Mode B, lead with the findings table, then give the corrected version.

---

## Deeper audit (only when asked)

If the user says "audit hard", "audit it properly", or the piece is going out
under their name to a client, run the judgment pass as a subagent instead of
inline. Give the subagent the rules file and the draft with no context about who
wrote it or what it's for. A reviewer who didn't compose the draft catches things
the author can't see, because the author already knows what they meant.

Don't do this by default.

## Known limits

State these if the audit result matters:

- The checker reads word boundaries, so it flags a banned word inside a
  hyphenated compound correctly, but it can't tell "a real problem" (banned) from
  "real estate" (fine). That's why those words are judgment candidates.
- It skips fenced code blocks and blockquoted lines, on the assumption that
  quoted source material isn't the user's prose. If they're auditing a doc where
  the blockquotes are their own writing, check those by hand.
- Rhythm, premise payoff, and the agency rule have no mechanical check at all.
  Skipping Step 2 means skipping half the doc.
