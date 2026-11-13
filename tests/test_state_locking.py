"""Concurrent sync/synthesize runs must not corrupt the state files.

The Claude Code Stop-hook runs ``sessionwiki sync`` after every reply, in
every open session, so several converters can start at once. Before
this guard they raced on ``.llmwiki-state.json``: a reader that caught a
half-written file got ``{}`` and re-processed the whole corpus. The
synth state has the same shape and a re-run there costs LLM calls.
"""

from __future__ import annotations

import json
from pathlib import Path

from sessionwiki import convert
from sessionwiki.lock import FileLock, atomic_write_text, lock_path_for
from sessionwiki.synth import pipeline


def test_lock_path_sits_next_to_state_file(tmp_path: Path) -> None:
    state = tmp_path / ".llmwiki-state.json"
    assert lock_path_for(state) == tmp_path / ".llmwiki-state.json.lock"


def test_atomic_write_replaces_content_and_leaves_no_temp(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    target.write_text("old", encoding="utf-8")

    atomic_write_text(target, '{"a": 1}')

    assert target.read_text(encoding="utf-8") == '{"a": 1}'
    assert sorted(p.name for p in tmp_path.iterdir()) == ["state.json"]


def test_convert_save_state_is_atomic(tmp_path: Path) -> None:
    target = tmp_path / ".llmwiki-state.json"
    convert.save_state(target, {"k": 1.0})

    assert json.loads(target.read_text(encoding="utf-8")) == {"k": 1.0}
    assert sorted(p.name for p in tmp_path.iterdir()) == [".llmwiki-state.json"]


def test_convert_all_skips_when_another_sync_holds_the_lock(
    tmp_path: Path, capsys
) -> None:
    state = tmp_path / ".llmwiki-state.json"
    with FileLock(lock_path_for(state)):
        rc = convert.convert_all(
            out_dir=tmp_path / "raw", state_file=state, lock_timeout=0
        )

    assert rc == 0
    assert not state.exists()
    assert "another sync is running" in capsys.readouterr().err


def test_convert_all_holds_the_lock_while_converting(
    tmp_path: Path, monkeypatch
) -> None:
    state = tmp_path / ".llmwiki-state.json"
    seen: list[bool] = []

    def fake_convert(**kwargs) -> int:
        probe = FileLock(lock_path_for(state), timeout=0)
        acquired = probe.acquire()
        if acquired:
            probe.release()
        seen.append(acquired)
        return 0

    monkeypatch.setattr(convert, "_convert_all_unlocked", fake_convert)

    assert convert.convert_all(state_file=state) == 0
    assert seen == [False]
    # Released afterwards.
    with FileLock(lock_path_for(state), timeout=0):
        pass


def test_synthesize_skips_when_another_run_holds_the_lock(
    tmp_path: Path, capsys
) -> None:
    state = tmp_path / ".llmwiki-synth-state.json"
    with FileLock(lock_path_for(state)):
        summary = pipeline.synthesize_new_sessions(
            raw_dir=tmp_path / "raw",
            wiki_sources_dir=tmp_path / "wiki" / "sources",
            state_file=state,
            lock_timeout=0,
        )

    assert summary["locked"] is True
    assert summary["synthesized"] == 0
    assert summary["errors"] == []
    assert not state.exists()
    assert "another synthesize is running" in capsys.readouterr().err


def test_synth_save_state_is_atomic(tmp_path: Path) -> None:
    target = tmp_path / ".llmwiki-synth-state.json"
    pipeline._save_state({"p.md": 1.0}, target)

    assert json.loads(target.read_text(encoding="utf-8")) == {"p.md": 1.0}
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        ".llmwiki-synth-state.json"
    ]


def _fake_nt_os(monkeypatch, lock):
    # Patch lock.os (not the global os.name) so pathlib still builds
    # PosixPath on Linux while lock.acquire takes the Windows branch.
    import os as real_os
    import types

    monkeypatch.setattr(
        lock, "os", types.SimpleNamespace(name="nt", fstat=real_os.fstat)
    )


def _fake_msvcrt(monkeypatch, locking):
    import sys
    import types

    fake = types.ModuleType("msvcrt")
    fake.LK_NBLCK = 1
    fake.LK_UNLCK = 2
    fake.locking = locking
    monkeypatch.setitem(sys.modules, "msvcrt", fake)


def test_windows_acquire_does_not_read_locked_byte(tmp_path, monkeypatch) -> None:
    # Windows msvcrt locks are mandatory: reading a byte another process
    # holds raises PermissionError. acquire() must not read file content.
    from sessionwiki import lock

    _fake_nt_os(monkeypatch, lock)
    _fake_msvcrt(monkeypatch, lambda fd, mode, n: None)

    class NoReadHandle:
        def __init__(self, real):
            self._real = real

        def read(self, *a, **k):
            raise PermissionError("locked byte")

        def __getattr__(self, name):
            return getattr(self._real, name)

    real_open = open

    def fake_open(*a, **k):
        return NoReadHandle(real_open(*a, **k))

    monkeypatch.setattr(lock, "open", fake_open, raising=False)
    assert lock.FileLock(tmp_path / "s.lock").acquire() is True


def test_windows_busy_lock_returns_false(tmp_path, monkeypatch) -> None:
    from sessionwiki import lock

    _fake_nt_os(monkeypatch, lock)

    def busy(fd, mode, n):
        raise OSError("busy")

    _fake_msvcrt(monkeypatch, busy)
    assert lock.FileLock(tmp_path / "s.lock", timeout=0).acquire() is False
