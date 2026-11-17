# Privacy

sessionwiki processes session transcripts that can contain PII, API keys, file paths, and internal URLs. Privacy is baked into the core design. This document is the full story on what sessionwiki does to protect you — and where you're still responsible.

## Hard rules

These are non-negotiable and enforced in both code and CI:

1. **Redaction is ON by default.** Username, API keys, tokens, passwords, and emails are redacted before anything hits `raw/`.
2. **Localhost-only binding.** The HTTP server binds to `127.0.0.1` unless you explicitly pass `--host 0.0.0.0`.
3. **No telemetry, ever.** The tool never calls home. No usage counts, no adapter pings, no error uploads.
4. **No network by default.** Everything runs offline after install. Synthesis is opt-in: the `extractive` and `dummy` backends are offline, a loopback `ollama` or `openai` server keeps transcripts on the machine, and a non-loopback `openai` `base_url` sends them off the machine (the backend logs a warning). Agent-delegate mode never makes an HTTP call.
5. **raw/, wiki/, site/, and .ingestion-state.json are gitignored.** They never enter version control.
6. **Privacy grep in CI.** GitHub Actions fails the build if any committed file contains the maintainer's real username.
7. **Gitleaks in CI.** Secret scanning blocks merges on any detected API key, token, or password.

## What gets redacted

The converter redacts each record the moment it parses the `.jsonl` into markdown, before the file reaches `raw/`. Redaction runs on user prompts, assistant text, tool inputs and tool results.

| Layer | What matches | Replacement |
|---|---|---|
| Username in home paths | `/Users/<you>`, `/home/<you>`, `C:\Users\<you>` (any drive, either slash), WSL `/mnt/<d>/Users/<you>` and `\\wsl$\…\home\<you>`, Cygwin `/cygdrive/<d>/Users/<you>`, `\\?\C:\Users\<you>` | `USER` in place of the name |
| Username in other contexts | Claude Code folder names (`-home-<you>-Projects-x`, `-Users-<you>-…`), `<you>@host`, the owner and group columns of `ls -l`, `id` output (`uid=1000(<you>)`), `USER=`, `LOGNAME=`, `User=`, `Group=`, `-U <you>`, `-u <you>`, `--user=`, `git -c user.name=`, `/tmp/pytest-of-<you>`, `[sudo] password for <you>`, and the name alone on a line (`whoami`) | `USER` in place of the name |
| 29 built-in secret patterns | **Prefix tokens:** GitHub (`ghp_`, `gho_`, `ghs_`, `ghu_`, `github_pat_`), GitLab `glpat-`, AWS `AKIA…`, Slack `xox[abprs]-`, Anthropic `sk-ant-api…`, OpenAI `sk-`, `sk-proj-`, `sk-svcacct-`, Google `AIza…`, Stripe `sk_live_`, `pk_live_`, `rk_live_`, npm `npm_`, Hugging Face `hf_`, Telegram bot tokens, JWT. **Blocks:** PEM and PGP private keys. **Values in context:** Slack and Discord webhook paths, the password in `scheme://user:<password>@host`, `Authorization: Basic\|Token\|Digest`, `mysql -p<password>`, `sshpass -p <password>`, `aws_secret_access_key`, and keyword + value (`api_key`, `secret`, `client_secret`, `token`, `bearer`, `password`, `passwd`, `NAME_PWD`, then `:`, `=`, quotes, whitespace, URL-encoded `%3D`/`%3A`/`%22` or JSON-escaped quotes, then 8+ characters) | `<REDACTED>`; for values in context only the value, so `MYSQL_PWD=<REDACTED>` keeps the name |
| Default `extra_patterns` | email addresses | `<REDACTED>` |
| Thinking blocks | `thinking` content blocks | dropped entirely (`drop_thinking_blocks`) |

The built-in secret patterns live in code (`_DEFAULT_TOKEN_PATTERNS` in `sessionwiki/convert.py`) and always run. Your config cannot turn them off. The `extra_patterns` list lives in `examples/sessions_config.json` and holds only the email pattern, because an address is not a secret. A `redaction.extra_patterns` list in `config.json` or `config.local.json` replaces it: copy the email pattern into your list if you want to keep it. A pattern with a named group `secret` masks only that group.

Stripe test keys (`sk_test_…`) are not redacted, because they are meant to ship in code. A keyword value that starts with `/`, `~`, `$`, `^`, `%`, `|` or `-` is not redacted, because it is a path, a variable or a flag, not a secret.

### Secrets split across lines

A terminal, an editor or a chat window can wrap a long token onto two or more lines. The redactor handles these cases:

