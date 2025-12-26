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


class TestActSelectionOnEnterEncounter(unittest.TestCase):
    def test_start_prompt_offers_acts_and_jump_works(self):
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
        ctx = {
            "state": state,
            "ui": ui,
            "phase_machine": phase_machine,
            "game_data": {"enemy_by_id": {}, "bestiary_meta": {}, "abilities": {"abilities": []}},
        }

        play.game_step(ctx, {"action": "start"})
        choice_events = [e for e in session.events if isinstance(e, dict) and e.get("type") == "choice"]
        self.assertTrue(choice_events)
        options = choice_events[-1].get("options") or []
        self.assertIn("enter_encounter", options)
        self.assertTrue(any(isinstance(o, str) and "Start Act" in o for o in options))

        # Jump to Act 3.
        act3_idx = next(i for i, opt in enumerate(options) if isinstance(opt, str) and "Act 3" in opt)
        play.game_step(ctx, {"choice": act3_idx})

        self.assertEqual(state.get("scene_id"), "scene.03.01")

        # After the jump, we should be back on a normal enter-encounter prompt (no act selector).
        choice_events = [e for e in session.events if isinstance(e, dict) and e.get("type") == "choice"]
        options = choice_events[-1].get("options") or []
        self.assertIn("enter_encounter", options)
        self.assertFalse(any(isinstance(o, str) and "Start Act" in o for o in options))


if __name__ == "__main__":
    unittest.main()

