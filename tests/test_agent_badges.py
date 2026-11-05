"""Agent badges for ZCode and OpenCode sessions.

The ZCode and OpenCode adapters tag their pages `zcode` / `opencode` and
leave `agent:` unset. Before this, those sessions fell through to the
model check — a ZCode session on a Claude model showed "Claude", and on
GLM / Qwen it showed the generic "Agent".
"""

from __future__ import annotations

import pytest

from sessionwiki.build import detect_agent_label
from sessionwiki.render.css import CSS


@pytest.mark.parametrize(
    "meta, expected",
    [
        ({"tags": ["zcode", "session-transcript"], "model": "glm-4.6"}, ("ZCode", "agent-zcode")),
        ({"tags": ["zcode", "session-transcript"], "model": "claude-sonnet-4-6"}, ("ZCode", "agent-zcode")),
        ({"tags": ["opencode", "session-transcript"], "model": "qwen3-coder"}, ("OpenCode", "agent-opencode")),
        ({"tags": "[opencode, session-transcript]", "model": "gpt-5"}, ("OpenCode", "agent-opencode")),
        ({"agent": "zcode"}, ("ZCode", "agent-zcode")),
        ({"agent": "opencode"}, ("OpenCode", "agent-opencode")),
    ],
)
def test_zcode_and_opencode_sessions_get_their_own_badge(meta, expected) -> None:
    assert detect_agent_label(meta) == expected


@pytest.mark.parametrize(
    "meta, expected",
    [
        ({"tags": ["claude-code", "session-transcript"], "model": "claude-sonnet-4-6"}, ("Claude", "agent-claude")),
        ({"tags": ["codex-cli"], "model": "gpt-5-codex"}, ("Codex", "agent-codex")),
        ({"model": "gemini-2.5-pro"}, ("Gemini", "agent-gemini")),
        # A project merely *named* after a tool must not change the badge.
        ({"tags": ["claude-code", "opencode-plugin"], "model": "claude-opus-4-7"}, ("Claude", "agent-claude")),
    ],
)
def test_other_agents_are_unchanged(meta, expected) -> None:
    assert detect_agent_label(meta) == expected


def test_badge_classes_have_light_and_dark_styles() -> None:
    for cls in ("agent-zcode", "agent-opencode"):
        assert f".{cls} " in CSS or f".{cls}{{" in CSS
        assert f':root[data-theme="dark"] .{cls}' in CSS
