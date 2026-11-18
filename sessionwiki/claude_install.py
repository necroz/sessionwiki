"""Install the Claude Code side of sessionwiki on this machine.

Three pieces, each skipped when it is already there:

* a ``Stop`` hook in Claude Code's ``settings.json`` that imports new
  Claude Code sessions into ``raw/`` in the background after every reply;
* a ``SessionStart`` hook that puts the project's recent sessions into
  the new session's context (``sessionwiki recall``);
* a nightly scheduler entry — systemd user timer (Linux), launchd agent
  (macOS) or a Task Scheduler wrapper (Windows) — that runs
  ``sessionwiki claude nightly``: sync, then synthesize every new raw
  session from any agent into wiki pages, then build the site.

Without the nightly job only ``raw/`` grows: the ZCode and OpenCode
autosync jobs coalesce but do not synthesize, so ``wiki/sources/`` stays
empty on a new machine.

Every function takes ``home`` and ``repo_root`` so tests never touch the
real user config. Scheduling helpers come from the ZCode installer.
"""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape as _xml_escape

from sessionwiki.lock import atomic_write_text
from sessionwiki.zcode.install import (
    _at_parts, _catch_up_command, _cmd_escape, _home, _python, detect_scheduler,
)

_SERVICE_NAME = "sessionwiki-synth.service"
_TIMER_NAME = "sessionwiki-synth.timer"
_LAUNCHD_LABEL = "com.sessionwiki.claude.nightly"
_WINDOWS_TASK = "sessionwiki-claude-nightly"

# A hook counts as ours when its command runs one of these, however it was
# written (by this installer, by hand from the README, by an older setup).
_SYNC_MARKER = "sessionwiki sync"
_RECALL_MARKER = "sessionwiki recall --format hook"

_SYNC_ARGS = [
    "sync", "--adapter", "claude_code",
    "--no-zcode-export", "--no-opencode-export", "--no-auto-build",
]


def settings_path(home: Optional[Path] = None) -> Path:
    """Claude Code's user settings file; honours ``$CLAUDE_CONFIG_DIR``."""
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    base = Path(config_dir).expanduser() if config_dir else _home(home) / ".claude"
    return base / "settings.json"


def _is_windows(windows: Optional[bool]) -> bool:
    return os.name == "nt" if windows is None else windows


