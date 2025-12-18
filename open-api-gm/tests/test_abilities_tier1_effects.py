import sys
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.action_resolution import (
    resolve_action_step,
    apply_action_effects,
    apply_effect_list,
)  # noqa: E402
from engine.status import tick_statuses  # noqa: E402


def load_ability(name):
    data = json.loads((ROOT / "game-data" / "abilities.json").read_text(encoding="utf-8"))
    abilities = {a["name"]: a for a in data.get("abilities", [])}
    return json.loads(json.dumps(abilities[name]))  # deep copy via json


def base_character():
    return {
        "resources": {"hp": 12, "resolve": 3, "momentum": 0, "heat": 0, "balance": 0, "idf": 1, "rp": 0},
        "stats": {"DEX": 12, "STR": 12, "WIS": 12, "INT": 12},
        "abilities": [],
        "temp_bonuses": {},
    }


def base_enemy():
    return {"hp": 10, "dv_base": 0, "idf": 0, "momentum": 0, "stat_block": {"defense": {"dv_base": 0}}}


class TestTier1AbilityEffects(unittest.TestCase):
    def test_pulse_strike_damage_and_momentum(self):
        ability = load_ability("Pulse Strike")
        character = base_character()
        enemy = base_enemy()
        state = {"log": []}
        with patch("engine.action_resolution.roll", return_value=3):
            resolve_action_step(state, character, ability, attack_roll=15, balance_bonus=0)
            apply_action_effects(state, character, [enemy], defense_d20=None)
        self.assertLess(enemy["hp"], 10)
        self.assertEqual(character["resources"].get("momentum"), 1)

    def test_stoneguard_step_sets_reduction_and_on_success(self):
        ability = load_ability("Stoneguard Step")
        character = base_character()
        enemy = base_enemy()
        apply_effect_list(ability.get("effects", {}).get("on_use", []), actor=character, enemy=enemy, default_target="self")
        self.assertTrue(character.get("damage_reduction"))
        # simulate full block
        apply_effect_list(ability.get("effects", {}).get("on_success", []), actor=character, enemy=enemy, default_target="self")
        self.assertEqual(character["resources"].get("momentum"), 1)

    def test_stonepulse_rhythm_grants_rp_momentum_attack_bonus(self):
        ability = load_ability("Stonepulse Rhythm")
        character = base_character()
        enemy = base_enemy()
        state = {"log": []}
        resolve_action_step(state, character, ability, attack_roll=10, balance_bonus=0)
        apply_action_effects(state, character, [enemy], defense_d20=None)
        self.assertEqual(character["resources"].get("rp"), 1)
        self.assertEqual(character["resources"].get("momentum"), 2)
        self.assertEqual(character.get("temp_bonuses", {}).get("attack"), 1)

    def test_oathbound_guard_reduction_and_defense_bonus(self):
        ability = load_ability("Oathbound Guard")
        character = base_character()
        enemy = base_enemy()
        apply_effect_list(ability.get("effects", {}).get("on_use", []), actor=character, enemy=enemy, default_target="self")
        self.assertTrue(character.get("damage_reduction"))
        self.assertEqual(character.get("temp_bonuses", {}).get("defense"), 1)
        apply_effect_list(ability.get("effects", {}).get("on_success", []), actor=character, enemy=enemy, default_target="self")
        self.assertEqual(character["resources"].get("momentum"), 1)

    def test_hymn_of_embers_radiance_and_momentum(self):
        ability = load_ability("Hymn of Embers")
        character = base_character()
        enemy = base_enemy()
        state = {"log": []}
        resolve_action_step(state, character, ability, attack_roll=10, balance_bonus=0)
        apply_action_effects(state, character, [enemy], defense_d20=None)
        self.assertEqual(character["resources"].get("momentum"), 2)
        self.assertEqual(character["resources"].get("radiance"), 2)
        self.assertEqual(character.get("temp_bonuses", {}).get("attack"), 1)

    def test_radiant_glide_radiance_and_momentum(self):
        ability = load_ability("Radiant Glide")
        character = base_character()
        enemy = base_enemy()
        state = {"log": []}
        resolve_action_step(state, character, ability, attack_roll=10, balance_bonus=0)
        apply_action_effects(state, character, [enemy], defense_d20=None)
        self.assertEqual(character["resources"].get("momentum"), 2)
        self.assertEqual(character["resources"].get("radiance"), 2)

    def test_cutpoint_slice_bleed_and_momentum(self):
        ability = load_ability("Cutpoint Slice")
        character = base_character()
        enemy = base_enemy()
        state = {"log": []}
        with patch("engine.action_resolution.roll", return_value=2):
            resolve_action_step(state, character, ability, attack_roll=15, balance_bonus=0)
            apply_action_effects(state, character, [enemy], defense_d20=None)
        self.assertEqual(character["resources"].get("momentum"), 1)
        self.assertIn("bleed", enemy.get("statuses", {}))
        hp_before = enemy["hp"]
        tick_statuses(enemy)
        self.assertLess(enemy["hp"], hp_before)

    def test_veil_step_reduction_and_bleed_on_success(self):
        ability = load_ability("Veil Step")
        character = base_character()
        enemy = base_enemy()
        apply_effect_list(ability.get("effects", {}).get("on_use", []), actor=character, enemy=enemy, default_target="self")
        # simulate full block
        apply_effect_list(ability.get("effects", {}).get("on_success", []), actor=character, enemy=enemy, default_target="self")
        self.assertEqual(character["resources"].get("momentum"), 1)
        self.assertIn("bleed", enemy.get("statuses", {}))

    def test_charge_bolt_damage_and_momentum(self):
        ability = load_ability("Charge Bolt")
        character = base_character()
        enemy = base_enemy()
        state = {"log": []}
        with patch("engine.action_resolution.roll", return_value=3):
            resolve_action_step(state, character, ability, attack_roll=15, balance_bonus=0)
            apply_action_effects(state, character, [enemy], defense_d20=None)
        self.assertLess(enemy["hp"], 10)
        self.assertEqual(character["resources"].get("momentum"), 1)

    def test_warding_pulse_reduction_and_on_success_damage(self):
        ability = load_ability("Warding Pulse")
        character = base_character()
        enemy = base_enemy()
        apply_effect_list(ability.get("effects", {}).get("on_use", []), actor=character, enemy=enemy, default_target="self")
        apply_effect_list(ability.get("effects", {}).get("on_success", []), actor=character, enemy=enemy, default_target="self")
        self.assertEqual(character["resources"].get("momentum"), 1)
        self.assertEqual(enemy["hp"], 9)  # hp -1 from on_success (target override)

    def test_arcane_channel_attack_bonus_and_rp(self):
        ability = load_ability("Arcane Channel")
        character = base_character()
        enemy = base_enemy()
        state = {"log": []}
        resolve_action_step(state, character, ability, attack_roll=10, balance_bonus=0)
        apply_action_effects(state, character, [enemy], defense_d20=None)
        self.assertEqual(character["resources"].get("momentum"), 2)
        self.assertEqual(character["resources"].get("rp"), 1)
        self.assertEqual(character.get("temp_bonuses", {}).get("attack"), 1)


if __name__ == "__main__":
    unittest.main()
