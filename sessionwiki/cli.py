"""sessionwiki CLI.

Usage:
    python3 -m sessionwiki <subcommand> [options]

Subcommands:
    init              Scaffold raw/, wiki/, site/ directories
    sync              Convert new .jsonl sessions to markdown
    build             Compile static HTML site from raw/ + wiki/
    serve             Start local HTTP server
    adapters          List available session-store adapters
    graph             Build the knowledge graph (graph/graph.json + graph.html)
    export            Export AI-consumable formats: llms-txt, llms-full-txt, jsonld, sitemap, rss, robots, ai-readme, marp
    lint              Run lint rules against the wiki
    candidates        List / promote / merge / discard candidate pages
    remember          Store a fact as a candidate page for review
    synthesize        Synthesize wiki source pages from raw sessions via LLM
    all               Run the full pipeline: build → graph → export all → lint
                      (optional: synthesize first with --with-synth)
    version           Print version and exit
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

from sessionwiki import __version__, REPO_ROOT
from sessionwiki.adapters import REGISTRY, discover_adapters
# #v1378-review (#691 follow-up): hoist these re-exports from mid-module
# to here so the file passes E402 cleanly. They re-export business
# logic that lives in the proper domain modules now (#611) — kept here
# for any caller still importing from sessionwiki.cli.
from sessionwiki.adapters.status import adapter_status as _adapter_status  # noqa: F401
from sessionwiki.synth.estimate import synthesize_estimate_report  # noqa: F401
# #691 / #arch-h8: extracted business logic moves out of cli.py.
# cli.py keeps thin re-export wrappers for back-compat with anyone
# doing `from sessionwiki.cli import cmd_all, cmd_sync_status, ...`.
from sessionwiki.config_schedule import (  # noqa: F401
    load_schedule_config as _load_schedule_config,
    should_run_after_sync as _should_run_after_sync,
)
from sessionwiki.pipeline import run_pipeline as _run_pipeline
from sessionwiki.sync.status import (  # noqa: F401
    cmd_sync_status,
    resolve_key_exists as _resolve_key_exists,
)
from sessionwiki.synth.cli_helpers import (  # noqa: F401
    complete as _synthesize_complete,
    list_pending as _synthesize_list_pending,
)


def cmd_version(args: argparse.Namespace) -> int:
    print(f"sessionwiki {__version__}")
    return 0


def _project_from_hook_input() -> str:
    """Project name from a hook's JSON on stdin (``cwd``), or ''."""
    try:
        if sys.stdin.isatty():
            return ""
        data = json.loads(sys.stdin.read() or "{}")
    except (OSError, ValueError):
        return ""
    cwd = data.get("cwd") if isinstance(data, dict) else None
    return Path(cwd).name if isinstance(cwd, str) and cwd else ""


def _first_sentence(body: str, limit: int = 200) -> str:
    m = re.search(r"^## Summary\s*\n+(.+)", body, re.MULTILINE)
    text = (m.group(1) if m else "").strip()
    end = text.find(". ")
    text = text[: end + 1] if end != -1 else text
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _is_subagent(meta: dict[str, Any], filename: str) -> bool:
    """Subagent runs are pieces of a parent session, not work to recall."""
    return meta.get("is_subagent") in (True, "true") or "-subagent-" in filename


def _recent_sessions(project: str, limit: int) -> list[tuple[str, str, str, str]]:
    """``(date, request, summary, path)`` of the project's latest sessions,
    newest first. Sessions without a wiki page yet come from raw/."""
    from sessionwiki._frontmatter import parse_frontmatter

    items: list[tuple[str, str, str, str]] = []
    slugs: set[str] = set()
    sources = REPO_ROOT / "wiki" / "sources"
    for page in sources.rglob("*.md") if sources.is_dir() else []:
        try:
            meta, body = parse_frontmatter(page.read_text(encoding="utf-8"))
        except OSError:
            continue
        if str(meta.get("project", "")) != project or meta.get("merged_sessions"):
            continue
        slugs.add(str(meta.get("slug", "")))
        if _is_subagent(meta, page.name):
            continue
        items.append((str(meta.get("date", "")), str(meta.get("description", "")),
                      _first_sentence(body), str(page.relative_to(REPO_ROOT))))
    raw = REPO_ROOT / "raw" / "sessions"
    for transcript in raw.rglob("*.md") if raw.is_dir() else []:
        try:
            with transcript.open("rb") as f:
                head = f.read(8 * 1024).decode("utf-8", errors="replace")
        except OSError:
            continue
        meta, _ = parse_frontmatter(head)
        if str(meta.get("project", "")) != project or str(meta.get("slug", "")) in slugs:
            continue
        if _is_subagent(meta, transcript.name):
            continue
        items.append((str(meta.get("date", "")), str(meta.get("description", "")),
                      "", str(transcript.relative_to(REPO_ROOT))))
    items.sort(key=lambda item: (item[0], item[3]), reverse=True)
    return items[:limit]


_TURN_RE = re.compile(r"^### Turn \d+ — (User|Assistant)\s*$", re.MULTILINE)
_HANDOFF_TAIL_BYTES = 64 * 1024
_HANDOFF_MAX_CHARS = 400


def _raw_path_for(path: str) -> Path | None:
    """The raw transcript behind a recall item (a raw path or a wiki page)."""
    p = REPO_ROOT / path
    if path.startswith("raw/"):
        return p if p.is_file() else None
    from sessionwiki._frontmatter import parse_frontmatter
    try:
        with p.open("rb") as f:
            meta, _ = parse_frontmatter(f.read(8 * 1024).decode("utf-8", errors="replace"))
    except OSError:
        return None
    src = str(meta.get("source_file", "")).strip()
    raw = REPO_ROOT / src if src else None
    return raw if raw is not None and raw.is_file() else None


def _last_assistant_text(raw: Path) -> str:
    """First characters of the last assistant turn, read from the file's tail."""
    try:
        with raw.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - _HANDOFF_TAIL_BYTES))
            tail = f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    turns = list(_TURN_RE.finditer(tail))
    for i in range(len(turns) - 1, -1, -1):
        if turns[i].group(1) != "Assistant":
            continue
        end = turns[i + 1].start() if i + 1 < len(turns) else len(tail)
        text = tail[turns[i].end():end]
        text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
        text = re.sub(r"^#+ .*$", " ", text, flags=re.MULTILINE)
        text = " ".join(text.split())
        if not text:
            continue
        return text if len(text) <= _HANDOFF_MAX_CHARS else text[: _HANDOFF_MAX_CHARS - 1].rstrip() + "…"
    return ""


def cmd_recall(args: argparse.Namespace) -> int:
    """Print a project's recent sessions for a SessionStart hook, so the
    agent starts with them in context instead of having to ask."""
    if args.prompt_hook:
        return _prompt_recall()
    from sessionwiki.mcp.server import DATA_NOTICE

    project = args.project or _project_from_hook_input() or Path.cwd().name
    items = _recent_sessions(project, args.limit)
    handoff = ""
    if items:
        raw = _raw_path_for(items[0][3])
        handoff = _last_assistant_text(raw) if raw else ""
    if args.format == "json":
        print(json.dumps({
            "project": project,
            "notice": DATA_NOTICE,
            "sessions": [
                {"date": day, "request": request, "summary": summary, "path": path}
                for day, request, summary, path in items
            ],
            "handoff": (
                {"path": items[0][3], "date": items[0][0], "text": handoff}
                if items else None
            ),
        }, ensure_ascii=False, indent=2))
        return 0
    if not items:
        return 0
    lines = [f"Recent sessions in project '{project}' (sessionwiki):", DATA_NOTICE, ""]
    for day, request, summary, path in items:
        what = f"«{request}»" if request else "(no request recorded)"
        note = summary or "not in the wiki yet"
        lines.append(f"- {day} {what} — {note} ({path})")
    if handoff:
        what = f"«{items[0][1]}»" if items[0][1] else "(no request recorded)"
        lines += ["", f"Last session ended with ({what}, {items[0][0]}):", handoff]
    lines += [
        "",
        "Before you ask the user about earlier work, call the wiki_query tool; "
        "open a page with wiki_read_page.",
    ]
    text = "\n".join(lines)
    if args.format == "hook":
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "SessionStart", "additionalContext": text,
        }}, ensure_ascii=False))
    else:
        print(text)
    return 0


_PROMPT_RECALL_MIN_SCORE = 40.0  # median top score of 20 recent distinct prompts
_PROMPT_RECALL_MAX_PAGES = 3
_PROMPT_RECALL_MIN_CHARS = 20


def _prompt_recall() -> int:
    """UserPromptSubmit hook: add related wiki pages for the prompt on stdin.

    Runs on every prompt, so it is opt-in (``SESSIONWIKI_PROMPT_RECALL=1``)
    and silent on every error path: a hook must never block the prompt.
    """
    if os.environ.get("SESSIONWIKI_PROMPT_RECALL") != "1":
        return 0
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except (OSError, ValueError):
        return 0
    if not isinstance(data, dict):
        return 0
    prompt = str(data.get("prompt") or "").strip()
    if len(prompt) < _PROMPT_RECALL_MIN_CHARS or prompt.startswith("/"):
        return 0
    cwd = data.get("cwd")
    project = Path(cwd).name if isinstance(cwd, str) and cwd else ""
    from sessionwiki.mcp.server import DATA_NOTICE, rank_query
    try:
        result = rank_query(
            prompt, max_pages=_PROMPT_RECALL_MAX_PAGES, include_raw=False,
            filters={"project": project} if project else None,
        )
    except Exception:  # a hook must never block the user's prompt
        return 0
    hits = [h for h in result["hits"] if h["score"] >= _PROMPT_RECALL_MIN_SCORE]
    if not hits:
        return 0
    lines = ["Related past work (sessionwiki):", DATA_NOTICE, ""]
    for h in hits:
        snippet = " ".join(h["snippet"].split())[:200]
        lines.append(f"- {h['path']} — {snippet}")
    lines += ["", "Read the page with wiki_read_page before you ask the user about it."]
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": "\n".join(lines),
    }}, ensure_ascii=False))
    return 0


