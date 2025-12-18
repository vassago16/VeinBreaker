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


def prompt_choice(ui, options, count=1, show_desc=None):
    picks = []
    while len(picks) < count:
        lines = []
        for i, opt in enumerate(options):
            desc = f" - {show_desc[opt]}" if show_desc and opt in show_desc else ""
            lines.append(f"{i+1}. {opt}{desc}")
        for line in lines:
            ui.system(line)
        choice = ui.text_input("> ")
        try:
            idx = int(choice) - 1
        except ValueError:
            ui.error("Invalid choice.")
            continue
        if 0 <= idx < len(options):
            picks.append(options[idx])
        else:
            ui.error("Invalid choice.")
    return picks if count > 1 else picks[0]


def prompt_attributes(ui, total_points=18, base=8, max_val=14):
    attrs = {"POW": base, "AGI": base, "MND": base, "SPR": base}
    remaining = total_points
    ui.system(f"Assign attributes (POW/AGI/MND/SPR). Base {base} each. Distribute {total_points} points (max {max_val}).")
    for key in attrs.keys():
        while True:
            try:
                val = int(ui.text_input(f"Add points to {key} (remaining {remaining}): ").strip())
            except ValueError:
                ui.error("Enter a number.")
                continue
            if val < 0 or val > remaining or attrs[key] + val > max_val:
                ui.error(f"Invalid. Cannot exceed remaining {remaining} or max {max_val}.")
                continue
            attrs[key] += val
            remaining -= val
            break
    if remaining > 0:
        ui.system(f"Unspent points ({remaining}) retained as Veinscore.")
    ui.system(f"Attributes set: {attrs}")
    return attrs, remaining


def run_character_creation(canon, narrator=None, ui=None):
    paths = list_available_paths(canon)
    pool_map = canon["abilities.json"].get("poolByPath", {})

    if narrator:
        narrator(f"Available paths: {paths}. Choose wisely.")

    attributes, veinscore = prompt_attributes(ui)

    ui.system("Choose your Path:")
    path = prompt_choice(ui, paths, show_desc=PATH_SUMMARIES)

    tier = 1
    resolve_data = canon.get("resolve_abilities.json", {}).get("abilities", [])
    resolve_options = [a for a in resolve_data if a.get("tier") == 0]
    resolve_pick = None
    if resolve_options:
        ui.system("Choose 1 Resolve Basic (you automatically gain the 4 core Tier-0 resolves):")
        resolve_pick = prompt_ability_choice(ui, resolve_options)
    else:
        ui.system("No resolve basics available; core Tier-0 resolves granted automatically.")

    tier_abilities = list_all_tier_abilities(canon, tier=tier)
    for a in tier_abilities:
        if "pool" not in a:
            a["pool"] = pool_map.get(a.get("path"))
    if narrator:
        narrator(f"Tier {tier} abilities (all paths): {[a['name'] for a in tier_abilities]}")

    ui.system("Choose 2 Tier 1 Abilities (paths can mix):")
    chosen = prompt_ability_choice(ui, tier_abilities, count=2)

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
def prompt_ability_choice(ui, abilities, count=1):
    picks = []
    while len(picks) < count:
        for i, ability in enumerate(abilities):
            path = ability.get("path", "")
            cost = ability.get("cost", 0)
            pool = ability.get("pool", "resolve")
            effect = ability.get("effect", "")
            ui.system(f"{i+1}. {ability['name']} [{path}] cost:{cost} pool:{pool} :: {effect}")
        try:
            choice = int(ui.text_input("> ")) - 1
        except ValueError:
            ui.error("Invalid choice.")
            continue
        if 0 <= choice < len(abilities):
            picks.append(abilities[choice]["name"])
        else:
            ui.error("Invalid choice.")
    return picks if count > 1 else picks[0]
