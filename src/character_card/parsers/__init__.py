"""V1 / V2 / V3 character card parsers.

Four entrypoints, one per variant on disk:

- :func:`v3.try_parse_v3` — V3 cards that use the ``ccv3`` tEXt key.
  Per the SillyTavern reference implementation, ``ccv3`` takes
  **precedence** over ``chara`` when both are present in the same
  PNG (SillyTavern's own writer dual-writes both chunks on export).

- :func:`v2.try_parse_v2_or_v3` — V2 cards use the ``chara`` tEXt
  chunk and ``base64(zlib(json))`` encoding. The same entrypoint
  also reads V3 cards that were written with the legacy ``chara``
  key (older SillyTavern versions used ``chara`` for both V2 and
  V3 before the ``ccv3`` key was finalised). spec_version is read
  from the payload to distinguish them.

- :func:`v1.parse_v1` — V1 spec: a flat JSON object (no ``data``
  wrapper) encoded as plain JSON, ``base64+JSON``, or
  ``base64+zlib+JSON``. The chunk key is ``chara`` (same as V2),
  which is how V1 cards co-exist on disk with V2 cards.

- :func:`v1_flat.parse_v1_flat` — V1 flat-tEXt layout: one
  metadata chunk per field (``name``, ``personality``, …) with
  no JSON envelope. This is what our own wizard helper writes and
  what hand-rolled fixtures like ``puro.png`` use.

- :func:`parse_character_card` — the dispatcher. Tries V3 first
  (matching SillyTavern's own priority), then V2 (the common
  shape for non-SillyTavern tools), then V1 flat (for hand-rolled
  fixtures). Field-validation errors (``name`` missing, no
  greeting) raise immediately and are **not** retried against
  other parsers — those errors are intrinsic to the payload, not
  the on-disk encoding.
"""

from __future__ import annotations

from ..models import CharacterCardData, CharacterCardParseError
from .v1 import parse_v1, try_parse_v1
from .v1_flat import parse_v1_flat, try_parse_v1_flat
from .v2 import try_parse_v2_or_v3
from .v3 import try_parse_v3


def parse_character_card(file_bytes: bytes, file_ext: str = ".png") -> CharacterCardData:
    """Parse a V1/V2/V3 character card from image bytes.

    ``file_ext`` is informational — PIL handles the format
    transparently for ``.png`` / ``.webp`` / ``.jpg``. The original
    ``file_bytes`` are kept as ``avatar_bytes`` on the result for
    the caller to persist.

    Strategy (matches the SillyTavern reference parser):

    1. V3 (``ccv3`` tEXt chunk) — highest priority so a PNG that
       was exported by SillyTavern and carries both ``chara`` and
       ``ccv3`` reads as V3, not V2.
    2. V2 / V3-via-``chara`` — the common shape for non-SillyTavern
       tools (JanitorAI, Risu, our own V2 builder).
    3. V1 spec (chara tEXt + flat JSON, no ``data`` wrapper).
    4. V1 flat-tEXt layout — hand-rolled fixtures, our wizard.
    5. If all four return ``None``, raise
       :class:`CharacterCardParseError`.
    """
    for parser in (
        try_parse_v3,
        try_parse_v2_or_v3,
        try_parse_v1,
        try_parse_v1_flat,
    ):
        try:
            card = parser(file_bytes)
        except CharacterCardParseError:
            # Field-validation error — payload was decoded but is
            # malformed. Don't fall back: the bytes are clearly
            # intended as a card, just an invalid one.
            raise
        if card is not None:
            return card
    raise CharacterCardParseError("No character card data found in image")


__all__ = [
    "parse_character_card",
    "parse_v1",
    "parse_v1_flat",
    "parse_v2_or_v3",
    "try_parse_v2_or_v3",
    "try_parse_v3",
]
