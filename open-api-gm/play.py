import json
import os
import argparse
from pathlib import Path
import random
from copy import deepcopy
from ai.narrator import narrate
from game_context import NARRATOR, NARRATION
from ui.ui import UI
from ui.cli_provider import CLIProvider
from ui.events import (
    emit_event,
    emit_combat_state,
    emit_combat_log,
    emit_interrupt,
    emit_character_update,
    emit_declare_chain,
)
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
    build_narration_payload,
)
from engine.interrupt_controller import InterruptController, apply_interrupt
from engine.status import apply_status_effects, tick_statuses

LOG_FILE = Path(__file__).parent / "narration.log"
DEFAULT_CHARACTER_PATH = Path(__file__).parent / "default_character.json"


def usable_ability_objects(state):
    member = state.get("party", {}).get("members", [None])[0]
    if not member:
        return []
    return [ab for ab in member.get("abilities", []) if ab.get("cooldown", 0) == 0]


def append_log(entry: str) -> None:
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass


def log_flags(prefix: str, state: dict) -> None:
    flags = state.get("flags", {})
    append_log(f"{prefix} flags={flags}")

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

def get_player_choice(options, ui, state):
    """
    Web-safe choice handler.
    Emits choices and waits for next step.
    """
    # In blocking UIs (CLI), keep the immediate return behavior.
    if getattr(ui, "is_blocking", True):
        idx = ui.choice("--- YOUR OPTIONS ---", options + ["exit"])
        return (options + ["exit"])[idx]

    ui.clear("narration")
    ui.choice(
        "Choose an option:",
        options
    )

    state["awaiting"] = {
        "type": "player_choice",
        "options": options
    }

    return None

def advance_phase(state, phase_machine, previous_phase):
    if state["phase"]["current"] != previous_phase:
        return  # action already changed phase

    transitions = phase_machine["phases"][previous_phase]["allowedTransitions"]
    if transitions:
        state["phase"]["current"] = transitions[0]

