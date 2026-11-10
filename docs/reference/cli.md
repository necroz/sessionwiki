---
title: "CLI reference"
type: navigation
docs_shell: true
---

# CLI reference

**Every** `python3 -m sessionwiki <subcommand>` — with the flags that
matter, realistic examples, and expected output. If a subcommand isn't
listed here it isn't shipping. A guard test checks the subcommand
headings; flags are reviewed by hand when the parser changes.

Global flags: `-h` / `--help` on every command, `--version` at the root.

---

## Top-level

```bash
python3 -m sessionwiki --version    # → sessionwiki <version>
python3 -m sessionwiki --help       # list every subcommand
python3 -m sessionwiki              # same as --help
```

The shorter alias `sessionwiki` works too once the package is installed
(`uv tool install sessionwiki` or `pip install sessionwiki` — see
[`deploy/pypi-publishing.md`](../deploy/pypi-publishing.md)).

---

## `init` — scaffold `raw/` / `wiki/` / `site/`

Creates the three data directories + seeds nine navigation files inside
`wiki/`.

```bash
python3 -m sessionwiki init
```

**Flags:** none.

**Expected output:**

```
  raw/sessions/
  wiki/sources/
  wiki/entities/
  wiki/concepts/
  wiki/syntheses/
  site/
  seeded wiki/dashboard.md
  seeded wiki/index.md
  ...
```

**Idempotent.** Safe to re-run — it never overwrites files that exist.

---

## `sync` — convert `.jsonl` sessions to markdown

The workhorse. Walks every configured adapter, converts new sessions
into `raw/sessions/`, then (by default) auto-builds and auto-lints.

```bash
python3 -m sessionwiki sync
python3 -m sessionwiki sync --since 2026-04-01 --project llm-wiki
python3 -m sessionwiki sync --adapter claude_code codex_cli
python3 -m sessionwiki sync --no-auto-build --no-auto-lint
python3 -m sessionwiki sync --vault "~/Documents/Obsidian Vault"
python3 -m sessionwiki sync --vault ~/my-vault --allow-overwrite
python3 -m sessionwiki sync --force
python3 -m sessionwiki sync --dry-run
python3 -m sessionwiki sync --adapter zcode --no-zcode-export
python3 -m sessionwiki sync --adapter opencode --no-opencode-export
```

### Flags

| Flag | What |
|---|---|
| `--adapter NAME [NAME ...]` | Limit to specific adapters. Default: every adapter with a session store on disk. |
| `--since YYYY-MM-DD` | Only sessions on/after this date (e.g. `--since 2026-04-01`). |
| `--project SUBSTRING` | Filter by project-slug substring. |
| `--include-current` | Include sessions < 60 min old (default skips live ones). |
| `--force` | Ignore the mtime state file, reconvert everything. |
| `--dry-run` | Preview conversions; does not write `raw/`, refresh the ZCode/OpenCode exports, or auto-build. |
| `--zcode-export` / `--no-zcode-export` | Refresh ZCode's JSONL corpus before converting (default: on when the database exists). |
| `--zcode-db PATH` | ZCode database path. Default: `~/.zcode/cli/db/db.sqlite`. |
| `--opencode-export` / `--no-opencode-export` | Refresh OpenCode's JSONL corpus before converting (default: on when the database exists). |
| `--opencode-db PATH` | OpenCode database path. Default: `~/.local/share/opencode/opencode.db`. |
| `--auto-build` / `--no-auto-build` | Rebuild `site/` after sync (default: on). |
| `--auto-lint` / `--no-auto-lint` | Run `lint` after sync (default: on). |
| `--vault PATH` | Vault-overlay mode — write new pages inside the given Obsidian / Logseq vault instead of `wiki/`. See [`guides/existing-vault.md`](../guides/existing-vault.md). |
| `--allow-overwrite` | With `--vault`: allow clobbering existing vault pages (default: refuse, append under `## Connections` instead). |

### Expected output (typical)

```
==> claude_code: 3 new sessions since last sync
✓ wrote 3 pages under raw/sessions/
✓ ingested into wiki/sources/ (2 new entities, 1 new concept)
✓ auto-build: site/ rebuilt (690 HTML files)
✓ auto-lint: 28 issues: 0 errors, 22 warnings, 6 info
```

