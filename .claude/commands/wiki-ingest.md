Ingest a source document (or folder) into the sessionwiki.

Usage: /wiki-ingest <path>

`$ARGUMENTS` should be a path relative to the repo root — typically a file or folder under `raw/`. Examples:

- `/wiki-ingest raw/sessions/ai-newsletter/2026-04-04-kind-tinkering-hejlsberg.md`
- `/wiki-ingest raw/sessions/ai-newsletter/`
- `/wiki-ingest raw/sessions/`

Follow the **Ingest Workflow** exactly as defined in `CLAUDE.md`:

1. Read the source file (or every file in the folder) using the Read tool
2. Read `wiki/index.md` and `wiki/overview.md` for current context
3. Write `wiki/sources/<slug>.md` per the Source Page Format in `CLAUDE.md`
4. Update `wiki/index.md` — add the new source under `## Sources`
5. Update `wiki/overview.md` if the source adds substantial new information
6. Create or update `wiki/entities/<Name>.md` for any people, companies, projects, tools, libraries mentioned
7. Create or update `wiki/concepts/<Name>.md` for any ideas, patterns, or frameworks discussed
8. Cross-link everything with `[[wikilinks]]` under `## Connections`
9. Flag any contradictions with existing wiki content under `## Contradictions`
10. Append to `wiki/log.md`: `## [YYYY-MM-DD] ingest | <title>`

If you are ingesting a **session-derived** source (a file under `raw/sessions/`), also apply the session-specific rules from `CLAUDE.md` §"Session-derived source specifics":

- Trust the frontmatter as authoritative metadata
- Do not copy the `## Conversation` section verbatim
- Create or update the project entity page
- Extract any explicit decisions into `wiki/concepts/`
- If there are more than ~20 files, ask the user before processing all of them

After finishing, summarise: what was added, which pages were created or updated, any contradictions found.
