import json
import os
import argparse
from pathlib import Path
import random
from copy import deepcopy
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
from engine.interrupt_controller import InterruptController, apply_interrupt

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

def deep_merge(base, overlay):
    """Recursively merge overlay into a deepcopy of base (lists are replaced)."""
    if isinstance(base, dict) and isinstance(overlay, dict):
        merged = deepcopy(base)
        for key, val in overlay.items():
            merged[key] = deep_merge(merged[key], val) if key in merged else deepcopy(val)
        return merged
    # For lists or scalars, overlay replaces base
    return deepcopy(overlay)


def format_enemy_preview(enemy):
    """Pretty-print an enemy for quick verification in the CLI."""
    stat_block = enemy.get("stat_block") or {}
    defense = stat_block.get("defense", {}) if isinstance(stat_block, dict) else {}
    dmg_profile = stat_block.get("damage_profile", {}) if isinstance(stat_block, dict) else {}
    name = enemy.get("name", enemy.get("id", "Enemy"))
    tier = enemy.get("tier", "?")
    role = enemy.get("role", "?")
    rarity = enemy.get("rarity", "?")
    tags = ", ".join(enemy.get("tags", []))
    hp = enemy.get("hp", stat_block.get("hp", {}).get("max") if isinstance(stat_block, dict) else "?")
    dv = enemy.get("dv_base", defense.get("dv_base", "?"))
    idf = enemy.get("idf", defense.get("idf", 0))

    def fmt_dmg(dmg):
        if not isinstance(dmg, dict):
            return "n/a"
        dice = dmg.get("dice", "?")
        flat = dmg.get("flat")
        flat_str = f"{flat:+}" if isinstance(flat, (int, float)) else ""
        return f"{dice}{flat_str}"

    baseline = fmt_dmg(dmg_profile.get("baseline", {}))
    spike = fmt_dmg(dmg_profile.get("spike", {})) if dmg_profile.get("spike") else None

    def fmt_effects(effects):
        rendered = []
        for eff in effects or []:
            if isinstance(eff, str):
                rendered.append(eff)
            elif isinstance(eff, dict):
                rendered.append(eff.get("type", str(eff)))
            else:
                rendered.append(str(eff))
        return ", ".join(rendered) if rendered else "none"

    def fmt_cond(cond):
        if not isinstance(cond, dict):
            return ""
        parts = []
        for k, v in cond.items():
            parts.append(f"{k}={v}")
        return ", ".join(parts)

    resolved = enemy.get("resolved_archetype", {}) or {}
    archetype_id = enemy.get("archetype_id", "")
    interrupt_windows = resolved.get("rhythm_profile", {}).get("interrupt", {}).get("windows", [])

    lines = []
    lines.append(f"Encounter: {name} (Tier {tier} / {role} / {rarity})")
    lines.append(f"Stats: HP {hp}, DV {dv}, IDF {idf}")
    dmg_line = f"Damage: baseline {baseline}"
    if spike:
        dmg_line += f", spike {spike}"
    lines.append(dmg_line)
    if tags:
        lines.append(f"Tags: {tags}")
    if archetype_id:
        lines.append(f"Archetype: {archetype_id}")
    if interrupt_windows:
        win_summaries = []
        for w in interrupt_windows:
            idxs = w.get("after_action_index", [])
            trig = fmt_cond(w.get("trigger_if", {}))
            weight = w.get("weight")
            summary = f"after {idxs}"
            if trig:
                summary += f" if {trig}"
            if weight is not None:
                summary += f" (w={weight})"
            win_summaries.append(summary)
        lines.append(f"Interrupt windows: { '; '.join(win_summaries) }")

    moves = enemy.get("moves", [])
    if moves:
        lines.append("Moves:")
        for mv in moves:
            mv_name = mv.get("name", mv.get("id", "move"))
            mv_type = mv.get("type", "")
            rp = mv.get("cost", {}).get("rp")
            cd = mv.get("cooldown", 0)
            on_hit = mv.get("on_hit", {})
            dmg_ref = on_hit.get("damage")
            dmg_str = dmg_ref if isinstance(dmg_ref, str) else fmt_dmg(dmg_ref) if isinstance(dmg_ref, dict) else "n/a"
            effects_str = fmt_effects(on_hit.get("effects"))
            lines.append(f"- {mv_name} ({mv_type}) RP {rp} CD {cd} dmg {dmg_str} effects: {effects_str}")
            if mv.get("on_miss", {}).get("notes"):
                lines.append(f"  - On miss: {mv['on_miss']['notes']}")
            if mv.get("card_text"):
                lines.append(f"  - Text: {mv['card_text']}")

    return "\n".join(lines)


