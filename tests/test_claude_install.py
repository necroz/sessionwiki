"""``sessionwiki claude install`` and ``sessionwiki claude nightly``.

A new machine had no command for the Claude Code side: the Stop hook
(sync after every reply), the SessionStart hook (recall) and the nightly
synthesize job were all written by hand. Every function takes ``home``
so the tests never touch the real user config.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sessionwiki import claude_install as ci

PY = "/opt/venv/bin/python"


def _settings(home: Path) -> dict:
    return json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))


def _commands(data: dict, event: str) -> list[str]:
    return [
        hook["command"]
        for entry in data.get("hooks", {}).get(event, [])
        for hook in entry.get("hooks", [])
    ]


def _install_hooks(home: Path, root: Path, **kw) -> list[str]:
    return ci.install_hooks(home=home, python_exe=PY, repo_root=root, windows=False, **kw)


# ─── hooks ───────────────────────────────────────────────────────────


def test_hooks_are_written_and_other_settings_kept(tmp_path: Path):
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"model": "opus", "hooks": {"Stop": [
        {"hooks": [{"type": "command", "command": "notify-send done"}]}]}}))
    _install_hooks(tmp_path, tmp_path / "wiki-home")
    data = _settings(tmp_path)
    assert data["model"] == "opus"
    stop = _commands(data, "Stop")
    assert stop[0] == "notify-send done"
    assert "-m sessionwiki sync --adapter claude_code" in stop[1]
    assert stop[1].rstrip().endswith("&")
    assert f"SESSIONWIKI_HOME={tmp_path / 'wiki-home'}" in stop[1]
    start = _commands(data, "SessionStart")
    assert len(start) == 1
    assert "-m sessionwiki recall --format hook" in start[0]


def test_reinstall_is_idempotent(tmp_path: Path):
    _install_hooks(tmp_path, tmp_path)
    messages = _install_hooks(tmp_path, tmp_path)
    data = _settings(tmp_path)
    assert len(_commands(data, "Stop")) == 1
    assert len(_commands(data, "SessionStart")) == 1
    assert all("already installed" in m for m in messages)


def test_hand_written_hooks_count_as_installed(tmp_path: Path):
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"hooks": {
        "Stop": [{"hooks": [{"type": "command",
                             "command": "cd /x && nohup .venv/bin/python -m sessionwiki sync --no-auto-build &"}]}],
        "SessionStart": [{"hooks": [{"type": "command",
                                     "command": "SESSIONWIKI_HOME=/x python -m sessionwiki recall --format hook"}]}],
    }}))
    before = settings.read_text()
    _install_hooks(tmp_path, tmp_path)
    assert settings.read_text() == before


def test_force_replaces_our_hooks_only(tmp_path: Path):
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"hooks": {"Stop": [
        {"hooks": [{"type": "command", "command": "old -m sessionwiki sync"}]},
        {"hooks": [{"type": "command", "command": "notify-send done"}]},
    ]}}))
    _install_hooks(tmp_path, tmp_path, force=True)
    stop = _commands(_settings(tmp_path), "Stop")
    assert "notify-send done" in stop
    assert not any(c.startswith("old ") for c in stop)
    assert sum("sessionwiki sync" in c for c in stop) == 1


def test_dry_run_writes_nothing(tmp_path: Path):
    messages = _install_hooks(tmp_path, tmp_path, dry_run=True)
    assert not (tmp_path / ".claude" / "settings.json").exists()
    assert all("would" in m for m in messages)


def test_claude_config_dir_is_respected(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    _install_hooks(tmp_path, tmp_path)
    assert (tmp_path / "cfg" / "settings.json").is_file()
    assert not (tmp_path / ".claude").exists()


def test_broken_settings_are_left_untouched(tmp_path: Path):
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text("{ not json")
    with pytest.raises(ValueError, match="settings.json"):
        _install_hooks(tmp_path, tmp_path)
    assert settings.read_text() == "{ not json"


def test_windows_skips_the_background_stop_hook(tmp_path: Path):
    messages = ci.install_hooks(home=tmp_path, python_exe=PY, repo_root=tmp_path, windows=True)
    data = _settings(tmp_path)
    assert _commands(data, "Stop") == []
    assert any("Stop hook: skipped" in m for m in messages)
    start = _commands(data, "SessionStart")
    assert start[0].startswith(f'cd "{tmp_path}" && ')


def test_paths_with_spaces_are_quoted(tmp_path: Path):
    root = tmp_path / "my wiki"
    ci.install_hooks(home=tmp_path, python_exe="/opt/my venv/python", repo_root=root, windows=False)
    stop = _commands(_settings(tmp_path), "Stop")[0]
    assert "'/opt/my venv/python'" in stop
    assert f"'{root}'" in stop


# ─── nightly scheduler entry ─────────────────────────────────────────


def test_systemd_units_run_the_nightly_command(tmp_path: Path):
    ci.install_scheduler("systemd", home=tmp_path, python_exe=PY, repo_root=tmp_path / "w", at="04:15")
    unit_dir = tmp_path / ".config" / "systemd" / "user"
    service = (unit_dir / "sessionwiki-synth.service").read_text()
    timer = (unit_dir / "sessionwiki-synth.timer").read_text()
    assert f"ExecStart={PY} -m sessionwiki claude nightly" in service
    assert f"Environment=SESSIONWIKI_HOME={tmp_path / 'w'}" in service
    assert "OnCalendar=*-*-* 04:15:00" in timer
    assert "Persistent=true" in timer


def test_existing_units_are_kept_without_force(tmp_path: Path):
    unit_dir = tmp_path / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True)
    (unit_dir / "sessionwiki-synth.service").write_text("hand-made\n")
    messages = ci.install_scheduler("systemd", home=tmp_path, python_exe=PY, repo_root=tmp_path)
    assert (unit_dir / "sessionwiki-synth.service").read_text() == "hand-made\n"
    assert any("already installed" in m for m in messages)
    ci.install_scheduler("systemd", home=tmp_path, python_exe=PY, repo_root=tmp_path, force=True)
    assert "claude nightly" in (unit_dir / "sessionwiki-synth.service").read_text()


def test_launchd_plist(tmp_path: Path):
    ci.install_scheduler("launchd", home=tmp_path, python_exe=PY, repo_root=tmp_path, at="4:05")
    plist = (tmp_path / "Library" / "LaunchAgents" / "com.sessionwiki.claude.nightly.plist").read_text()
    assert "<string>nightly</string>" in plist
    assert "<key>SESSIONWIKI_HOME</key>" in plist
    assert "<integer>4</integer>" in plist and "<integer>5</integer>" in plist


def test_windows_task_wrapper(tmp_path: Path):
    messages = ci.install_scheduler("windows", home=tmp_path, python_exe=PY, repo_root=tmp_path)
    script = (tmp_path / ".llmwiki" / "claude" / "nightly.cmd").read_text()
    assert "claude nightly" in script
    assert any("schtasks /Create" in m for m in messages)


def test_bad_time_is_an_error(tmp_path: Path):
    with pytest.raises(ValueError, match="HH:MM"):
        ci.install_scheduler("systemd", home=tmp_path, python_exe=PY, repo_root=tmp_path, at="25:00")


def test_install_all_prints_the_mcp_hint(tmp_path: Path):
    messages = ci.install_all(
        scheduler="none", home=tmp_path, python_exe=PY, repo_root=tmp_path, windows=False,
    )
    assert any(m.startswith("mcp: register with: claude mcp add") for m in messages)


# ─── nightly run ─────────────────────────────────────────────────────


def _record_main(monkeypatch, codes: dict[str, int], *, raw: bool = True) -> list[list[str]]:
    calls: list[list[str]] = []
    monkeypatch.setattr(ci, "_has_raw_sessions", lambda: raw)

    def fake_main(argv):
        calls.append(list(argv))
        return codes.get(argv[0], 0)

    monkeypatch.setattr("sessionwiki.cli.main", fake_main)
    return calls


def test_nightly_runs_sync_synthesize_build(monkeypatch):
    calls = _record_main(monkeypatch, {})
    assert ci.run_nightly() == 0
    assert [c[0] for c in calls] == ["sync", "synthesize", "build"]
    assert "--adapter" in calls[0] and "claude_code" in calls[0]
    assert "--no-auto-build" in calls[0]


def test_nightly_builds_even_when_synthesis_fails(monkeypatch):
    calls = _record_main(monkeypatch, {"synthesize": 1})
    assert ci.run_nightly() == 0
    assert [c[0] for c in calls] == ["sync", "synthesize", "build"]


def test_nightly_reports_a_failed_sync(monkeypatch):
    calls = _record_main(monkeypatch, {"sync": 2})
    assert ci.run_nightly() == 2
    assert [c[0] for c in calls] == ["sync", "synthesize", "build"]


def test_nightly_skips_build_on_an_empty_raw(monkeypatch):
    calls = _record_main(monkeypatch, {}, raw=False)
    assert ci.run_nightly() == 0
    assert [c[0] for c in calls] == ["sync", "synthesize"]


def test_has_raw_sessions(tmp_path: Path, monkeypatch):
    import sessionwiki

    monkeypatch.setattr(sessionwiki, "REPO_ROOT", tmp_path)
    assert ci._has_raw_sessions() is False
    (tmp_path / "raw" / "sessions").mkdir(parents=True)
    assert ci._has_raw_sessions() is False
    (tmp_path / "raw" / "sessions" / "s.md").write_text("x")
    assert ci._has_raw_sessions() is True


def test_nightly_no_build(monkeypatch):
    calls = _record_main(monkeypatch, {})
    ci.run_nightly(build=False)
    assert [c[0] for c in calls] == ["sync", "synthesize"]


# ─── CLI wiring ──────────────────────────────────────────────────────


def test_cli_install_dry_run(tmp_path: Path, monkeypatch, capsys):
    from sessionwiki import cli

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    rc = cli.main(["claude", "install", "--dry-run", "--scheduler", "none"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "would update" in out
    assert not (tmp_path / ".claude").exists()


def test_cli_nightly_calls_run_nightly(monkeypatch):
    from sessionwiki import cli

    seen = {}
    monkeypatch.setattr(ci, "run_nightly", lambda build=True: seen.setdefault("build", build) and 0)
    assert cli.main(["claude", "nightly", "--no-build"]) == 0
    assert seen == {"build": False}
