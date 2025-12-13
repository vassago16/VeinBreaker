from engine.character import (
    list_available_paths,
    list_tier_abilities,
    create_character,
    list_resolve_basics,
    list_all_tier_abilities,
)

PATH_SUMMARIES = {
    "stonepulse": "Martial/stone: rhythm, stance, balance control.",
    "canticle": "Faith/radiance: hymns, radiant strikes, defense.",
    "hemocratic": "Shadow/blood: bleed, precision, evasion.",
    "spellforged": "Magic/arcanum: charged spells and wards.",
}


def prompt_choice(options, count=1, show_desc=None):
    picks = []
    while len(picks) < count:
        for i, opt in enumerate(options):
            desc = f" - {show_desc[opt]}" if show_desc and opt in show_desc else ""
            print(f"{i+1}. {opt}{desc}")
        choice = int(input("> ")) - 1
        if 0 <= choice < len(options):
            picks.append(options[choice])
        else:
            print("Invalid choice.")
    return picks if count > 1 else picks[0]


def prompt_attributes(total_points=18, base=8, max_val=14):
    attrs = {"POW": base, "AGI": base, "MND": base, "SPR": base}
    remaining = total_points
    print(f"Assign attributes (POW/AGI/MND/SPR). Base {base} each. Distribute {total_points} points (max {max_val}).")
    for key in attrs.keys():
        while True:
            try:
                val = int(input(f"Add points to {key} (remaining {remaining}): ").strip())
            except ValueError:
                print("Enter a number.")
                continue
            if val < 0 or val > remaining or attrs[key] + val > max_val:
                print(f"Invalid. Cannot exceed remaining {remaining} or max {max_val}.")
                continue
            attrs[key] += val
            remaining -= val
            break
    if remaining > 0:
        print(f"Unspent points ({remaining}) retained as Veinscore.")
    print(f"Attributes set: {attrs}")
    return attrs, remaining


def run_character_creation(canon, narrator=None):
    paths = list_available_paths(canon)
    pool_map = canon["abilities.json"].get("poolByPath", {})

    if narrator:
        narrator(f"Available paths: {paths}. Choose wisely.")

    attributes, veinscore = prompt_attributes()

    print("Choose your Path:")
    path = prompt_choice(paths, show_desc=PATH_SUMMARIES)

    tier = 1
    resolve_data = canon.get("resolve_abilities.json", {}).get("abilities", [])
    resolve_options = [a for a in resolve_data if a.get("tier") == 0]
    resolve_pick = None
    if resolve_options:
        print("Choose 1 Resolve Basic (you automatically gain the 4 core Tier-0 resolves):")
        resolve_pick = prompt_ability_choice(resolve_options)
    else:
        print("No resolve basics available; core Tier-0 resolves granted automatically.")

    tier_abilities = list_all_tier_abilities(canon, tier=tier)
    for a in tier_abilities:
        if "pool" not in a:
            a["pool"] = pool_map.get(a.get("path"))
    if narrator:
        narrator(f"Tier {tier} abilities (all paths): {[a['name'] for a in tier_abilities]}")

    print("Choose 2 Tier 1 Abilities (paths can mix):")
    chosen = prompt_ability_choice(tier_abilities, count=2)

    character = create_character(
        canon,
        path,
        chosen,
        tier=tier,
        resolve_basic_choice=resolve_pick,
        attributes=attributes,
        veinscore=veinscore,
    )

    if narrator:
        narrator(f"You have created a {path} character with resolve basic {resolve_pick} and abilities {chosen}.")

    return character
def prompt_ability_choice(abilities, count=1):
    picks = []
    while len(picks) < count:
        for i, ability in enumerate(abilities):
            path = ability.get("path", "")
            cost = ability.get("cost", 0)
            pool = ability.get("pool", "resolve")
            effect = ability.get("effect", "")
            print(f"{i+1}. {ability['name']} [{path}] cost:{cost} pool:{pool} :: {effect}")
        choice = int(input("> ")) - 1
        if 0 <= choice < len(abilities):
            picks.append(abilities[choice]["name"])
        else:
            print("Invalid choice.")
    return picks if count > 1 else picks[0]
