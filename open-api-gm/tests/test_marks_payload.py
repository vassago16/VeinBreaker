import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.events import build_character_update  # noqa: E402


class TestMarksPayload(unittest.TestCase):
    def test_character_update_includes_marks(self):
        ch = {
            "name": "Test",
            "resources": {"hp": 10, "hp_max": 10, "resolve": 2, "resolve_cap": 5, "veinscore": 0},
            "marks": {"blood": 2, "duns": 1},
            "abilities": [],
        }
        payload = build_character_update(ch)
        self.assertEqual(payload.get("type"), "character_update")
        self.assertEqual(payload.get("character", {}).get("marks", {}).get("blood"), 2)


if __name__ == "__main__":
    unittest.main()

