def list_usable_abilities(state):
    usable = []
    member = state.get("party", {}).get("members", [None])[0]
    if not member:
        return usable
    for ability in member.get("abilities", []):
        if ability.get("cooldown", 0) == 0:
            usable.append(ability.get("name"))
    return usable


def allowed_actions(state, phase_machine):
    phase = state["phase"]["current"]
    actions = phase_machine["phases"][phase]["allowedActions"]
    # For chain_declaration, build a list of usable abilities
    if phase == "chain_declaration":
        usable = list_usable_abilities(state)
        return [f"use_ability:{a}" for a in usable] + [a for a in actions if a != "narrate"]
    return [a for a in actions if a != "narrate"]

def tick_cooldowns(state):
    for member in state.get("party", {}).get("members", []):
        for ability in member.get("abilities", []):
            cd = ability.get("cooldown", 0)
            if cd > 0:
                ability["cooldown"] = max(0, cd - 1)
