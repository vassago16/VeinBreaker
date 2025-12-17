import json
import os
import argparse
from pathlib import Path
import pdb
import random


from engine.chain_resolution_engine import ChainResolutionEngine
from engine.interrupt_policy import EnemyWindowPolicy, PlayerPromptPolicy


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
    emit_resource_update,
)
from combat import Combat
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
from engine.combat_state import register_participant, combat_get, combat_set

import debugpy



LOG_FILE = Path(__file__).parent / "narration.log"
DEFAULT_CHARACTER_PATH = Path(__file__).parent / "default_character.json"
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

def create_default_character():
    """Load the default character from character.json; fallback to built-in template."""
    fallback = {
        "name": "New Blood",
        "hp": {"current": 24, "max": 24},
        "rp": 5,
        "veinscore": 0,
        "attributes": {
            "pow": 1,
            "agi": 1,
            "mnd": 1,
            "spr": 1,
        },
        "abilities": [],
    }
    candidate_paths = [
        Path(__file__).parent / "character.json",
        DEFAULT_CHARACTER_PATH,
    ]
    for path in candidate_paths:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return fallback

def create_game_context(ui, skip_character_creation=False):
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true", help="Run in automated mode (no prompts).")
    parser.add_argument("--narrate", dest="narrate", action="store_true", help="Enable narration (off by default).")
    parser.add_argument("--nonarrate", dest="narrate", action="store_false", help="Disable narration (default).")
    parser.set_defaults(narrate=False)
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

    # Normalize player resources so hp_max is always available and hp is numeric.
    res = character.setdefault("resources", {})
    if isinstance(res.get("hp"), dict):
        hp_obj = res.get("hp") or {}
        res["hp"] = hp_obj.get("current", hp_obj.get("hp"))
        res["hp_max"] = hp_obj.get("max") or res.get("hp_max") or res.get("max_hp") or res.get("maxHp")
    if "hp_max" not in res and "max_hp" not in res and "maxHp" not in res and isinstance(res.get("hp"), (int, float)):
        res["hp_max"] = res["hp"]

    state = initial_state()
    state["flags"] = {"narration_enabled": bool(args.narrate)}
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
        "combat": None,
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

def round_upkeep(state: dict) -> None:
    """Per-round refresh: cooldowns, resolve regen, balance/momentum/heat resets, enemy budgets."""
    tick_cooldowns(state)
    ch = state["party"]["members"][0]
    res = ch.get("resources", {})
    cap = res.get("resolve_cap", res.get("resolve", 0))
    before = res.get("resolve", 0)
    regen = 2
    # RP is encounter-scoped; keep `resources.resolve` mirrored for legacy systems.
    if "encounter" in state and ch.get("_combat_key"):
        cur = combat_get(state, ch, "rp", before)
        rp_cap = combat_get(state, ch, "rp_cap", cap)
        new_rp = min(rp_cap, cur + regen)
        combat_set(state, ch, "rp", new_rp)
        combat_set(state, ch, "rp_cap", rp_cap)
        res["resolve"] = new_rp
    else:
        res["resolve"] = min(cap, before + regen)
    state["phase"]["resolve_regen"] = (before, regen, res["resolve"])
    # Combat meters:
    # - Balance resets per chain (handled at chain start/end), not here.
    # - Momentum/Heat persist for the encounter (for now), so do not reset here.
    if "encounter" not in state or not ch.get("_combat_key"):
        # Legacy non-encounter mode
        res["balance"] = 0
        res["momentum"] = 0
        res["heat"] = 0
    for en in state.get("enemies", []):
        en["interrupts_used"] = 0
        en["rp"] = en.get("rp_pool", 2)
        tick_statuses(en)
    tick_statuses(ch)

def emit_action_narration(state: dict, ui, idx: int) -> None:
    """Emit narration for a resolved action if available."""
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

