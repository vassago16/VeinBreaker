import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.chain_resolution_engine import ChainResolutionEngine  # noqa: E402


class _NoopPolicy:
    def decide(self, *args, **kwargs):
        class _Decision:
            kind = "none"
        return _Decision()


class _UI:
    def __init__(self):
        self.lines = []

    def system(self, text):
        self.lines.append(str(text))


class TestPerfectParryHeal(unittest.TestCase):
    def test_perfect_parry_heals_1d6_times_tier(self):
        # Controlled roller: 2d10 interrupt=20, 1d6 heal=4, 1d4 counter=1
        def roll_fn(dice: str) -> int:
            if dice == "2d10":
                return 20
            if dice == "1d6":
                return 4
            if dice == "1d4":
                return 1
            return 0

        engine = ChainResolutionEngine(
            roll_fn=roll_fn,
            resolve_action_step_fn=lambda *a, **k: None,
            apply_action_effects_fn=lambda *a, **k: None,
            interrupt_policy=_NoopPolicy(),
            emit_log_fn=None,
        )
        ui = _UI()
        state = {"log": []}

        defender = {
            "_combat_key": "player",
            "name": "Hero",
            "tier": 2,
            "resources": {"hp": 10, "hp_max": 20, "balance": 0, "momentum": 0, "heat": 0},
            "temp_bonuses": {},
        }
        aggressor = {"_combat_key": "enemy", "name": "Enemy", "hp": {"current": 20, "max": 20}}

        broke = engine._attempt_interrupt_newrules(state, ui, aggressor, defender, attack_total=0)
        self.assertTrue(broke)
        self.assertEqual(defender["resources"]["hp"], 18)  # + (4 * tier 2)


if __name__ == "__main__":
    unittest.main()

