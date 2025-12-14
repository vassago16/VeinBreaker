import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.interrupt_controller import InterruptController  # noqa: E402


class TestInterruptController(unittest.TestCase):
    def test_should_interrupt_respects_budget_and_trigger(self):
        enemy = {
            "resolved_archetype": {
                "rhythm_profile": {
                    "interrupt": {
                        "budget_per_round": 1,
                        "windows": [
                            {"after_action_index": [2], "trigger_if": {"player_missed_last_action": True}, "weight": 1.0}
                        ]
                    }
                }
            }
        }
        state = {"log": [{"action_effects": {"hit": False}}], "party": {"members": [{"chain": {"abilities": ["a", "b", "c"]}}]}}
        ic = InterruptController(enemy)
        # First opportunity should pass (action_index 1 -> after_action_index=2)
        self.assertTrue(ic.should_interrupt(state, action_index=1))
        # Budget spent; next should be False
        self.assertFalse(ic.should_interrupt(state, action_index=2))


if __name__ == "__main__":
    unittest.main()
