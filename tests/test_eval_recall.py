"""scripts/eval_recall.py: recall@k of wiki_query over a hand-made query set."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "eval_recall", Path(__file__).resolve().parents[1] / "scripts" / "eval_recall.py"
)
eval_recall = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(eval_recall)


QUERIES = [
    {"id": "q1", "kind": "exact", "question": "alpha", "expected": ["a.md", "b.md"]},
    {"id": "q2", "kind": "exact", "question": "beta", "expected": ["c.md"]},
    {"id": "q3", "kind": "relational", "question": "gamma", "expected": ["d.md", "e.md"]},
]
RANKED = {
    "alpha": ["a.md", "x.md", "b.md"],  # both found
    "beta": ["x.md", "y.md"],           # missed
    "gamma": ["e.md", "z.md"],          # half found
}


def test_recall_is_averaged_per_kind_and_overall():
    report = eval_recall.evaluate(QUERIES, RANKED.__getitem__)

    assert report["by_kind"]["exact"] == {"queries": 2, "recall": 0.5, "hit": 0.5}
    assert report["by_kind"]["relational"] == {"queries": 1, "recall": 0.5, "hit": 1.0}
    assert report["overall"] == {"queries": 3, "recall": 0.5, "hit": 2 / 3}


def test_report_lists_the_pages_each_query_missed():
    report = eval_recall.evaluate(QUERIES, RANKED.__getitem__)

    missed = {q["id"]: q["missed"] for q in report["queries"]}
    assert missed == {"q1": [], "q2": ["c.md"], "q3": ["d.md"]}


def test_text_report_shows_each_kind_and_the_misses():
    report = eval_recall.evaluate(QUERIES, RANKED.__getitem__)

    lines = eval_recall.format_report(report, k=3).splitlines()

    assert lines[0].split() == ["kind", "n", "recall@3", "hit@3"]
    assert lines[1].split() == ["exact", "2", "50.0%", "50.0%"]
    assert lines[3].split() == ["overall", "3", "50.0%", "66.7%"]
    assert lines[4:] == ["  q2 (exact) missed 1: c.md", "  q3 (relational) missed 1: d.md"]


def test_main_runs_wiki_query_and_writes_the_json_report(tmp_path: Path, capsys):
    from unittest.mock import patch

    from sessionwiki.mcp import server

    page = tmp_path / "wiki" / "sources" / "app" / "2026-01-01-s1.md"
    page.parent.mkdir(parents=True)
    page.write_text('---\ntitle: "Session: s1"\ntype: source\n---\n\nKeycloak login.\n', encoding="utf-8")
    queries = tmp_path / "q.json"
    queries.write_text(json.dumps([{"id": "q1", "kind": "exact", "question": "keycloak",
                                    "expected": ["wiki/sources/app/2026-01-01-s1.md"]}]))
    out = tmp_path / "report.json"

    with patch.object(server, "REPO_ROOT", tmp_path):
        assert eval_recall.main([str(queries), "--k", "3", "--json", str(out)]) == 0

    assert json.loads(out.read_text())["overall"]["recall"] == 1.0
    assert "overall" in capsys.readouterr().out


def test_ranked_paths_are_read_from_the_wiki_query_output():
    text = "# Query: x\n\n## `wiki/sources/p/a.md` (score: 3.0)\nsnippet\n## `raw/sessions/b.md` (score: 1.0)\n"

    assert eval_recall.ranked_paths(text) == ["wiki/sources/p/a.md", "raw/sessions/b.md"]


def _snapshot_wiki(tmp_path: Path) -> Path:
    """An old page that holds the answer and a newer one that quotes the query."""
    sources = tmp_path / "wiki" / "sources" / "app"
    sources.mkdir(parents=True)
    (sources / "2026-01-01-old.md").write_text(
        '---\ntitle: "Session: old"\ntype: source\ndate: 2026-01-01\n---\n\nKeycloak login.\n',
        encoding="utf-8",
    )
    (sources / "2026-02-01-new.md").write_text(
        '---\ntitle: "Keycloak"\ntype: source\ndate: 2026-02-01\n---\n\nKeycloak keycloak.\n',
        encoding="utf-8",
    )
    queries = tmp_path / "q.json"
    queries.write_text(json.dumps([{"id": "q1", "kind": "exact", "question": "keycloak",
                                    "expected": ["wiki/sources/app/2026-01-01-old.md"]}]))
    return queries


def test_date_to_pins_the_wiki_snapshot(tmp_path: Path, capsys):
    from unittest.mock import patch

    from sessionwiki.mcp import server

    queries = _snapshot_wiki(tmp_path)
    live, pinned = tmp_path / "live.json", tmp_path / "pinned.json"

    with patch.object(server, "REPO_ROOT", tmp_path):
        eval_recall.main([str(queries), "--k", "1", "--json", str(live)])
        eval_recall.main([str(queries), "--k", "1", "--date-to", "2026-01-31", "--json", str(pinned)])

    assert json.loads(live.read_text())["overall"]["recall"] == 0.0
    report = json.loads(pinned.read_text())
    assert report["overall"]["recall"] == 1.0
    assert report["date_to"] == "2026-01-31"
    assert "2026-01-31" in capsys.readouterr().out


def test_invalid_date_to_is_rejected(tmp_path: Path):
    import pytest

    queries = _snapshot_wiki(tmp_path)

    with pytest.raises(SystemExit):
        eval_recall.main([str(queries), "--date-to", "last week"])
