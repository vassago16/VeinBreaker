import random
from engine.stats import stat_mod


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
    die_total = base_d20 if base_d20 is not None else roll("1d20")
    add_stat = ability.get("addStatToAttackRoll", True)
    stat_key = ability.get("stat")
    stats = character.get("stats") or character.get("attributes", {})
    if add_stat and stat_key and stat_key in stats:
        return die_total + stat_mod(stats[stat_key]), die_total
    return die_total, die_total


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


def resolve_action_step(state, character, ability, attack_roll=None, balance_bonus=0):
    """
    Pay costs and roll dice; do not apply effects yet.
    """
    cost = ability.get("cost", 0)
    resource = ability.get("resource", "resolve")
    pool = ability.get("pool")
    if cost:
        if pool and pool in character.get("pools", {}):
            character["pools"][pool] = max(0, character["pools"][pool] - cost)
        elif resource != "resolve" and resource in character.get("resources", {}):
            character["resources"][resource] = max(
                0, character["resources"][resource] - cost
            )

    attack_total, d20_roll = ability_attack_roll(character, ability, base_d20=attack_roll)
    to_hit = attack_total + balance_bonus
    damage_roll = roll(ability.get("dice", "1d4"))

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

    ability = pending.get("ability_obj", {}) or {}
    damage_roll = pending.get("damage_roll", 0)
    to_hit = pending.get("to_hit", 0)
    tags = pending.get("tags", [])
    log = pending.get("log", {})

    # Defense roll: use static DV from data (no contested d20 for enemies)
    enemy = enemies[0] if enemies else None
    dv_base = None
    enemy_idf = 0
    enemy_momentum = 0
    if enemy:
        dv_base = enemy.get("dv_base")
        if dv_base is None:
            dv_base = enemy.get("stat_block", {}).get("defense", {}).get("dv_base")
        enemy_idf = enemy.get("idf", 0)
        enemy_momentum = enemy.get("momentum", 0)
    defense_roll = (dv_base if dv_base is not None else 0) + enemy_idf + enemy_momentum
    log["defense_roll"] = defense_roll
    log["defense_d20"] = None  # static DV (no roll)
    log["defense_breakdown"] = {
        "dv_base": dv_base if dv_base is not None else 0,
        "idf": enemy_idf,
        "momentum": enemy_momentum,
    }

    margin = defense_roll - to_hit
    if margin >= 5:
        log["perfect_defense"] = True
    if to_hit < defense_roll:
        log["hit"] = False
        # On miss, attacker drifts: Balance +2
        character["resources"]["balance"] = character["resources"].get("balance", 0) + 2
        log["balance"] = character["resources"].get("balance", 0)
        momentum_gained = apply_momentum_feeds(enemy, "player_miss")
        if momentum_gained:
            log["enemy_momentum_gained"] = momentum_gained
            log["enemy_momentum"] = enemy.get("momentum", 0)
        state.setdefault("log", []).append({"action_effects": log})
        state["pending_action"] = None
        return "miss"
    log["hit"] = True

    # Simple damage application to the first enemy, if any
    damage_applied = 0
    if enemies:
        enemy = enemies[0]
        # heat bonus to damage (use projected heat after this hit)
        prior_heat = character["resources"].get("heat", 0)
        projected_heat = prior_heat + 1
        heat_bonus = max(0, min(4, projected_heat - 1))
        dmg_total = ability_damage_total(character, ability, damage_roll) + heat_bonus
        damage_applied = dmg_total
        enemy["hp"] = enemy.get("hp", 10) - dmg_total
        enemy["momentum"] = enemy.get("momentum", 0)
        # gain heat on successful hit
        character["resources"]["heat"] = projected_heat

    if "momentum" in tags:
        character["resources"]["momentum"] = character["resources"].get("momentum", 0) + 1

    if "heat" in tags:
        character["resources"]["heat"] = character["resources"].get("heat", 0) + 1

    # Track Balance changes if tagged
    if "balance_minus_1" in tags:
        character["resources"]["balance"] = character["resources"].get("balance", 0) - 1
    if "balance_plus_2" in tags:
        character["resources"]["balance"] = character["resources"].get("balance", 0) + 2

    log.update({
        "damage_applied": damage_applied,
        "to_hit": to_hit,
        "heat_bonus": heat_bonus if 'heat_bonus' in locals() else 0,
        "heat": character["resources"].get("heat", 0),
        "balance": character["resources"].get("balance", 0),
        "resolve": character["resources"].get("resolve", 0),
        "momentum": character["resources"].get("momentum", 0),
    })
    state.setdefault("log", []).append({"action_effects": log})
    state["pending_action"] = None
    return "action_applied"


def check_exposure(character):
    if character["resources"].get("heat", 0) >= 5:
        return "overheat"
    if character["resources"].get("balance", 0) <= -3:
        return "off_balance"
    return None
