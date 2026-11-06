"""Install ZCode autosync: Stop-hook and native schedulers."""

from __future__ import annotations

import json
from pathlib import Path

from sessionwiki import cli
from sessionwiki.zcode import install


def _hook_config(home: Path) -> Path:
    return home / ".zcode" / "cli" / "config.json"


def test_install_hook_preserves_existing_and_is_idempotent(tmp_path):
    config_path = _hook_config(tmp_path)
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "enabled": False,
                    "events": {
                        "Stop": [
                            {"hooks": [{"type": "command", "command": "echo existing"}]}
                        ]
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    install.install_hook(home=tmp_path, python_exe="/venv/bin/python", repo_root=tmp_path)
    install.install_hook(home=tmp_path, python_exe="/venv/bin/python", repo_root=tmp_path)

    data = json.loads(config_path.read_text(encoding="utf-8"))
    stop = data["hooks"]["events"]["Stop"]
    commands = [hook["command"] for entry in stop for hook in entry["hooks"]]

    assert data["hooks"]["enabled"] is True
    assert len(stop) == 2
    assert sum("zcode autosync" in command for command in commands) == 1


def test_install_hook_dry_run_writes_nothing(tmp_path):
    config_path = _hook_config(tmp_path)

    install.install_hook(
        home=tmp_path,
        python_exe="/venv/bin/python",
        repo_root=tmp_path,
        dry_run=True,
    )

    assert not config_path.exists()


def test_install_systemd_writes_service_and_timer(tmp_path):
    install.install_systemd(
        home=tmp_path,
        python_exe="/venv/bin/python",
        repo_root=tmp_path,
        at="03:30",
        build=True,
    )

    unit_dir = tmp_path / ".config" / "systemd" / "user"
    service = (unit_dir / "sessionwiki-zcode.service").read_text(encoding="utf-8")
    timer = (unit_dir / "sessionwiki-zcode.timer").read_text(encoding="utf-8")

    assert f"WorkingDirectory={tmp_path}" in service
    assert "/venv/bin/python -m sessionwiki zcode autosync --build" in service
    assert "OnCalendar=*-*-* 03:30:00" in timer
    assert "Unit=sessionwiki-zcode.service" in timer


def test_install_launchd_writes_plist(tmp_path):
    path = install.install_launchd(
        home=tmp_path,
        python_exe="/venv/bin/python",
        repo_root=tmp_path,
        at="03:30",
        build=True,
    )

    text = path.read_text(encoding="utf-8")
    assert "com.sessionwiki.zcode.autosync" in text
    assert "<string>/venv/bin/python</string>" in text
    assert "<string>autosync</string>" in text
    assert "<key>Hour</key>" in text
    assert "<integer>3</integer>" in text
    assert "<integer>30</integer>" in text


def test_install_windows_task_writes_cmd_and_prints_schtasks(tmp_path):
    messages = install.install_windows_task(
        home=tmp_path,
        python_exe=r"C:\venv\python.exe",
        repo_root=tmp_path,
        at="03:30",
        build=True,
    )

    cmd = (tmp_path / ".llmwiki" / "zcode" / "autosync.cmd").read_text(
        encoding="utf-8"
    )
    assert "-m sessionwiki zcode autosync --build" in cmd
    assert any("schtasks" in message.lower() for message in messages)


def _schtasks_line(messages: list[str]) -> str:
    return next(message for message in messages if "schtasks" in message.lower())


def test_windows_task_runs_the_wrapper_not_python_directly(tmp_path):
    # The wrapper does `cd /d` and appends to autosync.log; a task that
    # runs python inline loses both.
    messages = install.install_windows_task(
        home=tmp_path, python_exe=r"C:\venv\python.exe", repo_root=tmp_path
    )

    cmd_path = tmp_path / ".llmwiki" / "zcode" / "autosync.cmd"
    line = _schtasks_line(messages)
    assert f'/TR "\\"{cmd_path}\\""' in line
    assert "-m sessionwiki" not in line


def test_windows_task_quotes_paths_with_spaces(tmp_path):
    home = tmp_path / "John Doe"
    messages = install.install_windows_task(
        home=home,
        python_exe=r"C:\Program Files\Python312\python.exe",
        repo_root=tmp_path / "my repo",
    )

    cmd_path = home / ".llmwiki" / "zcode" / "autosync.cmd"
    # schtasks needs the inner quotes escaped as \" inside the /TR value;
    # the old `/TR ""C:\Program Files\..."..."` split into separate args.
    assert f'/TR "\\"{cmd_path}\\""' in _schtasks_line(messages)
    assert '/TR ""' not in _schtasks_line(messages)

    script = cmd_path.read_text(encoding="utf-8")
    assert f'cd /d "{tmp_path / "my repo"}"' in script
    assert '"C:\\Program Files\\Python312\\python.exe" -m sessionwiki' in script


def test_windows_wrapper_escapes_percent_signs(tmp_path):
    # In a .cmd file `%name%` expands as a variable; a literal % must be %%.
    home = tmp_path / "100%home"
    install.install_windows_task(
        home=home, python_exe=r"C:\venv\python.exe", repo_root=tmp_path / "a%b"
    )

    script = (home / ".llmwiki" / "zcode" / "autosync.cmd").read_text(
        encoding="utf-8"
    )
    assert "a%%b" in script
    assert "100%%home" in script
    assert "a%b" not in script.replace("%%", "")


def test_windows_task_dry_run_prints_same_schtasks_and_writes_nothing(tmp_path):
    messages = install.install_windows_task(
        home=tmp_path, python_exe=r"C:\venv\python.exe", repo_root=tmp_path,
        dry_run=True,
    )

    cmd_path = tmp_path / ".llmwiki" / "zcode" / "autosync.cmd"
    assert f'/TR "\\"{cmd_path}\\""' in _schtasks_line(messages)
    assert not cmd_path.exists()


def test_install_dispatch_none_only_installs_hook(tmp_path):
    messages = install.install_all(
        scheduler="none",
        home=tmp_path,
        python_exe="/venv/bin/python",
        repo_root=tmp_path,
    )

    assert _hook_config(tmp_path).exists()
    assert any("hook" in message.lower() for message in messages)


def test_zcode_install_parser_accepts_flags():
    args = cli.build_parser().parse_args(
        ["zcode", "install", "--scheduler", "none", "--dry-run", "--no-hook"]
    )

    assert args.zcode_command == "install"
    assert args.scheduler == "none"
    assert args.dry_run is True
    assert args.no_hook is True

def test_install_hook_can_enable_coalescing(tmp_path):
    install.install_hook(
        home=tmp_path,
        python_exe="/venv/bin/python",
        repo_root=tmp_path,
        coalesce=True,
    )

    data = json.loads(_hook_config(tmp_path).read_text(encoding="utf-8"))
    command = data["hooks"]["events"]["Stop"][0]["hooks"][0]["command"]
    assert "--coalesce" in command


def test_zcode_stop_hook_skips_when_autosync_is_busy(tmp_path):
    # A Stop hook fires after every reply; it must not queue a process
    # that waits 600 s for the lock.
    install.install_hook(home=tmp_path, python_exe="/venv/bin/python")

    data = json.loads(_hook_config(tmp_path).read_text(encoding="utf-8"))
    command = data["hooks"]["events"]["Stop"][-1]["hooks"][0]["command"]
    assert "--lock-timeout 0" in command


def test_scheduled_autosync_still_waits_for_the_lock(tmp_path):
    # The nightly timer is the catch-up run: it should wait, not skip.
    install.install_systemd(home=tmp_path, python_exe="/venv/bin/python", repo_root=tmp_path)

    service = (tmp_path / ".config" / "systemd" / "user" / "sessionwiki-zcode.service").read_text(
        encoding="utf-8"
    )
    assert "--lock-timeout" not in service


def test_install_all_adds_a_session_start_recall_hook(tmp_path):
    """Agents rarely call memory tools themselves; a SessionStart hook
    puts the project's recent sessions into context up front."""
    for _ in range(2):
        install.install_all(
            scheduler="none", home=tmp_path, python_exe="/venv/bin/python", repo_root=tmp_path,
        )
    data = json.loads(_hook_config(tmp_path).read_text(encoding="utf-8"))
    start = data["hooks"]["events"]["SessionStart"]
    commands = [hook["command"] for entry in start for hook in entry["hooks"]]
    assert len(commands) == 1
    assert "sessionwiki recall --format hook" in commands[0]
    assert str(tmp_path) in commands[0]  # data root pinned for the hook


def test_no_hook_skips_the_recall_hook_too(tmp_path):
    install.install_all(
        scheduler="none", home=tmp_path, python_exe="/venv/bin/python",
        repo_root=tmp_path, hook=False,
    )
    assert not _hook_config(tmp_path).exists()


def test_existing_wrapper_script_stop_hook_counts_as_installed(tmp_path):
    """Older setups run scripts/zcode_sync_hook.sh, a wrapper around
    `zcode autosync`. Installing again must not add a second Stop hook
    that syncs after every reply twice."""
    config_path = _hook_config(tmp_path)
    config_path.parent.mkdir(parents=True)
    wrapper = "nohup /repo/scripts/zcode_sync_hook.sh --lock-timeout 0 >/dev/null 2>&1 &"
    config_path.write_text(json.dumps({"hooks": {"enabled": True, "events": {
        "Stop": [{"hooks": [{"type": "command", "command": wrapper}]}],
    }}}), encoding="utf-8")

    messages = install.install_hook(home=tmp_path, python_exe="/venv/bin/python", repo_root=tmp_path)

    stop = json.loads(config_path.read_text(encoding="utf-8"))["hooks"]["events"]["Stop"]
    assert len(stop) == 1
    assert "already installed" in messages[0]


def test_force_replaces_the_wrapper_with_the_direct_command(tmp_path):
    config_path = _hook_config(tmp_path)
    config_path.parent.mkdir(parents=True)
    wrapper = "nohup /repo/scripts/zcode_sync_hook.sh --lock-timeout 0 >/dev/null 2>&1 &"
    config_path.write_text(json.dumps({"hooks": {"enabled": True, "events": {
        "Stop": [{"hooks": [{"type": "command", "command": wrapper}]}],
    }}}), encoding="utf-8")

    install.install_hook(home=tmp_path, python_exe="/venv/bin/python", repo_root=tmp_path, force=True)

    stop = json.loads(config_path.read_text(encoding="utf-8"))["hooks"]["events"]["Stop"]
    commands = [hook["command"] for entry in stop for hook in entry["hooks"]]
    assert len(commands) == 1
    assert "zcode autosync" in commands[0]
