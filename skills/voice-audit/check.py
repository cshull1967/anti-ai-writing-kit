#!/usr/bin/env python3
"""
Voice DNA mechanical checker.

Catches the greppable half of anti-ai-writing-style.md: banned vocabulary,
banned phrases, em dashes, emoji, and the literal-enough negative-parallelism
patterns. Everything it can't grep (rhythm, agency, kickers, premise payoff)
is left to the judgment pass in SKILL.md.

Banned terms are parsed OUT of the rules doc at runtime, so adding a rule to
the doc in the existing format automatically arms it here. No second list to
maintain.

Usage:
    python3 check.py draft.md
    cat draft.md | python3 check.py --stdin
    python3 check.py draft.md --rules /path/to/anti-ai-writing-style.md
    python3 check.py draft.md --json

Exit codes: 0 = no hard fails, 1 = hard fails present, 2 = bad input.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


def canonical_rules():
    """Your rules file. Override with the VOICE_DNA_RULES environment variable
    if you keep it somewhere else."""
    env = os.environ.get("VOICE_DNA_RULES")
    if env and Path(env).expanduser().exists():
        return str(Path(env).expanduser())
    return str(Path.home() / ".claude/voice/anti-ai-writing-style.md")


CANONICAL_RULES = canonical_rules()

# ---------------------------------------------------------------- rule parsing

def parse_rules(path):
    """Pull banned vocabulary and phrases out of the Voice DNA doc itself."""
    text = Path(path).read_text(encoding="utf-8")
    words, phrases = set(), set()

    # 3A: the long comma-separated vocabulary line.
    sec_3a = _section(text, "### 3A", "### 3B")
    for line in sec_3a.splitlines():
        if line.count(",") > 15:
            for w in line.split(","):
                w = w.strip().strip(".").lower()
                # skip parenthetical glosses like "landscape (abstract)"
                w = re.sub(r"\s*\(.*?\)", "", w).strip()
                if w and "/" not in w and 2 < len(w) < 30:
                    words.add(w)
            break

    # "**Also banned: "x."**" entries anywhere in the doc.
    for m in re.finditer(r'\*\*Also banned:\s*(.+?)\*\*', text):
        for q in re.findall(r'"([^"]{2,40})"', m.group(1)):
            # commas usually sit inside the quotes ("out loud," "aloud,")
            q = q.strip().strip(".,;:").lower()
            if q:
                (words if " " not in q else phrases).add(q)

    # 3B / 3C / 3D / 3E: quoted phrases in bullet lists.
    for start, end in (("### 3B", "### 3C"), ("### 3C", "### 3D"),
                       ("### 3D", "### 3E"), ("### 3E", "### 3F")):
        for line in _section(text, start, end).splitlines():
            if not line.lstrip().startswith("-"):
                continue
            for q in re.findall(r'"([^"]{3,60})"', line):
                q = q.strip().strip(".,;:").lower()
                # placeholders like "in today's [anything]" -> keep the stem
                q = q.split("[")[0].strip()
                if q and len(q) > 3:
                    phrases.add(q)

    # 4V: the vague-attribution list lives in prose, not bullets.
    sec_4v = _section(text, "### 4V", "### 4W")
    for q in re.findall(r'"([^"]{3,40})"', sec_4v):
        q = q.strip().strip(".,").lower()
        if q and not q.endswith("..") and len(q.split()) <= 5:
            phrases.add(q)

    return sorted(words), sorted(phrases)


def _section(text, start_marker, end_marker):
    i = text.find(start_marker)
    if i == -1:
        return ""
    j = text.find(end_marker, i)
    return text[i:j if j != -1 else len(text)]


# ------------------------------------------------------------ structural rules
# Literal-enough patterns. HARD = absolute per the doc. SOFT = candidate for
# judgment; the model decides using context.

EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F0FF"
    "\U00002190-\U000021FF\U00002B00-\U00002BFF️✅❌❗]"
)

HARD_PATTERNS = [
    ("em dash (§2: NO em dashes)", re.compile(r"—")),
    ("emoji (§2: no emoji)", EMOJI),
    ("3F negative parallelism", re.compile(
        r"(?i)\b(it'?s not (just )?about\b|this isn'?t\b[^.!?]{0,60}\bit'?s\b"
        r"|the question isn'?t\b|you don'?t need\b[^.!?]{0,40}\byou need\b"
        r"|not only\b[^.!?]{0,50}\bbut also\b|less\b \w+, more \w+"
        r"|stop thinking\b[^.!?]{0,40}\bstart thinking\b"
        r"|forget \w+[.,][^.!?]{0,40}\bthis is\b)")),
    ("3F split-sentence negation", re.compile(
        r"(?i)\b(don'?t|doesn'?t|isn'?t|aren'?t|won'?t) (need|want|have to|about) "
        r"[^.!?]{2,60}[.!?]\s+(they|it|you|we|that)('?s| are| do| is)? "
        r"(need|want|is|are|about)\b")),
    ("4M/§1 colon reveal", re.compile(
        r"(?im)^(here'?s the (thing|deal|part)|what it comes down to"
        r"|the (real|key|biggest|honest) (question|problem|insight|point|pitch)"
        r"|why i'?m telling you this|here'?s what works|the result|the takeaway):")),
    # 4CC: bare command + "and" + predicted consequence ("Skip a domain and the
    # city can't defend its decisions"). An if-then in a costume. No exceptions,
    # including for consequences that land on an object rather than on people.
    # Narrowed to omission/error verbs, which is where the construction lives.
    ("4CC pseudo-imperative threat", re.compile(
        r"(?im)(?:^|(?<=[.!?] ))(get (it|this|that) wrong|skip|miss|ignore"
        r"|neglect|forget|overlook|underestimate|botch|rush|delay|guess|assume"
        r"|lose|break|mess up|screw up|cut corners|wait too long|ship)\b"
        r"[^.!?]{0,60}\band\b [^.!?]{2,80}[.!?]")),
]

SOFT_PATTERNS = [
    ("4B rule of three", re.compile(r"\b\w+, \w+,? and \w+\b")),
    ("4Y ‘gets [verbed]’ passive", re.compile(r"(?i)\bgets \w+ed\b")),
    ("4T gerund-as-subject", re.compile(r"(?m)^\s*[A-Z][a-z]+ing\b(?![^.!?]*\bis a\b)")),
    ("4F participle pseudo-analysis", re.compile(
        r"(?i),\s+(highlighting|underscoring|reflecting|showcasing|emphasizing"
        r"|demonstrating|signaling|marking|cementing)\b")),
    ("4J copulative avoidance", re.compile(
        r"(?i)\b(serves as|stands as|represents a|marks a|acts as|functions as)\b")),
    ("§2 sentence case after colon", re.compile(r":\s+[A-Z][a-z]+")),
    ("4L punchy summary tag", re.compile(
        r"(?i)(?:^|(?<=[.!?]) )(that'?s (the|it|all)|welcome to|worth (pausing|noting)"
        r"|there'?s the \w+)\b[^.!?]{0,25}[.!?]")),
    ("4BB rhetorical setup", re.compile(
        r"(?i)\b(what if i told you|think about it|plot twist|consider this)\b")),
]


# The doc bans these only inside a specific construction ("nobody tells you",
# "a real problem"), not as ordinary words. Flag for judgment, never hard-fail.
CONSTRUCTION_ONLY = {"nobody", "real", "really", "most people don't realize"}


def scan(draft_path, text, words, phrases):
    lines = text.splitlines()
    findings = []
    in_fence = False

    for n, raw in enumerate(lines, 1):
        if raw.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or raw.lstrip().startswith(">"):
            continue  # skip code and quoted source material

        low = raw.lower()

        for label, rx in HARD_PATTERNS:
            for m in rx.finditer(raw):
                findings.append(_f("HARD", label, m.group(0), n, raw))

        for label, rx in SOFT_PATTERNS:
            for m in rx.finditer(raw):
                findings.append(_f("SOFT", label, m.group(0), n, raw))

        for w in words:
            if re.search(r"\b" + re.escape(w) + r"(s|es|ed|ing|ly)?\b", low):
                sev = "SOFT" if w in CONSTRUCTION_ONLY else "HARD"
                note = " (only in the banned construction)" if sev == "SOFT" else ""
                findings.append(_f(sev, "3A banned word" + note, w, n, raw))

        for p in phrases:
            if p in low:
                sev = "SOFT" if p in CONSTRUCTION_ONLY else "HARD"
                note = " (only in the banned construction)" if sev == "SOFT" else ""
                findings.append(_f(sev, "3B-3E banned phrase" + note, p, n, raw))

        # 4K title case headers
        if raw.startswith("#"):
            body = raw.lstrip("#").strip()
            caps = [w for w in body.split() if w[:1].isupper()]
            if len(body.split()) > 2 and len(caps) >= len(body.split()) - 1:
                findings.append(_f("SOFT", "4K title case header", body, n, raw))

    # One flag per (line, matched text). A word caught by both the 3A list and
    # a 3B bullet is one problem, not two.
    seen, deduped = set(), []
    for f in findings:
        key = (f["line"], f["match"].lower().strip())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)
    return deduped


def _f(sev, rule, hit, line_no, line):
    return {"severity": sev, "rule": rule, "match": hit,
            "line": line_no, "context": line.strip()[:160]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft", nargs="?")
    ap.add_argument("--stdin", action="store_true")
    ap.add_argument("--rules", default=CANONICAL_RULES)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.stdin:
        text, name = sys.stdin.read(), "(stdin)"
    elif a.draft:
        p = Path(a.draft)
        if not p.exists():
            print(f"No such draft: {p}", file=sys.stderr)
            return 2
        text, name = p.read_text(encoding="utf-8"), str(p)
    else:
        print("Give a draft path or --stdin", file=sys.stderr)
        return 2

    if not Path(a.rules).exists():
        print(f"Rules file missing: {a.rules}", file=sys.stderr)
        return 2

    words, phrases = parse_rules(a.rules)
    findings = scan(name, text, words, phrases)

    if a.json:
        print(json.dumps({"draft": name, "rules_loaded": len(words) + len(phrases),
                          "findings": findings}, indent=2))
    else:
        hard = [f for f in findings if f["severity"] == "HARD"]
        soft = [f for f in findings if f["severity"] == "SOFT"]
        print(f"Draft: {name}")
        print(f"Rules armed from doc: {len(words)} words, {len(phrases)} phrases\n")
        for title, group in (("HARD FAILS", hard), ("JUDGMENT CANDIDATES", soft)):
            print(f"{title} ({len(group)})")
            print("-" * 60)
            for f in group:
                print(f"  L{f['line']:<4} [{f['rule']}] → {f['match']!r}")
                print(f"        {f['context']}")
            print()
        if not findings:
            print("Nothing mechanical. Judgment pass still required.")
    return 1 if any(f["severity"] == "HARD" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
