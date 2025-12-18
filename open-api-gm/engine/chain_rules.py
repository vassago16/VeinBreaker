from engine.validator import validate


def _safe_validate(condition, message):
    try:
        validate(condition, message)
        return True, ""
    except Exception as e:
        return False, str(e)


def can_declare_chain(state, character):
    return _safe_validate(
        state["phase"]["current"] == "chain_declaration",
        "Chains may only be declared during chain_declaration phase"
    )


def validate_chain_abilities(character, ability_names):
    owned = {a.get("name") for a in character.get("abilities", [])}
    seen = set()

    for name in ability_names:
        ok, msg = _safe_validate(name in owned, f"Ability not owned: {name}")
        if not ok:
            return ok, msg
        ok, msg = _safe_validate(name not in seen, f"Duplicate ability in chain: {name}")
        if not ok:
            return ok, msg
        seen.add(name)
    return True, ""


def validate_chain_cooldowns(character, ability_names):
    cooldowns = {a.get("name"): a.get("cooldown", 0) for a in character.get("abilities", [])}
    for name in ability_names:
        ok, msg = _safe_validate(
            cooldowns.get(name, 0) == 0,
            f"Ability on cooldown: {name}"
        )
        if not ok:
            return ok, msg
    return True, ""


def validate_chain_resolve(character, resolve_spent):
    ok, msg = _safe_validate(
        resolve_spent <= character["resources"]["resolve"],
        "Not enough Resolve to declare chain"
    )
    return ok, msg


def validate_chain_costs(character, abilities):
    total_cost = len(abilities)  # 1 RP per declared action
    pool_spend = {}
    for ability in abilities:
        cost = ability.get("cost", 0) or 0
        resource = ability.get("resource", "resolve")
        pool = ability.get("pool")
        if pool and pool in character.get("pools", {}):
            pool_spend[pool] = pool_spend.get(pool, 0) + cost
        elif resource != "resolve":
            total_cost += cost
    for pool, spend in pool_spend.items():
        if spend > character.get("pools", {}).get(pool, 0):
            return False, f"Not enough {pool} pool to pay for chain"
    if total_cost > character["resources"].get("resolve", 0):
        return False, "Not enough Resolve to pay for chain"
    return True, ""

#call this when any damage is taken
def invalidate_chain(character, reason="damage_taken"):
    if character.get("chain", {}).get("declared"):
        character["chain"]["invalidated"] = True
        character["chain"]["declared"] = False
        character["chain"]["abilities"] = []
        character["chain"]["reason"] = reason

def on_chain_declared(state):
    state["phase"]["current"] = "chain_resolution"

    

def declare_chain(state, character, ability_names, resolve_spent=0, stabilize=False, execute=False):
    """
    Declares a chain. This is the ONLY legal way to do so.
    """

    ok, msg = can_declare_chain(state, character)
    if not ok:
        return False, msg
    ok, msg = validate_chain_abilities(character, ability_names)
    if not ok:
        return False, msg
    ok, msg = validate_chain_cooldowns(character, ability_names)
    if not ok:
        return False, msg
    ok, msg = validate_chain_resolve(character, resolve_spent)
    if not ok:
        return False, msg
    # cost check using ability objects
    abilities = character.get("abilities", [])
    name_to_obj = {a.get("name"): a for a in abilities}
    selected = [name_to_obj[n] for n in ability_names if n in name_to_obj]
    ok, msg = validate_chain_costs(character, selected)
    if not ok:
        return False, msg

    # Spend resolve up front (1 per action + listed resolve costs)
    total_resolve_cost = len(ability_names)  # 1 RP per action (resolve costs handled here)
    character["resources"]["resolve"] = max(0, character["resources"].get("resolve", 0) - total_resolve_cost)

    character["chain"] = {
        "declared": True,
        "abilities": list(ability_names),
        "resolve_spent": total_resolve_cost,
        "invalidated": False,
        "execute": bool(execute),
    }

    return True, character["chain"]
