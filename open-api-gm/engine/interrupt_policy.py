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
    attempt: bool
    reason: str = ""
    window: Optional[Dict[str, Any]] = None


class InterruptPolicy(Protocol):
    def decide(self, when: str, ctx: InterruptContext) -> InterruptDecision: ...


class EnemyWindowPolicy:
    """
    Uses defender's interrupt windows (data-driven).
    Defender is the one attempting an interrupt (the target of the chain).
    """

    def __init__(self, rng):
        self.rng = rng

    def decide(self, when: str, ctx: InterruptContext) -> InterruptDecision:
        windows = ctx.defender.get("interrupt_windows") or ctx.defender.get("ai", {}).get("interrupt_windows") or []
        w = window_allows_interrupt(windows, when, ctx)
        if not w:
            return InterruptDecision(False, "no_matching_window")

        chance = float(w.get("chance", 0.0))
        roll = self.rng.random()
        return InterruptDecision(roll < chance, f"chance={chance:.2f},roll={roll:.2f}", window=w)


class PlayerPromptPolicy:
    """
    Prompts the player IF a window is open.
    The window rules live in a ruleset dict so you can edit without touching engine code.
    """

    def __init__(self, ui: UIProtocol, ruleset: Dict[str, Any]):
        self.ui = ui
        self.ruleset = ruleset or {}

    def decide(self, when: str, ctx: InterruptContext) -> InterruptDecision:
        # ruleset can define predicates via same window model
        windows = self.ruleset.get("interrupt_windows", [])
        w = window_allows_interrupt(windows, when, ctx)
        if not w:
            return InterruptDecision(False, "no_matching_window")

        # you can also enforce costs here:
        rp = int(ctx.defender.get("resources", {}).get("rp", 0))
        cost = int(w.get("rp_cost", 1))
        if rp < cost:
            return InterruptDecision(False, "insufficient_rp", window=w)

        # Non-blocking UI note: your system already has awaiting/choice patterns.
        # For now, keep this simple; the refactor step will use your awaiting mechanism.
        choice = self.ui.choice("Interrupt? (spend RP)", ["No", "Yes"])
        attempt = (choice == "Yes") if isinstance(choice, str) else False
        return InterruptDecision(attempt, "player_prompt", window=w)
