# character-card

SillyTavern V1 / V2 / V3 character card parser, builder, and PNG embedder.

Extracts the metadata payload that SillyTavern, Risu, Agnai, JanitorAI, and
other frontends embed inside PNG images (and writes it back). One runtime
dependency: Pillow. Pure stdlib for everything else.

## Quickstart

```python
from character_card import (
    parse_character_card,
    build_character_card_json,
    embed_card_in_png,
    CharacterCardData,
    CharacterCardParseError,
)

# Read a card from a PNG
with open("my_bot.png", "rb") as f:
    card: CharacterCardData = parse_character_card(f.read())

print(card.name)
print(card.personality)
print(card.first_message)
print(card.alternate_greetings)
print(card.spec_version)  # "1.0" | "2.0" | "3.0"

# Build a V2 payload from a Bot-like object (duck-typed, no Bot import)
payload = build_character_card_json(bot, knowledge_contents=["lore 1", "lore 2"])

# Write the payload back into a PNG
out_bytes = embed_card_in_png(png_bytes, payload)
```

## What it handles

- **V1 spec** — flat tEXt chunks (one per field), no JSON envelope. The
  format used by hand-rolled fixtures and the wizard helper that writes
  `puro.png`-style files.
- **V1 spec (chara tEXt)** — flat JSON object, no `data` wrapper.
- **V2 spec** — `chara` tEXt chunk with `base64(zlib(json))` payload.
- **V3 spec** — same layout as V2, but using the `ccv3` tEXt key and
  adding `group_only_greetings` (folded into `alternate_greetings`).

The parser tries V2 → V3 → V1 in turn and returns the first match. It
accepts all three PNG metadata chunk formats (`tEXt`, `zTXt`, `iTXt`)
and falls back to a manual chunk scan when PIL drops custom chunks.

Field-level details: see `CharacterCardData` in
[`src/character_card/models.py`](src/character_card/models.py).


## Module layout

```
src/character_card/
├── __init__.py        # public API re-exports
├── models.py          # CharacterCardData, CharacterCardParseError
├── decoders.py        # plain JSON / base64+JSON / base64+zlib+JSON
├── png_chunks.py      # raw PNG chunk scanner, tEXt/zTXt/iTXt readers
├── parsers/
│   ├── __init__.py    # parse_character_card dispatcher
│   ├── _fields.py     # shared V1/V2/V3 field mapper (spec-compliant)
│   ├── v1.py          # V1 (chara tEXt, flat JSON, no data wrapper)
│   ├── v2.py          # V2 (chara tEXt, data wrapper)
│   ├── v3.py          # V3 (ccv3 tEXt, group_only_greetings separate)
│   └── v1_flat.py     # V1 flat-tEXt layout (one chunk per field)
├── builder.py         # Bot-like object → V2 payload
└── embed.py           # V2+V3 payloads → PNG (SillyTavern-compatible)
```

## SillyTavern compatibility

The embed pipeline is a deliberate port of the
[SillyTavern reference parser](https://github.com/SillyTavern/SillyTavern/blob/release/src/character-card-parser.js)
behaviour:

- Embed writes BOTH `chara` (V2) and `ccv3` (V3) chunks into the
  same PNG. Older V2-only readers see the chara chunk; V3 readers
  see the ccv3 chunk.
- The payload is encoded as `base64(utf-8(json))` — no zlib. This
  matches SillyTavern's own writer and means the cards we produce
  are loadable by Risu, Agnai, JanitorAI, and any other
  SillyTavern-compatible tool without that tool having to try
  zlib as a fallback.
- The dispatcher reads `ccv3` (V3) first when both chunks are
  present, so a round-tripped card reports `spec_version = 3.0`.
- Pre-existing `chara`/`ccv3` chunks are stripped before writing,
  so re-embedding a card is idempotent (no chunk accumulation).

We also still **read** `base64(zlib(json))` cards (the older
format from Risu / JanitorAI / our pre-SillyTavern-compat
versions) via the same `decode_payload` chain — so we round-trip
ourselves across versions, and we can ingest cards from any of
the above tools.

## Installation

```sh
uv add character-card
# or
pip install character-card
```

From a local checkout (editable):

```sh
uv add --editable ../character-card
```

## Development

```sh
uv sync --extra test
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## License

MIT.
