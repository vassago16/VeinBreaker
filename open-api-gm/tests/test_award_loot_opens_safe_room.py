import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import play  # noqa: E402
from ui.web_provider import WebProvider  # noqa: E402


class _Session:
    def __init__(self):
        self.events = []

    def emit(self, payload):
        self.events.append(payload)


class TestAwardLootOpensSafeRoom(unittest.TestCase):
    def test_award_loot_choice_emits_safe_room_enter(self):
        session = _Session()
        ui = WebProvider(session)

        phase_machine = json.loads((ROOT / "canon" / "phase_machine.json").read_text(encoding="utf-8"))
        state = {
            "seed": 1,
            "phase": {"current": "out_of_combat", "round": 0, "round_started": False},
            "party": {
                "members": [
                    {
                        "id": "pc_1",
                        "name": "Test",
                        "tier": 1,
                        "abilities": [],
                        "resources": {"hp": 10, "hp_max": 10, "resolve": 3, "resolve_cap": 5, "veinscore": 0},
                    }
                ]
            },
            "enemies": [],
            "log": [],
        }
        ctx = {"state": state, "ui": ui, "phase_machine": phase_machine, "game_data": {"abilities": {"abilities": []}}}

        # First tick should emit the player choice list (including award_loot).
        play.game_step(ctx, {"action": "tick"})
        choice_events = [e for e in session.events if isinstance(e, dict) and e.get("type") == "choice"]
        self.assertTrue(choice_events)
        options = choice_events[-1].get("options") or []
        self.assertIn("award_loot", options)
        idx = options.index("award_loot")

        # Selecting award_loot should open the safe-room (level-up) screen.
        play.game_step(ctx, {"choice": idx})
        types = [e.get("type") for e in session.events if isinstance(e, dict)]
        self.assertIn("safe_room_enter", types)
        self.assertEqual(state.get("mode"), "safe_room")


if __name__ == "__main__":
    unittest.main()
