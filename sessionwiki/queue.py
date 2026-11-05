"""Back-compat shim — the queue module was renamed to ``ingest_queue``.

#491: shadowing the stdlib ``queue`` module is an anti-pattern that
breaks any code inside ``sessionwiki/`` wanting ``queue.Queue`` for
thread-safe primitives. The real implementation now lives at
``sessionwiki/ingest_queue.py``. This shim re-exports the public API so
existing third-party imports keep working through one minor cycle.

Deprecated as of v1.3.4. Remove in v1.5.
"""

from __future__ import annotations

import warnings

from sessionwiki.ingest_queue import (  # noqa: F401
    enqueue,
    dequeue,
    peek,
    clear,
    queue_size,
)

warnings.warn(
    "sessionwiki.queue is deprecated and will be removed in v1.5. "
    "Use sessionwiki.ingest_queue instead (#491).",
    DeprecationWarning,
    stacklevel=2,
)
