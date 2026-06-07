from decimal import Decimal
import unittest

from database.inventory_count_manager import InventoryCountManager


class FakeCursor:
    def __init__(self, fetchone_rows=None, fetchall_rows=None, lastrowid=123, rowcount=1):
        self.fetchone_rows = list(fetchone_rows or [])
        self.fetchall_rows = list(fetchall_rows or [])
        self.executed = []
        self.closed = False
        self.lastrowid = lastrowid
        self.rowcount = rowcount

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        if self.fetchone_rows:
            return self.fetchone_rows.pop(0)
        return None

    def fetchall(self):
        if self.fetchall_rows:
            return self.fetchall_rows.pop(0)
        return []

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


class FakeStockMovementLog:
    def __init__(self, movement_id=501):
        self.movement_id = movement_id
        self.calls = []

    def create_movement_log(self, **kwargs):
        self.calls.append(kwargs)
        return self.movement_id


def make_manager(db=None, stock_movement_log=None):
    manager = InventoryCountManager.__new__(InventoryCountManager)
    manager.db = db
    manager.stock_movement_log = stock_movement_log
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

    def test_scan_barcode_increment_mode_adds_to_existing_count(self):
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

        result = manager.scan_barcode(session_id=99, barcode="ABC-123", qty=2, user_id=5)

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "MATCHED")
        self.assertEqual(result["line"]["Counted_Qty"], Decimal("6"))
        self.assertEqual(result["line"]["Difference_Qty"], Decimal("-4"))
        self.assertEqual(result["line"]["Line_Status"], "SHORT")

    def test_scan_barcode_unknown_creates_unknown_line_and_scan(self):
        cursor = FakeCursor(
            [
                {"Session_ID": 99, "Status": "Counting"},
                None,
            ],
            lastrowid=77,
        )
        manager = make_manager(FakeDb(FakeConnection(cursor)))

        result = manager.scan_barcode(session_id=99, barcode=" UNKNOWN-1 ", qty=3, user_id=5)

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["line"]["Line_ID"], 77)
        self.assertEqual(result["line"]["Counted_Qty"], Decimal("3"))
        self.assertEqual(result["line"]["Difference_Qty"], Decimal("3"))
        self.assertEqual(result["line"]["Line_Status"], "UNKNOWN")
        executed_sql = "\n".join(query for query, _ in cursor.executed)
        self.assertIn("INSERT INTO Inventory_Count_Lines", executed_sql)
        self.assertIn("INSERT INTO Inventory_Count_Scans", executed_sql)
        self.assertIn("'UNKNOWN'", executed_sql)

    def test_scan_barcode_rejects_closed_session(self):
        cursor = FakeCursor([{"Session_ID": 99, "Status": "Applied"}])
        manager = make_manager(FakeDb(FakeConnection(cursor)))

        result = manager.scan_barcode(session_id=99, barcode="ABC-123", qty=1)

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "CLOSED")
        executed_sql = "\n".join(query for query, _ in cursor.executed)
        self.assertNotIn("UPDATE Inventory_Count_Lines", executed_sql)
        self.assertNotIn("INSERT INTO Inventory_Count_Scans", executed_sql)

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

    def test_apply_session_rejects_unknown_lines_without_override(self):
        cursor = FakeCursor(
            [
                {"Session_ID": 99, "Status": "Counting"},
                {"Total_Lines": 2},
                {"Unknown_Lines": 1},
                {"Unknown_Scans": 0},
            ]
        )
        connection = FakeConnection(cursor)
        stock_log = FakeStockMovementLog()
        manager = make_manager(FakeDb(connection), stock_log)

        result = manager.apply_session(session_id=99, user_id=7, allow_unknown=False)

        self.assertFalse(result["success"])
        self.assertIn("Unknown scanned barcodes", result["message"])
        self.assertEqual(stock_log.calls, [])
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)

    def test_apply_session_detects_snapshot_conflict_and_rolls_back(self):
        line = {
            "Line_ID": 10,
            "Batch_ID": 34,
            "Internal_Barcode": "ABC-123",
            "Program_Qty_Snapshot": Decimal("5"),
            "Counted_Qty": Decimal("3"),
            "Difference_Qty": Decimal("-2"),
        }
        batch = {
            "Batch_ID": 34,
            "Product_ID": 2,
            "Internal_Barcode": "ABC-123",
            "Quantity_Current": Decimal("6"),
            "Status": "Available",
            "Stock_Unit": "Unit",
        }
        cursor = FakeCursor(
            [
                {"Session_ID": 99, "Status": "Counting"},
                {"Total_Lines": 1},
                {"Unknown_Lines": 0},
                {"Unknown_Scans": 0},
                batch,
            ],
            fetchall_rows=[[line]],
        )
        connection = FakeConnection(cursor)
        stock_log = FakeStockMovementLog()
        manager = make_manager(FakeDb(connection), stock_log)

        result = manager.apply_session(session_id=99, user_id=7, allow_unknown=True)

        self.assertFalse(result["success"])
        self.assertEqual(len(result["conflicts"]), 1)
        self.assertEqual(result["conflicts"][0]["Batch_ID"], 34)
        self.assertEqual(result["conflicts"][0]["snapshot_qty"], Decimal("5"))
        self.assertEqual(result["conflicts"][0]["current_qty"], Decimal("6"))
        self.assertEqual(stock_log.calls, [])
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)

    def test_apply_session_success_updates_batch_logs_movement_and_commits(self):
        line = {
            "Line_ID": 10,
            "Batch_ID": 34,
            "Internal_Barcode": "ABC-123",
            "Program_Qty_Snapshot": Decimal("5"),
            "Counted_Qty": Decimal("3"),
            "Difference_Qty": Decimal("-2"),
        }
        batch = {
            "Batch_ID": 34,
            "Product_ID": 2,
            "Internal_Barcode": "ABC-123",
            "Quantity_Current": Decimal("5"),
            "Status": "Available",
            "Stock_Unit": "Box",
        }
        cursor = FakeCursor(
            [
                {"Session_ID": 99, "Status": "Counting"},
                {"Total_Lines": 1},
                {"Unknown_Lines": 0},
                {"Unknown_Scans": 0},
                batch,
            ],
            fetchall_rows=[[line]],
        )
        connection = FakeConnection(cursor)
        stock_log = FakeStockMovementLog()
        manager = make_manager(FakeDb(connection), stock_log)

        result = manager.apply_session(session_id=99, user_id=7, allow_unknown=True)

        self.assertTrue(result["success"])
        self.assertEqual(result["applied_count"], 1)
        self.assertEqual(result["conflicts"], [])
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertEqual(len(stock_log.calls), 1)
        movement = stock_log.calls[0]
        self.assertEqual(movement["product_id"], 2)
        self.assertEqual(movement["movement_type"], "Adjustment")
        self.assertEqual(movement["qty_change"], Decimal("-2"))
        self.assertEqual(movement["unit_used"], "Box")
        self.assertEqual(movement["batch_id"], 34)
        self.assertIs(movement["external_cursor"], cursor)
        executed_sql = "\n".join(query for query, _ in cursor.executed)
        self.assertIn("UPDATE Inventory_Batches", executed_sql)
        self.assertIn("UPDATE Inventory_Count_Sessions", executed_sql)


if __name__ == "__main__":
    unittest.main()
