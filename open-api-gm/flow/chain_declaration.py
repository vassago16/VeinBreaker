# flow/chain_declaration.py


def prompt_chain_declaration(state, character, usable_names):
    print("\nDeclare your chain by number (space or comma separated):")
    pools = character.get("pools", {})
    resources = character.get("resources", {})
    if resources:
        regen_info = state.get("phase", {}).get("resolve_regen")
        if regen_info:
            before, regen, after = regen_info
            res_str = f"Resolve: {resources.get('resolve', 0)}/{resources.get('resolve_cap', resources.get('resolve', 0))} ({before}->+{regen}->{after})"
        else:
            res_str = f"Resolve: {resources.get('resolve', 0)}/{resources.get('resolve_cap', resources.get('resolve', 0))}"
        print(res_str)
    if pools:
        pool_str = ", ".join(f"{k}:{v}" for k, v in pools.items())
        print(f"Pools: {pool_str}")
    print("Usable (off cooldown):")
    ability_lookup = {a.get("name"): a for a in character.get("abilities", [])}
    pool_map = (
        state.get("game_data", {})
        .get("abilities", {})
        .get("poolByPath", {})
    )
    for i, a in enumerate(usable_names, 1):
        ability = ability_lookup.get(a, {})
        effect = ability.get("effect", "")
        cost = ability.get("cost", 0)
        path = ability.get("path", "")
        pool = ability.get("pool") or pool_map.get(path) or ability.get("resource", "resolve")
        path = ability.get("path", "")
        print(f" {i}. {a} [{path}] cost:{cost} pool:{pool} :: {effect}")

    raw = input("> ").replace(",", " ").split()
    picks = []
    for token in raw:
        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(usable_names):
                picks.append(usable_names[idx])
    abilities = picks

    return abilities