- **Hard-wrapped tokens.** The redactor joins a line break that sits between two token characters (`A–Z`, `a–z`, `0–9`, `_`, `-`) and runs every pattern on the joined text. A match that crosses a joined break is redacted as a whole, with both halves and the break.
- **Shell continuations.** A `\` at the end of a line always joins the next line, as the shell does. `Bearer \` with the token on the next line is redacted.
- **Keyword on one line, value on the next.** `password:` followed by the value on the next line matches the keyword pattern, because the separator set includes the line break.
- **PEM keys without an END line.** A truncated paste or a preview can lose the END line. When the BEGIN line ends a line, the redactor masks everything from BEGIN to the end of the text block.
- **Truncation.** The converter redacts a field first and truncates it after. A token cut at the 200-character Bash summary limit, the Write preview line limit or the 120-character description limit cannot slip under a pattern threshold.

Limits of the joined pass:

- A dot does not join, because a sentence ends with a dot far more often than a wrap splits a JWT at its dot. A JWT split exactly at a dot is not caught.
- A match that runs into `NAME=` or `name:` on the next line is dropped. That is the next line of an `.env` or YAML file, not the tail of a token. The value on its own line is still redacted.
- When a secret ends a line and the next line starts with a word without indentation, that word can be redacted too. The redactor prefers an extra word to a leaked half key.
- A secret split between two separate messages or tool results is not joined, because each one is redacted on its own.

## What is NOT redacted by default

- **File paths that are not under your home directory.** `/opt/foo` and `/var/log/bar` are rendered as-is.
- **Relative paths.** `src/main.py` is rendered as-is.
- **Tool arguments that aren't recognised.** Bash commands get the first line preserved; Read/Write paths get the path preserved.
- **Secrets that match no pattern.** A bare password with no keyword before it, a customer name or an internal hostname stays as-is in prompts and tool output. Add your own pattern for these.
- **Your username in free text.** The name in a sentence (`git grep <you>`) or in output with no known context stays as-is. `sessionwiki audit` finds every occurrence.

**This is why `raw/` is gitignored and the server is localhost-only.** Run `sessionwiki audit` before you publish anything. It scans `raw/`, `wiki/` and `site/` with the same patterns, including PEM keys and wrapped tokens that span lines.

## Adding your own redaction patterns

Edit `config.local.json`:

```jsonc
{
  "redaction": {
    "real_username": "your-unix-username",
    "replacement_username": "USER",
    "extra_patterns": [
      // the default (emails):
      "[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+",

      // yours:
      "acmecorp\\.internal",
      "ACME-[0-9A-Z]{6,}"
    ]
  }
}
```

Re-run `sessionwiki sync --force` to apply the new patterns to existing sessions. Without `--force`, `sync` never overwrites a file that already exists in `raw/`.

## `.llmwikiignore` — coarse-grained exclusion

For entire projects, dates, or files you never want in the wiki at all, use `.llmwikiignore`. Gitignore syntax, one pattern per line:

```
# Skip a whole project
confidential-client/

# Skip anything from before a date
*2025-*

# Skip specific slugs
ai-newsletter/2026-04-04-secret-deal-*
```

## Where your data lives

| Path | What's there | Gitignored? |
|---|---|---|
| `~/.claude/projects/*/*.jsonl` | Raw session transcripts | N/A (outside repo) |
| `sessionwiki/raw/sessions/` | Converted, redacted markdown | ✅ |
| `sessionwiki/wiki/` | LLM-maintained wiki pages | ✅ |
| `sessionwiki/site/` | Generated HTML site | ✅ |
| `sessionwiki/.ingestion-state.json` | Mtime tracker | ✅ |
| `sessionwiki/.framework/` | Personal framework notes | ✅ |
| `sessionwiki/.temp/` | Research corpus (cloned repos) | ✅ |
| `sessionwiki/config.json` | Your config override | ✅ |

Everything with a ✅ stays on your machine. None of it is committed, uploaded, or synced.

## The `claude -p` synthesis exception

`sessionwiki build --synthesize` is the one feature that sends data off your machine. It does exactly this:

1. Builds a JSON summary of your projects (project names, session counts, dates, models — no content)
2. Calls the local `claude` binary (which Claude Code installed)
3. Gets back a 200–300 word markdown overview
4. Embeds it in `site/index.html`

Even this is off by default. You have to pass `--synthesize` explicitly. If you don't want any external API calls, just don't pass the flag — the home page still renders with project cards and stats, just without the synthesis paragraph.

## Localhost server

`sessionwiki serve` binds to `127.0.0.1:8765` by default. This means **only processes on your machine** can reach the server. Other machines on your LAN **cannot** see it. The browser tab is the only client.

If you want to share with a colleague on the same network:

```bash
./serve.sh --host 0.0.0.0 --port 8765
```

Note: this exposes `site/` (which may contain redacted transcripts of your sessions) to anyone who can reach your machine. Don't do this on untrusted networks.

## GitHub Pages (Self-Demo)

The `.github/workflows/pages.yml` workflow deploys a public demo site to `https://necroz.github.io/sessionwiki/` on every tag push. It uses **synthetic fixtures** from `tests/fixtures/demo/`, not your real session history. Your actual wiki is never touched by this workflow.

## Incident response

If you accidentally commit real PII or a secret:

1. **Don't just push a fix.** The history still has it.
2. Rotate the credential immediately if it's a key/token.
3. Use `git filter-repo` or `BFG Repo-Cleaner` to rewrite history.
4. Force-push to the branch.
5. Ask any collaborators to re-clone.
6. If the repo is public and the commit was pushed, assume the secret is compromised and rotate.

## Questions?

Open an issue with the `privacy` label. Or email — but not with PII in the subject line.
