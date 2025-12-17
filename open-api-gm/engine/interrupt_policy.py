from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

from engine.interrupt_windows import InterruptContext, window_allows_interrupt
from engine.combat_state import combat_get


class UIProtocol(Protocol):
    def choice(self, prompt: str, options: list[str]) -> Any: ...
    def emit(self, event: Dict[str, Any]) -> Any: ...
    def system(self, text: str) -> Any: ...


@dataclass
class InterruptDecision:
    kind: str                  # "no_interrupt" | "attempt" | "awaiting"
    window: Optional[Dict[str, Any]] = None


class InterruptPolicy(Protocol):
    def decide(
        self,
        when: str,
        ctx: InterruptContext,
        state: Optional[Dict[str, Any]] = None,
        ui: Optional[UIProtocol] = None,
    ) -> InterruptDecision: ...


def _last_action_missed(state: Dict[str, Any]) -> bool:
    for entry in reversed(state.get("log", [])):
        if isinstance(entry, dict) and "action_effects" in entry and isinstance(entry["action_effects"], dict):
            hit = entry["action_effects"].get("hit")
            if hit is False:
                return True
            if hit is True:
                return False
    return False


def _default_window_open(when: str, ctx: InterruptContext, state: Dict[str, Any]) -> bool:
    """
    Default rule when no data-driven policy exists:
    - if last action was a miss, a window is open
    - if chain is at/after the 2nd link (index>=1), a window is open
    """
    if _last_action_missed(state):
        return True
    return ctx.chain_index >= 1


def _legacy_window_allows_interrupt(w: Dict[str, Any], when: str, ctx: InterruptContext, state: Dict[str, Any]) -> bool:
    """
    Support older interrupt window format used in enemy archetype JSON:
      {
        "after_action_index": [2,3],
        "trigger_if": {...},
        "weight": 0.7
      }
    This is treated as an AFTER_LINK window keyed by action number (1-based).
    """
    if when != "after_link":
        return False

    after_idxs = w.get("after_action_index") or []
    action_number = ctx.chain_index + 1
    if after_idxs and action_number not in after_idxs:
        return False

    trigger = w.get("trigger_if", {}) or {}
    if not isinstance(trigger, dict):
        return False

    # Evaluate supported triggers against current state/ctx
    for key, val in trigger.items():
        if key == "player_missed_last_action":
            if _last_action_missed(state) != bool(val):
                return False
        elif key == "chain_length_gte":
            if ctx.chain_length < int(val):
                return False
        elif key == "player_heat_gte":
            heat = int(combat_get(state, ctx.aggressor, "heat", int((ctx.aggressor.get("resources") or {}).get("heat", 0))))
            if heat < int(val):
                return False
        elif key == "blood_mark_gte":
            blood = int(((ctx.aggressor.get("marks") or {}).get("blood", 0)))
            if blood < int(val):
                return False
        else:
            # Unknown trigger -> treat as unmet (fail closed)
            return False

    return True


class EnemyWindowPolicy:
    """
    Uses defender's interrupt windows (data-driven).
    Defender is the one attempting an interrupt (the target of the chain).
    """

    def __init__(self, rng):
        self.rng = rng

    def decide(self, when: str, ctx: InterruptContext, state: Optional[Dict[str, Any]] = None, ui: Optional[UIProtocol] = None) -> InterruptDecision:
        defender = ctx.defender or {}
        resolved = defender.get("resolved_archetype", {}) or {}
        windows = (
            (resolved.get("rhythm_profile", {}) or {}).get("interrupt", {}) or {}
        ).get("windows") or defender.get("interrupt_windows") or defender.get("ai", {}).get("interrupt_windows") or []

        w = None
        if windows:
            # New schema: {"when":"before_link|after_link","if":{...},"chance":...}
            if any(isinstance(x, dict) and "when" in x for x in windows):
                w = window_allows_interrupt(windows, when, ctx)
                if w:
                    chance = float(w.get("chance", 0.0))
                    roll = self.rng.random()
                    return InterruptDecision("attempt" if roll < chance else "no_interrupt", window=w)
            else:
                # Legacy schema: {"after_action_index":[...],"trigger_if":{...},"weight":...}
                if state:
                    for cand in windows:
                        if not isinstance(cand, dict):
                            continue
                        if _legacy_window_allows_interrupt(cand, when, ctx, state):
                            weight = float(cand.get("weight", 1.0))
                            roll = self.rng.random()
                            return InterruptDecision("attempt" if roll < weight else "no_interrupt", window=cand)

        if state and _default_window_open(when, ctx, state):
            return InterruptDecision("attempt", window={"source": "default"})

        return InterruptDecision("no_interrupt")


class PlayerPromptPolicy:
    """
    Non-blocking interrupt policy.
    Emits awaiting state and pauses chain resolution.
    """

    def decide(self, when: str, ctx: InterruptContext, state, ui) -> InterruptDecision:
        rules = state.get("player_interrupt_rules", {}) if isinstance(state, dict) else {}
        windows = rules.get("interrupt_windows", []) or []
        window = window_allows_interrupt(windows, when, ctx)

        if not window and isinstance(state, dict) and _default_window_open(when, ctx, state):
            window = {"source": "default", "rp_cost": 1}

        if not window:
            return InterruptDecision("no_interrupt")

        # If the UI already provided a decision, consume it.
        if isinstance(state, dict) and "pending_chain_interrupt" in state:
            attempt = bool(state.pop("pending_chain_interrupt"))
            return InterruptDecision("attempt" if attempt else "no_interrupt", window=window)

        # Blocking UIs can decide immediately.
        if getattr(ui, "is_blocking", True):
            idx = ui.choice("Interrupt?", ["No", "Interrupt"])
            attempt = (idx == 1)
            return InterruptDecision("attempt" if attempt else "no_interrupt", window=window)

        # Non-blocking: emit interrupt_window (ability cards) and wait for /step action.
        from ui.events import emit_event

        defender = ctx.defender if isinstance(ctx.defender, dict) else {}
        abilities = defender.get("abilities", []) if isinstance(defender.get("abilities"), list) else []
        usable_defense = []
        for ab in abilities:
            if not isinstance(ab, dict):
                continue
            if int(ab.get("cooldown", 0) or 0) != 0:
                continue
            tags = ab.get("tags", []) or []
            if "defense" not in tags and (ab.get("type") or "").lower() != "defense":
                continue
            usable_defense.append({
                "id": ab.get("id") or ab.get("name"),
                "name": ab.get("name"),
                "cost": ab.get("cost", 0),
                "effect": ab.get("effect"),
            })

        emit_event(ui, {"type": "interrupt_window", "abilities": usable_defense})
        options = [
            {"id": "interrupt_no", "label": "Do not interrupt"},
            {"id": "interrupt_yes", "label": "Interrupt"},
        ]
        state["awaiting"] = {"type": "chain_interrupt", "options": options, "abilities": usable_defense}
        return InterruptDecision("awaiting", window=window)