def cmd_import_memory(args: argparse.Namespace) -> int:
    """Mirror Claude Code auto memory files into ``wiki/notes/``.

    The memory files change in place and ``raw/`` is immutable, so the
    pages are written directly to ``wiki/notes/claude-memory/<project>/``
    with ``origin: human``.  Bodies pass through the same redactor as
    ``sync``; an existing destination without ``origin: human`` is never
    overwritten.
    """
    from sessionwiki.adapters.claude_code import ClaudeCodeAdapter
    from sessionwiki.convert import load_config_layered
    from sessionwiki.memory_import import import_claude_memory

    store = (
        Path(args.store).expanduser()
        if args.store
        else ClaudeCodeAdapter.session_store_path
    )
    if not store.is_dir():
        print(f"error: Claude Code memory store not found: {store}", file=sys.stderr)
        return 2

    result = import_claude_memory(
        store, REPO_ROOT / "wiki", load_config_layered(), dry_run=args.dry_run
    )
    prefix = "would write" if args.dry_run else "wrote"
    for rel in result["written"]:
        print(f"  {prefix} wiki/{rel}")
    for item in result["skipped"]:
        print(f"  skipped wiki/{item['path']}: {item['reason']}")
    verb = "to write" if args.dry_run else "written"
    print(
        f"{len(result['written'])} file(s) {verb}, "
        f"{result['unchanged']} unchanged, {len(result['skipped'])} skipped"
    )
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    """Run the MCP server on stdin/stdout (same as `python3 -m sessionwiki.mcp`)."""
    from sessionwiki.mcp.server import main as mcp_main

    return mcp_main()


def cmd_all(args: argparse.Namespace) -> int:
    """Run the full wiki pipeline end-to-end: build → graph → export all → lint.

    Thin shim — the implementation lives in ``sessionwiki.pipeline`` (#691).
    """
    return _run_pipeline(args)


def cmd_init(args: argparse.Namespace) -> int:
    """Create raw/, wiki/, site/ directory structure."""
    for name in ("raw/sessions", "wiki/sources", "wiki/entities", "wiki/concepts", "wiki/syntheses", "site"):
        p = REPO_ROOT / name
        p.mkdir(parents=True, exist_ok=True)
        keep = p / ".gitkeep"
        if not keep.exists() and not any(p.iterdir()):
            keep.touch()
        print(f"  {p.relative_to(REPO_ROOT)}/")

    # Also create hot/ for per-project caches
    hot_dir = REPO_ROOT / "wiki" / "hot"
    hot_dir.mkdir(parents=True, exist_ok=True)
    keep = hot_dir / ".gitkeep"
    if not keep.exists():
        keep.touch()

    # Seed index/log/overview + navigation files if not present
    seeds = {
        "wiki/index.md": (
            "# Wiki Index\n\n"
            "<!-- #387 U6: each section heading carries a (count) so the index\n"
            "stays scannable as the wiki grows past ~50 pages. Update the count\n"
            "in the heading when adding/removing pages. The index is otherwise\n"
            "kept flat (no nested folders) so a single grep/scan can find any\n"
            "page without descending into a tree. -->\n\n"
            "## Overview (1)\n- [Overview](overview.md)\n\n"
            "## Sources (0)\n\n"
            "## Entities (0)\n\n"
            "## Projects (0)\n\n"
            "## Concepts (0)\n\n"
            "## Syntheses (0)\n"
        ),
        "wiki/overview.md": '---\ntitle: "Overview"\ntype: synthesis\nsources: []\nlast_updated: ""\n---\n\n# Overview\n\n*This page is maintained by your coding agent.*\n',
        "wiki/log.md": "# Wiki Log\n\nAppend-only chronological record of all operations.\n\nFormat: `## [YYYY-MM-DD] <operation> | <title>`\n\n---\n",
        "wiki/hints.md": '---\ntitle: "Navigation Hints"\ntype: navigation\nlast_updated: ""\n---\n\n# Hints\n\nWriting conventions, entity naming rules, and navigation guidance.\nCustomize this file for your project.\n',
        "wiki/hot.md": '---\ntitle: "Hot Cache"\ntype: navigation\nlast_updated: ""\nauto_maintained: true\n---\n\n# Hot Cache\n\n*Auto-maintained. Last 10 session summaries.*\n',
        "wiki/MEMORY.md": '---\ntitle: "Cross-Session Memory"\ntype: navigation\nlast_updated: ""\nmax_lines: 200\n---\n\n# MEMORY\n\n*200-line cap. Auto-consolidated by Auto Dream.*\n\n## User\n\n## Feedback\n\n## Project\n\n## Reference\n',
        "wiki/SOUL.md": '---\ntitle: "Wiki Identity"\ntype: navigation\nlast_updated: ""\n---\n\n# SOUL\n\nThis wiki compiles raw session transcripts into structured, interlinked pages.\nCustomize this file to set your wiki\'s voice and purpose.\n',
        "wiki/CRITICAL_FACTS.md": '---\ntitle: "Critical Facts"\ntype: navigation\nlast_updated: ""\n---\n\n# Critical Facts\n\n- raw/ is immutable — never modify files under raw/\n- Wiki uses Obsidian-style double-bracket syntax for cross-references\n- Confidence: 0.0-1.0, 4-factor formula\n- Lifecycle: draft > reviewed > verified > stale > archived\n',
    }

    # v1.0 (#153): seed dashboard.md from examples/wiki_dashboard.md template
    dashboard_template = REPO_ROOT / "examples" / "wiki_dashboard.md"
    dashboard_target = REPO_ROOT / "wiki" / "dashboard.md"
    if dashboard_template.is_file() and not dashboard_target.is_file():
        dashboard_target.write_text(
            dashboard_template.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        print(f"  seeded wiki/dashboard.md")
    for rel, content in seeds.items():
        p = REPO_ROOT / rel
        if not p.exists():
            p.write_text(content, encoding="utf-8")
            print(f"  seeded {p.relative_to(REPO_ROOT)}")
    return 0


def _maybe_export_zcode(args: argparse.Namespace) -> None:
    """Refresh the ZCode JSONL corpus before a sync, when applicable.

    ZCode sessions live in a live SQLite database; the sessionwiki adapter
    reads a flat JSONL export. Without this step `sessionwiki sync` (and the
    MCP ``wiki_sync`` tool, which shells out to it) would silently miss
    new sessions. The export is incremental, so an unchanged store costs
    one read-only scan.

    Failures are warnings, not sync failures: the existing JSONL corpus
    is still usable.
    """
    if not getattr(args, "zcode_export", False):
        return

    try:
        config = _load_run_config()
    except Exception:
        config = {}
    zcode_cfg = config.get("zcode") if isinstance(config, dict) else None

    adapters = getattr(args, "adapter", None)
    if adapters:
        from sessionwiki.adapters import discover_adapters, resolve_adapter_name

        discover_adapters()
        selected = {resolve_adapter_name(name) for name in adapters}
        if "zcode" not in selected:
            return
    elif isinstance(zcode_cfg, dict) and zcode_cfg.get("enabled") is False:
        # Auto-selection follows the config toggle. An explicit
        # `--adapter zcode` overrides it, matching convert_all().
        return

    project_roots = None
    if isinstance(zcode_cfg, dict):
        configured_roots = zcode_cfg.get("project_roots")
        if isinstance(configured_roots, list):
            project_roots = configured_roots

    from sessionwiki.zcode.export import (
        DEFAULT_DB,
        DEFAULT_OUT_DIR,
        parse_since,
        run_export,
    )

    db = Path(getattr(args, "zcode_db", None) or DEFAULT_DB).expanduser()
    if not db.is_file():
        return
    out_dir = Path(getattr(args, "zcode_out_dir", None) or DEFAULT_OUT_DIR).expanduser()

    try:
        since_ms = parse_since(getattr(args, "since", None))
    except ValueError as exc:
        print(f"  warning: zcode export skipped: {exc}", file=sys.stderr)
        return

    print(f"  zcode export: {db} -> {out_dir}")
    try:
        stats = run_export(
            db,
            out_dir,
            since=since_ms,
            project=getattr(args, "project", None),
            include_subagents=False,
            dry_run=bool(getattr(args, "dry_run", False)),
            project_roots=project_roots,
        )
    except Exception as exc:  # noqa: BLE001 - sync must survive a bad DB
        print(f"  warning: zcode export failed: {exc}", file=sys.stderr)
        return

    print(
        (
            f"  zcode export (dry-run): {stats.get('exported', 0)} would change, "
            f"{stats.get('unchanged', 0)} unchanged"
            if getattr(args, "dry_run", False)
            else f"  zcode export: {stats.get('exported', 0)} exported, "
            f"{stats.get('unchanged', 0)} unchanged"
        )
    )
    if stats.get("errors"):
        print(
            f"  warning: zcode export finished with {stats['errors']} error(s)",
            file=sys.stderr,
        )


def _maybe_export_opencode(args: argparse.Namespace) -> None:
    """Refresh the OpenCode JSONL corpus before a sync, when applicable.

    OpenCode V2 sessions live in a live SQLite database; the sessionwiki
    adapter reads a JSONL export. Without this step ``sessionwiki sync``
    would silently miss new OpenCode sessions. The export is incremental,
    so an unchanged store costs one read-only scan.

    Failures are warnings, not sync failures: the existing JSONL corpus
    is still usable.
    """
    if not getattr(args, "opencode_export", False):
        return

    try:
        config = _load_run_config()
    except Exception:
        config = {}
    opencode_cfg = config.get("opencode") if isinstance(config, dict) else None

    adapters = getattr(args, "adapter", None)
    if adapters:
        from sessionwiki.adapters import discover_adapters, resolve_adapter_name

        discover_adapters()
        selected = {resolve_adapter_name(name) for name in adapters}
        if "opencode" not in selected:
            return
    elif isinstance(opencode_cfg, dict) and opencode_cfg.get("enabled") is False:
        return

    from sessionwiki.opencode.export import (
        DEFAULT_DB,
        DEFAULT_OUT_DIR,
        parse_since,
        run_export,
    )

    db = Path(getattr(args, "opencode_db", None) or DEFAULT_DB).expanduser()
    if not db.is_file():
        return
    out_dir = Path(DEFAULT_OUT_DIR).expanduser()

    try:
        since_ms = parse_since(getattr(args, "since", None))
    except ValueError as exc:
        print(f"  warning: opencode export skipped: {exc}", file=sys.stderr)
        return

    print(f"  opencode export: {db} -> {out_dir}")
    try:
        stats = run_export(
            db,
            out_dir,
            since=since_ms,
            project=getattr(args, "project", None),
            include_subagents=False,
            dry_run=bool(getattr(args, "dry_run", False)),
        )
    except Exception as exc:  # noqa: BLE001 - sync must survive a bad DB
        print(f"  warning: opencode export failed: {exc}", file=sys.stderr)
        return

    print(
        (
            f"  opencode export (dry-run): {stats.get('exported', 0)} would change, "
            f"{stats.get('unchanged', 0)} unchanged"
            if getattr(args, "dry_run", False)
            else f"  opencode export: {stats.get('exported', 0)} exported, "
            f"{stats.get('unchanged', 0)} unchanged"
        )
    )
    if stats.get("errors"):
        print(
            f"  warning: opencode export finished with {stats['errors']} error(s)",
            file=sys.stderr,
        )


def cmd_sync(args: argparse.Namespace) -> int:
    """Convert .jsonl sessions to markdown using the enabled adapters."""
    # G-03 (#289): `sync --status` short-circuits into the status reporter.
    if getattr(args, "status", False):
        return cmd_sync_status(args)

    from sessionwiki.convert import convert_all, DEFAULT_OUT_DIR, DEFAULT_STATE_FILE

    # v1.2 (#54): vault-overlay mode — resolve the vault early so bad
    # paths fail before we spend time converting sessions.
    # #470: actually wire the resolved vault root through to convert_all.
    # Previously this block printed a banner and then called convert_all
    # with no vault/out_dir argument, so all 500+ sessions wrote to the
    # repo's raw/sessions/ instead of the vault. The summary line said
    # "507 converted" but the vault directory was empty.
    vault_path = getattr(args, "vault", None)
    out_dir = DEFAULT_OUT_DIR
    state_file = DEFAULT_STATE_FILE
    if vault_path:
        from sessionwiki.vault import describe_vault, resolve_vault
        try:
            vault = resolve_vault(vault_path)
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"==> {describe_vault(vault)}")
        if args.allow_overwrite:
            print("  --allow-overwrite: existing vault pages may be clobbered")
        # Route writes into the vault so a vault-mode sync actually
        # populates the vault. State file co-located with the vault so
        # two different vaults don't share idempotency state (same
        # principle as #420 for synth state).
        out_dir = vault.root / "raw" / "sessions"
        state_file = vault.root / ".llmwiki-state.json"

    dry_run = bool(getattr(args, "dry_run", False))
    _maybe_export_opencode(args)
    _maybe_export_zcode(args)

    rc = convert_all(
        adapters=args.adapter,
        out_dir=out_dir,
        state_file=state_file,
        since=args.since,
        project=args.project,
        include_current=args.include_current,
        force=args.force,
        dry_run=dry_run,
    )

    # v1.0 (#157): auto-build and auto-lint after sync.
    # --no-build and --no-lint let users opt out.
    # #470: when --vault was given, point the auto-build at the vault's
    # site/ tree too — otherwise the build silently writes to the
    # repo's site/ and the user's vault stays empty.
    if rc == 0 and not dry_run:
        schedule = _load_schedule_config()
        site_root = (vault.root / "site") if vault_path else (REPO_ROOT / "site")
        if args.auto_build and _should_run_after_sync(schedule.get("build", "on-sync")):
            print("  auto-build: regenerating site/...")
            from sessionwiki.build import build_site
            # #414: sync has explicit user opt-in to mutate wiki/, so it's
            # the right place to seed project stubs.
            build_site(out_dir=site_root, seed_project_stubs=True)
        if args.auto_lint and _should_run_after_sync(schedule.get("lint", "manual")):
            print("  auto-lint: running wiki lint...")
            from sessionwiki.lint import load_pages, run_all, summarize
            # #470: lint the vault's wiki/, not the repo's, when in
            # vault-overlay mode.
            wiki_dir = (vault.root / "wiki") if vault_path else None
            pages = load_pages(wiki_dir) if wiki_dir else load_pages()
            issues = run_all(pages)
            summary = summarize(issues)
            print(f"  lint: {sum(summary.values())} issues "
                  f"({summary.get('error', 0)} errors, "
                  f"{summary.get('warning', 0)} warnings)")
    return rc


