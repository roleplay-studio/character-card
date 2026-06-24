"""V3 character card parser.

V3 is the natural evolution of the SillyTavern V2 spec: the same
``data`` wrapper layout, the same field names, and the same
``base64(zlib(json))`` encoding. The only differences are:

- The tEXt chunk key is ``ccv3`` (V2 uses ``chara``).
- ``spec_version`` reports ``"3.0"``.
- V3 adds these fields on top of V2 (per the V3 spec):
  - ``assets`` (list of image references)
  - ``nickname`` (display name alias)
  - ``creation_date`` / ``modification_date`` (timestamps)
  - ``source`` (provenance URLs/strings)
  - ``creator_notes_multilingual`` (i18n for creator_notes)
  - ``group_only_greetings`` (extra greetings for group chats —
    kept **separate** from ``alternate_greetings`` so the round-trip
    preserves the distinction)
  - Per-entry ``use_regex: boolean`` (mandatory in V3)

The mapping is shared with V2 (:func:`_fields.map_fields`) because
V3 added fields are a **superset** of V2 fields. We pass V3
``group_only_greetings`` through to a dedicated
``CharacterCardData.group_only_greetings`` field so the
consumer doesn't have to know which spec the card came from.
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from ..decoders import decode_payload
from ..models import CharacterCardData
from ..png_chunks import find_text_value, scan_png_chunks
from ._fields import map_fields

_CCV3_KEY = "ccv3"


def _extract_v3_payload(file_bytes: bytes) -> dict | None:
    """Pull the decoded JSON payload from a V3 (ccv3-keyed) PNG.

    Distinct from V2's :func:`v2._extract_payload` — that one
    probes ``chara`` first then ``ccv3``. Here we only accept
    ``ccv3`` because that's how the dispatcher routes this parser.
    A V3 card that was written with the legacy ``chara`` key falls
    through to the V2 entrypoint instead.
    """
    # Step 1: PIL — fast path.
    try:
        with Image.open(BytesIO(file_bytes)) as img:
            if _CCV3_KEY in img.info:
                candidate = decode_payload(str(img.info[_CCV3_KEY]))
                if candidate is not None:
                    return candidate
    except (OSError, ValueError, Image.UnidentifiedImageError):
        pass

    # Step 2: manual chunk scan.
    chunks = scan_png_chunks(file_bytes)
    text = find_text_value(chunks, _CCV3_KEY)
    if text is not None:
        candidate = decode_payload(text)
        if candidate is not None:
            return candidate
    return None


def try_parse_v3(file_bytes: bytes) -> CharacterCardData | None:
    """Try to parse a V3 card from image bytes.

    Returns ``None`` if the image doesn't carry a ``ccv3`` tEXt chunk
    with a valid V3 payload. Field-validation errors (missing
    ``name``, no greeting) still raise.

    V3 cards that use the older ``chara`` key instead of ``ccv3``
    are also accepted — the V2 parser handles those. This entrypoint
    is specifically for the ``ccv3`` form.
    """
    payload = _extract_v3_payload(file_bytes)
    if payload is None or "data" not in payload or not isinstance(payload["data"], dict):
        return None

    return map_fields(payload["data"], file_bytes, spec_version="3.0")
