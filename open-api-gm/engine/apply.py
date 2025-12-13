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
        state["phase"]["current"] = "chain_declaration"
        state["phase"]["round"] = 1
        return

    if action == "generate_encounter":
        # stub enemy for now
        state["enemies"] = [{
            "id": "enemy_1",
            "archetype": "stalker",
            "tier": 1,
            "flags": {
                "interruptUsedThisRound": False
            }
        }]
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
