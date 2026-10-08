# Review instructions

## Passes
Run three passes and tag each finding with its pass:
- **Bugs:** logic errors, broken edge cases, regressions in neighbouring flows.
- **Security:** injection, authentication gaps, permissions enforced only in the UI, personal data in logs.
- **Compliance:** the diff matches the work item's `spec.md` (every `AC-n`) and `plan.md`; departures from the plan are explained; the prototype's `data-testid`s are kept; no file listed in `work/*/locks.txt` changed.

## What Important means here
Reserve Important for findings that would break behaviour, leak data, or contradict the spec. Style and naming are nits.

## Cap the nits
Report at most five nits; summarize the rest as a count.

## Do not report
Generated files, lockfiles, the `prototype/` design files, and anything CI already enforces.
