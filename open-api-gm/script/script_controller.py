from pathlib import Path
from typing import Any, Dict, List, Optional

from script.scene_loader import SceneLoader


class ScriptController:
    """
    Top-level campaign / narrative controller.
    Handles scene progression and dispatches effects based on engine events.
    """

    def __init__(
        self,
        script_def: Dict[str, Any],
        scene_defs: Dict[str, Dict[str, Any]],
        effect_executor,
        condition_evaluator,
        scene_loader: Optional[SceneLoader] = None,
        data_root: Optional[Path] = None,
    ):
        """
        script_def: parsed script.json
        scene_defs: dict of scene_id -> scene.json
        effect_executor: callable(effect, context, payload)
        condition_evaluator: callable(condition, context) -> bool
        scene_loader: optional SceneLoader (injected for tests); if None, one is created
        data_root: optional base path for SceneLoader when not provided
        """

        self.script = script_def
        self.scenes = scene_defs

        self.effect_executor = effect_executor
        self.condition_evaluator = condition_evaluator

        self.scene_loader = scene_loader or SceneLoader(data_root or Path("open-api-gm/game-data"))

        # progression state
        self.current_act_id: Optional[str] = None
        self.current_scene_id: Optional[str] = None

        # runtime state
        self.scene_flags: Dict[str, bool] = {}
        self.scene_metrics: Dict[str, int] = {}
        self.event_log: List[Dict[str, Any]] = []

        # injectable runtime systems
        self.ui = None
        self.game = None

        self._init_first_act()

    # ──────────────────────────────────────────────
    # Initialization
    # ──────────────────────────────────────────────

    def _init_first_act(self):
        acts = sorted(self.script["acts"], key=lambda a: a.get("order", 0))
        if not acts:
            raise ValueError("Script contains no acts")

        self.current_act_id = acts[0]["id"]
        self._enter_first_scene_of_act()

    def _enter_first_scene_of_act(self):
        act = self._get_current_act()
        if not act["scenes"]:
            raise ValueError(f"Act {act['id']} has no scenes")

        first_scene_ref = act["scenes"][0]["$ref"]
        self.enter_scene(first_scene_ref)

    # ──────────────────────────────────────────────
    # Scene Lifecycle
    # ──────────────────────────────────────────────

    def enter_scene(self, scene_id: str):
        self.current_scene_id = scene_id
        scene_def = self.scenes[scene_id]
        
        # resolve scene
        self.current_scene = self.scene_loader.load_scene(scene_def)

        # reset runtime state
        self.scene_flags = self.current_scene.get("flags", {}).copy()
        self.scene_metrics = {k: 0 for k in self.current_scene.get("metrics", [])}

        # hand encounter to game engine
        if self.game:
            self.game.load_scene(self.current_scene)

        self._fire_trigger("on_scene_start")

    def complete_scene(self):
        self._fire_trigger("on_scene_complete")
        self._advance_scene_or_act()

    def fail_scene(self):
        self._fire_trigger("on_scene_failed")
        # failure handling left to script design

    # ──────────────────────────────────────────────
    # Event Handling
    # ──────────────────────────────────────────────

    def on_engine_event(self, event_type: str, payload: Optional[Dict[str, Any]] = None):
        """
        Called by combat / exploration engine.
        Example:
            controller.on_engine_event("on_enemy_defeated", {"enemy_id": "..."})
        """

        payload = payload or {}

        self.event_log.append({
            "scene": self.current_scene_id,
            "event": event_type,
            "payload": payload,
        })

        self._update_metrics_from_event(event_type, payload)
        self._fire_trigger(event_type, payload)

    # ──────────────────────────────────────────────
    # Trigger Evaluation
    # ──────────────────────────────────────────────

    def _fire_trigger(self, trigger_type: str, payload: Optional[Dict[str, Any]] = None):
        payload = payload or {}

        scene = self._get_current_scene()
        for evt in scene.get("events", []):
            trigger = evt.get("trigger", {})
            if trigger.get("type") != trigger_type:
                continue

            if self._conditions_pass(evt.get("conditions", [])):
                self._apply_effects(evt.get("effects", []), payload)

    def _conditions_pass(self, conditions: List[Dict[str, Any]]) -> bool:
        for cond in conditions:
            if not self.condition_evaluator(cond, self._build_context()):
                return False
        return True

    # ──────────────────────────────────────────────
    # Effects
    # ──────────────────────────────────────────────

    def _apply_effects(self, effects: List[Dict[str, Any]], payload: Dict[str, Any]):
        for eff in effects:
            self.effect_executor(eff, self._build_context(), payload)

    # ──────────────────────────────────────────────
    # Progression
    # ──────────────────────────────────────────────

    def _advance_scene_or_act(self):
        act = self._get_current_act()
        scene_ids = [s["$ref"] for s in act["scenes"]]
        idx = scene_ids.index(self.current_scene_id)

        if idx + 1 < len(scene_ids):
            self.enter_scene(scene_ids[idx + 1])
        else:
            self._advance_act()

    def _advance_act(self):
        acts = sorted(self.script["acts"], key=lambda a: a.get("order", 0))
        idx = next(i for i, a in enumerate(acts) if a["id"] == self.current_act_id)

        if idx + 1 < len(acts):
            self.current_act_id = acts[idx + 1]["id"]
            self._enter_first_scene_of_act()
        else:
            # end of script
            self.current_scene_id = None

    # ──────────────────────────────────────────────
    # Metrics / Flags
    # ──────────────────────────────────────────────

    def _update_metrics_from_event(self, event_type: str, payload: Dict[str, Any]):
        if event_type in self.scene_metrics:
            self.scene_metrics[event_type] += 1

    def set_scene_flag(self, flag: str, value: bool = True):
        self.scene_flags[flag] = value

    # ──────────────────────────────────────────────
    # Context helpers
    # ──────────────────────────────────────────────

    def _build_context(self) -> Dict[str, Any]:
        return {
            "script_id": self.script["id"],
            "act_id": self.current_act_id,
            "scene_id": self.current_scene_id,
            "scene_flags": self.scene_flags,
            "scene_metrics": self.scene_metrics,
            "event_log": self.event_log,
            "ui": self.ui,
            "game": self.game,
            "controller": self,
        }

    def _get_current_act(self) -> Dict[str, Any]:
        for act in self.script["acts"]:
            if act["id"] == self.current_act_id:
                return act
        raise KeyError(f"Current act not found: {self.current_act_id}")

    def _get_current_scene(self) -> Dict[str, Any]:
        if not self.current_scene_id:
            raise RuntimeError("No active scene")
        return self.scenes[self.current_scene_id]
