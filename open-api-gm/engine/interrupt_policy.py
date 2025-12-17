from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

from engine.interrupt_windows import InterruptContext, window_allows_interrupt


class UIProtocol(Protocol):
    def choice(self, prompt: str, options: list[str]) -> Any: ...
    def emit(self, event: Dict[str, Any]) -> Any: ...
    def system(self, text: str) -> Any: ...


@dataclass
class InterruptDecision:
    kind: str                  # "no_interrupt" | "attempt" | "awaiting"
    window: Optional[Dict[str, Any]] = None


class InterruptPolicy(Protocol):
    def decide(self, when: str, ctx: InterruptContext, state: Optional[Dict[str, Any]] = None, ui: Optional[UIProtocol] = None) -> InterruptDecision: ...


class EnemyWindowPolicy:
    """
    Uses defender's interrupt windows (data-driven).
    Defender is the one attempting an interrupt (the target of the chain).
    """

    def __init__(self, rng):
        self.rng = rng

    def decide(self, when: str, ctx: InterruptContext, state: Optional[Dict[str, Any]] = None, ui: Optional[UIProtocol] = None) -> InterruptDecision:
        windows = ctx.defender.get("interrupt_windows") or ctx.defender.get("ai", {}).get("interrupt_windows") or []
        w = window_allows_interrupt(windows, when, ctx)
        if not w:
            return InterruptDecision("no_interrupt")

        chance = float(w.get("chance", 0.0))
        roll = self.rng.random()
        return InterruptDecision("attempt" if roll < chance else "no_interrupt", window=w)


class PlayerPromptPolicy:
    """
    Non-blocking interrupt policy.
    Emits awaiting state and pauses chain resolution.
    """

    def decide(self, when: str, ctx, state, ui) -> InterruptDecision:
        windows = state.get("player_interrupt_rules", {}).get("interrupt_windows", [])
        window = window_allows_interrupt(windows, when, ctx)
        if not window:
            return InterruptDecision("no_interrupt")

        rp = ctx.defender.get("resources", {}).get("rp", 0)
        cost = int(window.get("rp_cost", 1))
        if rp < cost:
            return InterruptDecision("no_interrupt")

        state["awaiting"] = {
            "type": "interrupt",
            "chain": {
                "aggressor": ctx.aggressor.get("name"),
                "defender": ctx.defender.get("name"),
                "chain_index": ctx.chain_index,
                "ability": ctx.link.get("name"),
            },
            "options": [
                { "id": "interrupt_no", "label": "Do not interrupt" },
                { "id": "interrupt_yes", "label": f"Interrupt (Spend {cost} RP)" },
            ],
            "resume": {
                "engine": "chain",
                "payload": {
                    "decision_map": {
                        "interrupt_no": False,
                        "interrupt_yes": True,
                    }
                }
            }
        }

        ui.emit({"type": "awaiting_interrupt", "data": state["awaiting"]})
        return InterruptDecision("awaiting", window)