def handle_chain_declaration(ctx: dict, player_input: dict) -> bool | None:
    state = ctx["state"]
    ui = ctx["ui"]
    character = state["party"]["members"][0]
    res = character.get("resources", {})
    hp_cur = res.get("hp", "?")
    hp_max = res.get("hp_max") or res.get("max_hp") or res.get("maxHp") or hp_cur
    ui.system(f"PC HP: {hp_cur}/{hp_max} | {format_status_summary(character)}")
    usable_objs = usable_ability_objects(state)
    awaiting_chain_builder = state.get("awaiting", {}).get("type") == "chain_builder"

  
    if not getattr(ui, "is_blocking", True) and awaiting_chain_builder:
        append_log("DEBUG: handle_chain_declaration short-circuit (awaiting chain_builder)")
        # Always re-emit the chain prompt while awaiting so the UI sees it.
        emit_declare_chain(ui, usable_objs, max_len=state.get("phase", {}).get("chain_max", 6) or 6)
        ui.choice("Build your next chain?", ["Build chain"])
        return True
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
            emit_event(ui, {"type": "chain_rejected", "reason": resp})
            # Re-open chain builder with current usable abilities
            emit_declare_chain(ui, usable_objs, max_len=state.get("phase", {}).get("chain_max", 6) or 6)
            state["awaiting"] = {"type": "chain_builder", "options": usable_objs}
            return True
        for ability in character.get("abilities", []):
            if ability.get("name") in abilities:
                cd = ability.get("base_cooldown", ability.get("cooldown", 0) or 0)
                ability["base_cooldown"] = cd
                ability["cooldown"] = cd
                ability["cooldown_round"] = state["phase"]["round"] + cd if cd else state["phase"]["round"]
        state["phase"]["current"] = "chain_resolution"
        return True
    # Non-blocking: emit builder prompt unless we're already processing a declare_chain action
    if not (awaiting_chain_builder and isinstance(player_input, dict) and player_input.get("action") == "declare_chain"):
        append_log("DEBUG: emit_declare_chain from handle_chain_declaration (non-blocking)")
        emit_declare_chain(ui, usable_objs, max_len=state.get("phase", {}).get("chain_max", 6) or 6)
        ui.choice("Build your next chain?", ["Build chain"])
        state["awaiting"] = {"type": "chain_builder", "options": usable_objs}
        return True
    append_log("DEBUG: skipping emit_declare_chain because awaiting declare_chain action")
    return None

def handle_chain_resolution(ctx: dict) -> bool | None:
    """
    Resolves a declared chain using the unified Chain Resolution Engine.
    Handles both player and enemy chains symmetrically.
    """
    state = ctx["state"]
    ui = ctx["ui"]

    party = state.get("party", {})
    members = party.get("members", [])
    if not members:
        ui.system("No active party member.")
        state["phase"]["current"] = "chain_declaration"
        return True

    player = members[0]
    enemies = state.get("enemies", [])

    if not enemies:
        ui.system("No enemies remain.")
        state["phase"]["current"] = "chain_declaration"
        return True

    enemy = enemies[0]

    # ─────────────────────────────────────────
    # Determine who is acting this chain
    # ─────────────────────────────────────────
    active = state.get("active_combatant", "player")

    if active == "player":
        aggressor = player
        defender = enemy
        chain_names = list(player.get("chain", {}).get("abilities", []))
    else:
        aggressor = enemy
        defender = player
        chain_names = list(enemy.get("chain", {}).get("abilities", []))

    if not chain_names:
        ui.system("No chain declared.")
        state["phase"]["current"] = "chain_declaration"
        return True

    # ─────────────────────────────────────────
    # Interrupt policy selection (DEFENDER-based)
    # ─────────────────────────────────────────
    seed = state.get("seed", None)
    rng = random.Random(seed)

    # Player chain (player -> enemy): enemy decides (enemy policy)
    # Enemy chain (enemy -> player): player decides (player policy)
    interrupt_policy = PlayerPromptPolicy() if defender is player else EnemyWindowPolicy(rng)

    # ─────────────────────────────────────────
    # Chain Resolution Engine
    # ─────────────────────────────────────────
    cre = ChainResolutionEngine(
        roll_fn=roll,
        resolve_action_step_fn=resolve_action_step,
        apply_action_effects_fn=apply_action_effects,
        interrupt_policy=interrupt_policy,
        emit_log_fn=emit_combat_log,
        interrupt_apply_fn=apply_interrupt,
    )

    ui.system(f"{aggressor.get('name','Combatant')} resolves a chain...")

    result = cre.resolve_chain(
        state=state,
        ui=ui,
        aggressor=aggressor,
        defender=defender,
        chain_ability_names=chain_names,
        defender_group=enemies if defender is enemy else [player],
        dv_mode="per_chain",
    )

    if getattr(result, "status", None) == "awaiting":
        # Pause and wait for next /step to resolve the player's interrupt decision.
        state["phase"]["current"] = "chain_resolution"
        return True
    # Clear any suppression after a chain finishes resolving.
    state.pop("suppress_chain_interrupt", None)

    # Balance is per-chain: reset aggressor balance after chain resolves.
    try:
        combat_set(state, aggressor, "balance", 0)
    except Exception:
        pass

    ui.system(
        f"Chain resolved: {result.break_reason} "
        f"(links resolved: {result.links_resolved})"
    )

    # ─────────────────────────────────────────
    # Cleanup
    # ─────────────────────────────────────────
    aggressor["chain"] = {
        "abilities": [],
        "declared": False,
    }

    # Swap active combatant and advance phase
    state["active_combatant"] = "enemy" if active == "player" else "player"
    if state.get("active_combatant") == "enemy":
        state["phase"]["current"] = "enemy_turn"
    else:
        state["phase"]["current"] = "chain_declaration"

    # For non-blocking UI, emit the next actionable prompt NOW (player only).
    if not getattr(ui, "is_blocking", True) and state.get("active_combatant") == "player":
        reopen_chain_builder(state, ui)
    elif not getattr(ui, "is_blocking", True) and state.get("active_combatant") == "enemy":
        # Surface the enemy-turn prompt immediately so the client gets options in this same response.
        handle_enemy_turn(ctx, {})

    return True


