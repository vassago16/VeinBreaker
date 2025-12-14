import sys
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.action_resolution import resolve_action_step, apply_action_effects  # noqa: E402
from engine.status import tick_statuses  # noqa: E402


def load_ability(name):
    data = json.loads((ROOT / "game-data" / "abilities.json").read_text(encoding="utf-8"))
    abilities = {a["name"]: a for a in data.get("abilities", [])}
    return json.loads(json.dumps(abilities[name]))  # deep copy


def base_character():
    return {
        "resources": {"hp": 12, "resolve": 3, "momentum": 0, "heat": 0, "balance": 0, "idf": 1, "rp": 0},
        "stats": {"STR": 12},
        "temp_bonuses": {},
    }


def base_enemy():
    return {"hp": 12, "dv_base": 0, "idf": 0, "momentum": 0, "stat_block": {"defense": {"dv_base": 0}}, "statuses": {}}


class TestTier2Stonepulse(unittest.TestCase):
    def test_resonant_break_damage_stagger_and_resources(self):
        ability = load_ability("Resonant Break")
        character = base_character()
        enemy = base_enemy()
        state = {"log": []}
        with patch("engine.action_resolution.roll", return_value=4):
            resolve_action_step(state, character, ability, attack_roll=15, balance_bonus=0)
            apply_action_effects(state, character, [enemy], defense_d20=None)
        # Damage applied
        self.assertLess(enemy["hp"], 12)
        # Stagger applied
        self.assertIn("stagger", enemy.get("statuses", {}))
        # Momentum and RP gains
        self.assertEqual(character["resources"].get("momentum"), 2)
        self.assertEqual(character["resources"].get("rp"), 1)

    def test_anchored_form_reduction_and_retaliate(self):
        ability = load_ability("Anchored Form")
        character = base_character()
        enemy = base_enemy()
        # on_use reduce_damage
        resolve_action_step({"log": []}, character, ability, attack_roll=10, balance_bonus=0)
        # simulate success effects
        from engine.action_resolution import apply_effect_list  # local import to avoid circular

        apply_effect_list(ability.get("effects", {}).get("on_success", []), actor=character, enemy=enemy, default_target="self")
        self.assertEqual(character["resources"].get("momentum"), 1)
        self.assertIn("retaliate", character.get("statuses", {}))

    def test_stonepulse_focus_bonuses(self):
        ability = load_ability("Stonepulse Focus")
        character = base_character()
        enemy = base_enemy()
        state = {"log": []}
        resolve_action_step(state, character, ability, attack_roll=10, balance_bonus=0)
        apply_action_effects(state, character, [enemy], defense_d20=None)
        tb = character.get("temp_bonuses", {})
        self.assertEqual(tb.get("attack"), 1)
        self.assertEqual(tb.get("defense"), 1)
        self.assertEqual(tb.get("idf"), 1)
        self.assertEqual(character["resources"].get("momentum"), 2)

    def test_stonepulse_stance_applies_bonuses_and_status(self):
        ability = load_ability("Stonepulse Stance")
        character = base_character()
        enemy = base_enemy()
        state = {"log": []}
        resolve_action_step(state, character, ability, attack_roll=10, balance_bonus=0)
        apply_action_effects(state, character, [enemy], defense_d20=None)
        tb = character.get("temp_bonuses", {})
        self.assertEqual(tb.get("defense"), 1)
        self.assertEqual(tb.get("idf"), 1)
        self.assertEqual(character["resources"].get("momentum"), 2)
        self.assertIn("stonepulse_stance", character.get("statuses", {}))
        # stance duration should tick down
        tick_statuses(character)
        self.assertIn("stonepulse_stance", character.get("statuses", {}))


if __name__ == "__main__":
    unittest.main()
