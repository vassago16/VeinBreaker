import random
from engine.stats import stat_mod
from engine.status import apply_status_effects
from engine.utilities import compare
from engine.combat_state import combat_add, combat_get, combat_set, consume_shield, shield_value

try:
    from game_context import NARRATOR
except Exception:
    NARRATOR = None

def roll(dice: str) -> int:
    """
    Roll a dice expression like '1d6' or '2d4'.
    """
    try:
        count_str, die_str = dice.lower().split("d")
        count = int(count_str)
        die = int(die_str)
    except Exception:
        return 0
    return sum(random.randint(1, die) for _ in range(count))


def ability_attack_roll(character, ability, base_d20=None):
    """
    Attack roll: d20 plus stat mod if addStatToAttackRoll (default true) and stat provided.
    If base_d20 is provided, it is used instead of rolling a new d20.
    Returns (total, d20_roll).
    """
    die_total = base_d20 if base_d20 is not None else roll("2d10")
    add_stat = ability.get("addStatToAttackRoll", True)
    stat_key = ability.get("stat")
    stats = character.get("stats") or character.get("attributes", {})
    attack_bonus = (character.get("temp_bonuses", {}) or {}).get("attack", 0)
    total = die_total + attack_bonus
    if add_stat and stat_key and stat_key in stats:
        total += stat_mod(stats[stat_key])
    return total, die_total


def ability_damage_total(character, ability, base_roll):
    """
    Compute damage total; add stat mod if addStatToDamage is true (default).
    """
    add_stat = ability.get("addStatToDamage", True)
    stat_key = ability.get("stat")
    stats = character.get("stats") or character.get("attributes", {})
    if add_stat and stat_key and stat_key in stats:
        return base_roll + stat_mod(stats[stat_key])
    return base_roll


def apply_effect_list(effects, actor, enemy=None, default_target="enemy"):
    """
    Apply a list of structured effects to targets.
    Supported types: resource_delta, resource_set, status, buff, reduce_damage placeholder, damage_bonus placeholder.
    Returns a dict with any applied statuses.
    """
    applied = {"statuses": []}
    if not effects:
        return applied
    for eff in effects:
        if not isinstance(eff, dict):
            continue
        target = eff.get("target") or default_target
        dest = actor if target == "self" else enemy if target == "enemy" else actor
        if dest is None:
            continue
        etype = eff.get("type")
        if etype == "resource_delta":
            res_name = eff.get("resource")
            delta = eff.get("delta", 0)
            if res_name:
                res = dest.setdefault("resources", {}) if target == "self" else dest.get("resources", dest)
                res_val = res.get(res_name, 0)
                res[res_name] = res_val + delta
        elif etype == "heal":
            dice = eff.get("dice", "1d4")
            flat = eff.get("flat", 0) or 0
            amount = roll(dice) + int(flat)
            if amount <= 0:
                continue
            if isinstance(dest.get("resources"), dict) and dest["resources"].get("hp") is not None:
                res = dest["resources"]
                cur = int(res.get("hp", 0) or 0)
                max_hp = res.get("hp_max") or res.get("max_hp") or res.get("maxHp")
                if max_hp is None:
                    res["hp"] = max(0, cur + int(amount))
                else:
                    res["hp"] = min(int(max_hp), max(0, cur + int(amount)))
            else:
                hp_val = dest.get("hp", 0)
                if isinstance(hp_val, dict):
                    cur = int(hp_val.get("current", hp_val.get("hp", 0)) or 0)
                    max_hp = hp_val.get("max", hp_val.get("hp_max", cur))
                    hp_val["current"] = min(int(max_hp), max(0, cur + int(amount)))
                    dest["hp"] = hp_val
                else:
                    dest["hp"] = max(0, int(hp_val or 0) + int(amount))
        elif etype == "resource_set":
            res_name = eff.get("resource")
            val = eff.get("value")
            if res_name and val is not None:
                res = dest.setdefault("resources", {}) if target == "self" else dest.get("resources", dest)
                res[res_name] = val
        elif etype in {"status", "buff"}:
            # Normalize into a status effect for apply_status_effects
            status_name = eff.get("status") or etype
            stacks = eff.get("stacks", 1)
            duration = eff.get("duration")
            apply_status_effects(dest, [{"type": status_name, "stacks": stacks, "duration": duration}])
            applied["statuses"].append(status_name)
        elif etype == "reduce_damage":
            dest.setdefault("damage_reduction", []).append(eff)
        elif etype in {"attack_bonus", "defense_bonus", "idf_bonus"}:
            tb = dest.setdefault("temp_bonuses", {})
            key = "attack" if etype == "attack_bonus" else "defense" if etype == "defense_bonus" else "idf"
            tb[key] = tb.get(key, 0) + (eff.get("amount", eff.get("delta", 0)) or 0)
        # damage_bonus could be handled in attack contexts later
    return applied


