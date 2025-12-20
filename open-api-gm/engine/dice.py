from __future__ import annotations

import random
from typing import Any, Dict, Optional, Tuple


RollMode = str  # "normal" | "advantage" | "severe_advantage" | "extreme_advantage" | "disadvantage" | "severe_disadvantage" | "extreme_disadvantage"


def _roll_d10() -> int:
    return random.randint(1, 10)


def roll_2d10_modified(mode: RollMode = "normal") -> Tuple[int, Dict[str, Any]]:
    """
    Returns (total, meta) where meta contains the raw rolls and what was kept.

    Definitions (as requested):
      - disadvantage: roll 3d10, take the highest and lowest (discard the middle)
      - severe_disadvantage: roll 4d10, take the highest and lowest (discard the middle two)
      - extreme_disadvantage: roll 4d10, take the two lowest
      - advantage: inverse of disadvantage => roll 3d10, take the two highest
      - severe_advantage: inverse of severe_disadvantage => roll 4d10, take the two highest
      - extreme_advantage: inverse of extreme_disadvantage => roll 4d10, take the two highest
      - normal: roll 2d10, sum both
    """
    mode = str(mode or "normal").strip().lower()

    if mode == "normal":
        rolls = [_roll_d10(), _roll_d10()]
        kept = list(rolls)
        return int(sum(kept)), {"mode": mode, "rolls": rolls, "kept": kept}

    if mode == "disadvantage":
        rolls = [_roll_d10(), _roll_d10(), _roll_d10()]
        s = sorted(rolls)
        kept = [s[0], s[-1]]
        return int(sum(kept)), {"mode": mode, "rolls": rolls, "kept": kept}

    if mode == "severe_disadvantage":
        rolls = [_roll_d10(), _roll_d10(), _roll_d10(), _roll_d10()]
        s = sorted(rolls)
        kept = [s[0], s[-1]]
        return int(sum(kept)), {"mode": mode, "rolls": rolls, "kept": kept}

    if mode == "extreme_disadvantage":
        rolls = [_roll_d10(), _roll_d10(), _roll_d10(), _roll_d10()]
        s = sorted(rolls)
        kept = [s[0], s[1]]
        return int(sum(kept)), {"mode": mode, "rolls": rolls, "kept": kept}

    if mode == "advantage":
        rolls = [_roll_d10(), _roll_d10(), _roll_d10()]
        s = sorted(rolls)
        kept = [s[-2], s[-1]]
        return int(sum(kept)), {"mode": mode, "rolls": rolls, "kept": kept}

    if mode == "severe_advantage":
        rolls = [_roll_d10(), _roll_d10(), _roll_d10(), _roll_d10()]
        s = sorted(rolls)
        kept = [s[-2], s[-1]]
        return int(sum(kept)), {"mode": mode, "rolls": rolls, "kept": kept}

    if mode == "extreme_advantage":
        rolls = [_roll_d10(), _roll_d10(), _roll_d10(), _roll_d10()]
        s = sorted(rolls)
        kept = [s[-2], s[-1]]
        return int(sum(kept)), {"mode": mode, "rolls": rolls, "kept": kept}

    # Unknown mode falls back to normal.
    rolls = [_roll_d10(), _roll_d10()]
    kept = list(rolls)
    return int(sum(kept)), {"mode": "normal", "rolls": rolls, "kept": kept}


def _encounter_status_stacks(state: dict, entity: dict, status_name: str) -> int:
    try:
        from engine.combat_state import status_get
    except Exception:
        return 0
    if not isinstance(state, dict) or not isinstance(entity, dict):
        return 0
    sid = "status." + "".join(ch.lower() if ch.isalnum() else "_" for ch in str(status_name or "").strip())
    sid = "_".join([p for p in sid.split("_") if p])
    st = status_get(state, entity, sid)
    if not isinstance(st, dict):
        return 0
    return int(st.get("stacks", 0) or 0)


def roll_mode_for_entity(state: Optional[dict], entity: Optional[dict]) -> RollMode:
    """
    Map current statuses into a roll mode. For now only Stagger is implemented:
      - Stagger 1 => disadvantage
      - Stagger 2 => severe_disadvantage
      - Stagger 3+ => extreme_disadvantage
    """
    if not isinstance(state, dict) or not isinstance(entity, dict):
        return "normal"
    stacks = _encounter_status_stacks(state, entity, "stagger")
    if stacks >= 3:
        return "extreme_disadvantage"
    if stacks == 2:
        return "severe_disadvantage"
    if stacks == 1:
        return "disadvantage"
    return "normal"

