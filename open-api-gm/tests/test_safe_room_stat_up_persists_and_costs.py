import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import play  # noqa: E402


class _Session:
    def __init__(self):
        self.events = []

    def emit(self, payload):
        self.events.append(payload)


class _Provider:
    def __init__(self, session):
        self.session = session


class _UI:
    is_blocking = False

    def __init__(self, session):
        self.provider = _Provider(session)

    def system(self, _text):
        return None

    def error(self, _text):
        return None


class TestSafeRoomStatUpPersistsAndCosts(unittest.TestCase):
    def test_stat_up_charges_and_updates_normalized_stat(self):
        session = _Session()
        ui = _UI(session)
        phase_machine = play.load_canon().get("phase_machine.json")
        state = {
            "phase": {"current": "out_of_combat"},
            "mode": "safe_room",
            "party": {
                "members": [
                    {
                        "id": "character.test_stat_up",
                        "name": "Test",
                        "tier": 1,
                        "resources": {"hp": 10, "hp_max": 10, "resolve": 3, "resolve_cap": 5, "veinscore": 6},
                        # Simulate legacy/normalized attribute style (what the HUD uses).
                        "attributes": {"str": 8, "dex": 8, "int": 8, "wil": 8},
                        "abilities": [],
                    }
                ]
            },
        }
        ctx = {"state": state, "ui": ui, "game_data": {"abilities": {"abilities": []}}, "phase_machine": phase_machine}

        with patch.object(play, "save_profile_and_state", lambda *_a, **_k: None):
            handled = play.game_step(ctx, {"action": "safe_room_stat_up", "stat": "POW"})
            self.assertTrue(handled)

        ch = state["party"]["members"][0]
        self.assertEqual(int(ch["resources"]["veinscore"]), 3)
        # Both canonical and normalized keys should be updated in sync.
        self.assertEqual(int(ch["attributes"]["POW"]), 9)
        self.assertEqual(int(ch["attributes"]["str"]), 9)


if __name__ == "__main__":
    unittest.main()
