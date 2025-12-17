from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from engine.interrupt_policy import InterruptPolicy
from engine.interrupt_windows import InterruptContext
from engine.stats import stat_mod
from engine.combat_state import combat_get, combat_set


@dataclass
class ChainResult:
    status: str  # "completed" | "broken" | "awaiting"
    reason: str
    links_resolved: int = 0

    @property
    def break_reason(self) -> str:
        return self.reason


def _get_hp(entity: Dict[str, Any]) -> int:
    hp_val = entity.get("hp")
    if hp_val is None and isinstance(entity.get("resources"), dict):
        hp_val = entity["resources"].get("hp")
    if isinstance(hp_val, dict):
        return int(hp_val.get("current", hp_val.get("hp", 0)) or 0)
    return int(hp_val or 0)


def _set_hp(entity: Dict[str, Any], new_hp: int) -> None:
    new_hp = int(new_hp)
    if isinstance(entity.get("hp"), dict):
        entity["hp"]["current"] = new_hp
        return
    if isinstance(entity.get("resources"), dict) and entity["resources"].get("hp") is not None:
        entity["resources"]["hp"] = new_hp
        return
    entity["hp"] = new_hp


def _get_hp_max(entity: Dict[str, Any]) -> Optional[int]:
    hp_val = entity.get("hp")
    if isinstance(hp_val, dict):
        max_hp = hp_val.get("max") or hp_val.get("hp_max")
        return int(max_hp) if max_hp is not None else None
    res = entity.get("resources") if isinstance(entity.get("resources"), dict) else {}
    if isinstance(res, dict):
        max_hp = res.get("hp_max") or res.get("max_hp")
        return int(max_hp) if max_hp is not None else None
    max_hp = entity.get("hp_max") or entity.get("max_hp") or entity.get("maxHp")
    return int(max_hp) if max_hp is not None else None


def _get_resource(entity: Dict[str, Any], key: str, default: int = 0) -> int:
    if isinstance(entity.get("resources"), dict) and key in entity["resources"]:
        return int(entity["resources"].get(key, default) or 0)
    return int(entity.get(key, default) or 0)


def _set_resource(entity: Dict[str, Any], key: str, value: int) -> None:
    value = int(value)
    if isinstance(entity.get("resources"), dict):
        entity["resources"][key] = value
    else:
        entity[key] = value


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _get_dv_base(entity: Dict[str, Any]) -> int:
    """
    Newrules DV: treat as a static target number for the chain.
    - Enemies: dv_base is present.
    - Players: derive a baseline from AGI/DEX if missing.
    """
    dv = entity.get("dv_base")
    if dv is None:
        dv = (entity.get("stat_block") or {}).get("defense", {}).get("dv_base")
    if dv is not None:
        return int(dv)

    attrs = entity.get("attributes") or entity.get("stats") or {}
    agi = attrs.get("agi") or attrs.get("AGI") or attrs.get("dex") or attrs.get("DEX") or 10
    tb = entity.get("temp_bonuses", {}) or {}
    return 10 + stat_mod(int(agi or 10)) + int(tb.get("defense", 0) or 0)


def _get_idf(entity: Dict[str, Any]) -> int:
    if "idf" in entity:
        return int(entity.get("idf") or 0)
    if isinstance(entity.get("resources"), dict):
        return int(entity["resources"].get("idf") or 0)
    return 0


