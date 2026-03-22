# Project Memory

This file is the canonical handoff memory for AI work in this repository.

Last Updated: 2026-03-21

## Current Objective

- Combine memory, test, and documentation requirements into one clear exit checklist so sessions stop ending with stale context.

## Current State

- The canonical AI instruction set lives under `.agents/`.
- The repo already uses `.agents/rules/godtier-shorts.mdc` as an always-on project rule.
- `.agents/rules/godtier-shorts.mdc` now explicitly points agents to `PROJECT_MEMORY.md` at session start and session end.
- A dedicated always-on testing rule now exists to force relevant checks after code changes.
- A dedicated always-on documentation rule now exists to force doc updates when behavior or usage changes.
- A dedicated exit-protocol rule and matching human-readable doc now define the end-of-session checklist.
- `.cursor/` mirrors the `.agents/` setup for compatibility and should not diverge from it.
- The working tree already contains many unrelated in-progress changes; new tasks should avoid overwriting or reverting them.

## Decisions In Force

- `PROJECT_MEMORY.md` is the single canonical progress-memory file for ongoing AI work.
- Every future AI session should read this file before making changes and update it before finishing.
- The main repo rule should keep an explicit reference to `PROJECT_MEMORY.md` so the memory workflow stays visible.
- Every non-trivial code or config change should run at least one relevant verification command before the session ends.
- If verification is blocked, the exact blocker and pending command must be written here.
- Behavior-changing work should update the relevant docs in the same session, or record why no doc change was needed.
- Meaningful sessions should follow one combined exit checklist covering memory, tests, docs, and handoff quality.
- Canonical rule files live under `.agents/rules/`; `.cursor/rules/` should mirror them.
- Progress entries should stay concise and prioritize exact paths, commands, blockers, and next steps.

## Open Work / Next Steps

1. For each new task, replace `Current Objective` with the live goal before editing code.
2. Update `Validation Status` whenever commands or tests are run, including skipped checks.
3. Record which docs changed, or why no docs changed, whenever behavior or usage changed.
4. Use the exit checklist before closing any meaningful session.
5. Add a new `Session Log` entry after meaningful progress or handoff-worthy discoveries.
6. Keep unresolved blockers and assumptions visible until they are cleared.
7. If the team starts repeating an old issue, record the trigger, attempted fix, and next diagnostic step here.

## Validation Status

- No repo tests were run for this setup-only change.

## Key References

- `.agents/SKILL.md`
- `.agents/rules/godtier-shorts-exit-protocol.mdc`
- `.agents/rules/godtier-shorts.mdc`
- `.agents/rules/godtier-shorts-docs.mdc`
- `.agents/rules/godtier-shorts-progress.mdc`
- `.agents/rules/godtier-shorts-testing.mdc`
- `.cursor/rules/godtier-shorts-progress.mdc`
- `docs/operations/ai-session-exit-protocol.md`

## Session Log

### 2026-03-21

- Added `.agents/rules/godtier-shorts-exit-protocol.mdc` to combine memory, test, and documentation closeout into one checklist.
- Added `docs/operations/ai-session-exit-protocol.md` as the human-readable version of the closeout flow.
- Updated `docs/README.md` to link the new protocol doc.
- Updated `.agents/rules/godtier-shorts.mdc` to require the combined exit protocol.
- Added `.agents/rules/godtier-shorts-docs.mdc` to make relevant documentation updates mandatory.
- Updated `.agents/rules/godtier-shorts.mdc` to point the main rule at the documentation policy.
- Added `.agents/rules/godtier-shorts-testing.mdc` to make relevant verification mandatory after code changes.
- Updated `.agents/rules/godtier-shorts.mdc` to point the main rule at the mandatory test policy.
- Updated `.agents/rules/godtier-shorts.mdc` so the main always-on rule explicitly reads and updates `PROJECT_MEMORY.md`.
- Added `.agents/rules/godtier-shorts-progress.mdc` to require persistent progress tracking.
- Created `PROJECT_MEMORY.md` as the canonical AI handoff file.
- Created `.cursor/rules/godtier-shorts-progress.mdc` as the compatibility mirror for the new rule.
