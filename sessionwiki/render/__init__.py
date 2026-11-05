"""Static-site render modules (v1.1 · #217).

Split out of the monolithic ``sessionwiki/build.py`` (3,378 → ~1,740 lines)
so CSS + JS constants live in dedicated files.

Public API stays intact: ``sessionwiki.build.build_site`` still works
exactly as before. Build output is byte-identical (verified via hash).

Current modules:
  - ``css.py`` — the inline CSS constant (~670 lines)
  - ``js.py``  — the inline client-side JS constant (~970 lines)

Future phases may extract ``html_page.py`` (render_session, etc.)
and ``search_index.py`` (build_search_index + enrichment glue).
"""

from sessionwiki.render.css import CSS
from sessionwiki.render.js import JS

__all__ = ["CSS", "JS"]
