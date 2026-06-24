"""Tests for embed_card_in_png (SillyTavern-compatible dual-write embed).

The embedder writes BOTH ``chara`` (V2) and ``ccv3`` (V3) chunks
into the same PNG, base64-encoded without zlib (matching the
SillyTavern reference parser). The dispatcher reads V3 first when
both are present, so round-tripped cards report spec_version = 3.0.
"""

from __future__ import annotations

import base64
import json
import zlib

from character_card import (
    CharacterCardData,
    build_character_card_json,
    embed_card_in_png,
    parse_character_card,
)
from character_card.png_chunks import find_text_chunks, scan_png_chunks
from tests.helpers import build_base_png
from tests.test_builder import FakeBot


def _b64_zlib_json(payload: dict) -> str:
    """Legacy (pre-fix) encoding: base64(zlib(json))."""
    return base64.b64encode(zlib.compress(json.dumps(payload).encode("utf-8"))).decode("ascii")


def _b64_json(payload: dict) -> str:
    """SillyTavern-compatible encoding: base64(json)."""
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


class TestEmbedRoundTrip:
    def test_embed_then_parse_recovers_card(self) -> None:
        """Bot → V2 payload → embed in PNG → parse back: all fields match.

        The dispatcher reads V3 (ccv3) first when both chunks are
        present, so the result is reported as spec_version "3.0" —
        but all the V2 field semantics survive the round-trip.
        """
        bot = FakeBot(
            id=7,
            name="Luna the Dream Weaver",
            description="A mystical weaver of dreams.",
            personality="Gentle, wise, ethereal.",
            scenario="A moonlit garden.",
            first_message="Welcome, traveler.",
            categories=json.dumps(["Fantasy", "Mystic"]),
            alternate_greetings=json.dumps(["Alt greeting 1", "Alt greeting 2"]),
            bot_type="rp",
        )
        card_json = build_character_card_json(bot, knowledge_contents=["Lore one", "Lore two"])

        base_png = build_base_png()
        out_bytes = embed_card_in_png(base_png, card_json)

        # The output is a valid PNG
        assert isinstance(out_bytes, bytes)
        assert len(out_bytes) > 0

        # Round-trip: parse the embedded card and verify all the data.
        result = parse_character_card(out_bytes)
        assert isinstance(result, CharacterCardData)
        assert result.name == "Luna the Dream Weaver"
        assert result.first_message == "Welcome, traveler."
        assert result.alternate_greetings == ["Alt greeting 1", "Alt greeting 2"]
        # Knowledge entries from character_book survive the round trip.
        assert "Lore one" in result.character_book_entries
        assert "Lore two" in result.character_book_entries
        # Build/persist identity survives — extensions round-trip.
        # The dispatcher reads V3 (ccv3) first, so spec_version is "3.0".
        # V3 spec wraps the same V2 data so all V2 fields are intact.
        assert result.spec_version == "3.0"
        assert result.extensions.get("roleplay_studio_bot_id") == 7
        assert result.extensions.get("roleplay_studio_bot_type") == "rp"
        # Full character_book structure survives (entries keep their
        # extensions dicts, not just content).
        assert result.character_book is not None
        assert result.character_book["extensions"] == {}
        assert len(result.character_book["entries"]) == 2
        for entry in result.character_book["entries"]:
            assert entry["extensions"] == {}
            assert entry["enabled"] is True

    def test_preserves_existing_text_chunks(self) -> None:
        """Embedding a card must not clobber unrelated tEXt chunks.

        Uses raw chunk scanning (the SillyTavern-style embedder
        doesn't go through PIL's PngInfo, so img.info may not see
        our chunks; we walk the chunk stream directly instead).
        """
        base_png = build_base_png(extra_text={"Software": "CustomSoftware"})

        bot = FakeBot(name="X", first_message="hi")
        card_json = build_character_card_json(bot, knowledge_contents=[])

        out_bytes = embed_card_in_png(base_png, card_json)

        chunks = scan_png_chunks(out_bytes)
        text_chunks = dict(find_text_chunks(chunks))
        # The pre-existing 'Software' chunk is still there.
        assert text_chunks.get("Software") == "CustomSoftware"
        # …and our 'chara' + 'ccv3' chunks were added.
        assert "chara" in text_chunks
        assert "ccv3" in text_chunks

    def test_embed_with_no_existing_chunks(self) -> None:
        """Embedding into a plain PNG (no prior tEXt) must still round-trip."""
        base_png = build_base_png()  # no extra tEXt chunks

        bot = FakeBot(
            id=99,
            name="PlainPNG",
            description="d",
            personality="p",
            scenario="s",
            first_message="hello",
            categories=json.dumps(["tag1"]),
            alternate_greetings=json.dumps(["alt1"]),
        )
        card_json = build_character_card_json(bot, knowledge_contents=["kn1"])

        out_bytes = embed_card_in_png(base_png, card_json)
        result = parse_character_card(out_bytes)

        assert result.name == "PlainPNG"
        assert result.first_message == "hello"
        assert result.alternate_greetings == ["alt1"]
        assert result.character_book_entries == ["kn1"]
        # Dispatcher reads V3 first; chara + ccv3 are both in the PNG.
        assert result.spec_version == "3.0"


