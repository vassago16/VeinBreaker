from engine.validator import validate


def can_declare_chain(state, character):
    validate(
        state["phase"]["current"] == "chain_declaration",
        "Chains may only be declared during chain_declaration phase"
    )


def validate_chain_abilities(character, ability_names):
    owned = {a.get("name") for a in character.get("abilities", [])}
    seen = set()

    for name in ability_names:
        validate(name in owned, f"Ability not owned: {name}")
        validate(name not in seen, f"Duplicate ability in chain: {name}")
        seen.add(name)


def validate_chain_cooldowns(character, ability_names):
    cooldowns = {a.get("name"): a.get("cooldown", 0) for a in character.get("abilities", [])}
    for name in ability_names:
        validate(
            cooldowns.get(name, 0) == 0,
            f"Ability on cooldown: {name}"
        )


def validate_chain_resolve(character, resolve_spent):
    validate(
        resolve_spent <= character["resources"]["resolve"],
        "Not enough Resolve to declare chain"
    )

#call this when any damage is taken
def invalidate_chain(character, reason="damage_taken"):
    if character.get("chain", {}).get("declared"):
        character["chain"]["invalidated"] = True
        character["chain"]["declared"] = False
        character["chain"]["abilities"] = []
        character["chain"]["reason"] = reason

def on_chain_declared(state):
    state["phase"]["current"] = "chain_resolution"

    

def declare_chain(state, character, ability_names, resolve_spent=0, stabilize=False):
    """
    Declares a chain. This is the ONLY legal way to do so.
    """

    can_declare_chain(state, character)
    validate_chain_abilities(character, ability_names)
    validate_chain_cooldowns(character, ability_names)
    validate_chain_resolve(character, resolve_spent)

    character["chain"] = {
        "declared": True,
        "abilities": list(ability_names),
        "resolve_spent": resolve_spent,
        "invalidated": False
    }

    return character["chain"]
