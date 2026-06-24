"""V2 / V3 character card parser.

V2 and V3 share the same field layout: a top-level ``data`` object
holding all the character fields, optionally a ``character_book`` for
lorebook entries. The differences are:

- The tEXt chunk key: V2 uses ``chara``, V3 uses ``ccv3``.
- The ``spec_version`` field: V2 reports ``"2.0"``, V3 reports ``"3.0"``.

Both versions are spec-compliant with ``base64(zlib(json))``
encoding. Some real-world tools (JanitorAI in particular) skip the
zlib layer and emit ``base64(json)`` instead, so the parser tries
the plain-JSON and base64+JSON strategies first; the spec-conforming
zlib step is the fallback.

The parser pulls the raw payload from the image via PIL
(``img.info[key]``) and falls back to a manual chunk scan when
PIL drops the custom chunks (rare but observed on certain corrupt
PNG files).
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from ..decoders import decode_payload
from ..models import CharacterCardData, CharacterCardParseError
from ..png_chunks import find_text_value, scan_png_chunks
from ._fields import map_fields

# V2 always uses ``chara``. V3 cards written with the older key
# also live here; the dispatcher routes ccv3-keyed payloads to
# :func:`v3.try_parse_v3` so the V3-specific field merge
# (group_only_greetings → alternate_greetings) runs.
_CHARA_KEY = "chara"


def _extract_payload(file_bytes: bytes) -> dict | None:
    """Pull the decoded JSON payload from image bytes (V2 key).

    Tries the ``chara`` tEXt chunk (V2's standard key). V3 cards
    written with the legacy ``chara`` key are still accepted here
    — we just decode the payload and read ``spec_version`` from it,
    so the same parser handles both as long as the dispatcher routes
    them correctly. ``ccv3``-keyed payloads are V3-only and bypass
    this entrypoint entirely.
    """
    # Step 1: PIL — fast path.
    try:
        with Image.open(BytesIO(file_bytes)) as img:
            if _CHARA_KEY in img.info:
                candidate = decode_payload(str(img.info[_CHARA_KEY]))
                if candidate is not None:
                    return candidate
    except (OSError, ValueError, Image.UnidentifiedImageError):
        # Not a valid image — fall through to the manual chunk scan.
        pass

    # Step 2: manual chunk scan — catches the edge case where PIL
    # drops custom tEXt chunks during ``Image.open``.
    chunks = scan_png_chunks(file_bytes)
    text = find_text_value(chunks, _CHARA_KEY)
    if text is not None:
        candidate = decode_payload(text)
        if candidate is not None:
            return candidate
    return None


def parse_v2_or_v3(file_bytes: bytes) -> CharacterCardData:
    """Parse a V2 or V3 card from image bytes.

    Raises :class:`CharacterCardParseError` if the bytes don't
    contain a recognisable V2/V3 payload (no ``chara``/``ccv3`` tEXt
    chunk, no ``data`` wrapper, no ``name`` field, no greeting).
    Callers should fall back to the V1 parser when this raises.
    """
    raw_card = _extract_payload(file_bytes)
    if raw_card is None or "data" not in raw_card or not isinstance(raw_card["data"], dict):
        raise CharacterCardParseError("No character card data found in image")

    data = raw_card["data"]
    spec_version = str(raw_card.get("spec_version", "2.0"))
    return map_fields(data, file_bytes, spec_version)


def try_parse_v2_or_v3(file_bytes: bytes) -> CharacterCardData | None:
    """Same as :func:`parse_v2_or_v3` but returns ``None`` on
    payload-not-found instead of raising. Field-validation errors
    (``name`` missing, no greeting) still raise.
    """
    raw_card = _extract_payload(file_bytes)
    if raw_card is None or "data" not in raw_card or not isinstance(raw_card["data"], dict):
        return None

    data = raw_card["data"]
    spec_version = str(raw_card.get("spec_version", "2.0"))
    return map_fields(data, file_bytes, spec_version)
