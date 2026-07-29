#!/usr/bin/env python3
"""
Installer for the anti-AI writing kit.

Run:  python3 install.py

Copies the skill, the checker, and the hooks into ~/.claude/, then adds two hook
entries to ~/.claude/settings.json. Your existing settings are preserved: the
file is backed up first, existing hooks are left alone, and running this twice
changes nothing the second time.

Uninstall:  python3 install.py --uninstall
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLAUDE = Path.home() / ".claude"
SETTINGS = CLAUDE / "settings.json"

HOOK_ENTRIES = {
    "UserPromptSubmit": "python3 $HOME/.claude/hooks/voice-prompt-guard.py",
    "PostCompact": "python3 $HOME/.claude/hooks/voice-compact-reset.py",
}
FILE_GUARD = ("PostToolUse", "Edit|Write",
              "python3 $HOME/.claude/hooks/voice-guard.py")


def say(msg):
    print(f"  {msg}")


def install():
    print("\nInstalling the anti-AI writing kit\n" + "=" * 40)

    for sub in ("skills/voice-audit", "hooks", "voice"):
        (CLAUDE / sub).mkdir(parents=True, exist_ok=True)

    # Every skill folder in skills/ gets installed, so dropping a new skill into
    # this repo needs no change here.
    pairs = []
    for skill_dir in sorted(p for p in (HERE / "skills").iterdir() if p.is_dir()):
        target = CLAUDE / "skills" / skill_dir.name
        target.mkdir(parents=True, exist_ok=True)
        pairs += [(f, target / f.name) for f in sorted(skill_dir.iterdir())
                  if f.is_file()]
    pairs += [(f, CLAUDE / "hooks" / f.name)
              for f in sorted((HERE / "hooks").glob("*.py"))]

    for src, dest in pairs:
        shutil.copy2(src, dest)
        if dest.suffix == ".py":
            dest.chmod(0o755)
        say(f"installed {dest.relative_to(Path.home())}")

    # Never overwrite rules the user has already edited.
    rules = CLAUDE / "voice/anti-ai-writing-style.md"
    if rules.exists():
        say("kept your existing rules file (not overwritten)")
    else:
        shutil.copy2(HERE / "voice/anti-ai-writing-style.md", rules)
        say(f"installed {rules.relative_to(Path.home())}  <- edit this one")

    cfg = CLAUDE / "voice/config.json"
    if not cfg.exists():
        cfg.write_text(json.dumps({
            "watch": [],
            "allowed_terms": [],
            "banned_terms": [],
        }, indent=2) + "\n", encoding="utf-8")
        say("created voice/config.json (file guard off until you fill in 'watch')")

    merge_settings()

    print("\nDone.\n")
    print("  Next:")
    print("  1. Restart Claude Code, or open /hooks once, so it picks up the change.")
    print("  2. Edit ~/.claude/voice/anti-ai-writing-style.md so the rules are yours.")
    print("  3. Ask Claude to write something. The rules load automatically.")
    print("     Or run /voice-audit to check writing you already have.\n")


def merge_settings():
    data = {}
    if SETTINGS.exists():
        try:
            data = json.loads(SETTINGS.read_text(encoding="utf-8"))
        except Exception:
            say("WARNING: settings.json is not valid JSON. Fix it, then re-run.")
            sys.exit(1)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = SETTINGS.with_suffix(f".json.backup-{stamp}")
        shutil.copy2(SETTINGS, backup)
        say(f"backed up settings.json to {backup.name}")

    hooks = data.setdefault("hooks", {})
    added = 0

    for event, command in HOOK_ENTRIES.items():
        group = hooks.setdefault(event, [])
        if any(h.get("command") == command
               for entry in group for h in entry.get("hooks", [])):
            continue
        group.append({"hooks": [{"type": "command", "command": command,
                                 "timeout": 10}]})
        added += 1

    event, matcher, command = FILE_GUARD
    group = hooks.setdefault(event, [])
    if not any(h.get("command") == command
               for entry in group for h in entry.get("hooks", [])):
        group.append({"matcher": matcher,
                      "hooks": [{"type": "command", "command": command,
                                 "timeout": 30}]})
        added += 1

    SETTINGS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    say(f"settings.json updated ({added} hook(s) added)" if added
        else "settings.json already had the hooks, left alone")


def uninstall():
    print("\nRemoving the anti-AI writing kit\n" + "=" * 40)
    commands = set(HOOK_ENTRIES.values()) | {FILE_GUARD[2]}

    if SETTINGS.exists():
        try:
            data = json.loads(SETTINGS.read_text(encoding="utf-8"))
        except Exception:
            say("settings.json is not valid JSON, leaving it alone")
            data = None
        if data:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy2(SETTINGS, SETTINGS.with_suffix(f".json.backup-{stamp}"))
            for event, group in list(data.get("hooks", {}).items()):
                kept = [e for e in group
                        if not any(h.get("command") in commands
                                   for h in e.get("hooks", []))]
                if kept:
                    data["hooks"][event] = kept
                else:
                    data["hooks"].pop(event, None)
            SETTINGS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            say("removed the hook entries from settings.json")

    for p in [CLAUDE / "hooks/voice-prompt-guard.py",
              CLAUDE / "hooks/voice-compact-reset.py",
              CLAUDE / "hooks/voice-guard.py",
              CLAUDE / "skills/voice-audit/SKILL.md",
              CLAUDE / "skills/voice-audit/check.py"]:
        if p.exists():
            p.unlink()
            say(f"removed {p.relative_to(Path.home())}")

    say("left ~/.claude/voice/ alone, since your rules file lives there")
    print("\nDone. Restart Claude Code.\n")


if __name__ == "__main__":
    try:
        uninstall() if "--uninstall" in sys.argv else install()
    except KeyboardInterrupt:
        print("\nCancelled.")
