#!/usr/bin/env python3
"""Install the agentic SDLC kit into a project and configure it. Run it through install.sh.

  install.sh [project-dir] [--yes]

project-dir defaults to the current directory. --yes accepts every default without asking
(also the behaviour when stdin isn't a terminal); --ask forces the questions even then.
Re-running it updates the kit's files and can reconfigure the CLAUDE.md block. It never
writes credentials: it only checks whether the environment has them.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTS = ("skills", "agents", "hooks", "scripts")
START = "<!-- agentic-sdlc-kit:start"
END = "<!-- agentic-sdlc-kit:end -->"
OLD_SNIPPET_HEADER = "<!-- Add to the project's CLAUDE.md"
HOOK_CMD = 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/protect.py" || exit 2'
TBD = "TBD"


# ---------------------------------------------------------------- terminal UI

class UI:
    def __init__(self, interactive):
        self.interactive = interactive
        tty = sys.stdout.isatty()
        self.b = (lambda s: f"\033[1m{s}\033[0m") if tty else (lambda s: s)
        self.dim = (lambda s: f"\033[2m{s}\033[0m") if tty else (lambda s: s)

    def section(self, title):
        print("\n" + self.b(title))

    def note(self, text):
        print("  " + self.dim(text))

    def ask(self, question, default=""):
        shown = f" [{default}]" if default else ""
        if not self.interactive:
            print(f"  {question}{shown}: {default or '-'}")
            return default
        try:
            answer = input(f"  {question}{shown}: ").strip()
        except EOFError:
            answer = ""
        return answer or default

    def yes(self, question, default=True):
        hint = "Y/n" if default else "y/N"
        while True:
            answer = self.ask(f"{question} ({hint})", "").lower()
            if not answer:
                return default
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False
            print("  Please answer y or n.")

    def choose(self, question, options, default):
        """options: list of (value, label). Returns a value."""
        print(f"  {question}")
        for i, (value, label) in enumerate(options, 1):
            mark = "*" if value == default else " "
            print(f"   {mark}{i}) {label}")
        values = [v for v, _ in options]
        while True:
            answer = self.ask("Choose", str(values.index(default) + 1))
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                return values[int(answer) - 1]
            if answer in values:
                return answer
            print(f"  Enter a number from 1 to {len(options)}.")


# ---------------------------------------------------------------- detection

def run(cmd, cwd=None):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
        return r.returncode, r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def detect_commands(target):
    """-> dict test/build/lint/start/url with '' where nothing was found."""
    found = {"test": "", "build": "", "lint": "", "start": "", "url": ""}
    pkg = os.path.join(target, "package.json")
    if os.path.isfile(pkg):
        try:
            scripts = json.load(open(pkg, encoding="utf-8")).get("scripts", {})
        except ValueError:
            scripts = {}
        pm = next((m for f, m in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"), ("bun.lock", "bun"))
                   if os.path.exists(os.path.join(target, f))), "npm")
        runner = lambda s: f"{pm} test" if s == "test" else f"{pm} run {s}"
        if "test" in scripts and "no test specified" not in scripts["test"]:
            found["test"] = runner("test")
        for key in ("build", "lint"):
            if key in scripts:
                found[key] = runner(key)
        for key in ("dev", "start"):
            if key in scripts:
                found["start"] = runner(key)
                found["url"] = "http://localhost:3000"
                break
    makefile = os.path.join(target, "Makefile")
    if os.path.isfile(makefile):
        targets = set(re.findall(r"^([A-Za-z][\w-]*):", open(makefile, encoding="utf-8", errors="replace").read(), re.M))
        for key, names in (("test", ("test",)), ("build", ("build",)), ("lint", ("lint",)), ("start", ("run", "dev", "start"))):
            if not found[key]:
                found[key] = next((f"make {n}" for n in names if n in targets), "")
    if os.path.isfile(os.path.join(target, "pyproject.toml")) or os.path.isfile(os.path.join(target, "pytest.ini")):
        found["test"] = found["test"] or "pytest"
        pyproject = os.path.join(target, "pyproject.toml")
        if os.path.isfile(pyproject) and "ruff" in open(pyproject, encoding="utf-8", errors="replace").read():
            found["lint"] = found["lint"] or "ruff check ."
    if os.path.isfile(os.path.join(target, "Cargo.toml")):
        found.update({k: found[k] or v for k, v in (("test", "cargo test"), ("build", "cargo build"), ("lint", "cargo clippy"))})
    if os.path.isfile(os.path.join(target, "go.mod")):
        found.update({k: found[k] or v for k, v in (("test", "go test ./..."), ("build", "go build ./..."), ("lint", "go vet ./..."))})
    return found


def detect_prototype(target):
    for rel in ("prototype/index.html", "prototype.html"):
        if os.path.isfile(os.path.join(target, rel)):
            return rel
    proto_dir = os.path.join(target, "prototype")
    if os.path.isdir(proto_dir):
        htmls = sorted(f for f in os.listdir(proto_dir) if f.endswith(".html"))
        if htmls:
            return "prototype/" + htmls[0]
    return ""


def github_remote(target):
    code, url = run(["git", "remote", "get-url", "origin"], cwd=target)
    return code == 0 and "github.com" in url


def linear_teams():
    sys.path.insert(0, os.path.join(KIT, ".claude", "scripts"))
    try:
        import issue  # the kit's own client
        return [t["key"] for t in issue.linear_gql("{ teams(first:50){ nodes{ key } } }")["teams"]["nodes"]]
    except (SystemExit, Exception):
        return []


# ---------------------------------------------------------------- steps

def copy_kit(target, ui):
    dest = os.path.join(target, ".claude")
    existing = [p for p in PARTS if os.path.isdir(os.path.join(dest, p))]
    if existing:
        ui.note("The kit is already installed here; its files can be updated to this version.")
        ui.note("Any edits you made to the kit's own skills, agent, hook or script are overwritten.")
        if not ui.yes("Update the kit's files", True):
            return "kept"
    for part in PARTS:
        src = os.path.join(KIT, ".claude", part)
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            rel = os.path.relpath(root, src)
            out = os.path.join(dest, part, rel)
            os.makedirs(out, exist_ok=True)
            for f in files:
                if not f.endswith(".pyc"):
                    shutil.copy2(os.path.join(root, f), os.path.join(out, f))
    return "updated" if existing else "installed"


def merge_settings(target):
    path = os.path.join(target, ".claude", "settings.json")
    entry = {"matcher": "Edit|Write|MultiEdit|NotebookEdit|Bash", "hooks": [{"type": "command", "command": HOOK_CMD}]}
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"hooks": {"PreToolUse": [entry]}}, f, indent=2)
            f.write("\n")
        return "created"
    try:
        settings = json.load(open(path, encoding="utf-8"))
    except ValueError:
        return "invalid"
    pre = settings.setdefault("hooks", {}).setdefault("PreToolUse", [])
    if any(h.get("command") == HOOK_CMD for e in pre for h in e.get("hooks", [])):
        return "unchanged"
    shutil.copy2(path, path + ".bak")
    pre.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    return "merged"


def render_block(cfg):
    with open(os.path.join(KIT, "templates", "CLAUDE.md.snippet"), encoding="utf-8") as f:
        text = f.read()
    values = {
        "TEST_CMD": cfg["test"] or TBD, "BUILD_CMD": cfg["build"] or TBD, "LINT_CMD": cfg["lint"] or TBD,
        "START_CMD": cfg["start"] or TBD, "APP_URL": cfg["url"] or TBD, "PROTOTYPE": cfg["prototype"],
        "TRACKER": cfg["tracker"], "STATUS_UPDATES": cfg["status"], "TRIAGE": cfg["triage"],
    }
    text = re.sub(r"\{\{(\w+)\}\}", lambda m: values.get(m.group(1), m.group(0)), text)  # function replacer: values are data
    start, end = text.index(START), text.index(END) + len(END)
    return text[start:end], text[end:].strip()


def write_claude_md(target, cfg, ui):
    path = os.path.join(target, "CLAUDE.md")
    block, tail = render_block(cfg)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(block + "\n\n" + tail + "\n")
        return "created"
    current = open(path, encoding="utf-8").read()
    if START in current and END in current:
        shutil.copy2(path, path + ".bak")
        new = current[:current.index(START)] + block + current[current.index(END) + len(END):]
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
        return "updated (previous version in CLAUDE.md.bak)"
    if current.lstrip().startswith(OLD_SNIPPET_HEADER):  # an unedited copy of v0.1's snippet
        shutil.copy2(path, path + ".bak")
        with open(path, "w", encoding="utf-8") as f:
            f.write(block + "\n\n" + tail + "\n")
        return "replaced the v0.1 template copy (old one in CLAUDE.md.bak)"
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n\n" + block + "\n\n" + tail + "\n")
    return "appended the kit's section"


# ---------------------------------------------------------------- main

def configure(target, ui, cfg_existing_block):
    cfg = {}
    found = detect_commands(target)
    ui.section("Commands")
    ui.note("One command each; leave TBD if the app doesn't exist yet (/build fills them in).")
    cfg["test"] = ui.ask("Test", found["test"] or TBD)
    cfg["build"] = ui.ask("Build", found["build"] or TBD)
    cfg["lint"] = ui.ask("Lint", found["lint"] or TBD)
    cfg["start"] = ui.ask("Start the app", found["start"] or TBD)
    cfg["url"] = ui.ask("App URL", found["url"] or TBD)
    cfg = {k: ("" if v == TBD else v) for k, v in cfg.items()}

    ui.section("Prototype")
    proto = detect_prototype(target)
    if proto:
        ui.note(f"Found {proto}; /prototype will modify it.")
    else:
        ui.note("No prototype yet; the first /prototype creates one at this path.")
    path = ui.ask("Prototype path", proto or "prototype/index.html")
    cfg["prototype"] = path if os.path.isfile(os.path.join(target, path)) else f"{path} (created by the first /prototype)"

    ui.section("Issues")
    env_default = ("linear" if os.environ.get("LINEAR_API_KEY") else "jira" if os.environ.get("JIRA_BASE_URL")
                   else "github" if github_remote(target) else "none")
    tracker = ui.choose("Where do issues come from?", [
        ("none", "None, ideas only"), ("linear", "Linear"), ("jira", "Jira"),
        ("github", "GitHub issues"), ("file", "A local file (JSON, Markdown, CSV, SQLite)")], env_default)
    triage, status = "none", "off"
    if tracker == "linear":
        if not os.environ.get("LINEAR_API_KEY"):
            ui.note("LINEAR_API_KEY isn't set in this shell. Export it before using Linear issues.")
        teams = linear_teams()
        team = ui.ask("Linear team key" + (f" ({', '.join(teams)})" if teams else ""), teams[0] if len(teams) == 1 else "")
        triage = f"linear --team {team.upper() or '<KEY>'} --state Triage"
    elif tracker == "jira":
        missing = [v for v in ("JIRA_BASE_URL",) if not os.environ.get(v)]
        if not (os.environ.get("JIRA_PAT") or (os.environ.get("JIRA_EMAIL") and os.environ.get("JIRA_API_TOKEN"))):
            missing.append("JIRA_EMAIL + JIRA_API_TOKEN (or JIRA_PAT)")
        if missing:
            ui.note("Not set in this shell: " + ", ".join(missing) + ". Export them before using Jira issues.")
        project = ui.ask("Jira project key", "")
        triage = f"jira --project {project.upper() or '<KEY>'} --label triage"
    elif tracker == "github":
        if run(["gh", "auth", "status"])[0] != 0:
            ui.note("The gh CLI isn't signed in. Run: gh auth login")
        triage = "github --label " + ui.ask("Label that marks issues for /triage", "triage")
    elif tracker == "file":
        f = ui.ask("Issues file, relative to the project", "TASKS.md")
        if not os.path.isfile(os.path.join(target, f)):
            ui.note(f"{f} doesn't exist yet; create it before using it.")
        tracker = f"file:{f}"
        triage = f"file:{f}"
    if tracker != "none" and not tracker.startswith("file:"):
        status = "on" if ui.yes("Let the skills change issue status (In Progress, In Review)", False) else "off"
    cfg.update(tracker=tracker, triage=triage, status=status)
    return cfg


def main():
    ap = argparse.ArgumentParser(description="Install the agentic SDLC kit into a project.")
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("-y", "--yes", action="store_true", help="accept every default without asking")
    ap.add_argument("--ask", action="store_true", help="ask even when stdin isn't a terminal (scripted answers)")
    args = ap.parse_args()
    ui = UI(interactive=(args.ask or sys.stdin.isatty()) and not args.yes)
    target = os.path.abspath(os.path.expanduser(args.project))

    print(ui.b("Agentic SDLC kit") + f"  ->  {target}")
    if os.path.realpath(target) == os.path.realpath(KIT):
        sys.exit("That's the kit itself. Run this from a project, or pass the project's folder.")
    if not os.path.isdir(target):
        if not ui.yes(f"{target} doesn't exist. Create it", True):
            sys.exit("Nothing installed.")
        os.makedirs(target)

    ui.section("Checks")
    for tool, why, required in (("git", "branches and commits", True), ("gh", "/ship and /triage", False),
                                ("npx", "screenshots via npx playwright (or use the Playwright MCP)", False)):
        ok = shutil.which(tool) is not None
        print(f"  {'ok ' if ok else 'MISSING'} {tool}: {why}")
        if required and not ok:
            sys.exit(f"{tool} is required.")
    is_repo = run(["git", "rev-parse", "--is-inside-work-tree"], cwd=target)[0] == 0
    if not is_repo and ui.yes("Not a git repository. Run git init", True):
        run(["git", "init", "-q", "-b", "main"], cwd=target)
        is_repo = True

    claude_md = os.path.join(target, "CLAUDE.md")
    has_block = os.path.exists(claude_md) and START in open(claude_md, encoding="utf-8").read()
    reconfigure = True
    if has_block:
        ui.section("CLAUDE.md")
        ui.note("This project already has the kit's CLAUDE.md section. Reconfiguring replaces it (a backup is kept).")
        reconfigure = ui.yes("Reconfigure it", False)
    cfg = configure(target, ui, has_block) if reconfigure else None

    workflow = False
    if cfg and cfg["tracker"] != "none":
        ui.section("Triage")
        workflow = ui.yes("Add the nightly /triage GitHub workflow", False)

    ui.section("Installing")
    os.makedirs(os.path.join(target, ".claude"), exist_ok=True)
    print(f"  kit files: {copy_kit(target, ui)}")
    print(f"  .claude/settings.json: {merge_settings(target)}")
    if cfg:
        print(f"  CLAUDE.md: {write_claude_md(target, cfg, ui)}")
    review = os.path.join(target, "REVIEW.md")
    if os.path.exists(review):
        print("  REVIEW.md: kept the existing one")
    else:
        shutil.copy2(os.path.join(KIT, "templates", "REVIEW.md"), review)
        print("  REVIEW.md: created")
    if workflow:
        wf = os.path.join(target, ".github", "workflows", "triage.yml")
        if os.path.exists(wf):
            print("  .github/workflows/triage.yml: kept the existing one")
        else:
            os.makedirs(os.path.dirname(wf), exist_ok=True)
            shutil.copy2(os.path.join(KIT, "templates", "triage.yml"), wf)
            print("  .github/workflows/triage.yml: created (add the CLAUDE_CODE_OAUTH_TOKEN secret and your tracker's)")

    ui.section("Next")
    print("  1. Start a new Claude Code session in the project (skills load at session start).")
    print("  2. Type /intent <idea or issue>.")
    if not github_remote(target):
        print("  3. Before /ship: add a GitHub remote (gh repo create).")
    print("  Guide: " + os.path.join(KIT, "GUIDE.md"))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nCancelled; nothing after the last step shown was changed.")
