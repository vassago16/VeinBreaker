import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import play  # noqa: E402


class _Session:
    def __init__(self):
        self.events = []

    def emit(self, payload):
        self.events.append(payload)


class _Provider:
    def __init__(self, session):
        self.session = session


class _UI:
    is_blocking = False

    def __init__(self, session):
        self.provider = _Provider(session)

    def system(self, text, data=None):
        return None

    def choice(self, prompt, options, data=None):
        return 0


def _lurker_enemy():
    return {
        "_combat_key": "enemy",
        "name": "Brumklin Lurker",
        "tier": 1,
        "rp_pool": 2,
        "hp": {"current": 3, "max": 3},
        "stat_block": {
            "hp": {"max": 3},
            "defense": {"dv_base": 6, "idf": 0},
            "damage_profile": {"baseline": {"dice": "1d4", "flat": 0}},
        },
        "moves": [
            {
                "id": "move.hamstring_cut",
                "name": "Hamstring Cut",
                "type": "attack",
                "cost": {"rp": 1},
                "to_hit": {"av_mod": 0},
                "on_hit": {"damage": "baseline", "effects": ["bleed"]},
            },
            {
                "id": "move.brutal_shove",
                "name": "Brutal Shove",
                "type": "attack",
                "cost": {"rp": 1},
                "to_hit": {"av_mod": 0},
                "interrupt_window": {"when": "before_link", "if_prev_link_missed": True},
                "on_hit": {"damage": "baseline", "effects": ["stagger"]},
            },
        ],
    }


def _player(dv_base: int):
    return {
        "_combat_key": "player",
        "name": "Hero",
        "tier": 1,
        "dv_base": dv_base,
        "abilities": [],
        "attributes": {"AGI": 10, "POW": 8},
        "resources": {"hp": 10, "resolve": 3, "momentum": 0, "balance": 0, "heat": 0},
        "marks": {"blood": 0},
        "chain": {"abilities": [], "declared": False},
    }


class TestBrumklinLurkerLinkInterrupt(unittest.TestCase):
    def test_interrupt_window_opens_only_after_miss(self):
        session = _Session()
        ui = _UI(session)
        state = {
            "seed": 1,
            "phase": {"current": "enemy_turn", "round": 1},
            "party": {"members": [_player(dv_base=999)]},
            "enemies": [_lurker_enemy()],
            "log": [],
        }
        ctx = {"state": state, "ui": ui}

        play.handle_enemy_turn(ctx, {})

        self.assertEqual(state.get("awaiting", {}).get("type"), "chain_interrupt")
        types = [e.get("type") for e in session.events if isinstance(e, dict)]
        self.assertIn("interrupt_window", types)

    def test_no_interrupt_window_when_first_link_hits(self):
        session = _Session()
        ui = _UI(session)
        state = {
            "seed": 1,
            "phase": {"current": "enemy_turn", "round": 1},
            "party": {"members": [_player(dv_base=0)]},
            "enemies": [_lurker_enemy()],
            "log": [],
        }
        ctx = {"state": state, "ui": ui}

        play.handle_enemy_turn(ctx, {})

        self.assertNotEqual(state.get("awaiting", {}).get("type"), "chain_interrupt")


if __name__ == "__main__":
    unittest.main()

