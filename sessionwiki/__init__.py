"""sessionwiki — LLM-powered knowledge base from Claude Code, Codex CLI, Cursor,
Gemini CLI, and Obsidian sessions.

Follows Andrej Karpathy's LLM Wiki pattern:
    https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

Public API:
    - sessionwiki.cli.main()              — the command-line entry point
    - sessionwiki.convert.convert_all()   — .jsonl → markdown
    - sessionwiki.build.build_site()      — markdown → HTML
    - sessionwiki.serve.serve_site()      — local HTTP server
    - sessionwiki.graph.build_and_report() — knowledge graph
    - sessionwiki.exporters.export_all()  — AI-consumable exports
    - sessionwiki.adapters.REGISTRY       — adapter registry
    - sessionwiki.mcp.server.main()       — MCP server (stdio)
"""

__version__ = "2.0.4"
__author__ = "Igor Lashkevich"  # based on llmwiki by Pratiyush (MIT)
__license__ = "MIT"

import os
from pathlib import Path


def _resolve_root(package_file: "str | Path" = __file__) -> Path:
    """Directory that holds raw/, wiki/, site/ and the state files.

    1. ``$SESSIONWIKI_HOME`` (or the legacy ``$LLMWIKI_HOME``) when set.
    2. The source checkout, when the package runs from a clone (``./setup.sh``
       or ``pip install -e``): the parent of ``sessionwiki/`` has
       ``pyproject.toml``.
    3. Otherwise — ``pip install`` / ``uv tool install`` / ``uvx`` / Docker,
       where the parent is ``site-packages`` — the current directory.
    """
    for var in ("SESSIONWIKI_HOME", "LLMWIKI_HOME"):
        value = os.environ.get(var, "").strip()
        if value:
            return Path(value).expanduser().resolve()
    checkout = Path(package_file).resolve().parent.parent
    if (checkout / "pyproject.toml").is_file():
        return checkout
    return Path.cwd().resolve()


# Data root (raw/, wiki/, site/, state files). See _resolve_root().
REPO_ROOT = _resolve_root()
# The installed package itself — use this, not REPO_ROOT, for files that
# ship inside the package (templates, prompts, bundled assets).
PACKAGE_ROOT = Path(__file__).resolve().parent

# #arch-m4 (#617): the docstring above promised a "public API" but
# nothing was actually exported. Wire the listed symbols up as real
# re-exports so `from sessionwiki import build_site` etc. actually works.
# Lazy via __getattr__ so importing sessionwiki itself stays cheap (most
# CLI invocations don't touch the public API surface, just REPO_ROOT).
__all__ = [
    "REPO_ROOT",
    "PACKAGE_ROOT",
    "__version__",
    "main",
    "convert_all",
    "build_site",
    "serve_site",
    "build_and_report",
    "export_all",
    "REGISTRY",
]


def __getattr__(name: str):
    """PEP 562 module-level lazy attribute access.

    Lets `from sessionwiki import build_site` resolve without paying for
    the full transitive import graph at `import sessionwiki` time.
    """
    if name == "main":
        from sessionwiki.cli import main
        return main
    if name == "convert_all":
        from sessionwiki.convert import convert_all
        return convert_all
    if name == "build_site":
        from sessionwiki.build import build_site
        return build_site
    if name == "serve_site":
        from sessionwiki.serve import serve_site
        return serve_site
    if name == "build_and_report":
        from sessionwiki.graph import build_and_report
        return build_and_report
    if name == "export_all":
        from sessionwiki.exporters import export_all
        return export_all
    if name == "REGISTRY":
        from sessionwiki.adapters import REGISTRY
        return REGISTRY
    raise AttributeError(f"module 'sessionwiki' has no attribute {name!r}")
