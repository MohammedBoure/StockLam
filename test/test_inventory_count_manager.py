from decimal import Decimal
import unittest

from database.inventory_count_manager import InventoryCountManager


class FakeCursor:
    def __init__(self, fetchone_rows=None):
        self.fetchone_rows = list(fetchone_rows or [])
        self.executed = []
        self.closed = False

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        if self.fetchone_rows:
            return self.fetchone_rows.pop(0)
        return None

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.started = False
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def start_transaction(self):
        self.started = True

    def cursor(self, dictionary=False):
        self.dictionary = dictionary
        return self.cursor_obj

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def is_connected(self):
        return not self.closed

    def close(self):
        self.closed = True


class FakeDb:
    def __init__(self, connection):
        self.connection = connection

    def get_raw_connection(self):
        return self.connection

    def get_db_connection(self):
        return self.connection


def make_manager(db=None):
    manager = InventoryCountManager.__new__(InventoryCountManager)
    manager.db = db
    manager.stock_movement_log = None
    return manager


class InventoryCountManagerHelperTests(unittest.TestCase):
    def test_line_status_ok_and_zero_difference(self):
        self.assertEqual(InventoryCountManager._line_status(10, 10), "OK")
        self.assertEqual(InventoryCountManager._difference(10, 10), Decimal("0"))

    def test_line_status_short_and_negative_difference(self):
        self.assertEqual(InventoryCountManager._line_status(10, 7), "SHORT")
        self.assertEqual(InventoryCountManager._difference(10, 7), Decimal("-3"))

    def test_line_status_excess_and_positive_difference(self):
        self.assertEqual(InventoryCountManager._line_status(10, 12), "EXCESS")
        self.assertEqual(InventoryCountManager._difference(10, 12), Decimal("2"))

    def test_normalize_barcode_trims_spaces(self):
        self.assertEqual(InventoryCountManager._normalize_barcode("  ABC-123  "), "ABC-123")

    def test_can_apply_status_rejects_applied(self):
        self.assertFalse(InventoryCountManager._can_apply_status("Applied"))
        self.assertFalse(InventoryCountManager._can_apply_status("Cancelled"))
        self.assertTrue(InventoryCountManager._can_apply_status("Counting"))
        self.assertTrue(InventoryCountManager._can_apply_status("Review"))

    def test_scan_barcode_rejects_non_positive_qty_without_db(self):
        manager = make_manager()

        result = manager.scan_barcode(session_id=1, barcode="ABC-123", qty=0)

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "INVALID")
        self.assertEqual(result["message"], "Quantity must be positive.")

    def test_scan_barcode_replace_counted_uses_physical_quantity(self):
        cursor = FakeCursor(
            [
                {"Session_ID": 99, "Status": "Counting"},
                {
                    "Line_ID": 12,
                    "Session_ID": 99,
                    "Batch_ID": 34,
                    "Internal_Barcode": "ABC-123",
                    "Program_Qty_Snapshot": Decimal("10"),
                    "Counted_Qty": Decimal("4"),
                },
            ]
        )
        manager = make_manager(FakeDb(FakeConnection(cursor)))

        result = manager.scan_barcode(
            session_id=99,
            barcode="ABC-123",
            qty=7,
            user_id=5,
            replace_counted=True,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "MATCHED")
        self.assertEqual(result["line"]["Counted_Qty"], Decimal("7"))
        self.assertEqual(result["line"]["Difference_Qty"], Decimal("-3"))
        self.assertEqual(result["line"]["Line_Status"], "SHORT")
        match_query = cursor.executed[1][0]
        self.assertIn("p.Barcode = %s", match_query)
        self.assertIn("p.Manuf_Cat_No = %s", match_query)
        self.assertIn("ORDER BY", match_query)

    def test_get_session_line_by_barcode_uses_exact_priority_lookup(self):
        cursor = FakeCursor(
            [
                {
                    "Line_ID": 12,
                    "Session_ID": 99,
                    "Internal_Barcode": "ABC-123",
                    "Product_Name": "Produit test",
                },
            ]
        )
        manager = make_manager(FakeDb(FakeConnection(cursor)))

        result = manager.get_session_line_by_barcode(session_id=99, barcode=" ABC-123 ")

        self.assertEqual(result["Line_ID"], 12)
        query, params = cursor.executed[0]
        self.assertIn("l.Internal_Barcode = %s", query)
        self.assertIn("p.Barcode = %s", query)
        self.assertIn("p.Manuf_Cat_No = %s", query)
        self.assertEqual(params, (99, "ABC-123", "ABC-123", "ABC-123", "ABC-123", "ABC-123", "ABC-123"))

    def test_build_snapshot_uses_signed_difference_expression(self):
        cursor = FakeCursor(
            [
                {
                    "Session_ID": 99,
                    "Scope_Type": "ALL",
                    "Scope_ID": None,
                }
            ]
        )
        manager = make_manager(FakeDb(FakeConnection(cursor)))

        self.assertTrue(manager.build_snapshot(session_id=99))

        insert_query = cursor.executed[-1][0]
        self.assertIn("-CAST(b.Quantity_Current AS DECIMAL(15, 2))", insert_query)
        self.assertNotIn("0 - b.Quantity_Current", insert_query)

    def test_apply_session_rejects_applied_status_without_modification(self):
        cursor = FakeCursor(
            [
                {
                    "Session_ID": 99,
                    "Status": "Applied",
                }
            ]
        )
        connection = FakeConnection(cursor)
        manager = make_manager(FakeDb(connection))

        result = manager.apply_session(session_id=99, user_id=7)

        self.assertFalse(result["success"])
        self.assertEqual(result["applied_count"], 0)
        self.assertEqual(result["conflicts"], [])
        self.assertEqual(result["message"], "Session is already applied.")
        self.assertTrue(connection.started)
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
