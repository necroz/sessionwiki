# 24 — `synthesize --max-sessions N`

- Priority: P1
- Roadmap: Phase 1, E2
- Depends on: none
- Size: S (45 min–1 h)
- Files: `sessionwiki/synth/pipeline.py`, `sessionwiki/cli.py`,
  `tests/test_synth_pipeline.py`
- Branch: `feat/synthesize-max-sessions`
- PR title: `feat(synth): cap how many sessions one run synthesizes`

## Read first

- `sessionwiki/synth/pipeline.py`: `synthesize_new_sessions` (around
  line 1289), `_synthesize_new_sessions_unlocked` (around line 1363), the
  `new_files` loop and the `if backend is None:` line (around line 1459)
- `sessionwiki/cli.py`: the `synthesize` parser and the
  `synthesize_new_sessions(` call in `cmd_synthesize` (around line 1038)

## Problem

With a paid backend (`openai`, `ollama` on a rented GPU) one run can
synthesize hundreds of sessions. There is no cap. `dummy` and `agent` cost
nothing and do not need one, but the flag must work for every backend.

## Required change

1. Add `max_sessions: Optional[int] = None` to both
   `synthesize_new_sessions` and `_synthesize_new_sessions_unlocked`; pass
   it through.

2. In `_synthesize_new_sessions_unlocked`, directly before
   `if backend is None:`:

```python
if max_sessions is not None and max_sessions >= 0 and len(new_files) > max_sessions:
    summary["deferred"] = len(new_files) - max_sessions
    new_files = new_files[:max_sessions]
    print(f"  deferred: {summary['deferred']} session(s) — run again to continue")
```

   Add `"deferred": 0` to the `summary` dict. Keep the existing order of
   `new_files`. Deferred sessions are not written to the state, so the next
   run picks them up.

3. CLI: add to the `synthesize` parser (outside the mutually exclusive
   group):

```python
syn.add_argument(
    "--max-sessions", type=int, default=None, metavar="N",
    help="Synthesize at most N sessions in this run; the rest wait for the next run",
)
```

   Pass `max_sessions=args.max_sessions` in `cmd_synthesize`.

## Tests

Add to `tests/test_synth_pipeline.py` (use the existing fixtures):

- 3 new raw sessions, `max_sessions=1`: 1 synthesized, `deferred == 2`,
  the state has 1 entry.
- A second run with `max_sessions=1` synthesizes the next one.
- `max_sessions=None`: unchanged behaviour.

## Verification

```bash
.venv/bin/python -m pytest tests/test_synth_pipeline.py -q
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m sessionwiki synthesize --help | grep max-sessions
```

Back up the synth state before tests (see `docs/tasks/README.md`).

## Acceptance criteria

- [ ] The cap works and the rest is picked up next run.
- [ ] Default unchanged.
- [ ] `CHANGELOG.md` updated.

## Out of scope

- A dollar budget (needs per-backend pricing).
- A config key for the cap.

## Rollback

Revert the files.
