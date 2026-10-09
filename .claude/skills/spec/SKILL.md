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
5. **Present only the flags, using AskUserQuestion:**
   - **One question per flag.** The question states the conflict, for example "The prototype deletes chores, but the intent keeps history." Its options are your recommended resolution first, then 1–3 real alternatives.
   - **Up to 4 flags:** ask them all in one call.
   - **More than 4:** first ask "Accept all <n> recommended resolutions (Recommended)" or "Review them one by one". Then, only if the user wants to review, ask in batches of 4.
   - **No flags:** ask just for the approval: "Approve (Recommended)" or "Request changes".

   The user's answers to the flags are the approval.
6. **On approval:**
   1. write each flag's resolution into the spec;
   2. set `Status: approved`;
   3. append `work/<folder>/spec.md` to `locks.txt`;
   4. commit with the message `spec(<slug>): <title>`.
7. **Next step:** `/build <slug>`.

## Asking the user
Use the **AskUserQuestion** tool for every question and every approval, not a question in prose.
- **Batching:** up to 4 questions per call, with 2–4 options each.
- **The default** is the first option, labelled "(Recommended)".
- **Wording:** labels are short (1–5 words) and the reasoning goes in each option's description. Headers are at most 12 characters.
- **Free text:** the tool always adds "Other" for a typed answer, so never add an "Other" option yourself.
- **An approval is a question too:** "Approve (Recommended)" or "Request changes". Apply whatever the user types under Other, then ask again.
- **Without AskUserQuestion** (a headless run, or another agent harness), ask in one numbered message instead, with the default after each question.

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
