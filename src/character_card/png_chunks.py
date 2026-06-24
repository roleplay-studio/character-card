"""Raw PNG chunk scanner (fallback when PIL drops custom tEXt chunks).

PIL sometimes loses custom ``tEXt`` / ``zTXt`` chunks during
``Image.open`` (certain corrupt or non-standard PNGs). When that
happens we walk the raw PNG bytes ourselves and pull the chunks
out the same way a conformant PNG reader would. The format spec
is:

- 8-byte PNG signature.
- Then a stream of chunks: ``length(4) | type(4) | data(length) | crc(4)``.

For ``tEXt`` the chunk data is ``keyword\\0text`` (Latin-1). For
``zTXt`` it's ``keyword\\0compression_method(1)\\0compressed_text``;
we only accept compression method 0 (deflate) because that is the
only one defined in the PNG spec and the only one SillyTavern emits.

iTXt is intentionally handled (the legacy parser package skipped it,
which made some hand-rolled fixtures unloadable through the unified
API even though the legacy ``bot_loader`` could read them). The spec
lets authors emit any of the three for character card fields; in
practice tEXt is universal for SillyTavern cards but some
hand-rolled fixtures (JanitorAI exports, our own wizard helpers) use
iTXt.
"""

from __future__ import annotations

import zlib


def scan_png_chunks(data: bytes) -> list[tuple[str, bytes]]:
    """Walk raw PNG bytes and return ``(chunk_type, chunk_data)`` pairs.

    Stops at the first chunk that overruns the buffer; the caller
    decides what to do with truncated input (we surface it as a
    ``CharacterCardParseError`` in :func:`parse_character_card`).
    """
    chunks: list[tuple[str, bytes]] = []
    pos = 8  # skip PNG signature (8 bytes)
    while pos < len(data):
        if pos + 8 > len(data):
            break
        length = int.from_bytes(data[pos : pos + 4], "big")
        chunk_type = data[pos + 4 : pos + 8].decode(errors="ignore")
        chunk_data = data[pos + 8 : pos + 8 + length]
        chunks.append((chunk_type, chunk_data))
        pos += length + 12  # length(4) + type(4) + data(length) + crc(4)
    return chunks


def find_text_chunks(chunks: list[tuple[str, bytes]]) -> list[tuple[str, str]]:
    """Return ``(keyword, decoded_text)`` for tEXt, zTXt, and iTXt chunks.

    iTXt is also accepted — its compressed flag, language tag, and
    translated keyword are all preserved on disk but we only need
    the decoded text here.

    Skips chunks where the keyword delimiter (``\\0``) is missing or
    where the zlib decompression fails; those indicate a malformed
    chunk we cannot trust.
    """
    out: list[tuple[str, str]] = []
    for ctype, cdata in chunks:
        if ctype == "tEXt":
            try:
                null = cdata.index(b"\x00")
            except ValueError:
                continue
            keyword = cdata[:null].decode("latin-1", errors="ignore")
            text = cdata[null + 1 :].decode("latin-1", errors="ignore")
            out.append((keyword, text))
        elif ctype == "zTXt":
            try:
                null = cdata.index(b"\x00")
            except ValueError:
                continue
            keyword = cdata[:null].decode("latin-1", errors="ignore")
            rest = cdata[null + 1 :]
            if not rest:
                continue
            comp_method = rest[0]
            compressed = rest[1:]
            if comp_method != 0:
                continue
            try:
                text = zlib.decompress(compressed).decode("latin-1", errors="ignore")
            except zlib.error:
                continue
            out.append((keyword, text))
        elif ctype == "iTXt":
            # iTXt layout: keyword\0comp_flag(1)comp_method(1)lang_tag\0trans_keyword\0text
            # The first \0 separates the keyword. If comp_flag is set
            # the text portion is zlib-compressed.
            sep1 = cdata.find(b"\x00")
            if sep1 == -1 or len(cdata) < sep1 + 3:
                continue
            keyword = cdata[:sep1].decode("latin-1", errors="ignore")
            comp_flag = cdata[sep1 + 1]
            # Skip comp_method(1) + language_tag(\0-terminated) +
            # translated_keyword(\0-terminated) to land on the text.
            tail = cdata[sep1 + 3 :]
            sep2 = tail.find(b"\x00")
            if sep2 == -1:
                continue
            tail = tail[sep2 + 1 :]
            sep3 = tail.find(b"\x00")
            if sep3 == -1:
                continue
            text_bytes = tail[sep3 + 1 :]
            if comp_flag:
                try:
                    text_bytes = zlib.decompress(text_bytes)
                except zlib.error:
                    continue
            out.append((keyword, text_bytes.decode("utf-8", errors="ignore")))
    return out


def find_text_value(chunks: list[tuple[str, bytes]], key: str) -> str | None:
    """Convenience: scan chunks for a ``key`` tEXt/zTXt/iTXt entry and return its value."""
    for ckey, ctext in find_text_chunks(chunks):
        if ckey == key:
            return ctext
    return None
