"""V1 character card parser.

V1 has no ``data`` wrapper — the character fields are at the top
level of the JSON object. The encoding is plain JSON or
``base64+JSON`` (no zlib layer, because V1 predates the zlib spec).
The tEXt key is ``chara`` — same as V2.

V1 is rare in the wild but supported here for backward compatibility
with older bot exports.
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from ..decoders import decode_payload
from ..models import CharacterCardData, CharacterCardParseError
from ..png_chunks import find_text_value, scan_png_chunks
from ._fields import map_fields

_CHARA_KEY = "chara"


def _extract_payload(file_bytes: bytes) -> dict | None:
    """Pull the decoded JSON payload from image bytes (V1 encoding).

    V1 historically uses plain JSON or ``base64+JSON`` but the
    SillyTavern ecosystem has long emitted zlib-compressed V1
    cards in the wild (JanitorAI, some Risu exporters), so the
    decoder tries all three strategies. Spec-conformant V1 cards
    just hit the first two; zlib-compressed ones hit the third.
    """
    # Step 1: PIL — fast path.
    try:
        with Image.open(BytesIO(file_bytes)) as img:
            if _CHARA_KEY in img.info:
                candidate = decode_payload(str(img.info[_CHARA_KEY]))
                if candidate is not None:
                    return candidate
    except (OSError, ValueError, Image.UnidentifiedImageError):
        pass

    # Step 2: manual chunk scan.
    chunks = scan_png_chunks(file_bytes)
    text = find_text_value(chunks, _CHARA_KEY)
    if text is not None:
        candidate = decode_payload(text)
        if candidate is not None:
            return candidate
    return None


def try_parse_v1(file_bytes: bytes) -> CharacterCardData | None:
    """Try to parse a V1 (chara tEXt + flat JSON, no ``data`` wrapper) card.

    Returns ``None`` when no ``chara`` tEXt chunk is present or the
    payload can't be decoded. Field-validation errors (``name``
    missing, no greeting) still raise — those mean the bytes are
    clearly intended as a card, just an invalid one.
    """
    raw_card = _extract_payload(file_bytes)
    if raw_card is None:
        return None

    # V1 has no ``data`` wrapper — the fields are at the top level.
    return map_fields(raw_card, file_bytes, spec_version="1.0")


def parse_v1(file_bytes: bytes) -> CharacterCardData:
    """Parse a V1 card from image bytes, raising on any failure.

    Public alias for callers that want the old "raise on payload-not-
    found" contract (e.g. the per-version unit tests that drive
    this parser directly). The dispatcher uses :func:`try_parse_v1`
    so it can fall back to V1-flat when V1 also finds nothing.
    """
    card = try_parse_v1(file_bytes)
    if card is None:
        raise CharacterCardParseError("No character card data found in image")
    return card
