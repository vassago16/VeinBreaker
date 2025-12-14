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
    apply_effect_list,
)
from engine.interrupt_controller import InterruptController, apply_interrupt
from engine.status import apply_status_effects, tick_statuses

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

BUFF_TYPES = {
    "radiance",
    "quickened",
    "invisibility",
    "intangible",
    "defense up",
    "attack up",
    "idf up",
    "retaliate",
}

DEBUFF_TYPES = {
    "bleed",
    "radiant burn",
    "vulnerable",
    "primed",
    "telegraph",
    "stagger",
    "slowed",
    "distracted",
    "exhausted",
}


def format_status_summary(entity):
    statuses = entity.get("statuses", {}) or {}
    buffs = []
    debuffs = []
    neutrals = []
    for name, data in statuses.items():
        entry = name
        stacks = data.get("stacks")
        duration = data.get("duration")
        parts = []
        if stacks is not None:
            parts.append(f"{stacks}")
        if duration is not None:
            parts.append(f"{duration}r")
        if parts:
            entry = f"{name}({'/'.join(parts)})"
        lname = name.lower()
        if lname in BUFF_TYPES:
            buffs.append(entry)
        elif lname in DEBUFF_TYPES:
            debuffs.append(entry)
        else:
            neutrals.append(entry)
    buff_str = ", ".join(buffs) if buffs else "none"
    debuff_str = ", ".join(debuffs) if debuffs else "none"
    neutral_str = ", ".join(neutrals) if neutrals else "none"
    return f"Status:{neutral_str} Buff:{buff_str} Debuff:{debuff_str}"


def format_enemy_state(enemy):
    if not enemy:
        return ""
    hp = enemy.get("hp", "?")
    hp_max = enemy.get("hp_max") or enemy.get("stat_block", {}).get("hp", {}).get("max")
    rp = enemy.get("rp", enemy.get("rp_pool"))
    momentum = enemy.get("momentum", 0)
    statuses = enemy.get("statuses", {}) or {}
    if statuses:
        status_parts = []
        for name, data in statuses.items():
            stacks = data.get("stacks")
            dur = data.get("duration")
            part = name
            bits = []
            if stacks is not None:
                bits.append(str(stacks))
            if dur is not None:
                bits.append(f"{dur}r")
            if bits:
                part += f"({','.join(bits)})"
            status_parts.append(part)
        status_str = ", ".join(status_parts)
    else:
        status_str = "none"
    return f"[Enemy] HP {hp}/{hp_max or '?'} | RP {rp} | Momentum {momentum} | Status {status_str}"


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
    loot_path = root / "loot.json"
    if loot_path.exists():
        try:
            data["loot"] = json.loads(loot_path.read_text(encoding="utf-8")).get("loot", [])
        except Exception:
            data["loot"] = []
    veinscore_loot_path = root / "veinscore_loot.json"
    if veinscore_loot_path.exists():
        try:
            data["veinscore_loot"] = json.loads(veinscore_loot_path.read_text(encoding="utf-8")).get("items", [])
        except Exception:
            data["veinscore_loot"] = []
    level_table_path = root / "level_table.json"
    if level_table_path.exists():
        try:
            data["level_table"] = json.loads(level_table_path.read_text(encoding="utf-8")).get("levels", [])
        except Exception:
            data["level_table"] = []
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


def select_loot(game_data, enemy):
    """
    Pick a loot item for the given enemy tier.
    """
    loot_table = game_data.get("loot", [])
    if not loot_table:
        return None
    tier = enemy.get("tier", 1) if enemy else 1
    tier_matches = [l for l in loot_table if l.get("tier") == tier]
    if not tier_matches:
        tier_matches = [l for l in loot_table if l.get("tier", 0) <= tier]
    candidates = tier_matches or loot_table
    return random.choice(candidates) if candidates else None


def veinscore_value(name, game_data):
    table = game_data.get("veinscore_loot", [])
    for item in table:
        if item.get("name") == name:
            return item.get("veinscore", 0)
    return 0


def award_veinscore(character, amount):
    res = character.setdefault("resources", {})
    res["veinscore"] = res.get("veinscore", 0) + amount
    return res["veinscore"]


