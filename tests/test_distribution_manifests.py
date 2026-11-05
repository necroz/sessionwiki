"""Guardrails for the catalog manifests: the Claude Code plugin, its
marketplace, the MCP Registry `server.json` and the Glama claim file.

The catalogs read these files as published, and a published MCP Registry
version cannot be changed, so drift between them and the package is caught
here instead of after a release.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from sessionwiki import __version__
from sessionwiki.cli import build_parser

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_JSON = REPO_ROOT / "server.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
PLUGIN_DIR = REPO_ROOT / "plugin"
PLUGIN_JSON = PLUGIN_DIR / ".claude-plugin" / "plugin.json"
GLAMA_JSON = REPO_ROOT / "glama.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _subcommands() -> set[str]:
    for action in build_parser()._actions:
        if isinstance(getattr(action, "choices", None), dict):
            return set(action.choices)
    raise AssertionError("no subparsers on build_parser()")


def test_server_json_versions_match_package():
    server = _load(SERVER_JSON)
    assert server["version"] == __version__
    for package in server["packages"]:
        assert package["version"] == __version__


def test_server_json_pypi_package_runs_the_mcp_subcommand():
    (package,) = [p for p in _load(SERVER_JSON)["packages"] if p["registryType"] == "pypi"]
    assert package["identifier"] == "sessionwiki"
    assert package["transport"] == {"type": "stdio"}
    args = [a["value"] for a in package.get("packageArguments", [])]
    assert args == ["mcp"]
    assert "mcp" in _subcommands()
    env = {e["name"] for e in package.get("environmentVariables", [])}
    assert "SESSIONWIKI_HOME" in env


def test_server_json_description_fits_registry_limit():
    assert len(_load(SERVER_JSON)["description"]) <= 100


def test_readme_carries_the_registry_ownership_line():
    """The MCP Registry checks the PyPI description (our README) for
    `mcp-name: <server name>`, followed by whitespace or `-->`."""
    name = _load(SERVER_JSON)["name"]
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert re.search(rf"mcp-name: {re.escape(name)}(\s|-->)", readme)


def test_plugin_version_matches_package():
    assert _load(PLUGIN_JSON)["version"] == __version__


def test_plugin_mcp_server_uses_the_mcp_subcommand_and_user_folder():
    plugin = _load(PLUGIN_JSON)
    server = plugin["mcpServers"]["sessionwiki"]
    assert server["args"][-1] == "mcp"
    home = server["env"]["SESSIONWIKI_HOME"]
    key = re.fullmatch(r"\$\{user_config\.(\w+)\}", home).group(1)
    assert plugin["userConfig"][key]["required"] is True


def test_marketplace_points_to_the_plugin_folder():
    market = _load(MARKETPLACE_JSON)
    assert market["owner"]["name"]
    (entry,) = market["plugins"]
    assert entry["name"] == _load(PLUGIN_JSON)["name"]
    assert (REPO_ROOT / entry["source"]).resolve() == PLUGIN_DIR.resolve()


def test_plugin_skills_have_frontmatter():
    skills = sorted((PLUGIN_DIR / "skills").glob("*/SKILL.md"))
    assert skills
    for skill in skills:
        text = skill.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert re.search(rf"^name: {skill.parent.name}$", text, re.MULTILINE)
        assert re.search(r"^description: \S", text, re.MULTILINE)


def test_glama_claim_names_a_maintainer():
    assert _load(GLAMA_JSON)["maintainers"]
