"""Tests for the parse_character_card dispatcher — routing across parsers."""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from character_card import CharacterCardParseError, parse_character_card
from tests.helpers import (
    build_flat_card_png,
    build_v1_chara_card_png,
    build_v2_card_png,
    build_v3_card_png,
)

SAMPLE_V2_DATA: dict = {
    "name": "Luna the Dream Weaver",
    "description": "A mystical weaver of dreams.",
    "personality": "Gentle, wise, ethereal.",
    "scenario": "A moonlit garden.",
    "first_mes": "Welcome, traveler.",
    "system_prompt": "Speak in poetic verse.",
    "post_history_instructions": "End each turn with a question.",
    "alternate_greetings": ["Another greeting", "Yet another"],
    "tags": ["Fantasy", "Mystic"],
    "creator_notes": "Inspired by H.P. Lovecraft.",
    "character_book": {
        "entries": [
            {"content": "The moon garden glows with silver light."},
            {"content": ""},  # empty → filtered
            {"content": "Whispers echo from the well."},
        ]
    },
}


class TestDispatcherRouting:
    """End-to-end routing: ``parse_character_card`` picks the right
    parser for each on-disk layout.
    """

    def test_v2_png_routes_to_v2(self) -> None:
        png_bytes = build_v2_card_png(SAMPLE_V2_DATA)
        result = parse_character_card(png_bytes)
        assert result.spec_version == "2.0"

    def test_v3_ccv3_png_routes_to_v3(self) -> None:
        png_bytes = build_v3_card_png(SAMPLE_V2_DATA)
        result = parse_character_card(png_bytes)
        assert result.spec_version == "3.0"

    def test_v1_chara_flat_json_routes_to_v1(self) -> None:
        """V1 spec: chara tEXt chunk holding a flat JSON object
        (no ``data`` wrapper).
        """
        v1_payload = {
            "name": "Old Bot",
            "description": "d",
            "personality": "p",
            "first_mes": "hi",
        }
        png_bytes = build_v1_chara_card_png(v1_payload)
        result = parse_character_card(png_bytes)
        assert result.spec_version == "1.0"
        assert result.name == "Old Bot"

    def test_v1_flat_text_routes_to_v1_flat(self) -> None:
        """V1 flat: one tEXt chunk per field, no JSON envelope."""
        png_bytes = build_flat_card_png(
            {
                "name": "Puro",
                "personality": "Quiet.",
                "first_message": "Hi.",
                "scenario": "Shop.",
            }
        )
        result = parse_character_card(png_bytes)
        assert result.spec_version == "1.0"
        assert result.name == "Puro"


class TestParserErrors:
    def test_no_chara_chunk_raises(self) -> None:
        """PNG without 'chara'/'ccv3' → CharacterCardParseError."""
        img = Image.new("RGB", (32, 32), color="red")
        buf = BytesIO()
        img.save(buf, format="PNG")
        with pytest.raises(CharacterCardParseError):
            parse_character_card(buf.getvalue())

    def test_empty_name_raises(self) -> None:
        bad = {"name": "", "personality": "p", "first_mes": "hi"}
        png_bytes = build_v2_card_png(bad)
        with pytest.raises(CharacterCardParseError, match="no name"):
            parse_character_card(png_bytes)

    def test_no_greetings_raises(self) -> None:
        bad = {
            "name": "X",
            "personality": "p",
            "first_mes": "",
            "alternate_greetings": [],
        }
        png_bytes = build_v2_card_png(bad)
        with pytest.raises(CharacterCardParseError, match="greeting"):
            parse_character_card(png_bytes)

    def test_invalid_png_raises(self) -> None:
        """Random non-PNG bytes → CharacterCardParseError."""
        with pytest.raises(CharacterCardParseError):
            parse_character_card(b"not a png file at all, just garbage")