def handle_enemy_turn(ctx: dict, player_input: dict | None = None) -> bool | None:
    """
    Minimal enemy phase:
    - Enemy declares a simple one-move chain (first attack move)
    - Player gets a single interrupt prompt before the enemy chain resolves
    """
    state = ctx["state"]
    ui = ctx["ui"]

    party = state.get("party", {})
    members = party.get("members", [])
    if not members:
        state["phase"]["current"] = "chain_declaration"
        return True

    player = members[0]
    enemies = state.get("enemies", [])
    if not enemies:
        state["phase"]["current"] = "chain_declaration"
        return True

    enemy = enemies[0]

    awaiting = state.get("awaiting", {})
    if awaiting.get("type") == "enemy_interrupt":
        # Web-safe: resolve via actions instead of a blocking/choice return value.
        if isinstance(player_input, dict):
            act = player_input.get("action")
            if act == "interrupt_skip":
                state.pop("awaiting", None)
                state["pending_enemy_interrupt"] = False
            elif act == "interrupt":
                state.pop("awaiting", None)
                state["pending_enemy_interrupt"] = True
                # optional: stash chosen ability id/name for future interrupt mechanics
                if player_input.get("ability"):
                    state["pending_interrupt_ability"] = player_input["ability"]
        # still awaiting input
        if state.get("awaiting", {}).get("type") == "enemy_interrupt":
            return True

    pending = state.pop("pending_enemy_interrupt", None)

    # Prompt once per enemy turn (web/non-blocking)
    if pending is None and not getattr(ui, "is_blocking", True):
        from ui.events import emit_event

        # Present only defensive/interrupt-capable abilities.
        usable = usable_ability_objects(state)
        defense_abilities = []
        for ab in usable:
            tags = ab.get("tags", []) or []
            if "defense" in tags or ab.get("type") == "defense":
                defense_abilities.append({
                    "id": ab.get("id") or ab.get("name"),
                    "name": ab.get("name"),
                    "cost": ab.get("cost", 0),
                    "effect": ab.get("effect"),
                })

        # Keep legacy options so older UIs using `choice` still function.
        options = [
            {"id": "interrupt_no", "label": "Do not interrupt"},
            {"id": "interrupt_yes", "label": "Interrupt enemy action"},
        ]

        # Don't auto-dismiss; the player must explicitly Endure or pick an interrupt ability.
        state["suppress_chain_interrupt"] = True
        emit_event(ui, {"type": "clear", "target": "choices"})
        emit_event(ui, {"type": "interrupt_window", "abilities": defense_abilities})
        state["awaiting"] = {"type": "enemy_interrupt", "options": options, "abilities": defense_abilities}
        return True

    # Prompt (CLI/blocking)
    if pending is None and getattr(ui, "is_blocking", True):
        idx = ui.choice("Interrupt the enemy before they act?", ["No", "Interrupt"])
        pending = (idx == 1)

    # Minimal contest (no damage yet): player attempts to cancel the enemy's action.
    if pending:
        from engine.stats import stat_mod

        player_res = player.get("resources", {}) or {}
        momentum = combat_get(state, player, "momentum", player_res.get("momentum", 0) or 0)
        idf = player_res.get("idf", 0) or 0

        chosen_id = state.pop("pending_interrupt_ability", None)
        chosen = None
        if chosen_id:
            for ab in player.get("abilities", []) or []:
                if ab.get("id") == chosen_id or ab.get("name") == chosen_id:
                    chosen = ab
                    break

        # Ability-driven interrupt bonus (simple, tweakable):
        # - If player picked a defensive ability, add its stat mod (if any) to the interrupt roll
        # - Spend resolve + set cooldown like a normal use
        ab_bonus = 0
        if isinstance(chosen, dict):
            stat_key = chosen.get("stat")
            attrs = player.get("attributes") or player.get("stats") or {}
            if stat_key and stat_key in attrs:
                try:
                    ab_bonus += stat_mod(int(attrs.get(stat_key) or 0))
                except Exception:
                    pass

            cost = chosen.get("cost", 0) or 0
            if cost:
                cur_rp = combat_get(state, player, "rp", int(player_res.get("resolve", 0) or 0))
                new_rp = max(0, int(cur_rp) - int(cost))
                combat_set(state, player, "rp", new_rp)
                player_res["resolve"] = new_rp

            base_cd = chosen.get("base_cooldown")
            if base_cd is None:
                base_cd = chosen.get("cooldown", 0)
            try:
                base_cd = int(base_cd or 0)
            except Exception:
                base_cd = 0
            chosen["base_cooldown"] = base_cd
            chosen["cooldown"] = base_cd

            emit_combat_log(ui, f"Interrupt ability: {chosen.get('name')} (bonus {ab_bonus})", "system")

        p_d20 = roll("1d20")
        p_roll = p_d20 + int(idf) + int(momentum) + int(ab_bonus)
        defense = (enemy.get("stat_block", {}) or {}).get("defense", {})
        dv = enemy.get("dv_base", defense.get("dv_base", 10))
        e_d20 = roll("1d20")
        e_roll = e_d20 + (dv or 0)
        emit_combat_log(ui, f"Interrupt contest: player {p_roll} (d20 {p_d20}) vs enemy {e_roll} (d20 {e_d20})", "roll")
        if p_roll >= e_roll:
            emit_interrupt(ui)
            emit_combat_log(ui, "Player interrupt!", "interrupt")
            emit_combat_log(ui, "You cut the enemy's rhythm. Their action is denied.", "system")
            from ui.events import emit_event
            emit_event(ui, {"type": "chain_interrupted", "text": "Enemy chain interrupted."})
            state["active_combatant"] = "player"
            state["phase"]["current"] = "chain_declaration"
            if not getattr(ui, "is_blocking", True):
                reopen_chain_builder(state, ui)
            return True
        emit_combat_log(ui, "Interrupt failed. Enemy acts.", "system")

    # Enemy declares a simple one-move chain (first attack move)
    enemy_chain = []
    for mv in enemy.get("moves", []):
        if mv.get("type") == "attack":
            enemy_chain.append(mv.get("name") or mv.get("id"))
            break
    if not enemy_chain:
        state["active_combatant"] = "player"
        state["phase"]["current"] = "chain_declaration"
        if not getattr(ui, "is_blocking", True):
            reopen_chain_builder(state, ui)
        return True

    emit_combat_log(ui, f"{enemy.get('name','Enemy')} declares: {', '.join(enemy_chain)}", "system")
    enemy.setdefault("chain", {})
    enemy["chain"]["abilities"] = enemy_chain
    enemy["chain"]["declared"] = True
    state["active_combatant"] = "enemy"
    state["phase"]["current"] = "chain_resolution"
    # In web mode, resolve immediately so the response includes the enemy action and then returns to player prompt.
    if not getattr(ui, "is_blocking", True):
        return handle_chain_resolution(ctx)
    return True


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

