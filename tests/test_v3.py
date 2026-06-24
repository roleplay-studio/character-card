"""V3 character card parser tests."""

from __future__ import annotations

from character_card import parse_character_card
from tests.helpers import build_v3_card_png

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
}


class TestV3Parser:
    def test_parses_v3_png(self) -> None:
        png_bytes = build_v3_card_png(SAMPLE_V2_DATA)
        result = parse_character_card(png_bytes)

        assert result.name == "Luna the Dream Weaver"
        assert result.spec_version == "3.0"
        # V3 also keeps V2 behavior — same data fields parse correctly.
        assert result.first_message == "Welcome, traveler."
        assert result.alternate_greetings == ["Another greeting", "Yet another"]

    def test_v3_group_only_greetings_kept_separate(self) -> None:
        """V3-specific ``group_only_greetings`` are kept on a dedicated
        field, **not** folded into ``alternate_greetings``. This preserves
        the V2/V3 distinction across round-trips so the orchestrator
        (or any V3-aware consumer) can surface them differently.
        """
        data = dict(
            SAMPLE_V2_DATA,
            alternate_greetings=["Solo greeting"],
            group_only_greetings=["Group only 1", "Group only 2"],
        )
        png_bytes = build_v3_card_png(data)
        result = parse_character_card(png_bytes)

        assert result.spec_version == "3.0"
        # alternate_greetings is unchanged.
        assert result.alternate_greetings == ["Solo greeting"]
        # group_only_greetings lives on its own field.
        assert result.group_only_greetings == ["Group only 1", "Group only 2"]

    def test_v3_dedupes_when_greeting_in_both(self) -> None:
        """If a greeting appears in both alternate_greetings and
        group_only_greetings, the consumer decides how to merge them.
        The library does NOT silently merge — that would lose the V3
        semantic distinction. Each list is preserved as-is.
        """
        data = dict(
            SAMPLE_V2_DATA,
            alternate_greetings=["Shared"],
            group_only_greetings=["Shared", "Group only"],
        )
        png_bytes = build_v3_card_png(data)
        result = parse_character_card(png_bytes)

        assert result.alternate_greetings == ["Shared"]
        assert result.group_only_greetings == ["Shared", "Group only"]
