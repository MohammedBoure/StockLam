import unittest
from decimal import Decimal

from ui.formatting import format_money, format_quantity, quantity_to_int, _to_decimal


class UIFormattingTests(unittest.TestCase):
    def test_quantities_are_displayed_as_integers(self):
        self.assertEqual(format_quantity("10.00"), "10")
        self.assertEqual(format_quantity("7.4"), "7")
        self.assertEqual(format_quantity("7.5"), "8")

    def test_money_keeps_two_decimals(self):
        self.assertEqual(format_money("10"), "10,00")
        self.assertEqual(format_money("1234.5", "DA"), "1 234,50 DA")
        self.assertEqual(format_money("29950.00"), "29 950,00")
        self.assertEqual(format_money("100000.23"), "100 000,23")

    def test_number_parsing_accepts_decimal_and_thousand_commas(self):
        self.assertEqual(quantity_to_int("12,0"), 12)
        self.assertEqual(format_money("1 234,50"), "1 234,50")
        self.assertEqual(format_money("1,234.50"), "1 234,50")
        self.assertEqual(_to_decimal("29 950,00"), Decimal("29950.00"))
        self.assertEqual(_to_decimal("100 000,23"), Decimal("100000.23"))
        self.assertEqual(_to_decimal("Total TTC: 29 950,00 DA"), Decimal("29950.00"))


if __name__ == "__main__":
    unittest.main()
