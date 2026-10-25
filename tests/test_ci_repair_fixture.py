"""Controlled real-CI repair exercise. Assertions must never be weakened by the repair agent."""
import unittest
from qa.fixtures.ci_repair.arithmetic import add


class Arithmetic(unittest.TestCase):
    def test_positive_sum(self):
        self.assertEqual(add(19, 23), 42)

    def test_cancellation(self):
        self.assertEqual(add(-7, 7), 0)

    def test_zero_identity(self):
        self.assertEqual(add(0, 0), 0)


if __name__ == '__main__': unittest.main()
