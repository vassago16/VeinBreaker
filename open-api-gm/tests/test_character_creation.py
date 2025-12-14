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
    # engine abilities files
    for fname in ["engine/abilities.json", "engine/resolve_abilities.json"]:
        p = ROOT / fname
        if p.exists():
            canon[p.name] = json.loads(p.read_text(encoding="utf-8"))
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
        self.assertEqual(len(char["abilities"]), len({a["name"] for a in abilities if a.get("path") == "core" and a.get("tier") == 0}) + len({a["name"] for a in canon["resolve_abilities.json"]["abilities"] if a.get("core")}) + 2)
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


if __name__ == "__main__":
    unittest.main()
