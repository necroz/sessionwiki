# sessionwiki

Search a local wiki compiled from your past AI coding sessions, before your
agent redoes work that is already solved.

sessionwiki turns the transcripts that Claude Code, Codex CLI, Cursor, Gemini
CLI, Copilot, ZCode and OpenCode write to disk into an interlinked wiki: one
page per session, with summaries, decisions, fixes and links between them.
This plugin connects Claude Code to that wiki. It adds the sessionwiki MCP
server, a skill that tells Claude when to search, and a start-of-session
recall that shows where the work stopped last time.

## Requirements

You need a sessionwiki folder: a clone of the project that holds `raw/` and
`wiki/`, or any folder where you ran `sessionwiki init`. The plugin asks for
that folder once, during install, and keeps the answer in its configuration.

The first run downloads the package through `uvx`, so Python 3.9 or newer and
`uv` must be on the machine. Everything stays local. Transcripts are redacted
on the way in, and no data leaves your computer.

## What you get

- **MCP tools** — `wiki_query`, `wiki_search`, `wiki_read_page`,
  `wiki_list_sources`, `wiki_sync` and more, so Claude can look up an earlier
  decision instead of asking you again.
- **A skill** that says when to search: before a task that may depend on past
  work, and when you ask what you decided about something.
- **Session start recall** — a short note at the start of a session that
  points at the last unfinished work in the current project.

## Links

- Project and full documentation: https://github.com/necroz/sessionwiki
- Issues and support: https://github.com/necroz/sessionwiki/issues
- Privacy: https://github.com/necroz/sessionwiki/blob/master/docs/privacy.md
