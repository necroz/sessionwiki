"""Environment diagnostics for cross-machine installs."""

from __future__ import annotations

import json

from sessionwiki import doctor
from sessionwiki.synth.agent_delegate import sentinel_for


def test_collect_report_reports_core_environment(tmp_path):
    report = doctor.collect_report(repo_root=tmp_path, home=tmp_path)

    assert report["python"]["ok"] is True
    assert report["markdown"]["ok"] is True
    assert "version" in report["python"]["detail"].lower() or report["python"]["detail"]


def test_collect_report_flags_missing_zcode_paths(tmp_path):
    report = doctor.collect_report(repo_root=tmp_path, home=tmp_path)

    assert report["zcode_db"]["ok"] is False
    assert report["zcode_export"]["ok"] is False
    assert "not found" in report["zcode_db"]["detail"].lower()


def test_collect_report_detects_zcode_paths(tmp_path):
    db = tmp_path / ".zcode" / "cli" / "db" / "db.sqlite"
    db.parent.mkdir(parents=True)
    db.write_bytes(b"")
    export_dir = tmp_path / ".llmwiki" / "zcode" / "project"
    export_dir.mkdir(parents=True)
    (export_dir / "session.jsonl").write_text("{}\n", encoding="utf-8")

    report = doctor.collect_report(repo_root=tmp_path, home=tmp_path)

    assert report["zcode_db"]["ok"] is True
    assert report["zcode_export"]["ok"] is True


def test_cmd_doctor_returns_zero_when_core_checks_pass(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(doctor, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(doctor.Path, "home", classmethod(lambda cls: tmp_path))

    rc = doctor.cmd_doctor()

    out = capsys.readouterr().out
    assert rc == 0
    assert "python" in out.lower()
    assert "zcode" in out.lower()


def test_synthesis_check_ok_on_empty_repo(tmp_path):
    report = doctor.collect_report(repo_root=tmp_path, home=tmp_path)

    assert report["synthesis"]["ok"] is True
    assert "0 raw session(s)" in report["synthesis"]["detail"]


def test_synthesis_check_counts_unsynthesized_raw_sessions(tmp_path):
    raw = tmp_path / "raw" / "sessions"
    raw.mkdir(parents=True)
    done = raw / "done.md"
    done.write_text("# done\n", encoding="utf-8")
    (raw / "new.md").write_text("# new\n", encoding="utf-8")
    state_file = tmp_path / ".llmwiki-synth-state.json"
    state_file.write_text(
        json.dumps({"done.md": done.stat().st_mtime}), encoding="utf-8"
    )

    report = doctor.collect_report(repo_root=tmp_path, home=tmp_path)

    assert report["synthesis"]["ok"] is False
    assert "1 raw session(s) not synthesized" in report["synthesis"]["detail"]


def test_synthesis_check_counts_pages_waiting_for_the_agent(tmp_path):
    sources = tmp_path / "wiki" / "sources" / "project"
    sources.mkdir(parents=True)
    page = sources / "session.md"
    page.write_text(
        f"---\ntitle: x\n---\n{sentinel_for('00000000-0000-0000-0000-000000000000')}\n",
        encoding="utf-8",
    )

    report = doctor.collect_report(repo_root=tmp_path, home=tmp_path)

    assert report["synthesis"]["ok"] is False
    assert "1 page(s) waiting for the agent" in report["synthesis"]["detail"]


def test_cmd_doctor_returns_zero_when_only_synthesis_warns(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(doctor, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(doctor.Path, "home", classmethod(lambda cls: tmp_path))
    raw = tmp_path / "raw" / "sessions"
    raw.mkdir(parents=True)
    (raw / "new.md").write_text("# new\n", encoding="utf-8")

    rc = doctor.cmd_doctor()

    out = capsys.readouterr().out
    assert rc == 0
    assert "[warn] synthesis" in out


def test_synthesis_check_survives_an_unreadable_state_file(tmp_path, monkeypatch):
    import sessionwiki.synth.pipeline as pipeline

    def boom(_path):
        raise PermissionError("denied")

    monkeypatch.setattr(pipeline, "_load_state", boom)

    report = doctor._check_synthesis(tmp_path)

    assert report["ok"] is False
    assert "cannot read synthesis state" in report["detail"]
