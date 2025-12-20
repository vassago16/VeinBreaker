import sys
from pathlib import Path
import unittest
from unittest.mock import patch

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
        self.system_lines = []

    def system(self, text):
        self.system_lines.append(str(text))

    def narration(self, *_args, **_kwargs):
        pass


def _stub_resolve_action_step(state, _character, ability, **_kwargs):
    state["pending_action"] = {"ability_obj": ability, "to_hit": 0, "tags": [], "log": {}}
    return state["pending_action"]


def _stub_apply_action_effects(state, _character, _enemies, **_kwargs):
    pending = state.get("pending_action") or {}
    state.setdefault("log", []).append({
        "action_effects": {
            "ability_name": (pending.get("ability_obj") or {}).get("name"),
            "to_hit": pending.get("to_hit"),
            "hit": pending.get("resolved_hit"),
        }
    })
    state["pending_action"] = None
    return "action_applied"


class TestChainTempoRules(unittest.TestCase):
    def test_link_3_hit_grants_plus_1_rp(self):
        engine = ChainResolutionEngine(
            roll_fn=lambda _dice: 0,
            resolve_action_step_fn=_stub_resolve_action_step,
            apply_action_effects_fn=_stub_apply_action_effects,
            interrupt_policy=_NoopPolicy(),
        )
        ui = _UI()

        state = {"flags": {"narration_enabled": False}, "log": [], "rules": {}}
        aggressor = {
            "_combat_key": "player",
            "name": "Hero",
            "tier": 1,
            "resources": {"resolve": 0, "resolve_cap": 7, "balance": 0, "heat": 0, "momentum": 0},
            "temp_bonuses": {},
            "abilities": [
                {"id": "a1", "name": "A1", "type": "attack"},
                {"id": "a2", "name": "A2", "type": "attack"},
                {"id": "a3", "name": "A3", "type": "attack"},
            ],
        }
        defender = {"name": "Enemy", "dv_base": 5, "hp": {"current": 99, "max": 99}, "temp_bonuses": {}}

        # 2d10 roll is used for the whole chain (normal mode): 10+10 = 20
        with patch("random.randint", side_effect=[10, 10]):
            engine.resolve_chain(
                state=state,
                ui=ui,
                aggressor=aggressor,
                defender=defender,
                chain_ability_names=["A1", "A2", "A3"],
                defender_group=[defender],
            )

        self.assertEqual(aggressor["resources"]["resolve"], 1)
        self.assertIn("Tempo reward: +1 RP (link 3 hit).", ui.system_lines)

    def test_rerolls_attack_after_miss(self):
        engine = ChainResolutionEngine(
            roll_fn=lambda _dice: 0,
            resolve_action_step_fn=_stub_resolve_action_step,
            apply_action_effects_fn=_stub_apply_action_effects,
            interrupt_policy=_NoopPolicy(),
        )
        ui = _UI()

        state = {"flags": {"narration_enabled": False}, "log": [], "rules": {}}
        aggressor = {
            "_combat_key": "player",
            "name": "Hero",
            "tier": 1,
            "resources": {"resolve": 0, "resolve_cap": 7, "balance": 0, "heat": 0, "momentum": 0},
            "temp_bonuses": {},
            "abilities": [
                {"id": "a1", "name": "A1", "type": "attack"},
                {"id": "a2", "name": "A2", "type": "attack"},
            ],
        }
        defender = {"name": "Enemy", "dv_base": 15, "hp": {"current": 99, "max": 99}, "temp_bonuses": {}}

        # First chain roll: 1+1=2 (miss); next link rerolls: 10+10=20 (hit).
        with patch("random.randint", side_effect=[1, 1, 10, 10]):
            engine.resolve_chain(
                state=state,
                ui=ui,
                aggressor=aggressor,
                defender=defender,
                chain_ability_names=["A1", "A2"],
                defender_group=[defender],
            )

        action_logs = [e.get("action_effects") for e in state.get("log", []) if isinstance(e, dict) and "action_effects" in e]
        self.assertEqual(action_logs[0]["to_hit"], 2)
        self.assertFalse(action_logs[0]["hit"])
        self.assertEqual(action_logs[1]["to_hit"], 20)
        self.assertTrue(action_logs[1]["hit"])


if __name__ == "__main__":
    unittest.main()
