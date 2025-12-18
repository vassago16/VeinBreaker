from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from engine.interrupt_policy import InterruptPolicy
from engine.interrupt_windows import InterruptContext
from engine.stats import stat_mod
from engine.combat_state import combat_add, combat_get, combat_set, status_add, status_get
from ui.events import emit_event, emit_resource_update


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
    stat_block = entity.get("stat_block") if isinstance(entity.get("stat_block"), dict) else {}
    if isinstance(stat_block, dict):
        hp_block = stat_block.get("hp") if isinstance(stat_block.get("hp"), dict) else {}
        if isinstance(hp_block, dict) and hp_block.get("max") is not None:
            return int(hp_block.get("max") or 0)
    max_hp = entity.get("hp_max") or entity.get("max_hp") or entity.get("maxHp")
    return int(max_hp) if max_hp is not None else None


def _get_execution_threshold_pct(entity: Dict[str, Any]) -> float:
    """
    Execution threshold as a percentage of max HP. Default 25%.
    """
    try:
        v = entity.get("execution_threshold_pct")
        if v is not None:
            return float(v)
        stat_block = entity.get("stat_block") if isinstance(entity.get("stat_block"), dict) else {}
        execution = stat_block.get("execution") if isinstance(stat_block, dict) else None
        if isinstance(execution, dict) and execution.get("threshold_pct") is not None:
            return float(execution.get("threshold_pct") or 0.25)
    except Exception:
        pass
    return 0.25


def _status_id(name: str) -> str:
    s = "".join(ch.lower() if ch.isalnum() else "_" for ch in (name or "").strip())
    s = "_".join([p for p in s.split("_") if p])
    return f"status.{s}" if s else "status.unknown"


def _status_stacks(state: Dict[str, Any], entity: Dict[str, Any], status_name: str) -> int:
    sid = status_name if status_name.startswith("status.") else _status_id(status_name)
    st = status_get(state, entity, sid)
    if not isinstance(st, dict):
        return 0
    return int(st.get("stacks", 0) or 0)


def _is_primed_by_hp(entity: Dict[str, Any]) -> bool:
    hp_max = _get_hp_max(entity)
    if not hp_max:
        return False
    hp_cur = _get_hp(entity)
    pct = _get_execution_threshold_pct(entity)
    try:
        pct = float(pct)
    except Exception:
        pct = 0.25
    return hp_cur <= int(round(float(hp_max) * pct))


def _is_primed(state: Dict[str, Any], entity: Dict[str, Any]) -> bool:
    """
    Primed conditions (Phase 1+):
      - HP <= execution threshold
      - Vulnerable stacks >= 3
      - Stagger stacks >= 2
      - Explicit Primed status present
    Status stacks live in encounter state (engine.combat_state).
    """
    if _is_primed_by_hp(entity):
        return True
    if _status_stacks(state, entity, "Vulnerable") >= 3:
        return True
    if _status_stacks(state, entity, "Stagger") >= 2:
        return True
    if _status_stacks(state, entity, "Primed") >= 1:
        return True
    return False


def _canonical_prime_status(name: str) -> Optional[str]:
    n = str(name or "").strip().lower()
    if n.startswith("status."):
        n = n.split(".", 1)[1]
    if n in {"prime", "primed"}:
        return "Primed"
    if n == "vulnerable":
        return "Vulnerable"
    if n == "stagger":
        return "Stagger"
    return None


