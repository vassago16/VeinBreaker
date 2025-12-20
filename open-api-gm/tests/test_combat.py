import sys
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.action_resolution import resolve_action_step, apply_action_effects  # noqa: E402
from engine.interrupt_controller import apply_interrupt  # noqa: E402


def load_ability(name):
    data = json.loads((ROOT / "game-data" / "abilities.json").read_text(encoding="utf-8"))
    abilities = {a["name"]: a for a in data.get("abilities", [])}
    return abilities[name]


def base_enemy():
    return {"hp": 10, "dv_base": 5, "idf": 0, "momentum": 0, "stat_block": {"defense": {"dv_base": 5}}}


def base_character():
    return {
        "resources": {"hp": 12, "resolve": 3, "momentum": 0, "heat": 0, "balance": 0, "idf": 1},
        "stats": {"POW": 10, "AGI": 10, "MND": 10},
        "abilities": [],
        "temp_bonuses": {},
    }


class TestCombatMechanics(unittest.TestCase):
    def test_basic_attack_vs_static_dv(self):
        ability = load_ability("Basic Strike")
        character = base_character()
        enemy = base_enemy()
        state = {"log": []}
        # Fixed damage roll = 3
        with patch("engine.action_resolution.roll", return_value=3):
            resolve_action_step(state, character, ability, attack_roll=15, balance_bonus=0)
            result = apply_action_effects(state, character, [enemy], defense_d20=None)
        self.assertEqual(result, "action_applied")
        # Heat bonus when prior heat=0 is 0
        self.assertEqual(enemy["hp"], 7)

    def test_interrupt_breaks_chain_on_margin(self):
        character = base_character()
        character["chain"] = {"declared": True, "abilities": ["a"], "invalidated": False}
        enemy = base_enemy()
        enemy["resolved_archetype"] = {
            "rhythm_profile": {
                "interrupt": {
                    "margin_rules": {"break_chain_on_margin_gte": 2},
                }
            }
        }
        # Force rolls: enemy atk 15, player def 10 => margin 5 => chain invalidated
        # 2d10 rolls: (7+8)=15, (4+6)=10, damage roll=1
        with patch("random.randint", side_effect=[7, 8, 4, 6, 1]):
            hit, dmg, rolls, chain_broken = apply_interrupt({"phase": {}}, character, enemy)
        self.assertTrue(character.get("chain", {}).get("invalidated", False))


if __name__ == "__main__":
    unittest.main()
