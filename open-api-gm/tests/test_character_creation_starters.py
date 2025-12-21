import sys
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import play  # noqa: E402


def load_game_data():
    abilities = json.loads((ROOT / "game-data" / "abilities.json").read_text(encoding="utf-8"))
    resolve = json.loads((ROOT / "game-data" / "resolve_abilities.json").read_text(encoding="utf-8"))
    return {"abilities": abilities, "resolve_abilities": resolve}


class TestCharacterCreationStarters(unittest.TestCase):
    def test_requires_resolve_ability(self):
        gd = load_game_data()
        ch = play._create_draft_character(path_id="stonepulse")
        ch["abilities"] = play._starter_ability_ids_for_path("stonepulse", gd)
        err = play._character_create_validate_starter_picks(ch, gd)
        self.assertIn("resolve", (err or "").lower())

    def test_requires_exactly_three_picks(self):
        gd = load_game_data()
        ch = play._create_draft_character(path_id="stonepulse")
        ch["abilities"] = play._starter_ability_ids_for_path("stonepulse", gd) + ["resolve_basic.disengage"]
        err = play._character_create_validate_starter_picks(ch, gd)
        self.assertIn("exactly 3", (err or "").lower())

    def test_allows_three_any_paths(self):
        gd = load_game_data()
        ch = play._create_draft_character(path_id="stonepulse")
        ch["abilities"] = (
            play._starter_ability_ids_for_path("stonepulse", gd)
            + ["resolve_basic.disengage"]
            + [
                "hemocratic.cutpoint_slice",
                "spellforged.charge_bolt",
                "canticle.gleam_strike",
            ]
        )
        err = play._character_create_validate_starter_picks(ch, gd)
        self.assertIsNone(err)

    def test_allows_three_with_one_from_path(self):
        gd = load_game_data()
        ch = play._create_draft_character(path_id="stonepulse")
        ch["abilities"] = (
            play._starter_ability_ids_for_path("stonepulse", gd)
            + ["resolve_basic.disengage"]
            + [
                "stonepulse.pulse_strike",
                "hemocratic.cutpoint_slice",
                "spellforged.charge_bolt",
            ]
        )
        err = play._character_create_validate_starter_picks(ch, gd)
        self.assertIsNone(err)


if __name__ == "__main__":
    unittest.main()