class TestSillyTavernCompat:
    """Behavioural parity with the SillyTavern reference parser."""

    def test_dual_writes_chara_and_ccv3_chunks(self) -> None:
        """SillyTavern reference: on export, both ``chara`` and ``ccv3``
        chunks are written into the same PNG. Verify we do the same.
        """
        bot = FakeBot(name="Luna", first_message="hi")
        card_json = build_character_card_json(bot, knowledge_contents=[])
        out_bytes = embed_card_in_png(build_base_png(), card_json)

        chunks = scan_png_chunks(out_bytes)
        text_chunks = dict(find_text_chunks(chunks))
        assert "chara" in text_chunks
        assert "ccv3" in text_chunks

    def test_ccv3_chunk_uses_v3_spec_envelope(self) -> None:
        """The ``ccv3`` chunk must have spec=chara_card_v3 / spec_version=3.0."""
        bot = FakeBot(name="Luna", first_message="hi")
        card_json = build_character_card_json(bot, knowledge_contents=[])
        out_bytes = embed_card_in_png(build_base_png(), card_json)

        chunks = scan_png_chunks(out_bytes)
        text_chunks = dict(find_text_chunks(chunks))
        ccv3_decoded = json.loads(base64.b64decode(text_chunks["ccv3"]))
        assert ccv3_decoded["spec"] == "chara_card_v3"
        assert ccv3_decoded["spec_version"] == "3.0"
        # The V2 data sub-object is preserved.
        assert ccv3_decoded["data"]["name"] == "Luna"

    def test_chara_chunk_uses_v2_spec_envelope(self) -> None:
        """The ``chara`` chunk keeps the caller's spec/spec_version
        (typically V2), not the V3 envelope.
        """
        bot = FakeBot(name="Luna", first_message="hi")
        card_json = build_character_card_json(bot, knowledge_contents=[])
        out_bytes = embed_card_in_png(build_base_png(), card_json)

        chunks = scan_png_chunks(out_bytes)
        text_chunks = dict(find_text_chunks(chunks))
        chara_decoded = json.loads(base64.b64decode(text_chunks["chara"]))
        assert chara_decoded["spec"] == "chara_card_v2"
        assert chara_decoded["spec_version"] == "2.0"

    def test_no_zlib_compression(self) -> None:
        """SillyTavern reference: payload is base64(utf-8(json)),
        NOT base64(zlib(json)). Cards we write must be readable
        by a SillyTavern-style reader that doesn't try zlib.
        """
        bot = FakeBot(name="Luna", first_message="hi")
        card_json = build_character_card_json(bot, knowledge_contents=[])
        out_bytes = embed_card_in_png(build_base_png(), card_json)

        chunks = scan_png_chunks(out_bytes)
        text_chunks = dict(find_text_chunks(chunks))
        # If we were still using zlib, base64-decode would produce
        # a zlib-compressed byte stream, not a JSON string. Decoding
        # directly as utf-8 must yield valid JSON.
        chara_raw = base64.b64decode(text_chunks["chara"])
        payload = json.loads(chara_raw.decode("utf-8"))
        assert payload["spec"] == "chara_card_v2"
        assert payload["data"]["name"] == "Luna"

    def test_strips_existing_chara_chunks(self) -> None:
        """SillyTavern reference: existing chara/ccv3 chunks are
        stripped before writing, so calling embed twice is
        idempotent (no chunk accumulation).
        """
        bot = FakeBot(name="Luna", first_message="hi")
        card_json = build_character_card_json(bot, knowledge_contents=[])

        # First embed.
        out1 = embed_card_in_png(build_base_png(), card_json)
        chunks1 = scan_png_chunks(out1)
        text1 = dict(find_text_chunks(chunks1))
        assert "chara" in text1
        assert "ccv3" in text1

        # Second embed on top — the old chunks must be gone, not duplicated.
        out2 = embed_card_in_png(out1, card_json)
        chunks2 = scan_png_chunks(out2)
        text2 = dict(find_text_chunks(chunks2))
        # chara and ccv3 are keywords, not chunk types — so count via
        # find_text_chunks, not by chunk type filtering.
        assert "chara" in text2, "chara keyword missing after second embed"
        assert "ccv3" in text2, "ccv3 keyword missing after second embed"
        # Exactly one chara and one ccv3 (no stale duplicates).
        chara_count = sum(1 for k, _ in find_text_chunks(chunks2) if k == "chara")
        ccv3_count = sum(1 for k, _ in find_text_chunks(chunks2) if k == "ccv3")
        assert chara_count == 1, f"expected 1 chara, got {chara_count}"
        assert ccv3_count == 1, f"expected 1 ccv3, got {ccv3_count}"

    def test_strips_legacy_zlib_chara_chunks(self) -> None:
        """Cards written by older versions of this library used
        base64(zlib(json)). When the new embed runs on them, the
        old chunk must be replaced (not kept alongside the new one).
        """
        # Hand-craft a PNG with the legacy zlib-encoded chara chunk.
        legacy_payload = {"spec": "chara-card-v2", "spec_version": "2.0", "data": {"name": "Old"}}
        legacy_b64 = _b64_zlib_json(legacy_payload)
        # Use a raw chunk build via PIL since we need a starting PNG.
        from PIL import Image
        from PIL.PngImagePlugin import PngInfo

        img = Image.new("RGB", (32, 32), color="red")
        meta = PngInfo()
        meta.add_text("chara", legacy_b64)
        buf = __import__("io").BytesIO()
        img.save(buf, format="PNG", pnginfo=meta)
        legacy_png = buf.getvalue()

        # Verify the legacy chunk is present.
        chunks = scan_png_chunks(legacy_png)
        text_chunks = dict(find_text_chunks(chunks))
        assert "chara" in text_chunks

        # New embed on top — the old chara must be gone, replaced with
        # the new base64(json) chara.
        bot = FakeBot(name="NewBot", first_message="hi")
        new_payload = build_character_card_json(bot, knowledge_contents=[])
        out = embed_card_in_png(legacy_png, new_payload)

        out_chunks = scan_png_chunks(out)
        out_text = dict(find_text_chunks(out_chunks))
        chara_count = sum(1 for k, _ in find_text_chunks(out_chunks) if k == "chara")
        assert chara_count == 1, f"expected 1 chara, got {chara_count}"
        # The chara we read back is the NEW one (base64+json, not zlib).
        new_decoded = json.loads(base64.b64decode(out_text["chara"]))
        assert new_decoded["spec"] == "chara_card_v2"
        assert new_decoded["data"]["name"] == "NewBot"

    def test_pure_pil_based_chunks_preserved(self) -> None:
        """Pre-existing non-card tEXt chunks (like 'Software') survive
        the embed intact.
        """
        base_png = build_base_png(extra_text={"Software": "CustomSoftware", "Author": "Alice"})

        bot = FakeBot(name="Luna", first_message="hi")
        card_json = build_character_card_json(bot, knowledge_contents=[])

        out_bytes = embed_card_in_png(base_png, card_json)

        text_chunks = dict(find_text_chunks(scan_png_chunks(out_bytes)))
        assert text_chunks.get("Software") == "CustomSoftware"
        assert text_chunks.get("Author") == "Alice"


