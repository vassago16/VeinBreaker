import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import chain_rules  # noqa: E402


class TestChainRules(unittest.TestCase):
    def test_can_declare_chain_enforces_phase(self):
        state = {"phase": {"current": "out_of_combat"}}
        ok, msg = chain_rules.can_declare_chain(state, {})
        self.assertFalse(ok)
        self.assertIn("chain_declaration", msg)

    def test_validate_chain_abilities_requires_owned(self):
        character = {"abilities": [{"name": "A"}]}
        ok, msg = chain_rules.validate_chain_abilities(character, ["A", "B"])
        self.assertFalse(ok)
        self.assertIn("Ability not owned", msg)


if __name__ == "__main__":
    unittest.main()
