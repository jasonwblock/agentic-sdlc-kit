---
name: spec
description: Stage 2b (Design) of the agentic SDLC. Writes work/<slug>/spec.md from the approved intent, the prototype snapshot and the codebase, with quantified acceptance criteria and flagged concerns with defaults. Use after /intent (and /prototype if there is UI).
argument-hint: "[work item slug or issue id]"
disable-model-invocation: true
---

# /spec: what to build, written for the builder

You write `spec.md` for an engineer, or a build session, who has never seen the conversation. The user approves the **flags** you raise; they don't read the spec line by line.

Work item: $ARGUMENTS: a slug, a work folder, or an issue id (`ENG-123`, `#45`, `T-4`), which matches the `work/*` folder whose name contains it, lowercased, with `#` written as `gh-`. If that's empty, use the most recently modified `work/*/` folder with an approved intent and no `spec.md`. Name it in one line.

## Steps

1. **Read:**
   - `intent.md`;
   - `prototype-notes.md` and the snapshot in `prototype/`, if there's UI;
   - `CLAUDE.md`;
   - the parts of the codebase this touches: schema, routes, auth, existing tests.
2. **Cross-check three sources and turn each mismatch into a flag:**
   - **The intent's** *Data and backend* section;
   - **The prototype's** screens, actions and mock data;
   - **The existing code and schema.**

   Examples:
   - The intent keeps history, but the prototype's delete removes the item.
   - The prototype shows a field the schema doesn't have.
   - A role sees a screen that the intent says it mustn't.
3. **Write `spec.md`** from the template below. **What changes** is relative to the current app, or the whole thing for a new app.
4. **Number the acceptance criteria** `AC-1`, `AC-2`, … Each must be checkable without asking anyone:
   - a test assertion;
   - a request and its response ("a `kid` calling `PATCH /api/chores/:id` gets 403");
   - "the `#week` screen matches `screens/week.png`".

   Cover:
   - every screen in `prototype-notes.md`;
   - every rule and permission in the intent;
   - what happens to existing data.
5. **Present only the flags**, each with a recommended default:
   > **F-1** The prototype deletes chores; the intent says history is kept. **Default:** archive instead of delete, hidden from lists.

   Ask the user to reply "defaults" or to override specific flags by number.
6. **On approval:**
   1. write each flag's resolution into the spec;
   2. set `Status: approved`;
   3. append `work/<folder>/spec.md` to `locks.txt`;
   4. commit with the message `spec(<slug>): <title>`.
7. **Next step:** `/build <slug>`.

## Template

```markdown
# Spec: <title>
Status: draft
Intent: work/<folder>/intent.md · Prototype: work/<folder>/prototype/

## Summary
## What changes
### Data (entities, fields, migrations, existing data)
### API (endpoints, request and response, errors)
### Permissions (per role, enforced on the server)
### Screens (by prototype #id: what's new or changed)
### Jobs and integrations
## Rules
## Acceptance criteria
- AC-1 …
## Flags
- F-1 … Default: … Resolution: …
## Not in this change
```

## Rules
- Don't invent requirements. Anything not traceable to the intent, the prototype or the code goes in as a flag.
- Keep the user's and the prototype's names for things (testids, screen ids, terms) unchanged.
