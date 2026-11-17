"""Secrets that a line break or a truncation cuts into parts.

The redactor used to run every pattern on the text as it is. A token
that a terminal or an editor wrapped onto two lines then matched in
part or not at all, and the converter truncated some fields before it
redacted them, so a cut token slipped under the length threshold.

Every secret below is generated at run time (`tests/fake_secrets.py`),
so gitleaks does not flag the test file itself.
"""

from __future__ import annotations

import pytest

from sessionwiki import audit
from sessionwiki.convert import (
    DEFAULT_CONFIG,
    Redactor,
    derive_description,
    summarize_tool_use,
)
from tests.fake_secrets import fake, fake_jwt, fake_pem_body

ANTHROPIC_PREFIX = "sk-" + "ant-api03-"
ANTHROPIC_BODY = fake(42)
ANTHROPIC_KEY = ANTHROPIC_PREFIX + ANTHROPIC_BODY
GITHUB_KEY = "gh" + "p_" + fake(36)
DASHES = "-" * 5


def _pem_lines(kind: str = "RSA ") -> tuple[str, str, list[str]]:
    begin = f"{DASHES}BEGIN {kind}PRIVATE KEY{DASHES}"
    end = f"{DASHES}END {kind}PRIVATE KEY{DASHES}"
    body = fake_pem_body()
    return begin, end, body


@pytest.fixture
def redactor():
    return Redactor({"redaction": {"real_username": "", "extra_patterns": []}})


@pytest.fixture
def default_redactor():
    """The redactor a fresh install builds, with the shipped extra patterns."""
    return Redactor({"redaction": dict(DEFAULT_CONFIG["redaction"])})


# ─── hard-wrapped tokens ──────────────────────────────────────────────────


def test_wrapped_token_redacts_both_halves(redactor):
    text = f"key: {ANTHROPIC_KEY[:30]}\n{ANTHROPIC_KEY[30:]} is the new one"
    out = redactor(text)
    assert ANTHROPIC_KEY[:30] not in out
    assert ANTHROPIC_KEY[30:] not in out
    assert "is the new one" in out


def test_wrapped_token_with_short_head_is_redacted(redactor):
    """The head alone is shorter than the pattern threshold."""
    text = f"export GH={GITHUB_KEY[:8]}\n{GITHUB_KEY[8:]}\n"
    out = redactor(text)
    assert GITHUB_KEY[8:] not in out
    assert GITHUB_KEY[:8] not in out


def test_wrapped_token_with_crlf_is_redacted(redactor):
    text = f"{ANTHROPIC_KEY[:20]}\r\n{ANTHROPIC_KEY[20:]}\r\n"
    out = redactor(text)
    assert ANTHROPIC_KEY[20:] not in out


def test_token_wrapped_over_three_lines_is_redacted(redactor):
    text = f"{ANTHROPIC_KEY[:18]}\n{ANTHROPIC_KEY[18:36]}\n{ANTHROPIC_KEY[36:]}"
    out = redactor(text)
    for part in (ANTHROPIC_KEY[:18], ANTHROPIC_KEY[18:36], ANTHROPIC_KEY[36:]):
        assert part not in out


def test_wrapped_jwt_is_redacted(redactor):
    jwt = fake_jwt()
    text = f"Bearer {jwt[:50]}\n{jwt[50:]}"
    out = redactor(text)
    header, _payload, signature = jwt.split(".")
    assert signature[:20] not in out
    assert header[3:20] not in out


def test_wrapped_keyword_value_is_redacted(default_redactor):
    head, tail = ANTHROPIC_BODY[:12], ANTHROPIC_BODY[12:24]
    text = f'API_KEY="{head}\n{tail}"'
    out = default_redactor(text)
    assert head not in out
    assert tail not in out


def test_shell_continuation_between_keyword_and_value_is_redacted(default_redactor):
    value = fake(21)
    text = f'curl -H "Authorization: Bearer \\\n  {value}" https://x'
    out = default_redactor(text)
    assert value not in out


def test_keyword_with_value_on_next_line_is_redacted(default_redactor):
    value = fake(15)
    out = default_redactor(f"password:\n    {value}\nnext: 1")
    assert value not in out
    assert "next: 1" in out


# ─── no over-redaction across ordinary line breaks ────────────────────────


def test_env_file_keeps_next_variable_name(redactor):
    text = f"GITHUB_TOKEN={GITHUB_KEY}\nOPENAI_BASE_URL=http://localhost:8000\n"
    out = redactor(text)
    assert GITHUB_KEY not in out
    assert "OPENAI_BASE_URL=http://localhost:8000" in out


