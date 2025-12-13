import json
import os
import argparse
from pathlib import Path
import random
from ai.narrator import narrate
from engine.phases import allowed_actions, tick_cooldowns, list_usable_abilities
from engine.apply import apply_action
from flow.character_creation import run_character_creation
from engine.save_load import save_character, load_character
from flow.chain_declaration import prompt_chain_declaration
from engine.chain_rules import declare_chain
from engine.action_resolution import (
    resolve_action_step,
    apply_action_effects,
    check_exposure,
    roll,
)

def load_canon():
    canon = {}
    canon_dir = Path(__file__).parent / "canon"
    for fname in os.listdir(canon_dir):
        if fname.endswith('.json'):
            with open(canon_dir / fname) as f:
                canon[fname] = json.load(f)
    abilities_path = Path(__file__).parent / "engine" / "abilities.json"
    if abilities_path.exists():
        canon["abilities.json"] = json.loads(abilities_path.read_text(encoding="utf-8"))
    resolve_path = Path(__file__).parent / "engine" / "resolve_abilities.json"
    if resolve_path.exists():
        canon["resolve_abilities.json"] = json.loads(resolve_path.read_text(encoding="utf-8"))
    return canon


def load_game_data():
    root = Path(__file__).parent / "game-data"
    data = {}
    abilities_path = root / "abilities.json"
    if abilities_path.exists():
        data["abilities"] = json.loads(abilities_path.read_text(encoding="utf-8"))
    resolve_path = root / "resolve_abilities.json"
    if resolve_path.exists():
        data["resolve_abilities"] = json.loads(resolve_path.read_text(encoding="utf-8"))
    bestiary = []
    bestiary_path = root / "bestiary.json"
    if bestiary_path.exists():
        try:
            bj = json.loads(bestiary_path.read_text(encoding="utf-8"))
            bestiary.extend(bj.get("enemies", []))
        except Exception:
            pass
    beasts_dir = root / "beasts"
    if beasts_dir.exists():
        for bf in beasts_dir.glob("*.json"):
            try:
                bdata = json.loads(bf.read_text(encoding="utf-8"))
                if isinstance(bdata, dict) and "enemies" in bdata:
                    bestiary.extend(bdata["enemies"])
                elif isinstance(bdata, dict):
                    bestiary.append(bdata)
                elif isinstance(bdata, list):
                    bestiary.extend(bdata)
            except Exception:
                continue
    data["bestiary"] = bestiary
    return data

def initial_state():
    return {
        'phase': {
            'current': 'out_of_combat',
            'round': 0,
            'round_started': False
        },
        'party': {
            'members': [
                {
                    'id': 'pc_1',
                    'resources': {
                        'hp': 10,
                    'resolve': 3,
                    'momentum': 0,
                    'heat': 0,
                    'balance': 0,
                    'idf': 0
                },
                    'chain': {
                        'active': False,
                        'declaredActions': []
                    },
                    'marks': {
                        'blood': 0,
                        'duns': 0
                    },
                    'flags': {
                        'hasInterruptedThisRound': False
                    }
                }
            ]
        },
        'enemies': [],
        'log': []
    }

def get_player_choice(allowed):
    options = allowed + ["exit"]
    print('\n--- YOUR OPTIONS ---')
    for i, a in enumerate(options):
        print(f"{i+1}. {a}")

    while True:
        choice = input('> ').strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx]
        if choice in options:
            return choice
        print('Invalid choice.')

