"""Regenerate the README / docs screenshots in ``docs/images/``.

The screenshots show the public demo, not your own sessions:

  1. Builds the demo site in a temporary directory from the synthetic
     sessions in ``examples/demo-sessions/`` and the project cards in
     ``wiki/projects/`` — exactly what ``.github/workflows/pages.yml``
     deploys to GitHub Pages. Nothing from your ``raw/`` or ``wiki/``
     content is read.
  2. Serves it on 127.0.0.1 and walks the routes in ``ROUTES`` with
     Playwright at 1280×800 in the chosen theme.
  3. Reports which images changed, so the diff is easy to review.

Run locally:

    pip install -e '.[e2e]'
    python -m playwright install chromium      # or: --channel chrome
    python scripts/regen_docs_screenshots.py

``--channel chrome`` drives an installed Google Chrome instead of
Playwright's bundled Chromium (useful where the bundled build is not
supported, e.g. Ubuntu 26.04).

CI: ``.github/workflows/regen-screenshots.yml`` (manual dispatch) runs
this and opens a PR with the changed images.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_IMAGES = REPO_ROOT / "docs" / "images"
DEMO_SESSIONS = REPO_ROOT / "examples" / "demo-sessions"

# (output file, URL path, action). Actions: None, "code" (scroll to the
# first code block), "graph" (expand project clusters), "search" (open
# the Cmd+K palette and type a query). This list is the single source of
# truth for which screenshots the README and docs use.
ROUTES = [
    ("home.png", "/index.html", None),
    ("sessions.png", "/sessions/index.html", None),
    ("session-detail.png", "/sessions/edge-cache/2026-09-10-stale-while-revalidate.html", "code"),
    ("project-detail.png", "/projects/infra-stack.html", None),
    ("projects.png", "/projects/index.html", None),
    ("graph.png", "/graph.html", "graph"),
    ("search.png", "/index.html", "search"),
]


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: D401 - silence request logs
        pass


def build_demo_site(workdir: Path) -> Path:
    """Build the public demo into ``workdir/site`` and return that path.

    Mirrors pages.yml: a copy of the *tracked* files only (so untracked
    personal ``raw/`` and ``wiki/`` content never leaks into a screenshot),
    the demo sessions seeded into ``raw/sessions/``, then ``build`` run
    from that copy so ``sessionwiki`` resolves its root there.
    """
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=str(REPO_ROOT), check=True, capture_output=True
    ).stdout.decode("utf-8").split("\0")
    for rel in filter(None, tracked):
        src = REPO_ROOT / rel
        if src.is_file():
            dst = workdir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    raw = workdir / "raw" / "sessions"
    raw.mkdir(parents=True, exist_ok=True)
    for project in sorted(p for p in DEMO_SESSIONS.iterdir() if p.is_dir()):
        shutil.copytree(project, raw / project.name, dirs_exist_ok=True)
    site = workdir / "site"
    subprocess.run(
        [sys.executable, "-m", "sessionwiki", "build", "--out", str(site)],
        cwd=str(workdir),
        check=True,
    )
    return site


def capture(site: Path, theme: str, channel: str | None) -> dict[str, bool]:
    """Screenshot every route; return {filename: changed?}."""
    from playwright.sync_api import sync_playwright

    DOCS_IMAGES.mkdir(parents=True, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(_QuietHandler, directory=str(site)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    changed: dict[str, bool] = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel=channel) if channel else p.chromium.launch()
            ctx = browser.new_context(viewport={"width": 1280, "height": 800}, color_scheme=theme)
            ctx.add_init_script(
                f"try {{ localStorage.setItem('sessionwiki-theme', {theme!r}); }} catch (e) {{}}"
            )
            page = ctx.new_page()
            for fname, path, action in ROUTES:
                page.goto(base + path, wait_until="networkidle")
                page.wait_for_timeout(400)
                if action == "code":
                    page.evaluate(
                        "(() => { const el = document.querySelector('.content pre, pre');"
                        " if (el) window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - 330); })()"
                    )
                    page.wait_for_timeout(400)
                elif action == "graph":
                    toggle = page.get_by_role("button", name="Cluster")
                    if toggle.count():
                        toggle.first.click()
                    page.wait_for_timeout(3500)  # let the physics settle
                elif action == "search":
                    page.keyboard.press("Control+k")
                    page.wait_for_timeout(300)
                    page.keyboard.type("redis", delay=40)
                    page.wait_for_timeout(700)
                out = DOCS_IMAGES / fname
                before = out.read_bytes() if out.is_file() else b""
                page.screenshot(path=str(out), full_page=False)
                changed[fname] = out.read_bytes() != before
            browser.close()
    finally:
        srv.shutdown()
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate docs/images/*.png from the demo site")
    parser.add_argument("--theme", choices=("light", "dark"), default="dark")
    parser.add_argument("--channel", default=None,
                        help="Playwright browser channel, e.g. 'chrome' to use an installed Google Chrome")
    parser.add_argument("--site", type=Path, default=None,
                        help="Screenshot an already-built site instead of building the demo")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="sessionwiki-demo-") as tmp:
        site = args.site or build_demo_site(Path(tmp))
        result = capture(site, args.theme, args.channel)

    changed = [name for name, diff in result.items() if diff]
    print(f"{'changed' if changed else 'no changes'}: {len(changed)} / kept: {len(result) - len(changed)}")
    for name in changed:
        print(f"  changed: docs/images/{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
