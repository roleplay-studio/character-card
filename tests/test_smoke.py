"""Smoke test — proves the package installs and the public API is reachable."""

from __future__ import annotations

import character_card


def test_package_importable() -> None:
    assert character_card.__version__ == "0.1.0"


def test_public_api_surface() -> None:
    """The public API is currently minimal (only __version__).

    As modules are ported, this test will grow to assert each new symbol
    is exported from the top-level package.
    """
    assert hasattr(character_card, "__version__")