def _load_settings(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _event_entries(data: dict, path: Path, event: str) -> list:
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError(f"{path}: 'hooks' must be an object")
    entries = hooks.setdefault(event, [])
    if not isinstance(entries, list):
        raise ValueError(f"{path}: 'hooks.{event}' must be a list")
    return entries


def _entry_has(entry: object, marker: str) -> bool:
    return isinstance(entry, dict) and any(
        isinstance(hook, dict) and marker in str(hook.get("command", ""))
        for hook in entry.get("hooks", []) or []
    )


def _sync_hook_command(py: str, root: Path, home_dir: Path) -> str:
    # Background run: the hook must not hold up the reply. sync takes an OS
    # file lock, so overlapping runs wait for each other instead of racing.
    log = home_dir / ".llmwiki" / "logs" / "claude-sync.log"
    args = " ".join(_SYNC_ARGS)
    return (
        f"cd {shlex.quote(str(root))} && "
        f"SESSIONWIKI_HOME={shlex.quote(str(root))} "
        f"nohup {shlex.quote(py)} -m sessionwiki {args} "
        f">>{shlex.quote(str(log))} 2>&1 &"
    )


def _recall_hook_command(py: str, root: Path, windows: bool) -> str:
    if windows:
        # `cd "dir" && cmd` reads the same in cmd.exe and Git Bash; from the
        # data root, a checkout or a pip install both resolve it.
        return f'cd "{root}" && "{py}" -m sessionwiki recall --format hook'
    return (
        f"SESSIONWIKI_HOME={shlex.quote(str(root))} "
        f"{shlex.quote(py)} -m sessionwiki recall --format hook"
    )


def _add_hook(
    data: dict, path: Path, event: str, marker: str, command: str,
    *, timeout: int, force: bool, label: str, dry_run: bool,
) -> tuple[bool, str]:
    """Add one hook entry; returns (changed, message)."""
    entries = _event_entries(data, path, event)
    if any(_entry_has(entry, marker) for entry in entries):
        if not force:
            return False, f"{label}: already installed in {path}"
        entries[:] = [entry for entry in entries if not _entry_has(entry, marker)]
    entries.append({"hooks": [{"type": "command", "command": command, "timeout": timeout}]})
    verb = "would update" if dry_run else "installed in"
    return True, f"{label}: {verb} {path}"


def install_hooks(
    *,
    home: Optional[Path] = None,
    python_exe: Optional[Path | str] = None,
    repo_root: Optional[Path] = None,
    windows: Optional[bool] = None,
    dry_run: bool = False,
    force: bool = False,
) -> list[str]:
    """Add the Stop (sync) and SessionStart (recall) hooks. Idempotent.

    On Windows the Stop hook is skipped: a background launch that works in
    both cmd.exe and Git Bash does not exist, and a foreground sync would
    hold up every reply. The nightly task imports the sessions there.
    """
    home_dir = _home(home)
    py = _python(python_exe)
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    on_windows = _is_windows(windows)
    path = settings_path(home)
    data = _load_settings(path)

    messages: list[str] = []
    changed = False
    if on_windows:
        messages.append("Stop hook: skipped on Windows; the nightly task imports new sessions")
    else:
        did, message = _add_hook(
            data, path, "Stop", _SYNC_MARKER, _sync_hook_command(py, root, home_dir),
            timeout=10, force=force, label="Stop hook (sync)", dry_run=dry_run,
        )
        changed |= did
        messages.append(message)
    did, message = _add_hook(
        data, path, "SessionStart", _RECALL_MARKER, _recall_hook_command(py, root, on_windows),
        timeout=30, force=force, label="SessionStart hook (recall)", dry_run=dry_run,
    )
    changed |= did
    messages.append(message)

    if changed and not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        (home_dir / ".llmwiki" / "logs").mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return messages


def _systemd_word(text: str) -> str:
    """Quote one ExecStart word for systemd when it holds a space."""
    return f'"{text}"' if " " in text else text


def _write_new(paths_and_text: list[tuple[Path, str]], *, label: str, force: bool, dry_run: bool) -> list[str]:
    existing = [p for p, _ in paths_and_text if p.exists()]
    if existing and not force:
        return [f"{label}: already installed ({existing[0]}); --force replaces it"]
    if dry_run:
        return [f"{label}: would write {p}" for p, _ in paths_and_text]
    for p, text in paths_and_text:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return [f"{label}: wrote {p}" for p, _ in paths_and_text]


def install_scheduler(
    scheduler: str,
    *,
    home: Optional[Path] = None,
    python_exe: Optional[Path | str] = None,
    repo_root: Optional[Path] = None,
    at: str = "04:15",
    build: bool = True,
    dry_run: bool = False,
    force: bool = False,
) -> list[str]:
    """Write the nightly ``sessionwiki claude nightly`` job. Does not enable it."""
    hour, minute = _at_parts(at)
    home_dir = _home(home)
    py = _python(python_exe)
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    nightly = ["-m", "sessionwiki", "claude", "nightly"] + ([] if build else ["--no-build"])

    if scheduler == "systemd":
        unit_dir = home_dir / ".config" / "systemd" / "user"
        service = (
            "[Unit]\n"
            "Description=sessionwiki: import Claude Code sessions, synthesize wiki pages, build\n"
            "After=default.target\n\n"
            "[Service]\n"
            "Type=oneshot\n"
            f"WorkingDirectory={root}\n"
            f"Environment=SESSIONWIKI_HOME={root}\n"
            f"ExecStart={' '.join(_systemd_word(w) for w in [py, *nightly])}\n"
            "Nice=10\n"
        )
        timer = (
            "[Unit]\n"
            "Description=Nightly sessionwiki synthesis\n\n"
            "[Timer]\n"
            f"Unit={_SERVICE_NAME}\n"
            f"OnCalendar=*-*-* {hour:02d}:{minute:02d}:00\n"
            "Persistent=true\n"
            "RandomizedDelaySec=300\n\n"
            "[Install]\n"
            "WantedBy=timers.target\n"
        )
        messages = _write_new(
            [(unit_dir / _SERVICE_NAME, service), (unit_dir / _TIMER_NAME, timer)],
            label="systemd", force=force, dry_run=dry_run,
        )
        if any("wrote" in m for m in messages):
            messages.append(
                "systemd: enable with: systemctl --user daemon-reload && "
                f"systemctl --user enable --now {_TIMER_NAME}"
            )
        return messages

    if scheduler == "launchd":
        plist_path = home_dir / "Library" / "LaunchAgents" / f"{_LAUNCHD_LABEL}.plist"
        log = home_dir / ".llmwiki" / "claude" / "nightly.log"
        args_xml = "\n".join(f"    <string>{_xml_escape(a)}</string>" for a in [py, *nightly])
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
            "  <key>EnvironmentVariables</key>\n"
            "  <dict>\n"
            f"    <key>SESSIONWIKI_HOME</key>\n    <string>{_xml_escape(str(root))}</string>\n"
            "  </dict>\n"
            f"  <key>WorkingDirectory</key>\n  <string>{_xml_escape(str(root))}</string>\n"
            f"  <key>StandardOutPath</key>\n  <string>{_xml_escape(str(log))}</string>\n"
            f"  <key>StandardErrorPath</key>\n  <string>{_xml_escape(str(log))}</string>\n"
            "  <key>StartCalendarInterval</key>\n"
            "  <dict>\n"
            f"    <key>Hour</key>\n    <integer>{hour}</integer>\n"
            f"    <key>Minute</key>\n    <integer>{minute}</integer>\n"
            "  </dict>\n"
            # Catch up after a night with the Mac off: launchd only replays a
            # run missed during sleep. synthesize skips known sessions, so an
            # extra run at login is cheap.
            "  <key>RunAtLoad</key>\n  <true/>\n"
            "</dict>\n"
            "</plist>\n"
        )
        messages = _write_new([(plist_path, plist)], label="launchd", force=force, dry_run=dry_run)
        if any("wrote" in m for m in messages):
            log.parent.mkdir(parents=True, exist_ok=True)
            messages.append(f"launchd: load with: launchctl load {plist_path}")
        return messages

    if scheduler == "windows":
        out_dir = home_dir / ".llmwiki" / "claude"
        cmd_path = out_dir / "nightly.cmd"
        log = out_dir / "nightly.log"
        command = " ".join(f'"{w}"' if " " in w else w for w in [py, *nightly])
        script = (
            "@echo off\r\n"
            f'cd /d "{_cmd_escape(str(root))}"\r\n'
            f'set "SESSIONWIKI_HOME={_cmd_escape(str(root))}"\r\n'
            f'{_cmd_escape(command)} >> "{_cmd_escape(str(log))}" 2>&1\r\n'
        )
        task = (
            f"schtasks /Create /F /SC DAILY /ST {hour:02d}:{minute:02d} "
            f'/TN "{_WINDOWS_TASK}" /TR "\\"{cmd_path}\\""'
        )
        messages = _write_new([(cmd_path, script)], label="windows", force=force, dry_run=dry_run)
        messages.append(f"windows: register with: {task}")
        messages.append(
            "windows: then let a missed run start at the next boot: "
            + _catch_up_command(_WINDOWS_TASK)
        )
        return messages

    if scheduler == "none":
        return ["scheduler: none selected; run `sessionwiki claude nightly` yourself"]
    raise ValueError(f"unknown scheduler: {scheduler!r}")


