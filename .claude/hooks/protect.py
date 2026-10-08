#!/usr/bin/env python3
"""PreToolUse hook: refuse edits to paths listed in work/*/locks.txt.

Each line of a locks.txt is a repo-relative path; a line ending in "/" locks
everything under it. The locks files themselves can't be edited with the file
tools (skills append to them with the shell).

Installed as `python3 ".../protect.py" || exit 2`, so a crash or a missing
python3 blocks the action instead of letting it through (fails closed).
"""
import glob
import json
import os
import re
import sys

FILE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
# Shell commands that change a file named on their command line.
SHELL_WRITE = re.compile(r"\bsed\s+-i|\brm\b|\bmv\b|\bcp\b|\btee\b|\btruncate\b|\bgit\s+(checkout|restore)\b")


def block(reason):
    sys.stderr.write(
        f"Blocked: {reason}\n"
        "This file is locked because it was approved. If it really needs to change, "
        "stop and ask the user; they can remove the line from the work item's locks.txt.\n"
    )
    sys.exit(2)


def load_locks(root):
    locks = []
    for path in glob.glob(os.path.join(root, "work", "*", "locks.txt")):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    locks.append(line[2:] if line.startswith("./") else line)
    return locks


def rel_to_root(root, path):
    full = os.path.realpath(path if os.path.isabs(path) else os.path.join(root, path))
    rel = os.path.relpath(full, root)
    return None if rel.startswith("..") else rel.replace(os.sep, "/")


def locked_by(rel, locks):
    for lock in locks:
        if (lock.endswith("/") and rel.startswith(lock)) or rel == lock:
            return lock
    return None


def main():
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}
    root = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd())
    locks = load_locks(root)

    if tool in FILE_TOOLS:
        target = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        rel = rel_to_root(root, target) if target else None
        if rel is None:
            return 0
        if re.fullmatch(r"work/[^/]+/locks\.txt", rel):
            block(f"{rel} is a lock list; skills change it with the shell, as their steps say.")
        lock = locked_by(rel, locks)
        if lock:
            block(f"{rel} is locked by '{lock}'.")
    elif tool == "Bash":
        command = tool_input.get("command", "")
        for lock in locks:
            target = re.escape(lock.rstrip("/"))
            if re.search(r">>?\s*['\"]?" + target, command) or (SHELL_WRITE.search(command) and lock.rstrip("/") in command):
                block(f"the command would change '{lock}', which is locked.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:  # fail closed
        sys.stderr.write(f"protect.py failed ({e!r}); blocking to be safe.\n")
        sys.exit(2)
