# Publishing sessionwiki to plugin and MCP catalogs

Checked against each catalog's docs on 2026-11-05. Catalog rules change; re-check
the linked page before each step.

## Verdict

| Catalog | Worth it | Why |
|---|---|---|
| Own Claude Code plugin marketplace (this repo) | **Yes — do first** | One-command install of the MCP server + skill. Free. Live once on `master`. |
| Anthropic plugin directory (claude.ai/directory) | **Yes** | The official place Claude Code users browse. Needs a paid claude.ai plan and a review. |
| Official MCP Registry | **Yes** | Metadata only, free, permissive moderation. Aggregators and clients read from it. Needs the next PyPI release. |
| Glama | Optional | Indexes GitHub on its own. Claiming takes one file. |
| awesome-mcp-servers / awesome-claude-code | Optional | One PR each, a backlink. |
| Smithery | No | Wants an MCPB bundle or a hosted URL. sessionwiki reads local data, so hosting gives nothing, and MCPB packaging is a separate project. |
| mcp.so, Agensi and similar listing sites | No | Little traffic of the right kind; Agensi is a paid-skills shop, sessionwiki is free. |

Order: **1 → 2 → 3**, then the optional ones.

---

## What is in the repo

| File | For |
|---|---|
| `sessionwiki mcp` (in `sessionwiki/cli.py`) | Starts the stdio MCP server. Registry clients run `uvx sessionwiki mcp`. |
| `<!-- mcp-name: io.github.necroz/sessionwiki -->` at the top of `README.md` | MCP Registry ownership check on the PyPI description. |
| `server.json` | MCP Registry entry. |
| `.claude-plugin/marketplace.json` | Marketplace; points to `./plugin`. |
| `plugin/.claude-plugin/plugin.json` | Plugin: MCP server through `uvx`, asks the user for the sessionwiki folder (`userConfig.wiki_home` → `SESSIONWIKI_HOME`). |
| `plugin/skills/sessionwiki/SKILL.md` | Tells the agent when and how to use the MCP tools. |
| `glama.json` | Glama listing claim. |

`tests/test_distribution_manifests.py` keeps the versions in `plugin.json` and
`server.json` equal to `__version__` and checks the links between these files.
Maintainer-only commands and skills stay in `.claude/` and do not ship.

**Minimum version:** the `mcp` subcommand and the `mcp-name` line ship from
2.0.2. The plugin and `server.json` need 2.0.2 or later on PyPI.

---

## 1. Claude Code plugin marketplace (this repo)

Docs: <https://code.claude.com/docs/en/plugin-marketplaces>,
<https://code.claude.com/docs/en/plugins-reference>

No submission needed: the marketplace is live once the files are on `master`.

### Check before the release

```bash
claude plugin validate ./plugin --strict
```

```bash
claude plugin validate . --strict
```

Test the install from the local checkout:

```bash
claude plugin marketplace add ./
```

```bash
claude plugin install sessionwiki@sessionwiki
```

Claude Code asks for the sessionwiki folder. In a new session, `/mcp` lists
`sessionwiki`.

### Users install with

```
/plugin marketplace add necroz/sessionwiki
/plugin install sessionwiki@sessionwiki
```

These lines are in the README MCP section.

---

## 2. Submit to the Anthropic plugin directory

Docs: <https://claude.com/docs/plugins/submit#submit-a-plugin>

1. Finish step 1. `claude plugin validate ./plugin --strict`
   must pass.
2. `plugin.json` already has `documentationUrl`, `supportUrl` and
   `privacyPolicyUrl` (→ `docs/privacy.md`). The listing icon is `plugin/.claude-plugin/icon.png` (source: `docs/images/plugin-icon.svg`); the directory takes it only on the first submission.
3. Open <https://claude.ai/directory/manage> (needs Pro, Max, Ultra, or a
   Team/Enterprise owner account).
4. Submit the GitHub repo. The portal runs its own checks on top of the CLI ones;
   fix what it reports and resubmit.

---

## 3. Publish to the official MCP Registry

Docs: <https://modelcontextprotocol.io/registry/quickstart>,
<https://modelcontextprotocol.io/registry/package-types>.
The registry is in preview: breaking changes and data resets may happen.

### 3.1 `server.json`

`server.json` is at the repo root. It runs the PyPI package as
`uvx sessionwiki mcp` and asks for `SESSIONWIKI_HOME`.

- `description` is limited to 100 characters by the schema.
- `version` must be new for every publish. A published version cannot be changed.
  To fix only metadata, publish `X.Y.Z-1` with the package `version` still `X.Y.Z`.
- Version ranges (`^`, `~`, `>=`) are rejected.

### 3.2 Install the publisher

```bash
curl -L "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_$(uname -s | tr '[:upper:]' '[:lower:]')_$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/').tar.gz" | tar xz mcp-publisher && sudo mv mcp-publisher /usr/local/bin/
```

### 3.3 Publish

After the release is on PyPI:

```bash
mcp-publisher validate
```

```bash
mcp-publisher login github
```

```bash
mcp-publisher publish
```

`login github` shows a device code for <https://github.com/login/device>. The
`io.github.necroz/` prefix works only when you log in as `necroz`.

### 3.4 Automate later (optional)

Docs: <https://modelcontextprotocol.io/registry/github-actions>.
Add a job to the release workflow, after the PyPI upload, with
`permissions: id-token: write`, then `mcp-publisher login github-oidc` and
`mcp-publisher publish`. Set `server.json` versions from the tag first, for example
with `jq`.

---

## 4. Optional

### Glama

Glama lists public MCP repos on its own. `glama.json` at the repo root names
`necroz` as maintainer. Open the server page on <https://glama.ai/mcp/servers>, press **Claim**, and
fill in the build form (Python, `pip install sessionwiki`, command
`sessionwiki mcp`) so their checks can start the server.

### Awesome lists

One PR each, following each list's CONTRIBUTING:

- <https://github.com/punkpeye/awesome-mcp-servers> — category "Knowledge & Memory".
- <https://github.com/hesreallyhim/awesome-claude-code> — uses an issue form for
  submissions; read its README first.

---

## On every release

`RELEASE_PROCESS.md` lists the steps: bump the versions in
`plugin/.claude-plugin/plugin.json` and `server.json`, then run
`mcp-publisher publish` after the PyPI upload.
