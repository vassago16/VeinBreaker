import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import play  # noqa: E402
from ui.web_provider import WebProvider  # noqa: E402


class _Session:
    def __init__(self):
        self.events = []

    def emit(self, payload):
        self.events.append(payload)


def _load_enemy(enemy_id: str) -> dict:
    data = json.loads((ROOT / "game-data" / "monsters" / "bestiary.json").read_text(encoding="utf-8"))
    enemy = next(e for e in data.get("enemies", []) if isinstance(e, dict) and e.get("id") == enemy_id)
    # Prime minimal runtime fields.
    enemy = dict(enemy)
    enemy["_combat_key"] = "enemy"
    enemy.setdefault("hp", {"current": 999, "max": 999})
    enemy.setdefault("rp", enemy.get("rp_pool", 5))
    return enemy


def _player() -> dict:
    return {
        "_combat_key": "player",
        "name": "Hero",
        "tier": 1,
        "dv_base": 999,  # ensure enemy misses so we don't die mid-test
        "abilities": [],
        "attributes": {"AGI": 10, "POW": 8},
        "resources": {"hp": 50, "hp_max": 50, "resolve": 3, "resolve_cap": 5, "momentum": 0, "balance": 0, "heat": 0},
        "marks": {"blood": 0},
        "chain": {"abilities": [], "declared": False},
    }


class TestCarrionDancerInterruptOnlyOnTelegraph(unittest.TestCase):
    def test_only_prompts_on_last_link_telegraph(self):
        session = _Session()
        ui = WebProvider(session)

        state = {
            "seed": 1,
            "flags": {"narration_enabled": False},
            "phase": {"current": "enemy_turn", "round": 1},
            "party": {"members": [_player()]},
            "enemies": [_load_enemy("enemy.vein.carrion_dancer")],
            "log": [],
        }
        ctx = {"state": state, "ui": ui, "game_data": {}}

        play.handle_enemy_turn(ctx, {})

        # We should be awaiting a chain interrupt window at the telegraphed finisher (link 5),
        # meaning we already resolved links 1-4 without prompting.
        self.assertEqual(state.get("awaiting", {}).get("type"), "chain_interrupt")
        self.assertEqual(int(state.get("phase", {}).get("chain_resume_idx", -1)), 4)


if __name__ == "__main__":
    unittest.main()

