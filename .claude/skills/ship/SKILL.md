---
name: ship
description: Stage 5 (Deploy) of the agentic SDLC. Opens the PR for a verified work item, then works review comments and failing checks until it is green and waiting only on the user. Never merges. Use after /build or /fix.
argument-hint: "[work item slug or issue id]"
disable-model-invocation: true
---

# /ship: a green PR, waiting only on you

Work item: $ARGUMENTS: a slug, a work folder, or an issue id (`ENG-123`, `#45`, `T-4`), which matches the `work/*` folder whose name contains it, lowercased, with `#` written as `gh-`. If that's empty, use the most recently modified `work/*/` folder that has a `verify.md`. Name it in one line.

## Steps

1. **Check before opening the PR.**
   - `verify.md` exists, and it lists no open blocking findings. If it does, list them and ask whether to ship anyway.
   - The branch isn't `main` or `master`.
   - The working tree is clean.
2. **Release the test locks.**
   - Remove from `locks.txt` every line that isn't under `work/`, so later work can change those tests again:
     ```bash
     grep '^work/' work/<folder>/locks.txt > work/<folder>/locks.tmp; mv work/<folder>/locks.tmp work/<folder>/locks.txt
     ```
   - Commit it, if anything changed.
3. **Push the branch and open the PR** with `gh pr create`. Target the default branch unless `CLAUDE.md` names another.
   - **The title:** if the work came from an issue, start with its id: `ENG-123: <title>`. Jira and Linear link a PR by the key.
   - **The body:**
     - **What and why:** two or three sentences from the intent.
     - **The issue link,** taken from the `Source:` line of `intent.md` or `bug.md`. The wording depends on the source, so the tracker closes the issue when the PR merges:

       | Source | Line |
       |---|---|
       | Linear | `Closes ENG-123` |
       | GitHub | `Closes #45` (or `Closes owner/repo#45` for another repo) |
       | Jira | the key in the title is enough; add the issue's URL |
       | Local file | `Source: TASKS.md#T-4` |
     - **Links:** `intent.md`, `spec.md`, `plan.md`, `verify.md`.
     - **Acceptance:** each `AC-n` with pass or fail, from `verify.md`.
     - **Departures from the plan,** and the findings left open.
     - **Screenshots:** links to the `screens/` files, and to the build's screenshots if there are any.
   - **Report back to the issue,** if it came from a tracker:
     - **A comment** with the PR URL: `python3 .claude/scripts/issue.py comment "<ref>" "PR: <url>"`.
     - **The status:** only if `CLAUDE.md`'s `## Issues` section says `Status updates: on`, run `python3 .claude/scripts/issue.py status "<ref>" "<In review state>"`.
     - **If the script exits with 3,** skip the step.
     - **For a local issue file in the repo** that has a status field, set it to the review state as part of this PR.
4. **Babysit the PR,** for at most 3 rounds:
   1. `gh pr checks <n> --watch`, and read the result.
   2. Read the unresolved review comments: `gh pr view <n> --comments`, plus `gh api repos/{owner}/{repo}/pulls/<n>/comments` for comments on lines.
   3. **For a failing check:** find the cause, fix it, and push a new commit.
   4. **For a review comment:**
      - fix it if it's right and within the spec;
      - reply with your reasoning if you disagree;
      - list it for the user if it changes the spec.
   5. If the same mistake was flagged twice, propose a one-line addition to `CLAUDE.md` in the PR.
5. **Report:**
   - the PR URL;
   - whether the checks are green;
   - what's waiting on the user (approval, and the comments you didn't act on).

## Rules
- **Never merge,** never push to `main` or `master`, never force-push, never skip hooks (`--no-verify`).
- **Never weaken a test or a check** to get green.
