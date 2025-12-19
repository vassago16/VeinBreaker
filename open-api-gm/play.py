import json
import os
import argparse
from pathlib import Path
import pdb
import random


from engine.chain_resolution_engine import ChainResolutionEngine, ChainResult
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
from engine.save_load import save_character, load_character, load_profile
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
from engine.combat_state import register_participant, combat_get, combat_set, status_get

import debugpy



LOG_FILE = Path(__file__).parent / "narration.log"
DEFAULT_CHARACTER_PATH = Path(__file__).parent / "default_character.json"
PROFILE_PATH = Path(__file__).parent / "character.json"
PLAYER_STATE_PATH = Path(__file__).parent / "player_state.json"
CHARACTERS_DIR = Path(__file__).parent / "characters"
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
    """
    Load the default character.

    New model:
      - `character.json` is a profile (static, abilities are ids)
      - `player_state.json` is mutable runtime state (resources/pools/cooldowns)

    Back-compat:
      - if a legacy `character.json` includes full ability dicts/resources, we accept it.
      - if files are missing, fallback to `default_character.json` then a built-in template.
    """
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
    def _load_json(path: Path) -> dict | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    # If player state specifies a character_id, load that profile from `characters/<id>.json`.
    selected_profile = None
    try:
        state_blob = _load_json(PLAYER_STATE_PATH) or {}
        if isinstance(state_blob, dict):
            cid = state_blob.get("character_id")
            if cid:
                selected_profile = _load_json(CHARACTERS_DIR / f"{cid}.json")
    except Exception:
        selected_profile = None

    profile = selected_profile or _load_json(PROFILE_PATH)
    if profile:
        # If this is a legacy full character file, just return it.
        abilities = profile.get("abilities", [])
        if isinstance(abilities, list) and abilities and isinstance(abilities[0], dict):
            return profile

        merged = dict(profile)
        state = _load_json(PLAYER_STATE_PATH) or {}
        cooldowns = state.get("cooldowns") if isinstance(state.get("cooldowns"), dict) else {}
        merged["_cooldowns"] = cooldowns
        merged["_veins_spent_total"] = int(state.get("veins_spent_total", 0) or 0) if isinstance(state, dict) else 0
        # Merge mutable pieces from player_state.json if present
        if isinstance(state.get("resources"), dict):
            merged["resources"] = dict(state["resources"])
        if isinstance(state.get("pools"), dict):
            merged["pools"] = dict(state["pools"])
        if isinstance(state.get("marks"), dict):
            merged["marks"] = dict(state["marks"])
        if state.get("veinscore") is not None:
            merged["veinscore"] = state.get("veinscore")
        # Ensure chain scaffold exists (engine expects it).
        merged.setdefault("chain", {"declared": False, "abilities": [], "resolve_spent": 0, "stable": False, "invalidated": False})
        return merged

    # Fallback: old default file if present
    legacy_default = _load_json(DEFAULT_CHARACTER_PATH)
    if legacy_default:
        return legacy_default

    return fallback


def hydrate_character_abilities(character: dict, game_data: dict) -> None:
    """
    Convert `character["abilities"]` from ids into runtime ability dicts using game data.
    Also applies cooldown overrides from `character["_cooldowns"]` if present.
    """
    if not isinstance(character, dict) or not isinstance(game_data, dict):
        return

    abilities = character.get("abilities", [])
    if not isinstance(abilities, list):
        return

    pool_map = game_data.get("abilities", {}).get("poolByPath", {}) if isinstance(game_data.get("abilities"), dict) else {}
    gd_abilities = (game_data.get("abilities", {}) or {}).get("abilities", [])
    gd_resolve = (game_data.get("resolve_abilities", {}) or {}).get("abilities", [])
    catalog = [a for a in (gd_abilities + gd_resolve) if isinstance(a, dict)]
    by_id = {a.get("id"): a for a in catalog if a.get("id")}
    by_name = {a.get("name"): a for a in catalog if a.get("name")}

    cooldowns = character.pop("_cooldowns", None)
    cooldowns = cooldowns if isinstance(cooldowns, dict) else {}

    runtime: list[dict] = []
    for entry in abilities:
        if isinstance(entry, str):
            src = by_id.get(entry) or by_name.get(entry)
            if not src:
                continue
            ab = {"id": src.get("id") or entry, "name": src.get("name") or entry}
            for key in ["effect", "cost", "dice", "stat", "tags", "path", "tier", "type", "effects", "to_hit", "resourceDelta", "resolution"]:
                if key in src:
                    ab[key] = src[key]
            # base cooldown lives in game data `cooldown`
            ab["base_cooldown"] = int(src.get("cooldown", 0) or 0)
            ab["cooldown"] = 0
            # Pool: either explicit on src or derived from path
            if src.get("pool"):
                ab["pool"] = src.get("pool")
            else:
                path = ab.get("path")
                if path and path in pool_map:
                    ab["pool"] = pool_map[path]
            # Apply persisted cooldown overrides
            cd_state = cooldowns.get(ab["id"]) or cooldowns.get(ab["name"])
            if isinstance(cd_state, dict):
                if cd_state.get("cooldown") is not None:
                    ab["cooldown"] = int(cd_state.get("cooldown") or 0)
                if cd_state.get("base_cooldown") is not None:
                    ab["base_cooldown"] = int(cd_state.get("base_cooldown") or 0)
                if cd_state.get("cooldown_round") is not None:
                    ab["cooldown_round"] = int(cd_state.get("cooldown_round") or 0)
            runtime.append(ab)
            continue

        if isinstance(entry, dict):
            # Legacy/runtime ability dict; hydrate missing fields from catalog.
            src = by_id.get(entry.get("id")) or by_name.get(entry.get("name"))
            if src:
                for key in ["effect", "cost", "dice", "stat", "tags", "path", "tier", "type", "effects", "to_hit", "resourceDelta", "resolution"]:
                    if key not in entry and key in src:
                        entry[key] = src[key]
                if "base_cooldown" not in entry:
                    entry["base_cooldown"] = int(src.get("cooldown", entry.get("cooldown", 0) or 0) or 0)
            runtime.append(entry)
            continue

    character["abilities"] = runtime


def _character_id_from_name(name: str) -> str:
    s = "".join(ch.lower() if ch.isalnum() else "_" for ch in (name or "").strip())
    s = "_".join([p for p in s.split("_") if p])
    return f"character.{s}" if s else "character.unknown"


def split_profile_and_state(character: dict) -> tuple[dict, dict]:
    """
    Convert a runtime/legacy character dict into:
      - profile: static fields + ability ids
      - state: mutable resources/pools/cooldowns
    """
    if not isinstance(character, dict):
        return {}, {}

    name = character.get("name") or "New Blood"
    profile = {
        "id": character.get("id") or _character_id_from_name(str(name)),
        "name": name,
        "path": character.get("path"),
        "tier": character.get("tier", 1),
        "attributes": character.get("attributes") or character.get("stats") or {},
        "abilities": [],
    }

    abilities = character.get("abilities", [])
    if isinstance(abilities, list):
        for ab in abilities:
            if isinstance(ab, str):
                profile["abilities"].append(ab)
            elif isinstance(ab, dict):
                profile["abilities"].append(ab.get("id") or ab.get("name"))
    profile["abilities"] = [a for a in profile["abilities"] if a]

    resources = character.get("resources") if isinstance(character.get("resources"), dict) else {}
    pools = character.get("pools") if isinstance(character.get("pools"), dict) else {}
    marks = character.get("marks") if isinstance(character.get("marks"), dict) else {}

    cooldowns: dict[str, dict] = {}
    if isinstance(abilities, list):
        for ab in abilities:
            if not isinstance(ab, dict):
                continue
            aid = ab.get("id") or ab.get("name")
            if not aid:
                continue
            cooldowns[aid] = {
                "cooldown": int(ab.get("cooldown", 0) or 0),
            }
            if ab.get("base_cooldown") is not None:
                cooldowns[aid]["base_cooldown"] = int(ab.get("base_cooldown") or 0)
            if ab.get("cooldown_round") is not None:
                cooldowns[aid]["cooldown_round"] = int(ab.get("cooldown_round") or 0)

    # Normalize hp into hp/hp_max ints for state.
    hp_val = resources.get("hp") if isinstance(resources, dict) else None
    hp_max = resources.get("hp_max", resources.get("max_hp", resources.get("maxHp"))) if isinstance(resources, dict) else None
    if isinstance(hp_val, dict):
        hp_cur = hp_val.get("current") or hp_val.get("hp")
        hp_max = hp_val.get("max") or hp_max or hp_cur
    else:
        hp_cur = hp_val
    state = {
        "character_id": profile["id"],
        "resources": {
            "hp": int(hp_cur or 0),
            "hp_max": int(hp_max or hp_cur or 0),
            "resolve": int(resources.get("resolve", character.get("rp", 0)) or 0) if isinstance(resources, dict) else int(character.get("rp", 0) or 0),
            "resolve_cap": int(resources.get("resolve_cap", character.get("rp_cap", 0)) or 0) if isinstance(resources, dict) else int(character.get("rp_cap", 0) or 0),
            "idf": int(resources.get("idf", 0) or 0) if isinstance(resources, dict) else int(character.get("idf", 0) or 0),
        },
        "pools": dict(pools) if isinstance(pools, dict) else {},
        "marks": dict(marks) if isinstance(marks, dict) else {},
        "veinscore": character.get("veinscore", 0),
        "veins_spent_total": int(character.get("_veins_spent_total", 0) or 0),
        "cooldowns": cooldowns,
    }
    return profile, state


def save_profile_and_state(character: dict) -> None:
    profile, state = split_profile_and_state(character)
    if profile:
        CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
        (CHARACTERS_DIR / f"{profile.get('id') or 'character.unknown'}.json").write_text(
            json.dumps(profile, indent=2),
            encoding="utf-8",
        )
        # Keep the legacy `character.json` updated as a fallback.
        PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    if state:
        PLAYER_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def is_safe_room(state: dict) -> bool:
    env = state.get("environment") if isinstance(state.get("environment"), dict) else {}
    if isinstance(env, dict) and env.get("id") == "env.safe.room":
        return True
    scene = state.get("scene") if isinstance(state.get("scene"), dict) else {}
    env_id = ((scene.get("environment") or {}) if isinstance(scene.get("environment"), dict) else {}).get("id")
    return str(env_id) == "env.safe.room"


def _safe_room_cost(ability: dict) -> int:
    try:
        tier = int(ability.get("tier", 1) or 1)
    except Exception:
        tier = 1
    return max(1, tier)


# Vein-driven tier progression (simple rule table).
# Thresholds represent total Vein ever spent (veins_spent_total / _veins_spent_total).
VEIN_TIER_THRESHOLDS: list[tuple[int, int]] = [
    (1, 0),
    (2, 10),
    (3, 25),
    (4, 45),
]


