import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from unittest.mock import patch

from engine.chain_resolution_engine import ChainResolutionEngine  # noqa: E402
from engine.interrupt_policy import PlayerPromptPolicy  # noqa: E402


class _UI:
    is_blocking = True

    def system(self, _text):
        return None

    def choice(self, _prompt, _options):
        return 0


def _stub_resolve_action_step(state, _character, ability, **_kwargs):
    # minimal pending_action compatible with chain engine
    state["pending_action"] = {
        "ability_obj": ability,
        "damage_roll": 5,
        "log": {},
    }
    return state["pending_action"]


def _stub_apply_action_effects(state, _character, enemies, **_kwargs):
    pending = state.get("pending_action") or {}
    enemy = enemies[0] if enemies else None
    hit = bool(pending.get("resolved_hit"))
    dmg = int(pending.get("damage_roll") or 0) if hit else 0
    if isinstance(enemy, dict) and dmg:
        hp = enemy.get("hp", {})
        if isinstance(hp, dict):
            hp["current"] = max(0, int(hp.get("current", 0) or 0) - dmg)
        else:
            enemy["hp"] = max(0, int(hp or 0) - dmg)
    state.setdefault("log", []).append({"action_effects": {"hit": hit, "damage_applied": dmg}})
    state["pending_action"] = None
    return "ok"


class TestEnemyTraitsAndAvMod(unittest.TestCase):
    def test_link_av_mod_affects_hit(self):
        ui = _UI()
        state = {"log": [], "phase": {"round": 1}}
        aggressor = {"_combat_key": "player", "resources": {"balance": 0, "heat": 0}, "temp_bonuses": {}}
        defender = {"_combat_key": "enemy", "hp": {"current": 10, "max": 10}, "dv_base": 10, "temp_bonuses": {}}

        # Would hit at 10 vs 10, but per-link av_mod -2 should make it miss.
        move = {"id": "move.test", "name": "Test Strike", "type": "attack", "to_hit": {"av_mod": -2}}
        aggressor["moves"] = [move]

        cre = ChainResolutionEngine(
            roll_fn=lambda d: 0,
            resolve_action_step_fn=_stub_resolve_action_step,
            apply_action_effects_fn=_stub_apply_action_effects,
            interrupt_policy=PlayerPromptPolicy(),
            emit_log_fn=None,
            interrupt_apply_fn=lambda *_a, **_k: (False, 0, [], False),
        )

        with patch("engine.chain_resolution_engine.roll_2d10_modified", return_value=(10, {"mode": "normal"})), patch(
            "engine.chain_resolution_engine.roll_mode_for_entity", return_value="normal"
        ):
            cre.resolve_chain(
                state=state,
                ui=ui,
                aggressor=aggressor,
                defender=defender,
                chain_ability_names=["Test Strike"],
                defender_group=[defender],
            )

        self.assertFalse(state["log"][-1]["action_effects"]["hit"])

    def test_second_hit_gate_absorbs_first_damage(self):
        ui = _UI()
        state = {"log": [], "phase": {"round": 1}}
        aggressor = {"_combat_key": "player", "resources": {"balance": 0, "heat": 0}, "temp_bonuses": {}}
        defender = {
            "_combat_key": "enemy",
            "hp": {"current": 20, "max": 20},
            "dv_base": 5,
            "traits": {"second_hit_gate": True},
            "temp_bonuses": {},
        }

        move1 = {"id": "move.hit1", "name": "Hit One", "type": "attack"}
        move2 = {"id": "move.hit2", "name": "Hit Two", "type": "attack"}
        aggressor["moves"] = [move1, move2]

        cre = ChainResolutionEngine(
            roll_fn=lambda d: 0,
            resolve_action_step_fn=_stub_resolve_action_step,
            apply_action_effects_fn=_stub_apply_action_effects,
            interrupt_policy=PlayerPromptPolicy(),
            emit_log_fn=None,
            interrupt_apply_fn=lambda *_a, **_k: (False, 0, [], False),
        )

        with patch("engine.chain_resolution_engine.roll_2d10_modified", return_value=(12, {"mode": "normal"})), patch(
            "engine.chain_resolution_engine.roll_mode_for_entity", return_value="normal"
        ):
            cre.resolve_chain(
                state=state,
                ui=ui,
                aggressor=aggressor,
                defender=defender,
                chain_ability_names=["Hit One", "Hit Two"],
                defender_group=[defender],
            )

        # First hit: absorbed (0), second hit: applies 5 damage.
        self.assertEqual(state["log"][-2]["action_effects"]["damage_applied"], 0)
        self.assertEqual(state["log"][-1]["action_effects"]["damage_applied"], 5)
        self.assertEqual(int(defender["hp"]["current"]), 15)


if __name__ == "__main__":
    unittest.main()
