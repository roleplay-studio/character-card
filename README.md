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

## A note on `personality` / `description` / `creator_notes`

The parser maps these three fields **1:1** from the spec payload
into `CharacterCardData` and does no silent merging or fallback:

| Spec field (`data.*`)     | Dataclass field           | Goes into prompt? |
| ------------------------ | ------------------------- | ----------------- |
| `personality`            | `card.personality`        | yes               |
| `description`            | `card.description`        | yes               |
| `creator_notes`          | `card.creator_notes`      | **no** (spec MUST NOT) |

In particular: **if `data.personality` is empty, `card.personality`
is empty too** — the parser does **not** fall back to `description`
or `creator_notes`. If you want such a fallback (a common pattern
in downstream apps), do it yourself:

```python
effective_personality = card.personality or card.description
```

Heads-up for cards from chub / botbooru / most community exports:
authors typically write the actual character summary into
`description` and leave `personality` blank. The SillyTavern UI
labels this same field as "Personality Summary", which is why
many users expect `card.personality` to be populated. It won't be
unless the source card's `data.personality` was populated.

`creator_notes` is intentionally **separate** from `description`.
The V2 spec marks it as MUST NOT be used inside prompts, so it
must not be merged into `description` (this library used to do
that — it was a spec violation, now removed). Display layers that
want to show the two together should concatenate them downstream,
not at parse time.

## Working with the lorebook (`character_book`)

A character card may carry a **lorebook** — a structured bundle of
"world info" snippets that get spliced into the conversation when
certain keywords appear. The lorebook lives under
`data.character_book` in the spec payload. In SillyTavern /
Risu / JanitorAI / chub lorebooks are how authors ship dozens or
hundreds of lore fragments (NPCs, places, items, factions, rules)
alongside the main card without bloating the prompt by default.

The on-disk shape (V2; V3 is the same with `use_regex: true`
required on entries):

```json
{
  "name": "moon_lore",
  "description": "lore about the moon",
  "scan_depth": 5,
  "token_budget": 2048,
  "recursive_scanning": true,
  "extensions": {},
  "entries": [
    {
      "keys": ["moon", "silver"],
      "secondary_keys": ["night"],
      "content": "The moon is silver.",
      "enabled": true,
      "insertion_order": 0,
      "case_sensitive": false,
      "selective": true,
      "constant": false,
      "position": "before_char",
      "priority": 100,
      "id": 1,
      "name": "moon_entry",
      "comment": "core moon lore",
      "extensions": {},
      "use_regex": false
    }
  ]
}
```

What each piece means:

- `entries[]` — list of lore snippets. Each one has a `content`
  (the text to inject) and the metadata that decides **when** and
  **where** to inject it.
- `keys` / `secondary_keys` — trigger keywords. `secondary_keys`
  only count when an entry is already matched by its primary keys
  (AND logic on top of the primary match).
- `selective` — if `true`, the entry fires only when one of its
  `secondary_keys` matches (in addition to a primary `keys` match).
  If `false`, the entry fires whenever any primary key matches.
- `constant` — always-included, ignoring key matches. Use for
  world rules that should never drop out of context.
- `case_sensitive` — whether key matching is case-sensitive.
- `position` — `"before_char"`, `"after_char"`, or
  `"before_system"`. Determines where the entry is spliced in
  the prompt.
- `priority` — tie-breaker when multiple entries are competing
  for the same `token_budget`.
- `insertion_order` — secondary tie-breaker (matches the original
  V2 ordering).
- `enabled` — entries with `enabled: false` are inert.
- `use_regex` (V3) — if `true`, `keys` and `secondary_keys` are
  treated as JavaScript regexes. If the field is missing, treat
  it as `false`.
- `extensions` — opaque bag (V2 spec marks it MANDATORY-empty but
  MUST NOT destroy unknown keys; the parser preserves it as-is).
- `scan_depth`, `token_budget`, `recursive_scanning` — book-level
  knobs that gate how many tokens get pulled in and whether newly
  activated entries can themselves activate further entries.

How this library exposes the lorebook:

```python
from character_card import parse_character_card

card = parse_character_card(png_bytes)

# Full opaque bag — keep around for selective activation
# (keys, position, priority, use_regex, ...).
book = card.character_book           # dict | None
entries = book["entries"] if book else []

# Flattened convenience projection: just the .content strings,
# in declaration order, with empties filtered. Useful when you
# want a simple "inject everything" prompt.
contents = card.character_book_entries  # list[str]
```