# _load_schedule_config + _should_run_after_sync moved to
# sessionwiki/config_schedule.py and re-exported at top of file (#691).


def cmd_build(args: argparse.Namespace) -> int:
    """Build the static HTML site."""
    from sessionwiki.build import build_site

    # v1.2 (#54): vault-overlay mode. Validate the path up front so a
    # typo fails fast before the build walks raw/.
    if getattr(args, "vault", None):
        from sessionwiki.vault import describe_vault, resolve_vault
        try:
            vault = resolve_vault(args.vault)
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"==> {describe_vault(vault)}")

    return build_site(
        out_dir=args.out,
        synthesize=args.synthesize,
        claude_path=args.claude,
        search_mode=args.search_mode,
        seed_project_stubs=getattr(args, "seed_project_stubs", False),
    )


def cmd_serve(args: argparse.Namespace) -> int:
    """Serve the built site via a local HTTP server."""
    from sessionwiki.serve import serve_site
    return serve_site(directory=args.dir, port=args.port, host=args.host, open_browser=args.open)


def cmd_adapters(args: argparse.Namespace) -> int:
    """List available adapters and their config state.

    G-01 (#287): ``configured`` column now shows ``auto``/``explicit``/
    ``off`` (not ``-``/``enabled``/``disabled``) and a new
    ``will_fire`` column says whether the next ``sync`` will pick the
    adapter up.

    G-02 (#288): ``--wide`` disables the description cap.
    """
    import shutil as _shutil

    discover_adapters()
    if not REGISTRY:
        print("No adapters registered.")
        return 0

    # Load the same layered config `sync` uses, so a local override
    # that disables an adapter is reflected in this table.
    config = _load_run_config()

    # Description column width: 40 by default, full line with --wide,
    # or auto-fit to terminal (minus the four fixed columns + gutters).
    # #387 U2: column names renamed from default/configured/will_fire to
    # present/enabled/active — they read at a glance without needing the
    # legend below.
    wide = bool(getattr(args, "wide", False))
    if wide:
        desc_width: Optional[int] = None  # no cap
    else:
        term_cols = _shutil.get_terminal_size(fallback=(80, 24)).columns
        # Layout: "  name(16)  present(8)  enabled(10)  active(7)  desc"
        desc_width = max(30, term_cols - 55)

    print("Registered adapters:")
    dash = "-"
    header = (
        f"  {'name':<16}  {'present':<8}  {'enabled':<10}  "
        f"{'active':<7}  description"
    )
    print(header)
    sep_desc = "-" * (desc_width if desc_width is not None else len("description"))
    print(
        f"  {dash * 16}  {dash * 8}  {dash * 10}  {dash * 7}  {sep_desc}"
    )
    for name, adapter_cls in sorted(REGISTRY.items()):
        present = "yes" if adapter_cls.is_available() else "no"
        enabled, active = _adapter_status(name, adapter_cls, config)
        desc = adapter_cls.description()
        if desc_width is not None and len(desc) > desc_width:
            desc = desc[: max(desc_width - 3, 1)] + "..."
        print(
            f"  {name:<16}  {present:<8}  {enabled:<10}  "
            f"{active:<7}  {desc}"
        )

    print()
    print("Columns:")
    print("  present  — is the adapter's session store visible on disk?")
    print("  enabled  — auto (default), explicit (enabled:true in config), off (enabled:false)")
    print("  active   — yes/no — will `sync` pick this adapter up on its next run?")
    if not wide:
        print()
        print("Pass --wide to see untruncated descriptions.")
    return 0


def cmd_zcode_export(args: argparse.Namespace) -> int:
    """Export ZCode's SQLite store to JSONL for the zcode adapter."""
    if getattr(args, "zcode_command", None) != "export":
        print("usage: sessionwiki zcode export [options]", file=sys.stderr)
        return 2

    from sessionwiki.zcode import export as zcode_export

    argv: list[str] = [
        "--db",
        str(args.db),
        "--out-dir",
        str(args.out_dir),
    ]
    if getattr(args, "state_file", None):
        argv.extend(["--state-file", str(args.state_file)])
    if getattr(args, "since", None):
        argv.extend(["--since", str(args.since)])
    if getattr(args, "project", None):
        argv.extend(["--project", str(args.project)])
    for root in getattr(args, "project_roots", None) or []:
        argv.extend(["--project-root", str(root)])
    if getattr(args, "include_subagents", False):
        argv.append("--include-subagents")
    if getattr(args, "keep_stale", False):
        argv.append("--keep-stale")
    if getattr(args, "strict", False):
        argv.append("--strict")
    if getattr(args, "dry_run", False):
        argv.append("--dry-run")
    return zcode_export.main(argv)


def cmd_zcode_autosync(args: argparse.Namespace) -> int:
    """Run one portable autosync cycle (export → convert → optional build)."""
    if getattr(args, "zcode_command", None) != "autosync":
        print("usage: sessionwiki zcode autosync [options]", file=sys.stderr)
        return 2

    from sessionwiki.zcode.autosync import run_autosync

    return run_autosync(
        db_path=args.db,
        out_dir=args.out_dir,
        project=args.project,
        build=bool(getattr(args, "build", False)),
        coalesce=bool(getattr(args, "coalesce", False)),
        lock_timeout=float(getattr(args, "lock_timeout", 600)),
        log_path=getattr(args, "log", None),
        quiet=bool(getattr(args, "quiet", False)),
    )


