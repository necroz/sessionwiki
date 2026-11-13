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


class _RecordingStream:
    def __init__(self, lines=()):
        self.lines = list(lines)
        self.enc = None
        self.written: list[str] = []

    def reconfigure(self, **kw):
        self.enc = kw.get("encoding")

    def __iter__(self):
        return iter(self.lines)

    def write(self, text):
        self.written.append(text)

    def flush(self):
        pass


def test_main_forces_utf8_on_stdin_stdout_and_stderr(monkeypatch) -> None:
    # A regression that dropped one of the three calls used to pass.
    stdin = _RecordingStream(
        ['{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}\n']
    )
    stdout = _RecordingStream()
    stderr = _RecordingStream()
    monkeypatch.setattr(server.sys, "stdin", stdin)
    monkeypatch.setattr(server.sys, "stdout", stdout)
    monkeypatch.setattr(server.sys, "stderr", stderr)

    assert server.main() == 0
    assert stdin.enc == "utf-8"
    assert stdout.enc == "utf-8"
    assert stderr.enc == "utf-8"