import unittest
from unittest.mock import patch

from engine.dice import roll_2d10_modified


class TestAdvDisadvDice(unittest.TestCase):
    def test_disadvantage_3d10_keep_high_low(self):
        # rolls: 2, 9, 5 -> keep 2+9 = 11
        with patch("random.randint", side_effect=[2, 9, 5]):
            total, meta = roll_2d10_modified("disadvantage")
        self.assertEqual(total, 11)
        self.assertEqual(sorted(meta["kept"]), [2, 9])

    def test_severe_disadvantage_4d10_keep_high_low(self):
        # rolls: 1, 10, 4, 7 -> keep 1+10 = 11
        with patch("random.randint", side_effect=[1, 10, 4, 7]):
            total, meta = roll_2d10_modified("severe_disadvantage")
        self.assertEqual(total, 11)
        self.assertEqual(sorted(meta["kept"]), [1, 10])

    def test_extreme_disadvantage_4d10_keep_two_lowest(self):
        # rolls: 1, 10, 4, 7 -> keep 1+4 = 5
        with patch("random.randint", side_effect=[1, 10, 4, 7]):
            total, meta = roll_2d10_modified("extreme_disadvantage")
        self.assertEqual(total, 5)
        self.assertEqual(sorted(meta["kept"]), [1, 4])

    def test_advantage_3d10_keep_two_highest(self):
        # rolls: 2, 9, 5 -> keep 5+9 = 14
        with patch("random.randint", side_effect=[2, 9, 5]):
            total, meta = roll_2d10_modified("advantage")
        self.assertEqual(total, 14)
        self.assertEqual(sorted(meta["kept"]), [5, 9])

