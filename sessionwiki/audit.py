"""Pre-publish privacy audit for raw/, wiki/, and site/.

The converter redacts known secrets at ingest time, but generated pages
and tool output can still contain a username, a home path, or a token
that appeared after redaction. This command is a read-only second look:

    sessionwiki audit
    sessionwiki audit --path site --json
    sessionwiki audit --fail-on-findings

It never edits files. Exit code is 1 only with ``--fail-on-findings``.
"""

from __future__ import annotations

import json
import os
import re
from itertools import islice
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from sessionwiki import REPO_ROOT
from sessionwiki.config import resolve_config
from sessionwiki.convert import _DEFAULT_TOKEN_PATTERNS

DEFAULT_RELATIVE_PATHS = ("raw", "wiki", "site")
TEXT_EXTENSIONS = {
    ".md", ".txt", ".json", ".jsonl", ".html", ".htm", ".xml",
    ".yml", ".yaml", ".toml", ".css", ".js", ".log", ".csv",
}
SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache", ".ruff_cache"}


def _iter_files(paths: Sequence[Path]) -> Iterable[Path]:
    for base in paths:
        path = Path(base)
        if path.is_file():
            yield path
            continue
        if not path.is_dir():
            continue
        for child in path.rglob("*"):
            if any(part in SKIP_DIRS for part in child.parts):
                continue
            if child.is_file() and child.suffix.lower() in TEXT_EXTENSIONS:
                yield child


def _merge_ranges(ranges: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _preview(line: str, ranges: Sequence[tuple[int, int]], limit: int = 180) -> str:
    masked = line
    for start, end in sorted(ranges, reverse=True):
        masked = masked[:start] + "<MATCH>" + masked[end:]
    return " ".join(masked.split())[:limit]


def _line_findings(
    file_path: Path,
    line_number: int,
    line: str,
    user_re: Optional[re.Pattern[str]],
    secret_patterns: Sequence[tuple[re.Pattern[str], str]],
) -> Iterable[dict[str, Any]]:
    matches: list[tuple[int, int, str]] = []
    if user_re is not None:
        matches.extend(
            (match.start(), match.end(), "username") for match in user_re.finditer(line)
        )
    for pattern, kind in secret_patterns:
        matches.extend(
            (match.start(), match.end(), kind) for match in pattern.finditer(line)
        )
    if not matches:
        return
    # Mask every sensitive range on the line in each preview, so one
    # finding never leaks another match as clear text.
    ranges = _merge_ranges([(start, end) for start, end, _ in matches])
    for _start, _end, kind in matches:
        yield {
            "path": str(file_path),
            "line": line_number,
            "kind": kind,
            "preview": _preview(line, ranges),
        }


def _compile_user_patterns(patterns: Sequence[str]) -> list[re.Pattern[str]]:
    compiled: list[re.Pattern[str]] = []
    for raw in patterns:
        try:
            compiled.append(re.compile(raw))
        except re.error:
            continue
    return compiled


def _build_patterns(
    username: Optional[str], extra_patterns: Sequence[str]
) -> tuple[Optional[re.Pattern[str]], list[tuple[re.Pattern[str], str]]]:
    secret_patterns = [(pattern, "secret") for pattern in _DEFAULT_TOKEN_PATTERNS]
    secret_patterns.extend(
        (pattern, "pattern") for pattern in _compile_user_patterns(extra_patterns)
    )
    user_re = re.compile(re.escape(username), re.IGNORECASE) if username else None
    return user_re, secret_patterns


def _count_kinds(findings: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding["kind"]] = counts.get(finding["kind"], 0) + 1
    return counts


def audit_paths(
    paths: Sequence[Path],
    *,
    username: Optional[str] = None,
    extra_patterns: Sequence[str] = (),
    max_findings: int = 200,
) -> dict[str, Any]:
    """Scan text files and return findings. Does not modify anything."""
    findings: list[dict[str, Any]] = []
    files_scanned = 0
    user_re, secret_patterns = _build_patterns(username, extra_patterns)

    for file_path in _iter_files(paths):
        if len(findings) >= max_findings:
            break
        try:
            raw = file_path.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw[:4096]:
            continue
        text = raw.decode("utf-8", errors="replace")
        files_scanned += 1
        for line_number, line in enumerate(text.splitlines(), 1):
            remaining = max_findings - len(findings)
            findings.extend(
                islice(
                    _line_findings(file_path, line_number, line, user_re, secret_patterns),
                    remaining,
                )
            )
            if len(findings) >= max_findings:
                break

    return {
        "files_scanned": files_scanned,
        "username": username or "",
        "findings": findings,
        "counts": _count_kinds(findings),
        "truncated": len(findings) >= max_findings,
    }


def cmd_audit(args: Any) -> int:
    """Print the privacy report for the selected paths."""
    configured = resolve_config()
    redaction = configured.get("redaction") if isinstance(configured, dict) else None
    redaction = redaction if isinstance(redaction, dict) else {}
    username = (
        getattr(args, "username", None)
        or redaction.get("real_username")
        or os.environ.get("USER")
        or os.environ.get("USERNAME")
        or ""
    )
    paths = getattr(args, "path", None)
    if not paths:
        paths = [REPO_ROOT / relative for relative in DEFAULT_RELATIVE_PATHS]

    report = audit_paths(
        paths,
        username=username,
        extra_patterns=redaction.get("extra_patterns") or [],
    )

    if getattr(args, "json", False):
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"audit: scanned {report['files_scanned']} file(s)")
        print(f"audit: {len(report['findings'])} finding(s)")
        for kind, count in sorted(report["counts"].items()):
            print(f"  {kind}: {count}")
        for finding in report["findings"][:50]:
            print(
                f"  {finding['path']}:{finding['line']} "
                f"[{finding['kind']}] {finding['preview']}"
            )
        if report["truncated"]:
            print("  … findings truncated")
        if report["findings"]:
            print("audit: review before publishing raw/, wiki/, or site/")

    if report["findings"] and getattr(args, "fail_on_findings", False):
        return 1
    return 0