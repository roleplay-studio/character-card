"""Field mapping shared by V1 and V2/V3 parsers.

Both specs surface the same logical fields (``name``, ``personality``,
``scenario``, …) just under different wrappers — V2/V3 wraps them in
a ``data`` object, V1 puts them at the top level. Once the wrapper
is unwrapped, the mapping into :class:`CharacterCardData` is
identical, so we keep it in one place to avoid drift between the
two parsers.

This module is the spec-compliance gate. It honours every MUST in
the V2/V3 specs:

- ``data.extensions`` is preserved verbatim (the spec marks it as
  MANDATORY and forbids editors from destroying unknown keys).
- ``character_book`` is preserved as an opaque dict (the spec
  forbids destroying unknown keys on entries, including the
  per-entry ``extensions`` dict and the V3 ``use_regex`` flag).
- ``creator_notes`` is kept **separate** from ``description`` —
  the V2 spec says ``creator_notes`` **MUST NOT** be used inside
  prompts. Earlier versions of this module merged the two with a
  "— Creator Notes —" separator; that was a spec violation, now
  removed. Consumers that need a merged view for display must do
  it themselves, downstream, at the UI layer.
- V3-specific fields (``assets``, ``nickname``, ``creation_date``,
  ``modification_date``, ``source``, ``creator_notes_multilingual``,
  ``group_only_greetings``) are extracted to dedicated dataclass
  fields so they survive round-trips.
"""

from __future__ import annotations

from ..models import CharacterCardData, CharacterCardParseError


def map_fields(
    data: dict,
    file_bytes: bytes,
    spec_version: str,
) -> CharacterCardData:
    """Map a spec-version-shaped ``data`` dict to :class:`CharacterCardData`.

    Caller is responsible for unwrapping the ``data`` wrapper
    (V2/V3 puts it under a top-level ``data`` key; V1 keeps fields
    at the top level — V1 passes the top-level dict directly).
    """
    name = (data.get("name") or "").strip()
    if not name:
        raise CharacterCardParseError("Character card has no name")

    first_mes = (data.get("first_mes") or "").strip()
    alt_greetings = [g.strip() for g in (data.get("alternate_greetings") or []) if g and g.strip()]
    # V1/V2/V3 few-shot dialogue examples. Stored as-is (raw V2 string).
    # The frontend parses for display; the orchestrator injects verbatim.
    mes_example = (data.get("mes_example") or "").strip()
    if not first_mes and not alt_greetings:
        # V3 may satisfy this via group_only_greetings instead.
        group_only = data.get("group_only_greetings") or []
        if not (spec_version == "3.0" and any(g and g.strip() for g in group_only)):
            raise CharacterCardParseError("Character card has no greeting messages")

    # ── Logical fields ──────────────────────────────────────────────
    base_personality = (data.get("personality") or "").strip()
    sys_prompt = (data.get("system_prompt") or "").strip()
    post_hist = (data.get("post_history_instructions") or "").strip()
    description = (data.get("description") or "").strip()
    # creator_notes is kept SEPARATE per V2 MUST NOT ("MUST NOT be used
    # inside prompts"). Earlier implementations merged it into
    # description with a "— Creator Notes —" separator; that was a
    # spec violation. The dataclass exposes both fields so callers
    # that need to display them together can do so at the UI layer.
    creator_notes = (data.get("creator_notes") or "").strip()

    # ── Identity / metadata (MUST NOT in prompts) ──────────────────
    creator = (data.get("creator") or "").strip()
    character_version = (data.get("character_version") or "").strip()

    # ── Tags (deduped, non-empty, case-sensitive order preserved) ──
    tags: list[str] = []
    seen: set[str] = set()
    for tag in data.get("tags") or []:
        cleaned = (tag or "").strip()
        if cleaned and cleaned not in seen:
            tags.append(cleaned)
            seen.add(cleaned)

    # ── character_book: full opaque bag + flattened content view ───
    char_book_raw = data.get("character_book")
    if isinstance(char_book_raw, dict):
        character_book = dict(char_book_raw)  # shallow copy — caller can mutate freely
    elif char_book_raw is None:
        character_book = None
    else:
        # Spec says character_book is an object; coerce anything else to None
        # rather than raising — we want liberal parsing.
        character_book = None

    knowledge: list[str] = []
    if character_book is not None:
        for entry in character_book.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            content = (entry.get("content") or "").strip()
            if content:
                knowledge.append(content)

    # ── V2 data.extensions: preserve as opaque dict ────────────────
    raw_ext = data.get("extensions")
    if isinstance(raw_ext, dict):
        extensions = dict(raw_ext)
    else:
        # Spec mandates a default of {}. Missing / null / non-dict → {}.
        extensions = {}

    # ── V3-only fields (all optional) ──────────────────────────────
    assets_raw = data.get("assets")
    assets = [dict(a) for a in assets_raw] if isinstance(assets_raw, list) else None

    nickname = (data.get("nickname") or "").strip()

    creation_date = data.get("creation_date")
    if not isinstance(creation_date, int):
        creation_date = None

    modification_date = data.get("modification_date")
    if not isinstance(modification_date, int):
        modification_date = None

    source_raw = data.get("source")
    source = [str(s) for s in source_raw] if isinstance(source_raw, list) else None

    multilingual_raw = data.get("creator_notes_multilingual")
    if isinstance(multilingual_raw, dict):
        creator_notes_multilingual = {str(k): str(v) for k, v in multilingual_raw.items()}
    else:
        creator_notes_multilingual = None

    group_only = [g.strip() for g in (data.get("group_only_greetings") or []) if g and g.strip()]

    return CharacterCardData(
        # Logical
        name=name,
        description=description,
        personality=base_personality,
        scenario=(data.get("scenario") or "").strip(),
        first_message=first_mes,
        alternate_greetings=alt_greetings,
        mes_example=mes_example,
        system_prompt=sys_prompt,
        post_history_instructions=post_hist,
        creator_notes=creator_notes,
        tags=tags,
        character_book_entries=knowledge,
        # Identity / metadata
        creator=creator,
        character_version=character_version,
        # Opaque spec bags
        extensions=extensions,
        character_book=character_book,
        # V3-only
        assets=assets,
        nickname=nickname,
        creation_date=creation_date,
        modification_date=modification_date,
        source=source,
        creator_notes_multilingual=creator_notes_multilingual,
        group_only_greetings=group_only,
        # Transport / diagnostics
        avatar_bytes=file_bytes,
        spec_version=spec_version,
    )
