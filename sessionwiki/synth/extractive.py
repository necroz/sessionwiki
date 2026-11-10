"""Extractive synthesizer: a useful source page without any LLM (D1).

Picks text that is already in the transcript: the request, the last
answer, sentences that state a decision or a fix, file paths and tools.
Output follows the source-page sections so lint and the site work.
"""

from __future__ import annotations

import re
from typing import Any

from sessionwiki.synth.base import DummySynthesizer

_TURN_RE = re.compile(r"^### Turn \d+ — (User|Assistant)\s*$", re.MULTILINE)
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_DECISION_RE = re.compile(
    r"\b(decided|decision|we will|let's go with|chose|switched to|fixed|"
    r"root cause|the fix|because)\b|решил|выбрал|исправ|причина|потому что",
    re.IGNORECASE,
)
_PATH_RE = re.compile(r"(?<![\w/])[\w./-]+\.(?:py|md|json|toml|ya?ml|ts|tsx|js|sh|sql|go|rs)\b")
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_LIST_MARKER_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
_MAX_CLAIMS = 8
_MAX_FILES = 10
_MAX_LINE_CHARS = 300
_MAX_CLAIM_CHARS = 240


def _collapse(text: str) -> str:
    """Collapse every whitespace run into one space."""
    return " ".join(text.split())


def _strip_fences(text: str) -> str:
    """Remove fenced code blocks, so code never becomes a claim."""
    return _FENCE_RE.sub(" ", text)


def _strip_wikilinks(text: str) -> str:
    """Turn ``[[Page]]`` into plain text, so no link is fabricated."""
    text = _WIKILINK_RE.sub(lambda m: (m.group(2) or m.group(1)).strip(), text)
    return text.replace("[[", "[").replace("]]", "]")


def _clip(text: str, limit: int) -> str:
    """Keep at most ``limit`` characters, with an ellipsis when cut."""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _split_turns(raw_body: str) -> list[tuple[str, str]]:
    """Return ``(role, text)`` pairs in transcript order."""
    headings = list(_TURN_RE.finditer(raw_body))
    turns: list[tuple[str, str]] = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(raw_body)
        turns.append((heading.group(1), raw_body[heading.end() : end].strip()))
    return turns


def _lead_sentences(text: str, limit: int) -> str:
    """Take leading sentences until the next one would overflow ``limit``."""
    sentences = [sentence.strip() for sentence in _SENTENCE_RE.split(text) if sentence.strip()]
    if not sentences:
        return ""
    lead = sentences[0]
    for sentence in sentences[1:]:
        candidate = f"{lead} {sentence}"
        if len(candidate) > limit:
            break
        lead = candidate
    return _clip(lead, limit)


class ExtractiveSynthesizer(DummySynthesizer):
    """Build a source page from the transcript text alone.

    Deterministic and offline: same transcript in, same page out.
    """

    supports_chunking = False

    @property
    def name(self) -> str:
        return "ExtractiveSynthesizer"

    def _clean(self, text: str) -> str:
        """Fence- and link-free text with single spaces."""
        return _collapse(_strip_wikilinks(_strip_fences(text)))

    def _decision_sentences(self, turns: list[tuple[str, str]]) -> list[str]:
        """Assistant sentences that state a decision or a fix, newest first."""
        claims: list[str] = []
        seen: set[str] = set()
        for role, text in reversed(turns):
            if role != "Assistant":
                continue
            for sentence in _SENTENCE_RE.split(self._clean(text)):
                # A transcript list item would otherwise render as "- - …".
                sentence = _LIST_MARKER_RE.sub("", sentence.strip()).strip()
                if not sentence or not _DECISION_RE.search(sentence):
                    continue
                sentence = _clip(sentence, _MAX_CLAIM_CHARS)
                key = sentence.lower()
                if key in seen:
                    continue
                seen.add(key)
                claims.append(sentence)
                if len(claims) >= _MAX_CLAIMS:
                    return claims
        return claims

    def _file_paths(self, raw_body: str) -> list[str]:
        """File paths from the whole body, code included, first seen first."""
        paths: list[str] = []
        seen: set[str] = set()
        for match in _PATH_RE.finditer(raw_body):
            path = match.group(0)
            if path in seen:
                continue
            seen.add(path)
            paths.append(path)
            if len(paths) >= _MAX_FILES:
                break
        return paths

    def synthesize_source_page(
        self,
        raw_body: str,
        meta: dict[str, Any],
        prompt_template: str,
    ) -> str:
        turns = _split_turns(raw_body)
        if not turns:
            return super().synthesize_source_page(raw_body, meta, prompt_template)

        users = [text for role, text in turns if role == "User"]
        assistants = [text for role, text in turns if role == "Assistant"]

        description = self._clean(str(meta.get("description") or ""))
        request = description or (self._clean(users[0]) if users else "")
        request = _clip(request, _MAX_LINE_CHARS) or "(no request recorded)"
        last_answer = ""
        for text in reversed(assistants):
            cleaned = self._clean(text)
            if cleaned:
                last_answer = _lead_sentences(cleaned, _MAX_LINE_CHARS)
                break
        summary_line = f"{request} → {last_answer}" if last_answer else request
        stats_line = f"({meta.get('user_messages', '?')} user messages, {meta.get('tool_calls', '?')} tool calls.)"

        claims = [f"- {claim}" for claim in self._decision_sentences(turns)]
        files = self._file_paths(raw_body)
        if files:
            claims.append("- Files: " + ", ".join(f"`{path}`" for path in files))
        raw_tools = meta.get("tools_used") or []
        if isinstance(raw_tools, str):
            # Frontmatter may store the inline list form as one string.
            raw_tools = raw_tools.strip().strip("[]").split(",")
        tools = [
            str(tool).strip().strip("'\"")
            for tool in raw_tools
            if str(tool).strip()
        ]
        if tools:
            claims.append("- Tools: " + ", ".join(tools))
        if not claims:
            claims.append("- (no decisions, files or tools detected)")

        quote = self._clean(users[0]) if users else ""
        quote = _clip(quote, _MAX_LINE_CHARS) or "(no user turn recorded)"

        project = str(meta.get("project") or "").strip()
        project_entity = self._title_case_project(project) if project and project != "unknown" else ""
        connections = (
            f"- [[{project_entity}]] — parent project"
            if project_entity
            else "*(connections auto-extracted by a real synthesizer will appear here)*"
        )
        claims_block = "\n".join(claims)

        return f"""## Summary

{summary_line}
{stats_line}

## Key Claims

{claims_block}

## Key Quotes

> {quote}

## Connections

{connections}
"""
