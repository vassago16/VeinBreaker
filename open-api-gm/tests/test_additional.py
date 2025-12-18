import sys
import json
import random
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.status import apply_status_effects, tick_statuses  # noqa: E402
from engine.interrupt_controller import InterruptController  # noqa: E402
from engine.apply import pick_enemy  # noqa: E402
from play import build_enemy_chain, veinscore_value, award_veinscore, select_loot  # noqa: E402


class TestEnemyChainBuilder(unittest.TestCase):
    def test_respects_rp_costs(self):
        enemy = {
            "rp_pool": 3,
            "rp": 3,
            "moves": [
                {"id": "m1", "cost": {"rp": 2}},
                {"id": "m2", "cost": {"rp": 2}},
            ],
        }
        chain = build_enemy_chain(enemy)
        # Only first move fits into RP 3 (2 spent, 1 remaining, second skipped)
        self.assertEqual(len(chain), 1)
        self.assertEqual(chain[0]["id"], "m1")


class TestInterruptTriggers(unittest.TestCase):
    def test_chain_length_trigger(self):
        enemy = {
            "resolved_archetype": {
                "rhythm_profile": {
                    "interrupt": {
                        "budget_per_round": 1,
                        "windows": [
                            {"after_action_index": [2], "trigger_if": {"chain_length_gte": 2}, "weight": 1.0}
                        ],
                    }
                }
            }
        }
        state = {"party": {"members": [{"chain": {"abilities": ["a", "b"]}}]}, "log": []}
        ic = InterruptController(enemy)
        self.assertTrue(ic.should_interrupt(state, action_index=1))

    def test_player_heat_trigger(self):
        enemy = {
            "resolved_archetype": {
                "rhythm_profile": {
                    "interrupt": {
                        "budget_per_round": 1,
                        "windows": [
                            {"after_action_index": [1], "trigger_if": {"player_heat_gte": 3}, "weight": 1.0}
                        ],
                    }
                }
            }
        }
        state = {"party": {"members": [{"chain": {"abilities": ["a"]}, "resources": {"heat": 4}}]}, "log": []}
        ic = InterruptController(enemy)
        self.assertTrue(ic.should_interrupt(state, action_index=0))


class TestStatusExpiry(unittest.TestCase):
    def test_arcane_ward_expires(self):
        target = {"hp": 5}
        apply_status_effects(target, [{"type": "arcane ward", "duration": 2}])
        tick_statuses(target)
        self.assertIn("arcane ward", target["statuses"])
        tick_statuses(target)
        self.assertNotIn("arcane ward", target["statuses"])

    def test_intangible_expires(self):
        target = {"hp": 5}
        apply_status_effects(target, [{"type": "intangible", "duration": 1}])
        tick_statuses(target)
        self.assertNotIn("intangible", target["statuses"])


class TestLootVeinscore(unittest.TestCase):
    def test_veinscore_lookup_and_award(self):
        game_data = {
            "veinscore_loot": [
                {"name": "Faint Vein Sigil", "veinscore": 1},
                {"name": "True Vein Sigil", "veinscore": 10},
            ]
        }
        faint_vs = veinscore_value("Faint Vein Sigil", game_data)
        self.assertEqual(faint_vs, 1)
        character = {"resources": {"veinscore": 0}}
        award_veinscore(character, faint_vs * 2)
        self.assertEqual(character["resources"]["veinscore"], 2)

    def test_select_loot_by_tier(self):
        loot_table = [
            {"name": "Tier1 Item", "tier": 1},
            {"name": "Tier2 Item", "tier": 2},
        ]
        game_data = {"loot": loot_table}
        enemy = {"tier": 2}
        with patch.object(random, "choice", return_value=loot_table[1]):
            loot = select_loot(game_data, enemy)
        self.assertEqual(loot["name"], "Tier2 Item")


if __name__ == "__main__":
    unittest.main()
