"""Fake secret values generated when the tests run.

The redaction tests need strings that look like real keys. A literal key
in the source trips secret scanners (gitleaks flags `token: <value>` as a
generic API key), so the tests build every value here at run time.

Each run draws a new seed, so the tests check the pattern shape, not one
fixed string. After a failure pytest prints the seed; set ``FAKE_SECRET_SEED`` to
repeat that run.
"""

from __future__ import annotations

import os
import random
import string

SEED = int(os.environ.get("FAKE_SECRET_SEED") or random.SystemRandom().randrange(2**32))
_rng = random.Random(SEED)

ALNUM = string.ascii_letters + string.digits
BASE64URL = ALNUM + "_-"


def fake(length: int, alphabet: str = ALNUM) -> str:
    """A random string. It starts and ends with a letter or digit, so a
    `\\b` or a value-start rule in a pattern always sees a token edge."""
    if length <= 0:
        return ""
    if length <= 2:
        return "".join(_rng.choice(ALNUM) for _ in range(length))
    middle = "".join(_rng.choice(alphabet) for _ in range(length - 2))
    return _rng.choice(ALNUM) + middle + _rng.choice(ALNUM)


def fake_jwt() -> str:
    """Three base64url segments; header and payload start with `eyJ`."""
    return ".".join(["eyJ" + fake(33, BASE64URL), "eyJ" + fake(41, BASE64URL), fake(43, BASE64URL)])


def fake_pem_body(lines: int = 8) -> list[str]:
    """Base64 lines as in a PEM private key; distinct, so each can be
    looked up on its own."""
    return [fake(62) + f"{n:02d}" for n in range(lines)]
