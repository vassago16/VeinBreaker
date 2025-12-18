# flow/chain_declaration.py


def prompt_chain_declaration(state, character, usable_names, ui):
    ui.system("\nDeclare your chain by number (space or comma separated):")
    pools = character.get("pools", {})
    resources = character.get("resources", {})
    if resources:
        regen_info = state.get("phase", {}).get("resolve_regen")
        if regen_info:
            before, regen, after = regen_info
            res_str = f"Resolve: {resources.get('resolve', 0)}/{resources.get('resolve_cap', resources.get('resolve', 0))} ({before}->+{regen}->{after})"
        else:
            res_str = f"Resolve: {resources.get('resolve', 0)}/{resources.get('resolve_cap', resources.get('resolve', 0))}"
        ui.system(res_str)
    if pools:
        pool_str = ", ".join(f"{k}:{v}" for k, v in pools.items())
        ui.system(f"Pools: {pool_str}")
    ui.system("Usable (off cooldown):")
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
        ui.system(f" {i}. {a} [{path}] cost:{cost} pool:{pool} :: {effect}")

    # Blocking providers can read input immediately; non-blocking emit and wait.
    if getattr(ui, "is_blocking", True):
        raw = ui.text_input("> ").replace(",", " ").split()
        picks = []
        for token in raw:
            if token.isdigit():
                idx = int(token) - 1
                if 0 <= idx < len(usable_names):
                    picks.append(usable_names[idx])
        abilities = picks
        return abilities

    ui.choice(
        "Choose an option:",
        usable_names
    )
    state["awaiting"] = {
        "type": "chain_declaration",
        "options": usable_names
    }
    return None
