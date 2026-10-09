# Agentic SDLC kit

A skills-only version of the agentic SDLC from Anthropic's *The AI-Native SDLC Playbook*, for a solo developer who builds features from an HTML prototype. Seven skills, one subagent, one hook, one issue script and a few templates; no framework to install.

## The flow

```
/intent ──► /prototype ──► /spec ──► /build ──► /ship        (a feature)
   ▲         (if UI)                  │ verifier
   │                                  ▼
/triage ◄── issues, errors     /fix ──► /ship                 (a bug)
```

| Skill | Stage | Writes | Your part |
|---|---|---|---|
| `/intent` | Plan | `work/<date>-<slug>/intent.md` | Answer ≤5 questions (defaults offered), correct, approve |
| `/prototype` | Design | Changes to the **living prototype**; a snapshot in `work/…/prototype/`, `screens/`, `prototype-notes.md` | Iterate, approve |
| `/spec` | Design | `spec.md` with `AC-n` acceptance criteria and `F-n` flags | Reply "defaults" or override flags |
| `/build` | Build + Test | `plan.md`, the code and tests, `verify.md` | Accept the plan |
| `/fix` | Bug | `bug.md`, a locked failing test, the fix, `verify.md` | Rarely anything |
| `/ship` | Deploy | The PR, worked until green | Review and merge |
| `/triage` | Maintain | Draft intents and bugs in one PR (runs headless) | Pick what to pursue |

**The prototype:** the project keeps one living HTML prototype (its path is recorded in `CLAUDE.md`). `/prototype` modifies it for each feature, and creates one only if none exists. That means seeding from the app's look if there's an app, or starting from scratch if there isn't. On approval, it copies a snapshot into the work item, and `/build` and the verifier compare the app against that snapshot. That way the living prototype can keep changing without moving the target of a build in progress.

**Issues as the front door:** `/intent`, `/fix` and `/triage` take an issue from anywhere, and the issue's ID then carries through the work folder's name, the branch, the commits and the PR. `.claude/scripts/issue.py` reads every source and returns the same JSON shape:

| Source | Reference | Needs |
|---|---|---|
| Linear | `ENG-123` or its URL | `LINEAR_API_KEY` |
| Jira | `ENG-123`, a `/browse/` URL | `JIRA_BASE_URL` plus `JIRA_EMAIL` and `JIRA_API_TOKEN` (Cloud), or `JIRA_PAT` (Server/DC) |
| GitHub | `#45`, `owner/repo#45`, or its URL | the `gh` CLI, signed in |
| Local file | `backlog.json#BL-1`, `TASKS.md#T-4`, `issues.csv#12`, `issues.db#42` | nothing (read-only) |

- **A bare key:** `Tracker:` in `CLAUDE.md` says whose it is, since Linear and Jira keys look the same. A URL or a prefix (`jira:ENG-1`) always works.
- **When the script can't reach a source:** the skills fall back to a connected MCP server, or read the file themselves. They never write to a database.
- **What gets written back:** a comment when the intent is approved and another when the PR opens. Status changes happen only with `Status updates: on`. Otherwise, Linear's and Jira's GitHub integrations move issues when PRs open and merge.
- **Local Markdown files:** the script reads headings that contain an ID (`## T-4: …`), with an optional `Status:` line, and checklist items (`- [ ] T-6 …`).

**Locks:** when you approve an artifact, its path goes into `work/<folder>/locks.txt`, and `.claude/hooks/protect.py` refuses edits to it, whether through the file tools or common shell writes. `/fix` locks its failing test the same way, and `/ship` releases test locks when the PR opens. To reopen an approved artifact, delete its line from `locks.txt` yourself.

## Install into a project

```bash
git clone https://github.com/jasonwblock/agentic-sdlc-kit.git ~/code/agentic-sdlc-kit   # once
~/code/agentic-sdlc-kit/install.sh                      # asks for the project folder; or pass it: install.sh ~/code/my-project
```

The installer:
- **Asks for the project's folder,** defaulting to the current one, and offers to create it if it doesn't exist.
- **Offers to create a git repository** (`git init`) if the folder isn't one. For a folder inside another repository, it asks whether to keep using that one.
- **Checks** for `gh` and `npx`.
- **Asks a few questions:**
  - the test, build, lint and start commands, pre-filled from `package.json`, a `Makefile`, `pyproject.toml`, `Cargo.toml` or `go.mod`;
  - where the prototype lives;
  - where issues come from (Linear, Jira, GitHub, a local file, or none), and whether skills may change issue status;
  - whether to add the nightly triage workflow.
- **Copies the kit** into `.claude/`. It merges its hook into an existing `.claude/settings.json` and backs up the old file.
- **Writes a marked section into `CLAUDE.md`.** It creates the file, or appends below your own content.
- **Adds `REVIEW.md`** if the project doesn't have one.

`--yes` accepts every default. Re-running it updates the kit's files and can reconfigure the `CLAUDE.md` section. It never writes credentials; it only checks that the environment has them.

**Requirements:**
- `python3`, for the hook. Without it, every edit is blocked, by design (it fails closed).
- `gh`, signed in, for `/ship` and `/triage`.
- A way to take screenshots, for UI work: the Playwright MCP server, or `npx playwright` with a browser installed. Without one, the skills say they couldn't check visually rather than pretending.

**Optional:**
- `templates/triage.yml` runs `/triage` nightly in GitHub Actions.
- A PR reviewer that reads `REVIEW.md`: `claude-code-action` or managed Code Review.

## Limits

- **Skills are advisory.** The model decides how carefully it follows each step. The hard guarantees are the locks hook, the coverage check in `/build`, and the verifier running with fresh context.
- **The Bash part of the hook is a heuristic.** It catches redirects, `sed -i`, `rm`, `mv`, `cp`, `tee`, `truncate` and `git checkout`/`restore` that name a locked path. A script that writes to the file indirectly gets through.
- **Not yet run with a real session.** The hook has been tested with simulated tool calls; the skills haven't been through a real feature yet.
- **What `issue.py` has been tested against:**
  - Linear (reads) and GitHub (reads, plus refusing a status GitHub doesn't have);
  - local JSON, Markdown, CSV and SQLite files;
  - working out the source from a key, a URL, a prefix or the `Tracker:` line.

  Jira is written to Atlassian's REST API but hasn't been run against a real site. Comments and status changes haven't been run against a real tracker.

## License

MIT. See `LICENSE`.
