# 28 — CI on macOS and Windows

- Priority: P0
- Roadmap: Phase 2, E5
- Depends on: none
- Size: M (2–4 h, mostly waiting for CI)
- Files: `.github/workflows/ci.yml`; product code only for real
  portability bugs; tests only for documented skips
- Branch: `ci/macos-windows`
- PR title: `ci: run the test suite on macOS and Windows`

## Read first

- `.github/workflows/ci.yml`, job `lint-and-test`
- `sessionwiki/lock.py` (cross-platform lock) — an example of how the
  project handles platform differences

## Problem

CI runs on Ubuntu only. Install and hook breakage on Windows and macOS was
the top reason users left claude-mem. sessionwiki ships Windows scripts
(`*.bat`) and a Windows Task Scheduler path, but nothing tests them.

## Required change

1. Add a job to `ci.yml`, after `lint-and-test`:

```yaml
  cross-platform:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [macos-latest, windows-latest]
        python-version: ["3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v6
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install
        shell: bash
        run: |
          python -m pip install --upgrade pip
          python -m pip install markdown pytest
          python -m pip install -e .
      - name: CLI smoke
        shell: bash
        run: |
          python -m sessionwiki --version
          python -m sessionwiki adapters
          python -m sessionwiki init
          python -m sessionwiki doctor
      - name: Tests
        shell: bash
        env:
          PYTHONUTF8: "1"
        run: python -m pytest tests/ -q
```

2. Push the branch, open the PR and read failures:

```bash
gh run list --branch ci/macos-windows --limit 3
gh run view <run-id> --log-failed
```

3. For each failing test, decide:
   - **Real bug in product code** (path separator, missing
     `encoding="utf-8"`, POSIX-only call, `\r\n`), fix ≤ ~10 lines: fix it.
   - **Test assumes POSIX** (hard-coded `/`, `chmod`, symlinks): fix the
     test if ≤ ~5 lines; otherwise skip it with
     `@pytest.mark.skipif(sys.platform == "win32", reason="<concrete reason>")`.
   - Anything bigger: skip with a reason and list it in the PR body as a
     follow-up.

4. Stop and report instead of merging if more than 10% of tests need skips
   on one platform.

## Verification

- Both new matrix jobs are green on the PR.
- The Ubuntu job is still green.
- The PR body lists every skip with its reason and every product fix.

Locally:

```bash
.venv/bin/python -m pytest tests/ -q
```

## Acceptance criteria

- [ ] macOS and Windows jobs run on every PR.
- [ ] Green, with documented skips only.
- [ ] `CHANGELOG.md` updated.

## Out of scope

- Python 3.9 on macOS/Windows.
- E2E browser tests on new platforms.

## Rollback

Remove the job and revert the skips.