def reopen_chain_builder(state, ui, prompt="Build your next chain?", max_len=None):
    usable_objs = usable_ability_objects(state)
    state["phase"]["current"] = "chain_declaration"
    state["phase"]["round_started"] = False
    emit_declare_chain(ui, usable_objs, max_len=max_len or state.get("phase", {}).get("chain_max", 6) or 6)
    if prompt:
        ui.choice(prompt, ["Build chain"])
    state["awaiting"] = {"type": "chain_builder", "options": usable_objs}
    return usable_objs

def resolve_awaiting(state, ui, player_input):
    """
    Handle any pending awaiting payloads.
    Returns (resolved_choice, should_return_early).
    """
    resolved_choice = None
    should_return = False

    # Web-safe: chain interrupt decisions are action-based (not choice-index-based).
    if isinstance(state.get("awaiting"), dict) and isinstance(player_input, dict):
        awaiting = state.get("awaiting", {})
        if awaiting.get("type") == "chain_interrupt":
            act = player_input.get("action")
            if act == "interrupt_skip":
                state.pop("awaiting", None)
                state["pending_chain_interrupt"] = False
                # Continue game_step so chain resolution can resume in this same /step.
                should_return = False
            if act == "interrupt":
                state.pop("awaiting", None)
                state["pending_chain_interrupt"] = True
                if player_input.get("ability"):
                    state["pending_interrupt_ability"] = player_input["ability"]
                should_return = False

    if (
        "awaiting" in state
        and isinstance(player_input, dict)
        and "choice" in player_input
        and isinstance(player_input.get("choice"), int)
    ):
        awaiting = state.pop("awaiting")
        idx = player_input["choice"]

        if awaiting["type"] == "player_choice":
            if isinstance(idx, int) and 0 <= idx < len(awaiting["options"]):
                resolved_choice = awaiting["options"][idx]
            else:
                ui.error("Invalid choice selection.")
                should_return = True
        elif awaiting["type"] == "chain_declaration":
            if isinstance(idx, int) and 0 <= idx < len(awaiting["options"]):
                resolved_choice = [awaiting["options"][idx]]
            else:
                ui.error("Invalid chain selection.")
                should_return = True
        elif awaiting["type"] == "chain_builder":
            # handled via action "declare_chain"
            state["awaiting"] = awaiting  # restore; action handler will pop
        elif awaiting["type"] == "defense_pick":
            if isinstance(idx, int) and 0 <= idx < len(awaiting["options"]):
                state["pending_defense"] = awaiting["options"][idx]
            else:
                ui.error("Invalid defense selection.")
                should_return = True
        elif awaiting["type"] == "enemy_interrupt":
            if isinstance(idx, int) and 0 <= idx < len(awaiting["options"]):
                option = awaiting["options"][idx]
                option_id = option.get("id")

                # Normalize to a boolean interrupt decision
                if option_id == "interrupt_yes":
                    state["pending_enemy_interrupt"] = True
                else:
                    state["pending_enemy_interrupt"] = False
            else:
                ui.error("Invalid interrupt selection.")
                should_return = True
        elif awaiting["type"] == "chain_interrupt":
            if isinstance(idx, int) and 0 <= idx < len(awaiting["options"]):
                option = awaiting["options"][idx]
                option_id = option.get("id")
                state["pending_chain_interrupt"] = (option_id == "interrupt_yes")
            else:
                ui.error("Invalid interrupt selection.")
                should_return = True
        elif awaiting["type"] == "press_window":
            if isinstance(idx, int) and 0 <= idx < len(awaiting["options"]):
                option = awaiting["options"][idx]
                option_id = option.get("id")
                state["pending_press_decision"] = option_id
            else:
                ui.error("Invalid press selection.")
                should_return = True

        norm_choice = resolved_choice.lower().replace(" ", "_") if isinstance(resolved_choice, str) else resolved_choice
        if norm_choice == "build_chain":
            reopen_chain_builder(state, ui)
            should_return = True

    return resolved_choice, should_return

