import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.smalldata.run_player_interrupt_example import (  # noqa: E402
    apply_feedback_shield,
    load_ability,
)


class TestFeedbackShieldInterrupt(unittest.TestCase):
    def test_reflects_when_damage_fully_blocked(self):
        ability = load_ability("Feedback Shield")
        character = {"stats": {"INT": 14}, "resources": {"hp": 12, "momentum": 0}}
        enemy = {"hp": 15}

        result = apply_feedback_shield(
            character, enemy, incoming_damage=4, shield_roll=5, ability=ability
        )

        self.assertEqual(result["damage_after_shield"], 0)  # fully blocked
        self.assertEqual(result["reflected_damage"], 1)  # INT 14 => mod +1
        self.assertEqual(enemy["hp"], 14)  # took reflected damage
        self.assertEqual(character["resources"]["hp"], 12)  # no damage through
        self.assertEqual(character["resources"]["momentum"], 1)  # gained momentum


if __name__ == "__main__":
    unittest.main()
