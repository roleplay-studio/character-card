"""Shared dataclasses and exceptions for character card I/O.

These types live in their own module so that the parsers, builder, and
embedder can all depend on them without circular imports. The caller
reads :class:`CharacterCardData` via :func:`parse_character_card`; the
export path writes a V2 JSON payload back through
:func:`build_character_card_json`.

The dataclass surfaces both the "logical" fields the rest of the
application cares about (``name``, ``personality``, ``first_message``,
``scenario``, …) and the **opaque spec-shaped bags** the spec requires
us to preserve (``extensions``, ``character_book``, ``assets``,
``source``, etc.). Downstream code that doesn't need spec fidelity
can ignore the opaque bags; code that does need them has them.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class CharacterCardParseError(ValueError):
    """Raised when a character card cannot be parsed from the given bytes."""


@dataclass
class CharacterCardData:
    """Parsed character card fields. Mirrors the V1/V2/V3 spec.

    The fields here come in three flavours:

    1. **Logical fields** the rest of the application reads directly
       (``name``, ``personality``, ``scenario``, ``first_message``,
       ``alternate_greetings``, ``mes_example``, ``system_prompt``,
       ``post_history_instructions``, ``creator_notes``, ``tags``,
       ``character_book_entries``).
    2. **Identity / metadata** the spec marks as MUST NOT use in
       prompts (``creator``, ``character_version``).
    3. **Opaque spec bags** the spec requires us to preserve but
       the application doesn't interpret (``extensions``,
       ``character_book``, plus all V3-specific fields).

    ``character_book_entries`` is a **convenience projection** of
    ``character_book["entries"]`` that flattens out just the
    ``content`` strings, deduped, empty-filtered. The full entries
    (with their ``keys``, ``insertion_order``, ``enabled``,
    ``position``, etc.) live in ``character_book`` for any consumer
    that needs selective lorebook activation.
    """

    # ── Logical fields (V1 + V2 + V3) ─────────────────────────────────
    name: str
    description: str
    personality: str
    scenario: str
    first_message: str
    alternate_greetings: list[str] = field(default_factory=list)
    mes_example: str = ""  # V1/V2/V3 few-shot dialogue examples (raw string)
    system_prompt: str = ""
    post_history_instructions: str = ""
    creator_notes: str = ""
    tags: list[str] = field(default_factory=list)
    character_book_entries: list[str] = field(default_factory=list)

    # ── Identity / metadata (spec MUST NOT use in prompts) ───────────
    creator: str = ""
    character_version: str = ""

    # ── Opaque spec bags (must preserve on round-trip) ───────────────
    # V2 data.extensions — Record<string, any>. Builder writes
    # ``roleplay_studio_bot_id`` etc. here; parser returns the full
    # dict so re-imports of our own exports preserve identity.
    extensions: dict = field(default_factory=dict)
    # V2 character_book — full structure (name, scan_depth, entries
    # with keys/position/priority/...). ``character_book_entries``
    # above is a flattened convenience view.
    character_book: dict | None = None

    # ── V3-only fields (all optional) ────────────────────────────────
    # V3 spec: assets, nickname, creation_date, modification_date,
    # source, creator_notes_multilingual, group_only_greetings.
    # We keep V2's semantics for alternate_greetings (the orchestrator
    # surfaces them as swipe options) and store group_only_greetings
    # separately so the round-trip doesn't lose the distinction.
    assets: list[dict] | None = None
    nickname: str = ""
    creation_date: int | None = None
    modification_date: int | None = None
    source: list[str] | None = None
    creator_notes_multilingual: dict[str, str] | None = None
    group_only_greetings: list[str] = field(default_factory=list)

    # ── Transport / diagnostics ──────────────────────────────────────
    # Raw avatar bytes for re-saving (the original file bytes if no
    # separate avatar is embedded in the card).
    avatar_bytes: bytes | None = None
    # One of "1.0", "2.0", "3.0".
    spec_version: str = "2.0"
