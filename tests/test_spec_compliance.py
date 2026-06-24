"""Tests for spec-compliance behaviour: extensions, character_book, V3 fields.

These tests guard the fixes for the spec compliance audit. They cover:

- ``data.extensions`` round-trip (V2 MUST NOT destroy unknown keys)
- ``character_book`` opaque preservation (V2 MUST NOT destroy entry
  metadata like ``keys``, ``position``, ``use_regex``)
- ``creator_notes`` separation from ``description`` (V2 MUST NOT
  use creator_notes in prompts)
- ``creator`` and ``character_version`` round-trip (V2 string types)
- V3-only fields: ``assets``, ``nickname``, ``creation_date``,
  ``modification_date``, ``source``, ``creator_notes_multilingual``
"""

from __future__ import annotations

from character_card import (
    build_character_card_json,
    embed_card_in_png,
    parse_character_card,
)
from tests.helpers import build_base_png, build_v2_card_png, build_v3_card_png
from tests.test_builder import FakeBot

# ── Extensions round-trip (Fix #2) ───────────────────────────────────


class TestExtensionsRoundTrip:
    def test_v2_extensions_preserved(self) -> None:
        """V2 spec MUST: ``data.extensions`` is preserved verbatim."""
        data = {
            "name": "Luna",
            "first_mes": "hi",
            "personality": "p",
            "scenario": "s",
            "description": "d",
            "extensions": {
                "custom_key": "custom_value",
                "numeric_key": 42,
                "nested": {"deep": "object"},
            },
        }
        png = build_v2_card_png(data)
        result = parse_character_card(png)
        assert result.extensions == {
            "custom_key": "custom_value",
            "numeric_key": 42,
            "nested": {"deep": "object"},
        }

    def test_v2_extensions_default_empty_when_missing(self) -> None:
        """V2 spec MUST: extensions default to {} when absent."""
        data = {
            "name": "Luna",
            "first_mes": "hi",
            "personality": "p",
            "scenario": "s",
            "description": "d",
        }
        png = build_v2_card_png(data)
        result = parse_character_card(png)
        assert result.extensions == {}

    def test_v2_extensions_default_empty_when_null(self) -> None:
        """Defensive: null extensions → {} rather than None."""
        data = {
            "name": "Luna",
            "first_mes": "hi",
            "personality": "p",
            "scenario": "s",
            "description": "d",
            "extensions": None,
        }
        png = build_v2_card_png(data)
        result = parse_character_card(png)
        assert result.extensions == {}

    def test_extensions_round_trip_through_embed(self) -> None:
        """Our own ``roleplay_studio_bot_id`` survives parse → embed → parse."""
        bot = FakeBot(
            id=99,
            name="Re-Import",
            description="d",
            personality="p",
            scenario="s",
            first_message="hi",
        )
        payload = build_character_card_json(bot, knowledge_contents=[])
        png = embed_card_in_png(build_base_png(), payload)
        result = parse_character_card(png)
        assert result.extensions.get("roleplay_studio_bot_id") == 99
        assert result.extensions.get("roleplay_studio_bot_type") == "rp"


# ── character_book opaque preservation (Fix #6, #9) ──────────────────


class TestCharacterBookOpaquePreservation:
    def test_v2_character_book_top_level_fields_preserved(self) -> None:
        """V2 spec: ``CharacterBook`` carries name, scan_depth,
        token_budget, recursive_scanning, extensions, entries. We
        preserve the whole structure verbatim.
        """
        data = {
            "name": "Luna",
            "first_mes": "hi",
            "personality": "p",
            "scenario": "s",
            "description": "d",
            "character_book": {
                "name": "moon_lore",
                "description": "lore about the moon",
                "scan_depth": 5,
                "token_budget": 2048,
                "recursive_scanning": True,
                "extensions": {"book_meta": "value"},
                "entries": [
                    {
                        "keys": ["moon", "silver"],
                        "secondary_keys": ["night"],
                        "content": "The moon is silver.",
                        "enabled": True,
                        "insertion_order": 0,
                        "case_sensitive": False,
                        "selective": True,
                        "constant": False,
                        "position": "before_char",
                        "priority": 100,
                        "id": 1,
                        "name": "moon_entry",
                        "comment": "core moon lore",
                        "extensions": {"entry_meta": "entry_value"},
                    },
                ],
            },
        }
        png = build_v2_card_png(data)
        result = parse_character_card(png)
        assert result.character_book is not None
        # Top-level fields preserved.
        assert result.character_book["name"] == "moon_lore"
        assert result.character_book["scan_depth"] == 5
        assert result.character_book["token_budget"] == 2048
        assert result.character_book["recursive_scanning"] is True
        assert result.character_book["extensions"] == {"book_meta": "value"}
        # Entry-level fields preserved (the whole entry, not just content).
        entry = result.character_book["entries"][0]
        assert entry["keys"] == ["moon", "silver"]
        assert entry["secondary_keys"] == ["night"]
        assert entry["position"] == "before_char"
        assert entry["priority"] == 100
        assert entry["extensions"] == {"entry_meta": "entry_value"}
        # Flattened convenience view still works.
        assert "The moon is silver." in result.character_book_entries

    def test_v2_character_book_missing_returns_none(self) -> None:
        data = {
            "name": "Luna",
            "first_mes": "hi",
            "personality": "p",
            "scenario": "s",
            "description": "d",
        }
        png = build_v2_card_png(data)
        result = parse_character_card(png)
        assert result.character_book is None
        assert result.character_book_entries == []

    def test_v2_character_book_entries_with_use_regex(self) -> None:
        """V3 adds ``use_regex: boolean`` as mandatory on entries. V2
        entries don't have it, but if it's there we preserve it.
        """
        data = {
            "name": "Luna",
            "first_mes": "hi",
            "personality": "p",
            "scenario": "s",
            "description": "d",
            "character_book": {
                "entries": [
                    {
                        "keys": ["moon.*"],
                        "content": "Regex-triggered entry.",
                        "enabled": True,
                        "insertion_order": 0,
                        "use_regex": True,
                    },
                ],
            },
        }
        png = build_v2_card_png(data)
        result = parse_character_card(png)
        assert result.character_book is not None
        assert result.character_book["entries"][0]["use_regex"] is True


