"""Tests for lorebook normalisation — Risu / JanitorAI / mixed → V2 spec.

These tests guard the universal-library promise: regardless of which
tool wrote the card, consumers can read normalised spec-shaped
fields (``keys``, ``secondary_keys``, ``enabled``,
``insertion_order``, ``position``, ``priority``, ``case_sensitive``)
on every entry.
"""

from __future__ import annotations

from character_card.lorebook_normalize import normalize_entries, normalize_entry


class TestNormalizeEntrySpecPassthrough:
    """Spec-shaped entries pass through with no surprises."""

    def test_full_spec_entry(self) -> None:
        e = {
            "keys": ["moon", "silver"],
            "secondary_keys": ["night"],
            "enabled": True,
            "insertion_order": 5,
            "position": "before_char",
            "priority": 100,
            "case_sensitive": False,
            "content": "The moon is silver.",
        }
        n = normalize_entry(e)
        assert n["keys"] == ["moon", "silver"]
        assert n["secondary_keys"] == ["night"]
        assert n["enabled"] is True
        assert n["insertion_order"] == 5
        assert n["position"] == "before_char"
        assert n["priority"] == 100
        assert n["case_sensitive"] is False

    def test_minimal_spec_entry_gets_defaults(self) -> None:
        # Only content — everything else defaulted.
        n = normalize_entry({"content": "x"})
        assert n["keys"] == []
        assert n["secondary_keys"] == []
        assert n["enabled"] is True
        assert n["insertion_order"] == 0
        assert n["position"] == "after_char"
        assert n["priority"] == 0
        assert n["case_sensitive"] is False

    def test_spec_takes_priority_over_aliases(self) -> None:
        # When BOTH spec and Risu fields are present, spec wins
        # (a spec-compliant author should not be silently overridden).
        e = {
            "keys": ["spec_key"],
            "triggers": ["risu_key"],
            "enabled": True,
            "disable": True,  # Risu says disabled
            "insertion_order": 7,
            "order": 99,  # Risu says 99
            "position": "after_char",
            "priority": 50,
            "probability": 25,  # Risu says 25
            "case_sensitive": True,
            "caseSensitive": False,  # Risu says False
        }
        n = normalize_entry(e)
        assert n["keys"] == ["spec_key"]
        assert n["enabled"] is True
        assert n["insertion_order"] == 7
        assert n["priority"] == 50
        assert n["case_sensitive"] is True


class TestNormalizeEntryRisuAliases:
    """Risu / JanitorAI entries map into spec via aliases."""

    def test_triggers_becomes_keys(self) -> None:
        n = normalize_entry({"triggers": ["moon", "silver"], "content": "x"})
        assert n["keys"] == ["moon", "silver"]

    def test_keysecondary_becomes_secondary_keys(self) -> None:
        n = normalize_entry({"keysecondary": ["night"], "content": "x"})
        assert n["secondary_keys"] == ["night"]

    def test_disable_true_becomes_enabled_false(self) -> None:
        n = normalize_entry({"disable": True, "content": "x"})
        assert n["enabled"] is False

    def test_disable_false_becomes_enabled_true(self) -> None:
        n = normalize_entry({"disable": False, "content": "x"})
        assert n["enabled"] is True

    def test_position_int_1_becomes_after_char(self) -> None:
        # Risu default: 1 = after_char
        n = normalize_entry({"position": 1, "content": "x"})
        assert n["position"] == "after_char"

    def test_position_int_0_becomes_before_char(self) -> None:
        n = normalize_entry({"position": 0, "content": "x"})
        assert n["position"] == "before_char"

    def test_order_becomes_insertion_order(self) -> None:
        n = normalize_entry({"order": 42, "content": "x"})
        assert n["insertion_order"] == 42

    def test_display_index_fallback_for_insertion_order(self) -> None:
        # Some Risu cards have only displayIndex, not "order".
        n = normalize_entry({"displayIndex": 7, "content": "x"})
        assert n["insertion_order"] == 7

    def test_probability_becomes_priority(self) -> None:
        n = normalize_entry({"probability": 75, "content": "x"})
        assert n["priority"] == 75

    def test_case_sensitive_alias_becomes_case_sensitive(self) -> None:
        n = normalize_entry({"caseSensitive": True, "content": "x"})
        assert n["case_sensitive"] is True

    def test_real_risu_entry(self) -> None:
        """Shape lifted from a Risu-exported entry."""
        e = {
            "comment": "moon lore",
            "content": "The moon is silver.",
            "disable": False,
            "position": 1,
            "order": 5,
            "displayIndex": 5,
            "triggers": ["moon"],
            "keysecondary": [],
            "constant": False,
            "caseSensitive": False,
            "extensions": {},
            "role": None,
        }
        n = normalize_entry(e)
        assert n["keys"] == ["moon"]
        assert n["enabled"] is True
        assert n["position"] == "after_char"
        assert n["insertion_order"] == 5
        assert n["priority"] == 0  # probability not set on this entry
        assert n["case_sensitive"] is False


