"""Tests for character_book (lorebook) handling."""

from __future__ import annotations

from character_card import parse_character_card
from tests.helpers import build_v2_card_png

SAMPLE_V2_DATA: dict = {
    "name": "Luna",
    "description": "d",
    "personality": "p",
    "scenario": "s",
    "first_mes": "hi",
    "alternate_greetings": [],
}


class TestCharacterBook:
    def test_empty_content_filtered(self) -> None:
        data = dict(
            SAMPLE_V2_DATA,
            character_book={"entries": [{"content": ""}, {"content": "real"}]},
        )
        png_bytes = build_v2_card_png(data)
        result = parse_character_card(png_bytes)
        assert result.character_book_entries == ["real"]
