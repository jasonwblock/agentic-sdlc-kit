# Using the agentic SDLC skills

## One-time setup per project
Run `~/code/agentic-sdlc-kit/install.sh <project>` and answer its questions: the commands, the prototype path, and where issues come from. Then start a new Claude Code session in the project.

## A feature, start to finish
| Step | You type | You do |
|---|---|---|
| 1 | `/intent <idea or issue>` | Answer up to 4 questions, correct the draft, approve |
| 2 | `/prototype <id>` *(UI only)* | Look at the prototype, ask for changes, approve |
| 3 | `/spec <id>` | Pick a resolution for each flag, or accept them all at once |
| 4 | `/build <id>` | Approve the plan, then wait. It builds, tests itself and runs a fresh verifier |
| 5 | `/ship <id>` | Review the PR and merge it. That's the only merge |

**`<idea or issue>`** can be plain words or an issue:
- Linear or Jira: `ENG-123`, or the issue's URL;
- GitHub: `#45`, `owner/repo#45`, or the issue's URL;
- a local file: `TASKS.md#T-4`, `backlog.json#BL-1`.

**`<id>`** is the issue ID or the work item's slug. Leave it out and the skill picks the most recent work item and tells you which one.

Every question and approval is a Claude Code multiple-choice prompt, with the recommended answer first. Choose **Other** to type your own answer or ask for changes.

## A bug
`/fix <description or issue>`, then `/ship <id>`. It writes a failing test first, locks the test, and fixes the code without touching it.

## Incoming work
- **`/triage`** turns new issues into draft intents, all in one PR.
- **Run it** by hand, or nightly via `templates/triage.yml`.
- **To act on a draft:** `/intent <id>` (a feature) or `/fix <id>` (a bug).

## Where things live
Each piece of work gets a folder, `work/<date>-<id>-<name>/`:

| File | What it is |
|---|---|
| `intent.md` | What's wanted, and why |
| `prototype/` | The prototype as you approved it |
| `screens/` | Screenshots of that prototype |
| `spec.md` | What to build, with acceptance criteria `AC-n` |
| `plan.md` | How it'll be built |
| `verify.md` | The evidence that it works |

## Good to know
- **Approved files are locked.** Claude can't edit an approved intent, prototype snapshot or spec. To reopen one, delete its line from the work item's `locks.txt` yourself.
- **The prototype is shared.** Each feature edits the project's one living prototype. The build compares against the snapshot you approved, so later prototype edits don't move the target.
- **Nothing reaches `main` without you.** Claude never merges, and only comments on issues; it changes their status only if you turn on `Status updates: on`.
- **Teach it once.** When Claude makes the same mistake twice, add a line under *Things Claude gets wrong* in `CLAUDE.md`.
