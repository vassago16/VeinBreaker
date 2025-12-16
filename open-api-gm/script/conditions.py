from typing import Dict, Any, Callable


ConditionFn = Callable[[Dict[str, Any], Dict[str, Any]], bool]


class ConditionRegistry:
    """
    Central registry for all script / scene conditions.
    Conditions must be:
      - pure (no side effects)
      - deterministic
      - fast
    """

    def __init__(self):
        self._conditions: Dict[str, ConditionFn] = {}

        # register built-ins
        self.register("always", self._always)
        self.register("player_no_damage", self._player_no_damage)
        self.register("player_hp_above", self._player_hp_above)
        self.register("all_enemies_defeated", self._all_enemies_defeated)
        self.register("chain_length_at_least", self._chain_length_at_least)
        self.register("interrupts_taken_below", self._interrupts_taken_below)
        self.register("used_ability", self._used_ability)
        self.register("scene_flag_set", self._scene_flag_set)
        self.register("metric_at_least", self._metric_at_least)

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def register(self, name: str, fn: ConditionFn):
        if name in self._conditions:
            raise ValueError(f"Condition already registered: {name}")
        self._conditions[name] = fn

    def evaluate(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        condition = { "type": "...", ... }
        context = runtime context from ScriptController
        """
        ctype = condition.get("type")
        if not ctype:
            raise ValueError("Condition missing 'type'")

        if ctype not in self._conditions:
            raise KeyError(f"Unknown condition type: {ctype}")

        return self._conditions[ctype](condition, context)

    # ──────────────────────────────────────────────
    # Built-in Conditions
    # ──────────────────────────────────────────────

    def _always(self, cond, ctx) -> bool:
        return True

    def _player_no_damage(self, cond, ctx) -> bool:
        """
        True if no player took damage during this scene.
        Requires engine to increment 'damage_taken' metric.
        """
        return ctx["scene_metrics"].get("damage_taken", 0) == 0

    def _player_hp_above(self, cond, ctx) -> bool:
        """
        cond: { "type": "player_hp_above", "value": 5 }
        """
        threshold = cond.get("value", 0)
        hp = ctx.get("player", {}).get("hp", 0)
        return hp > threshold

    def _all_enemies_defeated(self, cond, ctx) -> bool:
        """
        Requires engine to set scene flag when encounter clears.
        """
        return ctx["scene_flags"].get("all_enemies_defeated", False)

    def _chain_length_at_least(self, cond, ctx) -> bool:
        """
        cond: { "type": "chain_length_at_least", "value": 3 }
        """
        required = cond.get("value", 0)
        max_chain = ctx.get("combat", {}).get("max_chain_declared", 0)
        return max_chain >= required

    def _interrupts_taken_below(self, cond, ctx) -> bool:
        """
        cond: { "type": "interrupts_taken_below", "value": 2 }
        """
        limit = cond.get("value", 0)
        interrupts = ctx["scene_metrics"].get("interrupts_taken", 0)
        return interrupts < limit

    def _used_ability(self, cond, ctx) -> bool:
        """
        cond: { "type": "used_ability", "ability_id": "ability.pulse_strike" }
        """
        ability_id = cond.get("ability_id")
        if not ability_id:
            return False

        used = ctx.get("combat", {}).get("abilities_used", [])
        return ability_id in used

    def _scene_flag_set(self, cond, ctx) -> bool:
        """
        cond: { "type": "scene_flag_set", "flag": "door_opened" }
        """
        flag = cond.get("flag")
        if not flag:
            return False
        return ctx["scene_flags"].get(flag, False)

    def _metric_at_least(self, cond, ctx) -> bool:
        """
        Generic metric gate.
        cond: { "type": "metric_at_least", "metric": "chains_declared", "value": 2 }
        """
        metric = cond.get("metric")
        value = cond.get("value", 0)
        if not metric:
            return False
        return ctx["scene_metrics"].get(metric, 0) >= value
