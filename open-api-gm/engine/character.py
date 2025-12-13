from engine.validator import validate


def list_available_paths(canon):
    abilities = canon["abilities.json"]["abilities"]
    return sorted(set(a["path"] for a in abilities))


def list_tier_abilities(canon, path, tier):
    abilities = canon["abilities.json"]["abilities"]
    return [a for a in abilities if a["path"] == path and a["tier"] <= tier]


def list_resolve_basics(canon):
    abilities = canon["abilities.json"]["abilities"]
    return [a["name"] for a in abilities if a.get("path") == "resolve_basic" and a.get("tier") == 0]


def list_all_tier_abilities(canon, tier):
    abilities = canon["abilities.json"]["abilities"]
    return [a for a in abilities if a.get("tier", 0) <= tier and a.get("path") != "resolve_basic"]


def build_runtime_ability(ability):
    return {
        "name": ability["name"],
        "path": ability.get("path"),
        "tier": ability.get("tier", 0),
        "cooldown": ability.get("cooldown", 0) or 0,
        "base_cooldown": ability.get("cooldown", 0) or 0,
    }


def create_character(
    canon,
    path,
    tier_one_choices,
    tier=1,
    resolve_basic_choice=None,
    attributes=None,
    veinscore=0,
):
    abilities = canon["abilities.json"]["abilities"]
    legal_paths = {a["path"] for a in abilities}
    validate(path in legal_paths, "Invalid path")

    # Attributes: POW/AGI/MND/SPR; default starting spread if none provided
    if attributes is None:
        attributes = {"POW": 8, "AGI": 8, "MND": 8, "SPR": 8}
    required_keys = {"POW", "AGI", "MND", "SPR"}
    validate(required_keys.issubset(attributes.keys()), "Missing attributes")

    pow_val = attributes["POW"]
    agi_val = attributes["AGI"]
    mnd_val = attributes["MND"]
    spr_val = attributes["SPR"]

    # Pools derived from attributes (rounded down)
    pools = {
        "martial": pow_val // 2,
        "shadow": agi_val // 2,
        "magic": mnd_val // 2,
        "faith": spr_val // 2,
    }

    # Resolve basic pick
    resolve_basics = list_resolve_basics(canon)
    validate(resolve_basic_choice in resolve_basics, "Must choose one resolve_basic ability")

    # Tier 1 picks (can mix paths)
    legal_tier = [a for a in abilities if a.get("tier", 0) <= tier and a.get("path") != "resolve_basic"]
    legal_names = {a["name"] for a in legal_tier}

    validate(len(tier_one_choices) == 2, "Must choose exactly 2 Tier 1 abilities")
    for name in tier_one_choices:
        validate(name in legal_names, f"Illegal ability: {name}")

    # Build runtime abilities with cooldown fields
    runtime_abilities = []
    name_to_ability = {a["name"]: a for a in abilities}

    # resolve basic
    runtime_abilities.append(build_runtime_ability(name_to_ability[resolve_basic_choice]))
    # tier 1 choices (can mix paths)
    for name in tier_one_choices:
        runtime_abilities.append(build_runtime_ability(name_to_ability[name]))

    return {
        "path": path,
        "tier": tier,
        "abilities": runtime_abilities,
        "resources": {
            "hp": 10 + pow_val,
            "resolve": 5,
            "resolve_cap": 5,
            "momentum": 0,
            "heat": 0,
            "balance": 0
        },
        "attributes": attributes,
        "pools": pools,
        "marks": {
            "blood": 0,
            "duns": 0
        },
        "veinscore": veinscore,
    }
