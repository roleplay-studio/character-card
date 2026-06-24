"""Tests for tag dedup behaviour."""

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


class TestTagDedup:
    def test_tags_deduped(self) -> None:
        data = dict(SAMPLE_V2_DATA, tags=["Fantasy", "Fantasy", "Mystic", ""])
        png_bytes = build_v2_card_png(data)
        result = parse_character_card(png_bytes)
        assert result.tags == ["Fantasy", "Mystic"]