def _mcp_hint(py: str, root: Path) -> str:
    return (
        "mcp: register with: claude mcp add -s user "
        f"-e SESSIONWIKI_HOME={shlex.quote(str(root))} sessionwiki -- "
        f"{shlex.quote(py)} -m sessionwiki mcp"
    )


def install_all(
    *,
    scheduler: str = "auto",
    home: Optional[Path] = None,
    python_exe: Optional[Path | str] = None,
    repo_root: Optional[Path] = None,
    at: str = "04:15",
    build: bool = True,
    hooks: bool = True,
    windows: Optional[bool] = None,
    dry_run: bool = False,
    force: bool = False,
) -> list[str]:
    """Install the hooks and the nightly job; end with the MCP hint."""
    chosen = detect_scheduler() if scheduler == "auto" else scheduler
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    messages: list[str] = []
    if hooks:
        messages += install_hooks(
            home=home, python_exe=python_exe, repo_root=root,
            windows=windows, dry_run=dry_run, force=force,
        )
    messages += install_scheduler(
        chosen, home=home, python_exe=python_exe, repo_root=root,
        at=at, build=build, dry_run=dry_run, force=force,
    )
    messages.append(_mcp_hint(_python(python_exe), root))
    return messages


def _has_raw_sessions() -> bool:
    from sessionwiki import REPO_ROOT

    raw = REPO_ROOT / "raw" / "sessions"
    return raw.is_dir() and next(raw.rglob("*.md"), None) is not None


def run_nightly(*, build: bool = True) -> int:
    """Import Claude Code sessions, synthesize new raw sessions, build.

    A failed synthesis (an unreachable LLM backend, say) does not stop the
    build: the pages that exist still get published. The exit code reports
    a failed sync or build.
    """
    from sessionwiki import cli

    steps: list[tuple[list[str], bool]] = [(_SYNC_ARGS, True), (["synthesize"], False)]
    if build:
        steps.append((["build"], True))
    rc = 0
    for argv, counts in steps:
        if argv[0] == "build" and not _has_raw_sessions():
            # A new machine before its first session: build exits 2 on an
            # empty raw/, which would mark every nightly run as failed.
            print("claude nightly: build skipped, raw/sessions/ is empty", flush=True)
            continue
        code = cli.main(list(argv))
        print(f"claude nightly: {argv[0]} exited {code}", flush=True)
        if counts and code and not rc:
            rc = int(code)
    return rc