def maybe_start_round(ctx):
    state = ctx["state"]
    ui = ctx["ui"]
    if state["phase"]["current"] == "chain_declaration" and not state["phase"].get("round_started"):
        state["phase"]["round"] += 1
        round_upkeep(state)
        state["phase"]["round_started"] = True
        # push updated resources after upkeep for web
        if not getattr(ui, "is_blocking", True):
            ch = state["party"]["members"][0]
            res = ch.get("resources", {})
            rp_cur = combat_get(state, ch, "rp", res.get("resolve", 0))
            rp_cap = combat_get(state, ch, "rp_cap", res.get("resolve_cap", rp_cur))
            emit_character_update(ui, {
                "hp": {"current": res.get("hp"), "max": res.get("hp_max", res.get("max_hp", res.get("maxHp", res.get("hp"))))},
                "rp": rp_cur,
                "rp_cap": rp_cap,
                "veinscore": res.get("veinscore", 0),
                "attributes": ch.get("attributes", {}),
                "name": ch.get("name"),
                "abilities": ch.get("abilities", []),
                "meters": {
                    "momentum": combat_get(state, ch, "momentum", res.get("momentum", 0)),
                    "balance": combat_get(state, ch, "balance", res.get("balance", 0)),
                    "heat": combat_get(state, ch, "heat", res.get("heat", 0)),
                },
            })
            emit_resource_update(
                ui,
                momentum=combat_get(state, ch, "momentum", res.get("momentum", 0)),
                balance=combat_get(state, ch, "balance", res.get("balance", 0)),
                heat=combat_get(state, ch, "heat", res.get("heat", 0)),
            )

