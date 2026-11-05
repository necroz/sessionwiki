Start a local HTTP server for the built sessionwiki site.

Usage: /wiki-serve [port]

Run:

```bash
python3 -m sessionwiki serve --port ${ARGUMENTS:-8765}
```

The server binds to `127.0.0.1` only by default (localhost-only). Report the URL to the user.

**Security note**: the server exposes `site/` to anyone who can reach `127.0.0.1:<port>`. For LAN sharing, the user must explicitly pass `--host 0.0.0.0`.