def tier_from_veins_spent(veins_spent_total: int, *, base_tier: int = 1) -> int:
    try:
        spent = int(veins_spent_total or 0)
    except Exception:
        spent = 0
    tier = int(base_tier or 1)
    for t, req in VEIN_TIER_THRESHOLDS:
        if spent >= int(req):
            tier = int(t)
    return max(int(base_tier or 1), tier)


def apply_vein_tier_progression(character: dict) -> bool:
    """
    Auto-increment character tier based on total veins spent.
    Returns True if the tier increased.
    """
    if not isinstance(character, dict):
        return False
    before = int(character.get("tier", 1) or 1)
    spent = int(character.get("_veins_spent_total", 0) or 0)
    after = tier_from_veins_spent(spent, base_tier=before)
    if after > before:
        character["tier"] = after
        return True
    return False


def safe_room_progression_payload(character: dict) -> dict:
    if not isinstance(character, dict):
        return {}
    spent = int(character.get("_veins_spent_total", 0) or 0)
    tier = int(character.get("tier", 1) or 1)

    next_tier = None
    next_req = None
    for t, req in VEIN_TIER_THRESHOLDS:
        if int(t) > tier:
            next_tier = int(t)
            next_req = int(req)
            break

    if next_tier is None or next_req is None:
        return {
            "tier": tier,
            "veins_spent_total": spent,
            "next_tier": None,
            "next_unlock_at": None,
            "remaining": 0,
        }

    return {
        "tier": tier,
        "veins_spent_total": spent,
        "next_tier": next_tier,
        "next_unlock_at": next_req,
        "remaining": max(0, int(next_req) - int(spent)),
    }


def build_safe_room_offers(character: dict, game_data: dict) -> list[dict]:
    """
    Offers are abilities at character tier or below that the character does not already own.
    """
    if not isinstance(character, dict) or not isinstance(game_data, dict):
        return []

    try:
        tier_cap = int(character.get("tier", 1) or 1)
    except Exception:
        tier_cap = 1

    owned_ids: set[str] = set()
    for ab in character.get("abilities", []) or []:
        if isinstance(ab, str):
            owned_ids.add(ab)
        elif isinstance(ab, dict):
            if ab.get("id"):
                owned_ids.add(str(ab["id"]))

    gd_abilities = (game_data.get("abilities", {}) or {}).get("abilities", [])
    if not isinstance(gd_abilities, list):
        return []

    offers: list[dict] = []
    for ab in gd_abilities:
        if not isinstance(ab, dict):
            continue
        aid = ab.get("id")
        if not aid or aid in owned_ids:
            continue
        try:
            t = int(ab.get("tier", 0) or 0)
        except Exception:
            t = 0
        if t <= tier_cap:
            offers.append({
                "id": aid,
                "name": ab.get("name", aid),
                "tier": t,
                "path": ab.get("path"),
                "type": ab.get("type"),
                "cost": _safe_room_cost(ab),
                "effect": ab.get("effect") or "",
            })

    # Stable sort by tier then name
    offers.sort(key=lambda o: (int(o.get("tier", 0) or 0), str(o.get("name") or "")))
    return offers


def emit_safe_room_enter(ctx: dict) -> None:
    state = ctx["state"]
    ui = ctx["ui"]
    game_data = ctx.get("game_data") or {}
    ch = state.get("party", {}).get("members", [None])[0]
    if not isinstance(ch, dict):
        return
    # Ensure tier progression is reflected in safe-room offers.
    apply_vein_tier_progression(ch)
    res = ch.get("resources", {}) if isinstance(ch.get("resources"), dict) else {}
    offers = build_safe_room_offers(ch, game_data)
    emit_event(ui, {
        "type": "safe_room_enter",
        "mode": "safe_room",
        "scene": state.get("scene_id"),
        "environment": (state.get("environment") or {}).get("id") if isinstance(state.get("environment"), dict) else None,
        "character": {
            "id": ch.get("id"),
            "name": ch.get("name"),
            "tier": ch.get("tier"),
            "veinscore": res.get("veinscore", ch.get("veinscore", 0)),
            "veins_spent_total": int(ch.get("_veins_spent_total", 0) or 0),
            "abilities": [a.get("id") if isinstance(a, dict) else a for a in (ch.get("abilities") or [])],
        },
        "progression": safe_room_progression_payload(ch),
        "rest_result": state.get("safe_room_last_rest") if isinstance(state.get("safe_room_last_rest"), dict) else None,
        "shop": {
            "currency": "veinscore",
            "offers": offers,
        }
    })


CHARACTER_CREATE_PATHS = [
    {"id": "stonepulse", "label": "Stone", "stat": "POW"},
    {"id": "hemocratic", "label": "Shadow", "stat": "AGI"},
    {"id": "spellforged", "label": "Magic", "stat": "MND"},
    {"id": "canticle", "label": "Canticle", "stat": "SPR"},
]


def _create_base_attributes() -> dict:
    return {"POW": 8, "AGI": 8, "MND": 8, "SPR": 8}


def _create_draft_character(*, path_id: str | None = None) -> dict:
    attrs = _create_base_attributes()
    if path_id:
        for p in CHARACTER_CREATE_PATHS:
            if p["id"] == path_id:
                attrs[p["stat"]] = int(attrs.get(p["stat"], 8) or 8) + 2
                break

    return {
        "id": "character.draft",
        "name": "New Blood",
        "path": path_id,
        "tier": 1,
        "attributes": attrs,
        "resources": {
            "hp": 28,
            "hp_max": 28,
            "resolve": 5,
            "resolve_cap": 5,
            "idf": 0,
            "veinscore": 3,
        },
        "pools": {},
        "marks": {"blood": 0, "duns": 0},
        "_veins_spent_total": 0,
        # start as ability ids; hydrate later
        "abilities": [],
    }


def _starter_ability_ids_for_path(path_id: str | None, game_data: dict) -> list[str]:
    base = ["core.basic_strike", "core.basic_guard", "core.focus_action", "core.shift"]
    if not path_id:
        return base
    out = list(base)
    try:
        gd_abilities = (game_data.get("abilities", {}) or {}).get("abilities", [])
    except Exception:
        gd_abilities = []
    if isinstance(gd_abilities, list):
        for ab in gd_abilities:
            if not isinstance(ab, dict):
                continue
            if ab.get("path") != path_id:
                continue
            try:
                t = int(ab.get("tier", 99) or 99)
            except Exception:
                t = 99
            if t == 1 and ab.get("id"):
                out.append(str(ab["id"]))
    # stable unique
    seen = set()
    uniq = []
    for a in out:
        if a and a not in seen:
            uniq.append(a)
            seen.add(a)
    return uniq


def _resolve_ability_catalog(game_data: dict) -> list[dict]:
    ra = (game_data.get("resolve_abilities", {}) or {}).get("abilities", [])
    return ra if isinstance(ra, list) else []


def build_character_create_offers(character: dict, game_data: dict) -> list[dict]:
    """
    Character creation shop: any tier 1 ability (any path), excluding already-owned.
    """
    if not isinstance(character, dict) or not isinstance(game_data, dict):
        return []
    owned_ids: set[str] = set()
    for ab in character.get("abilities", []) or []:
        if isinstance(ab, str):
            owned_ids.add(ab)
        elif isinstance(ab, dict) and ab.get("id"):
            owned_ids.add(str(ab["id"]))

    gd_abilities = (game_data.get("abilities", {}) or {}).get("abilities", [])
    if not isinstance(gd_abilities, list):
        return []
    offers: list[dict] = []
    for ab in gd_abilities:
        if not isinstance(ab, dict):
            continue
        aid = ab.get("id")
        if not aid or aid in owned_ids:
            continue
        try:
            t = int(ab.get("tier", 0) or 0)
        except Exception:
            t = 0
        if t != 1:
            continue
        offers.append({
            "id": aid,
            "name": ab.get("name", aid),
            "tier": t,
            "path": ab.get("path"),
            "type": ab.get("type"),
            "cost": 1,
            "effect": ab.get("effect") or "",
        })
    offers.sort(key=lambda o: (str(o.get("path") or ""), str(o.get("name") or "")))
    return offers


def emit_character_create(ctx: dict) -> None:
    state = ctx["state"]
    ui = ctx["ui"]
    game_data = ctx.get("game_data") or {}
    draft = state.get("character_create") if isinstance(state.get("character_create"), dict) else {}
    stage = draft.get("stage") or "choose_path"
    ch = draft.get("character") if isinstance(draft.get("character"), dict) else None
    if not isinstance(ch, dict):
        return

    # Keep pools derived from attributes for display consistency.
    try:
        _refill_pools_to_cap(ch)
    except Exception:
        pass

    res = ch.get("resources", {}) if isinstance(ch.get("resources"), dict) else {}
    offers = build_character_create_offers(ch, game_data) if stage == "shop" else []
    rp_catalog = _resolve_ability_catalog(game_data)

    emit_event(ui, {
        "type": "safe_room_enter",
        "mode": "character_create",
        "stage": stage,
        "character": {
            "id": ch.get("id"),
            "name": ch.get("name"),
            "tier": ch.get("tier"),
            "path": ch.get("path"),
            "veinscore": res.get("veinscore", 0),
            "veins_spent_total": int(ch.get("_veins_spent_total", 0) or 0),
            "abilities": [a.get("id") if isinstance(a, dict) else a for a in (ch.get("abilities") or [])],
        },
        "create": {
            "paths": CHARACTER_CREATE_PATHS,
            "rp_abilities": [
                {
                    "id": a.get("id") or a.get("name"),
                    "name": a.get("name"),
                    "cost": a.get("cost", 1),
                    "effect": a.get("effect") or "",
                    "path": a.get("path"),
                }
                for a in (rp_catalog or [])
                if isinstance(a, dict)
            ],
        },
        "shop": {
            "currency": "veinscore",
            "offers": offers,
        }
    })


