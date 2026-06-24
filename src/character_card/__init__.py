"""character-card — SillyTavern V1/V2/V3 character card I/O.

Public API:

- :func:`parse_character_card` — entrypoint that tries V2 → V3 → V1
  in turn and returns a :class:`CharacterCardData`.
- :func:`build_character_card_json` — reverse direction, build a V2
  JSON payload from a Bot-like object (used for export).
- :func:`embed_card_in_png` — write a V2 JSON payload into a PNG's
  ``chara`` tEXt chunk (used by the export endpoint).
- :class:`CharacterCardData` — parsed-fields dataclass.
- :class:`CharacterCardParseError` — raised by the parsers.

Modules:

- :mod:`.models` — shared dataclasses and exceptions.
- :mod:`.decoders` — payload decoding (plain JSON, base64+JSON,
  base64+zlib+JSON).
- :mod:`.png_chunks` — raw PNG chunk scanner (fallback for when PIL
  drops custom chunks).
- :mod:`.parsers` — per-version parser entrypoints (V1 / V2 / V3).
- :mod:`.builder` — Bot-like object → V2 JSON payload.
- :mod:`.embed` — V2 JSON payload → PNG.
"""

from __future__ import annotations

from .builder import build_character_card_json
from .embed import embed_card_in_png
from .models import CharacterCardData, CharacterCardParseError
from .parsers import parse_character_card

__version__ = "0.1.0"

__all__ = [
    "CharacterCardData",
    "CharacterCardParseError",
    "__version__",
    "build_character_card_json",
    "embed_card_in_png",
    "parse_character_card",
]
