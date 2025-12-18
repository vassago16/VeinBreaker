import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.action_resolution import conditions_met  # noqa: E402


class DummyCtx:
    def __init__(self):
        self.resources = {"resolve": 3, "heat": 2}
        self.enemy = type("E", (), {"statuses": {"bleed": {"stacks": 1}}, "other": True})
        self.self = type("S", (), {"statuses": {"arcane ward": {"duration": 1}}})
        self.chain_length = 3
        self.last_action = type("L", (), {"field": "x"})
        self.hit_result = "hit"


class TestConditionsMet(unittest.TestCase):
    def test_resource_condition(self):
        ctx = DummyCtx()
        cond = {"type": "resource", "resource": "resolve", "op": ">=", "value": 3}
        self.assertTrue(conditions_met(cond, ctx))
        cond2 = {"type": "resource", "resource": "heat", "op": ">=", "value": 3}
        self.assertFalse(conditions_met(cond2, ctx))

    def test_status_condition(self):
        ctx = DummyCtx()
        cond = {"type": "status", "target": "enemy", "status": "bleed", "present": True}
        self.assertTrue(conditions_met(cond, ctx))
        cond2 = {"type": "status", "target": "self", "status": "bleed", "present": True}
        self.assertFalse(conditions_met(cond2, ctx))

    def test_chain_length_condition(self):
        ctx = DummyCtx()
        cond = {"type": "chain_length", "op": ">=", "value": 3}
        self.assertTrue(conditions_met(cond, ctx))

    def test_last_action_condition(self):
        ctx = DummyCtx()
        cond = {"type": "last_action", "field": "field", "equals": "x"}
        self.assertTrue(conditions_met(cond, ctx))

    def test_hit_result_condition(self):
        ctx = DummyCtx()
        cond = {"type": "hit_result", "value": "hit"}
        self.assertTrue(conditions_met(cond, ctx))

    def test_nested_all_any_not(self):
        ctx = DummyCtx()
        cond = {
            "all": [
                {"type": "resource", "resource": "resolve", "op": ">=", "value": 3},
                {"any": [
                    {"type": "status", "target": "enemy", "status": "bleed", "present": True},
                    {"type": "status", "target": "enemy", "status": "stagger", "present": True},
                ]},
                {"not": {"type": "resource", "resource": "heat", "op": ">", "value": 5}}
            ]
        }
        self.assertTrue(conditions_met(cond, ctx))


if __name__ == "__main__":
    unittest.main()
