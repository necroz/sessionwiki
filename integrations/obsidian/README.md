# sessionwiki Obsidian Plugin

A minimal Obsidian plugin that syncs your sessionwiki knowledge base into an Obsidian vault.

## What it does

- Registers a **Wiki Sync** command that runs `python3 -m sessionwiki sync` and copies the resulting `wiki/` folder into your vault
- Registers a **Wiki Build** command that runs `python3 -m sessionwiki build`
- Preserves `[[wikilinks]]` natively -- sessionwiki already uses Obsidian-compatible link syntax

## Prerequisites

- An sessionwiki project on disk (with `wiki/index.md`)
- Python 3.9+ with `sessionwiki` installed

## Build

```bash
cd integrations/obsidian
npm install
npx esbuild main.ts --bundle --external:obsidian --outfile=main.js --format=cjs
```

## Install (development)

1. Build `main.js` as above
2. Copy `main.js` and `manifest.json` into your vault's `.obsidian/plugins/sessionwiki-sync/` directory
3. Enable the plugin in Obsidian settings

## Configuration

Open **Settings > Community Plugins > sessionwiki Sync** and set:

| Setting | Description |
|---|---|
| Project root | Absolute path to your sessionwiki repository |
| Python path | Python interpreter (default: `python3`) |
| Vault folder | Folder inside the vault for synced pages (default: `sessionwiki`) |

## How it works

The plugin shells out to the sessionwiki CLI for sync/build, then copies `.md` files from the project's `wiki/` directory into the configured vault folder. Since sessionwiki's `[[wikilinks]]` are already Obsidian-native, all cross-references work immediately in the graph view.

Note: the `sessionwiki export-obsidian` CLI command provides a more complete export path. This plugin is for users who want a one-click sync from within Obsidian.
