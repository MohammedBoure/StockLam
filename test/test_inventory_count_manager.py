from decimal import Decimal
import tempfile
import unittest
from unittest.mock import patch

import mysql.connector

from database.inventory_count_manager import InventoryCountManager


class FakeCursor:
    def __init__(
        self,
        fetchone_rows=None,
        fetchall_rows=None,
        lastrowid=123,
        rowcount=1,
        execute_errors=None,
    ):
        self.fetchone_rows = list(fetchone_rows or [])
        self.fetchall_rows = list(fetchall_rows or [])
        self.execute_errors = list(execute_errors or [])
        self.executed = []
        self.closed = False
        self.lastrowid = lastrowid
        self.rowcount = rowcount

    def execute(self, query, params=None):
        if self.execute_errors:
            error = self.execute_errors.pop(0)
            if error:
                raise error
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
        if isinstance(connection, list):
            self.connections = list(connection)
            self.connection = self.connections[0] if self.connections else None
        else:
            self.connections = [connection]
            self.connection = connection

    def get_raw_connection(self):
        return self._next_connection()

    def get_db_connection(self):
        return self._next_connection()

    def _next_connection(self):
        if len(self.connections) > 1:
            self.connection = self.connections.pop(0)
            return self.connection
        return self.connections[0]


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

    def test_decimal_helpers_handle_invalid_values_and_round_quantities(self):
        self.assertEqual(InventoryCountManager._to_decimal(None), Decimal("0"))
        self.assertEqual(InventoryCountManager._to_decimal("bad", default="4"), Decimal("4"))
        self.assertEqual(InventoryCountManager._quantity_to_int(Decimal("2.5")), 3)
        self.assertEqual(InventoryCountManager._quantity_to_int(Decimal("2.4")), 2)

    def test_refresh_line_status_updates_existing_line(self):
        cursor = FakeCursor(
            [
                {
                    "Line_ID": 9,
                    "Program_Qty_Snapshot": Decimal("8"),
                    "Counted_Qty": Decimal("10"),
                }
            ]
        )
        manager = make_manager()

        line = manager._refresh_line_status(cursor, 9)

        self.assertEqual(line["Difference_Qty"], Decimal("2"))
        self.assertEqual(line["Line_Status"], "EXCESS")
        update_query, params = cursor.executed[-1]
        self.assertIn("UPDATE Inventory_Count_Lines", update_query)
        self.assertEqual(params, (Decimal("2"), "EXCESS", 9))

    def test_refresh_line_status_returns_none_when_line_missing(self):
        cursor = FakeCursor([None])
        manager = make_manager()

        self.assertIsNone(manager._refresh_line_status(cursor, 404))
        self.assertEqual(len(cursor.executed), 1)

    def test_create_session_rejects_invalid_scope_without_db(self):
        manager = make_manager()

        self.assertIsNone(manager.create_session("Bad scope", scope_type="WRONG"))

    def test_create_session_inserts_snapshot_and_marks_counting(self):
        insert_cursor = FakeCursor(lastrowid=88)
        update_cursor = FakeCursor()
        insert_connection = FakeConnection(insert_cursor)
        db = FakeDb([insert_connection, FakeConnection(update_cursor)])
        manager = make_manager(db)
        snapshots = []
        manager.build_snapshot = lambda session_id: snapshots.append(session_id) or True

        session_id = manager.create_session(
            "Session test",
            scope_type="location",
            scope_id=5,
            created_by=7,
            notes="note",
        )

        self.assertEqual(session_id, 88)
        self.assertEqual(snapshots, [88])
        self.assertTrue(insert_connection.committed)
        self.assertIn("INSERT INTO Inventory_Count_Sessions", insert_cursor.executed[0][0])
        self.assertEqual(insert_cursor.executed[0][1], ("Session test", "LOCATION", 5, 7, "note"))
        self.assertIn("UPDATE Inventory_Count_Sessions", update_cursor.executed[0][0])
        self.assertEqual(update_cursor.executed[0][1], (88,))

    def test_create_session_returns_none_when_snapshot_fails(self):
        cursor = FakeCursor(lastrowid=88)
        manager = make_manager(FakeDb(FakeConnection(cursor)))
        manager.build_snapshot = lambda session_id: False

        self.assertIsNone(manager.create_session("Session test"))

    def test_build_snapshot_returns_false_when_session_missing(self):
        cursor = FakeCursor([None])
        manager = make_manager(FakeDb(FakeConnection(cursor)))

        self.assertFalse(manager.build_snapshot(session_id=404))
        self.assertEqual(len(cursor.executed), 1)

    def test_build_snapshot_adds_scope_filters_and_params(self):
        cases = [
            ("LOCATION", 11, "b.Location_ID = %s"),
            ("FAMILY", 22, "p.Family_ID = %s"),
            ("PRODUCT", 33, "b.Product_ID = %s"),
        ]

        for scope_type, scope_id, expected_clause in cases:
            with self.subTest(scope_type=scope_type):
                cursor = FakeCursor(
                    [
                        {
                            "Session_ID": 99,
                            "Scope_Type": scope_type,
                            "Scope_ID": scope_id,
                        }
                    ]
                )
                manager = make_manager(FakeDb(FakeConnection(cursor)))

                self.assertTrue(manager.build_snapshot(session_id=99))

                insert_query, params = cursor.executed[-1]
                self.assertIn(expected_clause, insert_query)
                self.assertIn("b.Quantity_Current > 0", insert_query)
                self.assertEqual(params, (99, scope_id))

    def test_build_snapshot_returns_false_on_mysql_error(self):
        cursor = FakeCursor(
            [
                {
                    "Session_ID": 99,
                    "Scope_Type": "ALL",
                    "Scope_ID": None,
                }
            ],
            execute_errors=[None, mysql.connector.Error("delete failed")],
        )
        manager = make_manager(FakeDb(FakeConnection(cursor)))

        self.assertFalse(manager.build_snapshot(session_id=99))

    def test_scan_barcode_rejects_non_positive_qty_without_db(self):
        manager = make_manager()

        result = manager.scan_barcode(session_id=1, barcode="ABC-123", qty=0)

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "INVALID")
        self.assertEqual(result["message"], "Quantity must be positive.")

    def test_scan_barcode_rejects_empty_barcode_without_db(self):
        manager = make_manager()

        result = manager.scan_barcode(session_id=1, barcode="   ", qty=1)

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "INVALID")
        self.assertEqual(result["message"], "Barcode is empty.")

    def test_scan_barcode_allows_zero_when_replacing_counted_quantity(self):
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

        result = manager.scan_barcode(session_id=99, barcode="ABC-123", qty=0, replace_counted=True)

        self.assertTrue(result["success"])
        self.assertEqual(result["line"]["Counted_Qty"], Decimal("0"))
        self.assertEqual(result["line"]["Difference_Qty"], Decimal("-10"))
        self.assertEqual(result["line"]["Line_Status"], "SHORT")

    def test_scan_barcode_returns_not_found_for_missing_session(self):
        cursor = FakeCursor([None])
        manager = make_manager(FakeDb(FakeConnection(cursor)))

        result = manager.scan_barcode(session_id=99, barcode="ABC-123", qty=1)

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "NOT_FOUND")

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

    def test_get_session_line_by_barcode_returns_none_for_empty_barcode(self):
        manager = make_manager()

        self.assertIsNone(manager.get_session_line_by_barcode(session_id=99, barcode=" "))

    def test_set_counted_quantity_rejects_negative_quantity(self):
        manager = make_manager()

        self.assertFalse(manager.set_counted_quantity(line_id=1, counted_qty=-1))

    def test_set_counted_quantity_returns_false_when_line_missing(self):
        cursor = FakeCursor([None])
        manager = make_manager(FakeDb(FakeConnection(cursor)))

        self.assertFalse(manager.set_counted_quantity(line_id=404, counted_qty=2))

    def test_set_counted_quantity_updates_regular_line_status(self):
        cursor = FakeCursor(
            [
                {
                    "Line_ID": 10,
                    "Program_Qty_Snapshot": Decimal("10"),
                    "Counted_Qty": Decimal("0"),
                    "Line_Status": "NOT_COUNTED",
                }
            ]
        )
        manager = make_manager(FakeDb(FakeConnection(cursor)))

        result = manager.set_counted_quantity(line_id=10, counted_qty=12)

        self.assertTrue(result["success"])
        self.assertEqual(result["line"]["Counted_Qty"], Decimal("12"))
        self.assertEqual(result["line"]["Difference_Qty"], Decimal("2"))
        self.assertEqual(result["line"]["Line_Status"], "EXCESS")
        self.assertEqual(cursor.executed[-1][1], (Decimal("12"), Decimal("2"), "EXCESS", 10))

    def test_set_counted_quantity_keeps_unknown_status(self):
        cursor = FakeCursor(
            [
                {
                    "Line_ID": 10,
                    "Program_Qty_Snapshot": Decimal("0"),
                    "Counted_Qty": Decimal("0"),
                    "Line_Status": "UNKNOWN",
                }
            ]
        )
        manager = make_manager(FakeDb(FakeConnection(cursor)))

        result = manager.set_counted_quantity(line_id=10, counted_qty=3)

        self.assertTrue(result["success"])
        self.assertEqual(result["line"]["Difference_Qty"], Decimal("3"))
        self.assertEqual(result["line"]["Line_Status"], "UNKNOWN")

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

    def test_get_sessions_applies_status_and_limit(self):
        cursor = FakeCursor(fetchall_rows=[[{"Session_ID": 1, "Status": "Review"}]])
        manager = make_manager(FakeDb(FakeConnection(cursor)))

        sessions = manager.get_sessions(status="Review", limit="5")

        self.assertEqual(sessions, [{"Session_ID": 1, "Status": "Review"}])
        query, params = cursor.executed[0]
        self.assertIn("WHERE s.Status = %s", query)
        self.assertEqual(params, ("Review", 5))

    def test_get_sessions_sanitizes_invalid_limit(self):
        cursor = FakeCursor(fetchall_rows=[[]])
        manager = make_manager(FakeDb(FakeConnection(cursor)))

        manager.get_sessions(limit="not-a-number")

        self.assertEqual(cursor.executed[0][1], (100,))

    def test_get_session_lines_adds_status_and_search_filters(self):
        cursor = FakeCursor(fetchall_rows=[[{"Line_ID": 1}]])
        manager = make_manager(FakeDb(FakeConnection(cursor)))

        lines = manager.get_session_lines(session_id=99, status="SHORT", search="abc")

        self.assertEqual(lines, [{"Line_ID": 1}])
        query, params = cursor.executed[0]
        self.assertIn("l.Line_Status = %s", query)
        self.assertIn("p.Product_Name LIKE %s", query)
        self.assertEqual(params[0:2], (99, "SHORT"))
        self.assertEqual(params[2:], tuple(["%abc%"] * 9))

    def test_get_session_summary_counts_statuses_and_variance_value(self):
        cursor = FakeCursor(
            fetchone_rows=[{"Variance_Value": Decimal("42.75")}],
            fetchall_rows=[
                [
                    {"Line_Status": "OK", "Count_Value": 2},
                    {"Line_Status": "SHORT", "Count_Value": 1},
                    {"Line_Status": "IGNORED", "Count_Value": 3},
                ]
            ],
        )
        manager = make_manager(FakeDb(FakeConnection(cursor)))

        summary = manager.get_session_summary(session_id=99)

        self.assertEqual(summary["OK"], 2)
        self.assertEqual(summary["SHORT"], 1)
        self.assertEqual(summary["Total_Lines"], 6)
        self.assertEqual(summary["Estimated_Variance_Value"], Decimal("42.75"))

    def test_mark_review_uses_rowcount(self):
        success_cursor = FakeCursor(rowcount=1)
        fail_cursor = FakeCursor(rowcount=0)

        self.assertTrue(make_manager(FakeDb(FakeConnection(success_cursor))).mark_review(99))
        self.assertFalse(make_manager(FakeDb(FakeConnection(fail_cursor))).mark_review(99))

    def test_cancel_session_handles_not_found_applied_cancelled_and_success(self):
        cases = [
            (None, False, "Session not found."),
            ({"Session_ID": 1, "Status": "Applied"}, False, "Applied sessions cannot be cancelled."),
            ({"Session_ID": 1, "Status": "Cancelled"}, True, "Session is already cancelled."),
            ({"Session_ID": 1, "Status": "Counting"}, True, "Session cancelled."),
        ]

        for session, expected_success, expected_message in cases:
            with self.subTest(session=session):
                cursor = FakeCursor([session])
                manager = make_manager(FakeDb(FakeConnection(cursor)))

                result = manager.cancel_session(1, user_id=7)

                self.assertEqual(result["success"], expected_success)
                self.assertEqual(result["message"], expected_message)
                if session and session.get("Status") == "Counting":
                    self.assertIn("UPDATE Inventory_Count_Sessions", cursor.executed[-1][0])

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

    def test_apply_session_rejects_missing_cancelled_invalid_and_empty_sessions(self):
        cases = [
            ([None], "Session not found."),
            ([{"Session_ID": 99, "Status": "Cancelled"}], "Cancelled sessions cannot be applied."),
            ([{"Session_ID": 99, "Status": "Draft"}], "Only Counting or Review sessions can be applied."),
            ([{"Session_ID": 99, "Status": "Counting"}, {"Total_Lines": 0}], "Session has no count lines to apply."),
        ]

        for fetchone_rows, expected_message in cases:
            with self.subTest(expected_message=expected_message):
                cursor = FakeCursor(fetchone_rows)
                connection = FakeConnection(cursor)
                manager = make_manager(FakeDb(connection))

                result = manager.apply_session(session_id=99, user_id=7)

                self.assertFalse(result["success"])
                self.assertEqual(result["message"], expected_message)
                self.assertTrue(connection.rolled_back)
                self.assertFalse(connection.committed)

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

    def test_apply_session_rejects_unknown_scans_without_override(self):
        cursor = FakeCursor(
            [
                {"Session_ID": 99, "Status": "Review"},
                {"Total_Lines": 2},
                {"Unknown_Lines": 0},
                {"Unknown_Scans": 1},
            ]
        )
        connection = FakeConnection(cursor)
        manager = make_manager(FakeDb(connection), FakeStockMovementLog())

        result = manager.apply_session(session_id=99, user_id=7, allow_unknown=False)

        self.assertFalse(result["success"])
        self.assertIn("scans: 1", result["message"])
        self.assertTrue(connection.rolled_back)

    def test_apply_session_missing_batch_is_conflict(self):
        line = {
            "Line_ID": 10,
            "Batch_ID": 34,
            "Internal_Barcode": "ABC-123",
            "Program_Qty_Snapshot": Decimal("5"),
            "Counted_Qty": Decimal("3"),
            "Difference_Qty": Decimal("-2"),
        }
        cursor = FakeCursor(
            [
                {"Session_ID": 99, "Status": "Counting"},
                {"Total_Lines": 1},
                {"Unknown_Lines": 0},
                {"Unknown_Scans": 0},
                None,
            ],
            fetchall_rows=[[line]],
        )
        connection = FakeConnection(cursor)
        stock_log = FakeStockMovementLog()
        manager = make_manager(FakeDb(connection), stock_log)

        result = manager.apply_session(session_id=99, user_id=7, allow_unknown=True)

        self.assertFalse(result["success"])
        self.assertEqual(result["conflicts"][0]["reason"], "Batch not found.")
        self.assertEqual(stock_log.calls, [])
        self.assertTrue(connection.rolled_back)

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

    def test_apply_session_zero_difference_marks_applied_without_movement(self):
        cursor = FakeCursor(
            [
                {"Session_ID": 99, "Status": "Counting"},
                {"Total_Lines": 1},
                {"Unknown_Lines": 0},
                {"Unknown_Scans": 0},
            ],
            fetchall_rows=[[]],
        )
        connection = FakeConnection(cursor)
        stock_log = FakeStockMovementLog()
        manager = make_manager(FakeDb(connection), stock_log)

        result = manager.apply_session(session_id=99, user_id=7, allow_unknown=True)

        self.assertTrue(result["success"])
        self.assertEqual(result["applied_count"], 0)
        self.assertEqual(stock_log.calls, [])
        self.assertTrue(connection.committed)
        self.assertIn("UPDATE Inventory_Count_Sessions", cursor.executed[-1][0])

    def test_apply_session_sets_depleted_available_and_preserves_special_status(self):
        lines = [
            {
                "Line_ID": 10,
                "Batch_ID": 34,
                "Program_Qty_Snapshot": Decimal("5"),
                "Counted_Qty": Decimal("0"),
                "Difference_Qty": Decimal("-5"),
            },
            {
                "Line_ID": 11,
                "Batch_ID": 35,
                "Program_Qty_Snapshot": Decimal("0"),
                "Counted_Qty": Decimal("2"),
                "Difference_Qty": Decimal("2"),
            },
            {
                "Line_ID": 12,
                "Batch_ID": 36,
                "Program_Qty_Snapshot": Decimal("4"),
                "Counted_Qty": Decimal("6"),
                "Difference_Qty": Decimal("2"),
            },
        ]
        batches = [
            {
                "Batch_ID": 34,
                "Product_ID": 2,
                "Internal_Barcode": "A",
                "Quantity_Current": Decimal("5"),
                "Status": "Available",
                "Stock_Unit": "Unit",
            },
            {
                "Batch_ID": 35,
                "Product_ID": 3,
                "Internal_Barcode": "B",
                "Quantity_Current": Decimal("0"),
                "Status": "Depleted",
                "Stock_Unit": "Unit",
            },
            {
                "Batch_ID": 36,
                "Product_ID": 4,
                "Internal_Barcode": "C",
                "Quantity_Current": Decimal("4"),
                "Status": "Quarantined",
                "Stock_Unit": "Unit",
            },
        ]
        cursor = FakeCursor(
            [
                {"Session_ID": 99, "Status": "Counting"},
                {"Total_Lines": 3},
                {"Unknown_Lines": 0},
                {"Unknown_Scans": 0},
                *batches,
            ],
            fetchall_rows=[lines],
        )
        connection = FakeConnection(cursor)
        stock_log = FakeStockMovementLog()
        manager = make_manager(FakeDb(connection), stock_log)

        result = manager.apply_session(session_id=99, user_id=7, allow_unknown=True)

        self.assertTrue(result["success"])
        self.assertEqual(result["applied_count"], 3)
        update_params = [
            params for query, params in cursor.executed
            if "UPDATE Inventory_Batches" in query
        ]
        self.assertEqual(update_params[0], (Decimal("0"), "Depleted", 34))
        self.assertEqual(update_params[1], (Decimal("2"), "Available", 35))
        self.assertEqual(update_params[2], (Decimal("6"), "Quarantined", 36))

    def test_apply_session_rolls_back_when_movement_log_fails(self):
        line = {
            "Line_ID": 10,
            "Batch_ID": 34,
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
            "Stock_Unit": None,
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
        stock_log = FakeStockMovementLog(movement_id=None)
        manager = make_manager(FakeDb(connection), stock_log)

        result = manager.apply_session(session_id=99, user_id=7, allow_unknown=True)

        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "Failed to write stock movement log.")
        self.assertEqual(stock_log.calls[0]["unit_used"], "Unit")
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)

    def test_apply_session_rolls_back_on_exception(self):
        cursor = FakeCursor(
            execute_errors=[RuntimeError("boom")]
        )
        connection = FakeConnection(cursor)
        manager = make_manager(FakeDb(connection))

        result = manager.apply_session(session_id=99, user_id=7)

        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "boom")
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

    def test_export_session_to_excel_rejects_empty_path_and_missing_engine(self):
        manager = make_manager()

        self.assertFalse(manager.export_session_to_excel(99, "")["success"])

        manager._excel_writer_engine = lambda: None
        result = manager.export_session_to_excel(99, "file.xlsx")
        self.assertFalse(result["success"])
        self.assertIn("Excel export requires", result["message"])

    def test_export_session_to_excel_rejects_missing_session(self):
        cursor = FakeCursor([None])
        manager = make_manager(FakeDb(FakeConnection(cursor)))

        result = manager.export_session_to_excel(99, "file.xlsx")

        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "Inventory count session not found.")

    def test_export_session_to_excel_writes_summary_lines_and_scans(self):
        cursor = FakeCursor(
            [
                {
                    "Session_ID": 99,
                    "Session_Name": "Session export",
                    "Status": "Applied",
                    "Started_At": "2026-06-07",
                    "Applied_At": "2026-06-07",
                }
            ],
            fetchall_rows=[
                [
                    {
                        "Scanned_Barcode": "ABC-123",
                        "Qty": Decimal("2"),
                        "Scan_Status": "MATCHED",
                        "Scanned_At": "10:00",
                        "Scanned_By": 7,
                    }
                ]
            ],
        )
        manager = make_manager(FakeDb(FakeConnection(cursor)))
        manager.get_session_lines = lambda session_id: [
            {
                "Product_Name": "Glucose",
                "Internal_Barcode": "ABC-123",
                "Lot_Number": "LOT-A",
                "Expiry_Date": "2027-01-01",
                "Location_Name": "Stock",
                "Program_Qty_Snapshot": Decimal("10"),
                "Counted_Qty": Decimal("8"),
                "Difference_Qty": Decimal("-2"),
                "Line_Status": "SHORT",
                "Comment": "missing",
            }
        ]
        manager.get_session_summary = lambda session_id: {
            "OK": 1,
            "SHORT": 1,
            "EXCESS": 0,
            "NOT_COUNTED": 0,
            "UNKNOWN": 0,
            "Estimated_Variance_Value": Decimal("12.50"),
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = f"{temp_dir}\\inventaire.xlsx"
            result = manager.export_session_to_excel(99, output_path)

        self.assertTrue(result["success"])
        self.assertIn("Exported inventory count", result["message"])


if __name__ == "__main__":
    unittest.main()
