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
