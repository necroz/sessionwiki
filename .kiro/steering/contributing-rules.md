---
name: contributing-rules
load: always
applies_to: "**/*"
---

# Contributing rules (always loaded)

These rules are enforced on every PR and commit. They come from the parent Open Source Framework v4.0 and apply to any work in this repo.

## Identity

- `git config user.name` = `Igor Lashkevich`
- `git config user.email` = `3133574+necroz@users.noreply.github.com`
- **Never** add `Co-authored-by: Claude`, `Co-authored-by: AI`, or any similar AI attribution line in commits.
- Author line on every commit is `Igor Lashkevich <3133574+necroz@users.noreply.github.com>` exactly.

## PR size

- **One concern per PR.** Never mix "add a new adapter" with "fix a CSS bug".
- **One file per PR preferred** unless the change is strictly atomic across files (e.g., a test fixture + a snapshot that must move together).
- **PR title format**:
  - `add: <thing>` — new feature
  - `fix: <thing>` — bug fix
  - `docs: <thing>` — docs-only
  - `chore: <thing>` — refactor, dep bump, CI
  - `test: <thing>` — tests only
- **PR body** must list every file touched and why.

## Branch protection

- Default branch is `master` (not `main`).
- CI must pass before merge.
- Signed commits are requested but not required for v0.1 (GPG setup is future work).

## Scope discipline

- **No scope creep.** If you notice something else that needs fixing, open an issue, don't fix it in the same PR.
- **No silent refactors.** If a PR renames a function, the PR title says so.
- **No dead code.** Remove unused imports, variables, and files as you go.

## Docs discipline

- **Every new feature ships with docs.** A PR that adds an adapter must add `docs/adapters/<name>.md`.
- **Every public function has a docstring.** Short is fine; absent is not.
- **CHANGELOG is updated in every PR** under `## [Unreleased]`.

## Privacy discipline

- **Never commit real session data.** Fixtures must be synthetic or heavily redacted.
- **Never commit machine-specific paths** (including `.claude/settings.local.json`, `.ingestion-state.json`, `.framework/`, `.temp/`).
- **Run privacy grep before committing**: `grep -r "<your_username>" .` should return zero hits outside `.gitignore`d paths.
