"""Payload decoders for the three encoding variants of character cards.

Character card payloads can show up in three on-wire encodings
(the order below is what we try, in order of cheapness):

1. **Plain JSON** — the chunk value is itself JSON text. Rare in
   practice but cheap to try first.
2. **Base64 + JSON** — the chunk value is base64-decoded into JSON.
   Some authors (JanitorAI in particular) skip the zlib layer.
3. **Base64 + zlib + JSON** — the SillyTavern V2/V3 standard
   encoding. ``zlib.decompress(base64.b64decode(text))`` gives JSON.

Each function returns the parsed JSON object on success or ``None``
if the encoding didn't apply; :func:`decode_payload` chains them.
"""

from __future__ import annotations

import base64
import binascii
import json
import zlib


def try_json(raw: str) -> dict | None:
    """Try parsing ``raw`` as a JSON object."""
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def try_base64_json(raw: str) -> dict | None:
    """Try ``base64 → JSON``."""
    try:
        decoded = base64.b64decode(raw)
        value = json.loads(decoded)
    except (TypeError, ValueError, binascii.Error):
        return None
    return value if isinstance(value, dict) else None


def try_zlib_json(raw: str) -> dict | None:
    """Try ``base64 → zlib → JSON`` (V2/V3 standard)."""
    try:
        decoded = base64.b64decode(raw)
        decompressed = zlib.decompress(decoded)
        value = json.loads(decompressed)
    except (TypeError, ValueError, binascii.Error, zlib.error):
        return None
    return value if isinstance(value, dict) else None


def decode_payload(raw: str, *, try_zlib: bool = True) -> dict | None:
    """Chain the three strategies; return the first successful parse.

    ``try_zlib=False`` skips the zlib step. Useful for V1 cards where
    no version of the spec uses zlib and we don't want to pay for a
    guaranteed zlib.error on every malformed chunk.
    """
    candidate = try_json(raw)
    if candidate is not None:
        return candidate
    candidate = try_base64_json(raw)
    if candidate is not None:
        return candidate
    if try_zlib:
        return try_zlib_json(raw)
    return None
