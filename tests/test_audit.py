"""Privacy audit for raw/wiki/site before publishing."""

from __future__ import annotations

from pathlib import Path

from sessionwiki import audit


def test_audit_finds_username_and_secret(tmp_path):
    root = tmp_path / "raw"
    root.mkdir()
    (root / "session.md").write_text(
        "home is /home/alice/project\n"
        "token sk-abcdefghijklmnopqrstuvwx\n",
        encoding="utf-8",
    )

    report = audit.audit_paths([root], username="alice")

    kinds = {finding["kind"] for finding in report["findings"]}
    assert "username" in kinds
    assert "secret" in kinds
    assert report["files_scanned"] == 1


def test_audit_clean_tree_has_no_findings(tmp_path):
    root = tmp_path / "wiki"
    root.mkdir()
    (root / "page.md").write_text("A clean page with no secrets.\n", encoding="utf-8")

    report = audit.audit_paths([root], username="alice")

    assert report["findings"] == []
    assert report["files_scanned"] == 1


def test_cli_audit_json_and_fail_flag(tmp_path, capsys, monkeypatch):
    from sessionwiki import cli

    root = tmp_path / "raw"
    root.mkdir()
    (root / "x.md").write_text("user alice\n", encoding="utf-8")
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)

    rc = cli.main(
        ["audit", "--path", str(root), "--json", "--fail-on-findings", "--username", "alice"]
    )

    out = capsys.readouterr().out
    assert rc == 1
    assert '"findings"' in out
    assert "alice" in out


def test_audit_parser_accepts_flags():
    from sessionwiki.cli import build_parser

    args = build_parser().parse_args(
        ["audit", "--path", "/tmp/raw", "--json", "--fail-on-findings"]
    )

    assert args.path == [Path("/tmp/raw")]
    assert args.json is True
    assert args.fail_on_findings is True


def test_audit_preview_masks_every_secret_on_a_line(tmp_path):
    # CodeQL py/clear-text-logging-sensitive-data: a preview masked only
    # its own match, so a second secret on the same line stayed clear text.
    root = tmp_path / "raw"
    root.mkdir()
    ghp = "ghp_" + "a" * 24
    akia = "AKIA" + "A" * 16
    (root / "session.md").write_text(
        f"keys {ghp} and {akia} here\n", encoding="utf-8"
    )

    report = audit.audit_paths([root])

    previews = [finding["preview"] for finding in report["findings"]]
    assert len(previews) == 2
    for preview in previews:
        assert ghp not in preview
        assert akia not in preview


def test_audit_preview_masks_username_next_to_secret(tmp_path):
    root = tmp_path / "raw"
    root.mkdir()
    token = "sk-abcdefghijklmnopqrstuvwx"
    (root / "session.md").write_text(f"alice uses {token}\n", encoding="utf-8")

    report = audit.audit_paths([root], username="alice")

    secret_previews = [
        finding["preview"] for finding in report["findings"] if finding["kind"] == "secret"
    ]
    assert secret_previews
    for preview in secret_previews:
        assert "alice" not in preview


def test_audit_preview_keeps_context_with_overlapping_patterns(tmp_path):
    # Overlapping matches must merge into one mask, not eat context chars.
    root = tmp_path / "raw"
    root.mkdir()
    (root / "session.md").write_text("zzabcdezz\n", encoding="utf-8")

    report = audit.audit_paths([root], extra_patterns=[r"abc", r"bcd"])

    previews = [finding["preview"] for finding in report["findings"]]
    assert previews == ["zz<MATCH>ezz", "zz<MATCH>ezz"]


def test_audit_max_findings_is_an_exact_cap(tmp_path):
    # The old loop appended before checking, so a line with several
    # secrets pushed the count past max_findings.
    root = tmp_path / "raw"
    root.mkdir()
    ghp = "ghp_" + "a" * 24
    akia = "AKIA" + "A" * 16
    (root / "session.md").write_text(f"{ghp} {akia}\n", encoding="utf-8")

    report = audit.audit_paths([root], max_findings=1)

    assert len(report["findings"]) == 1
    assert report["truncated"] is True