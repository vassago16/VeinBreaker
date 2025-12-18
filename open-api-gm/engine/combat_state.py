from __future__ import annotations

from typing import Any, Dict, Optional


COMBAT_METERS = {"heat", "balance", "momentum", "rp", "rp_cap"}


def _status_id(name: str) -> str:
    s = "".join(ch.lower() if ch.isalnum() else "_" for ch in (name or "").strip())
    s = "_".join([p for p in s.split("_") if p])
    return f"status.{s}" if s else "status.unknown"


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
        "statuses": {},
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


def status_add(
    state: Dict[str, Any],
    entity: Dict[str, Any],
    *,
    status: str,
    stacks: int = 1,
    duration_rounds: int = 1,
    shield: int = 0,
) -> None:
    p = participant(state, entity)
    if not p:
        return
    statuses = p.setdefault("statuses", {})
    if not isinstance(statuses, dict):
        statuses = {}
        p["statuses"] = statuses

    sid = status if status.startswith("status.") else _status_id(status)
    cur = statuses.get(sid) if isinstance(statuses.get(sid), dict) else {}
    cur_stacks = int(cur.get("stacks", 0) or 0)
    statuses[sid] = {
        "id": sid,
        "name": cur.get("name") or status,
        "stacks": cur_stacks + int(stacks or 0),
        "duration_rounds": int(cur.get("duration_rounds", 0) or 0) or int(duration_rounds or 0),
        "shield": int(cur.get("shield", 0) or 0) or int(shield or 0),
    }


def status_get(state: Dict[str, Any], entity: Dict[str, Any], status_id: str) -> Optional[Dict[str, Any]]:
    p = participant(state, entity)
    if not p:
        return None
    statuses = p.get("statuses")
    if not isinstance(statuses, dict):
        return None
    st = statuses.get(status_id)
    return st if isinstance(st, dict) else None


def shield_value(state: Dict[str, Any], entity: Dict[str, Any]) -> int:
    p = participant(state, entity)
    if not p:
        return 0
    statuses = p.get("statuses")
    if not isinstance(statuses, dict):
        return 0
    total = 0
    for st in statuses.values():
        if not isinstance(st, dict):
            continue
        stacks = int(st.get("stacks", 0) or 0)
        shield = int(st.get("shield", 0) or 0)
        if stacks > 0 and shield > 0:
            total += shield
    return total


def consume_shield(state: Dict[str, Any], entity: Dict[str, Any], amount: int = 1) -> int:
    """
    Consume up to `amount` shield from statuses, returning how much was actually consumed.
    Current policy: consumes one stack from the first status that provides shield.
    """
    if amount <= 0:
        return 0
    p = participant(state, entity)
    if not p:
        return 0
    statuses = p.get("statuses")
    if not isinstance(statuses, dict):
        return 0
    for sid, st in list(statuses.items()):
        if not isinstance(st, dict):
            continue
        stacks = int(st.get("stacks", 0) or 0)
        shield = int(st.get("shield", 0) or 0)
        if stacks <= 0 or shield <= 0:
            continue
        # Consume one stack worth of shield.
        st["stacks"] = stacks - 1
        if st["stacks"] <= 0:
            statuses.pop(sid, None)
        return min(amount, shield)
    return 0
