# flow/chain_declaration.py


def prompt_chain_declaration(character, usable_names):
    print("\nDeclare your chain by number (space or comma separated):")
    print("Usable (off cooldown):")
    for i, a in enumerate(usable_names, 1):
        print(f" {i}. {a}")

    raw = input("> ").replace(",", " ").split()
    picks = []
    for token in raw:
        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(usable_names):
                picks.append(usable_names[idx])
    abilities = picks

    return abilities
