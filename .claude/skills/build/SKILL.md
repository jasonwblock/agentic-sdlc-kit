---
name: build
description: Stage 3 (Build) of the agentic SDLC. Plans in plan mode, commits plan.md, implements against the approved spec with its own feedback loop, then runs the fresh verifier. Use after /spec is approved.
argument-hint: "[work item slug or issue id]"
disable-model-invocation: true
---

# /build: plan, implement, verify

Work item: $ARGUMENTS: a slug, a work folder, or an issue id (`ENG-123`, `#45`, `T-4`), which matches the `work/*` folder whose name contains it, lowercased, with `#` written as `gh-`. If that's empty, use the most recently modified `work/*/` folder whose spec is approved and which has no `verify.md`. Name it in one line.

## 1. Read everything first
- `intent.md` and `spec.md`. The spec must be approved.
- If there's UI: `prototype-notes.md`, the snapshot in `prototype/`, and `screens/*.png`.
- `CLAUDE.md`, especially its Commands and verification sections.

## 2. Plan (no code yet)
1. Enter plan mode if you can (EnterPlanMode). Otherwise, plan without editing any files.
2. Draft a plan with these sections:
   - **Files:** the files that change and what each gets.
   - **Order of work.**
   - **Risks:** what this could break, and the riskiest step.
   - **Coverage:** a table mapping **every** `AC-n` and every changed screen to the files and the test that proves it.
   - **Alternatives:** the options you didn't take, and why.
3. Check the coverage mechanically. Both commands must print nothing:
   ```bash
   comm -23 <(grep -o 'AC-[0-9]\+' work/<folder>/spec.md | sort -u) <(grep -o 'AC-[0-9]\+' work/<folder>/plan.md 2>/dev/null | sort -u)
   ```
   Run it after writing `plan.md`. If it prints any IDs, fix the plan. Do the same for screen ids, using `prototype-notes.md` as the source.
4. Show the plan to the user. When they accept it:
   - write `work/<folder>/plan.md`;
   - run the coverage check;
   - commit with the message `plan(<slug>): <title>`.

## 3. Implement, with your own loop
- **Work in the order the plan gives,** in small commits.
- **Loop until the targets pass,** typically 2–3 rounds:
  - write the code and tests for the next AC;
  - run the project's test, build and lint commands from `CLAUDE.md`;
  - fix the code, never the test or the target.
- **For UI:**
  - run the app;
  - screenshot each changed screen in the same state as `screens/*.png` (Playwright MCP or `npx playwright screenshot`);
  - compare layout, elements, hierarchy and copy, not pixels;
  - adjust.
- **Keep the prototype's `data-testid`s** in the app.
- **If you depart from the plan,** update `plan.md` in the same commit and say why.

## 4. Verify with fresh context
1. Spawn the `verifier` subagent. Give it the work folder path and the command that starts the app. Nothing else: it must form its own view.
2. Fix every finding marked **blocking**. Then run the verifier **once** more on the result.
3. Write `work/<folder>/verify.md`. It holds:
   - the verifier's final report;
   - the commands run and their pasted output;
   - the findings left open, with a reason for each.
4. Commit it.

## 5. Report
Tell the user:
- which ACs passed;
- what's left open;
- where the screenshots are;
- the next step: `/ship <slug>`.

## Rules
- **Never edit** anything listed in `work/*/locks.txt`, the living prototype, or tests that existed before this build, unless the spec says to change them. If a locked artifact is wrong, stop and tell the user.
- **Never skip, delete or weaken a failing test** to get green.
- **Show the output of every command you rely on.** Don't summarize it.