def resolve_action_step(state, character, ability, attack_roll=None, balance_bonus=0):
    """
    Pay costs and roll dice; do not apply effects yet.
    """
    resources = character.setdefault("resources", {}) if isinstance(character, dict) else {}
    cost = ability.get("cost", 0)
    resource = ability.get("resource", "resolve")
    pool = ability.get("pool")
    if cost:
        if pool and pool in character.get("pools", {}):
            character["pools"][pool] = max(0, character["pools"][pool] - cost)
        elif resource != "resolve" and resource in resources:
            resources[resource] = max(
                0, resources[resource] - cost
            )

    attack_total, d20_roll = ability_attack_roll(character, ability, base_d20=attack_roll)
    to_hit = attack_total + balance_bonus
    # On-use effects (self-target) before rolling
    effects = ability.get("effects") or {}
    apply_effect_list(effects.get("on_use", []), actor=character, enemy=None, default_target="self")

    # Determine damage dice from structured effects if present
    dmg_effects = (ability.get("effects") or {}).get("on_hit", [])
    dmg_entry = next((e for e in dmg_effects if e.get("type") == "damage"), None)
    dice_expr = ability.get("dice", "1d4")
    if dmg_entry and isinstance(dmg_entry, dict):
        dice_expr = dmg_entry.get("dice", dice_expr)
        if dmg_entry.get("stat"):
            ability.setdefault("stat", dmg_entry.get("stat"))
    damage_roll = roll(dice_expr)

    state["pending_action"] = {
        "ability": ability.get("name"),
        "to_hit": to_hit,
        "attack_d20": d20_roll,
        "damage_roll": damage_roll,
        "tags": ability.get("tags", []),
        "cancelled": False,
        "ability_obj": ability,
        "log": {
            "cost": cost,
            "resource": resource,
            "attack_d20": d20_roll,
            "balance_bonus": balance_bonus,
            "pool": pool,
            "to_hit": to_hit,
            "damage_roll": damage_roll,
        },
    }
    return state["pending_action"]


def apply_momentum_feeds(enemy, trigger: str):
    """
    Apply momentum feeds from enemy resolved_archetype.state_interactions.momentum.feeds
    for a given trigger (e.g., 'player_miss').
    Returns how much momentum was gained.
    """
    if not enemy:
        return 0
    feeds = (
        enemy.get("resolved_archetype", {})
        .get("state_interactions", {})
        .get("momentum", {})
        .get("feeds", [])
    )
    gained = 0
    for feed in feeds:
        if not isinstance(feed, dict):
            continue
        if feed.get("on") != trigger:
            continue
        chance = feed.get("chance", 1)
        try:
            if random.random() > float(chance):
                continue
        except Exception:
            continue
        enemy["momentum"] = enemy.get("momentum", 0) + 1
        gained += 1
    return gained