def enemy_move_damage(enemy, move):
    """Roll damage for an enemy move using its damage_profile."""
    stat_block = enemy.get("stat_block", {}) if enemy else {}
    dmg_profile = stat_block.get("damage_profile", {}) if isinstance(stat_block, dict) else {}
    on_hit = move.get("on_hit", {}) if move else {}
    dmg_ref = on_hit.get("damage")
    dmg_obj = {}
    if isinstance(dmg_ref, str):
        dmg_obj = dmg_profile.get(dmg_ref, {})
    elif isinstance(dmg_ref, dict):
        dmg_obj = dmg_ref
    dice = dmg_obj.get("dice", "1d6")
    flat = dmg_obj.get("flat", 0)
    dmg_roll = roll(dice)
    return dmg_roll + (flat if isinstance(flat, (int, float)) else 0)


def select_enemy_move(enemy, state):
    """Select an enemy move; fall back to first move."""
    moves = enemy.get("moves", []) if enemy else []
    if not moves:
        return None
    move_lookup = {m.get("id"): m for m in moves if m.get("id")}
    behavior = (enemy.get("resolved_archetype") or {}).get("ai", {}).get("behavior_script", {})

    def last_player_missed():
        for entry in reversed(state.get("log", [])):
            if isinstance(entry, dict) and "action_effects" in entry:
                hit = entry["action_effects"].get("hit")
                if hit is False:
                    return True
                if hit is True:
                    return False
        return False

    def check_cond(cond):
        if not cond:
            return True
        for k, v in cond.items():
            if k == "player_missed_last_action":
                if last_player_missed() != bool(v):
                    return False
            elif k == "player_moved":
                return False  # movement not tracked yet
            elif k == "blood_mark_gte":
                blood = state.get("party", {}).get("members", [{}])[0].get("marks", {}).get("blood", 0)
                if blood < v:
                    return False
            else:
                return False
        return True

    for step in behavior.get("default_loop", []):
        stype = step.get("type")
        if stype == "move":
            ref = step.get("ref")
            if ref and ref in move_lookup:
                return move_lookup[ref]
        elif stype == "conditional":
            if check_cond(step.get("if", {})):
                for inner in step.get("then", []):
                    if inner.get("type") == "move":
                        ref = inner.get("ref")
                        if ref and ref in move_lookup:
                            return move_lookup[ref]
    return moves[0]


def build_enemy_chain(enemy):
    """Build a simple move chain based on available RP."""
    moves = enemy.get("moves", []) if enemy else []
    if not moves:
        return []
    rp_available = enemy.get("rp", enemy.get("rp_pool", 2))
    chain = []
    # naive: iterate moves in order and take those we can afford until rp spent
    for mv in moves:
        cost = mv.get("cost", {}).get("rp", 0)
        if cost <= rp_available:
            chain.append(mv)
            rp_available -= cost
    # if nothing fit, take the first move once
    if not chain:
        chain.append(moves[0])
    return chain


