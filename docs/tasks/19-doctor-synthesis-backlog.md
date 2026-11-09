# 19 — `doctor` reports the synthesis backlog

- Priority: P0
- Roadmap: Phase 0, E11
- Depends on: none
- Size: S (45 min–1 h)
- Files: `sessionwiki/doctor.py`, `tests/test_doctor.py`
- Branch: `feat/doctor-synthesis-backlog`
- PR title: `feat(doctor): report sessions waiting for synthesis`

## Read first

- `sessionwiki/doctor.py` (whole file, ~120 lines)
- `sessionwiki/synth/pipeline.py`: `_load_state` (around line 204) and the
  loop that builds `new_files` (around line 1398) — this is the rule for
  "needs synthesis"
- `sessionwiki/synth/agent_delegate.py`: `is_pending`
- `tests/test_doctor.py`

## Problem

About 115 of 962 raw sessions in the maintainer's repository have no source
page, and 12 pages still carry the `agent` placeholder. `recall` then shows
"not in the wiki yet". Nothing reports this. `doctor` checks the install
only.

## Required change

Add a check to `doctor.py`:

```python
def _check_synthesis(repo_root: Path) -> dict[str, Any]:
    """Raw sessions not synthesized yet, and pages waiting for the agent."""
    from sessionwiki.synth.agent_delegate import is_pending
    from sessionwiki.synth.pipeline import _load_state

    raw_root = repo_root / "raw" / "sessions"
    state = _load_state(repo_root / ".llmwiki-synth-state.json")
    waiting = 0
    for p in raw_root.rglob("*.md") if raw_root.is_dir() else []:
        rel = str(p.relative_to(raw_root))
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        if rel not in state or state[rel] < mtime:
            waiting += 1
    pending = 0
    sources = repo_root / "wiki" / "sources"
    for page in sources.rglob("*.md") if sources.is_dir() else []:
        try:
            with page.open("rb") as f:
                head = f.read(16 * 1024).decode("utf-8", errors="replace")
        except OSError:
            continue
        if is_pending(head):
            pending += 1
    ok = waiting == 0 and pending == 0
    detail = f"{waiting} raw session(s) not synthesized, {pending} page(s) waiting for the agent"
    if not ok:
        detail += " — run `sessionwiki synthesize`"
    return {"ok": ok, "detail": detail}
```

Check that `_load_state` accepts a path argument and returns `{}` when the
file is missing; adapt the call if its signature differs. Check that
`rel` uses the same form as the state keys (look at one key in
`.llmwiki-synth-state.json`).

Register it in `collect_report` as `"synthesis": _check_synthesis(root)`.
It is **not** critical: do not add it to `critical` in `cmd_doctor`.

## Tests

Add to `tests/test_doctor.py`:

- Empty repo (`tmp_path`): `synthesis` is ok with `0 raw session(s)`.
- Two raw files, one in the state file with a current mtime: detail says
  `1 raw session(s) not synthesized`, `ok` is False.
- A source page whose body has `<!-- sessionwiki-pending: <uuid> -->`
  (use `sentinel_for` from `agent_delegate`): `1 page(s) waiting`.
- `cmd_doctor` still returns 0 when only `synthesis` warns.

## Verification

```bash
.venv/bin/python -m pytest tests/test_doctor.py -q
.venv/bin/python -m sessionwiki doctor
```

Expected in the maintainer's repository: a `[warn] synthesis` line with
non-zero counts.

## Acceptance criteria

- [ ] `doctor` prints the backlog line.
- [ ] The rule matches the pipeline's "needs synthesis" rule.
- [ ] The check never changes the exit code.
- [ ] `CHANGELOG.md` updated.

## Out of scope

- `doctor --json` and `doctor --gc` (E6).
- Running synthesis from `doctor`.

## Rollback

Remove the function and its registration.
