import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flow.chain_declaration import prompt_chain_declaration  # noqa: E402
from flow.character_creation import (
    prompt_choice,
    prompt_attributes,
    prompt_ability_choice,
)  # noqa: E402


class TestChainDeclaration(unittest.TestCase):
    def test_prompt_chain_declaration_selects_indices(self):
        state = {
            "phase": {"resolve_regen": (3, 2, 5)},
            "game_data": {"abilities": {"poolByPath": {"core": "resolve"}}},
        }
        character = {
            "abilities": [
                {"name": "MoveA", "path": "core", "cost": 1, "effect": "A"},
                {"name": "MoveB", "path": "core", "cost": 1, "effect": "B"},
                {"name": "MoveC", "path": "core", "cost": 1, "effect": "C"},
            ],
            "pools": {},
            "resources": {"resolve": 3, "resolve_cap": 5},
        }
        usable = ["MoveA", "MoveB", "MoveC"]
        with patch("builtins.input", return_value="1 3"):
            picks = prompt_chain_declaration(state, character, usable)
        self.assertEqual(picks, ["MoveA", "MoveC"])


class TestCharacterCreationPrompts(unittest.TestCase):
    def test_prompt_choice_single(self):
        options = ["a", "b", "c"]
        with patch("builtins.input", return_value="2"):
            choice = prompt_choice(options, show_desc={"a": "A", "b": "B", "c": "C"})
        self.assertEqual(choice, "b")

    def test_prompt_attributes_distribution(self):
        # distribute 2,3,4,0 points; leaves remaining=9 -> noted in output
        inputs = ["2", "3", "4", "0"]
        with patch("builtins.input", side_effect=inputs):
            attrs, remaining = prompt_attributes(total_points=18, base=8, max_val=14)
        self.assertEqual(attrs["POW"], 10)
        self.assertEqual(attrs["AGI"], 11)
        self.assertEqual(attrs["MND"], 12)
        self.assertEqual(attrs["SPR"], 8)
        self.assertEqual(remaining, 9)

    def test_prompt_ability_choice(self):
        abilities = [
            {"name": "Alpha", "path": "p", "cost": 1, "pool": "resolve", "effect": "x"},
            {"name": "Beta", "path": "p", "cost": 1, "pool": "resolve", "effect": "y"},
        ]
        with patch("builtins.input", return_value="2"):
            pick = prompt_ability_choice(abilities, count=1)
        self.assertEqual(pick, "Beta")


if __name__ == "__main__":
    unittest.main()
