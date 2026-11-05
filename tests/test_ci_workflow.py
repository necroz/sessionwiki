"""Tests for the wiki-checks CI workflow (v1.0, #163)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from sessionwiki import REPO_ROOT


WORKFLOW = REPO_ROOT / ".github" / "workflows" / "wiki-checks.yml"


def test_workflow_exists():
    assert WORKFLOW.is_file()


def test_workflow_has_name():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.startswith("name:")


def test_triggers_on_push_and_pr():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "push:" in text
    assert "pull_request:" in text


def test_workflow_dispatch_trigger():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text


def test_path_filters_include_sessionwiki():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "sessionwiki/**" in text


def test_runs_on_ubuntu():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: ubuntu-latest" in text


def test_uses_pinned_python_version():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python-version:" in text


def test_installs_sessionwiki():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "pip install -e ." in text


def test_seeds_from_demo_sessions():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "examples/demo-sessions" in text


def test_runs_eval():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "sessionwiki eval" in text


def test_runs_lint_with_fail_on_errors():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "sessionwiki lint" in text
    assert "--fail-on-errors" in text


def test_runs_build():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "sessionwiki build" in text


def test_runs_check_links():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "sessionwiki check-links" in text


def test_runs_adapters_listing():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "sessionwiki adapters" in text


def test_has_read_only_permissions():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "contents: read" in text


def test_pinned_setup_python_version():
    """Verify actions/setup-python@v6 (from the dependency bundle #189)."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "actions/setup-python@v6" in text


def test_pinned_checkout_version():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "actions/checkout@v4" in text