# ── creator_notes separation (Fix #8) ───────────────────────────────


class TestCreatorNotesSeparation:
    def test_creator_notes_kept_separate_from_description(self) -> None:
        """V2 spec MUST NOT: ``creator_notes`` is not used inside prompts.
        We keep it as a separate dataclass field rather than merging
        it into ``description`` (which may end up in prompts).
        """
        data = {
            "name": "Luna",
            "first_mes": "hi",
            "personality": "p",
            "scenario": "s",
            "description": "A clean character description.",
            "creator_notes": "Recommended temperature: 0.8",
        }
        png = build_v2_card_png(data)
        result = parse_character_card(png)
        assert result.description == "A clean character description."
        assert result.creator_notes == "Recommended temperature: 0.8"
        # No merge happened.
        assert "temperature" not in result.description

    def test_creator_notes_only_description_filled(self) -> None:
        """When only creator_notes is present, description stays empty.
        Caller decides what to do (display, route into Bot.description,
        etc.).
        """
        data = {
            "name": "Luna",
            "first_mes": "hi",
            "personality": "p",
            "scenario": "s",
            "creator_notes": "Just notes.",
        }
        png = build_v2_card_png(data)
        result = parse_character_card(png)
        assert result.description == ""
        assert result.creator_notes == "Just notes."


# ── creator + character_version (Fix #5) ────────────────────────────


class TestCreatorAndVersion:
    def test_creator_and_character_version_preserved(self) -> None:
        data = {
            "name": "Luna",
            "first_mes": "hi",
            "personality": "p",
            "scenario": "s",
            "description": "d",
            "creator": "SomeAuthor",
            "character_version": "2.5",
        }
        png = build_v2_card_png(data)
        result = parse_character_card(png)
        assert result.creator == "SomeAuthor"
        assert result.character_version == "2.5"

    def test_creator_and_version_default_empty(self) -> None:
        data = {
            "name": "Luna",
            "first_mes": "hi",
            "personality": "p",
            "scenario": "s",
            "description": "d",
        }
        png = build_v2_card_png(data)
        result = parse_character_card(png)
        assert result.creator == ""
        assert result.character_version == ""


# ── V3-only fields (Fix #7) ──────────────────────────────────────────


class TestV3OnlyFields:
    def test_v3_assets_preserved(self) -> None:
        data = {
            "name": "Luna",
            "first_mes": "hi",
            "personality": "p",
            "scenario": "s",
            "description": "d",
            "assets": [
                {"type": "icon", "uri": "user://avatar.png", "name": "avatar", "ext": "png"},
                {"type": "background", "uri": "user://bg.png", "name": "bg", "ext": "png"},
            ],
        }
        png = build_v3_card_png(data)
        result = parse_character_card(png)
        assert result.assets is not None
        assert len(result.assets) == 2
        assert result.assets[0]["type"] == "icon"
        assert result.assets[1]["name"] == "bg"

    def test_v3_nickname_preserved(self) -> None:
        data = {
            "name": "Luna",
            "first_mes": "hi",
            "personality": "p",
            "scenario": "s",
            "description": "d",
            "nickname": "Moonweaver",
        }
        png = build_v3_card_png(data)
        result = parse_character_card(png)
        assert result.nickname == "Moonweaver"

    def test_v3_timestamps_preserved(self) -> None:
        data = {
            "name": "Luna",
            "first_mes": "hi",
            "personality": "p",
            "scenario": "s",
            "description": "d",
            "creation_date": 1700000000,
            "modification_date": 1700000999,
        }
        png = build_v3_card_png(data)
        result = parse_character_card(png)
        assert result.creation_date == 1700000000
        assert result.modification_date == 1700000999

    def test_v3_source_preserved(self) -> None:
        data = {
            "name": "Luna",
            "first_mes": "hi",
            "personality": "p",
            "scenario": "s",
            "description": "d",
            "source": ["https://example.com/luna", "imported-from-janitor"],
        }
        png = build_v3_card_png(data)
        result = parse_character_card(png)
        assert result.source == ["https://example.com/luna", "imported-from-janitor"]

    def test_v3_creator_notes_multilingual_preserved(self) -> None:
        data = {
            "name": "Luna",
            "first_mes": "hi",
            "personality": "p",
            "scenario": "s",
            "description": "d",
            "creator_notes_multilingual": {
                "en": "English notes",
                "ru": "Русские заметки",
            },
        }
        png = build_v3_card_png(data)
        result = parse_character_card(png)
        assert result.creator_notes_multilingual == {
            "en": "English notes",
            "ru": "Русские заметки",
        }

    def test_v3_only_fields_default_to_empty(self) -> None:
        data = {
            "name": "Luna",
            "first_mes": "hi",
            "personality": "p",
            "scenario": "s",
            "description": "d",
        }
        png = build_v3_card_png(data)
        result = parse_character_card(png)
        assert result.assets is None
        assert result.nickname == ""
        assert result.creation_date is None
        assert result.modification_date is None
        assert result.source is None
        assert result.creator_notes_multilingual is None
        assert result.group_only_greetings == []
