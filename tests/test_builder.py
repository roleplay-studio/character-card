"""Tests for build_character_card_json (Bot-like object → V2 payload)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from character_card import build_character_card_json


@dataclass
class FakeBot:
    """Minimal Bot stand-in for the builder.

    Mirrors the relevant fields of ``Bot`` in the main project. The
    builder only reads attributes, so a dataclass is sufficient.
    """

    id: int = 1
    name: str = "TestBot"
    description: str = "desc"
    personality: str = "p"
    scenario: str = "s"
    first_message: str = "hi"
    # ``categories`` and ``alternate_greetings`` may be either JSON strings
    # (how the DB stores them) or Python lists — the builder must accept both.
    categories: Any = field(default_factory=lambda: "[]")
    alternate_greetings: Any = field(default_factory=lambda: "[]")
    bot_type: str = "rp"
    mes_example: str = ""


class TestBuilder:
    def test_builds_v2_payload_from_bot(self) -> None:
        bot = FakeBot(
            id=42,
            name="TestBot",
            description="desc",
            personality="p",
            scenario="s",
            first_message="hi",
            categories=json.dumps(["Anime", "Romance"]),
            alternate_greetings=json.dumps(["alt1", "alt2"]),
            bot_type="rp",
        )

        payload = build_character_card_json(bot, knowledge_contents=["lore 1", "lore 2"])

        # Envelope — V2 spec MUSTs:
        assert payload["spec"] == "chara_card_v2"  # underscores, not hyphens
        assert payload["spec_version"] == "2.0"
        data = payload["data"]
        # Required V2 fields
        assert data["name"] == "TestBot"
        assert data["description"] == "desc"
        assert data["personality"] == "p"
        assert data["scenario"] == "s"
        assert data["first_mes"] == "hi"
        assert data["first_message"] == "hi"
        # Always-empty fields per the spec
        assert data["mes_example"] == ""
        assert data["system_prompt"] == ""
        assert data["post_history_instructions"] == ""
        assert data["creator_notes"] == ""
        assert data["character_version"] == "1.0"
        assert data["creator"] == "Roleplay Studio"
        # Tags and greetings round-trip
        assert data["tags"] == ["Anime", "Romance"]
        assert data["alternate_greetings"] == ["alt1", "alt2"]
        # Extensions — V2 spec MUST default to {}, here we use it
        # for our own bot identity tracking.
        assert data["extensions"]["roleplay_studio_bot_id"] == 42
        assert data["extensions"]["roleplay_studio_bot_type"] == "rp"
        # Knowledge → character_book with spec-MANDATORY `extensions`
        # on the book itself and on every entry.
        book = data["character_book"]
        assert book["extensions"] == {}
        assert book["entries"][0] == {
            "content": "lore 1",
            "enabled": True,
            "insertion_order": 0,
            "extensions": {},
        }
        assert book["entries"][1] == {
            "content": "lore 2",
            "enabled": True,
            "insertion_order": 1,
            "extensions": {},
        }

    def test_handles_no_knowledge(self) -> None:
        bot = FakeBot()
        payload = build_character_card_json(bot, knowledge_contents=[])
        assert "character_book" not in payload["data"]

    def test_filters_empty_knowledge_entries(self) -> None:
        bot = FakeBot()
        payload = build_character_card_json(
            bot,
            knowledge_contents=["real lore", "", "   ", "another"],
        )
        entries = payload["data"]["character_book"]["entries"]
        contents = [e["content"] for e in entries]
        assert contents == ["real lore", "another"]
        # insertion_order preserves the original index from the input list
        # (per the spec, enumerate() runs over the unfiltered sequence).
        assert [e["insertion_order"] for e in entries] == [0, 3]

    def test_dedupes_and_cleans_tags_and_greetings(self) -> None:
        bot = FakeBot(
            categories=["Fantasy", "Fantasy", "  ", "Mystic", "Mystic", "Fantasy"],
            alternate_greetings=["alt1", "", "   ", "alt2", "alt1"],
        )
        payload = build_character_card_json(bot, knowledge_contents=[])
        data = payload["data"]
        # Tags: deduped, empties removed, first occurrence preserved.
        assert data["tags"] == ["Fantasy", "Mystic"]
        # Greetings: only filter empty/whitespace — order is preserved as-is.
        assert data["alternate_greetings"] == ["alt1", "alt2", "alt1"]

    def test_handles_string_and_list_categories(self) -> None:
        # JSON-string categories (the DB default).
        bot_str = FakeBot(categories=json.dumps(["Anime", "Romance"]))
        payload_str = build_character_card_json(bot_str, knowledge_contents=[])
        assert payload_str["data"]["tags"] == ["Anime", "Romance"]

        # Python list categories (DTO or in-memory bot).
        bot_list = FakeBot(categories=["Slice of Life", "Comedy"])
        payload_list = build_character_card_json(bot_list, knowledge_contents=[])
        assert payload_list["data"]["tags"] == ["Slice of Life", "Comedy"]

    def test_uses_roleplay_studio_as_creator(self) -> None:
        bot = FakeBot()
        payload = build_character_card_json(bot, knowledge_contents=[])
        assert payload["data"]["creator"] == "Roleplay Studio"

    def test_mes_example_roundtrips_through_export(self) -> None:
        """When a bot has mes_example, build_character_card_json writes it
        back into the V2 payload under 'mes_example' (not '')."""
        bot = FakeBot(
            id=42,
            name="TestBot",
            description="d",
            personality="p",
            scenario="s",
            first_message="hi",
            categories="[]",
            alternate_greetings="[]",
            bot_type="rp",
            mes_example="<START>\n{{user}}: hi\n<END>",
        )
        payload = build_character_card_json(bot, knowledge_contents=[])
        assert payload["data"]["mes_example"] == "<START>\n{{user}}: hi\n<END>"
