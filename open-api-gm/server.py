
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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


@app.get("/character")
def get_character():
    """
    Return the default character payload (from disk if present).
    """
    import play
    from copy import deepcopy

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
        hp_cur = resources.get("hp") or char.get("hp")
        hp_max = resources.get("hp_max") or resources.get("max_hp") or resources.get("maxHp") or hp_cur
        rp = resources.get("resolve") or char.get("rp")
        veinscore = resources.get("veinscore") or char.get("veinscore", 0)
        return {
            "name": char.get("name"),
            "hp": {"current": hp_cur, "max": hp_max},
            "rp": rp,
            "veinscore": veinscore,
            "attributes": norm_attrs,
        }

    try:
        path = play.DEFAULT_CHARACTER_PATH
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = play.create_default_character()

    return normalize(payload)


@app.post("/step")
def step(req: StepRequest):
    if req.session_id not in sessions:
        session = GameSession(None)
        ui = WebProvider(session)
        game = Game(ui)
        session.game = game
        sessions[req.session_id] = session

    session = sessions[req.session_id]
    events = session.step({
        "action": req.action,
        "choice": req.choice
    })
    return events
