# sessionwiki Integrations

Scaffold implementations showing how sessionwiki connects to other tools. Each integration is minimal but functional enough to demonstrate the pattern.

## Directory

| Integration | Type | Status | Description |
|---|---|---|---|
| [vscode/](vscode/) | VS Code extension | Scaffold | Sidebar tree view, sync/build commands, open site in browser |
| [obsidian/](obsidian/) | Obsidian plugin | Scaffold | Sync wiki/ into an Obsidian vault, preserving native `[[wikilinks]]` |
| [raycast/](raycast/) | Raycast extension | Scaffold | Full-text search across wiki pages from Raycast |
| [alfred/](alfred/) | Alfred workflow | Scaffold | Script Filter search via `wiki <query>` keyword |
| [webhook/](webhook/) | GitHub webhook | Scaffold | Auto-sync on push via stdlib HTTP handler |

## In-package Exporters

These live in the `sessionwiki/` package rather than `integrations/`:

| Module | Status | Description |
|---|---|---|
| `sessionwiki.export_jupyter` | Scaffold | Export wiki sections as Jupyter notebooks (.ipynb) |
| `sessionwiki.export_marp` | Shipped | Export wiki pages as Marp slide decks |
| `sessionwiki.export_qmd` | Shipped | Export for qmd hybrid search |
| `sessionwiki.obsidian_output` | Shipped | Full Obsidian vault export (`export-obsidian` CLI) |

## Contributing

Each integration should:

1. Be self-contained in its directory with its own README
2. Use the sessionwiki CLI (`python3 -m sessionwiki <subcommand>`) as the interface — do not import sessionwiki internals
3. Provide enough scaffolding to build and test locally
4. Stay stdlib-only for Python integrations; minimize dependencies for JS/TS integrations

To promote a scaffold to "shipped" status:

1. Add end-to-end tests
2. Wire up any needed CLI subcommands in `sessionwiki/cli.py`
3. Update this table
4. Add a changelog entry
