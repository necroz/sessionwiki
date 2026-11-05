# sessionwiki vs. llmwiki

sessionwiki is based on [llmwiki](https://github.com/Pratiyush/llm-wiki) by
Pratiyush (MIT). It forked from llmwiki **v1.3.82** (upstream commit
`b108889`) and keeps the full upstream history. Everything llmwiki does,
sessionwiki still does; this page lists what is different.

## Name and packaging

| | llmwiki | sessionwiki |
|---|---|---|
| PyPI distribution | `llm-notebook` | `sessionwiki` |
| Python module | `llmwiki` | `sessionwiki` |
| CLI command | `llmwiki` | `sessionwiki` |
| Repository | `Pratiyush/llm-wiki` | `necroz/sessionwiki` |
| Docker image | `ghcr.io/pratiyush/llm-wiki` | `ghcr.io/necroz/sessionwiki` |
| Version line | 1.x (last: 1.3.82) | starts at 2.0.0 (the rename is a breaking change; upstream tags `v0.1.0`…`v1.3.82` stay as history) |

**Kept on purpose for compatibility** — an existing llmwiki data directory
works with sessionwiki unchanged:

- state and cache files: `.llmwiki-state.json`, `.llmwiki-synth-state.json`,
  `.llmwiki-quarantine.json`, `.llmwiki-pending-prompts/`, `.llmwiki-*.lock`;
- the ignore file `.llmwikiignore`;
- the per-user data directory `~/.llmwiki/` (ZCode / OpenCode exports, logs);
- environment variables `LLMWIKI_*`.

See [Migrating from llmwiki](#migrating-from-llmwiki) below.

## New session sources

- **ZCode** — `sessionwiki zcode export` reads ZCode's SQLite store
  read-only and writes Claude-style JSONL; `zcode autosync` / `zcode install`
  wire it to a ZCode Stop hook plus a nightly systemd / launchd / Task
  Scheduler job. Draft workspaces collapse into one project.
- **OpenCode V2** — `sessionwiki opencode export` reads
  `opencode.db`; the OpenCode adapter is promoted from contrib to core;
  `opencode install` writes a server plugin that runs autosync on
  `session.idle` (honours `XDG_CONFIG_HOME`).
- Both exporters share one plumbing module (`sessionwiki/session_export.py`):
  read-only connection, schema check, incremental state, atomic writes,
  path-traversal-safe deletes, configurable project roots, git-root fallback
  for project slugs, reconciliation of deleted sessions.

## Synthesis

- **OpenAI-compatible backend** (vLLM, SGLang, LM Studio, LiteLLM, hosted
  providers) — stdlib only, retries only transient errors, warns when
  transcripts would leave the machine.
- **Low-signal session coalescing** — short or repetitive sessions are
  grouped into cluster pages instead of one thin page each
  (`synthesize --coalesce-only` runs it without an LLM).
- `synthesis.max_concurrency`, `synthesis.lock_skip_patterns`,
  `synthesis.strip_unresolved_wikilinks`.
- `synthesize --force` with an unavailable backend no longer wipes state;
  `--estimate` says which pricing it used.

## Reliability

- `sync` and `synthesize` run under an OS file lock and write their state
  atomically — parallel Stop-hook runs no longer corrupt state or
  re-synthesize the corpus.
- Hook-triggered autosync skips when a cycle is already running instead of
  queueing waiting processes; scheduled runs still wait.
- Cross-platform lock (`fcntl` / `msvcrt`) replaces the bash `flock` hook.
- Windows: the Task Scheduler command runs the generated wrapper and
  quotes paths with spaces correctly.

## Tooling

- `sessionwiki doctor` — environment and integration self-check.
- `sessionwiki audit` — pre-publish scan of `raw/`, `wiki/`, `site/` for
  your username, tokens and custom redaction patterns.
- Layered config for every command: `examples/sessions_config.json` →
  `config.json` → `config.local.json` (machine-local, gitignored).
- `setup.sh` / `setup.bat` create a checkout-local `.venv`.

## Graph and site

- Session / project graph with a project index; clustered view fits after
  grouping; node and cluster clicks open their pages (same-tab, so it works
  in embedded browsers that block popups).
- graphify exports are read through the `links` key and always overwritten;
  `[graph]` extras include `matplotlib` and `scipy`.
- Project pages keep hand-written notes: the generated session list lives
  between `<!-- sessions:auto:start/end -->` markers.

## Repository hygiene

- Generated wiki pages and synth state are no longer tracked in git.
- Examples, docs and fixtures use placeholder projects and a loopback LLM
  host; no personal data.

Two entries in the changelog's *Unreleased* section — `all --with-synth`
and the `sync --status` synthesis hint — are upstream llmwiki work
(Pratiyush/llm-wiki#709) that landed after v1.3.82 and came along with the
fork point.

## Migrating from llmwiki

1. Install sessionwiki in the same checkout or a new one:
   `pip install sessionwiki` (or `./setup.sh` in a clone).
2. Replace the command: `llmwiki <cmd>` → `sessionwiki <cmd>`, and
   `python -m llmwiki` → `python -m sessionwiki` — in shell aliases, hooks
   (`~/.claude/settings.json`, `~/.zcode/cli/config.json`), systemd /
   launchd units, and MCP configs (`python -m sessionwiki.mcp`).
3. Re-run `sessionwiki zcode install --force` / `sessionwiki opencode
   install --force` if you use those integrations, so the hook and plugin
   call the new command.
4. Your `raw/`, `wiki/`, state files and `~/.llmwiki/` stay as they are.