def handle_start_action(ctx, requested_action):
    state = ctx["state"]
    ui = ctx["ui"]
    if requested_action == "start" and not getattr(ui, "is_blocking", True):
        reopen_chain_builder(state, ui, max_len=3)
        return True
    return None

def handle_declare_chain_action(ctx, player_input, requested_action):
    state = ctx["state"]
    ui = ctx["ui"]
    if not (isinstance(player_input, dict) and requested_action == "declare_chain"):
        return None

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
        emit_event(ui, {"type": "chain_rejected", "reason": resp})
        reopen_chain_builder(state, ui, max_len=state.get("phase", {}).get("chain_max", 6) or 6)
        return True
    for ability in character.get("abilities", []):
        if ability.get("name") in names:
            cd = ability.get("base_cooldown", ability.get("cooldown", 0) or 0)
            ability["base_cooldown"] = cd
            ability["cooldown"] = cd
            ability["cooldown_round"] = state["phase"]["round"] + cd if cd else state["phase"]["round"]
    state["phase"]["current"] = "chain_resolution"
    state.pop("awaiting", None)
    # For web/non-blocking, immediately proceed into resolution so we don't get stuck waiting.
    if not getattr(ui, "is_blocking", True):
        return game_step(ctx, {"action": "tick"})
    return True

def maybe_delegate_combat(ctx, player_input):
    state = ctx["state"]
    combat = ctx.get("combat")
    if combat and state["phase"]["current"] in ("chain_declaration", "chain_resolution"):
        handled = combat.step(player_input if isinstance(player_input, dict) else {})
        if handled is not None:
            return handled
    return None

def maybe_auto_chain_prompt(ctx):
    state = ctx["state"]
    ui = ctx["ui"]
    current_phase = state["phase"]["current"]
    if current_phase == "chain_declaration" and not getattr(ui, "is_blocking", True) and "awaiting" not in state:
        append_log(f"DEBUG: auto chain prompt (phase={current_phase}, round={state['phase'].get('round')}, awaiting=None)")
        reopen_chain_builder(state, ui)
        return True
    return None

def choose_action(ctx, actions, resolved_choice, requested_action, auto_mode, interactive_defaults, nonarrate):
    state = ctx["state"]
    ui = ctx["ui"]
    if not (nonarrate or interactive_defaults):
        try:
            narrate(state, actions)
        except Exception as e:
            ui.error(f"[Narrator error: {e}]")
    else:
        ui.system("\n(Narration suppressed)")

    if resolved_choice is not None:
        return resolved_choice
    if requested_action in actions:
        return requested_action
    if auto_mode:
        choice = actions[0] if actions else "exit"
        ui.system(f"Auto choice: {choice}")
        return choice
    choice = get_player_choice(actions, ui, state)
    return choice



