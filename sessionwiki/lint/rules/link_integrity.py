"""link_integrity — [[wikilinks]] must resolve to existing pages."""

from __future__ import annotations

from sessionwiki.lint import LintRule, WIKILINK_RE, register
from sessionwiki.lint.rules._helpers import _page_slug


@register
class LinkIntegrity(LintRule):
    """[[wikilinks]] must resolve to existing pages."""

    name = "link_integrity"
    severity = "warning"
    auto_fixable = True

    def run(self, pages, *, llm_callback=None):
        # Build set of known page slugs. Archived pages are not loaded as
        # pages, but a link to one is valid.
        slugs = {_page_slug(rel) for rel in pages}
        slugs |= getattr(pages, "archived_slugs", set())
        issues = []
        for rel, page in pages.items():
            for target in set(WIKILINK_RE.findall(page["body"])):
                # Strip any embedded section anchors
                t = target.split("#")[0].strip()
                if not t:
                    continue
                if t not in slugs:
                    issues.append({
                        "rule": self.name,
                        "severity": "warning",
                        "page": rel,
                        "message": f"broken wikilink [[{target}]]",
                    })
        return issues
