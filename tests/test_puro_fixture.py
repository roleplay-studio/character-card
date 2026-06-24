"""Regression: the bots_examples/puro.png fixture parses through the
unified parse_character_card entry point.

The original puro.png was a hand-rolled fixture from before the unified
parser existed. It must keep loading through parse_character_card, not
just the legacy bot_loader.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from character_card import parse_character_card

FIXTURE = Path(__file__).parent / "fixtures" / "puro.png"


@pytest.mark.skipif(not FIXTURE.is_file(), reason=f"puro.png not found at {FIXTURE}")
class TestPuroFixture:
    def test_puro_png_artifact_parses(self) -> None:
        result = parse_character_card(FIXTURE.read_bytes(), ".png")
        assert result.name == "Puro"
        assert result.spec_version == "1.0"
        # The flat tEXt layout should yield non-empty greetings.
        assert result.first_message
        assert result.personality
