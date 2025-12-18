
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, Optional
from pathlib import Path
from copy import deepcopy
from game_runner import Game
from game_session import GameSession
from ui.web_provider import WebProvider

app = FastAPI()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


sessions = {}

class StepRequest(BaseModel):
    session_id: str
    action: str | None = None
    choice: int | None = None
    chain: list[str] | None = None
    ability: str | None = None
    execute: bool | None = None
    name: str | None = None
    path: str | None = None
    rp_ability: str | None = None


class EmitRequest(BaseModel):
    session_id: str
    type: str
    text: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class EventsRequest(BaseModel):
    session_id: str


class CharacterSelectRequest(BaseModel):
    character_id: str


class CharacterCreateRequest(BaseModel):
    name: str
    path: str | None = None
    rp_ability: str | None = None
    tier1_abilities: list[str] | None = None
    select: bool = True


@app.get("/character")
def get_character():
    """
    Return the default character payload (from disk if present).
    """
    import play

    def normalize(char):
        char = deepcopy(char) if isinstance(char, dict) else {}
        resources = char.get("resources", {})
        attrs = char.get("attributes", {}) or char.get("stats", {})
        attr_map = {
            "POW": "str",
            "STR": "str",
            "AGI": "dex",
            "DEX": "dex",
            "MND": "int",
            "INT": "int",
            "SPR": "wil",
            "WIL": "wil",
        }
        norm_attrs = {
            "str": attrs.get("str") or attrs.get("STR") or attrs.get("POW"),
            "dex": attrs.get("dex") or attrs.get("DEX") or attrs.get("AGI"),
            "int": attrs.get("int") or attrs.get("INT") or attrs.get("MND"),
            "wil": attrs.get("wil") or attrs.get("WIL") or attrs.get("SPR"),
        }
        hp_val = resources.get("hp") or char.get("hp")
        if isinstance(hp_val, dict):
            hp_cur = hp_val.get("current") or hp_val.get("hp")
            hp_max = hp_val.get("max")
        else:
            hp_cur = hp_val
            hp_max = None
        hp_max = hp_max or resources.get("hp_max") or resources.get("max_hp") or resources.get("maxHp") or hp_cur
        rp = resources.get("resolve") or char.get("rp")
        veinscore = resources.get("veinscore") or char.get("veinscore", 0)
        return {
            "name": char.get("name"),
            "hp": {"current": hp_cur, "max": hp_max},
            "rp": rp,
            "veinscore": veinscore,
            "attributes": norm_attrs,
            "abilities": char.get("abilities", []),
        }

    # Load the current profile + mutable state, then hydrate ability IDs into full objects.
    try:
        payload = play.create_default_character()
    except Exception:
        payload = {}
    try:
        game_data = play.load_game_data()
        play.hydrate_character_abilities(payload, game_data)
    except Exception:
        pass

    return normalize(payload)


