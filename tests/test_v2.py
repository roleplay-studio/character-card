"""V2 character card parser tests."""

from __future__ import annotations

from character_card import CharacterCardData, parse_character_card
from tests.helpers import build_v2_card_png

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


class TestV2Parser:
    def test_parses_v2_png(self) -> None:
        png_bytes = build_v2_card_png(SAMPLE_V2_DATA)
        result = parse_character_card(png_bytes)

        assert isinstance(result, CharacterCardData)
        assert result.name == "Luna the Dream Weaver"
        assert result.scenario == "A moonlit garden."
        assert result.first_message == "Welcome, traveler."
        assert result.alternate_greetings == ["Another greeting", "Yet another"]
        # The parser returns the four V2 system-level fields *separately*
        # so the import service can decide how to merge them into the
        # Bot's two text columns (personality, scenario).
        assert result.personality == "Gentle, wise, ethereal."
        assert result.system_prompt == "Speak in poetic verse."
        assert result.post_history_instructions == "End each turn with a question."
        # Tags round-trip
        assert result.tags == ["Fantasy", "Mystic"]
        # Empty character_book entry filtered
        assert len(result.character_book_entries) == 2
        assert "The moon garden glows" in result.character_book_entries[0]
        # creator_notes is kept SEPARATE from description (V2 spec
        # MUST NOT: creator_notes "MUST NOT be used inside prompts").
        # Earlier implementations merged the two; that violated the
        # spec. Verify both fields are present and distinct here.
        assert "H.P. Lovecraft" in result.creator_notes
        assert "H.P. Lovecraft" not in result.description
        # Spec version comes from the spec field; our builder wraps it
        assert result.spec_version in ("2.0", "3.0")
