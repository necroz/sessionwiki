"""Tests for light-mode polish CSS changes (v1.0, #119)."""

from __future__ import annotations

from sessionwiki.build import CSS


def test_card_shadow_var_defined():
    """Card shadow var must be defined so cards get depth on white backgrounds."""
    assert "--shadow-card:" in CSS
    assert "--shadow-card-hover:" in CSS


def test_card_uses_shadow_var():
    """The .card rule should apply the new shadow variable."""
    # .card { ...box-shadow: var(--shadow-card); }
    assert "var(--shadow-card)" in CSS
    assert "var(--shadow-card-hover)" in CSS


def test_border_darker_than_before():
    """Light-mode border was #e2e8f0; now #d1d5db for better card separation."""
    assert "--border: #d1d5db" in CSS


def test_border_subtle_var_defined():
    """--border-subtle is the old weaker border for less prominent separators."""
    assert "--border-subtle:" in CSS


def test_bg_code_darker_than_before():
    """--bg-code was #f1f5f9; now slightly darker for better contrast."""
    assert "--bg-code: #edf0f5" in CSS


def test_heatmap_level0_visible_on_white():
    """Level-0 was #ebedf0 (invisible on white); now #dde1e6."""
    assert "--heatmap-0: #dde1e6" in CSS


def test_tool_chart_bars_less_saturated():
    """Light-mode tool colors less saturated (better on white card)."""
    # Check new colors exist
    assert "--tool-cat-io: #2563eb" in CSS
    assert "--tool-cat-search: #9333ea" in CSS


def test_tool_chart_bars_have_stroke():
    """Bars now have a thin stroke for definition on light backgrounds."""
    assert "stroke: rgba(15, 23, 42, 0.08)" in CSS


def test_nav_has_shadow_for_grounding():
    """Nav gets a subtle box-shadow to stay grounded on light backgrounds."""
    # Match the updated .nav rule
    assert "box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04)" in CSS


def test_nav_backdrop_filter_stronger():
    """Backdrop blur bumped from 12px to 16px for better grounding."""
    assert "backdrop-filter: blur(16px)" in CSS


def test_dark_mode_preserves_shadow_vars():
    """Dark theme must also define --shadow-card so refs don't break."""
    # Check dark theme has shadow-card
    # Dark mode block contains its own --shadow-card value
    assert CSS.count("--shadow-card:") >= 2  # once in :root, once in dark theme


def test_dark_mode_preserves_border_subtle():
    """Dark theme also defines --border-subtle."""
    # There are 2 dark-mode rulesets (media query + [data-theme])
    count = CSS.count("--border-subtle:")
    assert count >= 3  # :root + @media dark + [data-theme=dark]