### Common recipes

- Nightly cron-style sync of one project only:
  `sessionwiki sync --project my-project --no-auto-lint --since $(date -v-1d +%Y-%m-%d)`
- Vault-overlay round-trip: `sessionwiki sync --vault "~/Documents/Obsidian Vault"`

---

## `build` — compile the static HTML site

Turns `wiki/` markdown into `site/` HTML.

```bash
python3 -m sessionwiki build
python3 -m sessionwiki build --out ~/public_html
python3 -m sessionwiki build --search-mode tree
python3 -m sessionwiki build --synthesize --claude /usr/local/bin/claude
python3 -m sessionwiki build --vault ~/my-vault --out ~/site
```

### Flags

| Flag | What |
|---|---|
| `--out PATH` | Output directory. Default: `./site/`. |
| `--synthesize` | Call the `claude` CLI for overview synthesis (experimental). |
| `--claude PATH` | Path to the `claude` binary. Default: `/usr/local/bin/claude`. |
| `--search-mode {auto,tree,flat}` | Search routing mode (#53). `auto` picks tree vs flat from heading depth; `tree` / `flat` force the mode. Default: `auto`. |
| `--vault PATH` | Vault-overlay mode — build from an existing Obsidian / Logseq vault. Output still lands at `--out`. |

### Expected output (final lines)

```
  wrote search-index.json (7 KB meta) + 30 chunks (904 KB total) · tree mode · 64% deep pages
  wrote 7 AI-consumable exports: ai-readme.md, graph.jsonld, llms-full.txt, llms.txt, robots.txt, rss.xml, sitemap.xml
  wrote site/graph.html (interactive graph viewer)
  wrote site/prototypes/index.html (6 prototype states)
  wrote site/docs/ (94 editorial pages: hub + tutorials + style guide)
==> build complete: 703 HTML files, 61 MB
```

---

## `serve` — start a local HTTP server

```bash
python3 -m sessionwiki serve
python3 -m sessionwiki serve --port 9000
python3 -m sessionwiki serve --dir ~/public_html
python3 -m sessionwiki serve --open
```

### Flags

| Flag | What |
|---|---|
| `--dir PATH` | Directory to serve. Default: `./site/`. |
| `--port N` | Port. Default: `8765`. |
| `--host ADDR` | Bind address. Default: `127.0.0.1`. Use `0.0.0.0` to share on LAN. |
| `--open` | Open the browser at the root URL after starting. |

**Stdlib only** — it's `http.server` underneath. Safe for local use;
don't expose to the public internet.

---

## `adapters` — list every adapter + its status

```bash
python3 -m sessionwiki adapters
```

**Flags:** none.

**Expected output:**

```
Registered adapters:
  name              default   configured    description
  ----------------  --------  ------------  ----------------------------------------
  chatgpt           no        -             ChatGPT — parses conversations.json …
  claude_code       yes       ✓            Claude Code — reads ~/.claude/projects/
  codex_cli         no        ✓            Codex CLI — reads ~/.codex/sessions/
  copilot           no        -             GitHub Copilot — reads VS Code …
  cursor            no        -             Cursor — reads VS Code workspaceStorage
  gemini_cli        no        -             Gemini CLI — reads ~/.gemini/
  jira              no        -             Jira — reads via REST API
  meeting           no        -             Meeting transcripts (VTT/SRT)
  obsidian          no        -             Obsidian — reads a vault
  opencode          no        -             OpenCode / OpenClaw sessions
  web_clipper       no        -             Obsidian Web Clipper intake
```

Columns: **default** (runs when you don't pass `--adapter`), **configured**
(adapter sees a valid session store on this machine).

---

## `zcode` — export the ZCode session store

ZCode keeps sessions in a live SQLite database, not in per-session
JSONL files. This command writes an incremental, Claude-style JSONL
corpus that the `zcode` adapter can convert. `sessionwiki sync` runs the
same export automatically when the database exists and the `zcode`
adapter is selected.

```bash
python3 -m sessionwiki zcode export
python3 -m sessionwiki zcode export --project demo_project --dry-run
python3 -m sessionwiki zcode export --since 2026-09-01
python3 -m sessionwiki zcode export --project-root ~/dev
python3 -m sessionwiki zcode export --include-subagents
```

### `zcode export` flags

| Flag | What |
|---|---|
| `--db PATH` | ZCode database. Default: `~/.zcode/cli/db/db.sqlite`. |
| `--out-dir DIR` | JSONL output. Default: `~/.llmwiki/zcode/`. |
| `--state-file PATH` | Incremental state. Default: `<out-dir>/.export-state.json`. |
| `--since YYYY-MM-DD` | Only sessions updated on or after this date. |
| `--project SUBSTR` | Case-insensitive project path or slug filter. |
| `--project-root DIR` | Treat this directory as a project root (repeatable). |
| `--include-subagents` | Include `subagent_child` sessions. Off by default. |
| `--keep-stale` | Keep JSONL for sessions deleted from the database. |
| `--strict` | Exit 1 if any session fails, even when others exported. |
| `--dry-run` | Print counters without writing files. |

The export is read-only against ZCode's database and idempotent:
`session.time_updated` is the incremental key. A full export also
removes JSONL for sessions that disappeared from the database.

### `zcode autosync`

Portable scheduler entry point. It uses an OS-level lock instead of
`flock`, so it works on Linux, macOS, and Windows.

```bash
python3 -m sessionwiki zcode autosync
python3 -m sessionwiki zcode autosync --build
python3 -m sessionwiki zcode autosync --coalesce --build
```

| Flag | What |
|---|---|
| `--project SUBSTR` | Export/convert one project substring. |
| `--build` | Rebuild `site/` after conversion. |
| `--coalesce` | Run deterministic low-signal coalescing (no LLM). |
| `--lock-timeout SECONDS` | Wait for another autosync. Default: 600. |
| `--log PATH` | Log file. Default: `~/.llmwiki/zcode/autosync.log`. |
| `--quiet` | Write only to the log. |

### `zcode install`

Installs the ZCode `Stop` hook and one native scheduler entry:
systemd user timer (Linux), launchd agent (macOS), or Task Scheduler
(Windows). The hook is idempotent.

```bash
python3 -m sessionwiki zcode install --dry-run
python3 -m sessionwiki zcode install --scheduler systemd --at 03:30
python3 -m sessionwiki zcode install --scheduler launchd --coalesce
python3 -m sessionwiki zcode install --scheduler windows --no-build
```

| Flag | What |
|---|---|
| `--scheduler {auto,systemd,launchd,windows,none}` | Default: auto-detect. |
| `--at HH:MM` | Daily start time. Default: `03:30`. |
| `--python PATH` | Interpreter for the scheduled command. Default: current. |
| `--repo-root PATH` | Checkout used as `WorkingDirectory`. |
| `--build` / `--no-build` | Rebuild `site/` after sync (default: on). |
| `--coalesce` | Also run deterministic coalescing. |
| `--no-hook` | Skip the ZCode Stop hook. |
| `--dry-run` | Print changes only. |
| `--force` | Replace an existing autosync hook. |

---

## `opencode` — export the OpenCode V2 session store

OpenCode V2 keeps sessions in a live SQLite database
(`~/.local/share/opencode/opencode.db`). This command writes an
incremental, Claude-style JSONL corpus under `~/.llmwiki/opencode/`.
`sessionwiki sync` runs the same export automatically when the database
exists and the `opencode` adapter is selected.

```bash
python3 -m sessionwiki opencode export
python3 -m sessionwiki opencode export --project demo --dry-run
python3 -m sessionwiki opencode export --since 2026-09-01
python3 -m sessionwiki opencode export --include-subagents
```

### `opencode export` flags

| Flag | What |
|---|---|
| `--db PATH` | OpenCode database. Default: `~/.local/share/opencode/opencode.db`. |
| `--out-dir DIR` | JSONL output. Default: `~/.llmwiki/opencode/`. |
| `--state-file PATH` | Incremental state. Default: `<out-dir>/.export-state.json`. |
| `--since YYYY-MM-DD` | Only sessions updated on or after this date. |
| `--project SUBSTR` | Case-insensitive project path or slug filter. |
| `--project-root DIR` | Treat this directory as a project root (repeatable). |
| `--include-subagents` | Include child sessions. Off by default. |
| `--keep-stale` | Keep JSONL for sessions deleted from the database. |
| `--strict` | Exit 1 if any session fails, even when others exported. |
| `--dry-run` | Print counters without writing files. |

The export is read-only against OpenCode's database and idempotent:
`session_v2.time_updated` is the incremental key.

### `opencode autosync`

Portable scheduler entry point. It uses the shared OS-level lock, so
concurrent `session.idle` events cannot overlap.

```bash
python3 -m sessionwiki opencode autosync
python3 -m sessionwiki opencode autosync --build
```

| Flag | What |
|---|---|
| `--project SUBSTR` | Export/convert one project substring. |
| `--build` | Rebuild `site/` after conversion. |
| `--lock-timeout SECONDS` | Wait for another autosync. Default: 600. |
| `--log PATH` | Log file. Default: `~/.llmwiki/opencode/autosync.log`. |
| `--quiet` | Write only to the log. |

### `opencode install`

Writes the OpenCode server plugin that runs autosync on `session.idle`:

```text
$XDG_CONFIG_HOME/opencode/plugins/sessionwiki-autosync/index.ts   # default: ~/.config/opencode/...
```

The plugin calls `opencode autosync --lock-timeout 0`, so an idle event
that arrives while a cycle is running is skipped rather than queued.

```bash
python3 -m sessionwiki opencode install --dry-run
python3 -m sessionwiki opencode install
python3 -m sessionwiki opencode install --no-build --force
```

| Flag | What |
|---|---|
| `--python PATH` | Interpreter for the plugin command. Default: current. |
| `--repo-root PATH` | sessionwiki checkout used as the plugin working directory. |
| `--build` | Rebuild `site/` after each autosync (default: off). |
| `--no-build` | Explicitly disable rebuilds. |
| `--dry-run` | Print the path without writing. |
| `--force` | Replace an existing plugin file. |

---

## `doctor` — check the local install

Prints Python, `markdown`, virtualenv, config files, and ZCode database /
export paths. Exits `1` only when a required check fails.

```bash
python3 -m sessionwiki doctor
```

Typical output:

```
sessionwiki doctor 2.1.0
  [ok  ] python       3.12.4
  [ok  ] markdown     installed
  [ok  ] venv         active
  [ok  ] config       examples/sessions_config.json, config.local.json
  [ok  ] zcode_db     /home/me/.zcode/cli/db/db.sqlite
  [ok  ] zcode_export 842 session file(s) in /home/me/.llmwiki/zcode
  [warn] synthesis    9 raw session(s) not synthesized, 0 page(s) waiting for the agent
```

The `synthesis` check is informational: it never changes the exit code.

---

## `audit` — scan for usernames and secrets

Read-only pre-publish check over `raw/`, `wiki/`, and `site/`. It reports
matches; it does not edit files.

```bash
python3 -m sessionwiki audit
python3 -m sessionwiki audit --path site --json
python3 -m sessionwiki audit --fail-on-findings
```

| Flag | What |
|---|---|
| `--path PATH` | File or directory to scan (repeatable). Default: `raw/ wiki/ site/`. |
| `--username NAME` | Username to search for. Default: `redaction.real_username` or `$USER`. |
| `--json` | Emit a machine-readable report. |
| `--fail-on-findings` | Exit 1 when anything is found (publish gate). |

Findings are grouped as `username`, `secret` (built-in token patterns),
or `pattern` (user `redaction.extra_patterns`). Matched text is masked
in the preview.

---

## `graph` — build the knowledge graph

```bash
python3 -m sessionwiki graph                              # builtin wikilink graph
python3 -m sessionwiki graph --engine graphify             # AI-powered graph (requires graphifyy)
python3 -m sessionwiki graph --format json
python3 -m sessionwiki graph --format html
```

### Flags

| Flag | What |
|---|---|
| `--format {json,html,both}` | Output format(s). Default: `both`. |
| `--engine {builtin,graphify}` | Graph engine. `builtin` = stdlib wikilink graph. `graphify` = AI-powered with community detection, confidence-scored edges, god nodes. Requires `pip install graphifyy`. Default: `builtin`. |

**Builtin engine:** Emits `graph/graph.json` (nodes + edges) and/or `graph/graph.html`
(vis-network interactive viewer). The interactive version is also
auto-copied into `site/graph.html` on every `build`.

**Graphify engine:** Runs the [Graphify](https://github.com/safishamsi/graphify) pipeline:
tree-sitter AST extraction for code, semantic analysis for docs, Leiden community
detection, god-node analysis. Outputs to `graphify-out/` (graph.json, graph.html,
GRAPH_REPORT.md) and copies to `graph/` for build compatibility. Install:
`pip install sessionwiki[graph]` or `pip install graphifyy`.

---

## `export` — AI-consumable site exports

Single positional argument picks the format.

```bash
python3 -m sessionwiki export llms-txt
python3 -m sessionwiki export llms-full-txt
python3 -m sessionwiki export jsonld
python3 -m sessionwiki export sitemap
python3 -m sessionwiki export rss
python3 -m sessionwiki export robots
python3 -m sessionwiki export ai-readme
python3 -m sessionwiki export all --out ~/custom-site
```

### Positional

| Value | Writes |
|---|---|
| `llms-txt` | `site/llms.txt` — llmstxt.org spec |
| `llms-full-txt` | `site/llms-full.txt` — flattened plain-text corpus (≤ 5 MB) |
| `jsonld` | `site/graph.jsonld` — schema.org entity graph |
| `sitemap` | `site/sitemap.xml` |
| `rss` | `site/rss.xml` |
| `robots` | `site/robots.txt` |
| `ai-readme` | `site/ai-readme.md` |
| `all` | all of the above |

### Flags

| Flag | What |
|---|---|
| `--out PATH` | Output directory. Default: `./site/`. |

---

## `lint` — run 14 wiki-quality rules

```bash
python3 -m sessionwiki lint
python3 -m sessionwiki lint --json
python3 -m sessionwiki lint --fail-on-errors
python3 -m sessionwiki lint --rules link_integrity,orphan_detection
python3 -m sessionwiki lint --include-llm
python3 -m sessionwiki lint --wiki-dir ~/another-wiki
```

### Flags

| Flag | What |
|---|---|
| `--wiki-dir PATH` | Wiki dir. Default: `./wiki`. |
| `--rules NAMES` | Comma-separated rule names. Default: all applicable. |
| `--include-llm` | Also run the three LLM-powered rules (requires a callback wired in). |
| `--json` | JSON output. |
| `--fail-on-errors` | Exit 1 if any error-severity issues. |

### Rules

8 structural (`frontmatter_completeness`, `frontmatter_validity`,
`link_integrity`, `orphan_detection`, `content_freshness`,
`entity_consistency`, `duplicate_detection`, `index_sync`) + 3 LLM-powered
(`contradiction_detection`, `claim_verification`, `summary_accuracy`) +
2 v1.1+ (`stale_candidates`, `cache_tier_consistency`).

### Expected output

```
  scanned 31 pages
  28 issues: 0 errors, 22 warnings, 6 info

## link_integrity (22)
  [warning] entities/GPT5.md: broken wikilink [[MultimodalModels]]
  ...
```

---

## `candidates` — approval workflow

Positional `action` picks `list` / `promote` / `merge` / `discard`.

```bash
python3 -m sessionwiki candidates list
python3 -m sessionwiki candidates list --stale --stale-days 60
python3 -m sessionwiki candidates list --json
python3 -m sessionwiki candidates promote --slug NewEntity
python3 -m sessionwiki candidates promote --slug NewEntity --kind concepts
python3 -m sessionwiki candidates merge --slug DuplicateFoo --into Foo
python3 -m sessionwiki candidates discard --slug BogusEntity --reason "LLM hallucinated"
```

### Flags

| Flag | What |
|---|---|
| `--slug NAME` | Candidate slug. **Required** for `promote` / `merge` / `discard`. |
| `--into NAME` | For `merge`: target slug. |
| `--reason TEXT` | For `discard`: why (written to archive's `.reason.txt`). |
| `--kind {entities,concepts,sources,syntheses}` | Subtree. Auto-detected if omitted. |
| `--wiki-dir PATH` | Wiki dir. Default: `./wiki`. |
| `--stale` | With `list`: only stale candidates. |
| `--stale-days N` | Staleness threshold. Default: 30. |
| `--json` | JSON output for `list`. |

See [`guides/existing-vault.md`](../guides/existing-vault.md) for the
round-trip semantics when a candidate lives inside a vault.

---

## `remember` — store a fact as a candidate

Saves one fact to `wiki/candidates/concepts/` with `status: candidate` and
`origin: human`. The trusted folders (`wiki/concepts/`, `wiki/entities/`)
never receive the page directly; review it with `candidates list` and then
promote, merge or discard it.

```bash
python3 -m sessionwiki remember "The vault keeps secrets in 1Password."
python3 -m sessionwiki remember "Deploys go through the kumquat pipeline." --title "Deploy pipeline" --project ai-newsletter
python3 -m sessionwiki candidates list
```

The file name is the TitleCase of the title words, letters and digits only,
capped at 60 characters; a taken name gets `-2`, `-3`, …. A title with no
letters or digits falls back to `Remembered-<YYYYMMDD-HHMMSS>`.

### Flags

| Flag | What |
|---|---|
| `--title TITLE` | Page title. Default: the first 8 words of the fact. |
| `--project NAME` | Project name and `[[ProjectEntity]]` link. Default: the current folder name. |

### Expected output

```
  remembered → wiki/candidates/concepts/TheVaultKeepsSecretsIn1Password.md
  review with: sessionwiki candidates list
```

---

## `synthesize` — LLM-backed source-page synthesis

```bash
python3 -m sessionwiki synthesize --check            # probe the backend
python3 -m sessionwiki synthesize --estimate         # cost preview, no API calls
python3 -m sessionwiki synthesize --force            # re-synth everything
python3 -m sessionwiki synthesize --coalesce-only    # deterministic cleanup, no LLM
python3 -m sessionwiki synthesize                    # real run
```

### Flags

| Flag | What |
|---|---|
| `--check` | Probe backend availability + exit (0 if reachable). |
| `--force` | Ignore state, re-synth every source. |
| `--estimate` | Print cached-vs-fresh token + dollar estimate (#50). |
| `--coalesce-only` | Merge low-signal sessions into cluster pages; no backend call. |
| `--backfill-only` | Add the user's request (`description`) to existing pages; no LLM. |
| `--list-pending` | List prompts waiting for the agent-delegate backend. |
| `--complete UUID` | Complete one pending synthesis from `--body` or stdin. |
| `--page PATH` | Target page for `--complete`. |
| `--body PATH` | Body file for `--complete` (default: stdin). |
| `--max-sessions N` | Synthesize at most N sessions; the rest wait for the next run. |
| `--vault PATH` | Keep `raw/`, `wiki/sources/` and the state file under a vault root. |

Backend is picked from `synthesis.backend` in `sessions_config.json`:
`dummy` (default, metadata-only), `extractive` (no model, no network),
`ollama`, `openai` (any OpenAI-compatible server) or `agent` (pending
prompts for the running agent). See
[`reference/prompt-caching.md`](prompt-caching.md).

### Long sessions (chunking)

A raw session can be megabytes of markdown. One LLM call cannot carry
it, and the backends used to keep only the head and the tail —
silently dropping the middle. Sessions above `synthesis.max_body_chars`
(default 40 000 for `openai`, 8 000 for `ollama`) now go through
map-reduce instead:

1. The body is split on `### Turn N` boundaries into chunks no larger
   than `chunking.chunk_chars` (also capped by `max_body_chars`). An
   oversized turn is split on paragraphs; code fences stay balanced.
2. Each chunk becomes a digest (decisions, paths, commands, errors,
   outcome, quotes), at most `chunking.digest_chars` characters.
3. Digests are reduced through the normal `source_page` prompt. If
   they still exceed `chunking.reduce_chars`, they are merged in
   batches first (hierarchical reduce, up to `max_depth` levels).

Every map and merge call is cached in `.llmwiki-synth-cache/`
(gitignored) by prompt, body and backend name. A failed run re-pays
only for the chunks that failed. `chunking.max_chunks` is a hard cap
per session (default 200); above it the head and tail are kept and the
omitted middle is named in the prompt, so the page can mention the gap.

```json
"synthesis": {
  "max_body_chars": 96000,
  "chunking": {
    "enabled": true,
    "chunk_chars": 96000,
    "digest_chars": 2000,
    "reduce_chars": 24000,
    "max_chunks": 200,
    "cache": true
  }
}
```

Raise `max_body_chars` and `chunk_chars` together for a large-context
model: with 96 000 chars a 1.5M-character session is ~16 map calls
instead of 125. The agent-delegate and dummy backends opt out —
the first writes one pending prompt per session, the second ignores
the body.

### Auto-tagging (#351)

Every `synthesize` call now produces **topical** tags alongside the
deterministic baseline.  The synthesizer emits a
`<!-- suggested-tags: prompt-caching, rag, github-actions -->` block
as the first line of its response; the pipeline parses it, strips it
from the body, and merges the tags into frontmatter with:

- **Baseline preserved** — adapter, project slug, model family stay.
- **Maintainer wins** — on `--force`, whatever you added via
  `sessionwiki tag add` is kept at the front of the list.
- **Stop-word filter** — the LLM can't re-add boilerplate tags
  (`session`, `summary`, `claude-code`, etc.).
- **Cap 5** — max 5 AI tags per page to prevent drift.
- **Near-dup rejection** — `prompt-cache` is blocked when
  `prompt-caching` is already on the page (threshold 0.80 + prefix
  check).

No extra API round-trip — rides the existing synthesis call, so cost
estimates from `--estimate` are unchanged.  If the backend returns no
suggested-tags block (dummy backend, malformed output), the page still
ships with baseline tags.

---

## `version` — print the installed version

```bash
python3 -m sessionwiki version
python3 -m sessionwiki --version
```

Both print `sessionwiki <version>`.

---

## `mcp` — run the MCP server on stdio

```bash
sessionwiki mcp
SESSIONWIKI_HOME=~/sessionwiki uvx sessionwiki mcp
```

Same server as `python3 -m sessionwiki.mcp`: JSON-RPC over stdin/stdout, 15
`wiki_*` tools. MCP clients and the MCP Registry start the PyPI package this
way. The data root is `$SESSIONWIKI_HOME` when set, the source checkout when run
from a clone, and the current directory otherwise. MCP clients choose the working
directory themselves, so set `SESSIONWIKI_HOME` in the client config.

---

## `recall` — a project's recent sessions

```bash
sessionwiki recall                          # project = current folder name
sessionwiki recall --project llm-wiki --limit 5
sessionwiki recall --format hook            # SessionStart JSON (additionalContext)
sessionwiki recall --format json            # machine-readable list
sessionwiki recall --prompt-hook            # UserPromptSubmit hook (opt-in)
```

Prints the latest sessions of one project, newest first: date, the
user's original request, the first sentence of the summary and the
page path. Sessions not synthesised yet come from `raw/sessions/`.
Prints nothing when the project has no sessions; `--format json` prints
a document with an empty `sessions` list instead. The newest session also
gets a `handoff` block: the end of its last assistant turn, stripped of
code blocks and headings and capped at 400 characters.

Meant for a `SessionStart` hook: agents rarely call memory tools on
their own, so the hook puts recent work into context up front. With
`--project` omitted it reads the hook's JSON from stdin and takes the
project from its `cwd`. The Claude Code plugin and
`sessionwiki zcode install` set the hook up.

`--prompt-hook` is a separate `UserPromptSubmit` hook. It reads the prompt
from stdin and prints up to three related pages, filtered to the session's
project. It is silent unless `SESSIONWIKI_PROMPT_RECALL=1` is set, and every
error path returns 0 without output. The score floor is 40 by default;
`SESSIONWIKI_PROMPT_RECALL_MIN_SCORE` overrides it.

---

## `import-memory` — mirror Claude Code auto memory

```bash
sessionwiki import-memory                     # ~/.claude/projects, writes
sessionwiki import-memory --dry-run           # list what would change
sessionwiki import-memory --store /path/to/projects
```

Claude Code keeps its own memory under
`~/.claude/projects/<dir>/memory/*.md`. This command copies each file to
`wiki/notes/claude-memory/<project>/` as a `note` page with `origin: human`,
so the wiki sees that memory and synthesis never rewrites it. The body and
the description pass through the same redaction as `sync`; `source_path`
uses a `~`-relative path, never the absolute home directory.

A file is rewritten only when its content changes, and an existing page
without `origin: human` is skipped, never overwritten. Nothing is deleted:
a page stays when its Claude memory file is gone. `--dry-run` prints the
files that would change and writes nothing.

---

## `query` — search the wiki

```bash
python3 -m sessionwiki query "what projects am I working on"
python3 -m sessionwiki query "Flutter mobile" --limit 3
python3 -m sessionwiki query "Flutter mobile" --json
python3 -m sessionwiki query "release" --project llm-wiki --type source
python3 -m sessionwiki query "Flutter mobile" --tag claude-code --date-from 2026-11-01
python3 -m sessionwiki query "Flutter mobile" --graph --depth 2 --budget 1000
```

Runs the same ranked lexical search with one graph hop as MCP
`wiki_query`: wiki pages first, transcripts only when no page matches
(or always with `--raw`). Works without the optional graph engine;
`--graph` switches to graphify.

### Flags

| Flag | What |
|---|---|
| `--limit N` | Pages to return. Default: `5`. |
| `--json` | Print `hits` (`path`, `score`, `via`, `snippet`) as JSON. |
| `--project NAME` | Only pages whose frontmatter `project` is `NAME`. |
| `--type TYPE` | Only this page type: `source`, `entity`, `concept`, … |
| `--tag TAG` | Only pages with this tag, e.g. the agent (`claude-code`, `zcode`). |
| `--date-from YYYY-MM-DD` | Only pages dated on or after this day (inclusive). |
| `--date-to YYYY-MM-DD` | Only pages dated on or before this day (inclusive). |
| `--raw` | Always rank raw transcripts too. |
| `--no-raw` | Never read raw transcripts. |
| `--graph` | Use the graphify engine instead of the ranked search. |
| `--depth N` | graphify BFS depth (with `--graph`). Default: `3`. |
| `--budget N` | graphify token budget (with `--graph`). Default: `2000`. |

Filters apply to wiki pages and to raw transcripts; a page that fails them
never appears, including through the graph hop. An unparseable date is
ignored, not an error. `--graph` ignores the filters.

Without `--raw` or `--no-raw`, transcripts are read only when no wiki
page matches. `--graph` requires Graphify (`pip install sessionwiki[graph]`)
and a graph built by `sessionwiki graph`.

---

## `all` — run the full pipeline

Convenience entry point that runs `build` → `graph` → `export all` → `lint`
in order. This is the one command to run after `sync` to produce a
CI-ready site.

```bash
python3 -m sessionwiki all
python3 -m sessionwiki all --graph-engine builtin   # skip optional graphify
python3 -m sessionwiki all --skip-graph --strict    # fail CI on any lint issue
```

### Flags

| Flag | What |
|---|---|
| `--out DIR` | Output dir for build + export. Default: `site/`. |
| `--search-mode {auto,tree,flat}` | Forwarded to `build`. Default: `auto`. |
| `--graph-engine {builtin,graphify}` | Forwarded to `graph`. Default: `graphify`. |
| `--skip-graph` | Skip the graph step entirely (useful when graphify is not installed). |
| `--fail-fast` | Stop at the first non-zero step. Default: continue, report the worst exit code. |
| `--strict` | Exit `2` if `lint` reports any errors/warnings. |

Exit codes:

- `0` — every step succeeded.
- non-zero — forwarded from the first (or worst) failing step.
- `2` — `--strict` and lint reported issues.

---

## Exit codes (conventions)

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Operation failed (user-visible error) |
| `2` | Usage error (bad flags, missing file, etc.) |

Subcommands document their own non-zero exit conditions where relevant
(`lint --fail-on-errors`).

---

## Related

- **[Slash commands](slash-commands.md)** — the `/wiki-*` surface used from Claude Code.
- **[UI reference](ui.md)** — every screen + nav surface on the compiled site.
- **[Configuration](../configuration.md)** · **[Full configuration reference](../configuration-reference.md)**.