`character_book_entries` is **not** the source of truth — it
loses the activation metadata. If your app does selective
matching (the common case for serious lorebooks with hundreds of
entries), use `card.character_book["entries"]` and walk it
yourself. The convenience list is for callers that genuinely
want every enabled entry inlined.

### Universal (Risu / JanitorAI / mixed) normalisation

Cards written by RisuAI, JanitorAI, or hand-rolled chub
exports don't use V2 field names — they use aliases
(`triggers` instead of `keys`, `disable` instead of
`enabled` with **inverted** semantics, `order` /
`displayIndex` instead of `insertion_order`, `probability`
0–100 instead of `priority`, `caseSensitive` camelCase,
numeric `position` 0/1 instead of the spec's strings).
A card that mixes both styles in the same `entries` list is
not unusual.

Reading the raw opaque bag, you'd need to detect each alias
yourself. The library does it for you and exposes seven
**parallel** lists on `CharacterCardData` that always carry
spec-shaped values, regardless of who wrote the card:

```python
# All same length as character_book['entries'] (or empty if
# there is no lorebook). Index i corresponds to entries[i].
card.character_book_keys             # list[list[str]]
card.character_book_secondary_keys   # list[list[str]]
card.character_book_enabled         # list[bool]
card.character_book_insertion_order # list[int]
card.character_book_position        # list[str]: "before_char" | "after_char" | "before_system"
card.character_book_priority        # list[int]
card.character_book_case_sensitive  # list[bool]
```

Field translation table:

| Spec field         | Risu / JanitorAI alias(s)                                |
| ------------------ | -------------------------------------------------------- |
| ``keys``           | ``triggers`` (also accepts a single string)              |
| ``secondary_keys`` | ``keysecondary``                                         |
| ``enabled``        | ``disable`` (inverted: ``True`` → ``False``)             |
| ``insertion_order``| ``order``, fallback ``displayIndex``                    |
| ``position``       | int 0/1 → ``"before_char"`` / ``"after_char"``; str passthrough |
| ``priority``       | ``probability`` 0–100                                    |
| ``case_sensitive`` | ``caseSensitive``                                        |

When both a spec field **and** a Risu alias are present on
the same entry, the **spec field wins** — a spec-compliant
author should not be silently overridden by an incidental
alias. Other entry fields (`content`, `selective`,
`constant`, `comment`, `use_regex`, `extensions`, and Risu
extensions like `addMemo` / `cooldown` / `vectorized`) are
**not** normalised — they keep their original names and
live only on the opaque `character_book['entries'][i]` dict.

The normalised lists are a derived view: round-tripping a
card through `embed_card_in_png` preserves the **original**
opaque `character_book` byte-for-byte (verified for the
382-entry Hoenn fixture in this repo's demo suite). If you
write a normalised spec-shaped payload back, use
`build_character_card_json(knowledge_contents=...)` or
construct `data["character_book"]` yourself — the embedder
writes the raw dict you hand it, not the normalised lists.

A quick check on the demo fixtures:

```python
from pathlib import Path
from character_card import parse_character_card

card = parse_character_card(Path("Card.png").read_bytes())
print(len(card.character_book["entries"]))              # 382 (opaque Risu-style)
print(sum(1 for e in card.character_book_enabled if e)) # 379
# Disable:True on three entries → inverted to enabled:False.
print(set(card.character_book_position))
# {"before_char", "after_char"} — int 0/1 translated to spec strings.
```

Hoenn has zero spec-shaped `keys` because it was written by
Risu for **system rules** (`constant: True` entries with
empty `triggers`), not key-triggered lore — that's by
design, not a parsing bug. Ori (66 entries, mixed style)
has 51 entries with populated `keys`, all visible on
`card.character_book_keys`.

Writing a lorebook back into a card: pass the snippets as
strings to `build_character_card_json`:

```python
from character_card import build_character_card_json, embed_card_in_png

payload = build_character_card_json(
    bot,
    knowledge_contents=[
        "The moon is silver.",
        "Dragons hoard memory, not gold.",
        "Every full moon, the city bells ring backward.",
    ],
)
new_png = embed_card_in_png(original_png_bytes, payload)
```

This produces a spec-compliant V2 `character_book` with empty
top-level `extensions`, mandatory `enabled: True` /
`insertion_order: i` per entry, and per-entry empty `extensions`.
Re-parsing the resulting PNG round-trips the structure.

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
