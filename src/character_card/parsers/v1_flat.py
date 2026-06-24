"""V1 flat-tEXt layout parser.

This is the original "V1" layout used by SillyTavern before the
``chara`` envelope was introduced: every character card field lives
in its **own** PNG metadata chunk under a stable keyword (``name``,
``personality``, ``first_message``, ``scenario``, ``description``,
``system_prompt``, ``post_history_instructions``, ``creator_notes``,
``categories``/``tags``, ``alternate_greetings``). No JSON wrapper.

We accept tEXt / zTXt / iTXt — iTXt was previously skipped by the
parser package, which made some hand-rolled fixtures (JanitorAI
exports, our own wizard helper) unloadable through the
``character_card`` API even though the legacy ``bot_loader`` could
read them. See :mod:`png_chunks`.

The flat layout is **not** a SillyTavern-V2-compliant V1 card; the
V2 spec calls for a ``chara`` envelope. We treat it as a separate
format with a dedicated parser so the dispatcher can try V2/V3
first and only fall back here when no envelope is present.
"""

from __future__ import annotations

import json

from ..models import CharacterCardData, CharacterCardParseError
from ..png_chunks import find_text_value, scan_png_chunks
from ._fields import map_fields

# Mapping from "PNG tEXt keyword" → "V2 field name in our dataclass".
# V2 field names are used as the keys in the dict we hand to
# :func:`_fields.map_fields` so we share the mapper with the other
# parsers.
_KEYWORD_TO_FIELD: dict[str, str] = {
    "name": "name",
    "personality": "personality",
    "scenario": "scenario",
    "first_mes": "first_mes",
    "first_message": "first_mes",
    "description": "description",
    "system_prompt": "system_prompt",
    "post_history_instructions": "post_history_instructions",
    "creator_notes": "creator_notes",
    "tags": "tags",
    "categories": "tags",
    "alternate_greetings": "alternate_greetings",
}


def _read_flat_payload(file_bytes: bytes) -> dict | None:
    """Pull a flat field dict from raw PNG metadata chunks.

    Returns ``None`` if no recognised keywords are present. Caller
    decides whether absence of fields is an error (it is, in
    :func:`parse_v1_flat` — we raise).
    """
    try:
        chunks = scan_png_chunks(file_bytes)
    except Exception:
        return None

    out: dict = {}
    for keyword, field in _KEYWORD_TO_FIELD.items():
        text = find_text_value(chunks, keyword)
        if text is None:
            continue
        # Tags / categories may be a JSON list (a bot written by a
        # sophisticated tool) or a comma-separated string (hand-rolled
        # fixtures like puro.png). Accept both.
        if field == "tags":
            stripped = text.strip()
            try:
                parsed = json.loads(stripped)
            except (TypeError, ValueError):
                parsed = [c.strip() for c in stripped.split(",") if c.strip()]
            if isinstance(parsed, list):
                out[field] = [str(c).strip() for c in parsed if str(c).strip()]
            continue
        if field == "alternate_greetings":
            stripped = text.strip()
            try:
                parsed = json.loads(stripped)
            except (TypeError, ValueError):
                # Pipe-separated is another convention seen in the wild.
                parsed = [g.strip() for g in stripped.split("|") if g.strip()]
            if isinstance(parsed, list):
                out[field] = [str(g).strip() for g in parsed if str(g).strip()]
            continue
        out[field] = text

    return out or None


def try_parse_v1_flat(file_bytes: bytes) -> CharacterCardData | None:
    """Try to parse a flat-layout (one tEXt chunk per field) PNG.

    Returns ``None`` if no recognised keywords are present. Field-
    validation errors (missing ``name``, no greeting) still raise
    — those mean the bytes are clearly intended as a card, just
    an invalid one.
    """
    payload = _read_flat_payload(file_bytes)
    if payload is None or "name" not in payload:
        return None

    # Reuse the shared field mapper. It validates the required fields
    # (``name`` + at least one greeting) and folds creator_notes into
    # description the way the V2/V3 parsers do.
    return map_fields(payload, file_bytes, spec_version="1.0")


def parse_v1_flat(file_bytes: bytes) -> CharacterCardData:
    """Parse a flat-layout (one tEXt chunk per field) PNG, raising on failure.

    Public alias for callers (per-version unit tests) that want the
    old "raise on payload-not-found" contract. The dispatcher uses
    :func:`try_parse_v1_flat` so it can fall back when this layout
    isn't present either.
    """
    card = try_parse_v1_flat(file_bytes)
    if card is None:
        raise CharacterCardParseError("No character card data found in image")
    return card