def game_step(ctx, player_input):
    state = ctx["state"]
    ui = ctx["ui"]
    phase_machine = ctx["phase_machine"]
    game_data = ctx["game_data"]
    args = ctx.get("args")

    resolved_choice, should_return = resolve_awaiting(state, ui, player_input)
    if should_return:
        return True


    nonarrate = not args.narrate if args else True
    interactive_defaults = args.interactive_defaults if args else False
    auto_mode = args.auto if args else False

    # Requested action (needed even when combat_over is set)
    requested_action = player_input.get("action") if isinstance(player_input, dict) else None

    if state.get("combat_over"):
        from ui.events import emit_event

        def _hp(entity):
            if not isinstance(entity, dict):
                return 0
            hp_val = entity.get("hp")
            if isinstance(hp_val, dict):
                return int(hp_val.get("current", hp_val.get("hp", 0)) or 0)
            if isinstance(entity.get("resources"), dict) and entity["resources"].get("hp") is not None:
                return int(entity["resources"].get("hp") or 0)
            return int(hp_val or 0)

        if requested_action == "combat_continue":
            state["combat_over"] = False
            state.pop("awaiting", None)
            state["phase"]["current"] = "out_of_combat"
            state.pop("encounter", None)
            emit_combat_state(ui, False)
            ui.system("Continuing...")
            return True

        player = state.get("party", {}).get("members", [None])[0]
        enemy = state.get("enemies", [None])[0] if state.get("enemies") else None
        player_dead = _hp(player) <= 0 if player else False
        enemy_dead = _hp(enemy) <= 0 if enemy else False
        result = "defeat" if player_dead else "victory" if enemy_dead else "ended"

        emit_combat_state(ui, False)
        state["phase"]["current"] = "out_of_combat"
        state.pop("awaiting", None)
        ui.system("Combat over.")
        emit_event(ui, {"type": "combat_result", "result": result})
        return True

    maybe_start_round(ctx)
    start_handled = handle_start_action(ctx, requested_action)
    if start_handled is not None:
        return start_handled

    declare_chain_handled = handle_declare_chain_action(ctx, player_input, requested_action)
    if declare_chain_handled is not None:
        return declare_chain_handled


    current_phase = state["phase"]["current"]
    combat_handled = maybe_delegate_combat(ctx, player_input)
    if combat_handled is not None:
        return combat_handled

    auto_prompt_handled = maybe_auto_chain_prompt(ctx)
    if auto_prompt_handled is not None:
        return auto_prompt_handled


    if current_phase == "chain_declaration":
        handled = handle_chain_declaration(ctx, player_input)
        if handled is not None:
            return handled
    if current_phase == "enemy_turn":
        handled = handle_enemy_turn(ctx, player_input if isinstance(player_input, dict) else {})
        if handled is not None:
            return handled
    if current_phase == "chain_resolution":
        handled = handle_chain_resolution(ctx)
        if handled is not None:
            return handled
    # For non-blocking UIs, if we're waiting on any prompt, do not surface generic action lists.
    if not getattr(ui, "is_blocking", True) and "awaiting" in state:
        return True


    actions = allowed_actions(state, phase_machine)

    choice = choose_action(ctx, actions, resolved_choice, requested_action, auto_mode, interactive_defaults, nonarrate)
    if choice is None:
        return True

    # Web helper: explicit build_chain choice should reopen chain builder instead of falling through to phase actions.
    choice_norm = choice.lower().replace(" ", "_") if isinstance(choice, str) else choice
    if choice_norm == "build_chain":
        usable_objs = usable_ability_objects(state)
        state["phase"]["current"] = "chain_declaration"
        state["phase"]["round_started"] = False
        emit_declare_chain(ui, usable_objs, max_len=state.get("phase", {}).get("chain_max", 6) or 6)
        state["awaiting"] = {"type": "chain_builder", "options": usable_objs}
        return True
    if choice == "exit":
        ui.system("Exiting Veinbreaker AI session.")
        return False
    prev_phase = state["phase"]["current"]
    apply_action(state, choice)
    if choice in ("enter_encounter", "generate_encounter" ):
        if state.get("enemies"):
            enemy = state["enemies"][0]
            # Encounter-scoped combat meters (heat/balance/momentum)
            player = state.get("party", {}).get("members", [None])[0]
            if choice == "enter_encounter" and player and enemy:
                try:
                    register_participant(state, key="player", entity=player, side="player")
                    register_participant(state, key="enemy0", entity=enemy, side="enemy")
                except Exception:
                    pass

            emit_combat_state(ui, True)
            # Emit preview only on generate, not on enter (avoid duplicate log/system spam)
            if choice == "generate_encounter":
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
                            "momentum": combat_get(state, player, "momentum", state["party"]["members"][0]["resources"].get("momentum", 0)),
                            "heat": combat_get(state, player, "heat", state["party"]["members"][0]["resources"].get("heat", 0)),
                            "balance": combat_get(state, player, "balance", state["party"]["members"][0]["resources"].get("balance", 0)),
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
        # Web: surface chain builder only when actually entering combat, not when just generating
        if not getattr(ui, "is_blocking", True) and choice == "enter_encounter":
            if not ctx.get("combat"):
                ctx["combat"] = Combat(ctx, handle_chain_declaration, handle_chain_resolution, usable_ability_objects)
            ctx["combat"].start()
            return True

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
