# Documentation translations

Translations of sessionwiki's user-facing documentation. All translations track
the English master in `docs/`. If a translation falls behind, a note at the
top of the file says so.

> [!NOTE]
> **Status at v1.0:** Translation scaffolds were seeded at v0.3 but have
> **not been actively maintained** since. The English docs under `docs/`
> are the source of truth and have evolved substantially through v0.4–v1.0.
> The zh-CN / ja / es files below are kept as structure for future
> contributors — PRs welcome.

## Available

| Language | Code | Page | Status |
|---|---|---|---|
| English | `en` | `../getting-started.md` | ✅ canonical |
| 中文 (简体) | `zh-CN` | `zh-CN/getting-started.md` | 🟠 stale scaffold (v0.3) |
| 日本語 | `ja` | `ja/getting-started.md` | 🟠 stale scaffold (v0.3) |
| Español | `es` | `es/getting-started.md` | 🟠 stale scaffold (v0.3) |

## Scope

v0.3 ships the **getting-started** page in three languages. Future versions
will extend this to architecture, configuration, and privacy as demand
surfaces.

## How to contribute a translation

1. Pick a page in `docs/` (must be user-facing, not internal framework docs).
2. Copy it to `docs/i18n/<lang-code>/<filename>.md`.
3. Translate. Leave code blocks, file paths, URLs, and shell commands
   untranslated.
4. Add a note at the top linking to the English master and the commit hash
   it was translated from.
5. Open a PR tagged `i18n:<lang-code>`.

## Keeping translations in sync

When the English master changes, we flag stale translations in `/wiki-lint`.
For v0.3, translations are best-effort — a slightly stale translation is
better than no translation.

## Why these three languages

Based on GitHub star distribution for similar tools (Karpathy's LLM Wiki
implementations): ~40% Chinese-speaking, ~15% Japanese-speaking, ~10%
Spanish-speaking users of dev tools in this category.

More languages welcome — open an issue tagged `i18n` with your target
language.
