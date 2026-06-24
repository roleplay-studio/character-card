"""Tests for the mes_example (V1/V2/V3 few-shot dialogue examples) field."""

from __future__ import annotations

from character_card import parse_character_card
from tests.helpers import build_v2_card_png, build_v3_card_png


class TestMesExampleExtraction:
    """Verify mes_example is extracted from V2/V3 cards, defaults to empty
    when missing, and round-trips through the export pipeline.
    """

    def test_v2_card_mes_example_extracted(self) -> None:
        png = build_v2_card_png(
            {
                "name": "Test",
                "first_mes": "Hi",
                "personality": "p",
                "description": "d",
                "scenario": "s",
                "mes_example": "<START>\n{{user}}: hi\n{{char}}: hello\n<END>",
            }
        )
        result = parse_character_card(png)
        assert result.mes_example == "<START>\n{{user}}: hi\n{{char}}: hello\n<END>"

    def test_v2_card_mes_example_default_empty_when_missing(self) -> None:
        png = build_v2_card_png(
            {
                "name": "Test",
                "first_mes": "Hi",
                "personality": "p",
                "description": "d",
                "scenario": "s",
            }
        )
        result = parse_character_card(png)
        assert result.mes_example == ""

    def test_v2_card_mes_example_empty_string(self) -> None:
        png = build_v2_card_png(
            {
                "name": "Test",
                "first_mes": "Hi",
                "personality": "p",
                "description": "d",
                "scenario": "s",
                "mes_example": "",
            }
        )
        result = parse_character_card(png)
        assert result.mes_example == ""

    def test_v3_card_mes_example_extracted(self) -> None:
        png = build_v3_card_png(
            {
                "name": "Test",
                "first_mes": "Hi",
                "personality": "p",
                "description": "d",
                "scenario": "s",
                "mes_example": "<START>\n{{user}}: hi\n<END>",
            }
        )
        result = parse_character_card(png)
        assert result.mes_example == "<START>\n{{user}}: hi\n<END>"
