"""Install ZCode autosync for the current machine.

Two pieces:

* a ZCode ``Stop`` hook, written into ``~/.zcode/cli/config.json``;
* a native scheduler entry — systemd user timer (Linux), launchd agent
  (macOS), or a Task Scheduler command (Windows).

All functions accept ``home`` and ``repo_root`` so tests (and callers
that manage a non-default profile) never touch the real user config.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape as _xml_escape

_AT_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
_SERVICE_NAME = "sessionwiki-zcode.service"
_TIMER_NAME = "sessionwiki-zcode.timer"
_LAUNCHD_LABEL = "com.sessionwiki.zcode.autosync"


def _home(home: Optional[Path]) -> Path:
    return Path(home) if home is not None else Path.home()


def _python(python_exe: Optional[Path | str]) -> str:
    return str(Path(python_exe) if python_exe is not None else Path(sys.executable))


def _at_parts(at: str) -> tuple[int, int]:
    match = _AT_RE.match(str(at).strip())
    if not match:
        raise ValueError(f"invalid --at value: {at!r} (expected HH:MM)")
    return int(match.group(1)), int(match.group(2))


def _autosync_command(python_exe: str, *, build: bool, coalesce: bool = False) -> str:
    executable = f'"{python_exe}"' if " " in python_exe else python_exe
    command = f'{executable} -m sessionwiki zcode autosync'
    if coalesce:
        command += " --coalesce"
    if build:
        command += " --build"
    return command


def _cmd_escape(text: str) -> str:
    """Escape ``%`` for a .cmd file, where ``%name%`` expands as a variable."""
    return text.replace("%", "%%")


def _hook_command(
    python_exe: str, *, build: bool, coalesce: bool = False
) -> str:
    # The Stop hook fires after every reply. --lock-timeout 0 skips when a
    # cycle is already running instead of queueing a process that waits up
    # to 600 s; the nightly timer (no flag) is the run that waits.
    base = (
        _autosync_command(python_exe, build=build, coalesce=coalesce)
        + " --lock-timeout 0"
    )
    if os.name == "nt":
        return f'start "" /B {base}'
    return f'nohup {base} >/dev/null 2>&1 &'


def _entry_has_autosync(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    hooks = entry.get("hooks")
    if not isinstance(hooks, list):
        return False
    return any(
        isinstance(hook, dict)
        and any(marker in str(hook.get("command", "")) for marker in _AUTOSYNC_MARKERS)
        for hook in hooks
    )


# A Stop hook runs autosync either directly or through the POSIX wrapper
# older setups installed (scripts/zcode_sync_hook.sh calls `zcode
# autosync`). Both count, or a reinstall adds a second hook that syncs
# twice after every reply.
_AUTOSYNC_MARKERS = ("zcode autosync", "zcode_sync_hook.sh")


def _contains_autosync(entries: list) -> bool:
    return any(_entry_has_autosync(entry) for entry in entries)


def install_hook(
    *,
    home: Optional[Path] = None,
    python_exe: Optional[Path | str] = None,
    repo_root: Optional[Path] = None,
    build: bool = False,
    coalesce: bool = False,
    dry_run: bool = False,
    force: bool = False,
) -> list[str]:
    """Add a ZCode ``Stop`` hook that runs autosync. Idempotent."""
    home_dir = _home(home)
    py = _python(python_exe)
    path = home_dir / ".zcode" / "cli" / "config.json"

    data: dict = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read {path}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ValueError(f"{path} must contain a JSON object")
        data = loaded

    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError(f"{path}: 'hooks' must be an object")
    events = hooks.setdefault("events", {})
    if not isinstance(events, dict):
        raise ValueError(f"{path}: 'hooks.events' must be an object")
    stop = events.setdefault("Stop", [])
    if not isinstance(stop, list):
        raise ValueError(f"{path}: 'hooks.events.Stop' must be a list")

    command = _hook_command(py, build=build, coalesce=coalesce)
    if _contains_autosync(stop):
        if not force:
            return [f"hook: already installed in {path}"]
        stop[:] = [entry for entry in stop if not _entry_has_autosync(entry)]
    hooks["enabled"] = True
    stop.append(
        {
            "hooks": [
                {
                    "type": "command",
                    "command": command,
                    "timeout": 10,
                }
            ]
        }
    )

    if dry_run:
        return [f"hook: would update {path}"]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return [f"hook: installed in {path}"]


def _recall_command(python_exe: str, repo_root: Path | None) -> str:
    executable = f'"{python_exe}"' if " " in python_exe else python_exe
    command = f"{executable} -m sessionwiki recall --format hook"
    if repo_root is None:
        return command
    # The hook runs in the project folder; pin the data root explicitly.
    if os.name == "nt":
        return f'set "SESSIONWIKI_HOME={repo_root}" && {command}'
    return f'SESSIONWIKI_HOME="{repo_root}" {command}'


def install_recall_hook(
    *,
    home: Path | None = None,
    python_exe: Path | str | None = None,
    repo_root: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> list[str]:
    """Add a ZCode ``SessionStart`` hook that prints the project's recent
    sessions (``sessionwiki recall``) into the new session's context.
    Agents rarely call memory tools on their own. Idempotent."""
    path = _home(home) / ".zcode" / "cli" / "config.json"
    data: dict = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read {path}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ValueError(f"{path} must contain a JSON object")
        data = loaded
    hooks = data.setdefault("hooks", {})
    events = hooks.setdefault("events", {}) if isinstance(hooks, dict) else None
    start = events.setdefault("SessionStart", []) if isinstance(events, dict) else None
    if not isinstance(start, list):
        raise ValueError(f"{path}: 'hooks.events.SessionStart' must be a list")

    def _is_recall(entry: object) -> bool:
        return isinstance(entry, dict) and any(
            isinstance(h, dict) and "sessionwiki recall" in str(h.get("command", ""))
            for h in entry.get("hooks", []) or []
        )

    if any(_is_recall(entry) for entry in start):
        if not force:
            return [f"recall hook: already installed in {path}"]
        start[:] = [entry for entry in start if not _is_recall(entry)]
    hooks["enabled"] = True
    start.append({"hooks": [{
        "type": "command",
        "command": _recall_command(_python(python_exe), repo_root),
        "timeout": 10,
    }]})
    if dry_run:
        return [f"recall hook: would update {path}"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return [f"recall hook: installed in {path}"]


def install_systemd(
    *,
    home: Optional[Path] = None,
    python_exe: Optional[Path | str] = None,
    repo_root: Optional[Path] = None,
    at: str = "03:30",
    build: bool = True,
    coalesce: bool = False,
    dry_run: bool = False,
) -> list[str]:
    """Write a systemd --user service and timer (does not enable them)."""
    hour, minute = _at_parts(at)
    home_dir = _home(home)
    py = _python(python_exe)
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    unit_dir = home_dir / ".config" / "systemd" / "user"
    service_path = unit_dir / _SERVICE_NAME
    timer_path = unit_dir / _TIMER_NAME

    service = (
        "[Unit]\n"
        "Description=Export ZCode sessions and sync sessionwiki\n"
        "After=default.target\n\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"WorkingDirectory={root}\n"
        f"ExecStart={_autosync_command(py, build=build, coalesce=coalesce)}\n"
        "Nice=10\n"
    )
    timer = (
        "[Unit]\n"
        "Description=Nightly sessionwiki ZCode sync\n\n"
        "[Timer]\n"
        f"Unit={_SERVICE_NAME}\n"
        f"OnCalendar=*-*-* {hour:02d}:{minute:02d}:00\n"
        "Persistent=true\n"
        "RandomizedDelaySec=300\n\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )

    if dry_run:
        return [
            f"systemd: would write {service_path}",
            f"systemd: would write {timer_path}",
        ]

    unit_dir.mkdir(parents=True, exist_ok=True)
    service_path.write_text(service, encoding="utf-8")
    timer_path.write_text(timer, encoding="utf-8")
    return [
        f"systemd: wrote {service_path}",
        f"systemd: wrote {timer_path}",
        "systemd: enable with: systemctl --user daemon-reload && "
        f"systemctl --user enable --now {_TIMER_NAME}",
    ]


def install_launchd(
    *,
    home: Optional[Path] = None,
    python_exe: Optional[Path | str] = None,
    repo_root: Optional[Path] = None,
    at: str = "03:30",
    build: bool = True,
    coalesce: bool = False,
    dry_run: bool = False,
) -> Path:
    """Write a launchd agent plist and return its path."""
    hour, minute = _at_parts(at)
    home_dir = _home(home)
    py = _python(python_exe)
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    plist_path = home_dir / "Library" / "LaunchAgents" / f"{_LAUNCHD_LABEL}.plist"
    log_dir = home_dir / ".llmwiki" / "zcode"
    program = [py, "-m", "sessionwiki", "zcode", "autosync"]
    if coalesce:
        program.append("--coalesce")
    if build:
        program.append("--build")
    args_xml = "\n".join(f"    <string>{_xml_escape(arg)}</string>" for arg in program)
    plist = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        f"  <key>Label</key>\n  <string>{_LAUNCHD_LABEL}</string>\n"
        "  <key>ProgramArguments</key>\n"
        "  <array>\n"
        f"{args_xml}\n"
        "  </array>\n"
        f"  <key>WorkingDirectory</key>\n  <string>{_xml_escape(str(root))}</string>\n"
        f"  <key>StandardOutPath</key>\n  <string>{_xml_escape(str(log_dir / 'autosync.log'))}</string>\n"
        f"  <key>StandardErrorPath</key>\n  <string>{_xml_escape(str(log_dir / 'autosync.log'))}</string>\n"
        "  <key>StartCalendarInterval</key>\n"
        "  <dict>\n"
        f"    <key>Hour</key>\n    <integer>{hour}</integer>\n"
        f"    <key>Minute</key>\n    <integer>{minute}</integer>\n"
        "  </dict>\n"
        "  <key>RunAtLoad</key>\n  <false/>\n"
        "</dict>\n"
        "</plist>\n"
    )
    if dry_run:
        return plist_path
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    plist_path.write_text(plist, encoding="utf-8")
    return plist_path


def install_windows_task(
    *,
    home: Optional[Path] = None,
    python_exe: Optional[Path | str] = None,
    repo_root: Optional[Path] = None,
    at: str = "03:30",
    build: bool = True,
    coalesce: bool = False,
    dry_run: bool = False,
) -> list[str]:
    """Write a .cmd wrapper and print the schtasks command."""
    hour, minute = _at_parts(at)
    home_dir = _home(home)
    py = _python(python_exe)
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    output_dir = home_dir / ".llmwiki" / "zcode"
    cmd_path = output_dir / "autosync.cmd"
    log_path = output_dir / "autosync.log"
    command = _autosync_command(py, build=build, coalesce=coalesce)
    script = (
        "@echo off\r\n"
        f'cd /d "{_cmd_escape(str(root))}"\r\n'
        f'{_cmd_escape(command)} >> "{_cmd_escape(str(log_path))}" 2>&1\r\n'
    )
    # The task runs the wrapper, not python: the wrapper sets the working
    # directory and appends to the log. Inside the /TR value schtasks
    # wants inner quotes escaped as \" — so a path with spaces
    # (C:\Users\John Doe\...) stays one argument.
    task_command = (
        f'schtasks /Create /F /SC DAILY /ST {hour:02d}:{minute:02d} '
        f'/TN "sessionwiki-zcode-autosync" /TR "\\"{cmd_path}\\""'
    )
    if dry_run:
        return [f"windows: would write {cmd_path}", f"windows: {task_command}"]
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd_path.write_text(script, encoding="utf-8")
    return [f"windows: wrote {cmd_path}", f"windows: run: {task_command}"]


def detect_scheduler() -> str:
    """Best-effort native scheduler for this OS."""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "launchd"
    if sys.platform.startswith("linux") and shutil.which("systemctl"):
        return "systemd"
    return "none"


def install_all(
    *,
    scheduler: str = "auto",
    home: Optional[Path] = None,
    python_exe: Optional[Path | str] = None,
    repo_root: Optional[Path] = None,
    at: str = "03:30",
    build: bool = True,
    coalesce: bool = False,
    hook: bool = True,
    dry_run: bool = False,
    force: bool = False,
) -> list[str]:
    """Install the Stop-hook and one native scheduler entry."""
    chosen = detect_scheduler() if scheduler == "auto" else scheduler
    if chosen not in {"systemd", "launchd", "windows", "none"}:
        raise ValueError(f"unknown scheduler: {scheduler!r}")

    messages: list[str] = []
    if hook:
        messages.extend(
            install_hook(
                home=home,
                python_exe=python_exe,
                repo_root=repo_root,
                build=build,
                coalesce=coalesce,
                dry_run=dry_run,
                force=force,
            )
        )
        messages.extend(
            install_recall_hook(
                home=home,
                python_exe=python_exe,
                repo_root=repo_root,
                dry_run=dry_run,
                force=force,
            )
        )
    if chosen == "systemd":
        messages.extend(
            install_systemd(
                home=home,
                python_exe=python_exe,
                repo_root=repo_root,
                at=at,
                build=build,
                coalesce=coalesce,
                dry_run=dry_run,
            )
        )
    elif chosen == "launchd":
        path = install_launchd(
            home=home,
            python_exe=python_exe,
            repo_root=repo_root,
            at=at,
            build=build,
            coalesce=coalesce,
            dry_run=dry_run,
        )
        verb = "would write" if dry_run else "wrote"
        messages.append(f"launchd: {verb} {path}")
        messages.append(f"launchd: load with: launchctl load {path}")
    elif chosen == "windows":
        messages.extend(
            install_windows_task(
                home=home,
                python_exe=python_exe,
                repo_root=repo_root,
                at=at,
                build=build,
                coalesce=coalesce,
                dry_run=dry_run,
            )
        )
    else:
        messages.append("scheduler: none selected")
    return messages