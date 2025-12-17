from __future__ import annotations

from typing import Any, Dict, Optional


COMBAT_METERS = {"heat", "balance", "momentum", "rp", "rp_cap"}


def ensure_encounter(state: Dict[str, Any]) -> Dict[str, Any]:
    enc = state.setdefault("encounter", {})
    enc.setdefault("participants", {})
    return enc


def register_participant(state: Dict[str, Any], *, key: str, entity: Dict[str, Any], side: str) -> None:
    enc = ensure_encounter(state)
    participants = enc["participants"]
    res = entity.get("resources", {}) if isinstance(entity.get("resources"), dict) else {}
    rp = res.get("resolve")
    if rp is None:
        rp = entity.get("rp")
    rp_cap = res.get("resolve_cap") or entity.get("rp_cap") or entity.get("resolve_cap")
    participants[key] = {
        "key": key,
        "side": side,
        "id": entity.get("id") or entity.get("name") or key,
        "combat": {
            "heat": 0,
            "balance": 0,
            "momentum": 0,
            "rp": int(rp or 0),
            "rp_cap": int(rp_cap or rp or 0),
        },
    }
    entity["_combat_key"] = key


def participant(state: Dict[str, Any], entity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    key = entity.get("_combat_key") if isinstance(entity, dict) else None
    if not key:
        return None
    enc = state.get("encounter") if isinstance(state, dict) else None
    participants = enc.get("participants") if isinstance(enc, dict) else None
    if not isinstance(participants, dict):
        return None
    p = participants.get(key)
    return p if isinstance(p, dict) else None


def combat_get(state: Dict[str, Any], entity: Dict[str, Any], meter: str, default: int = 0) -> int:
    if meter not in COMBAT_METERS:
        raise KeyError(f"Unknown combat meter: {meter}")
    p = participant(state, entity)
    if not p:
        return int(default)
    combat = p.get("combat")
    if not isinstance(combat, dict):
        return int(default)
    return int(combat.get(meter, default) or 0)


def combat_set(state: Dict[str, Any], entity: Dict[str, Any], meter: str, value: int) -> None:
    if meter not in COMBAT_METERS:
        raise KeyError(f"Unknown combat meter: {meter}")
    p = participant(state, entity)
    if not p:
        return
    combat = p.setdefault("combat", {})
    combat[meter] = int(value)


def combat_add(state: Dict[str, Any], entity: Dict[str, Any], meter: str, delta: int) -> int:
    cur = combat_get(state, entity, meter, 0)
    nxt = int(cur + int(delta))
    combat_set(state, entity, meter, nxt)
    return nxt


def combat_reset(state: Dict[str, Any], entity: Dict[str, Any]) -> None:
    for m in COMBAT_METERS:
        combat_set(state, entity, m, 0)
