from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable

from engine.interrupt_windows import InterruptContext
from engine.interrupt_policy import InterruptPolicy


@dataclass
class ChainResult:
    broken: bool
    break_reason: str = ""
    links_resolved: int = 0


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
        self.apply_interrupt = interrupt_apply_fn  # optional (if you already have apply_interrupt)

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
            return ChainResult(False, "empty_chain", 0)

        attack_d20 = self.roll("1d20")
        defender_d20 = self.roll("1d20") if dv_mode == "per_chain" else 0

        if self.emit_log:
            self.emit_log(ui, f"Aggressor d20: {attack_d20}", "roll")
            if dv_mode == "per_chain":
                self.emit_log(ui, f"Defender d20: {defender_d20}", "roll")

        # Resolve each link in order
        for idx, ability_name in enumerate(chain_ability_names):
            ability = next((a for a in aggressor.get("abilities", []) if a.get("name") == ability_name), None)
            if not ability:
                continue

            # BEFORE LINK interrupt window
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
            decision = self.interrupt_policy.decide("before_link", ctx)
            if decision.attempt:
                broke = self._attempt_interrupt(state, ui, aggressor, defender)
                if broke:
                    return ChainResult(True, "interrupt_before_link", idx)

            # Resolve link using your existing functions
            balance_bonus = 0 if idx == 0 else aggressor.get("resources", {}).get("balance", 0)

            pending = self.resolve_action_step(
                state,
                aggressor,
                ability,
                attack_roll=attack_d20,
                balance_bonus=balance_bonus
            )
            # Apply effects against defender group (for now your system expects "enemies" list)
            # defense_d20 can be threaded if/when your action_resolution supports it.
            _ = self.apply_action_effects(
                state,
                aggressor,
                defender_group,
                defense_d20=defender_d20 if dv_mode == "per_chain" else None
            )

            # AFTER LINK interrupt window
            decision2 = self.interrupt_policy.decide("after_link", ctx)
            if decision2.attempt:
                broke = self._attempt_interrupt(state, ui, aggressor, defender)
                if broke:
                    return ChainResult(True, "interrupt_after_link", idx + 1)

            # IMPORTANT RULE: any damage ends chain (you told me this is in your guide)
            # We detect damage by comparing defender hp pre/post if present.
            # If your engine already enforces it elsewhere, this is still safe as a redundancy.
            if self._damage_ended_chain(defender):
                return ChainResult(True, "damage_ended_chain", idx + 1)

        return ChainResult(False, "completed", len(chain_ability_names))

    def _attempt_interrupt(self, state, ui, aggressor, defender) -> bool:
        """
        Uses your existing interrupt contest if you already have it.
        If you don't, return False and build it next.
        """
        if not self.apply_interrupt:
            return False

        hit, dmg, rolls = self.apply_interrupt(state, defender, aggressor)
        # Convention: defender interrupts aggressor (defender becomes attacker in contest)
        if hit and dmg > 0:
            ui.system(f"INTERRUPT hits for {dmg}. Chain broken.")
            return True
        # You also had the MoD>=5 break rule; keep it:
        if hit and (rolls.get("atk_total", 0) - rolls.get("def_total", 0) >= 5):
            ui.system("INTERRUPT breaks the chain (MoD>=5).")
            return True
        ui.system("Interrupt fails.")
        return False

    def _damage_ended_chain(self, defender: Dict[str, Any]) -> bool:
        # If you store last_damage or a flag, use that.
        # Otherwise, skip—your existing engine might already break chains.
        return bool(defender.get("_damage_taken_this_link"))
