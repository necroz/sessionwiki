"""Two CSS regressions found while refreshing the demo screenshots."""

from __future__ import annotations

import re

from sessionwiki.render.css import CSS


def test_dark_mode_does_not_reset_highlight_token_colours() -> None:
    # A `color: unset` on .hljs-* under dark mode out-ranked the
    # github-dark stylesheet, so code blocks lost their colours.
    assert not re.search(r"\.hljs-[a-z_]+[^{}]*\{\s*color:\s*unset", CSS)


def test_light_token_overrides_only_apply_in_light_mode() -> None:
    assert ':root[data-theme="light"] .hljs-keyword' in CSS
    assert ":root:not([data-theme]) .hljs-keyword" in CSS
    # Never on a page that is explicitly dark.
    assert ':root:not([data-theme="dark"]) .hljs-keyword' not in CSS


def test_sessions_table_header_sticks_to_its_own_top_edge() -> None:
    # .table-wrap scrolls horizontally, so it is the sticky container;
    # an offset equal to the nav height pushed the header over row one.
    rule = re.search(r"\.sessions-table thead\s*\{([^}]*)\}", CSS)
    assert rule is not None
    assert re.search(r"\btop:\s*0\s*;", rule.group(1))
