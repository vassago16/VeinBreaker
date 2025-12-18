import math
import random

# Statuses that are treated as non-stackable; re-applying extends duration.
NON_STACKING = {
    "telegraph",
    "slowed",
    "distracted",
    "exhausted",
    "invisibility",
    "intangible",
    "quickened",
    "retaliate",
}


def normalize_effect(effect, default_duration=2):
    """
    Normalize an effect entry from data into (type, stacks, duration).
    Strings become type with 1 stack. Objects may specify stacks/duration.
    """
    if isinstance(effect, str):
        return effect.lower(), 1, default_duration
    if isinstance(effect, dict):
        etype = str(effect.get("type", "")).lower()
        stacks = effect.get("stacks", 1)
        duration = effect.get("duration", default_duration)
        return etype, stacks, duration
    return None, None, None


def apply_status_effects(target, effects, default_duration=2):
    """
    Apply a list of on-hit effects to a target (player or enemy).
    Stores on target["statuses"][type] = {"stacks": int, "duration": int}
    Stackable: adds stacks and refreshes duration.
    Non-stackable: reapplication extends duration by default_duration.
    """
    if target is None or not effects:
        return []
    target.setdefault("statuses", {})
    applied = []
    for eff in effects:
        etype, stacks, duration = normalize_effect(eff, default_duration=default_duration)
        if not etype:
            continue
        if duration is None:
            duration = default_duration
        status = target["statuses"].get(etype, {"stacks": 0, "duration": 0})
        if etype in NON_STACKING:
            # Non-stacking: keep stacks at max(1, existing) and extend duration
            status["stacks"] = max(status.get("stacks", 0), 1)
            status["duration"] = status.get("duration", 0) + duration
        else:
            # Stackable: add stacks and refresh duration
            status["stacks"] = status.get("stacks", 0) + (stacks or 0)
            status["duration"] = max(status.get("duration", 0), duration)
        target["statuses"][etype] = status
        applied.append(etype)
    return applied


def tick_statuses(target):
    """
    Tick durations and apply ongoing effects (e.g., Bleed damage).
    Returns a summary dict with any damage applied.
    """
    if not target or "statuses" not in target:
        return {}
    summary = {"damage": 0, "expired": []}
    statuses = target.get("statuses", {})
    to_remove = []
    for etype, data in list(statuses.items()):
        stacks = data.get("stacks", 0) or 0
        duration = data.get("duration", 0) or 0

        # Ongoing damage hooks
        if etype in {"bleed", "radiant burn"} and stacks > 0:
            dmg = stacks  # 1 damage per stack
            # Support both character (resources.hp) and enemy (top-level hp) storage
            if "resources" in target and "hp" in target["resources"]:
                res = target["resources"]
                res["hp"] = max(0, res.get("hp", 0) - dmg)
            else:
                target["hp"] = max(0, target.get("hp", 0) - dmg)
            summary["damage"] += dmg

        # Decrement duration
        duration -= 1
        if duration <= 0:
            to_remove.append(etype)
        else:
            statuses[etype]["duration"] = duration

    for etype in to_remove:
        statuses.pop(etype, None)
        summary["expired"].append(etype)

    return summary
