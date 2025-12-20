from engine.validator import validate
from engine.stats import idf_from_strength


def _resolve_data(canon):
    return canon.get("resolve_abilities.json", {}).get("abilities", [])


def list_available_paths(canon):
    abilities = canon["abilities.json"]["abilities"]
    reserved = {"core", "resolve_basic"}
    return sorted(set(a["path"] for a in abilities if a.get("path") not in reserved))


def list_tier_abilities(canon, path, tier):
    abilities = canon["abilities.json"]["abilities"]
    return [a for a in abilities if a["path"] == path and a["tier"] <= tier]


def list_resolve_basics(canon, include_core=True):
    abilities = _resolve_data(canon)
    if include_core:
        return [a["name"] for a in abilities if a.get("tier") == 0]
    return [a["name"] for a in abilities if a.get("tier") == 0 and not a.get("core", False)]


def list_all_tier_abilities(canon, tier):
    abilities = canon["abilities.json"]["abilities"]
    reserved = {"resolve_basic", "core"}
    return [a for a in abilities if a.get("tier", 0) <= tier and a.get("path") not in reserved]


def build_runtime_ability(ability, pool_map=None):
    pool_map = pool_map or {}
    pool = pool_map.get(ability.get("path"))
    return {
        "name": ability["name"],
        "path": ability.get("path"),
        "tier": ability.get("tier", 0),
        "cooldown": ability.get("cooldown", 0) or 0,
        "base_cooldown": ability.get("base_cooldown", 0) or 0,
        "cost": ability.get("cost", 0),
        "resource": ability.get("resource", "resolve"),
        "pool": pool,
        "dice": ability.get("dice", "1d4"),
        "tags": ability.get("tags", []),
        "effect": ability.get("effect", ""),
        "stat": ability.get("stat"),
        "addStatToAttackRoll": ability.get("addStatToAttackRoll", True),
        "addStatToDamage": ability.get("addStatToDamage", True),
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
    pool_map = canon["abilities.json"].get("poolByPath", {})
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

    resolve_data = _resolve_data(canon)
    resolve_lookup = {a["name"]: a for a in resolve_data}
    validate(resolve_data, "Resolve abilities missing from canon")

    validate(resolve_basic_choice is None or resolve_basic_choice in resolve_lookup, "Invalid resolve ability")

    # Tier 1 picks (can mix paths)
    legal_tier = [a for a in abilities if a.get("tier", 0) <= tier]
    legal_names = {a["name"] for a in legal_tier if a.get("path") not in {"resolve_basic", "core"}}

    validate(len(tier_one_choices) == 2, "Must choose exactly 2 Tier 1 abilities")
    for name in tier_one_choices:
        validate(name in legal_names, f"Illegal ability: {name}")

    # Build runtime abilities with cooldown fields
    runtime_abilities = []
    name_to_ability = {a["name"]: a for a in abilities}

    # auto-add core tier-0 abilities
    core_abilities = [a for a in abilities if a.get("path") == "core" and a.get("tier") == 0]
    for ability in core_abilities:
        runtime_abilities.append(build_runtime_ability(ability, pool_map))

    # selected resolve (skip if duplicate)
    if resolve_basic_choice:
        chosen_resolve = resolve_lookup[resolve_basic_choice]
        if chosen_resolve["name"] not in {a["name"] for a in runtime_abilities}:
            runtime_abilities.append(build_runtime_ability(chosen_resolve, pool_map))

    # tier 1 choices (can mix paths)
    for name in tier_one_choices:
        runtime_abilities.append(build_runtime_ability(name_to_ability[name], pool_map))

    return {
        "path": path,
        "tier": tier,
        "abilities": runtime_abilities,
        "stats": attributes,
        "resources": {
            "hp": 10 + pow_val,
            "resolve": 5,
            "resolve_cap": 5,
            "momentum": 0,
            "heat": 0,
            "balance": 0,
            "idf": idf_from_strength(pow_val),
        },
        "attributes": attributes,
        "pools": pools,
        "marks": {
            "blood": 0,
            "duns": 0
        },
        "chain": {
        "declared": False,
        "abilities": [],
        "resolve_spent": 0,
        "stable": False,
        "invalidated": False
    },
        "veinscore": veinscore,
    }
