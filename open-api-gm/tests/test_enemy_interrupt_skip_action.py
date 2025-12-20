import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import play  # noqa: E402


class _UI:
    is_blocking = False

    def error(self, _text):
        return None


class TestEnemyInterruptSkipAction(unittest.TestCase):
    def test_interrupt_skip_clears_enemy_interrupt_awaiting(self):
        state = {
            "awaiting": {"type": "enemy_interrupt", "options": [{"id": "interrupt_no"}, {"id": "interrupt_yes"}]},
            "phase": {"current": "chain_resolution"},
        }
        ui = _UI()

        _, should_return = play.resolve_awaiting(state, ui, {"action": "interrupt_skip"})

        self.assertFalse(should_return)
        self.assertNotIn("awaiting", state)
        self.assertIs(state.get("pending_enemy_interrupt"), False)


if __name__ == "__main__":
    unittest.main()

