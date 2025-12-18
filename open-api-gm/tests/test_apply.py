import sys
import json
import random
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.apply import pick_enemy  # noqa: E402


def load_bestiary():
    data = json.loads((ROOT / "game-data" / "bestiary.json").read_text(encoding="utf-8"))
    return data.get("enemies", [])


class TestPickEnemy(unittest.TestCase):
    def test_prefers_multi_move(self):
        bestiary = load_bestiary()
        state = {"game_data": {"bestiary": bestiary}, "party": {"members": [{"tier": 1}]}}
        multi_move = [e for e in bestiary if len(e.get("moves", [])) > 1]
        if not multi_move:
            self.skipTest("No multi-move enemies in bestiary to test")
        with patch.object(random, "choice", return_value=multi_move[0]):
            enemy = pick_enemy(state)
        self.assertEqual(enemy["id"], multi_move[0]["id"])


if __name__ == "__main__":
    unittest.main()