def advance_phase(state, phase_machine, previous_phase):
    if state["phase"]["current"] != previous_phase:
        return  # action already changed phase

    transitions = phase_machine["phases"][previous_phase]["allowedTransitions"]
    if transitions:
        state["phase"]["current"] = transitions[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true", help="Run in automated mode (no prompts).")
    parser.add_argument("--nonarrate", action="store_true", help="Disable narration.")
    parser.add_argument(
        "--interactive-defaults",
        action="store_true",
        help="Interactive mode but default to saved character and narration off without prompting."
    )
    args, _ = parser.parse_known_args()

    canon = load_canon()
    phase_machine = canon['phase_machine.json']
    game_data = load_game_data()

    if args.auto or args.interactive_defaults:
        character = load_character()
    else:
        print("Use saved character? (y/n)")
        use_saved = input("> ").strip().lower().startswith("y")
        if use_saved:
            character = load_character()
        else:
            character = run_character_creation(
                canon,
                narrator=None  # or narrator_stub if you want flavor text
            )
            save_character(character)

    state = initial_state()
    state["party"]["members"][0].update(character)
    state["game_data"] = game_data
    # hydrate abilities from game data (fills effect/pool/etc. for older saves)
    pool_map = game_data.get("abilities", {}).get("poolByPath", {})
    gd_abilities = game_data.get("abilities", {}).get("abilities", [])
    gd_resolve = game_data.get("resolve_abilities", {}).get("abilities", [])
    lookup = {a.get("name"): a for a in gd_abilities + gd_resolve}
    for ability in state["party"]["members"][0].get("abilities", []):
        src = lookup.get(ability.get("name"), {})
        if src:
            for key in ["effect", "cost", "dice", "stat", "tags", "path"]:
                if key not in ability and key in src:
                    ability[key] = src[key]
            if not ability.get("pool"):
                path = ability.get("path") or src.get("path")
                ability["path"] = path
                if path and path in pool_map:
                    ability["pool"] = pool_map[path]

    print('Veinbreaker AI Session Started.\n')

    while True:
        def round_upkeep():
            # decrement cooldowns once per round
            tick_cooldowns(state)
            ch = state["party"]["members"][0]
            res = ch.get("resources", {})
            # resolve regen +2 up to cap
            cap = res.get("resolve_cap", res.get("resolve", 0))
            before = res.get("resolve", 0)
            regen = 2
            res["resolve"] = min(cap, before + regen)
            after = res["resolve"]
            state["phase"]["resolve_regen"] = (before, regen, after)
            # balance reset to 0
            res["balance"] = 0
            # heat reset: if prior heat >=3 set to 2 else 0
            prior_heat = res.get("heat", 0)
            res["heat"] = 2 if prior_heat >= 3 else 0

        # start-of-round upkeep triggered when entering chain_declaration and not yet started
        if state["phase"]["current"] == "chain_declaration" and not state["phase"].get("round_started"):
            state["phase"]["round"] += 1
            round_upkeep()
            state["phase"]["round_started"] = True

        current_phase = state["phase"]["current"]
        if current_phase == "chain_declaration":
            character = state["party"]["members"][0]
            usable = list_usable_abilities(state)
            if not usable:
                print("No usable abilities available (all on cooldown).")
                state["phase"]["current"] = "chain_resolution"
                continue
            abilities = prompt_chain_declaration(state, character, usable)
            ok, resp = declare_chain(
                state,
                character,
                abilities,
                resolve_spent=0,
                stabilize=False
            )
            if not ok:
                print(f"Invalid chain: {resp}")
                continue
            else:
                # set cooldowns for declared abilities
                for ability in character.get("abilities", []):
                    if ability.get("name") in abilities:
                        ability["cooldown"] = ability.get("base_cooldown", 0)
                state["phase"]["current"] = "chain_resolution"
            continue

        if current_phase == "chain_resolution":
            character = state["party"]["members"][0]
            enemies = state.get("enemies", [])
            chain = character.get("chain", {})
            # single attack & defense roll per chain (player & enemy)
            chain_attack_d20 = roll("1d20")
            chain_defense_d20 = roll("1d20")

            for ability_name in chain.get("abilities", []):
                ability = next((a for a in character.get("abilities", []) if a.get("name") == ability_name), None)
                if not ability:
                    continue
                # snapshot resources before action
                res_before = character.get("resources", {}).copy()
                pre_enemy_hp = enemies[0].get("hp", 10) if enemies else None
                pending = resolve_action_step(state, character, ability, attack_roll=chain_attack_d20)
                result = apply_action_effects(state, character, enemies, defense_d20=chain_defense_d20)
                to_hit = pending.get("to_hit") if isinstance(pending, dict) else None
                attack_d20 = pending.get("attack_d20") if isinstance(pending, dict) else None
                damage_roll = pending.get("damage_roll") if isinstance(pending, dict) else None
                dmg = None
                post_enemy_hp = pre_enemy_hp
                if enemies:
                    post_enemy_hp = enemies[0].get("hp", pre_enemy_hp)
                    if pre_enemy_hp is not None and post_enemy_hp is not None:
                        dmg = pre_enemy_hp - post_enemy_hp
                res_after = character.get("resources", {})
                resolve_spent = max(0, res_before.get("resolve", 0) - res_after.get("resolve", 0))
                heat_now = res_after.get("heat", 0)
                balance_now = res_after.get("balance", 0)
                momentum_now = res_after.get("momentum", 0)
                resolve_now = res_after.get("resolve", 0)
                defense_d20 = None
                defense_roll = None
                if isinstance(state.get("log"), list) and state["log"]:
                    last = state["log"][-1]
                    if isinstance(last, dict) and "action_effects" in last:
                        aelog = last["action_effects"]
                        defense_d20 = aelog.get("defense_d20")
                        defense_roll = aelog.get("defense_roll")
                if defense_d20 is None:
                    defense_d20 = chain_defense_d20
                if defense_roll is None and defense_d20 is not None:
                    defense_roll = defense_d20 + enemies[0].get("momentum", 0) + enemies[0].get("idf", 0) if enemies else None

                print(
                    f"Resolved {ability_name}: to_hit={to_hit}, dmg_roll={damage_roll}, "
                    f"result={result}, damage={dmg}, enemy_hp={post_enemy_hp}, "
                    f"resolve_spent={resolve_spent}, resolve_now={resolve_now}, "
                    f"heat={heat_now}, balance={balance_now}, momentum={momentum_now}, "
                    f"attack_d20={attack_d20}, defense_d20={defense_d20}, defense_total={defense_roll}"
                )
                result = check_exposure(character)
                if result:
                    state["log"].append({"exposure": result})
            # simple enemy turn if alive
            if enemies:
                enemy_hp = enemies[0].get("hp", 0)
                if enemy_hp > 0:
                    enemy_to_hit = roll("1d20") + enemies[0].get("attack_mod", 0)
                    player_def = roll("1d20") + character["resources"].get("idf", 0) + character["resources"].get("momentum", 0)
                    if enemy_to_hit > player_def:
                        counter_dmg = roll("1d6")
                        character["resources"]["hp"] = max(0, character["resources"].get("hp", 0) - counter_dmg)
                        print(f"Enemy counterattacks: to_hit={enemy_to_hit}, def={player_def}, dmg={counter_dmg}. PC HP now {character['resources']['hp']}.")
                    else:
                        print(f"Enemy counterattack misses: to_hit={enemy_to_hit}, def={player_def}.")
            # check end conditions and loop combat
            if enemies and enemies[0].get("hp", 0) <= 0:
                print("Enemy defeated.")
                enemies.clear()
                state["phase"]["current"] = "out_of_combat"
            elif character["resources"].get("hp", 0) <= 0:
                print("PC defeated.")
                state["phase"]["current"] = "out_of_combat"
            else:
                state["phase"]["current"] = "chain_declaration"
                state["phase"]["round_started"] = False
            # heat resets when chain ends
            character["resources"]["heat"] = 0
            continue

        actions = allowed_actions(state, phase_machine)

        if not (args.nonarrate or args.interactive_defaults):
            try:
                narrate(state, actions)
            except Exception as e:
                print(f"[Narrator error: {e}]")
        else:
            print("\n(Narration suppressed)")

        if args.auto:
            choice = actions[0] if actions else "exit"
            print(f"Auto choice: {choice}")
        else:
            choice = get_player_choice(actions)
        if choice == "exit":
            print("Exiting Veinbreaker AI session.")
            break
        prev_phase = state["phase"]["current"]
        apply_action(state, choice)
        if choice in ("enter_encounter", "generate_encounter"):
            if state.get("enemies"):
                enemy = state["enemies"][0]
                print(f"Encounter: {enemy.get('name', 'Enemy')} (HP: {enemy.get('hp', '?')})")
        advance_phase(state, phase_machine, prev_phase)


if __name__ == '__main__':
    main()
