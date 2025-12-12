from engine.validator import validate

def list_available_paths(canon):
    abilities = canon["abilities.json"]["abilities"]
    return sorted(set(a["path"] for a in abilities))

def list_tier_abilities(canon, path, tier):
    abilities = canon["abilities.json"]["abilities"]
    return [a for a in abilities if a["path"] == path and a["tier"] <= tier]

def create_character(canon, path, ability_names):
    abilities = canon["abilities.json"]["abilities"]
    legal_paths = {a["path"] for a in abilities}
    validate(path in legal_paths, "Invalid path")

    tier = 1
    legal_abilities = [
        a for a in abilities
        if a["path"] == path and a["tier"] == tier
    ]
    legal_names = {a["name"] for a in legal_abilities}

    validate(len(ability_names) == 2, "Must choose exactly 2 abilities")
    for name in ability_names:
        validate(name in legal_names, f"Illegal ability: {name}")

    return {
        "path": path,
        "tier": tier,
        "abilities": ability_names,
        "resources": {
            "hp": 10,
            "resolve": 3,
            "momentum": 0,
            "heat": 0,
            "balance": 0
        },
        "marks": {
            "blood": 0,
            "duns": 0
        }
    }
