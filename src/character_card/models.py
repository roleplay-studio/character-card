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
    4. **Normalised lorebook fields** — parallel lists derived from
       ``character_book['entries']`` that translate Risu / JanitorAI
       aliases (``triggers``, ``disable``, ``order``, etc.) into
       spec-shaped values (``keys``, ``enabled``,
       ``insertion_order``, …) so consumers don't have to know
       which authoring tool wrote the card.

    ``character_book_entries`` is a **convenience projection** of
    ``character_book["entries"]`` that flattens out just the
    ``content`` strings, deduped, empty-filtered. The full entries
    (with their ``keys``, ``insertion_order``, ``enabled``,
    ``position``, etc.) live in ``character_book`` for any consumer
    that needs selective lorebook activation. The parallel
    ``character_book_*`` normalised lists offer the same
    activation metadata but in a unified spec shape regardless
    of whether the card was written with the V2 spec or a
    Risu / JanitorAI tool.
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

    # ── Normalised lorebook (Risu / JanitorAI / mixed → V2 spec) ─────
    # Parallel to ``character_book['entries']``. Each list is the
    # same length as ``character_book['entries']`` (or empty when
    # there is no lorebook). The i-th element corresponds to the
    # i-th entry on the opaque bag and is derived from either the
    # spec-shaped fields on that entry, or — if absent — from the
    # Risu / JanitorAI aliases (``triggers``, ``keysecondary``,
    # ``disable``, ``order`` / ``displayIndex``, ``probability``,
    # ``caseSensitive``).
    #
    # ``character_book`` is preserved byte-for-byte for round-trip;
    # these lists are a derived view. Other entry fields
    # (``content``, ``selective``, ``constant``, ``comment``,
    # ``extensions``, ``use_regex``, Risu extensions like
    # ``addMemo`` / ``cooldown`` / ``probability``) live only on
    # the original opaque entry — pick whichever side matches
    # your consumer's needs.
    character_book_keys: list[list[str]] = field(default_factory=list)
    character_book_secondary_keys: list[list[str]] = field(default_factory=list)
    character_book_enabled: list[bool] = field(default_factory=list)
    character_book_insertion_order: list[int] = field(default_factory=list)
    character_book_position: list[str] = field(default_factory=list)
    character_book_priority: list[int] = field(default_factory=list)
    character_book_case_sensitive: list[bool] = field(default_factory=list)

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
