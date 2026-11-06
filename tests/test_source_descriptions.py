"""Source pages keep the user's own wording.

Wiki source pages are synthesised in English, but the raw transcript's
``description`` holds the user's first request in their own language
(835 of 941 sessions on a real wiki were Russian). Synthesis dropped
it, so a question asked in that language matched no wiki page. These
tests pin that ``description`` and ``slug`` reach the source page, both
for new pages and, via a backfill, for pages written before.
"""

from __future__ import annotations

from pathlib import Path

from sessionwiki._frontmatter import parse_frontmatter
from sessionwiki.cli import build_parser
from sessionwiki.synth.pipeline import _build_source_page, backfill_source_descriptions


def _raw(root: Path, name: str, front: dict[str, str], body: str = "## Conversation\n") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = "\n".join(f"{k}: {v}" for k, v in front.items())
    path.write_text(f"---\n{meta}\n---\n\n{body}", encoding="utf-8")
    return path


_META = {
    "slug": "sess_abc",
    "title": "Session: sess_abc",
    "project": "car",
    "date": "2026-10-26",
    "source_file": "raw/sessions/2026-10-26T10-00-car-sess_abc.md",
    "description": 'Как поменять лампу "ближнего"\n света на поло седан?',
}


def test_new_source_page_keeps_slug_and_description():
    page = _build_source_page(dict(_META), "## Summary\n\nReplaced a bulb.\n")
    meta, body = parse_frontmatter(page)
    assert meta["slug"] == "sess_abc"
    # One line, no double quotes inside the quoted YAML value.
    assert meta["description"] == "Как поменять лампу 'ближнего' света на поло седан?"
    assert "Replaced a bulb." in body


def test_long_description_is_cut():
    meta_in = dict(_META, description="слово " * 200)
    meta, _ = parse_frontmatter(_build_source_page(meta_in, "body\n"))
    assert len(meta["description"]) <= 301
    assert meta["description"].endswith("…")


def test_page_without_raw_description_has_no_description_key():
    meta_in = {k: v for k, v in _META.items() if k != "description"}
    meta, _ = parse_frontmatter(_build_source_page(meta_in, "body\n"))
    assert "description" not in meta


def _old_page(sources: Path) -> Path:
    page = sources / "car" / "2026-10-26-sess_abc.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        '---\ntitle: "Session: sess_abc"\ntype: source\nproject: car\n---\n\n## Summary\n\nReplaced a bulb.\n',
        encoding="utf-8",
    )
    return page


def test_backfill_adds_description_and_slug_to_existing_page(tmp_path: Path):
    raw = tmp_path / "raw" / "sessions"
    sources = tmp_path / "wiki" / "sources"
    _raw(raw, "2026-10-26T10-00-car-sess_abc.md", {
        "slug": "sess_abc", "project": "car", "date": "2026-10-26",
        "description": '"Как поменять лампу ближнего света?"',
    })
    page = _old_page(sources)

    assert backfill_source_descriptions(raw_dir=raw, wiki_sources_dir=sources) == 1

    meta, body = parse_frontmatter(page.read_text(encoding="utf-8"))
    assert meta["description"] == "Как поменять лампу ближнего света?"
    assert meta["slug"] == "sess_abc"
    assert meta["title"] == "Session: sess_abc"
    assert body.strip() == "## Summary\n\nReplaced a bulb."


def test_backfill_is_idempotent_and_dry_run_writes_nothing(tmp_path: Path):
    raw = tmp_path / "raw" / "sessions"
    sources = tmp_path / "wiki" / "sources"
    _raw(raw, "2026-10-26T10-00-car-sess_abc.md", {
        "slug": "sess_abc", "project": "car", "date": "2026-10-26",
        "description": '"Как поменять лампу?"',
    })
    page = _old_page(sources)
    before = page.read_text(encoding="utf-8")

    assert backfill_source_descriptions(raw_dir=raw, wiki_sources_dir=sources, dry_run=True) == 1
    assert page.read_text(encoding="utf-8") == before

    assert backfill_source_descriptions(raw_dir=raw, wiki_sources_dir=sources) == 1
    assert backfill_source_descriptions(raw_dir=raw, wiki_sources_dir=sources) == 0


def test_backfill_skips_sessions_without_description_or_page(tmp_path: Path):
    raw = tmp_path / "raw" / "sessions"
    sources = tmp_path / "wiki" / "sources"
    _raw(raw, "a.md", {"slug": "sess_abc", "project": "car", "date": "2026-10-26"})
    _raw(raw, "b.md", {"slug": "sess_zzz", "project": "car", "date": "2026-10-27",
                       "description": '"no page for me"'})
    _old_page(sources)
    assert backfill_source_descriptions(raw_dir=raw, wiki_sources_dir=sources) == 0


def test_synthesize_has_backfill_only_flag():
    args = build_parser().parse_args(["synthesize", "--backfill-only"])
    assert args.backfill_only is True


# ─── Language of synthesised pages ───────────────────────────────────


from sessionwiki.synth.pipeline import _load_prompt_template  # noqa: E402


def test_prompt_asks_for_the_sessions_language_by_default():
    prompt = _load_prompt_template()
    assert "{language}" not in prompt
    assert "language the user wrote in" in prompt
    # Headings and links stay fixed so search, site and links keep working.
    assert "Keep the section headings" in prompt


def test_prompt_can_pin_one_language():
    prompt = _load_prompt_template(language="English")
    assert "Write the prose in English." in prompt
    assert "language the user wrote in" not in prompt
