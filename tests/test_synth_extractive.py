"""Extractive synthesis: a useful source page without an LLM (D1).

The page must pick text that is already in the transcript — the request,
the last answer, decision sentences, file paths and tools — and must
never invent a ``[[wikilink]]`` or copy code out as prose.
"""

from __future__ import annotations

from sessionwiki.synth.base import DummySynthesizer
from sessionwiki.synth.extractive import ExtractiveSynthesizer
from sessionwiki.synth.pipeline import resolve_backend

RAW_BODY = """### Turn 1 — User

Please make recall fast.

### Turn 2 — Assistant

Here is the patch:

```python
decided_in_code = True
```

### Turn 3 — Assistant

We decided to use SQLite because it ships with Python, see [[OtherPage]]. The change lands in sessionwiki/cli.py.
"""

META = {
    "slug": "sess_demo",
    "project": "demo-project",
    "date": "2026-11-09",
    "description": "Make recall fast",
    "user_messages": 1,
    "tool_calls": 2,
    "tools_used": ["Bash", "Edit"],
    "model": "demo-model",
}


def _section(page: str, heading: str) -> str:
    """Return the text between ``heading`` and the next ``## `` heading."""
    after = page.split(heading, 1)[1]
    return after.split("\n## ", 1)[0]


def test_page_has_all_four_source_sections() -> None:
    page = ExtractiveSynthesizer().synthesize_source_page(RAW_BODY, META, "")

    for heading in ("## Summary", "## Key Claims", "## Key Quotes", "## Connections"):
        assert heading in page


def test_decision_sentence_is_a_claim_and_code_is_not() -> None:
    page = ExtractiveSynthesizer().synthesize_source_page(RAW_BODY, META, "")
    claims = _section(page, "## Key Claims")

    assert "We decided to use SQLite because it ships with Python" in claims
    assert "decided_in_code" not in page


def test_claim_keeps_project_entity_as_the_only_link_and_lists_files() -> None:
    page = ExtractiveSynthesizer().synthesize_source_page(RAW_BODY, META, "")

    assert "[[OtherPage]]" not in page
    assert page.count("[[") == 1
    assert "[[DemoProject]]" in page
    assert "`sessionwiki/cli.py`" in _section(page, "## Key Claims")


def test_output_is_deterministic() -> None:
    synthesizer = ExtractiveSynthesizer()

    first = synthesizer.synthesize_source_page(RAW_BODY, META, "")
    second = synthesizer.synthesize_source_page(RAW_BODY, META, "")

    assert first == second


def test_body_without_turns_falls_back_to_dummy() -> None:
    body = "A body with no turn headings at all."

    assert ExtractiveSynthesizer().synthesize_source_page(
        body, META, ""
    ) == DummySynthesizer().synthesize_source_page(body, META, "")


def test_resolve_backend_returns_extractive() -> None:
    backend = resolve_backend({"synthesis": {"backend": "extractive"}})

    assert isinstance(backend, ExtractiveSynthesizer)


def test_russian_decision_words_are_picked_up() -> None:
    body = (
        "### Turn 1 — User\n\nОставь Markdown.\n\n"
        "### Turn 2 — Assistant\n\nРешили оставить Markdown, потому что так проще.\n"
    )

    page = ExtractiveSynthesizer().synthesize_source_page(body, META, "")

    assert "Решили оставить Markdown, потому что так проще." in _section(
        page, "## Key Claims"
    )


def test_list_marker_from_the_transcript_is_not_doubled() -> None:
    body = (
        "### Turn 1 — User\n\nFix the cache.\n\n"
        "### Turn 2 — Assistant\n\n- Fixed the cache bug in sessionwiki/cli.py.\n"
    )

    page = ExtractiveSynthesizer().synthesize_source_page(body, META, "")

    assert "- Fixed the cache bug in sessionwiki/cli.py." in _section(
        page, "## Key Claims"
    )
    assert "- - " not in page
