import random


def pick_enemy(state):
    bestiary = state.get("game_data", {}).get("bestiary", [])
    if not bestiary:
        return None
    # match tier to first party member
    pc = state.get("party", {}).get("members", [None])[0]
    tier = pc.get("tier", 1) if pc else 1
    candidates = [e for e in bestiary if e.get("tier") == tier]
    if not candidates:
        candidates = bestiary
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
    return {
        "id": enemy_def.get("id", "enemy"),
        "name": enemy_def.get("name", "Enemy"),
        "hp": hp,
        "idf": defense.get("idf", 0),
        "momentum": 0,
        "attack_mod": enemy_def.get("attack_mod", 0),
        "tier": enemy_def.get("tier", tier),
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
