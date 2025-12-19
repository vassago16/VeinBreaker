import sys
import copy
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.action_resolution import resolve_action_step, apply_action_effects  # noqa: E402
from engine.status import tick_statuses  # noqa: E402


def load_ability(name):
    data = json.loads((ROOT / "game-data" / "abilities.json").read_text(encoding="utf-8"))
    abilities = {a["name"]: a for a in data.get("abilities", [])}
    return copy.deepcopy(abilities[name])


def base_character():
    return {
        "resources": {"hp": 12, "resolve": 3, "momentum": 0, "heat": 0, "balance": 0, "idf": 1},
        "stats": {"DEX": 12, "STR": 12, "WIS": 12},
        "abilities": [],
        "temp_bonuses": {},
    }


class TestEngineEffects(unittest.TestCase):
    def test_cutpoint_slice_applies_bleed_and_momentum(self):
        ability = load_ability("Cutpoint Slice")
        character = base_character()
        enemy = {"hp": 10, "dv_base": 5, "idf": 0, "momentum": 0, "stat_block": {"defense": {"dv_base": 5}}}
        state = {"log": []}

        resolve_action_step(state, character, ability, attack_roll=15, balance_bonus=0)
        apply_action_effects(state, character, [enemy], defense_d20=0)

        # Enemy should have Bleed status applied
        statuses = enemy.get("statuses", {})
        self.assertIn("bleed", statuses)
        self.assertEqual(statuses["bleed"].get("stacks"), 1)
        # Character should gain momentum from the effect
        self.assertEqual(character["resources"].get("momentum"), 1)

        # Bleed ticks at end of round (manual tick in this unit test)
        hp_before = enemy["hp"]
        tick_statuses(enemy)
        self.assertEqual(enemy["hp"], hp_before - 1)
        # Bleed decays by 1 stack each tick
        self.assertEqual(enemy.get("statuses", {}).get("bleed", {}).get("stacks", 0), 0)

    def test_focus_action_grants_attack_bonus_and_momentum(self):
        ability = load_ability("Focus Action")
        character = base_character()
        enemy = {"hp": 10, "dv_base": 0, "idf": 0, "momentum": 0, "stat_block": {"defense": {"dv_base": 0}}}
        state = {"log": []}

        resolve_action_step(state, character, ability, attack_roll=10, balance_bonus=0)
        apply_action_effects(state, character, [enemy], defense_d20=0)

        # Temp attack bonus should be present
        self.assertEqual(character.get("temp_bonuses", {}).get("attack"), 1)
        # Momentum gain from on_use + resourceDelta (both present)
        self.assertEqual(character["resources"].get("momentum"), 2)


if __name__ == "__main__":
    unittest.main()