def compute_damage_reduction(target):
    """Consume and roll any stored damage_reduction effects on the target."""
    dr_list = target.pop("damage_reduction", [])
    total = 0
    for eff in dr_list:
        if not isinstance(eff, dict):
            continue
        dice = eff.get("dice")
        flat = eff.get("flat", 0)
        if dice:
            total += roll(dice)
        if isinstance(flat, (int, float)):
            total += flat
    return total
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
                    'idf': 0,
                    'veinscore': 0
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
            for key in ["effect", "cost", "dice", "stat", "tags", "path", "type"]:
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
                en["rp"] = en.get("rp_pool", 2)
                tick_statuses(en)
            tick_statuses(ch)

        # start-of-round upkeep triggered when entering chain_declaration and not yet started
        if state["phase"]["current"] == "chain_declaration" and not state["phase"].get("round_started"):
            state["phase"]["round"] += 1
            round_upkeep()
            state["phase"]["round_started"] = True

        current_phase = state["phase"]["current"]
        if current_phase == "chain_declaration":
            character = state["party"]["members"][0]
            res = character.get("resources", {})
            hp_cur = res.get("hp", "?")
            hp_max = res.get("hp_max") or res.get("max_hp") or res.get("maxHp") or hp_cur
            print(f"PC HP: {hp_cur}/{hp_max} | {format_status_summary(character)}")
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
            ic = InterruptController(enemies[0] if enemies else {})
            enemy = enemies[0] if enemies else None
            enemy_dv = 0
            enemy_dv_breakdown = {}
            if enemy:
                dv_base = enemy.get("dv_base") or enemy.get("stat_block", {}).get("defense", {}).get("dv_base", 0)
                enemy_dv = dv_base + enemy.get("idf", 0) + enemy.get("momentum", 0)
                enemy_dv_breakdown = {
                    "dv_base": dv_base,
                    "idf": enemy.get("idf", 0),
                    "momentum": enemy.get("momentum", 0),
                }
            print(f"Chain contest: player d20={chain_attack_d20} vs enemy DV={enemy_dv} (dv/idf/mom={enemy_dv_breakdown})")

            for idx, ability_name in enumerate(chain.get("abilities", [])):
                ability = next((a for a in character.get("abilities", []) if a.get("name") == ability_name), None)
                if not ability:
                    continue
                # snapshot resources before action
                res_before = character.get("resources", {}).copy()
                pre_enemy_hp = enemies[0].get("hp", 10) if enemies else None
                balance_bonus = 0 if idx == 0 else character.get("resources", {}).get("balance", 0)
                pending = resolve_action_step(state, character, ability, attack_roll=chain_attack_d20, balance_bonus=balance_bonus)
                result = apply_action_effects(state, character, enemies, defense_d20=None)
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
                statuses_applied = []
                if isinstance(state.get("log"), list) and state["log"]:
                    last = state["log"][-1]
                    if isinstance(last, dict) and "action_effects" in last:
                        aelog = last["action_effects"]
                        defense_d20 = aelog.get("defense_d20")
                        defense_roll = aelog.get("defense_roll")
                        statuses_applied = aelog.get("statuses_applied", [])

                print(
                    f"Resolved {ability_name}:\n"
                    f"  to_hit={to_hit} vs defense={defense_roll} (d20={defense_d20})\n"
                    f"  dmg_roll={damage_roll}, damage={dmg}, enemy_hp={post_enemy_hp}\n"
                    f"  resolve_spent={resolve_spent}, resolve_now={resolve_now}, "
                    f"heat={heat_now}, balance={balance_now}, momentum={momentum_now}\n"
                    f"  attack_d20={attack_d20}"
                    + (f"\n  statuses_applied={statuses_applied}" if statuses_applied else "")
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
            if enemies:
                print(format_enemy_state(enemies[0]))
            # simple enemy turn if alive
            if enemies:
                enemy_hp = enemies[0].get("hp", 0)
                if enemy_hp > 0:
                    enemy = enemies[0]
                    chain_moves = build_enemy_chain(enemy)
                    for midx, move in enumerate(chain_moves):
                        move = move or {}
                        move_name = move.get("name", move.get("id", "Enemy move"))
                        to_hit_mod = move.get("to_hit", {}).get("av_mod", 0)
                        atk_mod = enemy.get("attack_mod", 0)
                        enemy_to_hit_d20 = roll("1d20")
                        enemy_to_hit = enemy_to_hit_d20 + to_hit_mod + atk_mod
                        # Offer player interrupt before second+ attack
                        if midx > 0:
                            resp = input("Attempt interrupt? (y/n): ").strip().lower()
                            if resp.startswith("y"):
                                defenses = [a for a in character.get("abilities", []) if a.get("type") == "defense"]
                                if defenses:
                                    print("Choose defense ability:")
                                    for i, d in enumerate(defenses):
                                        print(f"{i+1}. {d.get('name')}")
                                    choice = input("> ").strip()
                                    try:
                                        idx_choice = int(choice) - 1
                                        defense_ability = defenses[idx_choice] if 0 <= idx_choice < len(defenses) else defenses[0]
                                    except Exception:
                                        defense_ability = defenses[0]
                                    # pay costs: base 1 RP plus ability cost/pool
                                    character["resources"]["resolve"] = max(0, character["resources"].get("resolve", 0) - 1)
                                    cost = defense_ability.get("cost", 0)
                                    pool = defense_ability.get("pool")
                                    if cost and pool and pool in character.get("pools", {}):
                                        character["pools"][pool] = max(0, character["pools"][pool] - cost)
                                    elif cost:
                                        character["resources"]["resolve"] = max(0, character["resources"].get("resolve", 0) - cost)
                                    # apply defense ability on_use effects (e.g., reduce_damage)
                                    apply_effect_list(defense_ability.get("effects", {}).get("on_use", []), actor=character, enemy=enemy, default_target="self")
                                    # store any on_success effects for when damage is fully prevented
                                    if defense_ability.get("effects", {}).get("on_success"):
                                        character.setdefault("damage_reduction_success", []).extend(defense_ability["effects"]["on_success"])
                                    int_d20 = roll("1d20")
                                    int_total = int_d20 + character["resources"].get("momentum", 0)
                                    print(f"Player interrupt attempt: d20={int_d20}+momentum={character['resources'].get('momentum',0)} => {int_total}")
                                    # simple resolution: compare to the enemy's planned attack total
                                    if int_total >= enemy_to_hit:
                                        print("Interrupt succeeds! Enemy chain ends.")
                                        break
                                    else:
                                        print(f"Interrupt fails (enemy atk {enemy_to_hit}).")
                                else:
                                    print("No defense abilities available.")
                        # proceed with move
                        player_def_d20 = roll("1d20")
                        tb = character.get("temp_bonuses", {}) or {}
                        player_def = player_def_d20 + character["resources"].get("idf", 0) + character["resources"].get("momentum", 0) + tb.get("idf", 0) + tb.get("defense", 0)
                        if enemy_to_hit > player_def:
                            counter_dmg = enemy_move_damage(enemy, move)
                            reduction = compute_damage_reduction(character)
                            dmg_after = max(0, counter_dmg - reduction)
                            character["resources"]["hp"] = max(0, character["resources"].get("hp", 0) - dmg_after)
                            # apply on_success effects if fully prevented
                            if dmg_after == 0 and character.get("damage_reduction_success"):
                                apply_effect_list(character.pop("damage_reduction_success", []), actor=character, enemy=enemy, default_target="self")
                            on_hit_effects = move.get("on_hit", {}).get("effects", [])
                            applied = apply_status_effects(character, on_hit_effects)
                            applied_note = f" Effects applied: {', '.join(applied)}." if applied else ""
                            print(f"Enemy uses {move_name}: atk {enemy_to_hit_d20}+{to_hit_mod}+{atk_mod}={enemy_to_hit} vs def {player_def_d20}+idf/mom={character['resources'].get('idf',0)}/{character['resources'].get('momentum',0)}={player_def} -> HIT for {counter_dmg - reduction} (raw {counter_dmg}, reduced {reduction}). PC HP {character['resources']['hp']}.{applied_note}")
                        else:
                            print(f"Enemy uses {move_name}: atk {enemy_to_hit_d20}+{to_hit_mod}+{atk_mod}={enemy_to_hit} vs def {player_def_d20}+idf/mom={character['resources'].get('idf',0)}/{character['resources'].get('momentum',0)}={player_def} -> MISS.")
            # check end conditions and loop combat
            if enemies and enemies[0].get("hp", 0) <= 0:
                print("Enemy defeated.")
                loot = select_loot(game_data, enemies[0])
                if loot:
                    state.setdefault("loot", []).append(loot)
                    lname = loot.get("name", "Loot")
                    lrar = loot.get("rarity", "?")
                    ltier = loot.get("tier", "?")
                    print(f"Loot gained: {lname} (Tier {ltier}, {lrar})")
                    vs = veinscore_value(lname, game_data)
                    if vs:
                        total_vs = award_veinscore(character, vs)
                        print(f"Gained +{vs} Veinscore from {lname}. Total Veinscore: {total_vs}.")
                # Always drop 1-2 Faint Vein Sigils
                faint_count = random.randint(1, 2)
                faint_value = veinscore_value("Faint Vein Sigil", game_data) or 1
                total_faint_vs = faint_count * faint_value
                award_veinscore(character, total_faint_vs)
                state.setdefault("loot", []).extend([{"name": "Faint Vein Sigil", "tier": 1, "veinscore": faint_value}] * faint_count)
                print(f"Loot gained: {faint_count}x Faint Vein Sigil (+{total_faint_vs} Veinscore). Total Veinscore: {character['resources'].get('veinscore', 0)}.")
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