def apply_action_effects(state, character, enemies, defense_d20=None):
    pending = state.get("pending_action")
    if not pending or pending.get("cancelled"):
        state["pending_action"] = None
        return "action_cancelled"

    resources = character.setdefault("resources", {}) if isinstance(character, dict) else {}

    ability = pending.get("ability_obj", {}) or {}
    damage_roll = pending.get("damage_roll", 0)
    to_hit = pending.get("to_hit", 0)
    tags = pending.get("tags", [])
    log = pending.get("log", {})
    log["ability_name"] = pending.get("ability")
    effects = ability.get("effects") or {}

    def _get_res(e, k, default=0):
        if isinstance(e, dict) and isinstance(e.get("resources"), dict) and k in e["resources"]:
            return e["resources"].get(k, default)
        if isinstance(e, dict):
            return e.get(k, default)
        return default

    def _get_hp_val(e):
        hp = _get_res(e, "hp", None)
        if hp is None:
            hp = e.get("hp") if isinstance(e, dict) else None
        if isinstance(hp, dict):
            return hp.get("current", hp.get("hp", 0))
        return hp if hp is not None else 0

    def _get_hp_max_val(e):
        if not isinstance(e, dict):
            return None
        hp = e.get("hp")
        if isinstance(hp, dict):
            mx = hp.get("max") or hp.get("hp_max") or hp.get("max_hp") or hp.get("maxHp")
            return int(mx) if mx is not None else None
        res = e.get("resources") if isinstance(e.get("resources"), dict) else None
        if isinstance(res, dict):
            mx = res.get("hp_max") or res.get("max_hp") or res.get("maxHp")
            return int(mx) if mx is not None else None
        stat_block = e.get("stat_block") if isinstance(e.get("stat_block"), dict) else {}
        if isinstance(stat_block, dict):
            hp_block = stat_block.get("hp") if isinstance(stat_block.get("hp"), dict) else {}
            if isinstance(hp_block, dict) and hp_block.get("max") is not None:
                return int(hp_block.get("max") or 0)
        mx = e.get("hp_max") or e.get("max_hp") or e.get("maxHp")
        return int(mx) if mx is not None else None

    def _is_wounded_foe(e) -> bool:
        try:
            cur = int(_get_hp_val(e) or 0)
            mx = _get_hp_max_val(e)
            if mx is None:
                return False
            mx = int(mx or 0)
            if mx <= 0:
                return False
            return cur < (mx / 2.0)
        except Exception:
            return False

    def _blood_marks() -> int:
        try:
            marks = character.get("marks") if isinstance(character.get("marks"), dict) else {}
            return int(marks.get("blood", 0) or 0)
        except Exception:
            return 0

    def _set_hp_val(e, hp):
        if not isinstance(e, dict):
            return
        if isinstance(e.get("hp"), dict):
            e["hp"]["current"] = hp
            return
        if isinstance(e.get("resources"), dict) and e["resources"].get("hp") is not None:
            e["resources"]["hp"] = hp
            return
        e["hp"] = hp

    # Defense roll:
    # - If defense_d20 provided, use contested DV: d20 + IDF + Momentum + temp bonuses
    # - Else, use static dv_base from data
    enemy = enemies[0] if enemies else None
    dv_base = None
    enemy_idf = 0
    enemy_momentum = 0
    enemy_tb = {}
    if enemy:
        dv_base = enemy.get("dv_base")
        if dv_base is None:
            dv_base = enemy.get("stat_block", {}).get("defense", {}).get("dv_base")
        enemy_idf = _get_res(enemy, "idf", enemy.get("idf", 0) if isinstance(enemy, dict) else 0)
        enemy_momentum = _get_res(enemy, "momentum", enemy.get("momentum", 0) if isinstance(enemy, dict) else 0)
        enemy_tb = enemy.get("temp_bonuses", {}) or {}

    forced_defense = pending.get("forced_defense_roll")
    if forced_defense is not None:
        defense_roll = forced_defense
        log["defense_d20"] = None
        log["defense_breakdown"] = {"forced": True}
        log["defense_roll"] = defense_roll
    else:
        if defense_d20 is not None:
            defense_roll = (
                defense_d20
                + enemy_idf
                + enemy_momentum
                + enemy_tb.get("defense", 0)
                + enemy_tb.get("idf", 0)
            )
            log["defense_d20"] = defense_d20
            log["defense_breakdown"] = {
                "defense_d20": defense_d20,
                "idf": enemy_idf,
                "momentum": enemy_momentum,
            }
        else:
            defense_roll = (
                (dv_base if dv_base is not None else 0)
                + enemy_idf
                + enemy_momentum
                + enemy_tb.get("defense", 0)
                + enemy_tb.get("idf", 0)
            )
            log["defense_d20"] = None
            log["defense_breakdown"] = {
                "dv_base": dv_base if dv_base is not None else 0,
                "idf": enemy_idf,
                "momentum": enemy_momentum,
            }

    log["defense_roll"] = defense_roll

    resolved_hit = pending.get("resolved_hit")
    if isinstance(resolved_hit, bool):
        log["forced_resolution"] = True
        log["hit"] = resolved_hit
        margin = defense_roll - to_hit
        if margin >= 5:
            log["perfect_defense"] = True
        if not resolved_hit:
            miss_applied = apply_effect_list(effects.get("on_miss", []), actor=character, enemy=enemy, default_target="self")
            if miss_applied.get("statuses"):
                log["statuses_applied"] = miss_applied["statuses"]
            state.setdefault("log", []).append({"action_effects": log})
            state["pending_action"] = None
            return "miss"
    else:
        margin = defense_roll - to_hit
        if margin >= 5:
            log["perfect_defense"] = True
        if to_hit < defense_roll:
            log["hit"] = False
            # On miss, attacker drifts: Balance +2
            if character.get("_combat_key"):
                combat_add(state, character, "balance", 2)
                log["balance"] = combat_get(state, character, "balance", 0)
            else:
                resources["balance"] = resources.get("balance", 0) + 2
                log["balance"] = resources.get("balance", 0)
            momentum_gained = apply_momentum_feeds(enemy, "player_miss")
            if momentum_gained:
                log["enemy_momentum_gained"] = momentum_gained
                log["enemy_momentum"] = combat_get(state, enemy, "momentum", enemy.get("momentum", 0) if isinstance(enemy, dict) else 0)
            # apply structured on_miss effects
            miss_applied = apply_effect_list(effects.get("on_miss", []), actor=character, enemy=enemy, default_target="self")
            if miss_applied.get("statuses"):
                log["statuses_applied"] = miss_applied["statuses"]
            state.setdefault("log", []).append({"action_effects": log})
            state["pending_action"] = None
            return "miss"
        log["hit"] = True

    # Crit: a hit where to_hit is 5+ above the (modified) defense target.
    try:
        crit_margin = int(to_hit) - int(defense_roll)
        log["crit"] = bool(log.get("hit") is True and crit_margin >= 5)
    except Exception:
        log["crit"] = False

    # Simple damage application to the first enemy, if any
    damage_applied = 0
    if enemies:
        enemy = enemies[0]
        # heat bonus to damage (use projected heat after this hit)
        prior_heat = combat_get(state, character, "heat", resources.get("heat", 0))
        projected_heat = prior_heat + 1
        heat_bonus = max(0, min(4, projected_heat - 1))
        # structured damage support
        dmg_extra_flat = 0
        dmg_effects = effects.get("on_hit", [])
        dmg_entry = next((e for e in dmg_effects if e.get("type") == "damage"), None)
        if dmg_entry and isinstance(dmg_entry, dict):
            dmg_extra_flat = dmg_entry.get("flat", 0) or 0
        dmg_total = ability_damage_total(character, ability, damage_roll) + heat_bonus + dmg_extra_flat
        # Blood Mark 1+: +1 passive damage vs wounded foes (< 50% HP).
        try:
            if _blood_marks() >= 1 and _is_wounded_foe(enemy):
                dmg_total += 1
                log["blood_mark_wounded_bonus"] = 1
        except Exception:
            pass
        # Status shields (starter): Arcane Ward reduces next incoming damage by 1.
        shield_used = 0
        if isinstance(enemy, dict) and enemy.get("_combat_key") and dmg_total > 0:
            if shield_value(state, enemy) > 0:
                shield_used = consume_shield(state, enemy, 1)
                dmg_total = max(0, int(dmg_total) - int(shield_used))
        damage_applied = dmg_total
        hp_now = _get_hp_val(enemy)
        _set_hp_val(enemy, hp_now - dmg_total)
        if isinstance(enemy, dict) and "momentum" in enemy:
            enemy["momentum"] = enemy.get("momentum", 0)
        # gain heat on successful hit
        if character.get("_combat_key"):
            combat_set(state, character, "heat", projected_heat)
        else:
            resources["heat"] = projected_heat
        # apply structured on_hit effects (statuses, resource deltas)
        hit_applied = apply_effect_list(effects.get("on_hit", []), actor=character, enemy=enemy, default_target="enemy")
        if hit_applied.get("statuses"):
            log["statuses_applied"] = hit_applied["statuses"]

        # Blood Mark 2+: +1 RP on crit. If the target is elite, it reacts aggressively.
        try:
            if _blood_marks() >= 2 and log.get("crit") is True:
                rp_gain = 1
                if character.get("_combat_key"):
                    cur_rp = combat_get(state, character, "rp", int(resources.get("resolve", 0) or 0))
                    rp_cap = combat_get(state, character, "rp_cap", int(resources.get("resolve_cap", cur_rp) or cur_rp))
                    new_rp = int(cur_rp) + rp_gain
                    if int(rp_cap or 0) > 0:
                        new_rp = min(int(rp_cap), int(new_rp))
                    combat_set(state, character, "rp", int(new_rp))
                    resources["resolve"] = int(new_rp)
                else:
                    cap = int(resources.get("resolve_cap", resources.get("resolve", 0)) or 0)
                    cur = int(resources.get("resolve", 0) or 0)
                    new_rp = cur + rp_gain
                    if cap > 0:
                        new_rp = min(cap, new_rp)
                    resources["resolve"] = int(new_rp)
                log["blood_mark_crit_rp"] = rp_gain

                elite = False
                try:
                    elite = str(enemy.get("rarity") or "").lower() == "elite"
                    if not elite:
                        elite = "elite" in [str(t).lower() for t in (enemy.get("tags") or [])]
                    if not elite and isinstance(enemy.get("stat_block"), dict):
                        elite = str(enemy["stat_block"].get("rarity") or "").lower() == "elite"
                except Exception:
                    elite = False
                if elite:
                    try:
                        if isinstance(enemy, dict) and enemy.get("_combat_key"):
                            combat_add(state, enemy, "momentum", 1)
                        else:
                            enemy["momentum"] = int(enemy.get("momentum", 0) or 0) + 1
                    except Exception:
                        pass
                    log["elite_reacts_aggressively"] = True
        except Exception:
            pass

    if "momentum" in tags:
        if character.get("_combat_key"):
            combat_add(state, character, "momentum", 1)
        else:
            resources["momentum"] = resources.get("momentum", 0) + 1

    if "heat" in tags:
        if character.get("_combat_key"):
            combat_add(state, character, "heat", 1)
        else:
            resources["heat"] = resources.get("heat", 0) + 1

    # Track Balance changes if tagged
    if "balance_minus_1" in tags:
        if character.get("_combat_key"):
            combat_add(state, character, "balance", -1)
        else:
            resources["balance"] = resources.get("balance", 0) - 1
    if "balance_plus_2" in tags:
        if character.get("_combat_key"):
            combat_add(state, character, "balance", 2)
        else:
            resources["balance"] = resources.get("balance", 0) + 2

    enemy_hp_after = _get_hp_val(enemy) if enemy else None  # if enemy else enemy_hp_before

    log.update({
        "damage_applied": damage_applied,
        "to_hit": to_hit,
        "heat_bonus": heat_bonus if 'heat_bonus' in locals() else 0,
        "shield_used": shield_used if 'shield_used' in locals() else 0,
        "heat": combat_get(state, character, "heat", resources.get("heat", 0)),
        "balance": combat_get(state, character, "balance", resources.get("balance", 0)),
        "resolve": resources.get("resolve", 0),
        "momentum": combat_get(state, character, "momentum", resources.get("momentum", 0)),
     #   "enemy_hp_before": enemy_hp_before,
        "enemy_hp_after": enemy_hp_after,
    })

    log_entry = {"type": "action_resolution", "action_effects": log}

    if state.get("flags", {}).get("narration_enabled") and NARRATOR:
        try:
            narration_input = build_narration_payload(state=state, effects=log)
            narration = NARRATOR.narrate(narration_input, scene_tag="combat")
            log_entry["narration"] = narration
        except Exception as e:
            log_entry["narration"] = None
            log_entry["narration_error"] = str(e)

    state.setdefault("log", []).append(log_entry)
    state["pending_action"] = None
    return "action_applied"


