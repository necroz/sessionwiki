"""Smoke tests for the CLI entry point."""

from __future__ import annotations

import subprocess
import sys

from sessionwiki import __version__


def test_version_flag():
    r = subprocess.run(
        [sys.executable, "-m", "sessionwiki", "--version"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert __version__ in r.stdout


def test_version_subcommand():
    r = subprocess.run(
        [sys.executable, "-m", "sessionwiki", "version"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert __version__ in r.stdout


def test_mcp_subcommand_serves_stdio(tmp_path):
    """`sessionwiki mcp` must start the stdio MCP server, so registry
    clients can launch the PyPI package as `uvx sessionwiki mcp`."""
    import json
    import os

    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    r = subprocess.run(
        [sys.executable, "-m", "sessionwiki", "mcp"],
        input=json.dumps(request) + "\n",
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "SESSIONWIKI_HOME": str(tmp_path)},
    )
    assert r.returncode == 0, r.stderr
    response = json.loads(r.stdout.splitlines()[0])
    names = {tool["name"] for tool in response["result"]["tools"]}
    assert {"wiki_query", "wiki_search", "wiki_read_page"} <= names


def test_adapters_lists_claude_code():
    r = subprocess.run(
        [sys.executable, "-m", "sessionwiki", "adapters"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert "claude_code" in r.stdout
    assert "codex_cli" in r.stdout
    # obsidian moved to contrib — no longer in default `adapters` output


def test_no_args_prints_help():
    r = subprocess.run(
        [sys.executable, "-m", "sessionwiki"],
        capture_output=True, text=True,
    )
    # Should print help and exit 0
    assert r.returncode == 0
    assert "usage" in r.stdout.lower() or "sessionwiki" in r.stdout