def _apply_prime_status_effects_on_hit(
    state: Dict[str, Any],
    *,
    aggressor: Dict[str, Any],
    defender: Dict[str, Any],
    action: Dict[str, Any],
) -> None:
    """
    Apply only priming-relevant statuses (Vulnerable/Stagger/Primed) into encounter state.
    We intentionally keep this narrow so we don't double-apply all legacy status plumbing.
    """
    effects: List[Any] = []

    # Abilities: {"effects": {"on_hit": [ ... ]}}
    eff = action.get("effects") if isinstance(action.get("effects"), dict) else None
    if isinstance(eff, dict) and isinstance(eff.get("on_hit"), list):
        effects = list(eff.get("on_hit") or [])

    # Monster moves: {"on_hit": {"effects": [ ... ]}}
    if not effects:
        on_hit = action.get("on_hit") if isinstance(action.get("on_hit"), dict) else None
        if isinstance(on_hit, dict) and isinstance(on_hit.get("effects"), list):
            effects = list(on_hit.get("effects") or [])

    if not effects:
        return

    for raw in effects:
        status_name: Optional[str] = None
        stacks = 1
        target = "enemy"

        if isinstance(raw, str):
            status_name = _canonical_prime_status(raw)
        elif isinstance(raw, dict):
            et = str(raw.get("type") or "").strip()
            if et.lower() == "status":
                status_name = _canonical_prime_status(raw.get("status") or raw.get("id") or "")
                stacks = int(raw.get("stacks", 1) or 1)
                target = str(raw.get("target") or "enemy")
            else:
                status_name = _canonical_prime_status(et)
                stacks = int(raw.get("stacks", 1) or 1)
                target = str(raw.get("target") or "enemy")
        else:
            continue

        if not status_name:
            continue

        dest = aggressor if target in {"self", "actor", "aggressor"} else defender
        status_add(state, dest, status=status_name, stacks=stacks, duration_rounds=1)


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
        start_index: int = 0,
    ) -> ChainResult:
        if state.get("combat_over"):
            return ChainResult("completed", "combat_over", 0)
        if not chain_ability_names:
            return ChainResult("completed", "empty_chain", 0)

        momentum_cap = int((state.get("rules") or {}).get("momentum_cap", 8) or 8)

        # Balance is per-chain: reset aggressor balance at chain start.
        if isinstance(aggressor, dict) and aggressor.get("_combat_key"):
            combat_set(state, aggressor, "balance", 0)

        def _lookup_action(name_or_id: str) -> Optional[Dict[str, Any]]:
            a = next(
                (x for x in aggressor.get("abilities", []) if x.get("name") == name_or_id or x.get("id") == name_or_id),
                None,
            )
            if a:
                return a
            m = next(
                (x for x in aggressor.get("moves", []) if x.get("name") == name_or_id or x.get("id") == name_or_id),
                None,
            )
            return m

        # Only roll if we have at least one non-movement link in this chain.
        needs_roll = False
        for n in chain_ability_names:
            action = _lookup_action(n)
            if not isinstance(action, dict):
                continue
            if (action.get("type") or "").lower() != "movement" and (action.get("resolution") or "").lower() != "movement":
                needs_roll = True
                break

        balance = combat_get(state, aggressor, "balance", _get_resource(aggressor, "balance", 0))
        heat = combat_get(state, aggressor, "heat", _get_resource(aggressor, "heat", 0))
        atk_tb = int(((aggressor.get("temp_bonuses") or {}).get("attack", 0)) or 0)

        # Execution intent (Phase 1): only HP-threshold priming is supported.
        chain_obj = aggressor.get("chain") if isinstance(aggressor.get("chain"), dict) else {}
        execute_requested = bool(chain_obj.get("execute")) if isinstance(chain_obj, dict) else False
        execute_primed = _is_primed(state, defender)
        execute_link_idx: Optional[int] = None

        if execute_requested and not execute_primed and self.emit_log:
            self.emit_log(ui, "Execution requested but target is not Primed.", "system")

        try:
            start_index = int(start_index or 0)
        except Exception:
            start_index = 0

        # Identify the first attack link (at/after start_index) that can be replaced by Execution Strike.
        if execute_requested and execute_primed:
            for i in range(max(0, start_index), len(chain_ability_names)):
                name_or_id = chain_ability_names[i]
                ab = _lookup_action(name_or_id)
                if not isinstance(ab, dict):
                    continue
                if (ab.get("type") or "").lower() == "attack":
                    execute_link_idx = i
                    break
            if execute_link_idx is None and self.emit_log:
                self.emit_log(ui, "Execution requested but no attack link exists in this chain.", "system")

        # Roll attack ONCE per chain (movement-only chains do not roll).
        # If we are resuming, reuse the prior chain roll.
        if start_index > 0 and isinstance(state, dict) and state.get("_chain_attack_d20") is not None:
            try:
                attack_d20 = int(state.get("_chain_attack_d20") or 0)
                attack_total = int(state.get("_chain_attack_total") or 0)
                needs_roll = bool(state.get("_chain_needs_roll", needs_roll))
            except Exception:
                attack_d20 = int(self.roll("1d20")) if needs_roll else 0
                attack_total = int(attack_d20 + balance + heat + atk_tb) if needs_roll else 0
        else:
            attack_d20 = int(self.roll("1d20")) if needs_roll else 0
            attack_total = int(attack_d20 + balance + heat + atk_tb) if needs_roll else 0
            if isinstance(state, dict):
                state["_chain_attack_d20"] = int(attack_d20)
                state["_chain_attack_total"] = int(attack_total)
                state["_chain_needs_roll"] = bool(needs_roll)

        if self.emit_log:
            if needs_roll:
                self.emit_log(
                    ui,
                    f"Aggressor d20: {attack_d20} (balance {balance}, heat {heat}, atk_bonus {atk_tb}) → attack_total {attack_total}",
                    "roll",
                )

        idx = max(0, start_index)
        while idx < len(chain_ability_names):
            name_or_id = chain_ability_names[idx]
            ability = _lookup_action(name_or_id)
            if not ability:
                if self.emit_log:
                    self.emit_log(ui, f"Unknown action: {name_or_id}", "system")
                idx += 1
                continue

            # Movement links: do not roll; apply resource/status deltas and continue.
            if (ability.get("type") or "").lower() == "movement" or (ability.get("resolution") or "").lower() == "movement":
                ab_name = ability.get("name") or ability.get("id") or name_or_id
                delta = ability.get("resourceDelta") if isinstance(ability.get("resourceDelta"), dict) else {}
                mom_delta = int(delta.get("momentum", 1) or 0) if isinstance(delta, dict) else 1
                if mom_delta:
                    combat_add(state, aggressor, "momentum", mom_delta)
                # Status application (Arcane Ward and future statuses)
                applied_statuses = []
                effects = ability.get("effects", {}) if isinstance(ability.get("effects"), dict) else {}
                on_use = effects.get("on_use", []) if isinstance(effects.get("on_use"), list) else []
                for eff in on_use:
                    if not isinstance(eff, dict):
                        continue
                    if eff.get("type") == "status":
                        sname = eff.get("status") or eff.get("id")
                        if not sname:
                            continue
                        stacks = int(eff.get("stacks", 1) or 1)
                        # Hardcoded starter: Arcane Ward -> shield 1 for 1 round
                        shield = 1 if str(sname).strip().lower() in {"arcane ward", "arcane_ward"} else 0
                        status_add(state, aggressor, status=str(sname), stacks=stacks, duration_rounds=1, shield=shield)
                        applied_statuses.append(str(sname))

                if self.emit_log:
                    bits = []
                    if mom_delta:
                        bits.append(f"+momentum {mom_delta}")
                    if applied_statuses:
                        bits.append("status " + ", ".join(applied_statuses))
                    suffix = (" (" + "; ".join(bits) + ")") if bits else ""
                    self.emit_log(ui, f"Link {idx + 1}:{ab_name} (movement){suffix}", "system")
                try:
                    emit_resource_update(
                        ui,
                        momentum=combat_get(state, aggressor, "momentum", _get_resource(aggressor, "momentum", 0)),
                        balance=combat_get(state, aggressor, "balance", _get_resource(aggressor, "balance", 0)),
                        heat=combat_get(state, aggressor, "heat", _get_resource(aggressor, "heat", 0)),
                    )
                except Exception:
                    pass
                idx += 1
                continue

            dv_base = _get_dv_base(defender)
            def_mom = combat_get(state, defender, "momentum", _get_resource(defender, "momentum", 0))
            def_tb = int(((defender.get("temp_bonuses") or {}).get("defense", 0)) or 0)
            defense_target = int(dv_base + def_mom + def_tb)

            # Execution Strike replaces the selected attack link.
            if execute_link_idx is not None and idx == execute_link_idx:
                # Must have 1 RP available.
                rp_cur = combat_get(state, aggressor, "rp", _get_resource(aggressor, "resolve", 0))
                if rp_cur < 1:
                    if self.emit_log:
                        self.emit_log(ui, "Execution failed: not enough RP (needs 1).", "system")
                    execute_link_idx = None
                else:
                    # Spend 1 RP and set Heat to 0 immediately.
                    combat_set(state, aggressor, "rp", int(rp_cur - 1))
                    if isinstance(aggressor.get("resources"), dict):
                        aggressor["resources"]["resolve"] = int(rp_cur - 1)
                    combat_set(state, aggressor, "heat", 0)
                    try:
                        emit_resource_update(
                            ui,
                            momentum=combat_get(state, aggressor, "momentum", _get_resource(aggressor, "momentum", 0)),
                            balance=combat_get(state, aggressor, "balance", _get_resource(aggressor, "balance", 0)),
                            heat=0,
                        )
                    except Exception:
                        pass

                    exec_balance = combat_get(state, aggressor, "balance", balance) - 2
                    try:
                        combat_set(state, aggressor, "balance", int(exec_balance))
                    except Exception:
                        pass
                    exec_attack_total = int(attack_d20 + exec_balance + 0 + atk_tb)
                    exec_hit = exec_attack_total >= defense_target

                    if self.emit_log:
                        self.emit_log(
                            ui,
                            f"EXECUTION STRIKE: roll {attack_d20} + balance {exec_balance} + heat 0 + {atk_tb} -> AV {exec_attack_total} "
                            f"vs DV {defense_target} -> {'SUCCESS' if exec_hit else 'FAIL'}",
                            "system",
                        )

                    if exec_hit:
                        # Kill: reduce defender to 0 HP and end fight.
                        _set_hp(defender, 0)
                        state["combat_over"] = True

                        # Rewards (Phase 1 minimal): +1 blood mark, +1 RP (clamped), netting the spend.
                        try:
                            marks = aggressor.setdefault("marks", {})
                            if isinstance(marks, dict):
                                marks["blood"] = int(marks.get("blood", 0) or 0) + 1
                        except Exception:
                            pass
                        try:
                            rp_cap = combat_get(state, aggressor, "rp_cap", 0)
                            rp_after = combat_get(state, aggressor, "rp", 0) + 1
                            if int(rp_cap or 0) > 0:
                                rp_after = min(int(rp_cap), int(rp_after))
                            combat_set(state, aggressor, "rp", int(rp_after))
                            if isinstance(aggressor.get("resources"), dict):
                                aggressor["resources"]["resolve"] = int(rp_after)
                        except Exception:
                            pass

                        try:
                            emit_event(
                                ui,
                                {
                                    "type": "enemy_executed",
                                    "enemy": defender.get("name", "Enemy"),
                                    "text": f"{defender.get('name', 'Enemy')} EXECUTED",
                                },
                            )
                        except Exception:
                            pass
                        if self.emit_log:
                            self.emit_log(ui, f"{defender.get('name','Target')} EXECUTED.", "system")

                        return ChainResult("completed", "execution", idx + 1)

                    # Failure outcomes.
                    margin = int(defense_target - exec_attack_total)
                    catastrophic = margin >= 10

                    # Stagger 1
                    try:
                        status_add(state, aggressor, status="Stagger", stacks=1, duration_rounds=1)
                    except Exception:
                        pass

                    # Lose all Momentum
                    try:
                        combat_set(state, aggressor, "momentum", 0)
                        emit_resource_update(
                            ui,
                            momentum=0,
                            balance=combat_get(state, aggressor, "balance", exec_balance),
                            heat=combat_get(state, aggressor, "heat", 0),
                        )
                    except Exception:
                        pass

                    # Enemy gains +1 Positive Balance (tracked as +1 balance for now)
                    try:
                        combat_add(state, defender, "balance", 1)
                    except Exception:
                        pass

                    # Catastrophic: take critical damage (scaled by encounter tier).
                    # Wiki guidance: 1d6–1d10 "GM fiat"; for now we scale by tier to keep pressure meaningful.
                    if catastrophic:
                        try:
                            tier = int(defender.get("tier", 1) or 1)
                        except Exception:
                            tier = 1
                        tier = max(1, tier)
                        try:
                            # Tier-scaled backlash: (1d6 × tier)
                            crit = max(0, int(self.roll("1d6")) * tier)
                        except Exception:
                            crit = 0
                        if crit > 0:
                            before_hp = _get_hp(aggressor)
                            _set_hp(aggressor, max(0, before_hp - crit))
                            state["_last_damage"] = {
                                "amount": crit,
                                "source": "execution_backfire",
                                "by": defender.get("name"),
                                "tier": tier,
                            }
                            ui.system(f"Catastrophic execution backlash: {crit} damage (1d6×T{tier}).")
                            if _get_hp(aggressor) <= 0:
                                ui.system(f"{aggressor.get('name', 'Target')} is defeated!")
                                state["combat_over"] = True

                    # UI + combat log signal
                    try:
                        emit_event(ui, {
                            "type": "execution_failed",
                            "catastrophic": bool(catastrophic),
                            "text": "CATASTROPHIC EXECUTION FAILURE" if catastrophic else "EXECUTION FAILED",
                        })
                    except Exception:
                        pass
                    if self.emit_log:
                        self.emit_log(ui, "CATASTROPHIC EXECUTION FAILURE" if catastrophic else "EXECUTION FAILED", "system")

                    return ChainResult("broken", "execution_failed_catastrophic" if catastrophic else "execution_failed", idx + 1)

            hit = attack_total >= defense_target

            if self.emit_log:
                ab_name = ability.get("name") or ability.get("id") or name_or_id
                self.emit_log(
                    ui,
                    f"Link {idx + 1}:{ab_name} roll {attack_d20} + {balance} + heat {heat} + {atk_tb} -> attack_total {attack_total} "
                    f"vs defense_target {dv_base} + {def_mom} + {def_tb} = {defense_target} -> {'HIT' if hit else 'MISS'}",
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
                    # Let the outer loop render a human-readable chain break banner.
                    try:
                        state["_chain_break_action"] = ability.get("name") or ability.get("id") or name_or_id
                    except Exception:
                        pass
                    return ChainResult("broken", "interrupt_before_link", idx)

            # Momentum/balance bookkeeping (authoritative here).
            if hit:
                mom_gain = 1 if idx < 2 else 2
                combat_set(state, defender, "momentum", _clamp(def_mom + mom_gain, 0, momentum_cap))
                combat_set(state, aggressor, "balance", combat_get(state, aggressor, "balance", balance) + 2)
            else:
                combat_set(state, defender, "momentum", _clamp(def_mom - 1, 0, momentum_cap))
                combat_set(state, aggressor, "balance", combat_get(state, aggressor, "balance", balance) + 1)

            # Emit updated meters after this link decision so UI can reflect balance/momentum live.
            try:
                emit_resource_update(
                    ui,
                    momentum=combat_get(state, aggressor, "momentum", _get_resource(aggressor, "momentum", 0)),
                    balance=combat_get(state, aggressor, "balance", _get_resource(aggressor, "balance", 0)),
                    heat=combat_get(state, aggressor, "heat", _get_resource(aggressor, "heat", 0)),
                )
            except Exception:
                pass

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

            # Encounter statuses (Primed conditions beyond HP): apply on-hit status effects.
            if hit:
                try:
                    _apply_prime_status_effects_on_hit(state, aggressor=aggressor, defender=defender, action=ability)
                except Exception:
                    pass

            # Mid-chain execution prompt: if the defender becomes Primed, pause and ask the player.
            try:
                if (
                    not getattr(ui, "is_blocking", True)
                    and isinstance(state, dict)
                    and aggressor.get("_combat_key") == "player"
                    and str(defender.get("_combat_key", "")).startswith("enemy")
                    and not bool(aggressor.get("chain", {}).get("execute"))
                    and _is_primed(state, defender)
                    and not state.get("phase", {}).get("execute_prompted")
                ):
                    emit_event(ui, {
                        "type": "execute_window",
                        "enemy": defender.get("name", defender.get("id", "Enemy")),
                        "text": "They are open. Their rhythm collapses. Take the mark—EXECUTE?",
                    })
                    state.setdefault("phase", {})["execute_prompted"] = True
                    state["awaiting"] = {"type": "execute_prompt"}
                    return ChainResult("awaiting", "execute_prompt", idx + 1)
            except Exception:
                pass

            # Scene metrics: track player damage taken.
            try:
                if isinstance(state, dict) and isinstance(defender, dict) and defender.get("_combat_key") == "player":
                    if after_hp < before_hp:
                        metrics = state.setdefault("scene_metrics", {})
                        if isinstance(metrics, dict):
                            metrics["damage_taken"] = int(metrics.get("damage_taken", 0) or 0) + int(before_hp - after_hp)
            except Exception:
                pass

            # Enemy HUD card: update enemy meters + HP each link.
            try:
                key = str(defender.get("_combat_key", "")) if isinstance(defender, dict) else ""
                if key.startswith("enemy"):
                    emit_event(ui, {
                        "type": "enemy_update",
                        "enemy": {
                            "name": defender.get("name", defender.get("id", "Enemy")),
                            "tier": defender.get("tier"),
                            "role": defender.get("role"),
                            "dv_base": dv_base,
                             "idf": _get_idf(defender),
                             "hp": {"current": int(after_hp), "max": int(_get_hp_max(defender) or after_hp)},
                             "execution_threshold_pct": _get_execution_threshold_pct(defender),
                             "primed": _is_primed(state, defender),
                             "heat": combat_get(state, defender, "heat", _get_resource(defender, "heat", 0)),
                             "momentum": combat_get(state, defender, "momentum", _get_resource(defender, "momentum", 0)),
                             "balance": combat_get(state, defender, "balance", _get_resource(defender, "balance", 0)),
                         }
                     })
            except Exception:
                pass

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
                    # Let the outer loop render a human-readable chain break banner.
                    try:
                        state["_chain_break_action"] = ability.get("name") or ability.get("id") or name_or_id
                    except Exception:
                        pass
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
        perfect_threshold = threshold + 5

        if self.emit_log:
            self.emit_log(
                ui,
                f"Interrupt d20: {interrupt_d20} → interrupt_total {interrupt_total} vs threshold {threshold}",
                "roll",
            )

        if interrupt_total < threshold:
            ui.system("Interrupt fails.")
            return False

        perfect = interrupt_total >= perfect_threshold

        # Interrupt applies penalties to the chain owner (aggressor).
        try:
            heat_pen = -2 if perfect else -1
            bal_pen = -1
            mom_pen = -2 if perfect else -1

            new_heat = _clamp(combat_get(state, aggressor, "heat", _get_resource(aggressor, "heat", 0)) + heat_pen, 0, 99)
            new_mom = _clamp(combat_get(state, aggressor, "momentum", _get_resource(aggressor, "momentum", 0)) + mom_pen, 0, 99)
            new_bal = _clamp(combat_get(state, aggressor, "balance", _get_resource(aggressor, "balance", 0)) + bal_pen, -10, 10)
            combat_set(state, aggressor, "heat", new_heat)
            combat_set(state, aggressor, "momentum", new_mom)
            combat_set(state, aggressor, "balance", new_bal)
            emit_resource_update(ui, heat=new_heat, momentum=new_mom, balance=new_bal)
        except Exception:
            pass

        if not perfect:
            ui.system("Interrupt succeeds (not perfect). Chain holds.")
            return False

        # UI signal: perfect interrupt (flash + INTERRUPTED overlay)
        try:
            emit_event(ui, {"type": "interrupt"})
            # Player perfect parry: surface a dedicated visceral prompt screen (no choices yet).
            if (
                isinstance(defender, dict)
                and isinstance(aggressor, dict)
                and defender.get("_combat_key") == "player"
                and str(aggressor.get("_combat_key", "")).startswith("enemy")
            ):
                emit_event(ui, {"type": "visceral_attack", "text": "Visceral Attack"})
            else:
                emit_event(ui, {"type": "chain_interrupted", "text": f"{defender.get('name', 'Defender')} interrupts!"})
            # Prevent the outer game loop from cascading into the next prompt in the same /step.
            if isinstance(state, dict):
                state["_pause_after_interrupt"] = True
        except Exception:
            pass

        # Counter reward: only on perfect counter (player interrupts enemy chain).
        try:
            if isinstance(defender, dict) and isinstance(aggressor, dict):
                if defender.get("_combat_key") == "player" and aggressor.get("_combat_key") == "enemy":
                    rp_cap = combat_get(state, defender, "rp_cap", 0)
                    rp_cur = combat_get(state, defender, "rp", 0)
                    rp_new = rp_cur + 1
                    if int(rp_cap or 0) > 0:
                        rp_new = min(int(rp_cap), int(rp_new))
                    combat_set(state, defender, "rp", int(rp_new))
                    emit_event(ui, {"type": "character_update", "character": {"rp": {"current": int(rp_new), "cap": int(rp_cap or 0)}}})
                    if self.emit_log:
                        self.emit_log(ui, f"Counter reward: +1 RP ({int(rp_new)}/{int(rp_cap or 0)})", "system")
        except Exception:
            pass

        # Perfect parry: counter damage.
        dmg = max(0, int(self.roll("1d4")))
        if dmg > 0:
            before_hp = _get_hp(aggressor)
            _set_hp(aggressor, max(0, before_hp - dmg))
            state["_last_damage"] = {"amount": dmg, "source": "counter", "by": defender.get("name")}
            ui.system(f"PERFECT PARRY hits for {dmg}.")
            try:
                if isinstance(state, dict) and isinstance(aggressor, dict) and aggressor.get("_combat_key") == "player":
                    metrics = state.setdefault("scene_metrics", {})
                    if isinstance(metrics, dict):
                        metrics["damage_taken"] = int(metrics.get("damage_taken", 0) or 0) + int(dmg)
            except Exception:
                pass
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

        ui.system("Chain broken by perfect interrupt.")
        return True