class ChainResolutionEngine:
    """
    Symmetric chain resolver for player/enemy using the newrules math from `CoreRules/newrules.md`.
    - Rolls ONE aggressor d20 for the entire chain (attack_total).
    - Uses static defense_target (dv + momentum + mods).
    - Defender-driven interrupt policy (injected) can pause via awaiting.
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
        if state.get("combat_over"):
            return ChainResult("completed", "combat_over", 0)
        if not chain_ability_names:
            return ChainResult("completed", "empty_chain", 0)

        momentum_cap = int((state.get("rules") or {}).get("momentum_cap", 8) or 8)

        # Roll attack ONCE per chain
        attack_d20 = int(self.roll("1d20"))
        balance = combat_get(state, aggressor, "balance", _get_resource(aggressor, "balance", 0))
        atk_tb = int(((aggressor.get("temp_bonuses") or {}).get("attack", 0)) or 0)
        attack_total = int(attack_d20 + balance + atk_tb)

        if self.emit_log:
            self.emit_log(ui, f"Aggressor d20: {attack_d20} → attack_total {attack_total}", "roll")

        idx = 0
        while idx < len(chain_ability_names):
            name_or_id = chain_ability_names[idx]
            ability = next(
                (a for a in aggressor.get("abilities", []) if a.get("name") == name_or_id or a.get("id") == name_or_id),
                None,
            )
            if not ability:
                ability = next(
                    (m for m in aggressor.get("moves", []) if m.get("name") == name_or_id or m.get("id") == name_or_id),
                    None,
                )
            if not ability:
                if self.emit_log:
                    self.emit_log(ui, f"Unknown action: {name_or_id}", "system")
                idx += 1
                continue

            dv_base = _get_dv_base(defender)
            def_mom = combat_get(state, defender, "momentum", _get_resource(defender, "momentum", 0))
            def_tb = int(((defender.get("temp_bonuses") or {}).get("defense", 0)) or 0)
            defense_target = int(dv_base + def_mom + def_tb)
            hit = attack_total >= defense_target

            if self.emit_log:
                self.emit_log(
                    ui,
                    f"Link {idx + 1}: attack_total {attack_total} vs defense_target {defense_target} → {'HIT' if hit else 'MISS'}",
                    "system",
                )

            ctx = InterruptContext(
                aggressor=aggressor,
                defender=defender,
                chain_index=idx,
                chain_length=len(chain_ability_names),
                link=ability,
                attack_d20=attack_d20,
                defender_d20=None,
                state=state,
            )

            # Interrupt window BEFORE link
            decision = self.interrupt_policy.decide("before_link", ctx, state, ui)
            if getattr(decision, "kind", None) == "awaiting":
                return ChainResult("awaiting", "interrupt_prompt", idx)
            if getattr(decision, "kind", None) == "attempt":
                if self._attempt_interrupt_newrules(state, ui, aggressor, defender, attack_total):
                    combat_set(state, defender, "momentum", combat_get(state, defender, "momentum", def_mom) // 2)
                    return ChainResult("broken", "interrupt_before_link", idx)

            # Momentum/balance bookkeeping (authoritative here).
            if hit:
                mom_gain = 1 if idx < 2 else 2
                combat_set(state, defender, "momentum", _clamp(def_mom + mom_gain, 0, momentum_cap))
                combat_set(state, aggressor, "balance", combat_get(state, aggressor, "balance", balance) + 1)
            else:
                combat_set(state, defender, "momentum", _clamp(def_mom - 1, 0, momentum_cap))
                combat_set(state, aggressor, "balance", combat_get(state, aggressor, "balance", balance) - 1)

            # Resolve + apply effects but force hit/miss so legacy code doesn't overwrite outcomes.
            before_hp = _get_hp(defender)

            self.resolve_action_step(state, aggressor, ability, attack_roll=attack_d20, balance_bonus=0)

            pending = state.get("pending_action")
            if isinstance(pending, dict):
                pending["to_hit"] = attack_total
                pending["resolved_hit"] = hit
                pending["forced_defense_roll"] = defense_target
                pending.setdefault("log", {})["chain_attack_total"] = attack_total
                pending.setdefault("log", {})["defense_target"] = defense_target

            self.apply_action_effects(state, aggressor, defender_group, defense_d20=None)

            after_hp = _get_hp(defender)
            if after_hp < 0:
                _set_hp(defender, 0)
                after_hp = 0

            if self.emit_log and after_hp != before_hp:
                max_hp = _get_hp_max(defender)
                if max_hp:
                    self.emit_log(ui, f"{defender.get('name', 'Target')} HP {after_hp}/{max_hp}", "system")
                else:
                    self.emit_log(ui, f"{defender.get('name', 'Target')} HP {after_hp}", "system")

            if after_hp <= 0:
                ui.system(f"{defender.get('name', 'Target')} is defeated!")
                state["combat_over"] = True
                return ChainResult("completed", "defender_defeated", idx + 1)

            # Interrupt window AFTER link
            decision2 = self.interrupt_policy.decide("after_link", ctx, state, ui)
            if getattr(decision2, "kind", None) == "awaiting":
                return ChainResult("awaiting", "interrupt_prompt", idx + 1)
            if getattr(decision2, "kind", None) == "attempt":
                if self._attempt_interrupt_newrules(state, ui, aggressor, defender, attack_total):
                    combat_set(state, defender, "momentum", combat_get(state, defender, "momentum", def_mom) // 2)
                    return ChainResult("broken", "interrupt_after_link", idx + 1)

            # Press window: after 3rd+ link that HIT, offer press/cash-out (web-safe).
            if hit and idx >= 2:
                if isinstance(state, dict) and "pending_press_decision" in state:
                    decision_id = state.pop("pending_press_decision")
                    if decision_id == "cash_out":
                        return ChainResult("completed", "cashed_out", idx + 1)
                elif not getattr(ui, "is_blocking", True):
                    options = [
                        {"id": "press", "label": "Press"},
                        {"id": "cash_out", "label": "Cash out"},
                    ]
                    ui.choice("Press the chain?", [o["label"] for o in options])
                    state["awaiting"] = {"type": "press_window", "options": options}
                    return ChainResult("awaiting", "press_window", idx + 1)

            idx += 1

        return ChainResult("completed", "completed", len(chain_ability_names))

    def _attempt_interrupt_newrules(
        self,
        state: Dict[str, Any],
        ui: Any,
        aggressor: Dict[str, Any],
        defender: Dict[str, Any],
        attack_total: int,
    ) -> bool:
        """
        Newrules interrupt math (`CoreRules/newrules.md`):
          interrupt_total = d20 + defender interrupt mods
          succeeds if interrupt_total >= attack_total + aggressor_idf - aggressor_balance
        Minimal interrupt damage placeholder is applied to the aggressor.
        """
        interrupt_d20 = int(self.roll("1d20"))
        def_tb = int(((defender.get("temp_bonuses") or {}).get("interrupt", 0)) or 0)
        interrupt_total = int(interrupt_d20 + def_tb)

        threshold = int(
            attack_total
            + _get_idf(aggressor)
            - combat_get(state, aggressor, "balance", _get_resource(aggressor, "balance", 0))
        )

        if self.emit_log:
            self.emit_log(
                ui,
                f"Interrupt d20: {interrupt_d20} → interrupt_total {interrupt_total} vs threshold {threshold}",
                "roll",
            )

        if interrupt_total < threshold:
            ui.system("Interrupt fails.")
            return False

        dmg = max(0, int(self.roll("1d4")))
        if dmg > 0:
            _set_hp(aggressor, max(0, _get_hp(aggressor) - dmg))
            state["_last_damage"] = {"amount": dmg, "source": "interrupt", "by": defender.get("name")}
            ui.system(f"INTERRUPT hits for {dmg}.")
            if self.emit_log:
                hp_now = _get_hp(aggressor)
                max_hp = _get_hp_max(aggressor)
                if max_hp:
                    self.emit_log(ui, f"{aggressor.get('name', 'Target')} HP {hp_now}/{max_hp}", "system")
                else:
                    self.emit_log(ui, f"{aggressor.get('name', 'Target')} HP {hp_now}", "system")
            if _get_hp(aggressor) <= 0:
                ui.system(f"{aggressor.get('name', 'Target')} is defeated!")
                state["combat_over"] = True

        ui.system("Chain broken by interrupt.")
        return True
