"""Where sessionwiki keeps raw/, wiki/ and site/.

Before 2.0.1 the root was always the parent of the package directory.
That is right for a git clone, but for `pip install` / `uv tool install`
/ Docker it is `site-packages`, so `sessionwiki init` scaffolded raw/,
wiki/ and site/ inside the virtualenv (or failed on a read-only image).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from sessionwiki import _resolve_root

CHECKOUT = Path(__file__).resolve().parent.parent


def _clear(monkeypatch):
    monkeypatch.delenv("SESSIONWIKI_HOME", raising=False)
    monkeypatch.delenv("LLMWIKI_HOME", raising=False)


def test_source_checkout_is_the_root(monkeypatch, tmp_path):
    _clear(monkeypatch)
    monkeypatch.chdir(tmp_path)
    pkg = CHECKOUT / "sessionwiki" / "__init__.py"
    assert _resolve_root(pkg) == CHECKOUT


def test_installed_package_uses_the_current_directory(monkeypatch, tmp_path):
    _clear(monkeypatch)
    site_packages = tmp_path / "venv" / "lib" / "site-packages"
    pkg = site_packages / "sessionwiki" / "__init__.py"
    pkg.parent.mkdir(parents=True)
    pkg.write_text("", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    assert _resolve_root(pkg) == work.resolve()


@pytest.mark.parametrize("var", ["SESSIONWIKI_HOME", "LLMWIKI_HOME"])
def test_environment_variable_wins(monkeypatch, tmp_path, var):
    _clear(monkeypatch)
    home = tmp_path / "my-wiki"
    monkeypatch.setenv(var, str(home))
    assert _resolve_root(CHECKOUT / "sessionwiki" / "__init__.py") == home.resolve()


def test_sessionwiki_home_beats_legacy_name(monkeypatch, tmp_path):
    monkeypatch.setenv("SESSIONWIKI_HOME", str(tmp_path / "new"))
    monkeypatch.setenv("LLMWIKI_HOME", str(tmp_path / "old"))
    assert _resolve_root(CHECKOUT / "sessionwiki" / "__init__.py") == (tmp_path / "new").resolve()


def test_blank_environment_variable_is_ignored(monkeypatch, tmp_path):
    _clear(monkeypatch)
    monkeypatch.setenv("SESSIONWIKI_HOME", "   ")
    assert _resolve_root(CHECKOUT / "sessionwiki" / "__init__.py") == CHECKOUT


def test_init_from_an_installed_copy_writes_into_the_working_directory(tmp_path):
    """End-to-end: a copy of the package outside any checkout (like
    site-packages) must scaffold into the current directory."""
    site_packages = tmp_path / "site-packages"
    subprocess.run(
        [sys.executable, "-c",
         "import shutil, sys; shutil.copytree(sys.argv[1], sys.argv[2], "
         "ignore=shutil.ignore_patterns('__pycache__'))",
         str(CHECKOUT / "sessionwiki"), str(site_packages / "sessionwiki")],
        check=True,
    )
    work = tmp_path / "work"
    work.mkdir()
    env = {k: v for k, v in os.environ.items() if k not in {"SESSIONWIKI_HOME", "LLMWIKI_HOME"}}
    env["PYTHONPATH"] = str(site_packages)
    env["HOME"] = str(tmp_path / "home")
    proc = subprocess.run(
        [sys.executable, "-m", "sessionwiki", "init"],
        cwd=str(work), env=env, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr[-500:]
    assert (work / "raw").is_dir() and (work / "wiki").is_dir()
    assert not (site_packages / "raw").exists()
    assert not (site_packages / "wiki").exists()