def resolve_defense_reaction(state, defender, attacker, ability, incoming_damage, block_roll=None):
    """
    Resolve a defensive reaction (e.g., Feedback Shield) against incoming damage.
    - Roll (or force) a block amount using ability dice.
    - Apply any remaining damage to defender.
    - If fully blocked, reflect INT (or ability stat) modifier damage to attacker.
    - Grant momentum if tagged.
    Returns a summary dict and logs to state["log"] under "defense_reaction".
    """
    ability = ability or {}
    block = block_roll if block_roll is not None else roll(ability.get("dice", "1d4"))

    remaining = max(0, incoming_damage - block)
    reflected = 0

    stats = defender.get("stats") or defender.get("attributes", {}) if defender else {}
    reflect_stat = ability.get("stat") or "INT"
    if remaining == 0:
        reflected = max(0, stat_mod(stats.get(reflect_stat, 0))) if reflect_stat in stats else 0
        if attacker is not None:
            attacker["hp"] = attacker.get("hp", 0) - reflected

    if defender is not None:
        res = defender.setdefault("resources", {})
        if remaining > 0:
            res["hp"] = max(0, res.get("hp", 0) - remaining)
        if "momentum" in ability.get("tags", []):
            res["momentum"] = res.get("momentum", 0) + 1

    summary = {
        "incoming": incoming_damage,
        "block_roll": block,
        "damage_after_block": remaining,
        "reflected_damage": reflected,
        "defender_hp": defender.get("resources", {}).get("hp") if defender else None,
        "attacker_hp": attacker.get("hp") if attacker is not None else None,
        "momentum_gained": 1 if defender and "momentum" in ability.get("tags", []) else 0,
    }
    state.setdefault("log", []).append({"defense_reaction": summary})
    return summary

