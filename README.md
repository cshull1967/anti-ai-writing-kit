# Anti-AI writing kit

Stop Claude writing like Claude.

This installs a set of writing rules into Claude Code, plus the machinery that
makes Claude actually follow them instead of forgetting they exist. Em dashes,
"delve", "it's not X, it's Y", the fake-profound closing line: all caught before
you ever see the draft.

You get a starting set of rules. Edit them until they sound like you.

## Why this exists

Telling Claude "follow my style guide" doesn't work for long. The guide sits in
a file, Claude has a note saying the file exists, and following it means deciding
to go read 500 lines before writing a sentence. In a long session that decision
loses to everything else going on.

So the rules load automatically instead. When you ask for writing of any kind,
your rules go into the conversation before Claude writes a word, along with
instructions to check the draft against them and fix it before showing you.

## What you need

Claude Code, and Python 3. Python already ships with macOS and Linux. On Windows,
install it from python.org if you don't have it.

## Install

**Easiest: let Claude do it.** Open Claude Code and paste this:

```
Install the anti-AI writing kit from https://github.com/cshull1967/anti-ai-writing-kit
Clone or download it somewhere sensible, run install.py, and tell me what changed.
```

**Or do it yourself.** Download the repo (green "Code" button, then "Download
ZIP"), unzip it, then in Terminal:

```bash
cd ~/Downloads/anti-ai-writing-kit-main
python3 install.py
```

Either way, restart Claude Code afterwards, or open `/hooks` once so it notices
the change.

## What gets installed

```
~/.claude/voice/anti-ai-writing-style.md   your rules, edit this
~/.claude/voice/config.json                settings for the file guard
~/.claude/skills/voice-audit/              the /voice-audit command
~/.claude/hooks/voice-prompt-guard.py      loads the rules when you ask for writing
~/.claude/hooks/voice-compact-reset.py     reloads them after a long chat compacts
~/.claude/hooks/voice-guard.py             blocks bad saves (off by default)
```

Your `settings.json` gets two or three hook entries added. It's backed up first,
anything already in it stays exactly as it was, and running the installer twice
does nothing the second time.

## Using it

Ask Claude to write anything. The rules load on their own and the draft gets
checked before it reaches you.

To check writing you already have:

```
/voice-audit
```

Then paste the text or point at a file. Works on anything, including writing
Claude produced earlier in the conversation.

To run the checker straight from Terminal:

```bash
python3 ~/.claude/skills/voice-audit/check.py yourfile.md
```

It reports HARD FAILS, which are absolute, and JUDGMENT CANDIDATES, which need
a human read.

## Making the rules yours

Edit `~/.claude/voice/anti-ai-writing-style.md`. The one shipped here belongs to
a working B2B marketer, so it bans things you may not care about and misses
things you do.

The checker reads that file every time it runs. Add a word to the banned list and
it's enforced on your next message. There's no second list anywhere, and nothing
to recompile.

Three formats it understands:

- The long comma-separated list in section 3A, for single words
- A bullet in sections 3B through 3E, with the phrase in quotes
- A line anywhere reading `**Also banned: "your phrase."**`

## Turning on the file guard

The prompt hook fires on words like "write", "draft", "post", "email". Say
something like "do the next batch for that client" and nothing trips, because
there's no writing word in it.

The file guard covers that gap by checking files as they're saved. It's off until
you tell it what to watch. Edit `~/.claude/voice/config.json`:

```json
{
  "watch": ["*/Documents/client-work/*/content/*"],
  "allowed_terms": ["leverage"],
  "banned_terms": ["synergize"]
}
```

`watch` takes path patterns. `allowed_terms` are words the rules ban that are
normal in your field, so a finance writer can keep "leverage". `banned_terms` are
extra words to ban beyond the rules file.

When it blocks a save, Claude sees the reason and fixes it. Source material,
transcripts, and reference folders are skipped by default, since quoting someone
else's banned words is the whole point of a transcript.

## What this does and doesn't catch

Reliably caught: em dashes, emoji, every banned word and phrase, and the literal
"this isn't X, it's Y" constructions. Those are mechanical.

Needs a human: rhythm, whether a closing line is trying too hard, whether an
abstract noun is doing work a person should be doing. Claude checks these every
time and will still miss some. You'll still read the draft. What changes is that
your attention goes to whether the writing is any good instead of counting
em dashes.

## Uninstall

```bash
python3 install.py --uninstall
```

Removes the hooks and the skill, backs up settings.json again on the way out, and
leaves your rules file alone in case you want it.

## Credit

The rules file grew out of a lot of drafts that got rewritten until they stopped
sounding like a machine. Sections 3F, 4A through 4Z, and the anti-overfitting
guide in section 5 are the parts worth reading first.

MIT licensed. Take it, change it, share it.
