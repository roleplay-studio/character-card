"""Lorebook normalization — translate Risu / JanitorAI / mixed
field styles into V2 spec fields.

The parser's contract today is "preserve the whole character_book
opaque" — that's still true. On top of that, this module surfaces
**normalized** fields that consume a unified spec-shaped view
regardless of which authoring tool wrote the card.

Field mapping:

| Spec field        | Risu / JanitorAI alias(s)                            |
| ----------------- | ---------------------------------------------------- |
| ``keys``          | ``triggers``                                         |
| ``secondary_keys``| ``keysecondary``                                     |
| ``enabled``       | invert ``disable`` if present, else ``enabled``      |
| ``insertion_order``| ``order`` (fallback), else ``displayIndex``, else 0 |
| ``position``      | int 0/1 → "before_char"/"after_char"; str passthrough|
| ``priority``      | ``probability`` (0-100), else ``priority``           |
| ``case_sensitive``| ``caseSensitive``                                    |

Anything else (selective, constant, content, comment, use_regex,
extensions, custom Risu fields) is **not** touched — those either
already have spec names or are extension data.
"""

from __future__ import annotations

# Mapping for integer "position" used by Risu and some JanitorAI
# exports. V2 spec uses strings: "before_char" / "after_char" /
# "before_system". Risu convention is 0 = before, 1 = after.
_RISU_POSITION_INT_TO_STR = {
    0: "before_char",
    1: "after_char",
}

# Some Risu exports use the strings directly (rare). Spec values are
# already strings, so this is a passthrough when the input is str.
_VALID_POSITION_STRINGS = {"before_char", "after_char", "before_system"}


def normalize_entry(entry: dict) -> dict:
    """Return a normalized copy of a lorebook entry.

    Reads Risu / JanitorAI aliases and falls back to spec fields.
    Mutates nothing on the input — the caller keeps the original
    opaque entry on ``character_book`` untouched.

    Returns a fresh dict with these normalized spec-shaped keys
    (other keys on the input are NOT carried over — the caller
    should keep the original ``character_book['entries'][i]``
    dict for round-trip):

        keys, secondary_keys, enabled, insertion_order,
        position, priority, case_sensitive

    Non-dict input (e.g. a stray string in a malformed entries
    list) returns the all-defaults dict rather than raising —
    the parser already handles malformed entries by skipping
    them, but the normalizer is also called independently by
    downstream consumers and should be safe.
    """
    defaults = {
        "keys": [],
        "secondary_keys": [],
        "enabled": True,
        "insertion_order": 0,
        "position": "after_char",
        "priority": 0,
        "case_sensitive": False,
    }
    if not isinstance(entry, dict):
        return defaults

    out: dict = {}

    # ── keys: spec "keys" → fallback Risu "triggers" ──────────────
    keys = entry.get("keys")
    if not keys:
        triggers = entry.get("triggers")
        if isinstance(triggers, list):
            keys = [k for k in triggers if isinstance(k, str) and k]
        elif isinstance(triggers, str) and triggers:
            # Some JanitorAI exports use a single string in triggers.
            keys = [triggers]
    out["keys"] = list(keys) if keys else []

    # ── secondary_keys: spec → Risu "keysecondary" ────────────────
    sec = entry.get("secondary_keys")
    if sec is None:
        sec = entry.get("keysecondary")
    if isinstance(sec, list):
        out["secondary_keys"] = [k for k in sec if isinstance(k, str) and k]
    else:
        out["secondary_keys"] = []

    # ── enabled: spec "enabled" → invert Risu "disable" ───────────
    enabled = entry.get("enabled")
    if enabled is None:
        disable = entry.get("disable")
        if isinstance(disable, bool):
            enabled = not disable
        else:
            enabled = True  # spec default
    out["enabled"] = bool(enabled)

    # ── insertion_order: spec → Risu "order" / "displayIndex" ─────
    insertion = entry.get("insertion_order")
    if insertion is None:
        insertion = entry.get("order")
    if insertion is None:
        insertion = entry.get("displayIndex")
    if insertion is None:
        insertion = 0
    try:
        out["insertion_order"] = int(insertion)
    except (TypeError, ValueError):
        out["insertion_order"] = 0

    # ── position: spec str → Risu int (0/1) ──────────────────────
    pos = entry.get("position")
    if isinstance(pos, bool):
        # bool is an int subclass — guard against True/False silently
        # turning into 1/0.
        out["position"] = "after_char"
    elif isinstance(pos, int) and pos in _RISU_POSITION_INT_TO_STR:
        out["position"] = _RISU_POSITION_INT_TO_STR[pos]
    elif isinstance(pos, str) and pos in _VALID_POSITION_STRINGS:
        out["position"] = pos
    else:
        # Risu default is "after_char" (position=1). V2 spec has no
        # default — but picking one keeps the field meaningful for
        # consumers that iterate normalized entries without checking.
        out["position"] = "after_char"

    # ── priority: spec → Risu "probability" (0-100) ──────────────
    prio = entry.get("priority")
    if prio is None:
        prob = entry.get("probability")
        if isinstance(prob, int | float) and not isinstance(prob, bool):
            prio = int(prob)
    if prio is None:
        prio = 0
    try:
        out["priority"] = int(prio)
    except (TypeError, ValueError):
        out["priority"] = 0

    # ── case_sensitive: spec → Risu "caseSensitive" ───────────────
    cs = entry.get("case_sensitive")
    if cs is None:
        cs = entry.get("caseSensitive")
    out["case_sensitive"] = bool(cs) if isinstance(cs, bool) else False

    return out


def normalize_entries(entries: list[dict] | None) -> list[dict]:
    """Apply :func:`normalize_entry` to a list of entries.

    Returns ``[]`` for missing / empty input.
    """
    if not entries:
        return []
    return [normalize_entry(e) for e in entries if isinstance(e, dict)]
