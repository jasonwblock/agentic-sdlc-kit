---
name: prototype
description: Stage 2a (Design) of the agentic SDLC. Updates the project's living HTML prototype for an approved intent, iterates with the user, and on approval snapshots it into the work item. Use after /intent when the change has UI.
argument-hint: "[work item slug or issue id]"
disable-model-invocation: true
---

# /prototype: design it in the project's prototype

The project keeps **one living HTML prototype**, and every feature changes it. When the user approves, you copy a snapshot into the work item. Later stages read that snapshot, never the living prototype.

Work item: $ARGUMENTS: a slug, a work folder, or an issue id (`ENG-123`, `#45`, `T-4`), which matches the `work/*` folder whose name contains it, lowercased, with `#` written as `gh-`. If that's empty, use the most recently modified `work/*/` folder whose `intent.md` is approved and which has no `prototype/` yet. Name it in one line before starting.

## Steps

1. **Read** the work item's `intent.md` (it must be approved) and `CLAUDE.md`.
2. **Find the prototype.**
   - **Look for it:** first the `Prototype:` line in `CLAUDE.md`; otherwise a `prototype/` folder; otherwise an HTML file with `data-screen` or `data-testid` markers.
   - **If you find more than one,** ask which.
   - **If `CLAUDE.md` doesn't record the path yet,** add a `Prototype: <path>` line to it once the user confirms.
3. **Choose the starting point:**
   - **A prototype exists (the normal case): modify it in place.**
     - Add or change only the screens this feature needs.
     - Keep every other screen as it is.
     - If the real app has visibly moved on from the prototype on the screens this feature touches, say so. Offer to bring those screens in line with the app first, as a separate commit.
   - **No prototype, but an app exists:**
     - Create `prototype/index.html`, seeded from the app: its CSS variables or theme, its components' look, and the screens next to this feature, rebuilt as static screens.
     - Fixtures follow the real data schema.
   - **No prototype and no app:** create `prototype/index.html` from scratch.
4. **Follow these conventions:**
   - **Structure:** one self-contained HTML file is preferred. A folder is fine if the prototype already is one.
   - **Screens:** each screen is a `<section data-screen="<id>">`, routed by `#<id>` in the URL so each screen has a direct link.
   - **Testids:** every interactive element has a stable `data-testid`, named the way the app should name it.
   - **Data:** in-memory mock data shaped like the real schema, in one `fixtures` object. No backend calls.
   - **Roles:** if the intent has several, add a role switcher. Each role sees only what it should.
   - **No network,** except pinned CDN assets.
5. **Iterate.**
   - After each change, tell the user how to view it: the file path, or `npx serve prototype`, with the `#screen` links that changed.
   - If a browser tool is available (Playwright MCP, or `npx playwright screenshot`), look at your own result before showing it.
   - Repeat until the user approves.
6. **On approval:**
   1. Write `work/<folder>/prototype-notes.md`:
      - the screens added and changed, with their `#ids`;
      - the testids that matter;
      - the design decisions the user made during the iteration;
      - mock data that implies a backend rule.
   2. Copy the living prototype into `work/<folder>/prototype/`, the complete snapshot.
   3. **Screenshots:** save one of each added or changed screen, per role where it differs, to `work/<folder>/screens/<screen-id>[-<role>].png`. If no browser tool works, say so plainly. Never claim screenshots you didn't take.
   4. **Lock the approved files:** append `work/<folder>/prototype/`, `work/<folder>/screens/` and `work/<folder>/prototype-notes.md` to `work/<folder>/locks.txt`.
   5. Commit the living prototype's changes, the snapshot and the notes with the message `prototype(<slug>): <summary>`.
7. **Next step:** `/spec <slug>`.

## Rules
- Never delete or restyle screens outside this feature's scope without asking.
- The prototype is a design artifact, not app code. Never copy it into the app's source.
