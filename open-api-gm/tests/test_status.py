import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.status import apply_status_effects, tick_statuses  # noqa: E402


class TestStatus(unittest.TestCase):
    def test_bleed_stacks_and_ticks(self):
        target = {"hp": 10}
        apply_status_effects(target, [{"type": "bleed", "stacks": 1}])
        apply_status_effects(target, [{"type": "bleed", "stacks": 2}])
        self.assertIn("bleed", target["statuses"])
        self.assertEqual(target["statuses"]["bleed"]["stacks"], 3)
        tick_statuses(target)
        self.assertEqual(target["hp"], 7)

    def test_non_stacking_extends_duration(self):
        target = {"hp": 0}
        apply_status_effects(target, [{"type": "invisibility"}], default_duration=2)
        first_dur = target["statuses"]["invisibility"]["duration"]
        apply_status_effects(target, [{"type": "invisibility"}], default_duration=2)
        self.assertGreater(target["statuses"]["invisibility"]["duration"], first_dur)


if __name__ == "__main__":
    unittest.main()
