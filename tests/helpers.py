"""Test helpers — build tiny PNGs with character-card metadata embedded.

These are the library-side equivalent of the helpers that lived in
``tests/test_character_card_parser.py`` in the main project. They are
intentionally self-contained (no fixtures) so each test is a self-
documenting recipe for the on-disk format it exercises.

Chunk encodings:

- **V2/V3** — ``chara`` (V2) or ``ccv3`` (V3) tEXt chunk carrying
  ``base64(zlib(json))``. The SillyTavern standard.
- **V1 (chara tEXt)** — same tEXt chunk, but the JSON has no
  ``data`` wrapper.
- **V1 flat** — one tEXt chunk per field, no JSON envelope.

For tEXt/zTXt/iTXt coverage we also have small builders that emit
those variants directly (no PIL involved).
"""

from __future__ import annotations

import base64
import json
import struct
import zlib
from io import BytesIO
from typing import Any

from PIL import Image
from PIL.PngImagePlugin import PngInfo

# ── V1 / V2 / V3 card PNGs (via PIL) ──────────────────────────────────


def build_v2_card_png(
    card_data: dict,
    png_size: tuple[int, int] = (64, 64),
    color: tuple[int, int, int] = (100, 150, 200),
) -> bytes:
    """Build a PNG with a V2 character card embedded in a ``chara`` tEXt chunk.

    The payload is wrapped in the V2 envelope
    ``{"spec": "chara_card_v2", "spec_version": "2.0", "data": ...}``,
    JSON-encoded, zlib-compressed, base64-encoded — the standard
    SillyTavern V2 encoding.
    """
    payload = {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": card_data,
    }
    return _embed_text_png("chara", _b64_zlib_json(payload), png_size=png_size, color=color)


def build_v3_card_png(
    card_data: dict,
    png_size: tuple[int, int] = (64, 64),
    color: tuple[int, int, int] = (100, 150, 200),
) -> bytes:
    """Build a PNG with a V3 character card embedded in a ``ccv3`` tEXt chunk.

    V3 wraps the same ``data`` payload as V2 but uses the newer
    ``ccv3`` keyword and ``spec_version: "3.0"``.
    """
    payload = {
        "spec": "chara-card-v3",
        "spec_version": "3.0",
        "data": card_data,
    }
    return _embed_text_png("ccv3", _b64_zlib_json(payload), png_size=png_size, color=color)


def build_v1_chara_card_png(
    card_data: dict,
    png_size: tuple[int, int] = (32, 32),
    color: str = "red",
) -> bytes:
    """Build a PNG with a V1 (chara tEXt, flat JSON, no ``data`` wrapper) card."""
    return _embed_text_png("chara", _b64_zlib_json(card_data), png_size=png_size, color=color)


def build_flat_card_png(
    fields: dict[str, str],
    png_size: tuple[int, int] = (16, 16),
    color: tuple[int, int, int] = (80, 80, 80),
) -> bytes:
    """Build a PNG with one tEXt chunk per field — V1 flat layout."""
    img = Image.new("RGB", png_size, color=color)
    meta = PngInfo()
    for k, v in fields.items():
        meta.add_text(k, v)
    buf = BytesIO()
    img.save(buf, format="PNG", pnginfo=meta)
    return buf.getvalue()


def build_base_png(
    png_size: tuple[int, int] = (64, 64),
    color: tuple[int, int, int] = (200, 100, 50),
    extra_text: dict[str, str] | None = None,
) -> bytes:
    """Build a plain PNG (optionally with extra tEXt chunks)."""
    img = Image.new("RGB", png_size, color=color)
    if extra_text:
        meta = PngInfo()
        for key, value in extra_text.items():
            meta.add_text(key, value)
        buf = BytesIO()
        img.save(buf, format="PNG", pnginfo=meta)
        return buf.getvalue()
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── Raw-chunk builders (PIL-free, for png_chunks tests) ───────────────


def build_raw_png_with_text_chunks(
    chunks: list[tuple[bytes, bytes]],
    width: int = 1,
    height: int = 1,
) -> bytes:
    """Build a minimal PNG by hand, splicing in custom chunks.

    ``chunks`` is a list of ``(chunk_type_bytes, chunk_data_bytes)``.
    Chunks are placed after the IHDR, before a single IDAT carrying a
    solid black pixel. The result is a valid PNG that PIL can also
    round-trip.

    This is used to build PNGs with tEXt/zTXt/iTXt variants that PIL
    doesn't expose a high-level API for.
    """
    out = bytearray()
    out += b"\x89PNG\r\n\x1a\n"

    def _emit(chunk_type: bytes, data: bytes) -> None:
        out.extend(struct.pack(">I", len(data)))
        out.extend(chunk_type)
        out.extend(data)
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        out.extend(struct.pack(">I", crc))

    # IHDR
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    _emit(b"IHDR", ihdr_data)

    # Custom chunks
    for ctype, cdata in chunks:
        _emit(ctype, cdata)

    # IDAT — single solid black pixel (filter byte 0 + 3 zero bytes per row)
    raw = b"\x00" + b"\x00\x00\x00" * (width * height)
    idat = zlib.compress(raw)
    _emit(b"IDAT", idat)

    _emit(b"IEND", b"")
    return bytes(out)


def build_ttext_chunk(keyword: str, text: str) -> tuple[bytes, bytes]:
    """Return ``(b"tEXt", keyword\\0text)`` for use with :func:`build_raw_png_with_text_chunks`."""
    return (b"tEXt", keyword.encode("latin-1") + b"\x00" + text.encode("latin-1"))


def build_ztext_chunk(keyword: str, text: str) -> tuple[bytes, bytes]:
    """Return ``(b"zTXt", keyword\\0\\0<deflate-compressed text>)``."""
    compressed = zlib.compress(text.encode("latin-1"))
    return (b"zTXt", keyword.encode("latin-1") + b"\x00\x00" + compressed)


def build_itext_chunk(
    keyword: str,
    text: str,
    *,
    compressed: bool = False,
    language: str = "",
    translated_keyword: str = "",
) -> tuple[bytes, bytes]:
    """Return an iTXt chunk payload (keyword\\0flag<1>method<1>lang\\0trans\\0text)."""
    flag = 1 if compressed else 0
    parts = (
        keyword.encode("latin-1")
        + b"\x00"
        + bytes([flag, 0])  # comp_flag, comp_method=0 (deflate)
        + language.encode("utf-8")
        + b"\x00"
        + translated_keyword.encode("utf-8")
        + b"\x00"
        + (zlib.compress(text.encode("utf-8")) if compressed else text.encode("utf-8"))
    )
    return (b"iTXt", parts)


# ── Internal ──────────────────────────────────────────────────────────


def _b64_zlib_json(payload: dict) -> str:
    raw = json.dumps(payload).encode("utf-8")
    return base64.b64encode(zlib.compress(raw)).decode("ascii")


def _embed_text_png(
    keyword: str,
    value: str,
    png_size: tuple[int, int],
    color: Any,
) -> bytes:
    img = Image.new("RGB", png_size, color=color)
    meta = PngInfo()
    meta.add_text(keyword, value)
    buf = BytesIO()
    img.save(buf, format="PNG", pnginfo=meta)
    return buf.getvalue()
