import json
import sys
from pathlib import Path

# Allow running from repo root or tools/ dir
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from script.script_controller import ScriptController
from script.conditions import ConditionRegistry
from script.effects import EffectRegistry
from script.scene_loader import SceneLoader   # ✅ IMPORT


# ──────────────────────────────────────────────
# Minimal stubs (no engine, no UI)
# ──────────────────────────────────────────────

class DummyUI:
    def emit(self, event):
        print(f"[UI EVENT] {event}")


class DummyGame:
    def __init__(self):
        self.loot = []
        self.achievements = []
        self.hunter_clock = 0

    def award_loot(self, loot_id):
        self.loot.append(loot_id)
        print(f"[GAME] Loot awarded: {loot_id}")

    def award_achievement(self, ach_id):
        self.achievements.append(ach_id)
        print(f"[GAME] Achievement unlocked: {ach_id}")

    def advance_hunter_clock(self, amount):
        self.hunter_clock += amount
        print(f"[GAME] Hunter clock +{amount} → {self.hunter_clock}")

    def load_scene(self, scene):
        """
        scene is the fully resolved bundle from SceneLoader
        """
        self.current_scene = scene

        print(f"[GAME] Scene loaded: {scene['id']}")
        print(f"       Environment: {scene['environment']['id'] if scene['environment'] else 'none'}")

        enc = scene["encounter"]
        print(f"       Monsters: {[m['id'] for m in enc['monsters']]}")
        print(f"       Traps: {[t['id'] for t in enc['traps']]}")
        print(f"       Hazards: {[h['id'] for h in enc['hazards']]}")
# ──────────────────────────────────────────────
# Load helpers
# ──────────────────────────────────────────────

DATA = ROOT / "game-data"   # ✅ single source of truth

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_script_bundle():
    script = load_json(DATA / "scripts" / "script.echoes.json")

    scenes = {}
    for act in script["acts"]:
        for ref in act["scenes"]:
            sid = ref["$ref"]
            scenes[sid] = load_json(DATA / "scenes" / f"{sid}.json")

    return script, scenes


# ──────────────────────────────────────────────
# One-command test
# ──────────────────────────────────────────────

def main():
    print("=== VEINBREAKER SCRIPT TEST RUN ===\n")

    script_def, scene_defs = load_script_bundle()

    ui = DummyUI()
    game = DummyGame()

    conditions = ConditionRegistry()
    effects = EffectRegistry()

    # ✅ SceneLoader created with SAME root as script loader
    scene_loader = SceneLoader(DATA)

    # ✅ SceneLoader passed into ScriptController
    controller = ScriptController(
        script_def=script_def,
        scene_defs=scene_defs,
        scene_loader=scene_loader,              # ← THIS IS THE SLOT
        effect_executor=effects.execute,
        condition_evaluator=conditions.evaluate,
    )

    # inject runtime systems
    controller.ui = ui
    controller.game = game

    print(f"Entered scene: {controller.current_scene_id}\n")

    # ──────────────────────────────────────────
    # Simulated combat events
    # ──────────────────────────────────────────

    print("→ Simulating chain declaration")
    controller.scene_metrics["chains_declared"] = 1
    controller.on_engine_event(
        "on_chain_declared",
        {"chain_length": 2}
    )

    print("\n→ Simulating enemy defeat")
    controller.set_scene_flag("all_enemies_defeated", True)
    controller.on_engine_event(
        "on_enemy_defeated",
        {"enemy_id": "enemy.veinbound_stalker"}
    )

    print("\n→ Completing scene")
    controller.complete_scene()

    print("\n=== RUN SUMMARY ===")
    print(f"Loot: {game.loot}")
    print(f"Achievements: {game.achievements}")
    print(f"Hunter Clock: {game.hunter_clock}")
    print(f"Current Scene: {controller.current_scene_id}")
    print("\n=== TEST COMPLETE ===")


if __name__ == "__main__":
    main()
