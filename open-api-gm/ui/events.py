"""
Shared UI event emitters.
Works for both CLI and Web providers by probing for a session.emit hook.
"""

from typing import Any, Dict, List


def emit_event(ui, payload: Dict[str, Any]) -> None:
    """
    Best-effort emit of structured events for non-blocking UIs.
    Falls back silently for CLI.
    """
    try:
        provider = getattr(ui, "provider", None) or ui
        session = getattr(provider, "session", None)
        if session and hasattr(session, "emit"):
            session.emit(payload)
    except Exception:
        # Swallow silently; emitting should never break the game loop.
        pass


def build_combat_state(active: bool) -> Dict[str, Any]:
    return {"type": "combat_state", "active": active}


def emit_combat_state(ui, active: bool) -> None:
    emit_event(ui, build_combat_state(active))


def emit_combat_log(ui, text: str) -> None:
    emit_event(ui, {"type": "combat_log", "text": text})
    ui.system(text)


def emit_interrupt(ui) -> None:
    emit_event(ui, {"type": "interrupt"})


def build_character_update(character: Dict[str, Any]) -> Dict[str, Any]:
    attrs = character.get("attributes", {}) if isinstance(character, dict) else {}
    norm_attrs = {
        "str": attrs.get("str") or attrs.get("STR") or attrs.get("POW"),
        "dex": attrs.get("dex") or attrs.get("DEX") or attrs.get("AGI"),
        "int": attrs.get("int") or attrs.get("INT") or attrs.get("MND"),
        "wil": attrs.get("wil") or attrs.get("WIL") or attrs.get("SPR"),
    }
    return {
        "type": "character_update",
        "character": {
            "name": character.get("name"),
            "hp": character.get("hp"),
            "rp": character.get("rp"),
            "veinscore": character.get("veinscore"),
            "attributes": norm_attrs,
        }
    }


def emit_character_update(ui, character: Dict[str, Any]) -> None:
    emit_event(ui, build_character_update(character))


def emit_declare_chain(ui, abilities: List[Dict[str, Any]], max_len: int = 3) -> None:
    emit_event(ui, build_declare_chain(abilities, max_len))


def build_declare_chain(abilities: List[Dict[str, Any]], max_len: int = 3) -> Dict[str, Any]:
    payload = []
    for ab in abilities:
        if not isinstance(ab, dict):
            continue
        payload.append({
            "id": ab.get("id") or ab.get("name"),
            "name": ab.get("name"),
            "type": ab.get("type"),
            "cost": ab.get("cost"),
            "cooldown": ab.get("cooldown") or ab.get("base_cooldown"),
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