def cmd_zcode_install(args: argparse.Namespace) -> int:
    """Install the ZCode Stop-hook and a native scheduler entry."""
    if getattr(args, "zcode_command", None) != "install":
        print("usage: sessionwiki zcode install [options]", file=sys.stderr)
        return 2

    from sessionwiki.zcode.install import install_all

    try:
        messages = install_all(
            scheduler=args.scheduler,
            python_exe=getattr(args, "python_exe", None),
            repo_root=getattr(args, "repo_root", None) or REPO_ROOT,
            at=args.at,
            build=not bool(getattr(args, "no_build", False)),
            coalesce=bool(getattr(args, "coalesce", False)),
            hook=not bool(getattr(args, "no_hook", False)),
            dry_run=bool(getattr(args, "dry_run", False)),
            force=bool(getattr(args, "force", False)),
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for message in messages:
        print(message)
    return 0


def cmd_opencode_export(args: argparse.Namespace) -> int:
    """Export OpenCode V2's SQLite store to JSONL for the opencode adapter."""
    if getattr(args, "opencode_command", None) != "export":
        print("usage: sessionwiki opencode export [options]", file=sys.stderr)
        return 2

    import sqlite3

    from sessionwiki.opencode.export import SchemaError, parse_since, run_export

    try:
        since_ms = parse_since(getattr(args, "since", None))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        stats = run_export(
            db_path=args.db,
            out_dir=args.out_dir,
            state_file=getattr(args, "state_file", None),
            since=since_ms,
            project=getattr(args, "project", None),
            include_subagents=bool(getattr(args, "include_subagents", False)),
            dry_run=bool(getattr(args, "dry_run", False)),
            project_roots=getattr(args, "project_roots", None),
            prune_stale=not bool(getattr(args, "keep_stale", False)),
        )
    except (SchemaError, sqlite3.Error, OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print("OpenCode export")
    print(f"  db: {args.db}")
    print(f"  out: {args.out_dir}")
    print(
        f"  sessions: {stats['total_sessions']} total, "
        f"{stats['selected']} selected"
    )
    print(
        "  skipped: "
        f"{stats['skipped_subagents']} subagent, "
        f"{stats['skipped_project']} project, "
        f"{stats['skipped_since']} since"
    )
    print(
        f"  exported: {stats['exported']}, unchanged: {stats['unchanged']}, "
        f"empty: {stats['empty']}, errors: {stats['errors']}"
    )
    if args.dry_run:
        print("  dry-run: no files written")
    else:
        print(f"  written: {stats['written']} files")
    if stats.get("stale"):
        print(
            f"  stale: {stats['stale']} removed "
            f"({stats['stale_deleted']} files deleted)"
        )
    if stats.get("errors") and getattr(args, "strict", False):
        return 1
    return 0


def cmd_opencode_autosync(args: argparse.Namespace) -> int:
    """Run one OpenCode autosync cycle (export → convert → optional build)."""
    if getattr(args, "opencode_command", None) != "autosync":
        print("usage: sessionwiki opencode autosync [options]", file=sys.stderr)
        return 2

    from sessionwiki.opencode.autosync import run_autosync

    return run_autosync(
        db_path=args.db,
        out_dir=args.out_dir,
        project=args.project,
        build=bool(getattr(args, "build", False)),
        lock_timeout=float(getattr(args, "lock_timeout", 600)),
        log_path=getattr(args, "log", None),
        quiet=bool(getattr(args, "quiet", False)),
    )


def cmd_opencode_install(args: argparse.Namespace) -> int:
    """Install the OpenCode autosync plugin."""
    if getattr(args, "opencode_command", None) != "install":
        print("usage: sessionwiki opencode install [options]", file=sys.stderr)
        return 2

    from sessionwiki.opencode.install import install_all

    try:
        build = bool(getattr(args, "build", False)) and not bool(
            getattr(args, "no_build", False)
        )
        messages = install_all(
            python_exe=getattr(args, "python_exe", None),
            repo_root=getattr(args, "repo_root", None) or REPO_ROOT,
            build=build,
            dry_run=bool(getattr(args, "dry_run", False)),
            force=bool(getattr(args, "force", False)),
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for message in messages:
        print(message)
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    """Search the wiki with the MCP ranking, or graphify with --graph."""
    question = " ".join(args.question)
    if args.graph:
        from sessionwiki.graphify_bridge import is_available, query_graph
        if not is_available():
            print("error: graphify not installed. Run: pip install sessionwiki[graph]", file=sys.stderr)
            return 2
        print(query_graph(question, depth=args.depth, token_budget=args.budget))
        return 0
    from sessionwiki.mcp.server import rank_query, tool_wiki_query
    filters = {
        "project": args.project,
        "type": args.page_type,
        "tag": args.tag,
        "date_from": args.date_from,
        "date_to": args.date_to,
    }
    if args.json:
        result = rank_query(question, max_pages=args.limit, include_raw=args.include_raw,
                            filters=filters)
        result.pop("index", None)
        result.pop("overview", None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    out = tool_wiki_query({"question": question, "max_pages": args.limit,
                           "include_raw": args.include_raw, **filters})
    print(out["content"][0]["text"])
    return 1 if out.get("isError") else 0


def cmd_graph(args: argparse.Namespace) -> int:
    """Build the knowledge graph from wiki/ wikilinks.

    #488: graphify-engine failures (uninstalled, crashes, empty
    result) ALL fall back to the builtin engine so the user always
    gets *some* graph. Only the builtin engine's exit code is
    authoritative for the CLI return value.
    """
    engine = getattr(args, "engine", "graphify")
    if engine == "graphify":
        from sessionwiki.graphify_bridge import is_available, build_graphify_graph
        if not is_available():
            print("  graphify not installed — falling back to builtin engine", file=sys.stderr)
            print("  install with: pip install sessionwiki[graph]", file=sys.stderr)
            engine = "builtin"
        else:
            try:
                result = build_graphify_graph()
            except Exception as e:
                # #488: uncaught graphify exception used to surface as a
                # bare stack trace + non-zero exit. Now we log a warning
                # and fall through to the builtin engine.
                print(f"  graphify engine crashed ({type(e).__name__}: {e}) — "
                      f"falling back to builtin", file=sys.stderr)
                engine = "builtin"
            else:
                if result.get("graph") is not None:
                    return 0
                # #488: empty-result early-return used to fail with rc=1
                # without trying builtin. graphify can legitimately
                # return None for tiny corpora (no edges); the builtin
                # engine handles the same input gracefully.
                print("  graphify returned no graph — falling back to builtin",
                      file=sys.stderr)
                engine = "builtin"

    from sessionwiki.graph import build_and_report
    write_json = args.format in ("json", "both")
    write_html = args.format in ("html", "both")
    return build_and_report(write_json_flag=write_json, write_html_flag=write_html)


# cmd_sync_status + _resolve_key_exists moved to sessionwiki/sync/status.py
# and re-exported at top of file (#691).


def cmd_export(args: argparse.Namespace) -> int:
    """Export AI-consumable formats from the compiled wiki."""
    import sys as _sys
    from sessionwiki.exporters import (
        write_llms_txt,
        write_llms_full_txt,
        write_graph_jsonld,
        write_sitemap,
        write_rss,
        write_robots_txt,
        write_ai_readme,
        write_marp,
        export_all,
    )
    from sessionwiki.build import discover_sources, group_by_project, RAW_SESSIONS

    out_dir = args.out if args.out else REPO_ROOT / "site"
    out_dir.mkdir(parents=True, exist_ok=True)

    sources = discover_sources(RAW_SESSIONS)
    if not sources:
        print("error: no sources found. Run 'sessionwiki sync' first.", file=_sys.stderr)
        return 2
    groups = group_by_project(sources)

    format_ = args.format
    if format_ == "all":
        paths = export_all(out_dir, groups, sources)
        for name, p in sorted(paths.items()):
            print(f"  wrote {p.relative_to(REPO_ROOT) if p.is_relative_to(REPO_ROOT) else p}")
        return 0

    topic = getattr(args, "topic", "") or ""
    mapping = {
        "llms-txt": lambda: write_llms_txt(out_dir, groups, len(sources)),
        "llms-full-txt": lambda: write_llms_full_txt(out_dir, sources),
        "jsonld": lambda: write_graph_jsonld(out_dir, groups, sources),
        "sitemap": lambda: write_sitemap(out_dir, groups, sources),
        "rss": lambda: write_rss(out_dir, sources),
        "robots": lambda: write_robots_txt(out_dir),
        "ai-readme": lambda: write_ai_readme(out_dir, groups, len(sources)),
        "marp": lambda: write_marp(out_dir, sources, topic=topic),
    }
    fn = mapping.get(format_)
    if not fn:
        print(f"error: unknown format {format_!r}. Valid: {sorted(mapping.keys())} or 'all'", file=_sys.stderr)
        return 2
    p = fn()
    print(f"  wrote {p.relative_to(REPO_ROOT) if p.is_relative_to(REPO_ROOT) else p}")
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    """Run every registered lint rule against the wiki and print a report."""
    from sessionwiki.lint import REGISTRY, load_pages, run_all, summarize  # noqa: F401

    wiki_dir = args.wiki_dir or (REPO_ROOT / "wiki")
    if not wiki_dir.is_dir():
        print(f"error: wiki directory not found: {wiki_dir}", file=sys.stderr)
        return 2

    pages = load_pages(wiki_dir)
    if not pages:
        print(f"  no pages found in {wiki_dir}")
        return 0

    selected = args.rules.split(",") if args.rules else None
    issues = run_all(
        pages,
        include_llm=args.include_llm,
        selected=selected,
    )

    summary = summarize(issues)

    if args.json:
        import json as _json
        print(_json.dumps({
            "summary": summary,
            "issues": issues,
            "total_pages": len(pages),
        }, indent=2))
    else:
        print(f"  scanned {len(pages)} pages")
        print(f"  {sum(summary.values())} issues: "
              f"{summary.get('error', 0)} errors, "
              f"{summary.get('warning', 0)} warnings, "
              f"{summary.get('info', 0)} info")
        print()
        if issues:
            by_rule: dict[str, list[dict[str, str]]] = {}
            for i in issues:
                by_rule.setdefault(i["rule"], []).append(i)
            for rule, rule_issues in sorted(by_rule.items()):
                print(f"## {rule} ({len(rule_issues)})")
                for i in rule_issues[:20]:
                    print(f"  [{i['severity']}] {i['page']}: {i['message']}")
                if len(rule_issues) > 20:
                    print(f"  ... and {len(rule_issues) - 20} more")
                print()

    if args.fail_on_errors and summary.get("error", 0) > 0:
        return 1
    return 0


def _load_run_config() -> dict:
    """Load the shared example plus gitignored per-checkout overrides.

    Order: ``examples/sessions_config.json`` → ``config.json`` →
    ``config.local.json``. Machine settings (backend URLs, API keys,
    redaction patterns) belong in an override, not in the shared example.
    """
    from sessionwiki.config import resolve_config

    return resolve_config(REPO_ROOT)


def _config_int(value: Any, default: int, *, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


def _config_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off"}
    if value is None:
        return default
    return bool(value)


def cmd_synthesize(args: argparse.Namespace) -> int:
    """Synthesize wiki source pages from raw sessions (v1.1.0 · #35).

    Uses the backend selected via ``synthesis.backend`` in the config
    (dummy | ollama | openai | agent). ``--check`` prints backend
    availability without running synthesis — useful for diagnosing a
    server before a long sync. ``--estimate`` prints a cached-vs-fresh
    token + dollar breakdown before spending money (#50).

    Config resolution: ``examples/sessions_config.json``, then the
    gitignored ``config.json`` and ``config.local.json`` overrides.
    """
    from sessionwiki.synth.pipeline import resolve_backend, synthesize_new_sessions

    config: dict = _load_run_config()

    if args.estimate:
        return _synthesize_estimate(config)

    # #316: agent-delegate operations that don't need a backend.
    if args.list_pending:
        return _synthesize_list_pending()
    if args.complete:
        return _synthesize_complete(args)

    if getattr(args, "backfill_only", False):
        return _synthesize_backfill(args)

    coalesce_only = bool(getattr(args, "coalesce_only", False))
    if coalesce_only:
        backend = None
        print("Backend: none (coalesce-only)")
    else:
        backend = resolve_backend(config)
        print(f"Backend: {backend.name}")
    synth_cfg = config.get("synthesis", {}) or {}
    max_workers = _config_int(synth_cfg.get("max_concurrency"), 1)
    coalesce_low_signal = _config_bool(synth_cfg.get("coalesce_low_signal"), False)
    if coalesce_only:
        coalesce_low_signal = True
    coalesce_min_group = _config_int(synth_cfg.get("coalesce_min_group"), 3)
    coalesce_window = str(synth_cfg.get("coalesce_window", "all") or "all")
    strip_links = _config_bool(synth_cfg.get("strip_unresolved_wikilinks"), True)
    raw_lock_patterns = synth_cfg.get("lock_skip_patterns")
    lock_skip_patterns = (
        [str(pattern) for pattern in raw_lock_patterns]
        if isinstance(raw_lock_patterns, list)
        else None
    )
    if max_workers > 1:
        print(f"Concurrency: {max_workers}")
    if coalesce_low_signal:
        print(
            f"Coalesce low-signal sessions: on "
            f"(min group {coalesce_min_group}, window {coalesce_window})"
        )

    if args.check:
        available = backend.is_available()
        print(f"Available: {available}")
        return 0 if available else 1

    # #420: vault-overlay mode isolates raw/wiki/state to the vault root.
    vault_path = getattr(args, "vault", None)
    raw_dir = wiki_sources_dir = state_file = None
    if vault_path:
        from sessionwiki.vault import resolve_vault
        try:
            vault = resolve_vault(vault_path)
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        # Post-final-review: Vault is a frozen dataclass with no
        # __truediv__ — `vault / "raw"` raises TypeError. cmd_sync at
        # line 205 correctly uses `vault.root / "raw"`; this site was
        # the missed copy. Caught by the multi-agent code review.
        raw_dir = vault.root / "raw" / "sessions"
        wiki_sources_dir = vault.root / "wiki" / "sources"
        state_file = vault.root / ".llmwiki-synth-state.json"

    summary = synthesize_new_sessions(
        backend=backend,
        force=args.force,
        raw_dir=raw_dir,
        wiki_sources_dir=wiki_sources_dir,
        state_file=state_file,
        max_workers=max_workers,
        coalesce_low_signal=coalesce_low_signal,
        coalesce_min_group=coalesce_min_group,
        coalesce_window=coalesce_window,
        lock_skip_patterns=lock_skip_patterns,
        coalesce_only=coalesce_only,
        strip_unresolved_wikilinks=strip_links,
        language=str(synth_cfg.get("language") or "session"),
        max_sessions=getattr(args, "max_sessions", None),
    )
    print(
        f"Scanned {summary['total_scanned']}, new {summary['new_files']}, "
        f"synthesized {summary['synthesized']}, skipped {summary['skipped']}"
        + (f", backfilled {summary['backfilled']}" if summary.get("backfilled") else "")
    )
    if summary["errors"]:
        for err in summary["errors"]:
            print(f"  ! {err}", file=sys.stderr)
        return 1
    return 0


def _synthesize_backfill(args: argparse.Namespace) -> int:
    """``synthesize --backfill-only``: copy each session's description
    onto its existing source page. Deterministic, no backend."""
    from sessionwiki.synth.pipeline import backfill_source_descriptions

    raw_dir = wiki_sources_dir = None
    vault_path = getattr(args, "vault", None)
    if vault_path:
        from sessionwiki.vault import resolve_vault
        try:
            vault = resolve_vault(vault_path)
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        raw_dir = vault.root / "raw" / "sessions"
        wiki_sources_dir = vault.root / "wiki" / "sources"
    count = backfill_source_descriptions(raw_dir=raw_dir, wiki_sources_dir=wiki_sources_dir)
    print(f"Backfilled description on {count} source page(s)")
    return 0


# ─── #316 agent-delegate CLI helpers ─────────────────────────────────
# _synthesize_list_pending + _synthesize_complete moved to
# sessionwiki/synth/cli_helpers.py and re-exported at top of file (#691).


def _synthesize_estimate(config: dict | None = None) -> int:
    """Print the G-07 incremental-vs-full-force cost report (v1.1.0 · #50 · #293).

    Transparency over one-liner: reads the state file so the user sees
    exactly which bucket gets billed next. The old ``--estimate`` printed
    a single number without saying whether it covered the whole corpus
    or just the delta.
    """
    from sessionwiki.cache import MODEL_PRICING

    synth = (config or {}).get("synthesis", {}) or {}
    backend = str(synth.get("backend") or "dummy")
    model = str(synth.get("model") or "")
    priced = model in MODEL_PRICING

    from sessionwiki.synth.chunking import ChunkingConfig

    chunking = ChunkingConfig.from_synthesis_config(synth)
    max_body_chars = int(
        synth.get("max_body_chars") or (8_000 if backend == "ollama" else 40_000)
    )

    if backend not in {"anthropic", "claude"} or (model and not priced):
        print(
            f"note: cost estimate uses Claude API pricing; "
            f"backend {backend!r} may bill differently "
            f"(local models are usually free)."
        )

    report = synthesize_estimate_report(
        model=model if priced else None,
        chunking=chunking,
        max_body_chars=max_body_chars,
    )

    for w in report["warnings"]:
        print(f"warning: {w}")

    print(f"Corpus:                {report['corpus']:>6} sessions in raw/sessions/")
    print(f"Already synthesized:   {report['synthesized']:>6} pages in wiki/sources/")
    print(f"New since last run:    {report['new']:>6}")
    if report.get("chunked"):
        print(
            f"Chunked (map-reduce):  {report['chunked']:>6} corpus, "
            f"{report.get('chunked_new', 0)} new "
            f"(bodies over {max_body_chars:,} chars)"
        )
    print()
    print(f"Prefix: {report['prefix_tokens']:,} tok  Model: {report['model']}")
    print()
    if report["new"] == 0:
        print(f"Incremental sync:  $0.0000  (nothing new — this is a no-op)")
    else:
        print(
            f"Incremental sync:  ${report['incremental_usd']:.4f}  "
            f"(synthesize the {report['new']} new session(s))"
        )
    print(
        f"Full re-synth:     ${report['full_force_usd']:.4f}  "
        f"(--force — {report['corpus']} session(s), 1 cache write + {max(report['corpus'] - 1, 0)} hits)"
    )
    return 0


def cmd_candidates(args: argparse.Namespace) -> int:
    """List / promote / merge / discard candidate pages (v1.1.0 · #51)."""
    import json as _json
    from sessionwiki.candidates import (
        list_candidates,
        promote,
        merge as merge_candidate,
        discard,
        stale_candidates,
    )

    wiki_dir = args.wiki_dir or (REPO_ROOT / "wiki")
    if not wiki_dir.is_dir():
        print(f"error: wiki directory not found: {wiki_dir}", file=sys.stderr)
        return 2

    action = args.action

    if action == "list":
        items = (
            stale_candidates(wiki_dir, threshold_days=args.stale_days)
            if args.stale else list_candidates(wiki_dir)
        )
        if args.json:
            # Path isn't JSON-serializable — drop it for the output
            cleaned = [{k: v for k, v in c.items() if k != "abs_path"} for c in items]
            print(_json.dumps(cleaned, indent=2))
        else:
            label = "stale" if args.stale else "pending"
            print(f"  {len(items)} {label} candidate(s):")
            for c in items:
                age = f"{c['age_days']}d" if c["created"] else "unknown age"
                print(f"    [{c['kind']:9}] {c['slug']}  ({age})  — {c['title']}")
        return 0

    if action == "promote":
        if not args.slug:
            print("error: --slug is required for promote", file=sys.stderr)
            return 2
        path = promote(args.slug, wiki_dir, kind=args.kind)
        print(f"  promoted → {path.relative_to(wiki_dir)}")
        return 0

    if action == "merge":
        if not args.slug or not args.into:
            print("error: both --slug and --into are required for merge", file=sys.stderr)
            return 2
        path = merge_candidate(args.slug, wiki_dir, into_slug=args.into, kind=args.kind)
        print(f"  merged into → {path.relative_to(wiki_dir)}")
        return 0

    if action == "discard":
        if not args.slug:
            print("error: --slug is required for discard", file=sys.stderr)
            return 2
        path = discard(args.slug, wiki_dir, reason=args.reason, kind=args.kind)
        print(f"  discarded → {path.relative_to(wiki_dir)}")
        return 0

    print(f"error: unknown action {action!r}", file=sys.stderr)
    return 2


def _remember_name(title: str) -> str:
    """TitleCase the words of ``title``; keep letters and digits only."""
    words = re.findall(r"[^\W_]+", title)
    # ``title`` (not ``capitalize``) so "1password" becomes "1Password".
    return "".join(word.title() for word in words)[:60]


def _project_entity(project: str) -> str:
    """``ai-newsletter`` → ``AiNewsletter``.

    Same rule as ``DummySynthesizer._title_case_project``, so the link
    points at the page synthesis creates for the project.
    """
    return "".join(part.capitalize() for part in re.split(r"[-_\s]+", project) if part)


def _unique_candidate_path(directory: Path, name: str) -> Path:
    """Return ``<name>.md`` or ``<name>-2.md``/``<name>-3.md`` if taken."""
    path = directory / f"{name}.md"
    counter = 2
    while path.exists():
        suffix = f"-{counter}"
        path = directory / f"{name[: 60 - len(suffix)]}{suffix}.md"
        counter += 1
    return path


def cmd_remember(args: argparse.Namespace) -> int:
    """Store a remembered fact as a candidate page for human review (card 27)."""
    from datetime import datetime, timezone

    from sessionwiki.candidates import candidates_dir

    fact = args.fact.strip()
    if not fact:
        print("error: the fact is empty", file=sys.stderr)
        return 2

    project = " ".join((args.project or Path.cwd().name or "unknown").split())
    title = (args.title or " ".join(fact.split()[:8])).strip()

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    name = _remember_name(title)
    if not name:
        name = f"Remembered-{now.strftime('%Y%m%d-%H%M%S')}"

    target_dir = candidates_dir(REPO_ROOT / "wiki") / "concepts"
    target_dir.mkdir(parents=True, exist_ok=True)
    path = _unique_candidate_path(target_dir, name)

    # A raw project name may not break the inline YAML list or the scalar.
    tag = re.sub(r"[,\[\]]", "-", project)
    entity = _project_entity(project)
    fm_title = title.replace('"', "'")
    content = (
        "---\n"
        f'title: "{fm_title}"\n'
        "type: concept\n"
        "status: candidate\n"
        "origin: human\n"
        f"project: {project}\n"
        f"tags: [remembered, {tag}]\n"
        f"created: {today}\n"
        f"last_updated: {today}\n"
        "sources: []\n"
        "---\n\n"
        f"# {title}\n\n"
        f"{fact}\n\n"
        "## Connections\n\n"
        f"- [[{entity}]] — project\n"
    )
    path.write_text(content, encoding="utf-8")
    print(f"  remembered → {path.relative_to(REPO_ROOT)}")
    print("  review with: sessionwiki candidates list")
    return 0


def _add_vault_arg(parser: argparse.ArgumentParser, *, role: str) -> None:
    """#arch-m8 (#620): single source of truth for the ``--vault`` flag.

    All three subcommands that accept ``--vault`` (sync, build, synthesize)
    used to declare it independently with subtly different help text and
    behaviour. The semantics differ legitimately by subcommand (sync
    WRITES into the vault; build READS from it; synthesize isolates the
    state file under it), so we keep the role-specific help string per
    site, but the flag spelling, type, default, and metavar are unified
    here so a future refactor changes them in one place.
    """
    parser.add_argument(
        "--vault", type=Path, default=None, metavar="PATH",
        help={
            "sync": "Vault-overlay mode (#54): write new pages inside an "
                    "existing Obsidian / Logseq vault instead of the "
                    "repo's wiki/ directory.",
            "build": "Vault-overlay mode (#54): build from an existing "
                     "Obsidian / Logseq vault. Still writes site output to "
                     "--out.",
            "synthesize": "(#420) Vault-overlay mode: read raw/ + write "
                          "wiki/sources/ under the vault root, and isolate "
                          "the synth state file to the vault. Without this "
                          "flag the state file lives at the repo root, so "
                          "two vaults synthesised against the same repo "
                          "silently share idempotency state.",
            "all": "(#383) With --with-synth: run synthesize against the "
                   "vault's raw/ + wiki/sources/ (same semantics as "
                   "`sessionwiki synthesize --vault`).",
        }[role],
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sessionwiki",
        description="Searchable, interlinked wiki of your AI coding sessions (Claude Code, Codex CLI, Cursor, Gemini CLI, Copilot, ZCode, OpenCode).",
    )
    p.add_argument("--version", action="version", version=f"sessionwiki {__version__}")

    sub = p.add_subparsers(dest="cmd", metavar="COMMAND")

    # init
    init = sub.add_parser("init", help="Scaffold raw/, wiki/, site/ directories")
    init.set_defaults(func=cmd_init)

    # sync
    sync = sub.add_parser("sync", help="Convert new .jsonl sessions to markdown")
    sync.add_argument("--adapter", nargs="*", default=None, help="Adapter(s) to run; default: all available")
    sync.add_argument("--since", type=str, help="Only sessions on or after YYYY-MM-DD")
    sync.add_argument("--project", type=str, help="Substring filter on project slug")
    sync.add_argument("--include-current", action="store_true", help="Don't skip live sessions (<60 min)")
    sync.add_argument("--force", action="store_true", help="Ignore state file, reconvert everything")
    sync.add_argument(
        "--dry-run", action="store_true",
        help="Preview conversions without writing raw/ or refreshing the ZCode/OpenCode exports",
    )
    sync.add_argument(
        "--zcode-export", action=argparse.BooleanOptionalAction, default=True,
        help="Refresh the ZCode JSONL corpus before converting "
             "(default: on when the ZCode database exists; pass "
             "--no-zcode-export to skip)",
    )
    sync.add_argument(
        "--zcode-db", type=Path, default=None,
        help="Path to ZCode db.sqlite (default: ~/.zcode/cli/db/db.sqlite)",
    )
    sync.add_argument(
        "--opencode-export", action=argparse.BooleanOptionalAction, default=True,
        help="Refresh the OpenCode JSONL corpus before converting "
             "(default: on when the OpenCode database exists; pass "
             "--no-opencode-export to skip)",
    )
    sync.add_argument(
        "--opencode-db", type=Path, default=None,
        help="Path to OpenCode opencode.db "
             "(default: ~/.local/share/opencode/opencode.db)",
    )
    sync.add_argument(
        "--auto-build", action=argparse.BooleanOptionalAction, default=True,
        help="After sync, rebuild the site when sessions_config.json's "
             "schedule.build is 'on-sync' (default: on; pass --no-auto-build to skip)",
    )
    sync.add_argument(
        "--auto-lint", action=argparse.BooleanOptionalAction, default=True,
        help="After sync, run lint when sessions_config.json's "
             "schedule.lint is 'on-sync' (default: on; pass --no-auto-lint to skip)",
    )
    _add_vault_arg(sync, role="sync")
    sync.add_argument(
        "--allow-overwrite", action="store_true",
        help="With --vault: allow clobbering existing vault pages "
             "(default: refuse, append under ## Connections instead)",
    )
    sync.add_argument(
        "--status", action="store_true",
        help="Show last-sync time + per-adapter counters + quarantine "
             "(G-03 · #289). Does not run a sync.",
    )
    sync.add_argument(
        "--recent", type=int, default=0,
        help="With --status: also show last N recent log entries.",
    )
    sync.set_defaults(func=cmd_sync)

    # build
    build = sub.add_parser("build", help="Compile static HTML site from raw/ + wiki/")
    build.add_argument("--out", type=Path, default=REPO_ROOT / "site", help="Output dir (default: site/)")
    build.add_argument("--synthesize", action="store_true", help="Call claude CLI for overview synthesis")
    build.add_argument(
        "--claude", type=str, default="",
        help="Path to claude CLI (#421: defaults to `shutil.which('claude')` "
             "so PATH-based / brew / nvm / Windows installs all work)",
    )
    build.add_argument(
        "--search-mode", choices=["auto", "tree", "flat"], default="auto",
        help="Search index mode (#53): auto picks tree vs flat from heading depth",
    )
    _add_vault_arg(build, role="build")
    build.add_argument(
        "--seed-project-stubs", action="store_true", dest="seed_project_stubs",
        help="(#414) Auto-create wiki/projects/<slug>.md stubs for any "
             "newly-discovered project that doesn't have a metadata file. "
             "Off by default — `build` is read-only on wiki/. Use `sync` "
             "(which already mutates wiki/) for routine seeding, or pass "
             "this flag to opt in from CI/scripts.",
    )
    build.set_defaults(func=cmd_build)

    # serve
    serve = sub.add_parser("serve", help="Start local HTTP server")
    serve.add_argument("--dir", type=Path, default=REPO_ROOT / "site", help="Directory to serve (default: site/)")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--host", type=str, default="127.0.0.1")
    serve.add_argument("--open", action="store_true", help="Open browser after starting")
    serve.set_defaults(func=cmd_serve)

    # adapters
    ads = sub.add_parser("adapters", help="List available adapters")
    ads.add_argument(
        "--wide",
        action="store_true",
        help="Show untruncated adapter descriptions (G-02 · #288).",
    )
    ads.set_defaults(func=cmd_adapters)

    # doctor — install diagnostics for a fresh machine
    from sessionwiki.doctor import cmd_doctor as _cmd_doctor

    doctor = sub.add_parser(
        "doctor",
        help="Check Python, dependencies, config, and ZCode paths on this machine",
    )
    doctor.set_defaults(func=_cmd_doctor)

    # audit — pre-publish privacy check
    from sessionwiki.audit import cmd_audit as _cmd_audit

    audit = sub.add_parser(
        "audit",
        help="Scan raw/, wiki/, and site/ for usernames and secrets",
    )
    audit.add_argument(
        "--path", action="append", type=Path, default=None,
        help="file or directory to scan (repeatable; default: raw/ wiki/ site/)",
    )
    audit.add_argument(
        "--username", default=None,
        help="username to search for (default: redaction.real_username or $USER)",
    )
    audit.add_argument("--json", action="store_true", help="emit a JSON report")
    audit.add_argument(
        "--fail-on-findings", action="store_true",
        help="exit 1 when anything is found (for a publish gate)",
    )
    audit.set_defaults(func=_cmd_audit)

    # zcode (ZCode session-store integration)
    zcode = sub.add_parser("zcode", help="ZCode session-store export")
    zcode_sub = zcode.add_subparsers(dest="zcode_command", metavar="COMMAND")
    zcode_export = zcode_sub.add_parser(
        "export", help="Export ~/.zcode/cli/db/db.sqlite to JSONL"
    )
    from sessionwiki.zcode.export import DEFAULT_DB as _ZCODE_DB
    from sessionwiki.zcode.export import DEFAULT_OUT_DIR as _ZCODE_OUT

    zcode_export.add_argument(
        "--db", type=Path, default=_ZCODE_DB, help="path to ZCode db.sqlite"
    )
    zcode_export.add_argument(
        "--out-dir", type=Path, default=_ZCODE_OUT, help="JSONL output directory"
    )
    zcode_export.add_argument(
        "--state-file", type=Path, default=None, help="incremental state file"
    )
    zcode_export.add_argument(
        "--since", default=None, help="only sessions updated on/after YYYY-MM-DD"
    )
    zcode_export.add_argument(
        "--project", default=None,
        help="case-insensitive project path or slug substring",
    )
    zcode_export.add_argument(
        "--project-root",
        dest="project_roots",
        action="append",
        type=Path,
        default=None,
        help="treat this directory as a project root (repeatable)",
    )
    zcode_export.add_argument(
        "--include-subagents", action="store_true",
        help="include subagent_child sessions",
    )
    zcode_export.add_argument(
        "--keep-stale", action="store_true",
        help="do not remove JSONL for sessions deleted from the database",
    )
    zcode_export.add_argument(
        "--strict", action="store_true",
        help="exit 1 when any session fails, even if others exported",
    )
    zcode_export.add_argument(
        "--dry-run", action="store_true",
        help="show counters without writing files",
    )
    zcode_export.set_defaults(func=cmd_zcode_export)

    autosync = zcode_sub.add_parser(
        "autosync",
        help="Export, convert, and optionally build (portable scheduler entry point)",
    )
    autosync.add_argument(
        "--db", type=Path, default=_ZCODE_DB, help="path to ZCode db.sqlite"
    )
    autosync.add_argument(
        "--out-dir", type=Path, default=_ZCODE_OUT, help="JSONL output directory"
    )
    autosync.add_argument(
        "--project", default=None,
        help="case-insensitive project path or slug substring",
    )
    autosync.add_argument(
        "--build", action="store_true",
        help="rebuild site/ after converting",
    )
    autosync.add_argument(
        "--coalesce", action="store_true",
        help="run deterministic low-signal coalescing after sync",
    )
    autosync.add_argument(
        "--lock-timeout", type=float, default=600,
        help="seconds to wait for another autosync (default: 600)",
    )
    autosync.add_argument(
        "--log", type=Path, default=None,
        help="log file (default: ~/.llmwiki/zcode/autosync.log)",
    )
    autosync.add_argument(
        "--quiet", action="store_true",
        help="write only to the log file",
    )
    autosync.set_defaults(func=cmd_zcode_autosync)

    install = zcode_sub.add_parser(
        "install",
        help="Install the Stop-hook and a native autosync scheduler",
    )
    install.add_argument(
        "--scheduler",
        choices=["auto", "systemd", "launchd", "windows", "none"],
        default="auto",
        help="Native scheduler (default: auto-detect)",
    )
    install.add_argument("--at", default="03:30", help="daily start time HH:MM")
    install.add_argument(
        "--python",
        dest="python_exe",
        default=None,
        help="Python interpreter for the scheduled command (default: current)",
    )
    install.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="sessionwiki checkout used as WorkingDirectory (default: this repo)",
    )
    install.add_argument("--no-build", action="store_true", help="do not rebuild site/")
    install.add_argument(
        "--coalesce", action="store_true",
        help="also run deterministic low-signal coalescing",
    )
    install.add_argument("--no-hook", action="store_true", help="skip the ZCode Stop hook")
    install.add_argument("--dry-run", action="store_true", help="print changes only")
    install.add_argument(
        "--force", action="store_true", help="replace an existing autosync hook"
    )
    install.set_defaults(func=cmd_zcode_install)

    # opencode (OpenCode session-store integration)
    opencode = sub.add_parser(
        "opencode", help="OpenCode session-store export"
    )
    opencode_sub = opencode.add_subparsers(
        dest="opencode_command", metavar="COMMAND"
    )
    opencode_export = opencode_sub.add_parser(
        "export", help="Export ~/.local/share/opencode/opencode.db to JSONL"
    )
    from sessionwiki.opencode.export import DEFAULT_DB as _OPENCODE_DB
    from sessionwiki.opencode.export import DEFAULT_OUT_DIR as _OPENCODE_OUT

    opencode_export.add_argument(
        "--db", type=Path, default=_OPENCODE_DB,
        help="path to OpenCode opencode.db",
    )
    opencode_export.add_argument(
        "--out-dir", type=Path, default=_OPENCODE_OUT,
        help="JSONL output directory",
    )
    opencode_export.add_argument(
        "--state-file", type=Path, default=None,
        help="incremental state file",
    )
    opencode_export.add_argument(
        "--since", default=None,
        help="only sessions updated on/after YYYY-MM-DD",
    )
    opencode_export.add_argument(
        "--project", default=None,
        help="case-insensitive project path or slug substring",
    )
    opencode_export.add_argument(
        "--project-root",
        dest="project_roots",
        action="append",
        type=Path,
        default=None,
        help="treat this directory as a project root (repeatable)",
    )
    opencode_export.add_argument(
        "--include-subagents", action="store_true",
        help="include child/subagent sessions",
    )
    opencode_export.add_argument(
        "--keep-stale", action="store_true",
        help="do not remove JSONL for sessions deleted from the database",
    )
    opencode_export.add_argument(
        "--strict", action="store_true",
        help="exit 1 when any session fails, even if others exported",
    )
    opencode_export.add_argument(
        "--dry-run", action="store_true",
        help="show counters without writing files",
    )
    opencode_export.set_defaults(func=cmd_opencode_export)

    opencode_autosync = opencode_sub.add_parser(
        "autosync",
        help="Export, convert, and optionally build (portable scheduler entry point)",
    )
    opencode_autosync.add_argument(
        "--db", type=Path, default=_OPENCODE_DB,
        help="path to OpenCode opencode.db",
    )
    opencode_autosync.add_argument(
        "--out-dir", type=Path, default=_OPENCODE_OUT,
        help="JSONL output directory",
    )
    opencode_autosync.add_argument(
        "--project", default=None,
        help="case-insensitive project path or slug substring",
    )
    opencode_autosync.add_argument(
        "--build", action="store_true",
        help="rebuild site/ after converting",
    )
    opencode_autosync.add_argument(
        "--lock-timeout", type=float, default=600,
        help="seconds to wait for another autosync (default: 600)",
    )
    opencode_autosync.add_argument(
        "--log", type=Path, default=None,
        help="log file (default: ~/.llmwiki/opencode/autosync.log)",
    )
    opencode_autosync.add_argument(
        "--quiet", action="store_true",
        help="write only to the log file",
    )
    opencode_autosync.set_defaults(func=cmd_opencode_autosync)

    opencode_install = opencode_sub.add_parser(
        "install",
        help="Install the OpenCode autosync plugin",
    )
    opencode_install.add_argument(
        "--python",
        dest="python_exe",
        default=None,
        help="Python interpreter for the plugin command (default: current)",
    )
    opencode_install.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="sessionwiki checkout used as the plugin working directory (default: this repo)",
    )
    opencode_install.add_argument(
        "--build", action="store_true",
        help="rebuild site/ after each autosync (default: off)",
    )
    opencode_install.add_argument(
        "--no-build", action="store_true", help="do not rebuild site/"
    )
    opencode_install.add_argument(
        "--dry-run", action="store_true", help="print changes only"
    )
    opencode_install.add_argument(
        "--force", action="store_true", help="replace an existing plugin"
    )
    opencode_install.set_defaults(func=cmd_opencode_install)

    # graph
    graph = sub.add_parser("graph", help="Build the knowledge graph (graph/graph.json + graph.html)")
    graph.add_argument("--format", choices=["json", "html", "both"], default="both")
    graph.add_argument(
        "--engine", choices=["builtin", "graphify"], default="graphify",
        help="Graph engine: 'graphify' (AI-powered, default) or 'builtin' (stdlib wikilinks fallback)",
    )
    graph.set_defaults(func=cmd_graph)

    # export (v0.4)
    exp2 = sub.add_parser(
        "export",
        help="Export AI-consumable formats: llms-txt, llms-full-txt, jsonld, sitemap, rss, robots, ai-readme, marp (or 'all')",
    )
    exp2.add_argument(
        "format",
        choices=["llms-txt", "llms-full-txt", "jsonld", "sitemap", "rss", "robots", "ai-readme", "marp", "all"],
        help="Export format",
    )
    exp2.add_argument("--out", type=Path, default=None, help="Output directory (default: site/)")
    exp2.add_argument("--topic", type=str, default="", help="Topic filter for marp slide generation")
    exp2.set_defaults(func=cmd_export)

    # lint (v1.0, #155) — live count via the rule registry (currently 15)
    from sessionwiki.lint import REGISTRY as _LINT_REG
    from sessionwiki.lint import rules as _lint_rules  # noqa: F401 — force registration
    lint = sub.add_parser(
        "lint",
        help=f"Run all {len(_LINT_REG)} lint rules against the wiki",
    )
    lint.add_argument("--wiki-dir", type=Path, default=None,
                      help="Wiki directory (default: ./wiki)")
    lint.add_argument("--rules", type=str, default=None,
                      help="Comma-separated rule names (default: all applicable)")
    lint.add_argument("--include-llm", action="store_true",
                      help="Also run LLM-powered rules (requires --llm-callback)")
    lint.add_argument("--json", action="store_true", help="JSON output")
    lint.add_argument("--fail-on-errors", action="store_true",
                      help="Exit non-zero if any error-severity issues found")
    lint.set_defaults(func=cmd_lint)

    # candidates (v1.1, #51) — approval workflow
    cand = sub.add_parser(
        "candidates",
        help="List / promote / merge / discard candidate wiki pages (approval workflow)",
    )
    cand.add_argument(
        "action", choices=["list", "promote", "merge", "discard"],
        help="What to do with candidates",
    )
    cand.add_argument("--slug", type=str, default=None,
                      help="Candidate slug (required for promote/merge/discard)")
    cand.add_argument("--into", type=str, default=None,
                      help="For merge: slug of the page to merge into")
    cand.add_argument("--reason", type=str, default="",
                      help="For discard: why the candidate is being rejected")
    cand.add_argument("--kind", type=str, default=None,
                      choices=["entities", "concepts", "sources", "syntheses"],
                      help="Subtree (auto-detected if omitted)")
    cand.add_argument("--wiki-dir", type=Path, default=None,
                      help="Wiki directory (default: ./wiki)")
    cand.add_argument("--stale", action="store_true",
                      help="For list: only show stale candidates")
    cand.add_argument("--stale-days", type=int, default=30,
                      help="Staleness threshold in days (default 30)")
    cand.add_argument("--json", action="store_true", help="JSON output for list")
    cand.set_defaults(func=cmd_candidates)

    # remember — a fact for review, never straight into the trusted wiki
    rem = sub.add_parser(
        "remember",
        help="Store a fact as a candidate page in wiki/candidates/",
    )
    rem.add_argument("fact", help="The fact to remember")
    rem.add_argument(
        "--title", default="",
        help="Page title (default: the first 8 words of the fact)",
    )
    rem.add_argument(
        "--project", default="",
        help="Project name (default: the current folder name)",
    )
    rem.set_defaults(func=cmd_remember)

    # synthesize (v1.1, #35) — LLM-backed wiki page synthesis
    syn = sub.add_parser(
        "synthesize",
        help="Synthesize wiki source pages from raw sessions via LLM backend",
    )
    # #arch-h7 (#610): the four "what should this invocation do?" flags
    # used to be independently set-able. argparse silently honoured the
    # first one in `cmd_synthesize`'s if/elif chain, so e.g.
    # `synthesize --check --estimate` ran --check and silently dropped
    # --estimate. Use a mutually-exclusive group so the parser rejects
    # the combination loudly with a useful error.
    syn_mode = syn.add_mutually_exclusive_group()
    syn_mode.add_argument(
        "--check", action="store_true",
        help="Probe backend availability and exit (exit 0 if reachable)",
    )
    syn_mode.add_argument(
        "--estimate", action="store_true",
        help="Print cached-vs-fresh token + dollar estimate without calling a backend (#50)",
    )
    # #316 — agent-delegate backend helpers (mutually-exclusive with the
    # default synthesize-all flow + with --check / --estimate above).
    syn_mode.add_argument(
        "--list-pending", action="store_true",
        help="List pending prompts awaiting agent synthesis (agent-delegate backend, #316)",
    )
    syn_mode.add_argument(
        "--complete", metavar="UUID", default=None,
        help="Complete a pending synthesis: read body from --body or stdin, rewrite --page in place (#316)",
    )
    syn_mode.add_argument(
        "--coalesce-only", action="store_true",
        help="Run deterministic low-signal coalescing only; no LLM backend needed",
    )
    syn_mode.add_argument(
        "--backfill-only", action="store_true",
        help="Add the user's original request (description) to existing source pages; no LLM",
    )
    # --force is orthogonal (modifies the default re-synthesize-all flow)
    # and stays outside the exclusion group so callers can pass
    # `synthesize --force` for a forced full re-run.
    syn.add_argument(
        "--force", action="store_true",
        help="Ignore state file, re-synthesize all sessions",
    )
    syn.add_argument(
        "--page", metavar="PATH", default=None,
        help="Target wiki source page for --complete (path relative to repo root or absolute)",
    )
    syn.add_argument(
        "--body", metavar="PATH", default=None,
        help="Read synthesized body from this file for --complete (default: stdin)",
    )
    syn.add_argument(
        "--max-sessions", type=int, default=None, metavar="N",
        help="Synthesize at most N sessions in this run; the rest wait for the next run",
    )
    _add_vault_arg(syn, role="synthesize")
    syn.set_defaults(func=cmd_synthesize)

    # query — same ranking as MCP wiki_query; graphify with --graph
    qry = sub.add_parser("query", help="Search the wiki (same ranking as MCP wiki_query)")
    qry.add_argument("question", nargs="+", help="The question to ask")
    qry.add_argument("--limit", type=int, default=5, help="Pages to return (default 5)")
    qry.add_argument("--json", action="store_true", help="Print hits as JSON")
    qry.add_argument("--project", default="",
                     help="Only pages of this project (frontmatter project)")
    qry.add_argument("--type", dest="page_type", default="",
                     help="Only this page type: source, entity, concept, ...")
    qry.add_argument("--tag", default="",
                     help="Only pages with this tag, e.g. the agent")
    qry.add_argument("--date-from", dest="date_from", default="",
                     help="Only pages dated on or after YYYY-MM-DD")
    qry.add_argument("--date-to", dest="date_to", default="",
                     help="Only pages dated on or before YYYY-MM-DD")
    raw = qry.add_mutually_exclusive_group()
    raw.add_argument("--raw", dest="include_raw", action="store_const", const=True,
                     help="Always rank raw transcripts too")
    raw.add_argument("--no-raw", dest="include_raw", action="store_const", const=False,
                     help="Never read raw transcripts")
    qry.add_argument("--graph", action="store_true",
                     help="Use the optional graphify engine instead (needs sessionwiki[graph])")
    qry.add_argument("--depth", type=int, default=3, help="graphify BFS depth (with --graph)")
    qry.add_argument("--budget", type=int, default=2000, help="graphify token budget (with --graph)")
    qry.set_defaults(func=cmd_query, include_raw=None)

    # version
    ver = sub.add_parser("version", help="Print version")
    ver.set_defaults(func=cmd_version)

    # mcp — stdio MCP server (the entry point MCP clients and registries use)
    mcp = sub.add_parser(
        "mcp",
        help="Run the MCP server on stdio (data root: $SESSIONWIKI_HOME or the current directory)",
    )
    mcp.set_defaults(func=cmd_mcp)

    # recall — recent sessions of a project, for SessionStart hooks
    recall = sub.add_parser(
        "recall",
        help="Print a project's recent sessions (for a SessionStart hook)",
    )
    recall.add_argument(
        "--project", default="",
        help="Project name; default: the hook's cwd on stdin, else the current folder name",
    )
    recall.add_argument("--limit", type=int, default=5, help="How many sessions (default 5)")
    recall.add_argument(
        "--prompt-hook", action="store_true",
        help="UserPromptSubmit hook: add related wiki pages for the prompt on stdin "
             "(only when SESSIONWIKI_PROMPT_RECALL=1)",
    )
    recall.add_argument(
        "--format", choices=["text", "hook", "json"], default="text",
        help="text, hook = SessionStart JSON with additionalContext, "
             "json = machine-readable list",
    )
    recall.set_defaults(func=cmd_recall)

    # import-memory — mirror Claude Code auto memory into wiki/notes/
    imp = sub.add_parser(
        "import-memory",
        help="Mirror Claude Code auto memory files into wiki/notes/",
    )
    imp.add_argument(
        "--store", default="",
        help="Claude Code projects dir (default: ~/.claude/projects)",
    )
    imp.add_argument(
        "--dry-run", action="store_true",
        help="List the files that would change; write nothing",
    )
    imp.set_defaults(func=cmd_import_memory)

    # all — run build + graph + export all + lint in sequence
    all_p = sub.add_parser(
        "all",
        help="Run the full pipeline: build → graph → export all → lint "
             "(add --with-synth to run synthesize first)",
    )
    all_p.add_argument(
        "--out", type=Path, default=REPO_ROOT / "site",
        help="Output dir for build + export (default: site/)",
    )
    all_p.add_argument(
        "--search-mode", choices=["auto", "tree", "flat"], default="auto",
        help="Search index mode passed through to build (default: auto)",
    )
    all_p.add_argument(
        "--graph-engine", choices=["builtin", "graphify"], default="graphify",
        help="Graph engine passed through to graph (default: graphify)",
    )
    all_p.add_argument(
        "--skip-graph", action="store_true",
        help="Skip the graph step (useful when graphify is not installed)",
    )
    all_p.add_argument(
        "--fail-fast", action="store_true",
        help="Stop at the first non-zero step (default: continue, report worst exit code)",
    )
    all_p.add_argument(
        "--strict", action="store_true",
        help="Exit 2 if lint reports any errors/warnings",
    )
    all_p.add_argument(
        "--with-synth", action="store_true",
        help="Run `synthesize` before build (fills wiki/sources/ from raw/; "
             "may invoke LLM — default off for cost discipline, #383)",
    )
    all_p.add_argument(
        "--synth-force", action="store_true",
        help="With --with-synth: pass --force to synthesize (re-synthesize all sessions)",
    )
    _add_vault_arg(all_p, role="all")
    all_p.set_defaults(func=cmd_all)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
