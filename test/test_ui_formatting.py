import unittest

from ui.formatting import format_money, format_quantity, quantity_to_int


class UIFormattingTests(unittest.TestCase):
    def test_quantities_are_displayed_as_integers(self):
        self.assertEqual(format_quantity("10.00"), "10")
        self.assertEqual(format_quantity("7.4"), "7")
        self.assertEqual(format_quantity("7.5"), "8")

    def test_money_keeps_two_decimals(self):
        self.assertEqual(format_money("10"), "10.00")
        self.assertEqual(format_money("1234.5", "DA"), "1,234.50 DA")

    def test_number_parsing_accepts_decimal_and_thousand_commas(self):
        self.assertEqual(quantity_to_int("12,0"), 12)
        self.assertEqual(format_money("1,234.50"), "1,234.50")


if __name__ == "__main__":
    unittest.main()
