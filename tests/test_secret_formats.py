"""Secret formats and username contexts the redactor used to miss.

A probe over 22 common formats found 13 that reached ``raw/`` in clear
text, and the username appeared in 644 of 1165 converted sessions
outside a home path. Every secret below is generated at run time
(`tests/fake_secrets.py`), so gitleaks does not flag the test file itself.
"""

from __future__ import annotations

import pytest

from sessionwiki.convert import DEFAULT_CONFIG, Redactor
from tests.fake_secrets import fake

BODY = fake(44)
DASHES = "-" * 5


@pytest.fixture
def bare():
    """Built-in patterns only: no username, no extra patterns."""
    return Redactor({"redaction": {"real_username": "", "extra_patterns": []}})


@pytest.fixture
def user_redactor():
    return Redactor({
        "redaction": {
            "real_username": "jdoe-x",
            "replacement_username": "USER",
            "extra_patterns": [],
        },
    })


# ─── 1. username outside home paths ───────────────────────────────────────


@pytest.mark.parametrize("text", [
    "/tmp/claude-1000/-home-jdoe-x-Projects-llm-wiki/scratchpad",
    "~/.claude/projects/-home-jdoe-x-Projects-audio/abc.jsonl",
    "~/.claude/projects/-Users-jdoe-x-code-app/abc.jsonl",
    "C--Users-jdoe-x-source-repo",
    "ssh -o BatchMode=yes jdoe-x@vdi-gpu-105 'nvidia-smi'",
    "scp model.bin jdoe-x@10.0.0.5:/data",
    "-rw-rw-r-- 1 jdoe-x jdoe-x 5582 Sep 25 15:58 notes.md",
    "drwx------  12 jdoe-x staff  384 Nov  9 07:51 .ssh",
    "uid=1000(jdoe-x) gid=1000(jdoe-x) groups=1000(jdoe-x),27(sudo)",
    "USER=jdoe-x\nLOGNAME=jdoe-x",
    "jdoe-x\n",
    "find /home/jdoe-x -maxdepth 2",
    "[Service]\nUser=jdoe-x\n",
    "psql -h 127.0.0.1 -p 5433 -U jdoe-x -d prod",
    "mysql -u jdoe-x -h db",
    'git -c user.name="jdoe-x" commit',
    "/tmp/pytest-of-jdoe-x/pytest-10/test0",
    "  → result (ok): -rw-rw-r-- 1 jdoe-x jdoe-x 0 Nov  2 15:00 a.txt",
    "-rw-rw-r--  1 jdoe-x",
    "[sudo] password for jdoe-x: ",
    "[Service]\nGroup=jdoe-x\n",
])
def test_username_is_redacted_in_context(user_redactor, text):
    assert "jdoe-x" not in user_redactor(text)


def test_ls_line_keeps_a_foreign_group(user_redactor):
    out = user_redactor("drwx------  12 jdoe-x staff  384 Nov  9 07:51 .ssh")
    assert out == "drwx------  12 USER staff  384 Nov  9 07:51 .ssh"


@pytest.mark.parametrize("text", [
    "jdoe-xyz is another account",
    "see the jdoe-x-tools repo",
    "ssh jdoe-xyz@host",
    "-rw-r--r-- 1 jdoe-xyz staff 10 Nov 9 07:51 a",
])
def test_username_inside_other_words_is_unchanged(user_redactor, text):
    assert user_redactor(text) == text


# ─── 2. formats with no pattern ───────────────────────────────────────────


@pytest.mark.parametrize("text", [
    f"aws_secret_access_key = {BODY[:40]}",
    f"AWS_SECRET_ACCESS_KEY={BODY[:40]}",
    f"Authorization: Basic YWRtaW46{BODY[:20]}",
    f"MYSQL_PWD={BODY[:14]}",
    f"passwd: {BODY[:14]}",
    f"mysql -u root -p{BODY[:12]} prod",
    f"sshpass -p '{BODY[:12]}' ssh host",
    "glpat-" + BODY[:20],
    "hf_" + BODY[:34],
    "123456789:AA" + BODY[:33],
    "https://hooks.slack.com/services/T0AB12CD3/B0AB12CD3/" + BODY[:24],
    "https://discord.com/api/webhooks/1234567890/" + BODY,
    "api_key%3D" + BODY[:20],
    '{"cmd": "export TOKEN=\\"' + BODY[:20] + '\\""}',
])
def test_format_is_redacted(bare, text):
    assert BODY[:10] not in bare(text)


def test_pgp_private_key_block_is_redacted(bare):
    text = (
        f"{DASHES}BEGIN PGP PRIVATE KEY BLOCK{DASHES}\n\nlQOYBF{BODY}\n=AbCd\n"
        f"{DASHES}END PGP PRIVATE KEY BLOCK{DASHES}"
    )
    out = bare(text)
    assert BODY[:10] not in out
    assert "=AbCd" not in out


# ─── 3. credentials in URLs ───────────────────────────────────────────────


@pytest.mark.parametrize("text", [
    f"DATABASE_URL=postgres://app:{BODY[:16]}@db.internal:5432/prod",
    f"git clone https://oauth2:{BODY[:20]}@gitlab.example.com/x.git",
    f"redis://:{BODY[:16]}@cache:6379/0",
])
def test_url_password_is_redacted_without_the_email_pattern(bare, text):
    out = bare(text)
    assert BODY[:10] not in out


def test_url_password_redaction_keeps_host(bare):
    out = bare(f"postgres://app:{BODY[:16]}@db.internal:5432/prod")
    assert out == "postgres://app:<REDACTED>@db.internal:5432/prod"


# ─── 4. the keyword pattern does not depend on extra_patterns ─────────────


@pytest.mark.parametrize("text", [
    f"OPENAI_API_KEY={BODY[:20]}",
    f"password: {BODY[:12]}",
    f'"client_secret": "{BODY[:24]}"',
    f"Bearer {BODY[:24]}",
])
def test_keyword_value_is_redacted_with_empty_extra_patterns(bare, text):
    assert BODY[:10] not in bare(text)


def test_keyword_name_stays_visible(bare):
    assert bare(f"MYSQL_PWD={BODY[:14]}") == "MYSQL_PWD=<REDACTED>"


def test_user_config_replacing_extra_patterns_keeps_keyword_redaction():
    r = Redactor({"redaction": {"real_username": "", "extra_patterns": [r"acme\.internal"]}})
    assert BODY[:10] not in r(f"password={BODY[:12]}")


# ─── no over-redaction ────────────────────────────────────────────────────


@pytest.mark.parametrize("text", [
    "the basic functionality works",
    "pwd && ls -la",
    "mysql -u root -P3306 -h db",
    "token_count: 12345678",
    "git@github.com:org/repo.git",
    "http://localhost:8000/api/v1",
    "1234:AAAA is not a bot token",
    'grep -rn -E "set_password|password" /home/USER/Projects/app',
    "from django.contrib.auth.hashers import make_password\n^3d34d62 fix",
    'grep -v "PASSWORD\\|SECRET\\|API_KEY" .env',
    "password=$DB_PASSWORD",
    "/home/jdoe-xyz/code",
    "SESSIONWIKI_HOME=$PWD .venv/bin/python -m sessionwiki",
    "cd $PWD && pwd   something_long",
])
def test_ordinary_text_is_unchanged(bare, text):
    assert bare(text) == text


def test_default_config_still_redacts_emails():
    r = Redactor({"redaction": dict(DEFAULT_CONFIG["redaction"])})
    assert "jane@example.com" not in r("write to jane@example.com")