def test_yaml_keeps_next_key(default_redactor):
    text = f"token: {ANTHROPIC_BODY[:18]}\nname: build\n"
    out = default_redactor(text)
    assert ANTHROPIC_BODY[:18] not in out
    assert "name: build" in out


def test_plain_lines_stay_unchanged(redactor):
    text = "first line ends here\nsecond line starts here\nsk-\nshort"
    assert redactor(text) == text


def test_sentence_end_does_not_join_the_next_line(default_redactor):
    text = "recall@20 fell below recall@10.\nSeeds are now the top 10 hits."
    assert default_redactor(text) == text


def test_markdown_bullet_does_not_join_the_previous_line(default_redactor):
    text = f"token: {ANTHROPIC_BODY[:18]}\n- next item\n"
    out = default_redactor(text)
    assert ANTHROPIC_BODY[:18] not in out
    assert "- next item" in out


# ─── PEM keys without an END line ─────────────────────────────────────────


def test_pem_without_end_line_is_redacted(redactor):
    begin, _end, body = _pem_lines()
    text = "\n".join([begin, *body[:4]])
    out = redactor(text)
    for line in body[:4]:
        assert line not in out


def test_pem_header_mentioned_in_prose_keeps_the_text(redactor):
    begin, _end, _body = _pem_lines("")
    text = f"A key file starts with `{begin}`; the rest of this sentence stays."
    assert redactor(text) == text


# ─── truncation must not cut a token before redaction ─────────────────────


def _config():
    return {"truncation": dict(DEFAULT_CONFIG["truncation"])}


def test_write_preview_does_not_leak_a_pem_body(redactor):
    begin, end, body = _pem_lines()
    content = "\n".join([begin, *body, end])
    block = {"name": "Write", "input": {"file_path": "/tmp/id_rsa", "content": content}}
    out = summarize_tool_use(block, redactor, _config())
    for line in body:
        assert line not in out


def test_bash_summary_redacts_before_truncating(redactor):
    """The 200-char cut leaves `sk-ant-api03-` plus a few key chars:
    too short for any pattern, but still a piece of the key."""
    command = "curl -s https://api.example.com/v1/messages -H 'x-api-key: "
    command += "a" * (194 - len(command) - len(ANTHROPIC_PREFIX)) + "=" + ANTHROPIC_KEY
    assert command.index(ANTHROPIC_KEY) + len(ANTHROPIC_PREFIX) == 195
    block = {"name": "Bash", "input": {"command": command}}
    out = summarize_tool_use(block, redactor, _config())
    assert ANTHROPIC_PREFIX + ANTHROPIC_BODY[:3] not in out


def test_bash_summary_redacts_a_token_split_by_the_first_line(redactor):
    command = f"echo {ANTHROPIC_KEY[:16]}\n{ANTHROPIC_KEY[16:]}"
    block = {"name": "Bash", "input": {"command": command}}
    out = summarize_tool_use(block, redactor, _config())
    assert ANTHROPIC_KEY[:16] not in out


def test_description_redacts_before_truncating(redactor):
    """A line with no spaces is cut hard at 117 chars, inside the key."""
    prompt = "auth fails: HEADER=" + "a" * 81 + "=" + ANTHROPIC_KEY
    assert prompt.index(ANTHROPIC_KEY) + len(ANTHROPIC_PREFIX) == 114
    records = [{"type": "user", "message": {"content": prompt}}]
    out = derive_description(records, redactor)
    assert ANTHROPIC_PREFIX not in out
    assert ANTHROPIC_BODY[:3] not in out


# ─── audit finds secrets that span lines ──────────────────────────────────


def test_audit_finds_pem_key_across_lines(tmp_path):
    begin, end, body = _pem_lines()
    page = tmp_path / "page.md"
    page.write_text("intro\n" + "\n".join([begin, *body, end]) + "\n", encoding="utf-8")
    report = audit.audit_paths([page])
    assert [f["line"] for f in report["findings"]] == [2]
    assert report["findings"][0]["kind"] == "secret"
    assert body[0] not in report["findings"][0]["preview"]


def test_audit_finds_wrapped_token(tmp_path):
    page = tmp_path / "page.md"
    page.write_text(f"header\nkey {GITHUB_KEY[:8]}\n{GITHUB_KEY[8:]}\n", encoding="utf-8")
    report = audit.audit_paths([page])
    assert [(f["line"], f["kind"]) for f in report["findings"]] == [(2, "secret")]
    assert GITHUB_KEY[:8] not in report["findings"][0]["preview"]