class TestNonPngInput:
    """Regression: ``embed_card_in_png`` must accept non-PNG image bytes
    (JPEG, WEBP, GIF) and produce a valid PNG-with-card on the output.

    Before the fix, the embedder assumed PNG bytes and ran them through
    ``scan_png_chunks`` directly — for JPEG/WEBP that yields garbage
    "chunks", and the output is a corrupted file with a PNG signature
    prepended but unparseable JPEG/WEBP bytes trailing it. PIL/browsers
    reject the file outright.
    """

    def test_jpeg_input_produces_valid_png_with_card(self) -> None:
        """A JPEG byte stream → embed_card_in_png → valid PNG that PIL
        can open AND that round-trips back to the card.
        """
        from io import BytesIO

        from PIL import Image

        # Build a real JPEG (the kind an avatar upload might produce).
        img = Image.new("RGB", (64, 64), color=(180, 120, 90))
        jpeg_buf = BytesIO()
        img.save(jpeg_buf, format="JPEG", quality=85)
        jpeg_bytes = jpeg_buf.getvalue()

        # Sanity: input is actually a JPEG.
        assert jpeg_bytes[:3] == b"\xff\xd8\xff"

        bot = FakeBot(name="JpegBot", first_message="hi from jpeg")
        card_json = build_character_card_json(bot, knowledge_contents=["j1"])

        out_bytes = embed_card_in_png(jpeg_bytes, card_json)

        # Output must be a valid PNG that PIL can open and reload.
        out_img = Image.open(BytesIO(out_bytes))
        out_img.load()
        assert out_img.format == "PNG"

        # Card round-trips back.
        result = parse_character_card(out_bytes)
        assert result.name == "JpegBot"
        assert result.first_message == "hi from jpeg"
        assert result.character_book_entries == ["j1"]

    def test_webp_input_produces_valid_png_with_card(self) -> None:
        """Same as the JPEG test, for WEBP."""
        from io import BytesIO

        from PIL import Image

        img = Image.new("RGB", (64, 64), color=(50, 200, 100))
        webp_buf = BytesIO()
        img.save(webp_buf, format="WEBP", quality=85)
        webp_bytes = webp_buf.getvalue()

        # Sanity: input is actually WEBP (RIFF....WEBP).
        assert webp_bytes[:4] == b"RIFF" and webp_bytes[8:12] == b"WEBP"

        bot = FakeBot(name="WebpBot", first_message="hi from webp")
        card_json = build_character_card_json(bot, knowledge_contents=["w1"])

        out_bytes = embed_card_in_png(webp_bytes, card_json)

        out_img = Image.open(BytesIO(out_bytes))
        out_img.load()
        assert out_img.format == "PNG"

        result = parse_character_card(out_bytes)
        assert result.name == "WebpBot"
        assert result.first_message == "hi from webp"
        assert result.character_book_entries == ["w1"]
