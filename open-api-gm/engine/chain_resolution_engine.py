from __future__ import annotations
from dataclasses import dataclass
import pdb
from typing import Any, Dict, List, Optional, Callable

from engine.interrupt_windows import InterruptContext
from engine.interrupt_policy import InterruptPolicy


@dataclass
class ChainResult:
    status: str  # "completed" | "broken" | "awaiting"
    reason: str
    links_resolved: int = 0

    @property
    def break_reason(self) -> str:
        return self.reason


class ChainResolutionEngine:
    """
    Symmetric chain resolver: works for player or enemy.
    Uses injected callbacks to resolve a link + apply effects,
    and injected InterruptPolicy to handle interrupt decisions.
    """

    def __init__(
        self,
        roll_fn: Callable[[str], int],
        resolve_action_step_fn: Callable[..., Any],
        apply_action_effects_fn: Callable[..., Any],
        interrupt_policy: InterruptPolicy,
        emit_log_fn: Optional[Callable[[Any, str, str], None]] = None,
        interrupt_apply_fn: Optional[Callable[..., Any]] = None,
    ):
        self.roll = roll_fn
        self.resolve_action_step = resolve_action_step_fn
        self.apply_action_effects = apply_action_effects_fn
        self.interrupt_policy = interrupt_policy
        self.emit_log = emit_log_fn
        self.apply_interrupt = interrupt_apply_fn

    def resolve_chain(
        self,
        state: Dict[str, Any],
        ui: Any,
        aggressor: Dict[str, Any],
        defender: Dict[str, Any],
        chain_ability_names: List[str],
        defender_group: List[Dict[str, Any]],
        dv_mode: str = "per_chain",
    ) -> ChainResult:

        
        if not chain_ability_names:
            return ChainResult("completed", "empty_chain", 0)

        attack_d20 = self.roll("1d20")
        defender_d20 = self.roll("1d20") if dv_mode == "per_chain" else None

        if self.emit_log:
            self.emit_log(ui, f"Aggressor d20: {attack_d20}", "roll")
            if defender_d20 is not None:
                self.emit_log(ui, f"Defender d20: {defender_d20}", "roll")

        for idx, ability_name in enumerate(chain_ability_names):
            ability = next((a for a in aggressor.get("abilities", []) if a.get("name") == ability_name), None)
            if not ability:
                continue

            ctx = InterruptContext(
                aggressor=aggressor,
                defender=defender,
                chain_index=idx,
                chain_length=len(chain_ability_names),
                link=ability,
                attack_d20=attack_d20,
                defender_d20=defender_d20,
                state=state,
            )

            decision = self.interrupt_policy.decide("before_link", ctx, state, ui)
            if getattr(decision, "kind", None) == "awaiting":
                return ChainResult("awaiting", "interrupt_prompt", idx)
            if getattr(decision, "kind", None) == "attempt":
                if self._attempt_interrupt(state, ui, aggressor, defender):
                    return ChainResult("broken", "interrupt_before_link", idx)

            balance_bonus = 0 if idx == 0 else aggressor.get("resources", {}).get("balance", 0)

            self.resolve_action_step(
                state,
                aggressor,
                ability,
                attack_roll=attack_d20,
                balance_bonus=balance_bonus,
            )

            self.apply_action_effects(
                state,
                aggressor,
                defender_group,
                defense_d20=defender_d20,
            )

            if defender.get("_damage_taken_this_link"):
                return ChainResult("broken", "damage_ended_chain", idx + 1)

            decision2 = self.interrupt_policy.decide("after_link", ctx, state, ui)
            if getattr(decision2, "kind", None) == "awaiting":
                return ChainResult("awaiting", "interrupt_prompt", idx + 1)
            if getattr(decision2, "kind", None) == "attempt":
                if self._attempt_interrupt(state, ui, aggressor, defender):
                    return ChainResult("broken", "interrupt_after_link", idx + 1)

        return ChainResult("completed", "completed", len(chain_ability_names))

    def _attempt_interrupt(self, state, ui, aggressor, defender) -> bool:
        if not self.apply_interrupt:
            return False

        hit, dmg, rolls, chain_broken = self.apply_interrupt(state, defender, aggressor)
        if chain_broken:
            ui.system(f"INTERRUPT hits for {dmg}. Chain broken.")
            return True
        if chain_broken and (rolls.get("atk_total", 0) - rolls.get("def_total", 0) >= 5):
            ui.system("INTERRUPT breaks the chain (MoD>=5).")
            return True
        ui.system("Interrupt fails.")
        return False

    def _damage_ended_chain(self, defender: Dict[str, Any]) -> bool:
        return bool(defender.get("_damage_taken_this_link"))
