"""
Shared UI event emitters.
Works for both CLI and Web providers by probing for a session.emit hook.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


_DEBUG_LOG_PATH = Path(__file__).resolve().parents[1] / "narration.log"


def _debug_log(line: str) -> None:
    try:
        ts = datetime.now().strftime("%H:%M:%S")
        _DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(f"{ts} {line}\n")
    except Exception:
        # never break game loop for debug logging
        pass


def emit_event(ui, payload: Dict[str, Any]) -> None:
    """
    Best-effort emit of structured events for non-blocking UIs.
    Falls back silently for CLI.
    """
    try:
        provider = getattr(ui, "provider", None) or ui
        session = getattr(provider, "session", None)
        # Debug a few critical wiring events; this helps trace "event emitted but not seen" issues.
        try:
            t = payload.get("type") if isinstance(payload, dict) else None
            if t in {"interrupt_window", "interrupt", "chain_interrupted", "combat_result", "declare_chain"}:
                _debug_log(
                    f"DEBUG: emit_event type={t} "
                    f"(has_session={bool(session)}, has_emit={bool(session and hasattr(session, 'emit'))})"
                )
        except Exception:
            pass
        if session and hasattr(session, "emit"):
            session.emit(payload)
    except Exception:
        # Swallow silently; emitting should never break the game loop.
        pass


def build_combat_state(active: bool) -> Dict[str, Any]:
    return {"type": "combat_state", "active": active}


def emit_combat_state(ui, active: bool) -> None:
    emit_event(ui, build_combat_state(active))


def emit_combat_log(ui, text: str, log_type: str | None = None) -> None:
    payload = {"type": "combat_log", "text": text}
    if log_type:
        payload["logType"] = log_type
    emit_event(ui, payload)
    ui.system(text)


def emit_interrupt(ui) -> None:
    emit_event(ui, {"type": "interrupt"})


def build_character_update(character: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(character, dict):
        character = {}

    resources = character.get("resources", {}) if isinstance(character.get("resources"), dict) else {}

    hp = character.get("hp")
    if hp is None:
        hp_cur = resources.get("hp")
        hp_max = resources.get("hp_max", resources.get("max_hp", resources.get("maxHp", hp_cur)))
        if hp_cur is not None:
            hp = {"current": hp_cur, "max": hp_max if hp_max is not None else hp_cur}

    rp = character.get("rp")
    if rp is None:
        rp = resources.get("resolve")
    rp_cap = character.get("rp_cap")
    if rp_cap is None:
        rp_cap = resources.get("resolve_cap")

    veinscore = character.get("veinscore")
    if veinscore is None:
        veinscore = resources.get("veinscore")

    meters = character.get("meters")

    # Compact ability payload: id + cooldown only (UI keeps a catalog from /character).
    abilities_full = character.get("abilities") or []
    abilities = []
    if isinstance(abilities_full, list):
        for ab in abilities_full:
            if not isinstance(ab, dict):
                continue
            abilities.append({
                "id": ab.get("id") or ab.get("name"),
                "cooldown": ab.get("cooldown", 0),
            })
    return {
        "type": "character_update",
        "character": {
            "name": character.get("name"),
            "hp": hp,
            "rp": {"current": rp, "cap": rp_cap} if rp_cap is not None else rp,
            "veinscore": veinscore,
            "abilities": abilities,
            "meters": meters,
        }
    }


def emit_character_update(ui, character: Dict[str, Any]) -> None:
    try:
        abilities = character.get("abilities") if isinstance(character, dict) else None
        if isinstance(abilities, list):
            pulse = next((a for a in abilities if isinstance(a, dict) and a.get("name") == "Pulse Strike"), None)
            if pulse is not None:
                _debug_log(
                    "DEBUG: character_update emitted "
                    f"(hp={character.get('hp')}, rp={character.get('rp')}, "
                    f"pulse_cd={pulse.get('cooldown')}, pulse_base_cd={pulse.get('base_cooldown')})"
                )
    except Exception:
        pass
    emit_event(ui, build_character_update(character))


def emit_resource_update(ui, *, momentum: int | None = None, balance: int | None = None, heat: int | None = None) -> None:
    payload: Dict[str, Any] = {"type": "resource_update"}
    if momentum is not None:
        payload["momentum"] = int(momentum)
    if balance is not None:
        payload["balance"] = int(balance)
    if heat is not None:
        payload["heat"] = int(heat)
    emit_event(ui, payload)


def emit_declare_chain(ui, abilities: List[Dict[str, Any]], max_len: int = 3) -> None:
    emit_event(ui, build_declare_chain(abilities, max_len))


def build_declare_chain(abilities: List[Dict[str, Any]], max_len: int = 3) -> Dict[str, Any]:
    payload = []
    for ab in abilities:
        if not isinstance(ab, dict):
            continue
        cd = ab.get("cooldown")
        if cd is None:
            cd = ab.get("base_cooldown", 0)
        payload.append({
            "id": ab.get("id") or ab.get("name"),
            "name": ab.get("name"),
            "type": ab.get("type"),
            "cost": ab.get("cost"),
            "cooldown": cd,
            "effect": ab.get("effect") or (ab.get("effects") or {}).get("on_use"),
        })
    return {
        "type": "declare_chain",
        "maxLength": max_len,
        "chainRules": {
            "min": 0,
            "max": max_len,
            "source": "Momentum + Tier Bonus",
        },
        "abilities": payload
    }
