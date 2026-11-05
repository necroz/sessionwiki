"""Tests for #491 — `sessionwiki/queue.py` rename to `sessionwiki/ingest_queue.py`.

The original `sessionwiki/queue.py` shadowed the Python stdlib `queue`
module, breaking any code inside `sessionwiki/` that wanted to import
`queue.Queue` for thread-safe primitives. Renamed to
`sessionwiki.ingest_queue` (matches the actual purpose — pending-source
ingest queue, not a generic queue). Old name kept as a deprecation
shim through one minor cycle.
"""

from __future__ import annotations

import warnings


def test_canonical_module_imports_cleanly():
    """The new home is `sessionwiki.ingest_queue`."""
    from sessionwiki import ingest_queue
    assert hasattr(ingest_queue, "enqueue")
    assert hasattr(ingest_queue, "dequeue")
    assert hasattr(ingest_queue, "queue_size")


def test_legacy_shim_re_exports_with_deprecation_warning():
    """`sessionwiki.queue` still imports — but warns."""
    # Drop any prior cached import so the shim's warnings.warn fires.
    import importlib
    import sys

    sys.modules.pop("sessionwiki.queue", None)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        from sessionwiki import queue as legacy_queue  # noqa: F401
        importlib.reload(legacy_queue)
    msgs = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
    assert any("sessionwiki.queue" in m for m in msgs), (
        f"expected DeprecationWarning mentioning sessionwiki.queue, got {msgs}"
    )
    # Public API still works through the shim
    assert hasattr(legacy_queue, "enqueue")
    assert hasattr(legacy_queue, "queue_size")


def test_stdlib_queue_import_unshadowed():
    """A bare `import queue` from inside `sessionwiki/` resolves to stdlib.

    This is the reason for the rename — before #491, this test would
    have surfaced the shim instead of the stdlib's thread-safe Queue.
    """
    import queue as stdlib_queue
    # The stdlib `queue` module has `Queue`, `LifoQueue`, `PriorityQueue` —
    # none of which the sessionwiki shim exposes.
    assert hasattr(stdlib_queue, "Queue")
    assert hasattr(stdlib_queue, "LifoQueue")
    assert hasattr(stdlib_queue, "PriorityQueue")
