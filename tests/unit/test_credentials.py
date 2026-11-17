"""DPAPI protection of secrets and migration of plain-text Binance keys."""
import json

import pytest

from dynamic_island.infrastructure import credentials
from dynamic_island.core.config.settings import Settings

pytest.importorskip("win32crypt")


def test_protect_round_trip_hides_plain_text():
    stored = credentials.protect("my-binance-secret")
    assert stored.startswith(credentials.PREFIX)
    assert "my-binance-secret" not in stored
    assert credentials.reveal(stored) == "my-binance-secret"


def test_empty_and_legacy_values():
    assert credentials.protect("") == ""
    assert credentials.reveal("") == ""
    assert credentials.reveal("plain-legacy") == "plain-legacy"
    assert not credentials.is_protected("plain-legacy")


@pytest.mark.parametrize("stored", ["dpapi:not base64!", "dpapi:AAAA"])
def test_undecryptable_value_reads_as_missing(stored):
    assert credentials.reveal(stored) == ""


def test_binance_keys_are_migrated_and_encrypted(tmp_path, monkeypatch):
    from dynamic_island.engines import binance

    store = Settings(tmp_path / "settings.json")
    store.set("binance", {"key": "PLAIN_KEY", "secret": "PLAIN_SECRET"})
    monkeypatch.setattr(binance, "settings", store)

    binance.Binance._encrypt_stored_keys()

    for name in ("settings.json", "settings.json.bak"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "PLAIN_KEY" not in text and "PLAIN_SECRET" not in text
    saved = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))["binance"]
    assert all(credentials.is_protected(v) for v in saved.values())
    assert binance.Binance._credentials() == ("PLAIN_KEY", "PLAIN_SECRET")
