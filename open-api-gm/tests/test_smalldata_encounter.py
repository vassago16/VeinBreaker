import json
import sys
from copy import deepcopy
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from unittest.mock import patch  # noqa: E402

from engine.action_resolution import resolve_action_step, apply_action_effects  # noqa: E402


def load_data():
    abilities = json.loads((ROOT / "smalldata" / "abilities.json").read_text(encoding="utf-8"))
    encounter = json.loads((ROOT / "smalldata" / "encounter_example_01.json").read_text(encoding="utf-8"))
    return abilities, encounter


def load_ability(abilities, name):
    for a in abilities["abilities"]:
        if a.get("name") == name:
            return deepcopy(a)
    raise KeyError(f"Ability not found: {name}")


def run_chain(abilities_data, encounter_data, chain, rolls):
    state = {"log": [], "pending_action": None}
    character = deepcopy(encounter_data["player"])
    enemy = deepcopy(encounter_data["enemy"]["instance"])
    enemies = [enemy]

    for ability_name, d20 in zip(chain, rolls):
        ability = load_ability(abilities_data, ability_name)
        resolve_action_step(state, character, ability, attack_roll=d20)
        apply_action_effects(state, character, enemies)

    return state, character, enemy


def run_smalldata_chain(
    chain,
    attack_rolls,
    damage_rolls=None,
    abilities_path=ROOT / "smalldata" / "abilities.json",
    encounter_path=ROOT / "smalldata" / "encounter_example_01.json",
):
    """
    Helper for quick iterative checks: pass ability names and d20 rolls, optionally
    deterministic damage_rolls (list of ints). Returns (state, character, enemy).
    """
    abilities = json.loads(Path(abilities_path).read_text(encoding="utf-8"))
    encounter = json.loads(Path(encounter_path).read_text(encoding="utf-8"))

    if damage_rolls is None:
        return run_chain(abilities, encounter, chain, attack_rolls)

    with patch("engine.action_resolution.roll", side_effect=damage_rolls):
        return run_chain(abilities, encounter, chain, attack_rolls)


class TestSmallerEncounterChains(unittest.TestCase):
    def test_scripted_chain_smoke(self):
        abilities, encounter = load_data()
        scenario = {
            "name": "example_chain",
            "chain": ["Basic Strike", "Pulse Strike", "Stonepulse Step"],
            "rolls": [14, 9, 17],
            "expected_enemy_hp": 0,
            "expected_player_heat": 3,
            "expected_player_momentum": 3,
        }

        with self.subTest(scenario=scenario["name"]):
            with patch("engine.action_resolution.roll", side_effect=[2, 2, 2]):
                _state, character, enemy = run_chain(
                    abilities, encounter, scenario["chain"], scenario["rolls"]
                )
            self.assertEqual(enemy["hp"], scenario["expected_enemy_hp"])
            self.assertEqual(character["resources"]["heat"], scenario["expected_player_heat"])
            self.assertEqual(character["resources"]["momentum"], scenario["expected_player_momentum"])


if __name__ == "__main__":
    unittest.main()
