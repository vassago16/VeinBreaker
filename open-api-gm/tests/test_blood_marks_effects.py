import sys
import copy
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.action_resolution import apply_action_effects  # noqa: E402


def load_ability_by_name(name: str) -> dict:
    data = json.loads((ROOT / "game-data" / "abilities.json").read_text(encoding="utf-8"))
    abilities = {a["name"]: a for a in data.get("abilities", [])}
    return copy.deepcopy(abilities[name])


class TestBloodMarksEffects(unittest.TestCase):
    def test_blood_mark_1_adds_damage_vs_wounded(self):
        ability = load_ability_by_name("Basic Strike")
        ability["addStatToDamage"] = False
        ability["addStatToAttackRoll"] = False

        state = {"log": []}
        player = {"resources": {"resolve": 0, "resolve_cap": 5, "heat": 0}, "stats": {"POW": 0}, "marks": {"blood": 1}}
        enemy = {"hp": {"current": 4, "max": 10}, "dv_base": 0, "idf": 0, "momentum": 0, "stat_block": {"defense": {"dv_base": 0}}}

        state["pending_action"] = {
            "ability": "Basic Strike",
            "ability_obj": ability,
            "to_hit": 99,
            "attack_d20": 10,
            "damage_roll": 2,
            "tags": [],
            "cancelled": False,
            "log": {"attack_d20": 10},
        }

        apply_action_effects(state, player, [enemy], defense_d20=None)
        self.assertEqual(enemy["hp"]["current"], 1)  # 2 base +1 wounded bonus = 3 damage

    def test_blood_mark_2_grants_rp_on_crit(self):
        ability = load_ability_by_name("Basic Strike")
        ability["addStatToDamage"] = False
        ability["addStatToAttackRoll"] = False

        state = {"log": []}
        player = {"resources": {"resolve": 0, "resolve_cap": 5, "heat": 0}, "stats": {"POW": 0}, "marks": {"blood": 2}}
        enemy = {"hp": {"current": 10, "max": 10}, "dv_base": 0, "idf": 0, "momentum": 0, "stat_block": {"defense": {"dv_base": 0}}}

        state["pending_action"] = {
            "ability": "Basic Strike",
            "ability_obj": ability,
            "to_hit": 99,
            "attack_d20": 20,
            "damage_roll": 1,
            "tags": [],
            "cancelled": False,
            "log": {"attack_d20": 20},
        }

        apply_action_effects(state, player, [enemy], defense_d20=None)
        self.assertEqual(player["resources"]["resolve"], 1)


if __name__ == "__main__":
    unittest.main()

