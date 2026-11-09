"""MCP clients truncate long text; keep every description under the cap."""

from __future__ import annotations

from sessionwiki.mcp import server

MAX_TOOL_DESCRIPTION = 1024
MAX_PROPERTY_DESCRIPTION = 400
MAX_INSTRUCTIONS = 2048


def test_every_tool_description_fits():
    too_long = {
        t["name"]: len(t["description"])
        for t in server.TOOLS
        if len(t["description"]) > MAX_TOOL_DESCRIPTION
    }
    assert not too_long, too_long


def test_every_property_description_fits():
    too_long = {}
    for tool in server.TOOLS:
        props = tool.get("inputSchema", {}).get("properties", {})
        for name, spec in props.items():
            text = spec.get("description", "")
            if len(text) > MAX_PROPERTY_DESCRIPTION:
                too_long[f"{tool['name']}.{name}"] = len(text)
    assert not too_long, too_long


def test_tool_names_are_unique():
    names = [t["name"] for t in server.TOOLS]
    assert len(names) == len(set(names))


def test_instructions_fit_when_present():
    result = server.handle_initialize({})
    text = result.get("instructions", "")
    assert len(text) <= MAX_INSTRUCTIONS, len(text)
