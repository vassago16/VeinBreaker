import sys
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.character import create_character  # noqa: E402


def load_canon():
    canon_dir = ROOT / "canon"
    canon = {}
    for f in canon_dir.glob("*.json"):
        canon[f.name] = json.loads(f.read_text(encoding="utf-8"))
    # abilities live in game-data (single source of truth)
    for fname in ["game-data/abilities.json", "game-data/resolve_abilities.json"]:
        p = ROOT / fname
        if p.exists():
            canon[p.name.split("/", 1)[-1]] = json.loads(p.read_text(encoding="utf-8"))
    return canon


class TestCharacterCreation(unittest.TestCase):
    def test_create_character_valid(self):
        canon = load_canon()
        # pick two legal tier-1 abilities from different paths if possible
        abilities = canon["abilities.json"]["abilities"]
        tier1 = [a for a in abilities if a.get("tier") == 1 and a.get("path") not in {"core", "resolve_basic"}]
        picks = [tier1[0]["name"], tier1[1]["name"]] if len(tier1) > 1 else [tier1[0]["name"], tier1[0]["name"]]
        char = create_character(
            canon,
            path=tier1[0]["path"],
            tier_one_choices=picks,
            tier=1,
            resolve_basic_choice=None,
            attributes={"POW": 10, "AGI": 10, "MND": 10, "SPR": 10},
            veinscore=5,
        )
        self.assertEqual(char["path"], tier1[0]["path"])
        self.assertEqual(len(char["abilities"]), len({a["name"] for a in abilities if a.get("path") == "core" and a.get("tier") == 0}) + 2)
        self.assertEqual(char["resources"]["hp"], 20)  # 10 + POW(10)
        self.assertEqual(char["veinscore"], 5)

    def test_invalid_path_raises(self):
        canon = load_canon()
        with self.assertRaises(ValueError):
            create_character(
                canon,
                path="invalid",
                tier_one_choices=["Basic Strike", "Pulse Strike"],
            )

    def test_single_resolve_choice_included_once(self):
        canon = load_canon()
        resolve_list = canon["resolve_abilities.json"]["abilities"]
        # pick the first non-core resolve if present, else first core
        non_core = [a for a in resolve_list if not a.get("core")]
        choice = (non_core[0]["name"] if non_core else resolve_list[0]["name"])
        abilities = canon["abilities.json"]["abilities"]
        tier1 = [a for a in abilities if a.get("tier") == 1 and a.get("path") not in {"core", "resolve_basic"}]
        picks = [tier1[0]["name"], tier1[1]["name"]] if len(tier1) > 1 else [tier1[0]["name"], tier1[0]["name"]]
        char = create_character(
            canon,
            path=tier1[0]["path"],
            tier_one_choices=picks,
            tier=1,
            resolve_basic_choice=choice,
            attributes={"POW": 10, "AGI": 10, "MND": 10, "SPR": 10},
            veinscore=0,
        )
        names = [a["name"] for a in char["abilities"]]
        self.assertEqual(names.count(choice), 1)

    def test_abilities_include_cooldown_fields(self):
        canon = load_canon()
        abilities = canon["abilities.json"]["abilities"]
        tier1 = [a for a in abilities if a.get("tier") == 1 and a.get("path") not in {"core", "resolve_basic"}]
        picks = [tier1[0]["name"], tier1[1]["name"]] if len(tier1) > 1 else [tier1[0]["name"], tier1[0]["name"]]
        char = create_character(
            canon,
            path=tier1[0]["path"],
            tier_one_choices=picks,
            tier=1,
            resolve_basic_choice=None,
            attributes={"POW": 10, "AGI": 10, "MND": 10, "SPR": 10},
            veinscore=0,
        )
        for ability in char["abilities"]:
            self.assertIn("cooldown", ability)
            self.assertIn("base_cooldown", ability)

    def test_only_chosen_and_core_abilities_present(self):
        canon = load_canon()
        abilities = canon["abilities.json"]["abilities"]
        tier1 = [a for a in abilities if a.get("tier") == 1 and a.get("path") not in {"core", "resolve_basic"}]
        picks = [tier1[0]["name"], tier1[1]["name"]] if len(tier1) > 1 else [tier1[0]["name"], tier1[0]["name"]]
        core_names = {a["name"] for a in abilities if a.get("path") == "core" and a.get("tier") == 0}
        expected = core_names | set(picks)
        char = create_character(
            canon,
            path=tier1[0]["path"],
            tier_one_choices=picks,
            tier=1,
            resolve_basic_choice=None,
            attributes={"POW": 10, "AGI": 10, "MND": 10, "SPR": 10},
            veinscore=0,
        )
        ability_names = {a["name"] for a in char["abilities"]}
        self.assertEqual(ability_names, expected)


if __name__ == "__main__":
    unittest.main()