class TestNormalizeEntryMixedAndEdge:
    """Mixed / malformed inputs."""

    def test_mixed_style_entry(self) -> None:
        """Some fields spec, some Risu — both should be picked up."""
        e = {
            "keys": ["spec_key"],  # spec
            "secondary_keys": ["spec2"],  # spec
            "triggers": ["risu_key"],  # ignored, spec wins
            "enabled": True,  # spec
            "disable": True,  # ignored, spec wins
            "position": 1,  # Risu int
            "order": 10,  # Risu
            "priority": 5,  # spec
            "probability": 90,  # ignored, spec wins
            "case_sensitive": True,  # spec
            "caseSensitive": False,  # ignored, spec wins
        }
        n = normalize_entry(e)
        assert n["keys"] == ["spec_key"]
        assert n["secondary_keys"] == ["spec2"]
        assert n["enabled"] is True
        assert n["position"] == "after_char"
        assert n["insertion_order"] == 10
        assert n["priority"] == 5
        assert n["case_sensitive"] is True

    def test_empty_triggers_yields_empty_keys(self) -> None:
        # Risu lorebooks for system rules have empty triggers —
        # they're constant entries, not key-triggered.
        n = normalize_entry({"triggers": [], "content": "x"})
        assert n["keys"] == []

    def test_string_triggers_is_wrapped_into_list(self) -> None:
        # JanitorAI sometimes puts a single string in triggers.
        n = normalize_entry({"triggers": "moon", "content": "x"})
        assert n["keys"] == ["moon"]

    def test_malformed_position_int_uses_default(self) -> None:
        # 5 is not a valid Risu int (only 0/1). Fall back to default.
        n = normalize_entry({"position": 5, "content": "x"})
        assert n["position"] == "after_char"

    def test_malformed_position_string_uses_default(self) -> None:
        n = normalize_entry({"position": "wherever", "content": "x"})
        assert n["position"] == "after_char"

    def test_no_position_uses_default(self) -> None:
        n = normalize_entry({"content": "x"})
        assert n["position"] == "after_char"

    def test_bool_position_treated_as_int(self) -> None:
        # Edge case: True/False should NOT be coerced to 1/0
        # silently. Python: True == 1, but bool semantics differ.
        n = normalize_entry({"position": True, "content": "x"})
        # True isn't 0/1 → falls through to default.
        assert n["position"] == "after_char"

    def test_non_int_insertion_order_uses_zero(self) -> None:
        n = normalize_entry({"insertion_order": "five", "content": "x"})
        assert n["insertion_order"] == 0

    def test_non_int_priority_uses_zero(self) -> None:
        n = normalize_entry({"priority": "high", "content": "x"})
        assert n["priority"] == 0

    def test_invalid_input_not_a_dict_returns_defaults(self) -> None:
        # Defensive: a malformed entry (e.g. a stray string in the
        # entries list) should not crash the normalizer.
        for bad in ("string", 42, []):
            n = normalize_entry(bad)  # type: ignore[arg-type]
            assert n["keys"] == []
            assert n["enabled"] is True


class TestNormalizeEntryIsPure:
    """The normalizer must NOT mutate the input entry."""

    def test_input_dict_unchanged(self) -> None:
        e = {
            "triggers": ["moon"],
            "disable": False,
            "position": 1,
            "order": 5,
            "caseSensitive": True,
        }
        snapshot = dict(e)
        normalize_entry(e)
        assert e == snapshot

    def test_triggers_list_unchanged(self) -> None:
        e = {"triggers": ["moon", "silver"]}
        triggers_before = list(e["triggers"])
        normalize_entry(e)
        assert e["triggers"] == triggers_before


class TestNormalizeEntriesList:
    """List-level wrapper."""

    def test_none_yields_empty(self) -> None:
        assert normalize_entries(None) == []

    def test_empty_list_yields_empty(self) -> None:
        assert normalize_entries([]) == []

    def test_preserves_length(self) -> None:
        entries = [{"content": "a"}, {"content": "b"}, {"content": "c"}]
        result = normalize_entries(entries)
        assert len(result) == 3

    def test_skips_non_dict_entries(self) -> None:
        # A defensive guard against malformed entries lists.
        entries: list = [{"content": "ok"}, "junk", None, {"content": "ok2"}]
        result = normalize_entries(entries)
        assert len(result) == 2
