def allowed_actions(state, phase_machine):
    phase = state["phase"]["current"]
    actions = phase_machine["phases"][phase]["allowedActions"]
    return [a for a in actions if a != "narrate"]

