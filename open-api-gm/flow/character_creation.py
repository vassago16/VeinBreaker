from engine.character import (
    list_available_paths,
    list_tier_abilities,
    create_character
)

def prompt_choice(options, count=1):
    picks = []
    while len(picks) < count:
        for i, opt in enumerate(options):
            print(f"{i+1}. {opt}")
        choice = int(input("> ")) - 1
        if 0 <= choice < len(options):
            picks.append(options[choice])
    return picks if count > 1 else picks[0]

def run_character_creation(canon, narrator=None):
    paths = list_available_paths(canon)

    if narrator:
        narrator(f"Available paths: {paths}. Choose wisely.")

    print("Choose your Path:")
    path = prompt_choice(paths)

    tier_abilities = list_tier_abilities(canon, path, tier=1)
    names = [a["name"] for a in tier_abilities]

    if narrator:
        narrator(f"Tier 1 abilities for {path}: {names}")

    print("Choose 2 Tier 1 Abilities:")
    chosen = prompt_choice(names, count=2)

    character = create_character(canon, path, chosen)

    if narrator:
        narrator(f"You have created a {path} character with abilities {chosen}.")

    return character
