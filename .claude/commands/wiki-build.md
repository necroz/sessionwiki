Regenerate the static HTML site for the sessionwiki.

Usage: /wiki-build [--synthesize]

Run:

```bash
python3 -m sessionwiki build $ARGUMENTS
```

The `--synthesize` flag (optional) calls the `claude` CLI once to generate an Overview paragraph for the home page.

Report the output directory (default: `site/`), the total number of HTML files, and total size.

Remind the user they can browse the result with `/wiki-serve` (starts a local HTTP server on port 8765).
