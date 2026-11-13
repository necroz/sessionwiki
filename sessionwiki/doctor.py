"""Install diagnostics: is this checkout usable on this machine?

``sessionwiki doctor`` is deliberately small and dependency-free. It checks
the things that break a fresh install on another machine:

* Python version
* the ``markdown`` runtime dependency
* whether the process runs inside a virtualenv
* which config files are present
* the ZCode database and exported JSONL corpus

Only Python and ``markdown`` are hard failures. Adapter and ZCode
checks are reported so a new user can see what is missing without
guessing.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from sessionwiki import REPO_ROOT, __version__

MIN_PYTHON = (3, 9)


def _check_python() -> dict[str, Any]:
    version = ".".join(str(part) for part in sys.version_info[:3])
    return {
        "ok": sys.version_info[:2] >= MIN_PYTHON,
        "detail": version,
    }


def _check_markdown() -> dict[str, Any]:
    found = importlib.util.find_spec("markdown") is not None
    return {
        "ok": found,
        "detail": "installed" if found else "missing — run: pip install markdown",
    }


def _check_venv() -> dict[str, Any]:
    active = sys.prefix != sys.base_prefix or hasattr(sys, "real_prefix")
    return {
        "ok": active,
        "detail": "active" if active else "not active — scripts fall back to system python3",
    }


def _check_config(repo_root: Path) -> dict[str, Any]:
    candidates = (
        repo_root / "examples" / "sessions_config.json",
        repo_root / "config.json",
        repo_root / "config.local.json",
    )
    present = [path.relative_to(repo_root).as_posix() for path in candidates if path.is_file()]
    return {
        "ok": candidates[0].is_file(),
        "detail": ", ".join(present) if present else "no config files found",
    }


def _check_zcode_db(home: Path) -> dict[str, Any]:
    db = home / ".zcode" / "cli" / "db" / "db.sqlite"
    return {
        "ok": db.is_file(),
        "detail": str(db) if db.is_file() else f"not found: {db}",
    }


def _check_zcode_export(home: Path) -> dict[str, Any]:
    root = home / ".llmwiki" / "zcode"
    sessions = len(list(root.rglob("*.jsonl"))) if root.is_dir() else 0
    return {
        "ok": sessions > 0,
        "detail": (
            f"{sessions} session file(s) in {root}"
            if sessions
            else f"not found: {root}"
        ),
    }


def _check_synthesis(repo_root: Path) -> dict[str, Any]:
    """Raw sessions not synthesized yet, and pages waiting for the agent."""
    from sessionwiki.synth.agent_delegate import is_pending
    from sessionwiki.synth.pipeline import _load_state

    raw_root = repo_root / "raw" / "sessions"
    try:
        state = _load_state(repo_root / ".llmwiki-synth-state.json")
    except OSError as e:
        # A broken install must not turn doctor into a traceback.
        return {
            "ok": False,
            "detail": f"cannot read synthesis state: {e}",
        }
    waiting = 0
    for p in raw_root.rglob("*.md") if raw_root.is_dir() else []:
        # Same skip as _discover_raw_sessions: underscore files are support
        # files, not sessions.
        if p.name.startswith("_"):
            continue
        rel = p.relative_to(raw_root).as_posix()
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        if rel not in state or state[rel] < mtime:
            waiting += 1
    pending = 0
    sources = repo_root / "wiki" / "sources"
    for page in sources.rglob("*.md") if sources.is_dir() else []:
        try:
            with page.open("rb") as f:
                head = f.read(16 * 1024).decode("utf-8", errors="replace")
        except OSError:
            continue
        if is_pending(head):
            pending += 1
    ok = waiting == 0 and pending == 0
    detail = (
        f"{waiting} raw session(s) not synthesized, "
        f"{pending} page(s) waiting for the agent"
    )
    if not ok:
        detail += " — run `sessionwiki synthesize`"
    return {"ok": ok, "detail": detail}


def collect_report(
    repo_root: Path | None = None,
    home: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Return one status entry per check, without printing anything."""
    root = Path(repo_root) if repo_root is not None else Path(REPO_ROOT)
    home_dir = Path(home) if home is not None else Path.home()
    return {
        "python": _check_python(),
        "markdown": _check_markdown(),
        "venv": _check_venv(),
        "config": _check_config(root),
        "zcode_db": _check_zcode_db(home_dir),
        "zcode_export": _check_zcode_export(home_dir),
        "synthesis": _check_synthesis(root),
    }


def cmd_doctor(args: Any = None) -> int:
    """Print the install report and return 1 only for hard failures."""
    report = collect_report()
    print(f"sessionwiki doctor {__version__}")
    print(f"  root: {REPO_ROOT}")
    for name, item in report.items():
        marker = "ok  " if item["ok"] else "warn"
        print(f"  [{marker}] {name:<12} {item['detail']}")
    critical = ("python", "markdown")
    return 0 if all(report[name]["ok"] for name in critical) else 1