def check_exposure(character):
    res = character.get("resources", {}) if isinstance(character, dict) else {}
    heat = res.get("heat", 0)
    if isinstance(character, dict) and character.get("_combat_key"):
        try:
            # state isn't available here; leave legacy path for now.
            pass
        except Exception:
            pass
    if heat >= 5:
        return "overheat"
    if res.get("balance", 0) <= -3:
        return "off_balance"
    return None


def build_narration_payload(*, state, effects):
    """
    Convert engine truth into narration-safe data. Do not infer or invent.
    """
    return {
        "action": effects.get("ability_name"),
        "hit": effects.get("hit"),
        "to_hit": effects.get("to_hit"),
        "defense": effects.get("defense_roll"),
        "damage": effects.get("damage_applied"),
        "enemy_hp_before": effects.get("enemy_hp_before"),
        "enemy_hp_after": effects.get("enemy_hp_after"),
        "statuses_applied": effects.get("statuses_applied", []),
        "player_resources": {
            "resolve": effects.get("resolve"),
            "momentum": effects.get("momentum"),
            "heat": effects.get("heat"),
            "balance": effects.get("balance"),
        },
        "chain_index": effects.get("chain_index"),
        "chain_broken": effects.get("chain_broken", False),
    }


def conditions_met(cond, context):
    if "all" in cond:
        return all(conditions_met(c, context) for c in cond["all"])
    if "any" in cond:
        return any(conditions_met(c, context) for c in cond["any"])
    if "not" in cond:
        return not conditions_met(cond["not"], context)

    # atomic
    t = cond["type"]

    if t == "resource":
        val = context.resources[cond["resource"]]
        return compare(val, cond["op"], cond["value"])

    if t == "status":
        target = context.enemy if cond["target"] == "enemy" else context.self
        return (cond["status"] in target.statuses) == cond["present"]

    if t == "chain_length":
        return compare(context.chain_length, cond["op"], cond["value"])

    if t == "last_action":
        return getattr(context.last_action, cond["field"]) == cond["equals"]

    if t == "hit_result":
        return context.hit_result == cond["value"]
