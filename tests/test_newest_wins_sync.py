from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import ANY, patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

# The policy modules only need Collection for annotations. Keep these unit tests
# independent of a full Anki build/runtime.
anki = ModuleType("anki")
anki_collection = ModuleType("anki.collection")
anki_collection.Collection = object
anki.collection = anki_collection
sys.modules.setdefault("anki", anki)
sys.modules.setdefault("anki.collection", anki_collection)

from kelma.kelma_sync_v2 import (
    anki_apply,
    anki_local,
    card_sync,
    deck_sync,
    note_sync,
    notetype_sync,
)


class FakeClient:
    def __init__(self, pulled: dict | None = None) -> None:
        self.pulled = pulled or {"notes": [], "cards": []}
        self.pull_requests: list[dict] = []
        self.push_requests: list[dict] = []

    def batch_pull(self, **request):
        self.pull_requests.append(request)
        return self.pulled

    def batch_push(self, payload):
        self.push_requests.append(payload)
        return {
            "accepted": {
                "notes": len(payload.get("notes", [])),
                "cards": len(payload.get("cards", [])),
            },
            "conflicts": {"notes": []},
        }


class NewestWinsSyncTest(unittest.TestCase):
    def test_server_newer_note_is_pulled_without_conflict(self) -> None:
        local = [{
            "guid": "g1", "checksum": "local",
            "modified_at": "2026-07-14T10:00:00Z",
        }]
        server = {
            "server_time": "2026-07-14T12:00:00Z",
            "notes": [{
                "guid": "g1", "checksum": "server",
                "client_modified_at": "2026-07-14T11:00:00Z",
                "modified_at": "2026-07-14T12:00:00Z",
            }],
        }
        client = FakeClient(pulled={"notes": [{
            "guid": "g1", "fields": ["new"], "tags": [],
            "client_modified_at": "2026-07-14T11:00:00Z",
        }]})
        applied: list[str] = []
        with (
            patch.object(anki_local, "note_manifest", return_value=local),
            patch.object(anki_apply, "apply_note", side_effect=lambda _col, rec: applied.append(rec["guid"])),
        ):
            result = note_sync.sync_notes_once(
                object(), client, server_manifest=server, newest_wins=True
            )
        self.assertEqual(result.pulled, 1)
        self.assertEqual(applied, ["g1"])
        self.assertEqual(client.pull_requests, [{"notes": ["g1"]}])
        self.assertEqual(client.push_requests, [])

    def test_local_newer_note_uses_server_checksum_as_write_base(self) -> None:
        local = [{
            "guid": "g1", "checksum": "local",
            "modified_at": "2026-07-14T11:00:00Z",
        }]
        server = {"notes": [{
            "guid": "g1", "checksum": "server",
            "client_modified_at": "2026-07-14T10:00:00Z",
        }]}
        local_record = {
            "guid": "g1", "notetype_id": 1, "fields": ["new"], "tags": [],
            "client_modified_at": "2026-07-14T11:00:00Z",
        }
        client = FakeClient()
        with (
            patch.object(anki_local, "note_manifest", return_value=local),
            patch.object(anki_local, "note_record", return_value=local_record),
        ):
            result = note_sync.sync_notes_once(
                object(), client, server_manifest=server, newest_wins=True
            )
        self.assertEqual(result.pushed, 1)
        payload = client.push_requests[0]["notes"][0]
        self.assertEqual(payload["base_checksum"], "server")

    def test_tied_note_times_remain_a_real_conflict(self) -> None:
        stamp = "2026-07-14T10:00:00Z"
        local = [{"guid": "g1", "checksum": "local", "modified_at": stamp}]
        server = {"notes": [{
            "guid": "g1", "checksum": "server", "client_modified_at": stamp,
        }]}
        client = FakeClient()
        with patch.object(anki_local, "note_manifest", return_value=local):
            with self.assertRaises(note_sync.NoteSyncConflict):
                note_sync.sync_notes_once(
                    object(), client, server_manifest=server, newest_wins=True
                )

    def test_server_newer_deck_and_notetype_are_pulled(self) -> None:
        deck_local = [{
            "name": "Deck", "checksum": "local",
            "modified_at": "2026-07-14T10:00:00Z",
        }]
        deck_server = {"decks": [{
            "name": "Deck", "checksum": "server",
            "client_modified_at": "2026-07-14T11:00:00Z",
        }]}
        notetype_local = [{
            "notetype_id": 1, "checksum": "local",
            "modified_at": "2026-07-14T10:00:00Z",
        }]
        notetype_server = {"notetypes": [{
            "notetype_id": 1, "checksum": "server",
            "client_modified_at": "2026-07-14T11:00:00Z",
        }]}
        client = FakeClient()
        with (
            patch.object(anki_local, "deck_manifest", return_value=deck_local),
            patch.object(anki_apply, "apply_server_deck") as apply_deck,
        ):
            decks = deck_sync.sync_decks_once(
                object(), client, server_manifest=deck_server, newest_wins=True
            )
        with (
            patch.object(anki_local, "notetype_manifest", return_value=notetype_local),
            patch.object(anki_apply, "apply_server_notetype") as apply_notetype,
        ):
            notetypes = notetype_sync.sync_notetypes_once(
                object(), client, server_manifest=notetype_server,
                newest_wins=True,
            )
        self.assertEqual(decks.pulled, 1)
        self.assertEqual(notetypes.pulled, 1)
        apply_deck.assert_called_once_with(ANY, client, "Deck")
        apply_notetype.assert_called_once_with(ANY, client, 1)

    def test_server_newer_structural_card_is_pulled(self) -> None:
        local = [{
            "logical_key": "g1:0", "card_id": 1, "checksum": "local",
            "modified_at": "2026-07-14T10:00:00Z",
        }]
        server = {"cards": [{
            "logical_key": "g1:0", "card_id": 2, "checksum": "server",
            "client_modified_at": "2026-07-14T11:00:00Z",
        }]}
        client = FakeClient(pulled={"cards": [{"card_id": 2}]})
        applied: list[int] = []
        with (
            patch.object(anki_local, "card_manifest", return_value=local),
            patch.object(anki_apply, "apply_card", side_effect=lambda _col, rec: applied.append(rec["card_id"])),
        ):
            result = card_sync.sync_cards_once(
                object(), client, server_manifest=server, newest_wins=True
            )
        self.assertEqual(result.pulled, 1)
        self.assertEqual(applied, [2])


class DesktopModeTest(unittest.TestCase):
    def test_desktop_runtime_overrides_shared_false_config(self) -> None:
        aqt = ModuleType("aqt")
        aqt.mw = SimpleNamespace(
            addonManager=SimpleNamespace(
                getConfig=lambda _addon: {
                    "kelmasync_only": False,
                    "ankiweb_hkey": "stale-shared-profile-key",
                },
                writeConfig=lambda *_args: None,
            )
        )
        aqt._kelma_bundled = SimpleNamespace(IS_KELMA_DESKTOP=True)
        old = sys.modules.get("aqt")
        sys.modules["aqt"] = aqt
        try:
            sys.modules.pop("kelma.config", None)
            from kelma import config, consts
            self.assertTrue(config.kelmasync_only())
            self.assertEqual(config.ui_services(), (consts.KELMA,))
            self.assertFalse(config.has_credentials(consts.ANKIWEB))
        finally:
            sys.modules.pop("kelma.config", None)
            if old is None:
                sys.modules.pop("aqt", None)
            else:
                sys.modules["aqt"] = old


if __name__ == "__main__":
    unittest.main()
