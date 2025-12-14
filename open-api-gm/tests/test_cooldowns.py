import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.phases import tick_cooldowns, list_usable_abilities  # noqa: E402


class TestCooldowns(unittest.TestCase):
    def test_tick_cooldowns_updates_round(self):
        state = {
            "phase": {"round": 1},
            "party": {
                "members": [
                    {
                        "abilities": [
                            {"name": "Test", "cooldown": 2, "base_cooldown": 2}
                        ]
                    }
                ]
            },
        }
        tick_cooldowns(state)
        ability = state["party"]["members"][0]["abilities"][0]
        self.assertEqual(ability["cooldown"], 1)
        self.assertEqual(ability["cooldown_round"], 2)

    def test_chain_declaration_sets_cooldown_and_round(self):
        # Mimic the play.py logic when declaring a chain
        phase_round = 3
        abilities = [
            {"name": "Alpha", "base_cooldown": 2, "cooldown": 0},
            {"name": "Beta", "base_cooldown": 0, "cooldown": 0},
        ]
        declared = ["Alpha"]
        for ability in abilities:
            if ability["name"] in declared:
                cd = ability.get("base_cooldown", ability.get("cooldown", 0) or 0)
                ability["base_cooldown"] = cd
                ability["cooldown"] = cd
                ability["cooldown_round"] = phase_round + cd if cd else phase_round

        alpha = next(a for a in abilities if a["name"] == "Alpha")
        beta = next(a for a in abilities if a["name"] == "Beta")
        self.assertEqual(alpha["cooldown"], 2)
        self.assertEqual(alpha["cooldown_round"], 5)
        self.assertEqual(beta.get("cooldown_round"), None)

    def test_usable_list_respects_cooldown(self):
        state = {
            "party": {
                "members": [
                    {
                        "abilities": [
                            {"name": "Up", "cooldown": 1},
                            {"name": "Ready", "cooldown": 0},
                        ]
                    }
                ]
            }
        }
        usable = list_usable_abilities(state)
        self.assertEqual(usable, ["Ready"])


if __name__ == "__main__":
    unittest.main()
