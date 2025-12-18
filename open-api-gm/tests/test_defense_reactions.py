import sys
from pathlib import Path
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.action_resolution import resolve_defense_reaction  # noqa: E402
from engine.interrupt_controller import apply_interrupt  # noqa: E402


class TestDefenseReactions(unittest.TestCase):
    def setUp(self):
        self.ability = {
            "name": "Feedback Shield",
            "dice": "1d6",
            "stat": "INT",
            "tags": ["momentum", "defense"],
        }

    def test_full_block_reflects_and_preserves_hp(self):
        state = {"log": []}
        defender = {"stats": {"INT": 14}, "resources": {"hp": 12, "momentum": 0}}
        attacker = {"hp": 15}

        summary = resolve_defense_reaction(
            state, defender, attacker, self.ability, incoming_damage=4, block_roll=5
        )

        self.assertEqual(summary["damage_after_block"], 0)
        self.assertEqual(summary["reflected_damage"], 1)  # INT 14 => +1
        self.assertEqual(attacker["hp"], 14)
        self.assertEqual(defender["resources"]["hp"], 12)
        self.assertEqual(defender["resources"]["momentum"], 1)
        self.assertEqual(summary["momentum_gained"], 1)
        self.assertEqual(state["log"][-1]["defense_reaction"]["damage_after_block"], 0)

    def test_partial_block_stops_reflect_and_takes_damage(self):
        state = {"log": []}
        defender = {"stats": {"INT": 14}, "resources": {"hp": 12, "momentum": 0}}
        attacker = {"hp": 15}

        summary = resolve_defense_reaction(
            state, defender, attacker, self.ability, incoming_damage=8, block_roll=3
        )

        self.assertEqual(summary["damage_after_block"], 5)
        self.assertEqual(summary["reflected_damage"], 0)
        self.assertEqual(attacker["hp"], 15)
        self.assertEqual(defender["resources"]["hp"], 7)
        self.assertEqual(defender["resources"]["momentum"], 1)
        self.assertEqual(summary["momentum_gained"], 1)
        self.assertEqual(state["log"][-1]["defense_reaction"]["damage_after_block"], 5)

    def test_apply_interrupt_with_defense_reaction_blocks_damage_and_reflects(self):
        state = {"log": []}
        defender = {"stats": {"INT": 14}, "resources": {"hp": 12, "momentum": 0}}
        defender["chain"] = {"declared": True, "abilities": ["a"], "invalidated": False}
        attacker = {
            "hp": 10,
            "attack_mod": 0,
            "stat_block": {"damage_profile": {"baseline": {"dice": "1d6", "flat": 0}}},
            "resolved_archetype": {"rhythm_profile": {"interrupt": {"margin_rules": {"break_chain_on_margin_gte": 20}}}},
        }
        ability = {
            "name": "Feedback Shield",
            "dice": "1d6",
            "stat": "INT",
            "tags": ["momentum", "defense"],
        }

        # Force: atk d20=15, def d20=5 => hit; damage roll=4; block roll=5 -> full block + reflect 1
        with mock.patch("random.randint", side_effect=[15, 5, 4]):
            hit, dmg, rolls = apply_interrupt(
                state, defender, attacker, defense_ability=ability, defense_block_roll=5
            )

        self.assertTrue(hit)
        self.assertEqual(dmg, 0)  # fully blocked
        self.assertEqual(defender["resources"]["hp"], 12)
        self.assertEqual(defender["resources"]["momentum"], 1)
        self.assertEqual(attacker["hp"], 9)  # reflected 1
        self.assertEqual(state["log"][-1]["defense_reaction"]["damage_after_block"], 0)


if __name__ == "__main__":
    unittest.main()