def _refill_pools_to_cap(ch: dict) -> None:
    attrs = ch.get("attributes") or ch.get("stats") or {}
    pow_val = int(attrs.get("POW") or attrs.get("pow") or attrs.get("STR") or attrs.get("str") or 0)
    agi_val = int(attrs.get("AGI") or attrs.get("agi") or attrs.get("DEX") or attrs.get("dex") or 0)
    mnd_val = int(attrs.get("MND") or attrs.get("mnd") or attrs.get("INT") or attrs.get("int") or 0)
    spr_val = int(attrs.get("SPR") or attrs.get("spr") or attrs.get("WIL") or attrs.get("wil") or 0)
    pool_caps = {
        "martial": max(0, pow_val // 2),
        "shadow": max(0, agi_val // 2),
        "magic": max(0, mnd_val // 2),
        "faith": max(0, spr_val // 2),
    }
    pools = ch.setdefault("pools", {})
    if isinstance(pools, dict):
        for k, cap in pool_caps.items():
            pools[k] = int(cap)

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
        # Saved run: merge profile + mutable state.
        try:
            # Prefer selecting profile by `player_state.json.character_id`.
            state_blob = load_character(PLAYER_STATE_PATH.name)
            cid = state_blob.get("character_id") if isinstance(state_blob, dict) else None
            if cid:
                profile = load_profile(CHARACTERS_DIR / f"{cid}.json")
            else:
                profile = load_profile(PROFILE_PATH.name)
        except Exception:
            profile = {}
        try:
            state_blob = load_character(PLAYER_STATE_PATH.name)
        except Exception:
            state_blob = {}
        character = dict(profile) if isinstance(profile, dict) else {}
        if isinstance(state_blob, dict):
            cooldowns = state_blob.get("cooldowns") if isinstance(state_blob.get("cooldowns"), dict) else {}
            character["_cooldowns"] = cooldowns
            if isinstance(state_blob.get("resources"), dict):
                character["resources"] = dict(state_blob["resources"])
            if isinstance(state_blob.get("pools"), dict):
                character["pools"] = dict(state_blob["pools"])
            if isinstance(state_blob.get("marks"), dict):
                character["marks"] = dict(state_blob["marks"])
            if state_blob.get("veinscore") is not None:
                character["veinscore"] = state_blob.get("veinscore")
        character.setdefault("chain", {"declared": False, "abilities": [], "resolve_spent": 0, "stable": False, "invalidated": False})
    else:
        use_saved = ui.choice("Use saved character?", ["Yes", "No"]) == 0
        if use_saved:
            try:
                state_blob = load_character(PLAYER_STATE_PATH.name)
                cid = state_blob.get("character_id") if isinstance(state_blob, dict) else None
                if cid:
                    profile = load_profile(CHARACTERS_DIR / f"{cid}.json")
                else:
                    profile = load_profile(PROFILE_PATH.name)
            except Exception:
                profile = {}
            try:
                state_blob = load_character(PLAYER_STATE_PATH.name)
            except Exception:
                state_blob = {}
            character = dict(profile) if isinstance(profile, dict) else {}
            if isinstance(state_blob, dict):
                cooldowns = state_blob.get("cooldowns") if isinstance(state_blob.get("cooldowns"), dict) else {}
                character["_cooldowns"] = cooldowns
                if isinstance(state_blob.get("resources"), dict):
                    character["resources"] = dict(state_blob["resources"])
                if isinstance(state_blob.get("pools"), dict):
                    character["pools"] = dict(state_blob["pools"])
                if isinstance(state_blob.get("marks"), dict):
                    character["marks"] = dict(state_blob["marks"])
                if state_blob.get("veinscore") is not None:
                    character["veinscore"] = state_blob.get("veinscore")
            character.setdefault("chain", {"declared": False, "abilities": [], "resolve_spent": 0, "stable": False, "invalidated": False})
        else:
            character = run_character_creation(
                canon,
                narrator=None,  # or narrator_stub if you want flavor text
                ui=ui,
            )
            # Persist new character as profile + state (web-first model).
            save_profile_and_state(character)

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
    hydrate_character_abilities(state["party"]["members"][0], game_data)

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
    # Reset pools at the start of the player's turn (current rule).
    # Pools are derived from attributes (POW/AGI/MND/SPR) and treated as per-turn spend.
    try:
        _refill_pools_to_cap(ch)
    except Exception:
        pass
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
    # Status ticking (Bleed, radiant burn, etc.) is applied at END OF ROUND, not here.


def emit_authoritative_player_update(ui, state: dict, ch: dict) -> None:
    """
    Single authoritative UI update for the player sheet + meters.
    Avoids mixing separate `resource_update` emissions that can drift.
    """
    if getattr(ui, "is_blocking", True):
        return
    if not isinstance(state, dict) or not isinstance(ch, dict):
        return
    res = ch.get("resources", {}) if isinstance(ch.get("resources"), dict) else {}
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


def reset_encounter_meters(state: dict, *, player: dict | None = None, enemy: dict | None = None, reset_rp: bool = True) -> None:
    """
    Enforce encounter-boundary resets.
      - heat/momentum/balance -> 0 for all participants
      - resolve (rp) -> cap on encounter start (configurable)
    """
    if not isinstance(state, dict):
        return
    if not isinstance(player, dict):
        player = state.get("party", {}).get("members", [None])[0]
    if not isinstance(enemy, dict):
        enemy = state.get("enemies", [None])[0] if state.get("enemies") else None

    if isinstance(player, dict) and player.get("_combat_key"):
        combat_set(state, player, "heat", 0)
        combat_set(state, player, "momentum", 0)
        combat_set(state, player, "balance", 0)
        if reset_rp:
            res = player.get("resources", {}) if isinstance(player.get("resources"), dict) else {}
            cap = combat_get(state, player, "rp_cap", res.get("resolve_cap", res.get("resolve", 0)))
            combat_set(state, player, "rp", int(cap or 0))
            if isinstance(res, dict):
                res["resolve"] = int(cap or 0)

    if isinstance(enemy, dict) and enemy.get("_combat_key"):
        combat_set(state, enemy, "heat", 0)
        combat_set(state, enemy, "momentum", 0)
        combat_set(state, enemy, "balance", 0)

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
        # A chain of length 0 is a deliberate choice (brace/endure).
        if isinstance(aggressor.get("chain"), dict) and aggressor["chain"].get("declared"):
            emit_combat_log(ui, f"{aggressor.get('name','Combatant')} declares an empty chain.", "system")
            # Keep enemy HUD authoritative even on empty chains (no engine resolution pass).
            try:
                if not getattr(ui, "is_blocking", True) and enemies:
                    emit_enemy_update(ui, state, enemies[0])
            except Exception:
                pass
            result = ChainResult("completed", "empty_chain", 0)
            # Treat as resolved without running the engine; proceed to the same cleanup/swap logic.
            state.pop("suppress_chain_interrupt", None)
        else:
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
    cre = None
    if not chain_names:
        # result was created above for empty-chain and we skip engine resolution.
        pass
    else:
        cre = ChainResolutionEngine(
            roll_fn=roll,
            resolve_action_step_fn=resolve_action_step,
            apply_action_effects_fn=apply_action_effects,
            interrupt_policy=interrupt_policy,
            emit_log_fn=emit_combat_log,
            interrupt_apply_fn=apply_interrupt,
        )

        ui.system(f"{aggressor.get('name','Combatant')} resolves a chain...")

    # ── Combat log round/chain banners (helps readability) ─────────────────────
    try:
        round_no = int(state.get("phase", {}).get("round") or 0)
        active_side = active.upper()
        ag_name = aggressor.get("name", active_side)
        def_name = defender.get("name", "DEFENDER")

        # Begin round banner only once per round (player chain is the first half).
        if active == "player" and state.get("phase", {}).get("round_banner") != round_no:
            emit_combat_log(ui, f"BEGIN ROUND {round_no}", "system")
            state.setdefault("phase", {})["round_banner"] = round_no

        # Begin chain banner only once, even if we pause for awaiting interrupts.
        if not state.get("phase", {}).get("chain_banner_open"):
            emit_combat_log(ui, f"BEGIN {active_side} CHAIN — {ag_name} → {def_name}", "system")
            state.setdefault("phase", {})["chain_banner_open"] = True
            state["phase"]["chain_banner_side"] = active
            state["phase"]["chain_banner_round"] = round_no
    except Exception:
        pass

    # Apply any pending mid-chain execute decision.
    if active == "player" and isinstance(player.get("chain"), dict) and "pending_execute" in state:
        if bool(state.pop("pending_execute")):
            player["chain"]["execute"] = True
        else:
            player["chain"].pop("execute", None)

    start_idx = int(state.get("phase", {}).get("chain_resume_idx", 0) or 0)
    if cre is not None:
        result = cre.resolve_chain(
            state=state,
            ui=ui,
            aggressor=aggressor,
            defender=defender,
            chain_ability_names=chain_names,
            defender_group=enemies if defender is enemy else [player],
            dv_mode="per_chain",
            start_index=start_idx,
        )

    if getattr(result, "status", None) == "awaiting":
        # Pause and wait for next /step to resolve the player's interrupt decision.
        state["phase"]["current"] = "chain_resolution"
        try:
            state.setdefault("phase", {})["chain_resume_idx"] = int(getattr(result, "links_resolved", 0) or 0)
        except Exception:
            state.setdefault("phase", {})["chain_resume_idx"] = 0
        return True
    # Chain finished/broke: clear resume + chain-roll state.
    state.get("phase", {}).pop("chain_resume_idx", None)
    state.get("phase", {}).pop("execute_prompted", None)
    state.pop("_chain_attack_d20", None)
    state.pop("_chain_attack_total", None)
    state.pop("_chain_needs_roll", None)
    # Clear any suppression after a chain finishes resolving.
    state.pop("suppress_chain_interrupt", None)

    # Balance is per-chain: reset aggressor balance after chain resolves.
    try:
        combat_set(state, aggressor, "balance", 0)
    except Exception:
        pass

    # End chain banner and (if enemy just finished) end-round banner.
    try:
        round_no = int(state.get("phase", {}).get("chain_banner_round") or state.get("phase", {}).get("round") or 0)
        chain_side = state.get("phase", {}).get("chain_banner_side", active).upper()
        reason = getattr(result, "break_reason", None) or "completed"
        if reason in {"interrupt_after_link", "interrupt_before_link"}:
            action_name = None
            try:
                action_name = state.pop("_chain_break_action", None)
            except Exception:
                action_name = None
            reason = f"{action_name} Interrupted" if action_name else "Interrupted"
        emit_combat_log(ui, f"END {chain_side} CHAIN — {reason}", "system")
        state.get("phase", {}).pop("chain_banner_open", None)
        state.get("phase", {}).pop("chain_banner_side", None)
        state.get("phase", {}).pop("chain_banner_round", None)
    except Exception:
        pass

    ui.system(
        f"Chain resolved: {result.break_reason} "
        f"(links resolved: {result.links_resolved})"
    )

    # If chain resolution ended combat, emit the result immediately for web UI.
    try:
        if state.get("combat_over") and not getattr(ui, "is_blocking", True):
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

            player_dead = _hp(player) <= 0 if player else False
            enemy_dead = _hp(enemy) <= 0 if enemy else False
            result_label = "defeat" if player_dead else "victory" if enemy_dead else "ended"
            state["scene_complete"] = bool(enemy_dead)

            emit_combat_state(ui, False)
            state["phase"]["current"] = "out_of_combat"
            state.pop("awaiting", None)
            ui.system("Combat over.")
            emit_event(ui, {"type": "combat_result", "result": result_label})
            return True
    except Exception:
        pass

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
        # Enemy just completed their half; declare end of round.
        try:
            round_no = int(state.get("phase", {}).get("round") or 0)
            emit_combat_log(ui, f"END ROUND {round_no}", "system")
        except Exception:
            pass
        # End-of-round status tick (Bleed etc.).
        try:
            from engine.status import tick_statuses
            def _hp(entity):
                if not isinstance(entity, dict):
                    return 0
                hp_val = entity.get("hp")
                if isinstance(hp_val, dict):
                    return int(hp_val.get("current", hp_val.get("hp", 0)) or 0)
                if isinstance(entity.get("resources"), dict) and entity["resources"].get("hp") is not None:
                    return int(entity["resources"].get("hp") or 0)
                return int(hp_val or 0)

            def _bleed_stacks(entity):
                if not isinstance(entity, dict):
                    return 0
                st = entity.get("statuses", {})
                if not isinstance(st, dict):
                    return 0
                bleed = st.get("bleed")
                if isinstance(bleed, dict):
                    return int(bleed.get("stacks", 0) or 0)
                if isinstance(bleed, (int, float)):
                    return int(bleed or 0)
                return 0

            for en in state.get("enemies", []):
                before_hp = _hp(en)
                before_bleed = _bleed_stacks(en)
                summary = tick_statuses(en) or {}
                dmg = int(summary.get("damage", 0) or 0) if isinstance(summary, dict) else 0
                if dmg > 0:
                    emit_combat_log(ui, f"{en.get('name', 'Enemy')} takes {dmg} damage from statuses.", "damage")
                if before_bleed > 0:
                    # Bleed always decays by 1 on tick (our rule), so surface it for clarity.
                    emit_combat_log(ui, f"{en.get('name', 'Enemy')} Bleed decays: {before_bleed} → {max(0, before_bleed - 1)}", "system")
                after_hp = _hp(en)
                if after_hp <= 0 and before_hp > 0:
                    emit_combat_log(ui, f"{en.get('name', 'Enemy')} falls.", "system")

            # Player status tick (usually just for completeness).
            if isinstance(player, dict):
                before_hp = _hp(player)
                summary = tick_statuses(player) or {}
                dmg = int(summary.get("damage", 0) or 0) if isinstance(summary, dict) else 0
                if dmg > 0:
                    emit_combat_log(ui, f"{player.get('name', 'Player')} takes {dmg} damage from statuses.", "damage")
                after_hp = _hp(player)
                if after_hp <= 0 and before_hp > 0:
                    emit_combat_log(ui, f"{player.get('name', 'Player')} is brought to 0 HP.", "system")
            # End-of-round Radiance decay: -1 per round (clamped), persists as a resource.
            try:
                # Player
                if isinstance(player.get("resources"), dict):
                    r = int(player["resources"].get("radiance", 0) or 0)
                    if r > 0:
                        player["resources"]["radiance"] = r - 1
                # Enemies (if they ever receive radiance effects)
                for en in state.get("enemies", []):
                    if isinstance(en, dict) and isinstance(en.get("resources"), dict):
                        r = int(en["resources"].get("radiance", 0) or 0)
                        if r > 0:
                            en["resources"]["radiance"] = r - 1
            except Exception:
                pass
            # Refresh HUDs after end-of-round damage/decay.
            if not getattr(ui, "is_blocking", True):
                try:
                    emit_authoritative_player_update(ui, state, player)
                except Exception:
                    pass
                try:
                    if state.get("enemies"):
                        emit_enemy_update(ui, state, state["enemies"][0])
                except Exception:
                    pass

            # If an end-of-round status tick killed someone, mark combat over so the next /step renders the result.
            try:
                player_dead = _hp(player) <= 0 if player else False
                enemy0 = state.get("enemies", [None])[0] if state.get("enemies") else None
                enemy_dead = _hp(enemy0) <= 0 if enemy0 else False
                if player_dead or enemy_dead:
                    state["combat_over"] = True
                    # For web UI, emit result immediately so the player isn't stranded waiting for another /step.
                    if not getattr(ui, "is_blocking", True):
                        from ui.events import emit_event
                        result = "defeat" if player_dead else "victory" if enemy_dead else "ended"
                        state["scene_complete"] = bool(enemy_dead)
                        emit_combat_state(ui, False)
                        state["phase"]["current"] = "out_of_combat"
                        state.pop("awaiting", None)
                        ui.system("Combat over.")
                        emit_event(ui, {"type": "combat_result", "result": result})
                        return True
            except Exception:
                pass
        except Exception:
            pass

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
    # Ensure the enemy HUD is current before we show the interrupt UI.
    try:
        if not getattr(ui, "is_blocking", True):
            emit_enemy_update(ui, state, enemy)
    except Exception:
        pass

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
            # Prevent game_step() from immediately cascading into the next turn in the same /step.
            state["_pause_after_interrupt"] = True
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


def emit_enemy_update(ui, state, enemy) -> None:
    """
    Web UI helper: emit an enemy HUD payload (name/meta + hp + meters).
    """
    try:
        from ui.events import emit_event
        from engine.combat_state import combat_get

        if not isinstance(enemy, dict):
            return

        stat_block = enemy.get("stat_block") or {}
        defense = stat_block.get("defense", {}) if isinstance(stat_block, dict) else {}

        name = enemy.get("name", enemy.get("id", "Enemy"))
        tier = enemy.get("tier")
        role = enemy.get("role")
        dv_base = enemy.get("dv_base", defense.get("dv_base", 10))
        idf = enemy.get("idf", defense.get("idf", 0))

        hp_val = enemy.get("hp")
        if isinstance(hp_val, dict):
            hp_cur = hp_val.get("current", hp_val.get("hp", 0))
            hp_max = hp_val.get("max", hp_cur)
        else:
            hp_cur = hp_val if hp_val is not None else None
            hp_max = None

        if hp_cur is None:
            res = enemy.get("resources", {}) if isinstance(enemy.get("resources"), dict) else {}
            hp_cur = res.get("hp")
            hp_max = hp_max or res.get("hp_max") or res.get("max_hp") or res.get("maxHp")

        if hp_max is None:
            try:
                hp_max = (stat_block.get("hp", {}) or {}).get("max") if isinstance(stat_block, dict) else None
            except Exception:
                hp_max = None
        hp_max = hp_max or hp_cur
        if hp_cur is None:
            hp_cur = hp_max or 0

        payload = {
            "name": name,
            "tier": tier,
            "role": role,
            "dv_base": dv_base,
            "idf": idf,
            "hp": {"current": int(hp_cur or 0), "max": int(hp_max or hp_cur or 0)},
            "heat": combat_get(state, enemy, "heat", 0),
            "momentum": combat_get(state, enemy, "momentum", 0),
            "balance": combat_get(state, enemy, "balance", 0),
        }
        # Primed + execution threshold are part of the enemy HUD (separate from any execution UI affordance).
        try:
            from engine.combat_state import status_get

            def _sid(name: str) -> str:
                s = "".join(ch.lower() if ch.isalnum() else "_" for ch in (name or "").strip())
                s = "_".join([p for p in s.split("_") if p])
                return f"status.{s}" if s else "status.unknown"

            thresh = float(enemy.get("execution_threshold_pct", 0.25) or 0.25)
            hp_cur_i = int(payload["hp"]["current"] or 0)
            hp_max_i = int(payload["hp"]["max"] or hp_cur_i or 0)
            primed_hp = bool(hp_max_i and hp_cur_i <= int(round(hp_max_i * thresh)))
            vulnerable = int((status_get(state, enemy, _sid("Vulnerable")) or {}).get("stacks", 0) or 0)
            stagger = int((status_get(state, enemy, _sid("Stagger")) or {}).get("stacks", 0) or 0)
            primed_flag = int((status_get(state, enemy, _sid("Primed")) or {}).get("stacks", 0) or 0) >= 1
            payload["execution_threshold_pct"] = thresh
            payload["primed"] = bool(primed_hp or vulnerable >= 3 or stagger >= 2 or primed_flag)
        except Exception:
            pass
        try:
            res = enemy.get("resources", {}) if isinstance(enemy.get("resources"), dict) else {}
            if isinstance(res, dict) and res.get("radiance") is not None:
                payload["radiance"] = int(res.get("radiance", 0) or 0)
        except Exception:
            pass
        try:
            statuses = enemy.get("statuses", {}) if isinstance(enemy.get("statuses"), dict) else {}
            bleed = statuses.get("bleed")
            status_payload: dict = {}
            if isinstance(bleed, dict):
                stacks = int(bleed.get("stacks", 0) or 0)
                duration = int(bleed.get("duration", 0) or 0)
                if stacks > 0:
                    status_payload["bleed"] = {"stacks": stacks, "duration": duration}
            elif isinstance(bleed, (int, float)):
                stacks = int(bleed or 0)
                if stacks > 0:
                    status_payload["bleed"] = {"stacks": stacks, "duration": 0}
            # Always include statuses so the UI can clear badges when stacks hit 0.
            payload["statuses"] = status_payload
        except Exception:
            payload["statuses"] = {}
        emit_event(ui, {"type": "enemy_update", "enemy": payload})
    except Exception:
        pass


def build_victory_loot(game_data: dict, enemy: dict | None = None) -> list[dict]:
    """
    Minimal loot generator for the web loot overlay.
    Picks a few items from game-data/loot.json by tier, falling back gracefully.
    """
    # Prefer scene-authored loot_table (IDs pointing at game-data/loot/<id>.json).
    scene = None
    try:
        scene = enemy.get("_scene") if isinstance(enemy, dict) else None
    except Exception:
        scene = None

    # In practice we keep the scene on state; callers should pass enemy only for tier fallback.
    # So we accept an optional state-like dict via game_data["__scene"] as a pragmatic bridge.
    if isinstance((game_data or {}).get("__scene"), dict):
        scene = game_data["__scene"]

    if isinstance(scene, dict) and isinstance(scene.get("loot_table"), list) and scene["loot_table"]:
        items: list[dict] = []
        for loot_id in scene["loot_table"]:
            if not isinstance(loot_id, str):
                continue
            items.append(resolve_loot_item(loot_id))
        return [it for it in items if isinstance(it, dict) and it]

    # Fallback: pick a couple items from the compiled loot table by tier.
    loot_all = (game_data or {}).get("loot", [])
    if not isinstance(loot_all, list) or not loot_all:
        return []

    tier = 1
    try:
        if isinstance(enemy, dict) and enemy.get("tier") is not None:
            tier = int(enemy.get("tier") or 1)
    except Exception:
        tier = 1

    candidates = [it for it in loot_all if isinstance(it, dict) and int(it.get("tier", tier) or tier) == tier]
    if not candidates:
        candidates = [it for it in loot_all if isinstance(it, dict)]

    # Keep it deterministic for now (easier to debug): first 2 items.
    return candidates[:2]


def apply_loot_to_player(state: dict, items: list[dict]) -> None:
    """
    Minimal effect application:
    - grant_veinscore: adds to player resources.veinscore
    """
    party = state.get("party", {})
    members = party.get("members", []) if isinstance(party, dict) else []
    if not members:
        return
    player = members[0]
    if not isinstance(player, dict):
        return

    res = player.get("resources")
    if not isinstance(res, dict):
        res = {}
        player["resources"] = res

    for it in items or []:
        if not isinstance(it, dict):
            continue
        for eff in it.get("effects", []) or []:
            if not isinstance(eff, dict):
                continue
            if eff.get("type") in {"grant_veinscore", "add_veinscore"}:
                try:
                    delta = int(eff.get("value") or eff.get("amount") or 0)
                except Exception:
                    delta = 0
                res["veinscore"] = int(res.get("veinscore", 0) or 0) + delta


def apply_dun_mark_and_restore(state: dict) -> None:
    party = state.get("party", {}) if isinstance(state.get("party"), dict) else {}
    members = party.get("members", []) if isinstance(party.get("members"), list) else []
    if not members or not isinstance(members[0], dict):
        return
    player = members[0]

    # Mark
    marks = player.get("marks")
    if not isinstance(marks, dict):
        marks = {}
        player["marks"] = marks
    marks["duns"] = int(marks.get("duns", 0) or 0) + 1

    # Restore HP to max
    res = player.get("resources")
    if not isinstance(res, dict):
        res = {}
        player["resources"] = res
    hp_max = res.get("hp_max") or res.get("max_hp") or res.get("maxHp")
    if hp_max is None:
        hp_val = player.get("hp")
        if isinstance(hp_val, dict):
            hp_max = hp_val.get("max")
        else:
            hp_max = player.get("hp_max") or player.get("max_hp") or player.get("maxHp")
    try:
        hp_max = int(hp_max or 0)
    except Exception:
        hp_max = 0
    if hp_max <= 0:
        hp_max = int(res.get("hp", 0) or 28)
    res["hp"] = hp_max
    res["hp_max"] = hp_max
    # Keep dict hp mirror if present
    if isinstance(player.get("hp"), dict):
        player["hp"]["current"] = hp_max
        player["hp"]["max"] = int(player["hp"].get("max") or hp_max)

    # Lose all unspent Veinscore on re-awaken.
    try:
        res["veinscore"] = 0
    except Exception:
        pass
    try:
        player["veinscore"] = 0
    except Exception:
        pass


def resolve_loot_item(loot_id: str) -> dict:
    path = Path(__file__).parent / "game-data" / "loot" / f"{loot_id}.json"
    data = _read_json(path)
    if isinstance(data, dict) and data:
        data.setdefault("id", loot_id)
        return data
    return {"id": loot_id, "name": loot_id}


def resolve_narration_template(prompt_id: str) -> str | None:
    """
    Reads game-data/narrations.json which may be a single object or a list of objects.
    """
    path = Path(__file__).parent / "game-data" / "narrations.json"
    data = _read_json(path)
    if isinstance(data, dict) and data.get("id") == prompt_id:
        return data.get("template")
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        for it in data["items"]:
            if isinstance(it, dict) and it.get("id") == prompt_id:
                return it.get("template")
    if isinstance(data, list):
        for it in data:
            if isinstance(it, dict) and it.get("id") == prompt_id:
                return it.get("template")
    return None


def scene_conditions_pass(conditions: list, state: dict) -> bool:
    if not conditions:
        return True
    metrics = state.get("scene_metrics", {}) if isinstance(state.get("scene_metrics"), dict) else {}
    for cond in conditions:
        if not isinstance(cond, dict):
            continue
        ctype = cond.get("type")
        if ctype == "player_no_damage":
            if int(metrics.get("damage_taken", 0) or 0) != 0:
                return False
    return True


def apply_scene_complete_events(ctx: dict) -> dict:
    """
    Applies on_scene_complete events and returns a reward summary payload:
      {"narration": str|None, "achievements": [..]}
    """
    state = ctx["state"]
    scene = state.get("scene") if isinstance(state.get("scene"), dict) else {}
    if not isinstance(scene, dict):
        return {}
    rewards: dict = {"achievements": []}

    events = scene.get("events", []) if isinstance(scene.get("events"), list) else []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        trig = ev.get("trigger", {}) if isinstance(ev.get("trigger"), dict) else {}
        if trig.get("type") != "on_scene_complete":
            continue
        if not scene_conditions_pass(ev.get("conditions", []) or [], state):
            continue
        for eff in ev.get("effects", []) or []:
            if not isinstance(eff, dict):
                continue
            et = eff.get("type")
            if et == "award_achievement":
                aid = eff.get("id")
                if aid:
                    rewards["achievements"].append(aid)
            if et == "narration_prompt":
                pid = eff.get("id")
                if pid:
                    txt = resolve_narration_template(pid)
                    if txt:
                        rewards["narration"] = txt

    # Persist achievements to state
    if rewards.get("achievements"):
        state.setdefault("achievements", [])
        if isinstance(state["achievements"], list):
            for a in rewards["achievements"]:
                if a not in state["achievements"]:
                    state["achievements"].append(a)

    state["scene_rewards"] = rewards
    return rewards

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
    statuses_path = root / "statuses.json"
    if statuses_path.exists():
        try:
            sj = json.loads(statuses_path.read_text(encoding="utf-8"))
            statuses = sj.get("statuses", []) if isinstance(sj, dict) else []
            data["statuses"] = statuses if isinstance(statuses, list) else []
        except Exception:
            data["statuses"] = []
    bestiary: list[dict] = []
    # Bestiary source (prefer the newer monsters/ folder bestiary when present).
    bestiary_path = root / "monsters" / "bestiary.json"
    fallback_bestiary_path = root / "bestiary.json"
    chosen_bestiary_path = bestiary_path if bestiary_path.exists() else fallback_bestiary_path
    if chosen_bestiary_path.exists():
        try:
            bj = json.loads(chosen_bestiary_path.read_text(encoding="utf-8"))
            if isinstance(bj, dict) and isinstance(bj.get("meta"), dict):
                data["bestiary_meta"] = bj["meta"]
            bestiary.extend(bj.get("enemies", []))
        except Exception:
            pass
    beasts_dir = root / "beasts"
    if beasts_dir.exists():
        for bf in beasts_dir.glob("*.json"):
            # Legacy aggregate file (kept for reference); avoid duplicate/conflicting entries.
            if bf.name.lower() == "oldbestiary.json":
                continue
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
    # Hybrid overlay: build a fast ID lookup where later entries override earlier ones.
    enemy_by_id = {}
    for e in data["bestiary"]:
        if not isinstance(e, dict):
            continue
        eid = e.get("id")
        if not eid:
            continue
        enemy_by_id[eid] = e
    data["enemy_by_id"] = enemy_by_id
    return data


DEFAULT_SCRIPT_PATH = Path(__file__).parent / "game-data" / "scripts" / "script.echoes.json"


def load_script(path: Path | None = None) -> dict:
    path = path or DEFAULT_SCRIPT_PATH
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def script_scene_ids(script: dict) -> list[str]:
    acts = script.get("acts", []) if isinstance(script, dict) else []
    if not isinstance(acts, list):
        return []
    # Sort by "order" if present, otherwise keep file order.
    def _order(a):
        try:
            return int(a.get("order", 0) or 0)
        except Exception:
            return 0
    ordered = sorted([a for a in acts if isinstance(a, dict)], key=_order)
    scene_ids: list[str] = []
    for act in ordered:
        for s in act.get("scenes", []) or []:
            if isinstance(s, dict) and "$ref" in s:
                scene_ids.append(str(s["$ref"]))
            elif isinstance(s, str):
                scene_ids.append(s)
    # De-dupe while preserving order.
    out: list[str] = []
    seen = set()
    for sid in scene_ids:
        if sid in seen:
            continue
        seen.add(sid)
        out.append(sid)
    return out


def ensure_campaign(state: dict, game_data: dict) -> None:
    """
    Initializes a simple linear campaign (script.echoes.json) into state["campaign"].
    """
    if isinstance(state.get("campaign"), dict) and state["campaign"].get("scene_ids"):
        return
    script = load_script()
    scene_ids = script_scene_ids(script)
    state["campaign"] = {
        "script_id": script.get("id", "script.echoes"),
        "scene_ids": scene_ids,
        "index": 0,
    }


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_scene(scene_id: str) -> dict:
    path = Path(__file__).parent / "game-data" / "scenes" / f"{scene_id}.json"
    return _read_json(path)


def resolve_trap(trap_id: str) -> dict:
    path = Path(__file__).parent / "game-data" / "traps" / f"{trap_id}.json"
    data = _read_json(path)
    return data or {"id": trap_id}


def resolve_hazard(hazard_id: str) -> dict:
    path = Path(__file__).parent / "game-data" / "hazards" / f"{hazard_id}.json"
    data = _read_json(path)
    return data or {"id": hazard_id}


def resolve_environment(env_id: str) -> dict:
    path = Path(__file__).parent / "game-data" / "environments" / f"{env_id}.json"
    data = _read_json(path)
    return data or {"id": env_id}


def _prime_enemy_for_combat(enemy: dict) -> dict:
    """
    Ensure an enemy object has runtime fields expected by the combat loop (hp/dv/idf).
    """
    if not isinstance(enemy, dict):
        return {}
    stat_block = enemy.get("stat_block") or {}
    defense = stat_block.get("defense", {}) if isinstance(stat_block, dict) else {}
    execution = stat_block.get("execution", {}) if isinstance(stat_block, dict) else {}

    # HP
    hp_max = None
    hp_min = None
    hp_variance_pct = None
    try:
        hp_def = (stat_block.get("hp", {}) or {}) if isinstance(stat_block, dict) else {}
        hp_max = hp_def.get("max")
        hp_min = hp_def.get("min")
        hp_variance_pct = hp_def.get("variance_pct", hp_def.get("variance"))
    except Exception:
        hp_max = None
    if hp_max is None:
        hp_val = enemy.get("hp")
        if isinstance(hp_val, dict):
            hp_max = hp_val.get("max")
        else:
            hp_max = enemy.get("hp_max") or enemy.get("max_hp") or enemy.get("maxHp")
    try:
        hp_max = int(hp_max or 0)
    except Exception:
        hp_max = 0
    if hp_max <= 0:
        hp_max = 10

    # Optional per-spawn HP randomization.
    # - Prefer explicit hp.min/hp.max if provided in the data.
    # - Otherwise allow a variance percentage around hp.max (±variance).
    rng = enemy.get("_spawn_rng") if hasattr(enemy, "get") else None
    if rng is None and isinstance(enemy, dict):
        rng = enemy.get("_rng")
    if rng is None:
        rng = random

    try:
        hp_base_max = int(hp_max)
        hp_spawn_min = None
        hp_spawn_max = None
        if hp_min is not None:
            hp_spawn_min = int(hp_min)
            hp_spawn_max = int(hp_base_max)
        else:
            v = hp_variance_pct
            if v is None:
                v = float(enemy.get("_hp_variance_pct", 0.0) or 0.0)
            v = max(0.0, float(v))
            if v > 0.0:
                hp_spawn_min = max(1, int(round(hp_base_max * (1.0 - v))))
                hp_spawn_max = max(1, int(round(hp_base_max * (1.0 + v))))

        if hp_spawn_min is not None and hp_spawn_max is not None:
            if hp_spawn_min > hp_spawn_max:
                hp_spawn_min, hp_spawn_max = hp_spawn_max, hp_spawn_min
            hp_spawn_max = int(rng.randint(int(hp_spawn_min), int(hp_spawn_max)))
        else:
            hp_spawn_max = int(hp_base_max)
    except Exception:
        hp_base_max = int(hp_max)
        hp_spawn_max = int(hp_base_max)

    enemy["_hp_base_max"] = hp_base_max
    enemy["hp"] = {"current": hp_spawn_max, "max": hp_spawn_max}

    # Execution threshold (percentage of max HP). Default: 25%.
    try:
        enemy["execution_threshold_pct"] = float(execution.get("threshold_pct", 0.25) or 0.25)
    except Exception:
        enemy["execution_threshold_pct"] = 0.25

    # Defense
    if enemy.get("dv_base") is None:
        enemy["dv_base"] = defense.get("dv_base", 10)
    if enemy.get("idf") is None:
        enemy["idf"] = defense.get("idf", 0)

    return enemy


def enter_scene_into_state(ctx: dict, scene_id: str) -> bool:
    """
    Loads a scene and populates state with encounter content (enemies/traps/hazards/env).
    Returns True if loaded.
    """
    state = ctx["state"]
    ui = ctx["ui"]
    game_data = ctx["game_data"]

    scene = load_scene(scene_id)
    if not scene or scene.get("id") != scene_id:
        ui.error(f"Missing scene: {scene_id}")
        return False

    state["scene_id"] = scene_id
    state["scene"] = scene
    state.pop("scene_rewards", None)
    state["scene_complete"] = False
    state["active_combatant"] = "player"

    # Initialize per-scene metrics
    metrics_def = scene.get("metrics", {}) if isinstance(scene.get("metrics"), dict) else {}
    track = metrics_def.get("track", []) if isinstance(metrics_def.get("track"), list) else []
    scene_metrics: dict = {}
    for k in track:
        if isinstance(k, str):
            scene_metrics[k] = 0
    # Always track damage_taken for scene conditions.
    scene_metrics.setdefault("damage_taken", 0)
    state["scene_metrics"] = scene_metrics

    env_id = ((scene.get("environment") or {}) if isinstance(scene.get("environment"), dict) else {}).get("id")
    if env_id:
        state["environment"] = resolve_environment(str(env_id))

    # Safe room is a special non-combat environment.
    if is_safe_room(state):
        state["mode"] = "safe_room"
        state["phase"]["current"] = "out_of_combat"
        state["active_combatant"] = "player"
        state.pop("encounter", None)
        state["enemies"] = []
        state["traps"] = []
        state["hazards"] = []
        emit_combat_state(ui, False)
        if not getattr(ui, "is_blocking", True):
            ui.clear("all")
            emit_safe_room_enter(ctx)
        return True

    encounter = scene.get("encounter", {}) if isinstance(scene.get("encounter"), dict) else {}
    monsters = encounter.get("monsters", []) if isinstance(encounter.get("monsters"), list) else []
    traps = encounter.get("traps", []) if isinstance(encounter.get("traps"), list) else []
    hazards = encounter.get("hazards", []) if isinstance(encounter.get("hazards"), list) else []

    # Enemies: resolve by id using hybrid overlay bestiary.
    enemy_by_id = (game_data or {}).get("enemy_by_id", {})
    meta = (game_data or {}).get("bestiary_meta", {}) if isinstance((game_data or {}).get("bestiary_meta"), dict) else {}
    hp_rules = (meta.get("system_rules", {}) or {}).get("enemy_hp", {}) if isinstance((meta.get("system_rules", {}) or {}).get("enemy_hp", {}), dict) else {}
    try:
        default_hp_variance = float(hp_rules.get("variance_pct", 0.0) or 0.0)
    except Exception:
        default_hp_variance = 0.0
    enemies = []
    spawn_idx = 0
    for m in monsters:
        if not isinstance(m, dict):
            continue
        mid = m.get("id")
        if not mid:
            continue
        try:
            count = int(m.get("count", 1) or 1)
        except Exception:
            count = 1
        template = enemy_by_id.get(mid) if isinstance(enemy_by_id, dict) else None
        if not isinstance(template, dict):
            template = {"id": mid, "name": mid}
        for _ in range(max(1, count)):
            inst = deepcopy(template)
            # Per-spawn deterministic RNG (uses Random's stable string seeding for str inputs).
            seed = state.get("seed")
            r = random.Random()
            r.seed(f"{seed}|{scene_id}|{mid}|{spawn_idx}")
            inst["_spawn_rng"] = r
            inst["_hp_variance_pct"] = default_hp_variance
            enemies.append(_prime_enemy_for_combat(inst))
            spawn_idx += 1
    state["enemies"] = enemies

    # Traps/hazards: per-file
    state["traps"] = []
    for t in traps:
        if not isinstance(t, dict) or not t.get("id"):
            continue
        try:
            count = int(t.get("count", 1) or 1)
        except Exception:
            count = 1
        for _ in range(max(1, count)):
            state["traps"].append(resolve_trap(str(t["id"])))

    state["hazards"] = []
    for h in hazards:
        if isinstance(h, str):
            state["hazards"].append(resolve_hazard(h))
        elif isinstance(h, dict) and h.get("id"):
            state["hazards"].append(resolve_hazard(str(h["id"])))

    # UI surface: scene title + prime enemy HUD + choice to enter encounter.
    title = scene.get("title", scene_id)
    ui.scene(f"{title}")
    if enemies:
        emit_enemy_update(ui, state, enemies[0])
    if not getattr(ui, "is_blocking", True):
        ui.choice("Enter encounter?", ["enter_encounter"])
        state["awaiting"] = {"type": "player_choice", "options": ["enter_encounter"]}
    return True

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
        "seed": random.randint(1, 2**31 - 1),
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
    # If the current enemy is Primed, expose execution affordance (Phase 1+).
    try:
        def _status_id(name: str) -> str:
            s = "".join(ch.lower() if ch.isalnum() else "_" for ch in (name or "").strip())
            s = "_".join([p for p in s.split("_") if p])
            return f"status.{s}" if s else "status.unknown"

        enemy = (state.get("enemies") or [None])[0]
        if isinstance(enemy, dict) and isinstance(enemy.get("hp"), dict):
            hp_cur = int(enemy["hp"].get("current", 0) or 0)
            hp_max = int(enemy["hp"].get("max", hp_cur) or hp_cur)
            thresh = float(enemy.get("execution_threshold_pct", 0.25) or 0.25)
            primed_hp = bool(hp_max and hp_cur <= int(round(hp_max * thresh)))
            vulnerable = int((status_get(state, enemy, _status_id("Vulnerable")) or {}).get("stacks", 0) or 0)
            stagger = int((status_get(state, enemy, _status_id("Stagger")) or {}).get("stacks", 0) or 0)
            primed_flag = int((status_get(state, enemy, _status_id("Primed")) or {}).get("stacks", 0) or 0) >= 1
            primed = primed_hp or vulnerable >= 3 or stagger >= 2 or primed_flag
            if primed:
                emit_event(ui, {"type": "execution_available", "enemy": enemy.get("name"), "threshold_pct": thresh})
    except Exception:
        pass
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
        if awaiting.get("type") == "execute_prompt":
            act = player_input.get("action")
            if act == "execute_yes":
                state.pop("awaiting", None)
                state["pending_execute"] = True
                should_return = False
            if act == "execute_no":
                state.pop("awaiting", None)
                state["pending_execute"] = False
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
        # push a single authoritative update after upkeep for web
        try:
            ch = state["party"]["members"][0]
            emit_authoritative_player_update(ui, state, ch)
        except Exception:
            pass

def handle_start_action(ctx, requested_action):
    state = ctx["state"]
    ui = ctx["ui"]
    if requested_action == "start" and not getattr(ui, "is_blocking", True):
        ensure_campaign(state, ctx.get("game_data", {}))
        camp = state.get("campaign", {}) if isinstance(state.get("campaign"), dict) else {}
        scene_ids = camp.get("scene_ids", []) if isinstance(camp.get("scene_ids"), list) else []
        idx = int(camp.get("index", 0) or 0)
        if scene_ids and 0 <= idx < len(scene_ids):
            enter_scene_into_state(ctx, scene_ids[idx])
        else:
            # Fallback to legacy flow if no script/scenes are available.
            reopen_chain_builder(state, ui, max_len=3)
        return True
    return None

def handle_declare_chain_action(ctx, player_input, requested_action):
    state = ctx["state"]
    ui = ctx["ui"]
    if not (isinstance(player_input, dict) and requested_action == "declare_chain"):
        return None

    chain_ids = player_input.get("chain") or []
    execute_requested = bool(player_input.get("execute")) if isinstance(player_input, dict) else False
    # Player is explicitly declaring a chain; ensure turn ownership is correct for the upcoming resolution.
    state["active_combatant"] = "player"
    awaiting = state.pop("awaiting", None) if state.get("awaiting", {}).get("type") == "chain_builder" else None
    usable = awaiting.get("options") if awaiting else usable_ability_objects(state)
    names = []
    selected = []
    missing = []
    for cid in chain_ids:
        ab = next((a for a in usable if a.get("id") == cid or a.get("name") == cid), None)
        if ab and ab.get("name"):
            names.append(ab["name"])
            selected.append(ab)
        else:
            missing.append(cid)
    # If the client sent IDs but none of them resolved, do NOT treat it as an empty-chain "pass".
    if missing:
        ui.error(f"Unknown abilities selected: {', '.join(str(m) for m in missing)}")
        reopen_chain_builder(state, ui, max_len=state.get("phase", {}).get("chain_max", 6) or 6)
        return True

    # Server-side validation: EXECUTE requires at least one declared link (it may replace any link while Primed).
    if execute_requested and not selected:
        reason = "EXECUTE requires at least one declared link."
        ui.error(reason)
        emit_event(ui, {"type": "chain_rejected", "reason": reason})
        reopen_chain_builder(state, ui, max_len=state.get("phase", {}).get("chain_max", 6) or 6)
        return True
    character = state["party"]["members"][0]
    # Keep legacy character.resources and encounter combat meters in sync before and after declaration.
    # Source of truth for RP is encounter combat meters when present.
    res = character.setdefault("resources", {})
    if "encounter" in state and character.get("_combat_key"):
        rp_cur = combat_get(state, character, "rp", int(res.get("resolve", 0) or 0))
        rp_cap = combat_get(state, character, "rp_cap", int(res.get("resolve_cap", rp_cur) or rp_cur))
        res["resolve"] = int(rp_cur)
        res["resolve_cap"] = int(rp_cap)
    ok, resp = declare_chain(
        state,
        character,
        names,
        resolve_spent=0,
        stabilize=False,
        execute=execute_requested,
    )
    if not ok:
        ui.error(f"Invalid chain: {resp}")
        emit_event(ui, {"type": "chain_rejected", "reason": resp})
        reopen_chain_builder(state, ui, max_len=state.get("phase", {}).get("chain_max", 6) or 6)
        return True
    if "encounter" in state and character.get("_combat_key"):
        combat_set(state, character, "rp", int(res.get("resolve", 0) or 0))
        combat_set(state, character, "rp_cap", int(res.get("resolve_cap", combat_get(state, character, "rp_cap", 0)) or 0))
        # Push the RP change immediately in web mode (RP is spent at declaration time).
        if not getattr(ui, "is_blocking", True):
            hp_cur = res.get("hp")
            hp_max = res.get("hp_max", res.get("max_hp", res.get("maxHp", hp_cur)))
            emit_character_update(ui, {
                "name": character.get("name"),
                "hp": {"current": hp_cur, "max": hp_max},
                "rp": combat_get(state, character, "rp", int(res.get("resolve", 0) or 0)),
                "rp_cap": combat_get(state, character, "rp_cap", int(res.get("resolve_cap", 0) or 0)),
                "veinscore": res.get("veinscore", 0),
                "abilities": character.get("abilities", []),
                "meters": {
                    "momentum": combat_get(state, character, "momentum", int(res.get("momentum", 0) or 0)),
                    "balance": combat_get(state, character, "balance", int(res.get("balance", 0) or 0)),
                    "heat": combat_get(state, character, "heat", int(res.get("heat", 0) or 0)),
                },
            })
    try:
        metrics = state.get("scene_metrics", {})
        if isinstance(metrics, dict):
            metrics["chains_declared"] = int(metrics.get("chains_declared", 0) or 0) + 1
    except Exception:
        pass
    for ability in character.get("abilities", []):
        if ability.get("name") in names:
            cd = ability.get("base_cooldown", ability.get("cooldown", 0) or 0)
            ability["base_cooldown"] = cd
            ability["cooldown"] = cd
            ability["cooldown_round"] = state["phase"]["round"] + cd if cd else state["phase"]["round"]
    state["phase"]["current"] = "chain_resolution"
    state.pop("awaiting", None)
    # New chain: reset resume bookkeeping.
    try:
        state.setdefault("phase", {})["chain_resume_idx"] = 0
        state.setdefault("phase", {})["execute_prompted"] = False
    except Exception:
        pass
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

    # ── Character creation (web-first) ────────────────────────────────
    if requested_action == "new_character_begin" and not getattr(ui, "is_blocking", True):
        state["mode"] = "character_create"
        state["character_create"] = {
            "stage": "choose_path",
            "character": _create_draft_character(path_id=None),
        }
        emit_character_create(ctx)
        return True

    if state.get("mode") == "character_create" and not getattr(ui, "is_blocking", True):
        draft = state.get("character_create") if isinstance(state.get("character_create"), dict) else {}
        ch = draft.get("character") if isinstance(draft.get("character"), dict) else None
        if not isinstance(ch, dict):
            return True

        if requested_action == "character_create_path":
            path_id = player_input.get("path") if isinstance(player_input, dict) else None
            if path_id not in {p["id"] for p in CHARACTER_CREATE_PATHS}:
                ui.error("Invalid path selection.")
                emit_character_create(ctx)
                return True
            ch = _create_draft_character(path_id=path_id)
            ch["abilities"] = _starter_ability_ids_for_path(path_id, ctx.get("game_data") or {})
            draft["character"] = ch
            draft["stage"] = "choose_rp"
            state["character_create"] = draft
            emit_character_create(ctx)
            return True

        if requested_action == "character_create_rp":
            rp_id = player_input.get("rp_ability") if isinstance(player_input, dict) else None
            catalog = _resolve_ability_catalog(ctx.get("game_data") or {})
            if rp_id not in {str(a.get("id") or a.get("name")) for a in catalog if isinstance(a, dict)}:
                ui.error("Invalid resolve ability selection.")
                emit_character_create(ctx)
                return True
            if rp_id not in (ch.get("abilities") or []):
                ch.setdefault("abilities", []).append(rp_id)
            draft["character"] = ch
            draft["stage"] = "shop"
            state["character_create"] = draft
            emit_character_create(ctx)
            return True

        if requested_action == "character_create_buy":
            ability_id = player_input.get("ability") if isinstance(player_input, dict) else None
            if not ability_id:
                ui.error("Missing ability id.")
                emit_character_create(ctx)
                return True
            offers = build_character_create_offers(ch, ctx.get("game_data") or {})
            offer = next((o for o in offers if o.get("id") == ability_id), None)
            if not offer:
                ui.error("That ability is not available.")
                emit_character_create(ctx)
                return True
            res = ch.get("resources", {}) if isinstance(ch.get("resources"), dict) else {}
            vein = int(res.get("veinscore", 0) or 0)
            cost = int(offer.get("cost", 1) or 1)
            if vein < cost:
                ui.error("Not enough Veinscore.")
                emit_character_create(ctx)
                return True
            res["veinscore"] = vein - cost
            ch["veinscore"] = res["veinscore"]
            if ability_id not in (ch.get("abilities") or []):
                ch.setdefault("abilities", []).append(ability_id)
            draft["character"] = ch
            state["character_create"] = draft
            emit_character_create(ctx)
            return True

        if requested_action == "character_create_finish":
            name = (player_input.get("name") if isinstance(player_input, dict) else None) or "New Blood"
            name = str(name).strip() or "New Blood"
            ch["name"] = name
            ch["id"] = _character_id_from_name(name)

            try:
                hydrate_character_abilities(ch, ctx.get("game_data") or {})
            except Exception:
                pass
            try:
                save_profile_and_state(ch)
            except Exception:
                pass
            try:
                ps = json.loads(PLAYER_STATE_PATH.read_text(encoding="utf-8")) if PLAYER_STATE_PATH.exists() else {}
                if not isinstance(ps, dict):
                    ps = {}
                ps["character_id"] = ch.get("id")
                PLAYER_STATE_PATH.write_text(json.dumps(ps, indent=2), encoding="utf-8")
            except Exception:
                pass

            state.setdefault("party", {}).setdefault("members", [None])[0] = ch
            state.pop("character_create", None)
            state.pop("mode", None)

            ensure_campaign(state, ctx.get("game_data", {}))
            camp = state.get("campaign", {}) if isinstance(state.get("campaign"), dict) else {}
            scene_ids = camp.get("scene_ids", []) if isinstance(camp.get("scene_ids"), list) else []
            idx = int(camp.get("index", 0) or 0)
            if scene_ids and 0 <= idx < len(scene_ids):
                enter_scene_into_state(ctx, scene_ids[idx])
            else:
                reopen_chain_builder(state, ui, max_len=3)
            return True

        # Default: keep the character creation overlay alive.
        emit_character_create(ctx)
        return True

    # ── Safe room mode (no combat) ───────────────────────────────
    if ctx.get("state", {}).get("mode") == "safe_room" or is_safe_room(ctx.get("state", {})):
        state = ctx["state"]
        ui = ctx["ui"]
        ch = state.get("party", {}).get("members", [None])[0]
        if not isinstance(ch, dict):
            return True
        res = ch.get("resources", {}) if isinstance(ch.get("resources"), dict) else {}

        if requested_action == "safe_room_rest":
            # Capture a simple rest summary for UI.
            try:
                before_hp = int(res.get("hp", 0) or 0)
                before_hp_max = int(res.get("hp_max", res.get("max_hp", res.get("maxHp", before_hp))) or before_hp)
                before_rp = int(res.get("resolve", 0) or 0)
                before_rp_cap = int(res.get("resolve_cap", before_rp) or before_rp)
                before_pools = dict(ch.get("pools", {})) if isinstance(ch.get("pools"), dict) else {}
            except Exception:
                before_hp = before_hp_max = before_rp = before_rp_cap = 0
                before_pools = {}

            # Full refill on rest.
            hp_max = res.get("hp_max", res.get("max_hp", res.get("maxHp", res.get("hp"))))
            if hp_max is not None:
                res["hp"] = int(hp_max)
                res["hp_max"] = int(hp_max)
            cap = res.get("resolve_cap", res.get("resolve", 0))
            res["resolve"] = int(cap or 0)
            _refill_pools_to_cap(ch)

            try:
                after_hp = int(res.get("hp", 0) or 0)
                after_hp_max = int(res.get("hp_max", after_hp) or after_hp)
                after_rp = int(res.get("resolve", 0) or 0)
                after_rp_cap = int(res.get("resolve_cap", after_rp) or after_rp)
                after_pools = dict(ch.get("pools", {})) if isinstance(ch.get("pools"), dict) else {}
                state["safe_room_last_rest"] = {
                    "hp": {"before": before_hp, "after": after_hp, "max": after_hp_max or before_hp_max},
                    "rp": {"before": before_rp, "after": after_rp, "cap": after_rp_cap or before_rp_cap},
                    "pools": {
                        k: {"before": int(before_pools.get(k, 0) or 0), "after": int(after_pools.get(k, 0) or 0)}
                        for k in sorted(set(list(before_pools.keys()) + list(after_pools.keys())))
                    },
                }
            except Exception:
                pass

            # Clear encounter meters (safe room is non-combat)
            try:
                if "encounter" in state and ch.get("_combat_key"):
                    combat_set(state, ch, "heat", 0)
                    combat_set(state, ch, "momentum", 0)
                    combat_set(state, ch, "balance", 0)
            except Exception:
                pass
            ui.system("You rest. Blood steadies. Pools refilled.")
            try:
                save_profile_and_state(ch)
            except Exception:
                pass
            if not getattr(ui, "is_blocking", True):
                emit_character_update(ui, {
                    "name": ch.get("name"),
                    "hp": {"current": res.get("hp"), "max": res.get("hp_max", res.get("hp"))},
                    "rp": res.get("resolve"),
                    "rp_cap": res.get("resolve_cap", res.get("resolve")),
                    "veinscore": res.get("veinscore", ch.get("veinscore", 0)),
                    "abilities": ch.get("abilities", []),
                })
            emit_safe_room_enter(ctx)
            return True

        if requested_action == "safe_room_buy" and isinstance(player_input, dict):
            ability_id = player_input.get("ability")
            if not ability_id:
                ui.error("Missing ability id.")
                emit_safe_room_enter(ctx)
                return True

            game_data = ctx.get("game_data") or {}
            offers = build_safe_room_offers(ch, game_data)
            offer = next((o for o in offers if o.get("id") == ability_id), None)
            if not offer:
                ui.error("That ability is not available.")
                emit_safe_room_enter(ctx)
                return True

            try:
                cost = int(offer.get("cost", 1) or 1)
            except Exception:
                cost = 1
            vein = int(res.get("veinscore", ch.get("veinscore", 0)) or 0)
            if vein < cost:
                ui.error("Not enough Veinscore.")
                emit_safe_room_enter(ctx)
                return True

            # Deduct and track spent.
            vein_new = vein - cost
            res["veinscore"] = vein_new
            ch["veinscore"] = vein_new
            ch["_veins_spent_total"] = int(ch.get("_veins_spent_total", 0) or 0) + int(cost)
            leveled = apply_vein_tier_progression(ch)

            # Add to profile on disk (ids only), then hydrate into runtime.
            try:
                profile_path = CHARACTERS_DIR / f"{ch.get('id') or 'character.unknown'}.json"
                profile = json.loads(profile_path.read_text(encoding="utf-8")) if profile_path.exists() else {}
                if not isinstance(profile, dict):
                    profile = {}
                ab_list = profile.get("abilities") if isinstance(profile.get("abilities"), list) else []
                if ability_id not in ab_list:
                    ab_list.append(ability_id)
                profile["abilities"] = ab_list
                profile.setdefault("id", ch.get("id"))
                profile.setdefault("name", ch.get("name"))
                profile.setdefault("path", ch.get("path"))
                profile["tier"] = ch.get("tier")
                profile.setdefault("attributes", ch.get("attributes") or {})
                CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
                profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
                # Also update legacy file.
                PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")
            except Exception as e:
                ui.error(f"Failed to save profile: {e}")

            # Refresh runtime character abilities
            try:
                ch["abilities"] = (profile.get("abilities") if isinstance(profile, dict) else []) or ch.get("abilities", [])
                hydrate_character_abilities(ch, ctx.get("game_data") or {})
            except Exception:
                pass

            ui.system(f"Learned: {offer.get('name', ability_id)} (-{cost} Vein)")
            if leveled:
                ui.system(f"Tier up: {ch.get('tier')}")
            try:
                save_profile_and_state(ch)
            except Exception:
                pass
            if not getattr(ui, "is_blocking", True):
                emit_character_update(ui, {
                    "name": ch.get("name"),
                    "hp": {"current": res.get("hp"), "max": res.get("hp_max", res.get("hp"))},
                    "rp": res.get("resolve"),
                    "rp_cap": res.get("resolve_cap", res.get("resolve")),
                    "veinscore": res.get("veinscore", ch.get("veinscore", 0)),
                    "abilities": ch.get("abilities", []),
                })
            emit_safe_room_enter(ctx)
            return True

        if requested_action == "safe_room_continue":
            # Advance campaign to the next scene.
            try:
                ensure_campaign(state, ctx.get("game_data", {}))
                camp = state.get("campaign", {}) if isinstance(state.get("campaign"), dict) else {}
                scene_ids = camp.get("scene_ids", []) if isinstance(camp.get("scene_ids"), list) else []
                idx = int(camp.get("index", 0) or 0) + 1
                if scene_ids and 0 <= idx < len(scene_ids):
                    camp["index"] = idx
                    state["campaign"] = camp
                    state.pop("mode", None)
                    enter_scene_into_state(ctx, scene_ids[idx])
                    return True
            except Exception:
                pass
            ui.system("No further scenes.")
            return True

        # Default: re-emit safe room screen so the UI never gets stranded.
        if not getattr(ui, "is_blocking", True):
            emit_safe_room_enter(ctx)
        return True

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

        # Loot flow while combat is over (web UI).
        if state.get("loot_pending"):
            if requested_action == "loot_take_all":
                items = state.get("loot_pending_items", [])
                apply_loot_to_player(state, items if isinstance(items, list) else [])
                ui.system("Loot claimed.")
                try:
                    emit_event(ui, {"type": "signal", "signalType": "loot", "text": "Spoils claimed."})
                except Exception:
                    pass
                # Push a character update so veinscore/etc can refresh immediately.
                try:
                    ch = state.get("party", {}).get("members", [None])[0]
                    if isinstance(ch, dict):
                        res = ch.get("resources", {}) if isinstance(ch.get("resources"), dict) else {}
                        emit_character_update(ui, {
                            "hp": {"current": res.get("hp"), "max": res.get("hp_max", res.get("max_hp", res.get("maxHp", res.get("hp"))))},
                            "rp": combat_get(state, ch, "rp", res.get("resolve", 0)),
                            "rp_cap": combat_get(state, ch, "rp_cap", res.get("resolve_cap", res.get("resolve", 0))),
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
                except Exception:
                    pass
                return True

            if requested_action == "loot_continue":
                state["loot_pending"] = False
                state.pop("loot_pending_items", None)
                # Continue behaves like the old combat_continue.
                state["combat_over"] = False
                state.pop("awaiting", None)
                state["phase"]["current"] = "out_of_combat"
                state.pop("encounter", None)
                emit_combat_state(ui, False)
                ui.system("Continuing...")
                # Advance to next scripted scene (if any) and prompt to enter.
                try:
                    ensure_campaign(state, ctx.get("game_data", {}))
                    camp = state.get("campaign", {}) if isinstance(state.get("campaign"), dict) else {}
                    scene_ids = camp.get("scene_ids", []) if isinstance(camp.get("scene_ids"), list) else []
                    idx = int(camp.get("index", 0) or 0) + 1
                    if scene_ids and 0 <= idx < len(scene_ids):
                        camp["index"] = idx
                        state["campaign"] = camp
                        enter_scene_into_state(ctx, scene_ids[idx])
                        return True
                except Exception:
                    pass
                if not getattr(ui, "is_blocking", True):
                    return game_step(ctx, {"action": "tick"})
                return True

            # Re-emit loot screen if the UI polls/refreshes.
            items = state.get("loot_pending_items", [])
            summary = "Victory spoils."
            rewards = state.get("scene_rewards", {}) if isinstance(state.get("scene_rewards"), dict) else {}
            if rewards.get("narration"):
                summary = str(rewards["narration"])
            emit_event(ui, {"type": "loot_screen", "items": items if isinstance(items, list) else [], "summary": summary})
            return True

        if requested_action == "defeat_continue":
            # No loot on defeat; apply Dun mark, restore HP, and restart the current encounter.
            apply_dun_mark_and_restore(state)

            # Reset combat state and restart encounter in the same scene (no campaign advance).
            state["combat_over"] = False
            state.pop("awaiting", None)
            state["loot_pending"] = False
            state.pop("loot_pending_items", None)
            state["scene_complete"] = False
            emit_combat_state(ui, False)

            # Reload the current scene to reset enemies/traps/hazards, then auto-enter encounter.
            scene_id = state.get("scene_id")
            if isinstance(scene_id, str) and scene_id:
                enter_scene_into_state(ctx, scene_id)

            # Auto-enter encounter and open chain builder immediately.
            state["phase"]["current"] = "chain_declaration"
            state["active_combatant"] = "player"
            emit_combat_state(ui, True)
            if state.get("enemies"):
                emit_enemy_update(ui, state, state["enemies"][0])
            try:
                player = state.get("party", {}).get("members", [None])[0]
                enemy = state.get("enemies", [None])[0] if state.get("enemies") else None
                if player and enemy:
                    register_participant(state, key="player", entity=player, side="player")
                    register_participant(state, key="enemy0", entity=enemy, side="enemy")
                    reset_encounter_meters(state, player=player, enemy=enemy, reset_rp=True)
            except Exception:
                pass

            if not ctx.get("combat"):
                ctx["combat"] = Combat(ctx, handle_chain_declaration, handle_chain_resolution, usable_ability_objects)
            ctx["combat"].start()

            ui.system("A Dun mark burns cold. You re-awaken.")
            return True

        if requested_action == "combat_loot":
            player = state.get("party", {}).get("members", [None])[0]
            enemy = state.get("enemies", [None])[0] if state.get("enemies") else None
            # Apply scene-complete events once on victory so loot can show the reward summary.
            try:
                scene = state.get("scene") if isinstance(state.get("scene"), dict) else None
                if scene and state.get("scene_complete") and not state.get("scene_rewards"):
                    apply_scene_complete_events(ctx)
            except Exception:
                pass

            gd = dict(game_data or {})
            if isinstance(state.get("scene"), dict):
                gd["__scene"] = state["scene"]

            items = build_victory_loot(gd, enemy=enemy)
            state["loot_pending"] = True
            state["loot_pending_items"] = items
            summary = "Victory spoils."
            rewards = state.get("scene_rewards", {}) if isinstance(state.get("scene_rewards"), dict) else {}
            if rewards.get("narration"):
                summary = str(rewards["narration"])
            emit_event(ui, {"type": "loot_screen", "items": items, "summary": summary})
            return True

        if requested_action == "combat_continue":
            state["combat_over"] = False
            state.pop("awaiting", None)
            state["phase"]["current"] = "out_of_combat"
            # Encounter boundary: clear combat meters and emit one authoritative update before dropping encounter state.
            try:
                player = state.get("party", {}).get("members", [None])[0]
                reset_encounter_meters(state, player=player, enemy=None, reset_rp=False)
                emit_authoritative_player_update(ui, state, player)
            except Exception:
                pass
            state.pop("encounter", None)
            emit_combat_state(ui, False)
            ui.system("Continuing...")
            if not getattr(ui, "is_blocking", True):
                return game_step(ctx, {"action": "tick"})
            return True

        player = state.get("party", {}).get("members", [None])[0]
        enemy = state.get("enemies", [None])[0] if state.get("enemies") else None
        player_dead = _hp(player) <= 0 if player else False
        enemy_dead = _hp(enemy) <= 0 if enemy else False
        result = "defeat" if player_dead else "victory" if enemy_dead else "ended"
        state["scene_complete"] = bool(enemy_dead)

        if enemy_dead:
            try:
                scene = state.get("scene") if isinstance(state.get("scene"), dict) else None
                if isinstance(scene, dict):
                    scene_flags = scene.get("flags")
                    if not isinstance(scene_flags, dict):
                        scene_flags = {}
                        scene["flags"] = scene_flags
                    scene_flags["all_enemies_defeated"] = True
            except Exception:
                pass
            try:
                apply_scene_complete_events(ctx)
            except Exception:
                pass
        if player_dead:
            try:
                ui.system("A Dun mark burns cold. You will re-awaken.")
            except Exception:
                pass

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
                    state["active_combatant"] = "player"
                    register_participant(state, key="player", entity=player, side="player")
                    register_participant(state, key="enemy0", entity=enemy, side="enemy")
                    # Encounter boundary: reset combat meters and refill resolve to cap.
                    reset_encounter_meters(state, player=player, enemy=enemy, reset_rp=True)
                except Exception:
                    pass

            emit_combat_state(ui, True)
            # Emit preview only on generate, not on enter (avoid duplicate log/system spam)
            if choice == "generate_encounter":
                emit_combat_log(ui, format_enemy_preview(enemy))
            # Always refresh the enemy HUD card.
            emit_enemy_update(ui, state, enemy)
            # Web: after generating an encounter, immediately offer the next required action.
            if not getattr(ui, "is_blocking", True) and choice == "generate_encounter":
                ui.choice("Enter encounter?", ["enter_encounter"])
                state["awaiting"] = {"type": "player_choice", "options": ["enter_encounter"]}
                return True
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
            # Single authoritative player update on encounter start (meters + rp after reset).
            try:
                emit_authoritative_player_update(ui, state, player)
            except Exception:
                pass
            return True

    # For non-blocking UIs, immediately surface the next prompt without waiting for another action payload.
    # If an interrupt just occurred, pause and wait for the user to read/react before advancing.
    if not getattr(ui, "is_blocking", True) and "awaiting" not in state:
        if state.pop("_pause_after_interrupt", False):
            return True
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
