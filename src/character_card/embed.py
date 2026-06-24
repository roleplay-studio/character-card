"""Embed a character card JSON payload into a PNG image.

SillyTavern-compatible embedder. We follow the reference
implementation at
https://github.com/SillyTavern/SillyTavern/blob/release/src/character-card-parser.js
closely:

- The payload is encoded as ``base64(utf-8(json))`` — **no zlib**.
  This matches what SillyTavern's own writer emits. The downside
  is slightly larger PNGs (~30% bigger card payload); the upside
  is that any SillyTavern-compatible reader (Risu, Agnai,
  JanitorAI, hand-rolled tools) can load the card without
  having to try zlib as a fallback.
- Both ``chara`` (V2) and ``ccv3`` (V3) chunks are written into
  the same PNG, with the V3 payload having ``spec: "chara_card_v3"``
  and ``spec_version: "3.0"``. The dual-write matches the
  SillyTavern reference so older (V2-only) readers still see the
  card, and V3 readers get the richer V3 metadata. When the
  same PNG is read back, V3 (ccv3) takes priority (the dispatcher
  in :mod:`parsers` honours this).
- Pre-existing ``chara``/``ccv3`` tEXt chunks are **removed**
  before writing — otherwise repeated embeds would accumulate
  stale chunks. The SillyTavern reference does the same.
- All other tEXt chunks (``Software``, ``Author``, etc.) are
  preserved. Non-tEXt chunks (IDAT, IHDR, IEND, PLTE, iCCP, etc.)
  are passed through unchanged. The IDAT (pixel data) is
  preserved exactly as PIL wrote it; we never re-encode the
  image.

This implementation walks the PNG chunk stream directly rather
than going through PIL's ``PngInfo`` API. PIL's API doesn't let
us (a) remove existing ``chara`` chunks, (b) control chunk
ordering, or (c) compute CRC32 ourselves. Walking chunks is
what the SillyTavern reference does, and it's the only way to
match its behaviour exactly.
"""

from __future__ import annotations

import base64
import io
import json
import struct
import zlib

from PIL import Image

from .png_chunks import scan_png_chunks

# PNG file signature (8 bytes).
_PNG_SIG = b"\x89PNG\r\n\x1a\n"

# Chunk keywords we own. Both are written on every embed so that
# V2-only and V3 readers can both load the card. The V3 payload
# has spec/spec_version set to V3; the V2 payload keeps the
# caller's chosen spec/spec_version (typically V2).
_CHARA_KEY = b"chara"
_CCV3_KEY = b"ccv3"


