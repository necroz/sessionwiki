"""MCP stdio must be UTF-8 regardless of the platform default encoding.

On Windows a redirected stdin/stdout defaults to the ANSI code page
(e.g. cp1251), which mangles non-ASCII JSON-RPC requests and responses.
"""

from __future__ import annotations

from sessionwiki.mcp import server


def test_force_utf8_reconfigures_stream() -> None:
    class S:
        def __init__(self) -> None:
            self.enc = None

        def reconfigure(self, **kw) -> None:
            self.enc = kw.get("encoding")

    s = S()
    server._force_utf8(s)
    assert s.enc == "utf-8"


def test_force_utf8_tolerates_plain_stream() -> None:
    # A stream without reconfigure (e.g. io.StringIO) must not raise.
    server._force_utf8(object())