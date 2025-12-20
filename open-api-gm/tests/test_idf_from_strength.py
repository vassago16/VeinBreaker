import unittest

from engine.stats import idf_from_strength


class TestIdfFromStrength(unittest.TestCase):
    def test_idf_baseline(self):
        self.assertEqual(idf_from_strength(8), 0)
        self.assertEqual(idf_from_strength(10), 1)
        self.assertEqual(idf_from_strength(12), 2)


if __name__ == "__main__":
    unittest.main()

