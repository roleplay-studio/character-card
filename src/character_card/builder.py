"""Build a V2 character card JSON payload from a Bot-like object + knowledge.

Used by the bot export endpoint to construct the JSON that gets
embedded in the bot's avatar PNG. The ``bot`` argument is duck-typed
— we only read attributes. This keeps the builder usable from tests
(with a ``FakeBot``) and from the DB model alike, without forcing a
hard import dependency on a ``Bot`` type.

The output honours every MUST in the V2 spec:

- ``spec: "chara_card_v2"`` (underscores, per spec — NOT
  ``chara-card-v2`` which is a known producer-side bug in some
  tools).
- ``spec_version: "2.0"``.
- ``data.extensions: {}`` always present (spec default).
- ``character_book.extensions: {}`` always present (spec marks it
  mandatory on the CharacterBook type).
- Each character_book entry has ``extensions: {}`` (spec marks it
  mandatory per entry).

The round-trip is intentionally lossy for some fields:

- ``system_prompt`` and ``post_history_instructions`` are exported
  as empty strings because the import service folds them into
  ``personality`` on import and doesn't split them back out.
- ``description`` carries whatever the Bot has on disk; that may be
  the V2 description or the creator notes (depending on whether
  the import consumed the description for the personality fallback).
- V3-only fields (``assets``, ``nickname``, etc.) are not exported
  by this builder — it's the V2 builder, not V3. Round-tripping a
  V3 card through this builder drops V3 extensions.
"""

from __future__ import annotations

import json


def _coerce_str_list(value: object) -> list[str]:
    """Accept either a JSON string (DB default) or a Python list.

    The ``Bot`` model stores ``categories`` and ``alternate_greetings`` as
    JSON strings, but a DTO or in-memory bot may hand us a list. Both forms
    are supported — anything else falls back to an empty list.
    """
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []
    if isinstance(value, list):
        return value
    return []


def _dedupe_tags(values: list[str]) -> list[str]:
    """Strip, drop empties, and dedupe (preserving first occurrence)."""
    tags: list[str] = []
    seen: set[str] = set()
    for raw in values:
        cleaned = (raw or "").strip()
        if cleaned and cleaned not in seen:
            tags.append(cleaned)
            seen.add(cleaned)
    return tags


def _clean_greetings(values: list[str]) -> list[str]:
    """Drop falsy/empty/whitespace-only greetings; preserve order."""
    return [g for g in values if g and g.strip()]


def build_character_card_json(
    bot: object,
    knowledge_contents: list[str],
) -> dict:
    """Build a V2 character card JSON payload from a Bot-like object + knowledge.

    The ``bot`` argument is duck-typed — we only read attributes. This keeps
    the builder usable from tests (with a ``FakeBot``) and from the DB model
    alike, without forcing a hard import dependency on ``Bot``.
    """
    categories = _coerce_str_list(getattr(bot, "categories", None))
    alt_greetings = _coerce_str_list(getattr(bot, "alternate_greetings", None))

    data: dict = {
        "name": getattr(bot, "name", "") or "",
        "description": getattr(bot, "description", "") or "",
        "personality": getattr(bot, "personality", "") or "",
        "scenario": getattr(bot, "scenario", "") or "",
        "first_message": getattr(bot, "first_message", "") or "",
        "first_mes": getattr(bot, "first_message", "") or "",
        "mes_example": getattr(bot, "mes_example", "") or "",
        "system_prompt": "",
        "post_history_instructions": "",
        "alternate_greetings": _clean_greetings(alt_greetings),
        "tags": _dedupe_tags(categories),
        "creator_notes": "",
        "character_version": "1.0",
        "creator": "Roleplay Studio",
        "extensions": {
            "roleplay_studio_bot_id": getattr(bot, "id", None),
            "roleplay_studio_bot_type": getattr(bot, "bot_type", None) or "rp",
        },
    }

    if knowledge_contents:
        # Spec mandates `extensions: {}` on CharacterBook itself
        # and on each entry. The `enabled` and `insertion_order`
        # fields on entries are mandatory in V2 (no `?` in TS).
        data["character_book"] = {
            "extensions": {},
            "entries": [
                {
                    "content": content,
                    "enabled": True,
                    "insertion_order": i,
                    "extensions": {},
                }
                for i, content in enumerate(knowledge_contents)
                if content and content.strip()
            ],
        }

    return {
        "spec": "chara_card_v2",  # per V2 spec — underscores, not hyphens
        "spec_version": "2.0",
        "data": data,
    }
