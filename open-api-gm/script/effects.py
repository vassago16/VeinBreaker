from typing import Dict, Any, Callable


EffectFn = Callable[[Dict[str, Any], Dict[str, Any], Dict[str, Any]], None]


class EffectRegistry:
    """
    Executes effects emitted by ScriptController.

    Effects are commands, not logic.
    They may:
      - emit UI events
      - modify script/controller state
      - call into game systems (loot, achievements, clocks)
    """

    def __init__(self):
        self._effects: Dict[str, EffectFn] = {}

        # register built-ins
        self.register("narration_prompt", self._narration_prompt)
        self.register("award_loot", self._award_loot)
        self.register("award_achievement", self._award_achievement)
        self.register("advance_hunter_clock", self._advance_hunter_clock)
        self.register("set_scene_flag", self._set_scene_flag)
        self.register("increment_metric", self._increment_metric)
        self.register("emit_ui_event", self._emit_ui_event)

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def register(self, name: str, fn: EffectFn):
        if name in self._effects:
            raise ValueError(f"Effect already registered: {name}")
        self._effects[name] = fn

    def execute(self, effect: Dict[str, Any], context: Dict[str, Any], payload: Dict[str, Any]):
        """
        effect = { "type": "...", ... }
        context = ScriptController runtime context
        payload = engine event payload (optional)
        """
        etype = effect.get("type")
        if not etype:
            raise ValueError("Effect missing 'type'")

        if etype not in self._effects:
            raise KeyError(f"Unknown effect type: {etype}")

        self._effects[etype](effect, context, payload)

    # ──────────────────────────────────────────────
    # Built-in Effects (Veinbreaker-specific)
    # ──────────────────────────────────────────────

    def _narration_prompt(self, effect, ctx, payload):
        """
        effect:
          { "type": "narration_prompt", "id": "narration.clean_victory" }
        """
        prompt_id = effect.get("id")
        if not prompt_id:
            return

        ui = ctx.get("ui")
        if ui:
            ui.emit({
                "type": "narration",
                "prompt_id": prompt_id,
                "scene": ctx.get("scene_id"),
            })

    def _award_loot(self, effect, ctx, payload):
        """
        effect:
          { "type": "award_loot", "loot_id": "loot.vein_fragment.t1" }
        """
        loot_id = effect.get("loot_id")
        if not loot_id:
            return

        game = ctx.get("game")
        if game:
            game.award_loot(loot_id)

        ui = ctx.get("ui")
        if ui:
            ui.emit({
                "type": "loot",
                "loot_id": loot_id
            })

    def _award_achievement(self, effect, ctx, payload):
        """
        effect:
          { "type": "award_achievement", "id": "ach.flawless.vein" }
        """
        ach_id = effect.get("id")
        if not ach_id:
            return

        game = ctx.get("game")
        if game:
            game.award_achievement(ach_id)

        ui = ctx.get("ui")
        if ui:
            ui.emit({
                "type": "system",
                "text": f"Achievement unlocked: {ach_id}"
            })

    def _advance_hunter_clock(self, effect, ctx, payload):
        """
        effect:
          { "type": "advance_hunter_clock", "amount": 1 }
        """
        amount = effect.get("amount", 1)

        game = ctx.get("game")
        if game:
            game.advance_hunter_clock(amount)

        ui = ctx.get("ui")
        if ui:
            ui.emit({
                "type": "system",
                "text": "The Hunter draws closer."
            })

    def _set_scene_flag(self, effect, ctx, payload):
        """
        effect:
          { "type": "set_scene_flag", "flag": "alarm_triggered" }
        """
        flag = effect.get("flag")
        if not flag:
            return

        controller = ctx.get("controller")
        if controller:
            controller.set_scene_flag(flag, True)

    def _increment_metric(self, effect, ctx, payload):
        """
        effect:
          { "type": "increment_metric", "metric": "chains_declared", "amount": 1 }
        """
        metric = effect.get("metric")
        amount = effect.get("amount", 1)
        if not metric:
            return

        metrics = ctx.get("scene_metrics")
        if metrics is not None:
            metrics[metric] = metrics.get(metric, 0) + amount

    def _emit_ui_event(self, effect, ctx, payload):
        """
        Generic UI passthrough for scripted beats.

        effect:
          {
            "type": "emit_ui_event",
            "event": {
              "type": "interrupt",
              "text": "The vein shudders violently."
            }
          }
        """
        event = effect.get("event")
        if not event:
            return

        ui = ctx.get("ui")
        if ui:
            ui.emit(event)
