# PyPI publishing — one-time setup

> Status: the Actions workflow (`/.github/workflows/release.yml`) is ready.
> This document is the checklist for **one-time PyPI configuration** that
> unblocks `pip install sessionwiki` (#101).

## How the pipeline works

Every time a version tag (`v*.*.*`) is pushed:

1. **`build`** — builds sdist + wheel with `python -m build` on Python 3.12.
2. **`publish`** — uploads to PyPI via OIDC trusted publisher. **Gated on
   `vars.PYPI_PUBLISHING == 'true'`**: until that variable is set, the job
   is skipped silently so unconfigured repos don't fail on every tag.
3. **`sign`** — signs artifacts with Sigstore (`gh-action-sigstore-python`).
4. **`github-release`** — creates (or updates) the matching GitHub Release
   with `--generate-notes`, attaches all artifacts + signatures. Runs even
   if publish/sign fail so Releases always keep tracking tags.

The package is uploaded as **`sessionwiki`**. The CLI command, the Python
import (`import sessionwiki`) and the GitHub repo (`necroz/sessionwiki`)
use the same name. (Upstream llmwiki had to publish as `llm-notebook`
because `llmwiki` is taken on PyPI.)

## One-time setup (do this once, on pypi.org)

### 1. Reserve the project name on PyPI

1. Log in to [pypi.org](https://pypi.org) (create an account if you
   haven't yet — GitHub sign-in works).
2. Check that `sessionwiki` is still free on PyPI (it was on 2026-11-05).
3. Reserve the `sessionwiki` name (PyPI lets you create a project
   directly via the trusted-publisher flow below — no upload needed).

### 2. Add the GitHub repo as a trusted publisher

Inside the PyPI **"Your account → Publishing"** page (or the project's
own Publishing tab once it exists):

**Add a new pending publisher → GitHub**

| Field | Value |
|---|---|
| PyPI Project Name | `sessionwiki` |
| Owner | `necroz` |
| Repository name | `sessionwiki` |
| Workflow name | `release.yml` |
| Environment name | `release` |

Save. This binds the GitHub OIDC identity to PyPI so the workflow can
upload without a long-lived API token.

### 3. Create the `release` GitHub environment

1. **[Repository settings → Environments → New environment](https://github.com/necroz/sessionwiki/settings/environments)**
2. Name: **`release`**
3. Optional protection rules:
   - **Required reviewers** — add your own handle so every PyPI upload
     requires an explicit click.
   - **Wait timer** — 5 minutes gives you time to abort a mis-tagged release.
   - **Deployment branches** — limit to `master` so only master-tagged
     releases can trigger the upload.

### 4. Flip the publishing gate on

```bash
gh variable set PYPI_PUBLISHING --body "true" --repo necroz/sessionwiki
# Verify
gh variable list --repo necroz/sessionwiki | grep PYPI_PUBLISHING
```

### 5. Cut a real release tag

```bash
# Make sure you are on master with everything merged
git checkout master && git pull

# Bump version if needed, update CHANGELOG, commit...

# Create a signed tag
git tag -s v2.0.0 -m "v2.0.0 release"
git push origin v2.0.0
```

Watch the workflow at:
<https://github.com/necroz/sessionwiki/actions/workflows/release.yml>

The `publish` job should now run and show `uploading` + `success`.

### 6. Verify from a clean machine

```bash
python3 -m venv /tmp/pypi-smoke && source /tmp/pypi-smoke/bin/activate
pip install sessionwiki
sessionwiki --version    # should match the tag
sessionwiki adapters     # should list Claude Code, Codex, Cursor, Gemini, …
deactivate
```

### 7. Move the major tag

Consumers pin the action to `@v2`, so keep a moving major tag on the
latest stable release:

```bash
git tag -f v2 v2.0.0
git push -f origin v2
```

## Troubleshooting

**`publish` skipped** — `PYPI_PUBLISHING` variable not set, or set to
something other than `"true"`. Fix:
`gh variable set PYPI_PUBLISHING --body "true"`.

**`publish` fails with "invalid-publisher"** — the OIDC binding on
pypi.org doesn't match what GitHub sent. Double-check: owner =
`necroz`, repo = `sessionwiki`, workflow = `release.yml`, environment
= `release`. Casing matters.

**`publish` fails with "403 Forbidden: User ... isn't allowed to upload
to project ..."** — the PyPI project exists but the trusted publisher
hasn't been added yet (or was added under a different project name).
Re-check step 2.

**Artifacts rejected for metadata** — check that `pyproject.toml`'s
`name`, `version`, and `description` are all present; `python -m build`
locally + `twine check dist/*` surface issues before a tag push.

**Second upload of the same version** — PyPI refuses to overwrite a
version. Bump to the next patch (`v1.1.1`), update the changelog, re-tag.

## Related

- `#101` — this issue
- `.github/workflows/release.yml` — the pipeline
