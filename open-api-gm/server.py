
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

    try:
        path = play.DEFAULT_CHARACTER_PATH
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return play.create_default_character()


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
