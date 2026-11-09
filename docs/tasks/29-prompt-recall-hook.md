# 29 — Opt-in `UserPromptSubmit` hook: `recall --prompt-hook`

- Priority: P1
- Roadmap: Phase 2, C1
- Depends on: 12, 17 (`rank_query`), 20 (filters)
- Size: M (2–3 h)
- Files: `sessionwiki/cli.py`, `tests/test_prompt_recall_hook.py` (new),
  `README.md` (hook section)
- Branch: `feat/prompt-recall-hook`
- PR title: `feat(recall): opt-in prompt hook that adds related past work`

## Read first

- `sessionwiki/cli.py`: `cmd_recall`, `_project_from_hook_input`, the
  `recall` parser
- `sessionwiki/mcp/server.py`: `rank_query` (card 17) with `filters`
  (card 20), `DATA_NOTICE`
- `README.md`: the Claude Code `Stop` hook snippet (around line 104)
- Claude Code hook input for `UserPromptSubmit`: JSON on stdin with
  `prompt` and `cwd`. The output format
  `{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "..."}}`
  is the same shape `recall --format hook` already uses for `SessionStart`.

## Problem

Agents ask the human without reading memory first (kaeru: 80% of
questions). Card 12 tells them to search; this card pushes the related
pages into context when the user sends a prompt. It runs on **every**
prompt, so it must be opt-in, fast, and silent when nothing matches.

## Required change

1. New flag on `recall`:

```python
recall.add_argument(
    "--prompt-hook", action="store_true",
    help="UserPromptSubmit hook: add related wiki pages for the prompt on stdin "
         "(only when SESSIONWIKI_PROMPT_RECALL=1)",
)
```

2. In `cmd_recall`, at the start:

```python
if args.prompt_hook:
    return _prompt_recall()
```

3. `_prompt_recall()`:

```python
_PROMPT_RECALL_MIN_SCORE = 0.0  # set from the calibration below
_PROMPT_RECALL_MAX_PAGES = 3
_PROMPT_RECALL_MIN_CHARS = 20


def _prompt_recall() -> int:
    if os.environ.get("SESSIONWIKI_PROMPT_RECALL") != "1":
        return 0
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except (OSError, ValueError):
        return 0
    prompt = str(data.get("prompt") or "").strip()
    if len(prompt) < _PROMPT_RECALL_MIN_CHARS or prompt.startswith("/"):
        return 0
    cwd = data.get("cwd")
    project = Path(cwd).name if isinstance(cwd, str) and cwd else ""
    from sessionwiki.mcp.server import DATA_NOTICE, rank_query
    result = rank_query(
        prompt, max_pages=_PROMPT_RECALL_MAX_PAGES, include_raw=False,
        filters={"project": project} if project else None,
    )
    hits = [h for h in result["hits"] if h["score"] >= _PROMPT_RECALL_MIN_SCORE]
    if not hits:
        return 0
    lines = ["Related past work (sessionwiki):", DATA_NOTICE, ""]
    for h in hits:
        snippet = " ".join(h["snippet"].split())[:200]
        lines.append(f"- {h['path']} — {snippet}")
    lines += ["", "Read the page with wiki_read_page before you ask the user about it."]
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": "\n".join(lines),
    }}, ensure_ascii=False))
    return 0
```

   Every error path returns 0 and prints nothing: a hook must never block
   the user's prompt. Wrap the `rank_query` call in `try/except Exception`
   for the same reason.

4. **Calibrate the threshold.** In a scratch script outside the repo, take
   the `description` (first user request) of 20 recent raw sessions, call
   `rank_query` with the session's project as filter, and print the top
   score. Choose `_PROMPT_RECALL_MIN_SCORE` so that roughly the top half of
   prompts get context. Put the table (prompt length, top score, chosen
   threshold) in the PR body — no prompt text, it is private.

5. **Measure latency.** Run 5 times and report the median:

```bash
time (printf '%s' '{"prompt":"how did we chunk large sessions in synthesis","cwd":"/x/llm-wiki"}' \
  | SESSIONWIKI_PROMPT_RECALL=1 .venv/bin/python -m sessionwiki recall --prompt-hook)
```

   Also measure through `uvx sessionwiki` if `uvx` is installed.

6. `README.md`: after the `Stop` hook snippet, add an opt-in
   `UserPromptSubmit` snippet for `~/.claude/settings.json` with
   `SESSIONWIKI_PROMPT_RECALL=1` in the command and `"timeout": 10`, and one
   sentence on cost (one wiki scan per prompt, measured median). Do **not**
   register the hook in `plugin/hooks/hooks.json`.

## Tests

New `tests/test_prompt_recall_hook.py` (seed a wiki; patch both
`REPO_ROOT`s; set the env var with `monkeypatch.setenv`):

- Without the env var: no output, exit 0.
- Short prompt or `/command`: no output.
- Matching prompt: valid JSON, `hookEventName == "UserPromptSubmit"`,
  context contains the page path and `DATA_NOTICE`.
- Pages of another project are not included.
- Below-threshold hits: no output (patch `_PROMPT_RECALL_MIN_SCORE` high).
- Broken stdin JSON: no output, exit 0.
- `rank_query` raising: no output, exit 0.

## Verification

```bash
.venv/bin/python -m pytest tests/test_prompt_recall_hook.py tests/test_mcp_recall.py -q
.venv/bin/python -m pytest tests/ -q
```

## Acceptance criteria

- [ ] Opt-in by env var; silent otherwise.
- [ ] Never fails the prompt.
- [ ] Threshold calibrated and latency measured in the PR body.
- [ ] README snippet; plugin hooks unchanged.
- [ ] `CHANGELOG.md` updated.

## Out of scope

- Registering the hook in the plugin by default (decide after real use).
- Detecting "the agent is about to ask a question" (no such hook event).
- Pre-compaction checkpoint (C3).

## Rollback

Remove the flag, the function, the test and the README snippet.
