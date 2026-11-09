"""Mirror Claude Code auto memory into ``wiki/notes`` (card 26, roadmap C5).

Claude Code keeps its own memory under
``~/.claude/projects/<dir>/memory/*.md``.  Those files change in place and
``raw/`` is immutable, so they are mirrored into
``wiki/notes/claude-memory/<project>/`` instead of going through the session
pipeline.

The mirrored pages are ``origin: human``: the user, or an agent acting on the
user's request, owns the text.  Synthesis and every other LLM writer must not
rewrite them (card 22).
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from sessionwiki._frontmatter import (
    format_frontmatter_value,
    is_human_page,
    parse_frontmatter,
)
from sessionwiki.adapters.claude_code import ClaudeCodeAdapter
from sessionwiki.convert import Redactor

_NOTES_SUBDIR = Path("notes") / "claude-memory"
# Canonical location in Claude Code.  `source_path` keeps this `~`-relative
# form even when the store is overridden, so no absolute home path is written.
_CANONICAL_STORE = "~/.claude/projects"


def _one_line(value: Any) -> str:
    """Collapse whitespace and drop double quotes so the value fits on one
    frontmatter line."""
    text = value if isinstance(value, str) else str(value or "")
    return " ".join(text.split()).replace('"', "'")


def _project_entity(project: str) -> str:
    """``ai-newsletter`` → ``AiNewsletter`` — same rule as the synthesizers."""
    return "".join(
        part.capitalize() for part in re.split(r"[-_\s]+", project) if part
    )


def _project_tag(project: str) -> str:
    """Make the project slug safe for the inline ``tags: [...]`` list."""
    tag = re.sub(r"[^\w.\-/+ ]", "-", project)
    return tag[:64] or "unknown"


def _render_page(
    project: str,
    memory_file: Path,
    description: str,
    body: str,
    date: str,
) -> str:
    """Build one ``wiki/notes`` page from a Claude memory file."""
    title = _one_line(f"Claude memory: {project} — {memory_file.stem}")
    project_dir = memory_file.parent.parent.name
    source_path = f"{_CANONICAL_STORE}/{project_dir}/memory/{memory_file.name}"
    lines = [
        "---",
        f"title: {format_frontmatter_value(title)}",
        "type: note",
        "origin: human",
        f"project: {format_frontmatter_value(project)}",
    ]
    if description:
        lines.append(f"description: {format_frontmatter_value(description)}")
    lines += [
        f"source_path: {format_frontmatter_value(source_path)}",
        f"tags: {format_frontmatter_value(['claude-memory', _project_tag(project)])}",
        f"last_updated: {format_frontmatter_value(date)}",
        "---",
    ]
    parts = ["\n".join(lines), ""]
    if body:
        parts += [body, ""]
    parts += ["## Connections", "", f"- [[{_project_entity(project)}]] — project", ""]
    return "\n".join(parts)


def import_claude_memory(
    store: Path,
    wiki_dir: Path,
    config: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Mirror ``<store>/<dir>/memory/*.md`` into
    ``wiki/notes/claude-memory/<project>/``.

    Returns ``{"written": [...], "unchanged": int, "skipped": [...]}``.
    ``written`` lists the relative paths, also in ``dry_run`` mode where
    nothing is written; ``skipped`` holds ``{"path", "reason"}`` entries for
    destinations the mirror must not touch.
    """
    store = Path(store).expanduser()
    adapter = ClaudeCodeAdapter()
    # derive_project_slug resolves the project against this attribute, so
    # --store must move it too.
    adapter.session_store_path = store
    redact = Redactor(config)

    written: list[str] = []
    skipped: list[dict[str, str]] = []
    unchanged = 0

    if not store.is_dir():
        return {"written": written, "unchanged": unchanged, "skipped": skipped}

    for project_dir in sorted(path for path in store.iterdir() if path.is_dir()):
        memory_dir = project_dir / "memory"
        if not memory_dir.is_dir():
            continue
        project = adapter.derive_project_slug(project_dir / "session.jsonl")
        for memory_file in sorted(memory_dir.glob("*.md")):
            source_text = memory_file.read_text(encoding="utf-8", errors="replace")
            meta, body = parse_frontmatter(source_text)
            description = _one_line(redact(str(meta.get("description", ""))))
            date = datetime.fromtimestamp(
                memory_file.stat().st_mtime
            ).strftime("%Y-%m-%d")
            page = _render_page(
                project, memory_file, description, redact(body).strip(), date
            )

            dest = wiki_dir / _NOTES_SUBDIR / project / memory_file.name
            rel = dest.relative_to(wiki_dir).as_posix()
            existing = None
            if dest.is_file():
                if not is_human_page(dest):
                    skipped.append({
                        "path": rel,
                        "reason": "destination exists without origin: human",
                    })
                    continue
                existing = dest.read_text(encoding="utf-8", errors="replace")
            if existing == page:
                unchanged += 1
                continue
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(page, encoding="utf-8")
            written.append(rel)

    return {"written": written, "unchanged": unchanged, "skipped": skipped}
