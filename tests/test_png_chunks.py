"""Tests for the raw PNG chunk scanner and tEXt/zTXt/iTXt decoders."""

from __future__ import annotations

from character_card.png_chunks import (
    find_text_chunks,
    find_text_value,
    scan_png_chunks,
)
from tests.helpers import (
    build_itext_chunk,
    build_raw_png_with_text_chunks,
    build_ttext_chunk,
    build_ztext_chunk,
)

# ── scan_png_chunks ───────────────────────────────────────────────────


class TestScanPngChunks:
    def test_returns_all_chunks_in_order(self) -> None:
        png = build_raw_png_with_text_chunks(
            [
                build_ttext_chunk("name", "Luna"),
                build_ttext_chunk("personality", "Quiet."),
            ]
        )
        chunks = scan_png_chunks(png)
        types = [ctype for ctype, _ in chunks]
        # IHDR + our 2 tEXt + IDAT + IEND
        assert types == ["IHDR", "tEXt", "tEXt", "IDAT", "IEND"]

    def test_ignores_png_signature(self) -> None:
        png = build_raw_png_with_text_chunks([])
        chunks = scan_png_chunks(png)
        # We never want the 8-byte signature showing up as a chunk.
        assert all(ctype != "" for ctype, _ in chunks)

    def test_handles_truncated_buffer(self) -> None:
        """When the buffer is truncated mid-chunk, the scanner still
        reports the chunk we managed to read but stops at the next
        iteration (no IndexError, no infinite loop).
        """
        import struct

        sig = b"\x89PNG\r\n\x1a\n"
        ihdr = struct.pack(">I", 13) + b"IHDR" + b"\x00" * 13 + struct.pack(">I", 0)
        # Fake chunk header claiming 1000 bytes but only 4 follow.
        truncated = struct.pack(">I", 1000) + b"tEXt" + b"abc"
        png = sig + ihdr + truncated

        chunks = scan_png_chunks(png)
        types = [ctype for ctype, _ in chunks]
        # IHDR scans cleanly; the truncated tEXt is appended with whatever
        # bytes are available, then the loop breaks when the next chunk
        # header overruns the buffer.
        assert "IHDR" in types
        assert "IEND" not in types  # the loop did not reach a valid end


# ── find_text_chunks / find_text_value ────────────────────────────────


class TestFindTextChunks:
    def test_reads_text_chunk(self) -> None:
        png = build_raw_png_with_text_chunks(
            [build_ttext_chunk("name", "Luna"), build_ttext_chunk("age", "eternal")]
        )
        chunks = scan_png_chunks(png)
        out = find_text_chunks(chunks)
        assert ("name", "Luna") in out
        assert ("age", "eternal") in out

    def test_reads_ztext_chunk(self) -> None:
        png = build_raw_png_with_text_chunks(
            [build_ztext_chunk("chara", "compressed-payload-here")]
        )
        chunks = scan_png_chunks(png)
        out = find_text_chunks(chunks)
        assert ("chara", "compressed-payload-here") in out

    def test_reads_itext_chunk_uncompressed(self) -> None:
        png = build_raw_png_with_text_chunks(
            [build_itext_chunk("name", "Puro", language="en", translated_keyword="Name")]
        )
        chunks = scan_png_chunks(png)
        out = find_text_chunks(chunks)
        assert ("name", "Puro") in out

    def test_reads_itext_chunk_compressed(self) -> None:
        png = build_raw_png_with_text_chunks([build_itext_chunk("name", "Puro", compressed=True)])
        chunks = scan_png_chunks(png)
        out = find_text_chunks(chunks)
        assert ("name", "Puro") in out

    def test_skips_ttext_with_no_null_separator(self) -> None:
        # Malformed tEXt with no keyword delimiter is silently skipped.
        png = build_raw_png_with_text_chunks([(b"tEXt", b"no-null-separator-here")])
        chunks = scan_png_chunks(png)
        assert find_text_chunks(chunks) == []

    def test_skips_ztext_with_invalid_zlib(self) -> None:
        png = build_raw_png_with_text_chunks([(b"zTXt", b"chara\x00\x00not-actually-zlib")])
        chunks = scan_png_chunks(png)
        assert find_text_chunks(chunks) == []

    def test_skips_ztext_with_non_deflate_compression(self) -> None:
        # comp_method != 0 — non-spec, must be skipped.
        png = build_raw_png_with_text_chunks([(b"zTXt", b"chara\x00\x99" + b"\x00" * 8)])
        chunks = scan_png_chunks(png)
        assert find_text_chunks(chunks) == []

    def test_find_text_value_returns_first_match(self) -> None:
        png = build_raw_png_with_text_chunks([build_ttext_chunk("name", "Luna")])
        chunks = scan_png_chunks(png)
        assert find_text_value(chunks, "name") == "Luna"
        assert find_text_value(chunks, "missing") is None

    def test_find_text_value_returns_first_when_duplicated(self) -> None:
        # Multiple chunks with the same keyword — we return the first.
        png = build_raw_png_with_text_chunks(
            [build_ttext_chunk("name", "First"), build_ttext_chunk("name", "Second")]
        )
        chunks = scan_png_chunks(png)
        assert find_text_value(chunks, "name") == "First"
