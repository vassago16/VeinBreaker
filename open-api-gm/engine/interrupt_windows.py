from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class InterruptContext:
    # Who is acting / defending
    aggressor: Dict[str, Any]
    defender: Dict[str, Any]

    # Chain state
    chain_index: int
    chain_length: int
    link: Dict[str, Any]

    # Roll/contest context (optional)
    attack_d20: int
    defender_d20: int

    # Shared state access
    state: Dict[str, Any]


def _get(d: Dict[str, Any], path: str, default=None):
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _compare(a: int | float, op: str, b: int | float) -> bool:
    if op == "==": return a == b
    if op == "!=": return a != b
    if op == ">":  return a > b
    if op == ">=": return a >= b
    if op == "<":  return a < b
    if op == "<=": return a <= b
    raise ValueError(f"Unknown op: {op}")


def eval_predicate(pred: Dict[str, Any], ctx: InterruptContext) -> bool:
    """
    Tiny predicate DSL for interrupt windows.

    Examples:
      {"type":"chain_index_at_least","value":1}
      {"type":"defender_resource_at_least","resource":"rp","value":1}
      {"type":"attacker_momentum_at_least","value":2}
      {"type":"link_type_is","value":"attack"}
      {"type":"always"}
      {"type":"not", "pred": {...}}
      {"type":"and", "preds":[...]}
      {"type":"or", "preds":[...]}
    """
    t = pred.get("type", "always")

    if t == "always":
        return True

    if t == "chain_index_at_least":
        return ctx.chain_index >= int(pred.get("value", 0))

    if t == "chain_index_is":
        return ctx.chain_index == int(pred.get("value", 0))

    if t == "chain_length_at_least":
        return ctx.chain_length >= int(pred.get("value", 0))

    if t == "link_type_is":
        return (ctx.link.get("type") or "").lower() == str(pred.get("value", "")).lower()

    if t == "defender_resource_at_least":
        r = pred.get("resource", "")
        v = int(pred.get("value", 0))
        return int(_get(ctx.defender, f"resources.{r}", 0)) >= v

    if t == "attacker_momentum_at_least":
        v = int(pred.get("value", 0))
        return int(_get(ctx.aggressor, "resources.momentum", 0)) >= v

    if t == "compare":
        # generic comparison for quick experiments
        # {"type":"compare","left":"defender.resources.rp","op":">=","right":1}
        left = pred.get("left")
        op = pred.get("op")
        right = pred.get("right")
        if not isinstance(left, str) or not isinstance(op, str):
            return False
        lv = _get({"attacker": ctx.aggressor, "defender": ctx.defender, "state": ctx.state}, left, 0)
        return _compare(float(lv), op, float(right))

    if t == "not":
        return not eval_predicate(pred.get("pred", {"type": "always"}), ctx)

    if t == "and":
        return all(eval_predicate(p, ctx) for p in pred.get("preds", []))

    if t == "or":
        return any(eval_predicate(p, ctx) for p in pred.get("preds", []))

    raise ValueError(f"Unknown predicate type: {t}")


def window_allows_interrupt(windows: List[Dict[str, Any]], when: str, ctx: InterruptContext) -> Optional[Dict[str, Any]]:
    """
    Returns the first matching window config if any.
    Window format:
      {
        "when": "before_link" | "after_link",
        "if": { predicate },
        "chance": 0.35,           # optional; AI policy can use
        "priority": 10            # optional
      }
    """
    candidates = []
    for w in windows or []:
        if w.get("when") != when:
            continue
        pred = w.get("if", {"type": "always"})
        if eval_predicate(pred, ctx):
            candidates.append(w)

    if not candidates:
        return None

    # highest priority wins
    candidates.sort(key=lambda x: int(x.get("priority", 0)), reverse=True)
    return candidates[0]
