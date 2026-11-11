"""frontmatter_validity — frontmatter values must have valid types/enum values."""

from __future__ import annotations

from sessionwiki.lifecycle import LifecycleState
from sessionwiki.lint import LintRule, register
from sessionwiki.schema import ENTITY_TYPES


@register
class FrontmatterValidity(LintRule):
    """Frontmatter values must have valid types/enum values."""

    name = "frontmatter_validity"
    severity = "error"

    VALID_TYPES = {"source", "entity", "concept", "synthesis",
                   "comparison", "question", "navigation", "context", "note",
                   "lesson"}
    VALID_LIFECYCLES = {s.value for s in LifecycleState}

    def run(self, pages, *, llm_callback=None):
        issues = []
        for rel, page in pages.items():
            meta = page["meta"]

            t = meta.get("type", "").lower()
            if t and t not in self.VALID_TYPES:
                issues.append({
                    "rule": self.name,
                    "severity": "error",
                    "page": rel,
                    "message": f"invalid type {t!r} (expected one of {sorted(self.VALID_TYPES)})",
                })

            lc = meta.get("lifecycle", "").lower()
            if lc and lc not in self.VALID_LIFECYCLES:
                issues.append({
                    "rule": self.name,
                    "severity": "error",
                    "page": rel,
                    "message": f"invalid lifecycle {lc!r} (expected one of {sorted(self.VALID_LIFECYCLES)})",
                })

            et = meta.get("entity_type", "").lower()
            if et and et not in ENTITY_TYPES:
                issues.append({
                    "rule": self.name,
                    "severity": "error",
                    "page": rel,
                    "message": f"invalid entity_type {et!r} (expected one of {list(ENTITY_TYPES)})",
                })

            issues += self._confidence_issues(meta, rel)
        return issues

    def _confidence_issues(self, meta: dict, rel: str) -> list[dict]:
        """A confidence must be a number in range and carry provenance."""
        conf = meta.get("confidence", "")
        if not conf:
            return []
        try:
            c = float(conf)
        except (ValueError, TypeError):
            return [{
                "rule": self.name, "severity": "error", "page": rel,
                "message": f"confidence not numeric: {conf!r}",
            }]
        if not (0.0 <= c <= 1.0):
            return [{
                "rule": self.name, "severity": "error", "page": rel,
                "message": f"confidence {c} out of range [0.0, 1.0]",
            }]
        if not meta.get("confidence_measured"):
            return [{
                "rule": self.name, "severity": "warning", "page": rel,
                "message": "confidence without provenance: stamp "
                           "confidence_measured and confidence_pages "
                           "when scoring",
            }]
        return []
