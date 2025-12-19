import random


def pick_enemy(state):
    game_data = state.get("game_data", {}) if isinstance(state.get("game_data", {}), dict) else {}
    enemy_by_id = game_data.get("enemy_by_id") if isinstance(game_data, dict) else None
    if isinstance(enemy_by_id, dict) and enemy_by_id:
        bestiary = list(enemy_by_id.values())
    else:
        bestiary = game_data.get("bestiary", [])
    if not bestiary:
        return None
    # match tier to first party member
    pc = state.get("party", {}).get("members", [None])[0]
    tier = pc.get("tier", 1) if pc else 1
    candidates = [e for e in bestiary if e.get("tier") == tier]
    multi_move = [e for e in candidates if len(e.get("moves", [])) > 1]
    if multi_move:
        candidates = multi_move
    if not candidates:
        candidates = bestiary
        multi_move = [e for e in candidates if len(e.get("moves", [])) > 1]
        if multi_move:
            candidates = multi_move
    enemy_def = random.choice(candidates)
    # flatten to runtime enemy
    stat_block = enemy_def.get("stat_block", {}) or {}
    hp = (
        stat_block.get("hp", {}).get("max")
        or stat_block.get("hp")
        or enemy_def.get("hp")
        or 10
    )
    defense = stat_block.get("defense", {}) or {}
    try:
        hp = int(hp or 0)
    except Exception:
        hp = 10
    return {
        "id": enemy_def.get("id", "enemy"),
        "name": enemy_def.get("name", "Enemy"),
        "hp": {"current": hp, "max": hp},
        "dv_base": defense.get("dv_base", 10),
        "idf": defense.get("idf", 0),
        "momentum": 0,
        "attack_mod": enemy_def.get("attack_mod", 0),
        "tier": enemy_def.get("tier", tier),
        "role": enemy_def.get("role"),
        "rarity": enemy_def.get("rarity"),
        "tags": enemy_def.get("tags", []),
        "stat_block": stat_block,
        "damage_profile": stat_block.get("damage_profile", {}) if isinstance(stat_block, dict) else {},
        "moves": enemy_def.get("moves", []),
        "lore": enemy_def.get("lore", {}),
        "archetype_id": enemy_def.get("archetype_id"),
        "resolved_archetype": enemy_def.get("resolved_archetype", {}),
        "definition": enemy_def,
    }


def apply_action(state, action):
    phase = state["phase"]["current"]

    # LOG EVERYTHING
    state["log"].append({
        "phase": phase,
        "action": action
    })

    # OUT OF COMBAT ACTIONS
    if action == "offer_choices":
        # purely narrative, no state change
        return

    if action == "enter_encounter":
        # Ensure an enemy exists; if not, roll a new one
        if not state.get("enemies"):
            enemy = pick_enemy(state)
            if enemy:
                state["enemies"] = [enemy]
        state["phase"]["current"] = "chain_declaration"
        state["phase"]["round"] = 1
        return

    if action == "generate_encounter":
        enemy = pick_enemy(state)
        if enemy:
            state["enemies"] = [enemy]
        return

    if action.startswith("use_ability:"):
        ability_name = action.split(":", 1)[1]
        # find ability on the first party member for now
        member = state.get("party", {}).get("members", [None])[0]
        if not member:
            return
        for ability in member.get("abilities", []):
            if ability.get("name") == ability_name:
                # set cooldown to base_cooldown
                ability["cooldown"] = ability.get("base_cooldown", 0)
                break