def load_game_data():
    root = Path(__file__).parent / "game-data"
    data = {}
    archetypes = {}
    archetypes_path = Path(__file__).parent / "canon" / "enemy_archetypes.json"
    if archetypes_path.exists():
        try:
            arc_data = json.loads(archetypes_path.read_text(encoding="utf-8"))
            for arc in arc_data.get("archetypes", []):
                aid = arc.get("id")
                defaults = arc.get("defaults", {})
                if not aid:
                    continue
                archetypes[aid] = defaults
                if aid.startswith("archetype."):
                    archetypes[aid.replace("archetype.", "", 1)] = defaults
        except Exception:
            archetypes = {}
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
    def resolve_enemy_archetype(enemy):
        aid = enemy.get("archetype_id")
        if not aid:
            return enemy
        defaults = archetypes.get(aid) or archetypes.get(aid.replace("archetype.", "", 1)) if isinstance(aid, str) else None
        if not defaults:
            return enemy
        merged = deep_merge(defaults, enemy.get("resolved_archetype", {}))
        overrides = enemy.get("overrides")
        if isinstance(overrides, dict):
            merged = deep_merge(merged, overrides)
        enemy["resolved_archetype"] = merged
        return enemy

    data["archetypes"] = archetypes
    data["bestiary"] = [resolve_enemy_archetype(e) for e in bestiary]
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
            # momentum resets each turn
            res["momentum"] = 0
            # heat reset: if prior heat >=3 set to 2 else 0
            prior_heat = res.get("heat", 0)
            res["heat"] = 2 if prior_heat >= 3 else 0
            # reset enemy interrupt budgets each round
            for en in state.get("enemies", []):
                en["interrupts_used"] = 0

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
            ic = InterruptController(enemies[0] if enemies else {})
            print(f"Chain contests: player d20={chain_attack_d20} vs enemy DV d20={chain_defense_d20}")

            for idx, ability_name in enumerate(chain.get("abilities", [])):
                ability = next((a for a in character.get("abilities", []) if a.get("name") == ability_name), None)
                if not ability:
                    continue
                # snapshot resources before action
                res_before = character.get("resources", {}).copy()
                pre_enemy_hp = enemies[0].get("hp", 10) if enemies else None
                balance_bonus = 0 if idx == 0 else character.get("resources", {}).get("balance", 0)
                pending = resolve_action_step(state, character, ability, attack_roll=chain_attack_d20, balance_bonus=balance_bonus)
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
                # Interrupt window after first action in chain
                if enemies and len(enemies) > 0 and ic.should_interrupt(state, idx):
                    hit, dmg, rolls = apply_interrupt(state, character, enemies[0])
                    atk_mod = enemies[0].get("attack_mod", 0)
                    def_mod = character["resources"].get("idf", 0) + character["resources"].get("momentum", 0)
                    print(f"Interrupt contest: enemy ({rolls['atk_d20']}+{atk_mod}={rolls['atk_total']}) vs player ({rolls['def_d20']}+{def_mod}={rolls['def_total']})")
                    if hit and dmg > 0:
                        print(f"Enemy INTERRUPT hits for {dmg} dmg. Chain broken.")
                        break
                    elif hit and rolls["atk_total"] - rolls["def_total"] >= 5:
                        print("Enemy INTERRUPT breaks the chain (MoD>=5).")
                        break
                    else:
                        print("Enemy interrupt fails.")
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
            # heat resets when chain ends (unless carried via stabilize rule above; we already set on round start)
            character["resources"]["heat"] = character["resources"].get("heat", 0) if character["resources"].get("heat", 0) <= 2 else 0
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
                print(format_enemy_preview(enemy))
        advance_phase(state, phase_machine, prev_phase)


if __name__ == '__main__':
    main()
