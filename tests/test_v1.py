"""V1 (chara tEXt + flat JSON) parser tests + V1 flat-tEXt layout tests."""

from __future__ import annotations

import pytest

from character_card import CharacterCardParseError, parse_character_card
from tests.helpers import build_flat_card_png, build_v1_chara_card_png

# ── V1 (chara tEXt, flat JSON, no data wrapper) ──────────────────────


class TestV1Parser:
    def test_parses_v1_no_data_wrapper(self) -> None:
        """V1 cards have fields at the top level, not under 'data'."""
        v1: dict = {
            "name": "Old Bot",
            "description": "d",
            "personality": "p",
            "first_mes": "hi",
        }
        png_bytes = build_v1_chara_card_png(v1)
        result = parse_character_card(png_bytes)

        assert result.name == "Old Bot"
        assert result.spec_version == "1.0"
        assert result.first_message == "hi"


# ── V1 flat tEXt layout (one chunk per field) ────────────────────────


class TestV1FlatParser:
    def test_parses_v1_flat_png(self) -> None:
        """One tEXt chunk per field, no JSON wrapper.

        Matches the format of ``bots_examples/puro.png``.
        """
        png_bytes = build_flat_card_png(
            {
                "name": "Puro",
                "personality": "Soft-spoken bookshop catgirl.",
                "first_message": "*looks up* Oh.",
                "scenario": "A quiet bookshop at night.",
                "description": "Puro runs a small bookshop.",
            }
        )
        result = parse_character_card(png_bytes)
        assert result.spec_version == "1.0"
        assert result.name == "Puro"
        assert result.personality == "Soft-spoken bookshop catgirl."
        assert result.first_message == "*looks up* Oh."
        assert result.scenario == "A quiet bookshop at night."

    def test_v1_flat_categories_comma_separated(self) -> None:
        """Hand-rolled fixtures often store categories as a
        comma-separated string. The parser accepts that.
        """
        png_bytes = build_flat_card_png(
            {
                "name": "Puro",
                "personality": "Quiet.",
                "first_message": "Hi.",
                "scenario": "Shop.",
                "categories": "Slice of Life, Literary, Quiet",
            }
        )
        result = parse_character_card(png_bytes)
        assert result.tags == ["Slice of Life", "Literary", "Quiet"]

    def test_v1_flat_categories_json_list(self) -> None:
        """Sophisticated writers sometimes emit tags as a JSON list
        in a tEXt chunk. The parser also accepts that.
        """
        png_bytes = build_flat_card_png(
            {
                "name": "Puro",
                "personality": "Quiet.",
                "first_message": "Hi.",
                "scenario": "Shop.",
                "tags": '["Slice of Life", "Literary"]',
            }
        )
        result = parse_character_card(png_bytes)
        assert result.tags == ["Slice of Life", "Literary"]

    def test_v1_flat_no_data_raises(self) -> None:
        """A PNG with no recognised keywords is not a card."""
        png_bytes = build_flat_card_png({"author": "ignored", "software": "also ignored"})
        with pytest.raises(CharacterCardParseError, match="No character card data"):
            parse_character_card(png_bytes)

    def test_v1_flat_alternate_greetings_pipe_separated(self) -> None:
        """Some hand-rolled fixtures use ``|`` as a separator for
        alternate_greetings instead of JSON. The parser accepts that
        too because real on-disk files use both conventions.
        """
        png_bytes = build_flat_card_png(
            {
                "name": "Echo",
                "personality": "Quiet.",
                "first_message": "First.",
                "scenario": "Library.",
                "alternate_greetings": "Greeting 1 | Greeting 2 | Greeting 3",
            }
        )
        result = parse_character_card(png_bytes)
        assert result.alternate_greetings == [
            "Greeting 1",
            "Greeting 2",
            "Greeting 3",
        ]