def create_default_character():
    fallback = {
        "name": "The Blooded",
        "hp": {"current": 24, "max": 24},
        "rp": 5,
        "veinscore": 0,
        "attributes": {
            "str": 14,
            "dex": 14,
            "int": 14,
            "wil": 8,
        },
        "abilities": [
            {
      "name": "Basic Strike",
      "path": "core",
      "tier": 0,
      "cooldown": 1,
      "base_cooldown": 0,
      "cost": 1,
      "resource": "resolve",
      "pool": "free",
      "dice": "1d4",
      "tags": [
        "core",
        "attack"
      ],
      "effect": "Make a basic attack for 1d4 + stat. On hit gain +1 Heat. Applies -1 Balance penalty.",
      "stat": "weapon",
      "addStatToAttackRoll": "true",
      "addStatToDamage": "true"
    },

        ],
    }
    try:
        return json.loads(DEFAULT_CHARACTER_PATH.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def create_game_context(ui, skip_character_creation=False):
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
    phase_machine = canon["phase_machine.json"]
    game_data = load_game_data()

    if skip_character_creation:
        character = create_default_character()
    elif args.auto or args.interactive_defaults:
        character = load_character()
    else:
        use_saved = ui.choice("Use saved character?", ["Yes", "No"]) == 0
        if use_saved:
            character = load_character()
        else:
            character = run_character_creation(
                canon,
                narrator=None,  # or narrator_stub if you want flavor text
                ui=ui,
            )
            save_character(character)

    state = initial_state()
    state["flags"] = {"narration_enabled": not args.nonarrate}
    append_log(f"SESSION_START flags={state.get('flags')}")
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
            for key in ["effect", "cost", "dice", "stat", "tags", "path", "type", "effects", "to_hit"]:
                if key not in ability and key in src:
                    ability[key] = src[key]
            if not ability.get("pool"):
                path = ability.get("path") or src.get("path")
                ability["path"] = path
                if path and path in pool_map:
                    ability["pool"] = pool_map[path]

    ui.system("Veinbreaker AI Session Started.\n")

    return {
        "ui": ui,
        "state": state,
        "phase_machine": phase_machine,
        "game_data": game_data,
        "args": args,
    }


def start_game(ctx):
    ui = ctx["ui"]

    text = """
WELCOME, VEINBREAKER

You are wondering if this is a game.
If there are rules. if you can win.
NO. THIS IS NOT A GAME.
Games forgive hesitation.
I do not.  Games give you turns. I give you moments—and I take them back when you waste them.

WHAT YOU ARE
You are not a hero. You are not chosen. You are not special.
You are interesting.
You came from a place where rules were safety rails. Where numbers meant comfort. Where death was the end.
Here, numbers are temptation. Here, death is a lesson.

HOW YOU SURVIVE

You will strike. You will miss. You will strike again anyway.
You will learn that a failed blow does not end a fight— but greed does.
You will feel your Balance slip as you overreach.
You will feel Heat rise as blood splashes the stone.
You will feel Momentum surge when you defend perfectly and realize—
That feeling? 
That is Resolve. Spend it. Spend it boldly. Spend it gloriously.
I do not want perfection.I do not want safety.I do not want caution.
I want commitment.
Declare your chains before you swing.Show me your plan before you bleed.
Let me see whether your hands shake when the rhythm turns against you.
And when an enemy is Primed—when they are open, gasping, begging—do not hesitate.
Execute.Take the Blood Mark.Feel the weight of it settle into your bones.
You will be stronger after.You will also be ... noticed.

A WARNING (I ONLY GIVE ONE)
The longer you impress me,the more I will send things that remember how to impress me back.
Former players.Broken champions.Hunters who learned too much and stopped dying properly.
You cannot kill them.You can only survive them.
Come, Veinbreaker.I am watching.I am listening.I am already entertained.
And if you live long enough—maybe I will let you change the rules.Or maybe I will carve your name into the walls
and let the next one read it while they wonder how long they’ll last.
Come. Let’s see how you move when the stone starts breathing.

"""
    ui.scene(text)

    ui.choice(
        "What do you do?",
        ["Advance"]
    )


def game_step(ctx, player_input):
    state = ctx["state"]
    ui = ctx["ui"]
    phase_machine = ctx["phase_machine"]
    game_data = ctx["game_data"]
    args = ctx.get("args")

    resolved_choice = None

    # ── Resolve awaited choice ───────────────────
    if "awaiting" in state and isinstance(player_input, dict) and "choice" in player_input:
        awaiting = state.pop("awaiting")
        idx = player_input["choice"]

        if awaiting["type"] == "player_choice":
            if isinstance(idx, int) and 0 <= idx < len(awaiting["options"]):
                resolved_choice = awaiting["options"][idx]
            else:
                ui.error("Invalid choice selection.")
                return True
        elif awaiting["type"] == "chain_declaration":
            if isinstance(idx, int) and 0 <= idx < len(awaiting["options"]):
                resolved_choice = [awaiting["options"][idx]]
            else:
                ui.error("Invalid chain selection.")
                return True
        elif awaiting["type"] == "chain_builder":
            # handled via action "declare_chain"
            state["awaiting"] = awaiting  # restore; action handler will pop

    nonarrate = args.nonarrate if args else False
    interactive_defaults = args.interactive_defaults if args else False
    auto_mode = args.auto if args else False

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
        ui.system(f"PC HP: {hp_cur}/{hp_max} | {format_status_summary(character)}")
        usable_objs = usable_ability_objects(state)
        awaiting_chain_builder = state.get("awaiting", {}).get("type") == "chain_builder"
        if getattr(ui, "is_blocking", True):
            usable = [ab.get("name") for ab in usable_objs if ab.get("name")]
            abilities = prompt_chain_declaration(state, character, usable, ui)
            if abilities is None:
                return True
            ok, resp = declare_chain(
                state,
                character,
                abilities,
                resolve_spent=0,
                stabilize=False
            )
            if not ok:
                ui.error(f"Invalid chain: {resp}")
                return True
            # set cooldowns for declared abilities
            for ability in character.get("abilities", []):
                if ability.get("name") in abilities:
                    cd = ability.get("base_cooldown", ability.get("cooldown", 0) or 0)
                    ability["base_cooldown"] = cd
                    ability["cooldown"] = cd
                    ability["cooldown_round"] = state["phase"]["round"] + cd if cd else state["phase"]["round"]
            state["phase"]["current"] = "chain_resolution"
            return True
        # non-blocking: emit chain builder event unless we're already awaiting a submission
        if not (awaiting_chain_builder and isinstance(player_input, dict) and player_input.get("action") == "declare_chain"):
            emit_declare_chain(ui, usable_objs, max_len=3)
            state["awaiting"] = {"type": "chain_builder", "options": usable_objs}
            return True

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
        ui.system(f"Chain contest: player d20={chain_attack_d20} vs enemy DV={enemy_dv} (dv/idf/mom={enemy_dv_breakdown})")

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
            emit_character_update(ui, {
                "hp": {"current": res_after.get("hp"), "max": res_after.get("hp_max", res_after.get("max_hp", res_after.get("maxHp", res_after.get("hp"))))},
                "rp": res_after.get("resolve", 0),
                "veinscore": res_after.get("veinscore", 0),
                "attributes": character.get("attributes", {}),
                "name": character.get("name")
            })
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

            ui.system(
                f"Resolved {ability_name}:\n"
                f"  to_hit={to_hit} vs defense={defense_roll} (d20={defense_d20})\n"
                f"  dmg_roll={damage_roll}, damage={dmg}, enemy_hp={post_enemy_hp}\n"
                f"  resolve_spent={resolve_spent}, resolve_now={resolve_now}, "
                f"heat={heat_now}, balance={balance_now}, momentum={momentum_now}\n"
                f"  attack_d20={attack_d20}"
                + (f"\n  statuses_applied={statuses_applied}" if statuses_applied else "")
            )
            # Emit narration attached by action_resolution, if present; otherwise try now
            if state.get("log"):
                last = state["log"][-1]
                if "action_effects" in last:
                    last["action_effects"].setdefault("chain_index", idx + 1)
                narration = last.get("narration")
                if narration:
                    ui.narration(narration, data=last)
                    append_log(f"NARRATION_COMBAT: {narration}")
                elif state.get("flags", {}).get("narration_enabled"):
                    log_flags("COMBAT_STEP", state)
                    effects = last.get("action_effects")
                    if not effects:
                        append_log("NARRATION_SKIP: no action_effects")
                    elif not NARRATION and not NARRATOR:
                        append_log("NARRATION_SKIP: no narrator available")
                    elif effects and NARRATION:
                        try:
                            narration = NARRATION.combat_step(
                                action_effects=effects,
                                chain_index=effects.get("chain_index", idx + 1),
                            )
                            if narration:
                                last["narration"] = narration
                                ui.narration(narration, data=last)
                                append_log(f"NARRATION_COMBAT: {narration}")
                            else:
                                append_log("NARRATION_EMPTY: combat_step returned None/empty")
                        except Exception as e:
                            last["narration_error"] = str(e)
                            ui.error(f"[NARRATOR ERROR] {e}", data=last)
                            append_log(f"NARRATION_ERROR: {e}")
                    elif effects and NARRATOR:
                        try:
                            payload = build_narration_payload(state=state, effects=effects)
                            narration = NARRATOR.narrate(payload, scene_tag="combat")
                            last["narration"] = narration
                            ui.narration(narration, data=last)
                            append_log(f"NARRATION_COMBAT: {narration}")
                            if not narration:
                                append_log("NARRATION_EMPTY: direct narrate returned empty")
                        except Exception as e:
                            last["narration_error"] = str(e)
                            ui.error(f"[NARRATOR ERROR] {e}", data=last)
                            append_log(f"NARRATION_ERROR: {e}")
                elif last.get("narration_error"):
                    ui.error(f"[NARRATOR ERROR] {last.get('narration_error')}", data=last)
                    append_log(f"NARRATION_ERROR: {last.get('narration_error')}")
            result = check_exposure(character)
            if result:
                state["log"].append({"exposure": result})
            # Interrupt window after first action in chain
            if enemies and len(enemies) > 0 and ic.should_interrupt(state, idx):
                hit, dmg, rolls = apply_interrupt(state, character, enemies[0])
                atk_mod = enemies[0].get("attack_mod", 0)
                def_mod = character["resources"].get("idf", 0) + character["resources"].get("momentum", 0)
                emit_interrupt(ui)
                ui.system(f"Interrupt contest: enemy ({rolls['atk_d20']}+{atk_mod}={rolls['atk_total']}) vs player ({rolls['def_d20']}+{def_mod}={rolls['def_total']})")
                if hit and dmg > 0:
                    ui.system(f"Enemy INTERRUPT hits for {dmg} dmg. Chain broken.")
                    break
                elif hit and rolls["atk_total"] - rolls["def_total"] >= 5:
                    ui.system("Enemy INTERRUPT breaks the chain (MoD>=5).")
                    break
                else:
                    ui.system("Enemy interrupt fails.")
        if enemies:
            ui.system(format_enemy_state(enemies[0]))
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
                        if getattr(ui, "is_blocking", True):
                            resp = ui.text_input("Attempt interrupt? (y/n): ")
                            resp = resp.lower() if isinstance(resp, str) else ""
                        else:
                            resp = "n"
                        if resp.startswith("y"):
                            defenses = [a for a in character.get("abilities", []) if a.get("type") == "defense"]
                            if defenses:
                                idx_choice = ui.choice("Choose defense ability:", [d.get("name") for d in defenses])
                                defense_ability = defenses[idx_choice] if 0 <= idx_choice < len(defenses) else defenses[0]
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
                                # use the player's original chain attack d20 for the interrupt attempt
                                int_d20 = chain_attack_d20
                                int_total = int_d20 + character["resources"].get("momentum", 0)
                                ui.system(f"Player interrupt attempt: d20={int_d20}+momentum={character['resources'].get('momentum',0)} => {int_total}")
                                # simple resolution: compare to the enemy's planned attack total
                                if int_total >= enemy_to_hit:
                                    ui.system("Interrupt succeeds! Enemy chain ends.")
                                    break
                                else:
                                    ui.system(f"Interrupt fails (enemy atk {enemy_to_hit}).")
                            else:
                                ui.system("No defense abilities available.")
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
                        ui.system(f"Enemy uses {move_name}: atk {enemy_to_hit_d20}+{to_hit_mod}+{atk_mod}={enemy_to_hit} vs def {player_def_d20}+idf/mom={character['resources'].get('idf',0)}/{character['resources'].get('momentum',0)}={player_def} -> HIT for {counter_dmg - reduction} (raw {counter_dmg}, reduced {reduction}). PC HP {character['resources']['hp']}.{applied_note}")
                    else:
                        ui.system(f"Enemy uses {move_name}: atk {enemy_to_hit_d20}+{to_hit_mod}+{atk_mod}={enemy_to_hit} vs def {player_def_d20}+idf/mom={character['resources'].get('idf',0)}/{character['resources'].get('momentum',0)}={player_def} -> MISS.")
        # check end conditions and loop combat
        if enemies and enemies[0].get("hp", 0) <= 0:
            ui.system("Enemy defeated.")
            emit_combat_state(ui, False)
            loot_items_payload = []
            # Aftermath narration hook
            if state.get("flags", {}).get("narration_enabled") and NARRATION:
                log_flags("AFTERMATH", state)
                try:
                    enemy_name = enemies[0].get("name", enemies[0].get("id", "Enemy"))
                    aftermath_text = NARRATION.aftermath(
                        location="encounter",
                        enemies_defeated=[{"name": enemy_name, "condition": "defeated"}],
                        player_state={
                            "hp": character["resources"].get("hp"),
                            "heat": character["resources"].get("heat"),
                            "balance": character["resources"].get("balance"),
                            "momentum": character["resources"].get("momentum"),
                        },
                        environment_change="quiet",
                    )
                    if aftermath_text:
                        state.setdefault("log", []).append({"aftermath_narration": aftermath_text})
                        ui.narration(aftermath_text)
                        append_log(f"NARRATION_AFTER: {aftermath_text}")
                except Exception as e:
                    ui.error(f"[NARRATOR ERROR] {e}")
                    append_log(f"NARRATION_ERROR: {e}")
            loot = select_loot(game_data, enemies[0])
            if loot:
                state.setdefault("loot", []).append(loot)
                loot_items_payload.append({
                    "name": loot.get("name"),
                    "tier": loot.get("tier"),
                    "rarity": loot.get("rarity"),
                    "type": loot.get("type"),
                })
                lname = loot.get("name", "Loot")
                lrar = loot.get("rarity", "?")
                ltier = loot.get("tier", "?")
                ui.loot(f"Loot gained: {lname} (Tier {ltier}, {lrar})", data=loot)
                vs = veinscore_value(lname, game_data)
                if vs:
                    total_vs = award_veinscore(character, vs)
                    ui.system(f"Gained +{vs} Veinscore from {lname}. Total Veinscore: {total_vs}.")
            # Always drop 1-2 Faint Vein Sigils
            faint_count = random.randint(1, 2)
            faint_value = veinscore_value("Faint Vein Sigil", game_data) or 1
            total_faint_vs = faint_count * faint_value
            award_veinscore(character, total_faint_vs)
            state.setdefault("loot", []).extend([{"name": "Faint Vein Sigil", "tier": 1, "veinscore": faint_value}] * faint_count)
            loot_items_payload.extend(
                [{"name": "Faint Vein Sigil", "tier": 1, "type": "veinscore_token", "veinscore": faint_value}]
                * faint_count
            )
            ui.loot(
                f"Loot gained: {faint_count}x Faint Vein Sigil (+{total_faint_vs} Veinscore). Total Veinscore: {character['resources'].get('veinscore', 0)}.",
                data={"faint_count": faint_count, "veinscore_value": faint_value},
            )
            # Loot narration after loot resolution
            if state.get("flags", {}).get("narration_enabled") and NARRATION:
                try:
                    loot_text = NARRATION.loot_drop(
                        loot_items=loot_items_payload,
                        veinscore_total=character["resources"].get("veinscore", 0),
                    )
                    if loot_text:
                        append_log(f"NARRATION_LOOT: {loot_text}")
                        ui.loot(loot_text, data={"loot": loot_items_payload})
                except Exception as e:
                    append_log(f"NARRATION_ERROR: {e}")
            enemies.clear()
            state["phase"]["current"] = "out_of_combat"
        elif character["resources"].get("hp", 0) <= 0:
            ui.system("PC defeated.")
            emit_combat_state(ui, False)
            emit_character_update(ui, {
                "hp": {"current": character["resources"].get("hp"), "max": character["resources"].get("hp_max", character["resources"].get("max_hp", character["resources"].get("maxHp", character["resources"].get("hp"))))},
                "rp": character["resources"].get("resolve", 0),
                "veinscore": character["resources"].get("veinscore", 0),
                "attributes": character.get("attributes", {}),
                "name": character.get("name")
            })
            state["phase"]["current"] = "out_of_combat"
        else:
            state["phase"]["current"] = "chain_declaration"
            state["phase"]["round_started"] = False
        # heat resets when chain ends (unless carried via stabilize rule above; we already set on round start)
        character["resources"]["heat"] = character["resources"].get("heat", 0) if character["resources"].get("heat", 0) <= 2 else 0
        return True

    actions = allowed_actions(state, phase_machine)

    if not (nonarrate or interactive_defaults):
        try:
            narrate(state, actions)
        except Exception as e:
            ui.error(f"[Narrator error: {e}]")
    else:
        ui.system("\n(Narration suppressed)")

    requested_action = player_input.get("action") if isinstance(player_input, dict) else None
    # quick start hook for web: immediately prompt chain builder
    if requested_action == "start" and not getattr(ui, "is_blocking", True):
        usable_objs = usable_ability_objects(state)
        emit_declare_chain(ui, usable_objs, max_len=3)
        state["awaiting"] = {"type": "chain_builder", "options": usable_objs}
        return True
    if isinstance(player_input, dict) and player_input.get("action") == "declare_chain":
        chain_ids = player_input.get("chain") or []
        awaiting = state.pop("awaiting", None) if state.get("awaiting", {}).get("type") == "chain_builder" else None
        usable = awaiting.get("options") if awaiting else usable_ability_objects(state)
        names = []
        for cid in chain_ids:
            ab = next((a for a in usable if a.get("id") == cid or a.get("name") == cid), None)
            if ab and ab.get("name"):
                names.append(ab["name"])
        character = state["party"]["members"][0]
        ok, resp = declare_chain(
            state,
            character,
            names,
            resolve_spent=0,
            stabilize=False
        )
        if not ok:
            ui.error(f"Invalid chain: {resp}")
            return True
        for ability in character.get("abilities", []):
            if ability.get("name") in names:
                cd = ability.get("base_cooldown", ability.get("cooldown", 0) or 0)
                ability["base_cooldown"] = cd
                ability["cooldown"] = cd
                ability["cooldown_round"] = state["phase"]["round"] + cd if cd else state["phase"]["round"]
        state["phase"]["current"] = "chain_resolution"
        # For web/non-blocking, immediately proceed into resolution so we don't get stuck waiting.
        if not getattr(ui, "is_blocking", True):
            return game_step(ctx, {"action": "tick"})
        return True
    if resolved_choice is not None:
        choice = resolved_choice
    elif requested_action in actions:
        choice = requested_action
    elif auto_mode:
        choice = actions[0] if actions else "exit"
        ui.system(f"Auto choice: {choice}")
    else:
        choice = get_player_choice(actions, ui, state)
        if choice is None:
            return True
    if choice == "exit":
        ui.system("Exiting Veinbreaker AI session.")
        return False
    prev_phase = state["phase"]["current"]
    apply_action(state, choice)
    if choice in ("enter_encounter", "generate_encounter"):
        if state.get("enemies"):
            enemy = state["enemies"][0]
            emit_combat_state(ui, True)
            emit_combat_log(ui, format_enemy_preview(enemy))
            # Scene intro narration
            if state.get("flags", {}).get("narration_enabled") and NARRATION:
                log_flags("SCENE_INTRO", state)
                try:
                    scene_text = NARRATION.scene_intro(
                        location=enemy.get("location", "encounter"),
                        environment_tags=enemy.get("tags", []),
                        enemy_presence={
                            "count": 1,
                            "type": enemy.get("name", enemy.get("id", "Enemy")),
                            "distance": "near",
                        },
                        player_state={
                            "momentum": state["party"]["members"][0]["resources"].get("momentum", 0),
                            "heat": state["party"]["members"][0]["resources"].get("heat", 0),
                            "balance": state["party"]["members"][0]["resources"].get("balance", 0),
                        },
                        threat_level="immediate",
                    )
                    if scene_text:
                        ui.narration(scene_text)
                        append_log(f"NARRATION_SCENE: {scene_text}")
                except Exception as e:
                    ui.error(f"[NARRATOR ERROR] {e}")
                    append_log(f"NARRATION_ERROR: {e}")
        advance_phase(state, phase_machine, prev_phase)

    # For non-blocking UIs, immediately surface the next prompt without waiting for another action payload.
    if not getattr(ui, "is_blocking", True) and "awaiting" not in state:
        return game_step(ctx, {"action": "tick"})

    return True


def main():
    ui = UI(CLIProvider())
    ctx = create_game_context(ui)

    start_game(ctx)

    while True:
        keep_going = game_step(ctx, {"action": "tick"})
        if keep_going is False:
            break


if __name__ == "__main__":
    main()
