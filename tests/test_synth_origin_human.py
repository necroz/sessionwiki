"""Tests for the ``origin: human`` guard (card 22)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sessionwiki._frontmatter import is_human_page
from sessionwiki.synth.base import BaseSynthesizer
from sessionwiki.synth.pipeline import (
    _coalesce_low_signal_sessions,
    backfill_source_descriptions,
    synthesize_new_sessions,
)

RAW_SESSION = """---
title: "Session: test-synth — 2026-04-09"
type: source
tags: [claude-code]
date: 2026-04-09
source_file: raw/sessions/test-proj/2026-04-09-test-synth.md
slug: test-synth
project: test-proj
model: claude-sonnet-4-6
user_messages: 3
tool_calls: 5
---

# Session: test-synth — 2026-04-09

### Turn 1 — User

Write a test.

### Turn 1 — Assistant

Done.
"""

HUMAN_PAGE = """---
title: "Hand-written source note"
type: source
origin: human
project: test-proj
date: 2026-04-09
---

# Hand-written source note

Do not overwrite me.
"""

NO_RESPONSE_BODY = """### Turn 1 — User

Run the next mission step.

### Turn 1 — Assistant
"""


class RecordingBackend(BaseSynthesizer):
    """Backend stub that records every session slug it is asked about."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def synthesize_source_page(self, raw_body, meta, prompt_template) -> str:
        self.calls.append(str(meta.get("slug")))
        return "## Summary\n\nRewritten by the backend.\n"

    def is_available(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def _isolated_synth_state(tmp_path, monkeypatch):
    """Keep the real .llmwiki-synth-state.json out of test runs."""
    monkeypatch.setattr(
        "sessionwiki.synth.pipeline.STATE_FILE",
        tmp_path / "synth-state.json",
    )


def _seed(tmp_path: Path) -> tuple[Path, Path, Path]:
    raw = tmp_path / "raw" / "sessions"
    sessions = raw / "test-proj"
    sessions.mkdir(parents=True)
    (sessions / "2026-04-09-test-synth.md").write_text(
        RAW_SESSION, encoding="utf-8"
    )
    sources = tmp_path / "wiki" / "sources"
    sources.mkdir(parents=True)
    log_file = tmp_path / "wiki" / "log.md"
    log_file.write_text("# Log\n", encoding="utf-8")
    return raw, sources, log_file


def _source_page(sources: Path, *, origin: str | None) -> Path:
    page = sources / "test-proj" / "2026-04-09-test-synth.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    extra = f"origin: {origin}\n" if origin else ""
    page.write_text(
        "---\ntitle: \"Existing page\"\ntype: source\n"
        f"{extra}project: test-proj\n---\n\nOriginal body.\n",
        encoding="utf-8",
    )
    return page


def test_human_page_survives_forced_synthesis(tmp_path: Path):
    raw, sources, log_file = _seed(tmp_path)
    page = _source_page(sources, origin="human")
    before = page.read_text(encoding="utf-8")
    backend = RecordingBackend()

    summary = synthesize_new_sessions(
        backend=backend,
        raw_dir=raw,
        wiki_sources_dir=sources,
        log_path=log_file,
        force=True,
    )

    assert page.read_text(encoding="utf-8") == before
    assert backend.calls == []
    assert summary["kept_human"] == 1
    assert summary["synthesized"] == 0
    # Recorded as handled so the next run does not retry the session.
    state = json.loads((tmp_path / "synth-state.json").read_text(encoding="utf-8"))
    assert "test-proj/2026-04-09-test-synth.md" in state


def test_page_without_origin_is_overwritten(tmp_path: Path):
    raw, sources, log_file = _seed(tmp_path)
    page = _source_page(sources, origin=None)
    before = page.read_text(encoding="utf-8")
    backend = RecordingBackend()

    summary = synthesize_new_sessions(
        backend=backend,
        raw_dir=raw,
        wiki_sources_dir=sources,
        log_path=log_file,
    )

    after = page.read_text(encoding="utf-8")
    assert after != before
    assert "Rewritten by the backend." in after
    assert backend.calls == ["test-synth"]
    assert summary["kept_human"] == 0
    assert summary["synthesized"] == 1


def test_coalescing_leaves_a_human_cluster_page_alone(tmp_path: Path):
    raw = tmp_path / "raw"
    sources = tmp_path / "wiki" / "sources" / "proj"
    sessions = []
    for day in ("01", "02", "03"):
        date = f"2026-01-{day}"
        slug = f"s{day}"
        path = raw / "proj" / f"{date}-{slug}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(NO_RESPONSE_BODY, encoding="utf-8")
        meta = {
            "slug": slug,
            "date": date,
            "project": "proj",
            "tool_calls": "0",
            "token_totals": json.dumps({"output": 0}),
        }
        sessions.append((path, meta, NO_RESPONSE_BODY))

    individual = []
    for _, meta, _ in sessions:
        page = sources / f"{meta['date']}-{meta['slug']}.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(
            "---\ntitle: old\n---\n\nAuto-generated cluster page\n",
            encoding="utf-8",
        )
        individual.append(page)

    cluster = sources / "2026-noop-sessions.md"
    cluster.write_text(HUMAN_PAGE, encoding="utf-8")
    before = cluster.read_text(encoding="utf-8")
    state: dict[str, float] = {}

    clusters, coalesced, affected = _coalesce_low_signal_sessions(
        sessions,
        sources_out=tmp_path / "wiki" / "sources",
        state=state,
        raw_dir=raw,
        min_group=3,
        window="all",
    )

    assert clusters == 0
    assert coalesced == set()
    assert affected == set()
    assert cluster.read_text(encoding="utf-8") == before
    assert all(page.exists() for page in individual)
    assert state == {}


def test_backfill_skips_a_human_page(tmp_path: Path):
    raw = tmp_path / "raw" / "proj"
    raw.mkdir(parents=True)
    (raw / "2026-04-09-test-synth.md").write_text(
        RAW_SESSION.replace(
            'date: 2026-04-09\n',
            'date: 2026-04-09\ndescription: "Hand-written request"\n',
        ),
        encoding="utf-8",
    )
    (raw / "2026-04-10-test-synth.md").write_text(
        RAW_SESSION.replace(
            'date: 2026-04-09\n',
            'date: 2026-04-10\ndescription: "Second request"\n',
        ),
        encoding="utf-8",
    )
    sources = tmp_path / "wiki" / "sources"

    human = _source_page(sources, origin="human")
    human_before = human.read_text(encoding="utf-8")
    control = sources / "test-proj" / "2026-04-10-test-synth.md"
    control.write_text(
        "---\ntitle: \"Existing page\"\ntype: source\n"
        "project: test-proj\n---\n\nOriginal body.\n",
        encoding="utf-8",
    )

    updated = backfill_source_descriptions(
        raw_dir=raw, wiki_sources_dir=sources
    )

    assert human.read_text(encoding="utf-8") == human_before
    assert "description:" in control.read_text(encoding="utf-8")
    assert updated == 1


def test_is_human_page_rejects_missing_and_llm_pages(tmp_path: Path):
    assert is_human_page(tmp_path / "missing.md") is False

    llm = tmp_path / "llm.md"
    llm.write_text("---\ntitle: \"x\"\norigin: llm\n---\n\nBody.\n", encoding="utf-8")
    assert is_human_page(llm) is False

    human = tmp_path / "human.md"
    human.write_text(
        "---\ntitle: \"x\"\norigin: human\n---\n\nBody.\n", encoding="utf-8"
    )
    assert is_human_page(human) is True
