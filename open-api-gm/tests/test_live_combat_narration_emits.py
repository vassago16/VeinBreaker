import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.chain_resolution_engine import ChainResolutionEngine  # noqa: E402


class _UI:
    is_blocking = False

    def __init__(self):
        self.narrations = []

    def narration(self, text, data=None):
        self.narrations.append(text)

    def system(self, *_args, **_kwargs):
        pass


class _NoopPolicy:
    def decide(self, *args, **kwargs):
        class _Decision:
            kind = "none"
        return _Decision()


class TestLiveCombatNarrationEmits(unittest.TestCase):
    def test_chain_engine_emits_narration_from_log(self):
        def roll_fn(_dice: str) -> int:
            return 2

        def resolve_action_step(state, character, ability, **_kwargs):
            state["pending_action"] = {"ability_obj": ability, "to_hit": 0, "tags": [], "log": {}}
            return state["pending_action"]

        def apply_action_effects(state, _character, _enemies, **_kwargs):
            state.setdefault("log", []).append({"narration": "DUNGEON SPEAKS."})
            state["pending_action"] = None
            return "action_applied"

        engine = ChainResolutionEngine(
            roll_fn=roll_fn,
            resolve_action_step_fn=resolve_action_step,
            apply_action_effects_fn=apply_action_effects,
            interrupt_policy=_NoopPolicy(),
        )

        ui = _UI()
        state = {"flags": {"narration_enabled": True}, "log": [], "rules": {}}
        aggressor = {"_combat_key": "player", "abilities": [{"id": "a", "name": "A", "type": "attack"}], "temp_bonuses": {}}
        defender = {"_combat_key": "enemy0", "name": "Enemy", "hp": {"current": 99, "max": 99}, "temp_bonuses": {}}

        engine.resolve_chain(
            state=state,
            ui=ui,
            aggressor=aggressor,
            defender=defender,
            chain_ability_names=["A"],
            defender_group=[defender],
        )

        self.assertTrue(ui.narrations)
        self.assertEqual(ui.narrations[-1], "DUNGEON SPEAKS.")


if __name__ == "__main__":
    unittest.main()

