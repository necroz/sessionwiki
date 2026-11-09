# Autonomous task-card worker

One scheduled run executes exactly one card from the
[Roadmap 2026-11 table](README.md#roadmap-2026-11-cards).

The worker is local-only: it commits on a branch and fast-forwards local
`master`. It never pushes and never opens a PR.

## State files

| File | Role |
|---|---|
| `docs/tasks/README.md` | Queue: order, dependencies and the `Status` column. Authoritative. |
| `docs/tasks/RUN_JOURNAL.md` | Append-only run log. The last entries are the context for the next run. |
| `docs/tasks/RUN.lock` | Transient lock. Gitignored. |

Statuses: `todo`, `in-progress`, `done`, `blocked`.

## Each run

1. **Lock.** If `docs/tasks/RUN.lock` exists and is younger than 90 minutes,
   another run is active: exit without action and without a journal entry.
   Otherwise create it with `touch`.
2. **Read.** `README.md` (the queue), the last three entries of
   `RUN_JOURNAL.md`, and the selected card in full.
3. **Select.** Take the first card in table order with status `todo` (or
   resume `in-progress`) whose `Depends on` cards are all `done`. Never start
   a card whose dependency is not `done`. Skip `blocked` cards.
4. **Check whether it is already done.** Test the acceptance criteria against
   `master`. If the card is already satisfied, set its status to `done`,
   append a journal entry with the evidence, remove the lock and stop. Do not
   start another card in the same run.
5. **Implement one card.** Read only the files under "Read first" plus what
   they lead to. Stay inside "Files" and "Out of scope". Follow
   `.kiro/steering/`.
6. **Gates.** Run every command under "Verification" in the card, then the
   baseline from `README.md`:
   - `.venv/bin/python -m pytest tests/ -q`
   - `.venv/bin/python -m sessionwiki lint` — count `[error]`; the number
     must not grow compared with the count before the card
   - `.venv/bin/python -m sessionwiki --version`
   Capture honest exit codes. Do not mask failures with pipes.
7. **Commit and merge locally.**
   - `git switch -c <card branch> master`
   - Commit title: the card's PR title (Conventional Commits). Author is the
     repository user; no AI attribution.
   - `.venv/bin/python -m sessionwiki lint` stays clean and tests pass.
   - `git switch master && git merge --ff-only <card branch>`, then delete
     the branch.
   - If the gates fail, fix once. If they still fail, do not merge: keep the
     branch, journal the blocker, remove the lock and stop. The next run
     resumes the branch.
8. **Update the queue.** Set the card status to `done` in `README.md`.
   `CHANGELOG.md` is updated by the card itself.
9. **Journal.** Append:

   ```markdown
   ## YYYY-MM-DD HH:MM — card NN: <title>

   - Status: done | blocked | failed
   - Files: <list>
   - Gates: pytest <rc>, lint <errors before → after>, version <rc>
   - Commit: <hash or "none: reason">
   - Decisions: <none or what was decided>
   - Next card: <NN or "auto-stop">
   - Blockers: <none or the blocker>
   ```

10. **Commit the record.** On `master`, commit the `Status` and journal
    changes: `chore: record card NN completion`. The working tree must be
    clean before the lock is removed.
11. **Unlock.** Remove `RUN.lock`. Stop.

## Rules

- `raw/` is immutable. `site/` is generated. Touch neither.
- No push, no PR, no network writes.
- One concern per commit. Do not refactor unrelated code.
- Do not edit card files. The only edit is the `Status` column in
  `README.md`.
- If a card conflicts with the code, make the smallest change that satisfies
  its acceptance criteria and record the interpretation in the journal.
- Privacy: the privacy grep from `.kiro/steering/contributing-rules.md` must
  return zero hits.

## Stop conditions

- **Queue empty.** No `todo` or `in-progress` cards remain. Final run: append
  `AUTOSTOP: queue empty`, then call `CronPauseSelf` (fallback: disable the
  automation row in the ZCode task index), remove the lock and stop.
- **Deadlock.** `todo` cards remain, but every one depends on a `blocked`
  card. Journal `PAUSED: blocked dependencies`, call `CronPauseSelf`, remove
  the lock.
- **Two consecutive failures on the same card.** Journal
  `PAUSED: card NN failed twice`, call `CronPauseSelf`, remove the lock.
- **A card needs a decision the repository cannot answer.** Set it to
  `blocked` with the question in the journal, then continue with the next
  independent card on the next run.
