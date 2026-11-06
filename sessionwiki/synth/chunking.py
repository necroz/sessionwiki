"""Chunked synthesis for very large raw sessions.

The one-shot synthesis prompt carries the whole transcript body. A
backend context window cannot hold a session whose markdown is
megabytes long, so the backends used to keep only the head and the
tail (``_truncate_body``). That silently dropped the middle of long
sessions — often the part where the work actually happened.

This module replaces the silent drop with map-reduce:

1. ``split_session`` cuts the body on ``### Turn N`` boundaries into
   chunks that fit the backend's ``max_body_chars``. A single
   oversized turn is split on paragraphs (code fences stay balanced)
   and every part repeats the turn header.
2. Each chunk goes through a digest prompt (see
   ``prompts/chunk_digest.md``) that extracts decisions, facts,
   paths, commands, errors, outcomes and quotes in a bounded number
   of characters.
3. The digests are concatenated and sent through the normal source
   page prompt. When the digests still overflow the reduce budget,
   they are merged in batches first (hierarchical reduce).

Every map and merge call is cached by prompt + backend name, so a
failed run only re-pays for the chunks that failed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sessionwiki import REPO_ROOT
from sessionwiki.synth.base import BaseSynthesizer

#: ``### Turn 12 — User`` / ``### Turn 12 — Assistant`` — the marker the
#: converters write. Keep the pattern in sync with ``pipeline._TURN_MARKER``.
TURN_RE = re.compile(r"(?m)^### Turn \d+ — (?:User|Assistant)\s*$")
_TURN_NUM_RE = re.compile(r"(?m)^### Turn (\d+)")
_FENCE_RE = re.compile(r"(?m)^```")
_MIN_CHUNK_CHARS = 256
_DEFAULT_CACHE_DIR = REPO_ROOT / ".llmwiki-synth-cache"
_DIGEST_PROMPT_PATH = Path(__file__).parent / "prompts" / "chunk_digest.md"
_MERGE_PROMPT_PATH = Path(__file__).parent / "prompts" / "digest_merge.md"
_USER_DIGEST_OVERRIDE = REPO_ROOT / "wiki" / "prompts" / "chunk_digest.md"
_USER_MERGE_OVERRIDE = REPO_ROOT / "wiki" / "prompts" / "digest_merge.md"


@dataclass(frozen=True)
class Chunk:
    """One slice of a raw session body."""

    index: int
    total: int
    text: str
    turns: str


@dataclass(frozen=True)
class ChunkingConfig:
    """``synthesis.chunking`` block with conservative defaults.

    ``chunk_chars`` is an upper bound: the effective size is
    ``min(chunk_chars, backend.max_body_chars)`` so a small model
    context still works.
    """

    enabled: bool = True
    chunk_chars: int = 40_000
    digest_chars: int = 2_000
    reduce_chars: int = 12_000
    max_chunks: int = 200
    max_depth: int = 6
    cache: bool = True
    cache_dir: Path | None = None

    @classmethod
    def from_synthesis_config(cls, synth_cfg: dict[str, Any] | None) -> ChunkingConfig:
        synth = synth_cfg or {}
        nested = synth.get("chunking")
        block = nested if isinstance(nested, dict) else {}
        cache_dir = block.get("cache_dir")
        return cls(
            enabled=bool(block.get("enabled", True)),
            chunk_chars=max(_MIN_CHUNK_CHARS, _int(block.get("chunk_chars"), 40_000)),
            digest_chars=max(200, _int(block.get("digest_chars"), 2_000)),
            reduce_chars=max(_MIN_CHUNK_CHARS, _int(block.get("reduce_chars"), 12_000)),
            max_chunks=max(1, _int(block.get("max_chunks"), 200)),
            max_depth=max(0, _int(block.get("max_depth"), 6)),
            cache=bool(block.get("cache", True)),
            cache_dir=Path(cache_dir) if cache_dir else None,
        )


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ─── splitting ───────────────────────────────────────────────────────────


def split_session(body: str, max_chars: int) -> list[Chunk]:
    """Split ``body`` into chunks of at most ``max_chars`` characters.

    Cuts on turn markers first, so a chunk never starts mid-turn. A
    single turn larger than the limit is split on paragraph
    boundaries; code fences are closed and reopened around each part.
    """
    limit = max(_MIN_CHUNK_CHARS, int(max_chars))
    if not body:
        return [Chunk(0, 1, "", "")]

    pieces: list[str] = []
    current = ""
    for section in _sections(body):
        if len(section) > limit:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(_split_oversized(section, limit))
            continue
        if current and len(current) + len(section) > limit:
            pieces.append(current)
            current = ""
        current += section
    if current:
        pieces.append(current)

    total = len(pieces)
    return [
        Chunk(index=i, total=total, text=text, turns=_turn_range(text))
        for i, text in enumerate(pieces)
    ]


def _sections(body: str) -> list[str]:
    """Turn boundary sections, including any preamble before turn 1."""
    matches = list(TURN_RE.finditer(body))
    if not matches:
        return [body]
    sections: list[str] = []
    if matches[0].start() > 0:
        sections.append(body[: matches[0].start()])
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections.append(body[match.start() : end])
    return sections


def _split_oversized(section: str, limit: int) -> list[str]:
    header, rest = _split_header(section)
    suffix_room = len(" (part 999/999)")
    # Leave room for the header and the part suffix; a floor of 32 keeps
    # every split step making progress even at a tiny configured limit.
    budget = max(32, limit - len(header) - suffix_room - 2)
    parts = _pack_blocks(_blocks(rest), budget) or [""]
    out: list[str] = []
    for i, part in enumerate(parts, 1):
        decorated = f"{header} (part {i}/{len(parts)})" if header else ""
        text = f"{decorated}\n\n{part}" if decorated and part else decorated or part
        if len(text) > limit:
            text = _hard_trim(text, limit)
        out.append(text)
    return out


def _split_header(section: str) -> tuple[str, str]:
    match = TURN_RE.match(section)
    if not match:
        return "", section
    return section[: match.end()], section[match.end() :]


def _blocks(text: str) -> list[str]:
    """Paragraph blocks; a fenced code block stays one block."""
    blocks: list[str] = []
    buffer: list[str] = []
    in_fence = False
    for line in text.splitlines(keepends=True):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
        buffer.append(line)
        if not in_fence and not line.strip():
            blocks.append("".join(buffer))
            buffer = []
    if buffer:
        blocks.append("".join(buffer))
    return blocks


def _pack_blocks(blocks: list[str], budget: int) -> list[str]:
    parts: list[str] = []
    current = ""
    for block in blocks:
        if len(block) > budget:
            if current:
                parts.append(current)
                current = ""
            parts.extend(_split_block(block, budget))
            continue
        if current and len(current) + len(block) > budget:
            parts.append(current)
            current = ""
        current += block
    if current:
        parts.append(current)
    return parts


def _split_block(block: str, budget: int) -> list[str]:
    lines = block.splitlines(keepends=True)
    if not lines:
        return [block]
    fenced = _FENCE_RE.match(lines[0])
    last = len(lines) - 1
    while last > 0 and not lines[last].strip():
        last -= 1
    if fenced and last >= 1 and lines[last].strip().startswith("```"):
        return _split_fenced(lines[: last + 1], budget)
    return _split_lines(lines, budget)


def _split_fenced(lines: list[str], budget: int) -> list[str]:
    opener = lines[0].rstrip("\n")
    closer = lines[-1].rstrip("\n")
    inner = lines[1:-1]
    inner_budget = budget - len(opener) - len(closer) - 2
    if inner_budget < 64:
        return _split_lines(lines, budget)
    groups = _split_lines(inner, inner_budget)
    out: list[str] = []
    for group in groups:
        if group and not group.endswith("\n"):
            group += "\n"
        out.append(f"{opener}\n{group}{closer}\n")
    return out


def _split_lines(lines: list[str], budget: int) -> list[str]:
    parts: list[str] = []
    current = ""
    for line in lines:
        if len(line) > budget:
            if current:
                parts.append(current)
                current = ""
            parts.extend(_hard_slices(line, budget))
            continue
        if current and len(current) + len(line) > budget:
            parts.append(current)
            current = ""
        current += line
    if current:
        parts.append(current)
    return parts


def _hard_slices(text: str, budget: int) -> list[str]:
    return [text[i : i + budget] for i in range(0, len(text), budget)] or [""]


def _hard_trim(text: str, limit: int) -> str:
    return text[: max(1, limit - 1)].rstrip() + "…"


def _turn_range(text: str) -> str:
    numbers = _TURN_NUM_RE.findall(text)
    if not numbers:
        return ""
    first, last = numbers[0], numbers[-1]
    return first if first == last else f"{first}-{last}"


def _cap_text(text: str, limit: int) -> str:
    """Trim an LLM answer at a line boundary so reduce input stays bounded."""
    if not text or len(text) <= limit:
        return text
    cut = text.rfind("\n", 0, limit)
    if cut < limit // 2:
        cut = limit
    return text[:cut].rstrip() + "…"


# ─── prompt cache ────────────────────────────────────────────────────────


class PromptCache:
    """Content-addressed cache for LLM answers.

    Keys include the backend name, the rendered template and the
    request body, so switching models or prompts re-runs the call
    instead of silently reusing an answer from another model.
    """

    def __init__(self, root: Path | str):
        self.root = Path(root)

    def key(self, *parts: Any) -> str:
        digest = hashlib.sha256()
        for part in parts:
            digest.update(b"\0")
            if isinstance(part, str):
                digest.update(part.encode("utf-8"))
            else:
                digest.update(
                    json.dumps(part, sort_keys=True, ensure_ascii=False, default=str).encode(
                        "utf-8"
                    )
                )
        return digest.hexdigest()

    def get(self, key: str) -> str | None:
        path = self.root / key[:2] / f"{key}.txt"
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None

    def put(self, key: str, text: str) -> None:
        path = self.root / key[:2] / f"{key}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".txt")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


# ─── templates ───────────────────────────────────────────────────────────


def load_digest_template(language_rule: str = "") -> str:
    return _load_template(_DIGEST_PROMPT_PATH, _USER_DIGEST_OVERRIDE).replace(
        "{language}", language_rule
    )


def load_merge_template(language_rule: str = "") -> str:
    return _load_template(_MERGE_PROMPT_PATH, _USER_MERGE_OVERRIDE).replace(
        "{language}", language_rule
    )


def _load_template(builtin: Path, override: Path) -> str:
    path = override if override.is_file() else builtin
    return path.read_text(encoding="utf-8")


# ─── synthesis ───────────────────────────────────────────────────────────


class ChunkedSynthesizer(BaseSynthesizer):
    """Map-reduce wrapper around a backend that returns real text.

    ``supports_chunking`` is False here so ``resolve_backend`` never
    wraps the wrapper twice. The agent-delegate and dummy backends
    also opt out: the first writes one pending prompt per session, the
    second ignores the body.
    """

    supports_chunking = False

    def __init__(
        self,
        backend: BaseSynthesizer,
        config: ChunkingConfig | None = None,
        cache: PromptCache | None = None,
        digest_template: str | None = None,
        merge_template: str | None = None,
    ):
        self.backend = backend
        self.config = config or ChunkingConfig()
        self.cache = cache
        self.digest_template = digest_template or load_digest_template()
        self.merge_template = merge_template or load_merge_template()

    @property
    def name(self) -> str:
        return f"ChunkedSynthesizer({self.backend.name})"

    @property
    def max_body_chars(self) -> int:
        return int(getattr(self.backend, "max_body_chars", 40_000))

    def is_available(self) -> bool:
        return self.backend.is_available()

    def synthesize_source_page(
        self,
        raw_body: str,
        meta: dict[str, Any],
        prompt_template: str,
    ) -> str:
        if not self.config.enabled:
            return self.backend.synthesize_source_page(raw_body, meta, prompt_template)

        limit = max(
            _MIN_CHUNK_CHARS,
            min(int(self.config.chunk_chars), self.max_body_chars),
        )
        body, notice = self._bounded(raw_body, limit)
        if len(body) <= limit:
            return self.backend.synthesize_source_page(body, meta, prompt_template)

        chunks = split_session(body, limit)
        if len(chunks) > 1:
            print(
                f"  chunked: {meta.get('slug', 'session')} → {len(chunks)} part(s)",
                file=sys.stderr,
            )
        sections = [
            self._digest_section(chunk, meta, chunks_count=len(chunks)) for chunk in chunks
        ]
        return self._reduce(sections, meta, prompt_template, notice)

    # ── limits ──

    def _bounded(self, body: str, limit: int) -> tuple[str, str]:
        """Keep the head and the tail when even chunking would cost too
        many calls. The omission is written into the reduce input so the
        generated page can mention the gap instead of hiding it.

        ``max_chunks`` is a hard cap: if the head/tail budget still
        splits into more chunks (turn headers and part suffixes eat a
        few characters), shrink the budget until it fits.
        """
        max_chunks = max(1, self.config.max_chunks)
        if len(body) <= limit:
            return body, ""
        budget = limit * max_chunks
        if len(body) <= budget:
            return body, ""
        while budget > limit:
            candidate, notice = _head_tail(body, budget)
            if len(split_session(candidate, limit)) <= max_chunks:
                return candidate, notice
            budget = int(budget * 0.9)
        return _head_tail(body, limit)

    def _digest_cap(self) -> int:
        # A digest larger than the reduce budget cannot be merged.
        return max(200, min(self.config.digest_chars, self.config.reduce_chars - 200))

    # ── map ──

    def _digest_section(
        self, chunk: Chunk, meta: dict[str, Any], *, chunks_count: int
    ) -> str:
        chunk_meta = dict(meta or {})
        chunk_meta["chunk"] = {
            "index": chunk.index,
            "total": chunk.total,
            "turns": chunk.turns,
        }
        digest = self._cached_call(chunk.text, chunk_meta, self.digest_template)
        digest = _cap_text(digest, self._digest_cap())
        label = f"turns {chunk.turns}" if chunk.turns else "opening"
        return f"## Part {chunk.index + 1}/{chunks_count} ({label})\n{digest}"

    # ── reduce ──

    def _reduce(
        self,
        sections: list[str],
        meta: dict[str, Any],
        prompt_template: str,
        notice: str,
    ) -> str:
        limit = max(
            _MIN_CHUNK_CHARS,
            min(int(self.config.reduce_chars), self.max_body_chars),
        )
        combined = self._combine(sections, notice)
        depth = 0
        while (
            len(combined) > limit
            and len(sections) > 1
            and depth < max(0, self.config.max_depth)
        ):
            batches = _batch_sections(sections, limit)
            merged: list[str] = []
            for index, batch in enumerate(batches):
                merge_meta = dict(meta or {})
                merge_meta["merge"] = {"index": index, "total": len(batches)}
                text = self._cached_call(
                    "\n\n".join(batch), merge_meta, self.merge_template
                )
                merged.append(_cap_text(text, self._digest_cap()))
            sections = [
                f"## Merged digest {i + 1}/{len(merged)}\n{text}"
                for i, text in enumerate(merged)
            ]
            combined = self._combine(sections, notice)
            depth += 1
        return self.backend.synthesize_source_page(combined, meta, prompt_template)

    def _combine(self, sections: list[str], notice: str) -> str:
        parts: list[str] = []
        if notice:
            parts.append(
                "NOTE: this session was too large to summarize completely; "
                f"{notice}. Mention the gap in the summary if it matters."
            )
        parts.extend(sections)
        return "\n\n".join(parts)

    # ── paid call ──

    def _cached_call(
        self, body: str, meta: dict[str, Any], template: str
    ) -> str:
        key = None
        if self.cache is not None and self.config.cache:
            key = self.cache.key(self.backend.name, template, body, meta)
            hit = self.cache.get(key)
            if hit is not None:
                return hit
        answer = self.backend.synthesize_source_page(body, meta, template)
        if key is not None:
            self.cache.put(key, answer)
        return answer


def _head_tail(body: str, budget: int) -> tuple[str, str]:
    """Two-thirds head plus one-third tail, with an explicit gap marker."""
    omitted = max(0, len(body) - budget)
    notice = f"[middle omitted: {omitted:,} characters]"
    keep = max(2, budget - len(notice) - 4)
    head = (keep * 2) // 3
    tail = keep - head
    return f"{body[:head]}\n\n...{notice}...\n\n{body[-tail:]}", notice


def _batch_sections(sections: list[str], limit: int) -> list[list[str]]:
    batches: list[list[str]] = []
    current: list[str] = []
    size = 0
    for section in sections:
        addition = len(section) + (2 if current else 0)
        if current and size + addition > limit:
            batches.append(current)
            current = [section]
            size = len(section)
        else:
            current.append(section)
            size += addition
    if current:
        batches.append(current)
    return batches