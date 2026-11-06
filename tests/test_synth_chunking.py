"""Chunked synthesis for very large raw sessions.

A session whose markdown body exceeds the backend's ``max_body_chars``
used to lose everything between the head and the tail: the OpenAI
backend kept 12K chars, Ollama 8K. These tests pin the replacement:
split on turn boundaries, map each part to a digest, reduce the
digests into the usual source page, and cache every paid call.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sessionwiki.synth.base import BaseSynthesizer
from sessionwiki.synth.chunking import (
    Chunk,
    ChunkedSynthesizer,
    ChunkingConfig,
    PromptCache,
    split_session,
)

DIGEST_TEMPLATE = "DIGEST {body}\nMETA {meta}"
MERGE_TEMPLATE = "MERGE {body}\nMETA {meta}"
PAGE_TEMPLATE = "PAGE {body}\nMETA {meta}"


class RecordingBackend(BaseSynthesizer):
    """Backend double: records every call, answers by prompt prefix."""

    supports_chunking = True
    max_body_chars = 12000

    def __init__(self, digest_size: int = 120, fail_on_index: int | None = None):
        self.calls: list[dict] = []
        self.digest_size = digest_size
        self.fail_on_index = fail_on_index

    @property
    def name(self) -> str:
        return "RecordingBackend"

    def is_available(self) -> bool:
        return True

    def synthesize_source_page(self, raw_body, meta, prompt_template):
        self.calls.append(
            {"body": raw_body, "meta": meta, "template": prompt_template}
        )
        chunk = (meta or {}).get("chunk") or {}
        if (
            self.fail_on_index is not None
            and prompt_template.startswith("DIGEST")
            and chunk.get("index") == self.fail_on_index
        ):
            raise RuntimeError("boom")
        if prompt_template.startswith("DIGEST"):
            return ("- fact " + "d" * max(0, self.digest_size - 7))[: self.digest_size]
        if prompt_template.startswith("MERGE"):
            return ("- merged " + "m" * max(0, self.digest_size - 9))[: self.digest_size]
        assert prompt_template.startswith("PAGE")
        return "## Summary\n\nDone."

    def digest_calls(self) -> list[dict]:
        return [c for c in self.calls if c["template"].startswith("DIGEST")]

    def merge_calls(self) -> list[dict]:
        return [c for c in self.calls if c["template"].startswith("MERGE")]

    def page_calls(self) -> list[dict]:
        return [c for c in self.calls if c["template"].startswith("PAGE")]


def _body(turns: int = 4, size: int = 300) -> str:
    return "\n".join(
        f"### Turn {i} — User\n\nrequest {i} " + "x" * size
        for i in range(1, turns + 1)
    )


def _wrap(backend, *, config: ChunkingConfig | None = None, cache=None):
    return ChunkedSynthesizer(
        backend,
        config or ChunkingConfig(),
        cache=cache,
        digest_template=DIGEST_TEMPLATE,
        merge_template=MERGE_TEMPLATE,
    )


# ─── splitter ────────────────────────────────────────────────────────────


def test_split_keeps_every_turn_and_stays_under_limit():
    body = _body(turns=6, size=400)
    chunks = split_session(body, max_chars=1200)

    assert len(chunks) > 1
    assert all(isinstance(c, Chunk) for c in chunks)
    assert all(len(c.text) <= 1200 for c in chunks)
    for i in range(1, 7):
        assert f"### Turn {i} — User" in "".join(c.text for c in chunks)


def test_split_concatenation_preserves_original_text():
    body = _body(turns=4, size=100)
    chunks = split_session(body, max_chars=250)

    assert "\n".join(c.text for c in chunks).replace("\n\n", "\n") == body.replace(
        "\n\n", "\n"
    )


def test_split_records_turn_range():
    body = _body(turns=3, size=100)
    chunks = split_session(body, max_chars=250)

    assert chunks[0].turns.startswith("1")
    assert chunks[-1].turns.endswith("3")


def test_split_huge_single_turn_on_paragraphs():
    body = "### Turn 1 — Assistant\n\n" + "\n\n".join(
        f"paragraph {i} " + "p" * 200 for i in range(10)
    )
    chunks = split_session(body, max_chars=700)

    assert len(chunks) > 1
    assert all(len(c.text) <= 700 for c in chunks)
    assert all("### Turn 1 — Assistant" in c.text for c in chunks)
    assert "part 2/" in chunks[1].text


def test_split_keeps_code_fences_balanced():
    fenced = "```python\n" + "\n".join(f"line_{i} = {i}" for i in range(80)) + "\n```"
    body = f"### Turn 1 — Assistant\n\n{fenced}"
    chunks = split_session(body, max_chars=500)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.text.count("```") % 2 == 0, chunk.text


def test_split_empty_body_returns_one_empty_chunk():
    assert split_session("", max_chars=100) == [Chunk(0, 1, "", "")]


def test_split_tiny_limit_is_clamped_not_looping():
    chunks = split_session(_body(turns=1, size=5000), max_chars=1)
    assert len(chunks) > 1
    assert all(len(c.text) <= 256 for c in chunks)


# ─── map → reduce ────────────────────────────────────────────────────────


def test_small_body_goes_straight_to_the_page_call():
    backend = RecordingBackend()
    synth = _wrap(backend, config=ChunkingConfig(chunk_chars=12000))

    out = synth.synthesize_source_page(_body(turns=1, size=50), {}, PAGE_TEMPLATE)

    assert out.startswith("## Summary")
    assert len(backend.page_calls()) == 1
    assert backend.digest_calls() == []


def test_large_body_maps_each_chunk_then_reduces():
    backend = RecordingBackend()
    synth = _wrap(
        backend,
        config=ChunkingConfig(chunk_chars=700, reduce_chars=100_000),
    )

    out = synth.synthesize_source_page(_body(turns=4, size=300), {}, PAGE_TEMPLATE)

    assert out.startswith("## Summary")
    assert len(backend.digest_calls()) > 1
    assert len(backend.page_calls()) == 1
    final_body = backend.page_calls()[0]["body"]
    assert "Part 1/" in final_body
    assert final_body.count("- fact") == len(backend.digest_calls())


def test_backend_cap_limits_the_chunk_size():
    backend = RecordingBackend()
    backend.max_body_chars = 300
    synth = _wrap(
        backend,
        config=ChunkingConfig(chunk_chars=50_000, reduce_chars=100_000),
    )

    synth.synthesize_source_page(_body(turns=4, size=300), {}, PAGE_TEMPLATE)

    assert backend.digest_calls()
    assert all(len(c["body"]) <= 300 for c in backend.digest_calls())


def test_digest_calls_carry_chunk_position_and_turn_range():
    backend = RecordingBackend()
    synth = _wrap(
        backend,
        config=ChunkingConfig(chunk_chars=700, reduce_chars=100_000),
    )

    synth.synthesize_source_page(_body(turns=4, size=300), {"slug": "s1"}, PAGE_TEMPLATE)

    metis = [c["meta"] for c in backend.digest_calls()]
    assert metis[0]["slug"] == "s1"
    assert metis[0]["chunk"]["index"] == 0
    assert metis[0]["chunk"]["total"] == len(metis)
    assert metis[0]["chunk"]["turns"]


def test_hierarchical_reduce_when_digests_overflow():
    backend = RecordingBackend(digest_size=500)
    synth = _wrap(
        backend,
        config=ChunkingConfig(
            chunk_chars=300, digest_chars=500, reduce_chars=1200, max_depth=6
        ),
    )

    out = synth.synthesize_source_page(_body(turns=9, size=300), {}, PAGE_TEMPLATE)

    assert out.startswith("## Summary")
    assert backend.merge_calls(), "digests should be merged in batches first"
    assert len(backend.page_calls()) == 1
    assert len(backend.page_calls()[0]["body"]) <= 1200


def test_digest_is_capped_at_digest_chars():
    backend = RecordingBackend(digest_size=5000)
    synth = _wrap(
        backend,
        config=ChunkingConfig(
            chunk_chars=300, digest_chars=400, reduce_chars=100_000
        ),
    )

    synth.synthesize_source_page(_body(turns=3, size=300), {}, PAGE_TEMPLATE)

    final_body = backend.page_calls()[0]["body"]
    long_lines = [line for line in final_body.splitlines() if line.startswith("- fact")]
    assert long_lines, final_body
    assert all(len(line) <= 401 for line in long_lines)


def test_failed_chunk_raises_and_keeps_successful_digests(tmp_path: Path):
    cache = PromptCache(tmp_path / "cache")
    failing = RecordingBackend(fail_on_index=1)
    synth = _wrap(
        failing,
        config=ChunkingConfig(chunk_chars=700, reduce_chars=100_000),
        cache=cache,
    )

    with pytest.raises(RuntimeError):
        synth.synthesize_source_page(_body(turns=4, size=300), {}, PAGE_TEMPLATE)

    assert failing.digest_calls()[0]["meta"]["chunk"]["index"] == 0

    healthy = RecordingBackend()
    synth2 = _wrap(
        healthy,
        config=ChunkingConfig(chunk_chars=700, reduce_chars=100_000),
        cache=cache,
    )
    synth2.synthesize_source_page(_body(turns=4, size=300), {}, PAGE_TEMPLATE)

    called_indexes = [c["meta"]["chunk"]["index"] for c in healthy.digest_calls()]
    assert 0 not in called_indexes
    assert 1 in called_indexes


def test_cache_skips_paid_map_calls_on_rerun(tmp_path: Path):
    cache = PromptCache(tmp_path / "cache")
    first = RecordingBackend()
    _wrap(
        first,
        config=ChunkingConfig(chunk_chars=700, reduce_chars=100_000),
        cache=cache,
    ).synthesize_source_page(_body(turns=4, size=300), {}, PAGE_TEMPLATE)

    second = RecordingBackend()
    out = _wrap(
        second,
        config=ChunkingConfig(chunk_chars=700, reduce_chars=100_000),
        cache=cache,
    ).synthesize_source_page(_body(turns=4, size=300), {}, PAGE_TEMPLATE)

    assert out.startswith("## Summary")
    assert second.digest_calls() == []
    assert len(second.page_calls()) == 1


def test_oversized_session_is_head_tail_truncated_with_notice():
    backend = RecordingBackend()
    synth = _wrap(
        backend,
        config=ChunkingConfig(
            chunk_chars=100, max_chunks=2, reduce_chars=100_000
        ),
    )

    synth.synthesize_source_page(_body(turns=10, size=1000), {}, PAGE_TEMPLATE)

    final_body = backend.page_calls()[0]["body"]
    assert "omitted" in final_body.lower()
    assert len(backend.digest_calls()) <= 2


def test_disabled_chunking_keeps_old_single_call(tmp_path: Path):
    backend = RecordingBackend()
    synth = _wrap(
        backend,
        config=ChunkingConfig(enabled=False, chunk_chars=700),
    )

    out = synth.synthesize_source_page(_body(turns=8, size=300), {}, PAGE_TEMPLATE)

    assert out.startswith("## Summary")
    assert backend.digest_calls() == []
    assert len(backend.page_calls()) == 1


# ─── config + cache ──────────────────────────────────────────────────────


def test_config_reads_nested_chunking_block():
    cfg = ChunkingConfig.from_synthesis_config(
        {
            "max_body_chars": 96000,
            "chunking": {
                "enabled": False,
                "chunk_chars": 24000,
                "digest_chars": 800,
                "reduce_chars": 9000,
                "max_chunks": 50,
                "cache": False,
            },
        }
    )
    assert cfg.enabled is False
    assert cfg.chunk_chars == 24000
    assert cfg.digest_chars == 800
    assert cfg.reduce_chars == 9000
    assert cfg.max_chunks == 50
    assert cfg.cache is False


def test_config_defaults_are_sane():
    cfg = ChunkingConfig()
    assert cfg.enabled is True
    assert cfg.chunk_chars == 40_000
    assert cfg.reduce_chars <= cfg.chunk_chars * 2
    assert cfg.max_chunks >= 100


def test_prompt_cache_roundtrip(tmp_path: Path):
    cache = PromptCache(tmp_path / "cache")
    key = cache.key("backend", "template", "body", {"chunk": 1})
    assert cache.get(key) is None
    cache.put(key, "hello")
    assert cache.get(key) == "hello"
    assert cache.key("backend2", "template", "body", {"chunk": 1}) != key


def test_cache_disabled_writes_nothing(tmp_path: Path):
    backend = RecordingBackend()
    synth = _wrap(
        backend,
        config=ChunkingConfig(
            chunk_chars=300, cache=False, reduce_chars=100_000
        ),
        cache=PromptCache(tmp_path / "cache"),
    )
    synth.synthesize_source_page(_body(turns=2, size=300), {}, PAGE_TEMPLATE)
    assert not (tmp_path / "cache").exists() or not any(
        (tmp_path / "cache").iterdir()
    )


# ─── backend wiring ──────────────────────────────────────────────────────


def test_resolve_backend_wraps_chunk_capable_backends():
    from sessionwiki.synth.pipeline import resolve_backend

    backend = resolve_backend(
        {
            "synthesis": {
                "backend": "openai",
                "base_url": "http://127.0.0.1:8001/v1",
                "model": "qwen3.8",
            }
        }
    )
    assert isinstance(backend, ChunkedSynthesizer)
    assert backend.supports_chunking is False


def test_resolve_backend_leaves_dummy_unwrapped():
    from sessionwiki.synth.base import DummySynthesizer
    from sessionwiki.synth.pipeline import resolve_backend

    backend = resolve_backend({"synthesis": {"backend": "dummy"}})
    assert isinstance(backend, DummySynthesizer)


def test_max_body_chars_reaches_openai_backend_config():
    from sessionwiki.synth.openai_compat import load_openai_config

    cfg = load_openai_config(
        {"synthesis": {"max_body_chars": 96000}}
    )
    assert cfg.max_body_chars == 96000


def test_json_meta_is_still_serialisable_in_digest_call():
    backend = RecordingBackend()
    synth = _wrap(
        backend,
        config=ChunkingConfig(chunk_chars=300, reduce_chars=100_000),
    )
    synth.synthesize_source_page(_body(turns=2, size=300), {"tags": ["a"]}, PAGE_TEMPLATE)
    for call in backend.digest_calls():
        json.dumps(call["meta"])


def test_builtin_prompt_templates_have_placeholders_and_language():
    from sessionwiki.synth.chunking import load_digest_template, load_merge_template

    for template in (
        load_digest_template("LANGUAGE_RULE"),
        load_merge_template("LANGUAGE_RULE"),
    ):
        assert "{body}" in template
        assert "{meta}" in template
        assert "LANGUAGE_RULE" in template