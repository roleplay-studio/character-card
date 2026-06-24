"""Tests for the three payload decoders."""

from __future__ import annotations

import base64
import json
import zlib

import pytest

from character_card.decoders import (
    decode_payload,
    try_base64_json,
    try_json,
    try_zlib_json,
)

# ── try_json ──────────────────────────────────────────────────────────


class TestTryJson:
    def test_parses_object(self) -> None:
        assert try_json('{"a": 1}') == {"a": 1}

    def test_returns_none_for_non_object(self) -> None:
        # Arrays, strings, numbers aren't valid card payloads
        assert try_json("[1, 2, 3]") is None
        assert try_json('"hi"') is None
        assert try_json("42") is None

    def test_returns_none_on_invalid_json(self) -> None:
        assert try_json("not json") is None
        assert try_json("{") is None


# ── try_base64_json ───────────────────────────────────────────────────


class TestTryBase64Json:
    def test_parses_b64_encoded_object(self) -> None:
        raw = json.dumps({"name": "Luna"}).encode()
        assert try_base64_json(base64.b64encode(raw).decode()) == {"name": "Luna"}

    def test_returns_none_on_invalid_b64(self) -> None:
        assert try_base64_json("!!!not base64!!!") is None

    def test_returns_none_on_valid_b64_invalid_json(self) -> None:
        assert try_base64_json(base64.b64encode(b"not json").decode()) is None


# ── try_zlib_json ─────────────────────────────────────────────────────


class TestTryZlibJson:
    def test_parses_b64_zlib_json(self) -> None:
        raw = json.dumps({"x": 1}).encode()
        encoded = base64.b64encode(zlib.compress(raw)).decode()
        assert try_zlib_json(encoded) == {"x": 1}

    def test_returns_none_on_zlib_error(self) -> None:
        # Valid b64, but not zlib-compressed
        raw = json.dumps({"x": 1}).encode()
        encoded = base64.b64encode(raw).decode()
        assert try_zlib_json(encoded) is None


# ── decode_payload (chain) ────────────────────────────────────────────


class TestDecodePayload:
    def test_picks_json_first(self) -> None:
        # Plain JSON wins even if the same object is also valid base64-JSON.
        assert decode_payload('{"a": 1}') == {"a": 1}

    def test_picks_base64_when_json_fails(self) -> None:
        raw = json.dumps({"a": 2}).encode()
        encoded = base64.b64encode(raw).decode()
        # Not plain JSON, but valid base64-JSON
        assert decode_payload(encoded) == {"a": 2}

    def test_picks_zlib_when_others_fail(self) -> None:
        raw = json.dumps({"a": 3}).encode()
        encoded = base64.b64encode(zlib.compress(raw)).decode()
        assert decode_payload(encoded) == {"a": 3}

    def test_returns_none_for_garbage(self) -> None:
        assert decode_payload("not anything") is None
        assert decode_payload("") is None

    def test_try_zlib_false_skips_zlib_step(self) -> None:
        # A payload that ONLY decodes via zlib
        raw = json.dumps({"a": 3}).encode()
        encoded = base64.b64encode(zlib.compress(raw)).decode()
        # With try_zlib=True (default), this decodes fine
        assert decode_payload(encoded) == {"a": 3}
        # With try_zlib=False, the chain only tries JSON then b64-JSON.
        # The encoded blob is not valid base64-JSON (it's zlib-compressed
        # binary inside the base64), so the chain returns None.
        assert decode_payload(encoded, try_zlib=False) is None


# ── Realistic fixtures ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw",
    [
        '{"spec": "chara_card_v2", "spec_version": "2.0", "data": {}}',
        '{"name": "Luna", "description": "d"}',
    ],
)
def test_decodes_card_shaped_payloads(raw: str) -> None:
    """V2 envelope and V1 flat JSON both decode through try_json."""
    result = decode_payload(raw)
    assert result is not None
    assert "spec" in result or "name" in result