def embed_card_in_png(image_bytes: bytes, card_json: dict) -> bytes:
    """Embed a character card JSON into a PNG as ``chara`` and ``ccv3`` chunks.

    The payload is JSON-encoded (UTF-8), base64-encoded, and written
    verbatim — no zlib, matching the SillyTavern reference. The
    V3 copy is derived from the V2 payload by setting
    ``spec = "chara_card_v3"`` and ``spec_version = "3.0"`` (only
    top-level fields; the ``data`` sub-object is shared). If the
    payload already has ``spec == "chara_card_v3"`` we still write
    the V2 copy because most V2 readers expect the V2 envelope.

    Pre-existing ``chara`` and ``ccv3`` tEXt chunks are stripped
    first, so calling this twice on the same bytes is idempotent.
    All other chunks (including any other tEXt chunks like
    ``Software``) are preserved in place.

    The input may be any image format PIL can open (PNG, JPEG, WEBP,
    GIF, BMP, …). Non-PNG inputs are re-encoded to PNG before
    embedding, so the function always produces a valid PNG on the
    output. For PNG inputs the IDAT/pixel data is preserved exactly
    as PIL wrote it — we never re-encode a PNG.
    """
    image_bytes = _ensure_png_bytes(image_bytes)
    chunks = scan_png_chunks(image_bytes)

    # ── Build the V2 payload (what the caller handed us) ───────────
    v2_payload_bytes = json.dumps(card_json, ensure_ascii=False).encode("utf-8")
    v2_b64 = base64.b64encode(v2_payload_bytes).decode("ascii")

    # ── Build the V3 payload (V2 with spec/spec_version promoted) ─
    # We always overwrite spec/spec_version on the V3 copy, regardless
    # of what the caller had — the ccv3 chunk must identify itself as
    # V3 per the spec, even if the caller mistakenly passed a V2
    # envelope (or vice versa).
    v3_card_json = dict(card_json)
    v3_card_json["spec"] = "chara_card_v3"
    v3_card_json["spec_version"] = "3.0"
    v3_payload_bytes = json.dumps(v3_card_json, ensure_ascii=False).encode("utf-8")
    v3_b64 = base64.b64encode(v3_payload_bytes).decode("ascii")

    # ── Assemble the new chunk stream ──────────────────────────────
    out = bytearray()
    out += _PNG_SIG

    # Walk the original chunks, skipping any chara/ccv3 tEXt chunks
    # we own. We split the stream at the IEND chunk so we can splice
    # our own chara + ccv3 tEXt chunks in just before it (SillyTavern
    # writes them with `splice(-1, 0, ...)` for the same reason).
    #
    # chara / ccv3 are *keywords* inside tEXt chunks, not chunk
    # types — so we have to decode the tEXt data to inspect the
    # keyword. Format: ``keyword\\0text`` in Latin-1. Empty keyword
    # (no NUL byte) is a malformed chunk we should leave alone.
    body = bytearray()
    for chunk_type, chunk_data in chunks:
        # scan_png_chunks decodes the chunk type to str for ergonomics;
        # we need bytes to feed the writer.
        chunk_type_bytes = chunk_type.encode("ascii")
        if chunk_type == "IEND":
            continue
        if chunk_type == "tEXt":
            # Inspect the keyword.
            null_idx = chunk_data.find(b"\x00")
            if null_idx > 0:
                keyword = chunk_data[:null_idx]
                if keyword in (_CHARA_KEY, _CCV3_KEY):
                    continue
        body += _emit_chunk(chunk_type_bytes, chunk_data)

    # Insert our owned chunks just before IEND.
    body += _emit_text_chunk(_CHARA_KEY, v2_b64)
    body += _emit_text_chunk(_CCV3_KEY, v3_b64)
    # IEND last.
    body += _emit_chunk(b"IEND", b"")

    out += body
    return bytes(out)


def _emit_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Build a complete PNG chunk: length(4) | type(4) | data | crc(4)."""
    length = struct.pack(">I", len(data))
    crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    return length + chunk_type + data + crc


def _emit_text_chunk(keyword: bytes, text: str) -> bytes:
    """Build a tEXt chunk with the given keyword and Latin-1 text.

    tEXt is keyword\\0text, both Latin-1. The SillyTavern reference
    uses base64(utf-8(json)) for the text portion; base64 only
    contains ASCII characters, so Latin-1 is sufficient.
    """
    return _emit_chunk(b"tEXt", keyword + b"\x00" + text.encode("latin-1"))


def _ensure_png_bytes(image_bytes: bytes) -> bytes:
    """Return ``image_bytes`` unchanged if it is already a PNG,
    otherwise re-encode it through PIL as a PNG.

    The embedder walks the PNG chunk stream directly (see module
    docstring), so it requires PNG bytes to function. Without this
    normalization, callers that pass JPEG/WEBP/GIF bytes — which
    is the common case for bot avatar uploads — would get a corrupt
    file out: a PNG signature prepended to the original JPEG/WEBP
    bytes, which PIL and browsers cannot decode.

    PNG inputs are passed through untouched so that the IDAT
    (pixel data) and any non-card tEXt chunks survive byte-for-byte.
    PIL's own PNG re-encoder drops custom tEXt chunks (it has no
    ``format=PNG, pnginfo=...`` we could thread through cleanly
    while still avoiding a second scan), so we want to avoid that
    round-trip whenever possible.
    """
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return image_bytes

    # Non-PNG: re-encode through PIL. This loses any non-PNG metadata
    # (EXIF, XMP, …) but the embedder never had a way to preserve
    # those anyway — the card data goes into a tEXt chunk on the
    # re-encoded PNG, not the original image. The visible pixels
    # survive intact.
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
        # Convert modes PIL can't write as PNG (e.g. CMYK JPEGs).
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
