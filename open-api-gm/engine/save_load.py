import json
from pathlib import Path


_BASE_DIR = Path(__file__).resolve().parents[1]


def _resolve_path(filename: str | Path) -> Path:
    p = filename if isinstance(filename, Path) else Path(str(filename))
    return p if p.is_absolute() else (_BASE_DIR / p)

def save_character(character, filename: str | Path = "player_state.json"):
    """
    Persist mutable player state.
    Character profiles are kept in separate files under `characters/`.
    """
    path = _resolve_path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(character, indent=2), encoding="utf-8")

def load_character(filename: str | Path = "player_state.json"):
    """
    Load mutable player state (default: `player_state.json`).
    """
    path = _resolve_path(filename)
    return json.loads(path.read_text(encoding="utf-8"))


def load_profile(filename: str | Path = "characters/character.new_blood.json"):
    """
    Load a character profile (static info + ability ids).
    """
    path = _resolve_path(filename)
    return json.loads(path.read_text(encoding="utf-8"))
