import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from play import apply_vein_tier_progression  # noqa: E402


class TestTier2Attainment(unittest.TestCase):
    def test_tier2_attained_at_3_veinscore(self):
        ch = {
            "tier": 1,
            "resources": {
                "hp": 20,
                "hp_max": 20,
                "resolve": 5,
                "veinscore": 3,
            },
            "_veins_spent_total": 0,
        }

        info = apply_vein_tier_progression(ch)

        self.assertTrue(info["leveled"])
        self.assertEqual(info["after"], 2)
        self.assertEqual(ch["tier"], 2)
        self.assertEqual(ch["resources"]["hp_max"], 30)
        self.assertEqual(ch["resources"]["resolve_cap"], 7)


if __name__ == "__main__":
    unittest.main()