@app.get("/characters")
def list_characters():
    """
    List available character profiles (static) from `open-api-gm/characters/`.
    """
    root = Path(__file__).resolve().parent
    chars_dir = root / "characters"
    out = []
    if chars_dir.exists():
        for p in sorted(chars_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                out.append({
                    "id": data.get("id") or p.stem,
                    "name": data.get("name") or p.stem,
                    "path": data.get("path"),
                    "tier": data.get("tier"),
                })
            except Exception:
                continue
    return out


@app.post("/character/select")
def select_character(req: CharacterSelectRequest):
    """
    Select which profile `player_state.json` points at.
    """
    import play

    root = Path(__file__).resolve().parent
    chars_dir = root / "characters"
    target = chars_dir / f"{req.character_id}.json"
    if not target.exists():
        return {"ok": False, "error": f"Unknown character_id: {req.character_id}"}

    try:
        state_path = play.PLAYER_STATE_PATH
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        if not isinstance(state, dict):
            state = {}
        state["character_id"] = req.character_id
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        return {"ok": True, "character_id": req.character_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/character/create")
def create_character(req: CharacterCreateRequest):
    """
    Create a new character profile on disk and optionally select it in `player_state.json`.
    This avoids needing to go through the in-game /step character creation loop.
    """
    import play

    game_data = {}
    try:
        game_data = play.load_game_data()
    except Exception:
        game_data = {}

    allowed_paths = {p.get("id") for p in getattr(play, "CHARACTER_CREATE_PATHS", []) if isinstance(p, dict)}
    path_id = req.path if req.path in allowed_paths else None
    if req.path and not path_id:
        return {"ok": False, "error": f"Invalid path: {req.path}"}

    name = (req.name or "").strip()
    if not name:
        return {"ok": False, "error": "Missing name"}

    # Build a draft and apply the same starter rules as the in-game creator.
    ch = play._create_draft_character(path_id=path_id)
    ch["name"] = name

    # Ensure unique character id.
    base_id = play._character_id_from_name(name)
    root = Path(__file__).resolve().parent
    chars_dir = root / "characters"
    chars_dir.mkdir(parents=True, exist_ok=True)
    cid = base_id
    n = 2
    while (chars_dir / f"{cid}.json").exists():
        cid = f"{base_id}_{n}"
        n += 1
    ch["id"] = cid

    # Starter abilities: core + tier1 abilities for selected path (if any).
    starter = play._starter_ability_ids_for_path(path_id, game_data)
    ch["abilities"] = list(starter)

    # Add one resolve ability (optional).
    if req.rp_ability:
        catalog = play._resolve_ability_catalog(game_data)
        valid = {str(a.get("id") or a.get("name")) for a in catalog if isinstance(a, dict)}
        if req.rp_ability not in valid:
            return {"ok": False, "error": f"Invalid rp_ability: {req.rp_ability}"}
        if req.rp_ability not in ch["abilities"]:
            ch["abilities"].append(req.rp_ability)

    # Optional tier1 purchases: cost 1 each, up to starting veinscore (default 3).
    if req.tier1_abilities:
        try:
            offers = play.build_character_create_offers(ch, game_data)
        except Exception:
            offers = []
        offer_ids = {o.get("id") for o in offers if isinstance(o, dict) and o.get("id")}
        res = ch.get("resources", {}) if isinstance(ch.get("resources"), dict) else {}
        vein = int(res.get("veinscore", 0) or 0)
        for aid in req.tier1_abilities:
            if vein <= 0:
                break
            if aid not in offer_ids:
                return {"ok": False, "error": f"Invalid tier1 ability: {aid}"}
            if aid in ch["abilities"]:
                continue
            ch["abilities"].append(aid)
            vein -= 1
        res["veinscore"] = max(0, vein)

    # Hydrate for runtime/use in /character responses, then persist.
    try:
        play.hydrate_character_abilities(ch, game_data)
    except Exception:
        pass

    try:
        play.save_profile_and_state(ch)
    except Exception as e:
        return {"ok": False, "error": f"Failed to save: {e}"}

    if req.select:
        try:
            state_path = play.PLAYER_STATE_PATH
            state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
            if not isinstance(state, dict):
                state = {}
            state["character_id"] = cid
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception as e:
            return {"ok": False, "error": f"Created but failed to select: {e}", "character_id": cid}

    return {"ok": True, "character_id": cid, "selected": bool(req.select)}


@app.post("/step")
def step(req: StepRequest):
    # Starting a run should always rebuild the in-memory session so character selection
    # (player_state.json.character_id) is reflected immediately without requiring a server restart.
    if req.action in {"start"} and req.session_id in sessions:
        sessions.pop(req.session_id, None)

    if req.session_id not in sessions:
        session = GameSession(None)
        ui = WebProvider(session)
        game = Game(ui)
        session.game = game
        sessions[req.session_id] = session

    session = sessions[req.session_id]
    payload: Dict[str, Any] = {
        "action": req.action,
        "choice": req.choice,
        "chain": req.chain,
        "ability": req.ability,
        "execute": req.execute,
        "name": req.name,
        "path": req.path,
        "rp_ability": req.rp_ability,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    events = session.step(payload)
    return events


@app.post("/emit")
def emit(req: EmitRequest):
    if req.session_id not in sessions:
        session = GameSession(None)
        ui = WebProvider(session)
        game = Game(ui)
        session.game = game
        sessions[req.session_id] = session

    session = sessions[req.session_id]
    payload = req.payload or {"type": req.type, "text": req.text}
    session.emit(payload)
    return session.events


@app.post("/events")
def events(req: EventsRequest):
    if req.session_id not in sessions:
        return []
    session = sessions[req.session_id]
    evs = session.events[:]
    session.events = []
    return evs
