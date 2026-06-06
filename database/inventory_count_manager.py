import importlib.util
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, List, Optional

import mysql.connector
import pandas as pd

from .base.schema_initializer import INDEX_QUERIES, SCHEMA_QUERIES
from .stock_movement_log_manager import StockMovementLogManager
from .system_logger import log_methods


@log_methods()
class InventoryCountManager:
    """Manage physical inventory count sessions, scans, review, and application."""

    _schema_checked = False

    VALID_SCOPE_TYPES = {"ALL", "LOCATION", "FAMILY", "PRODUCT"}
    OPEN_STATUSES = {"Counting", "Review"}
    FINAL_STATUSES = {"Applied", "Cancelled"}

    def __init__(self, db_instance):
        self.db = db_instance
        self.stock_movement_log = StockMovementLogManager(db_instance)
        self._ensure_schema()

    @staticmethod
    def _normalize_barcode(barcode) -> str:
        return str(barcode or "").strip()

    @staticmethod
    def _to_decimal(value, default="0") -> Decimal:
        if value is None:
            value = default
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return Decimal(default)

    @staticmethod
    def _line_status(snapshot_qty, counted_qty) -> str:
        difference = InventoryCountManager._to_decimal(counted_qty) - InventoryCountManager._to_decimal(snapshot_qty)
        if difference == 0:
            return "OK"
        if difference < 0:
            return "SHORT"
        return "EXCESS"

    @staticmethod
    def _difference(snapshot_qty, counted_qty) -> Decimal:
        return InventoryCountManager._to_decimal(counted_qty) - InventoryCountManager._to_decimal(snapshot_qty)

    @staticmethod
    def _quantity_to_int(value) -> int:
        return int(InventoryCountManager._to_decimal(value).to_integral_value(rounding=ROUND_HALF_UP))

    @staticmethod
    def _can_apply_status(status) -> bool:
        return status in InventoryCountManager.OPEN_STATUSES

    @staticmethod
    def _excel_writer_engine() -> Optional[str]:
        if importlib.util.find_spec("xlsxwriter"):
            return "xlsxwriter"
        if importlib.util.find_spec("openpyxl"):
            return "openpyxl"
        return None

    def _ensure_schema(self):
        if InventoryCountManager._schema_checked:
            return

        schema_queries = [query for query in SCHEMA_QUERIES if "Inventory_Count_" in query]
        index_queries = [query for query in INDEX_QUERIES if "Inventory_Count_" in query]

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                for query in schema_queries:
                    try:
                        cursor.execute(query)
                        while cursor.nextset():
                            pass
                    except mysql.connector.Error as err:
                        if err.errno not in (1060, 1061, 1826):
                            raise

                for query in index_queries:
                    try:
                        cursor.execute(query)
                        while cursor.nextset():
                            pass
                    except mysql.connector.Error as err:
                        if err.errno != 1061:
                            raise

            InventoryCountManager._schema_checked = True
        except mysql.connector.Error as err:
            logging.error(f"Error ensuring inventory count schema: {err}", exc_info=True)

    def _fetch_session(self, cursor, session_id) -> Optional[Dict]:
        cursor.execute(
            """
            SELECT *
            FROM Inventory_Count_Sessions
            WHERE Session_ID = %s
            """,
            (session_id,)
        )
        return cursor.fetchone()

    def _fetch_count_line_by_barcode(self, cursor, session_id, barcode) -> Optional[Dict]:
        cursor.execute(
            """
            SELECT
                l.*,
                p.Product_Name,
                p.Barcode AS Product_Barcode,
                p.Manuf_Cat_No,
                p.Stock_Unit,
                p.Ordering_Unit,
                p.Usage_Unit,
                p.Usage_Qty_Per_Stock_Unit,
                p.Minimum_Stock_Level,
                p.Storage_Temp_Req,
                pf.Family_Name,
                m.Manuf_Name,
                a.Automate_Name,
                b.Lot_Number,
                b.Expiry_Date,
                b.Quantity_Current,
                b.Quantity_Initial,
                b.Status AS Batch_Status,
                b.Reception_Note,
                b.Unit_Price_Received,
                loc.Location_Name
            FROM Inventory_Count_Lines l
            LEFT JOIN Inventory_Batches b ON l.Batch_ID = b.Batch_ID
            LEFT JOIN Products_Master p ON COALESCE(l.Product_ID, b.Product_ID) = p.Product_ID
            LEFT JOIN Product_Families pf ON p.Family_ID = pf.Family_ID
            LEFT JOIN Manufacturers m ON p.Manuf_ID = m.Manuf_ID
            LEFT JOIN Automates a ON p.Preferred_Automate_ID = a.Automate_ID
            LEFT JOIN Locations loc ON b.Location_ID = loc.Location_ID
            WHERE l.Session_ID = %s
              AND l.Batch_ID IS NOT NULL
              AND (
                    l.Internal_Barcode = %s OR
                    p.Barcode = %s OR
                    p.Manuf_Cat_No = %s
              )
            ORDER BY
                CASE
                    WHEN l.Internal_Barcode = %s THEN 0
                    WHEN p.Barcode = %s THEN 1
                    WHEN p.Manuf_Cat_No = %s THEN 2
                    ELSE 3
                END,
                b.Expiry_Date ASC,
                b.Batch_ID ASC
            LIMIT 1
            """,
            (session_id, barcode, barcode, barcode, barcode, barcode, barcode)
        )
        return cursor.fetchone()

    def _refresh_line_status(self, cursor, line_id) -> Optional[Dict]:
        cursor.execute(
            """
            SELECT Line_ID, Program_Qty_Snapshot, Counted_Qty
            FROM Inventory_Count_Lines
            WHERE Line_ID = %s
            """,
            (line_id,)
        )
        line = cursor.fetchone()
        if not line:
            return None

        difference = self._difference(line["Program_Qty_Snapshot"], line["Counted_Qty"])
        status = self._line_status(line["Program_Qty_Snapshot"], line["Counted_Qty"])
        cursor.execute(
            """
            UPDATE Inventory_Count_Lines
            SET Difference_Qty = %s,
                Line_Status = %s
            WHERE Line_ID = %s
            """,
            (difference, status, line_id)
        )
        line["Difference_Qty"] = difference
        line["Line_Status"] = status
        return line

    def create_session(self, session_name, scope_type="ALL", scope_id=None, created_by=None, notes=None):
        scope_type = str(scope_type or "ALL").upper()
        if scope_type not in self.VALID_SCOPE_TYPES:
            logging.error(f"Invalid inventory count scope: {scope_type}")
            return None

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO Inventory_Count_Sessions
                    (Session_Name, Scope_Type, Scope_ID, Status, Created_By, Notes)
                    VALUES (%s, %s, %s, 'Draft', %s, %s)
                    """,
                    (session_name, scope_type, scope_id, created_by, notes)
                )
                session_id = cursor.lastrowid
                conn.commit()

            if not self.build_snapshot(session_id):
                return None

            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE Inventory_Count_Sessions
                    SET Status = 'Counting'
                    WHERE Session_ID = %s
                    """,
                    (session_id,)
                )
            return session_id

        except mysql.connector.Error as err:
            logging.error(f"Error creating inventory count session: {err}", exc_info=True)
            return None

    def build_snapshot(self, session_id) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                session = self._fetch_session(cursor, session_id)
                if not session:
                    return False

                where_clauses = ["b.Quantity_Current > 0"]
                params = []
                scope_type = session.get("Scope_Type")
                scope_id = session.get("Scope_ID")

                if scope_type == "LOCATION":
                    where_clauses.append("b.Location_ID = %s")
                    params.append(scope_id)
                elif scope_type == "FAMILY":
                    where_clauses.append("p.Family_ID = %s")
                    params.append(scope_id)
                elif scope_type == "PRODUCT":
                    where_clauses.append("b.Product_ID = %s")
                    params.append(scope_id)

                cursor.execute(
                    "DELETE FROM Inventory_Count_Lines WHERE Session_ID = %s",
                    (session_id,)
                )

                query = f"""
                    INSERT INTO Inventory_Count_Lines
                    (Session_ID, Batch_ID, Product_ID, Internal_Barcode,
                     Program_Qty_Snapshot, Counted_Qty, Difference_Qty, Line_Status)
                    SELECT
                        %s,
                        b.Batch_ID,
                        b.Product_ID,
                        b.Internal_Barcode,
                        b.Quantity_Current,
                        0,
                        -CAST(b.Quantity_Current AS DECIMAL(15, 2)),
                        'NOT_COUNTED'
                    FROM Inventory_Batches b
                    JOIN Products_Master p ON b.Product_ID = p.Product_ID
                    WHERE {" AND ".join(where_clauses)}
                """
                cursor.execute(query, tuple([session_id] + params))
                return True

        except mysql.connector.Error as err:
            logging.error(f"Error building inventory count snapshot: {err}", exc_info=True)
            return False

    def scan_barcode(self, session_id, barcode, qty=1, user_id=None, replace_counted=False) -> Dict:
        barcode = self._normalize_barcode(barcode)
        qty_decimal = self._to_decimal(qty)
        if not barcode:
            return {"success": False, "status": "INVALID", "message": "Barcode is empty.", "line": None}
        if qty_decimal < 0 or (qty_decimal == 0 and not replace_counted):
            return {"success": False, "status": "INVALID", "message": "Quantity must be positive.", "line": None}

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                session = self._fetch_session(cursor, session_id)
                if not session:
                    return {"success": False, "status": "NOT_FOUND", "message": "Session not found.", "line": None}
                if session.get("Status") not in self.OPEN_STATUSES:
                    return {
                        "success": False,
                        "status": "CLOSED",
                        "message": "Session is not open for counting.",
                        "line": None,
                    }

                line = self._fetch_count_line_by_barcode(cursor, session_id, barcode)

                if line:
                    if replace_counted:
                        counted_qty = qty_decimal
                    else:
                        counted_qty = self._to_decimal(line["Counted_Qty"]) + qty_decimal
                    difference = self._difference(line["Program_Qty_Snapshot"], counted_qty)
                    status = self._line_status(line["Program_Qty_Snapshot"], counted_qty)
                    cursor.execute(
                        """
                        UPDATE Inventory_Count_Lines
                        SET Counted_Qty = %s,
                            Difference_Qty = %s,
                            Line_Status = %s,
                            Last_Scanned_At = NOW()
                        WHERE Line_ID = %s
                        """,
                        (counted_qty, difference, status, line["Line_ID"])
                    )
                    cursor.execute(
                        """
                        INSERT INTO Inventory_Count_Scans
                        (Session_ID, Line_ID, Scanned_Barcode, Qty, Scan_Status, Scanned_By)
                        VALUES (%s, %s, %s, %s, 'MATCHED', %s)
                        """,
                        (session_id, line["Line_ID"], barcode, qty_decimal, user_id)
                    )
                    line.update(
                        {
                            "Counted_Qty": counted_qty,
                            "Difference_Qty": difference,
                            "Line_Status": status,
                        }
                    )
                    return {
                        "success": True,
                        "status": "MATCHED",
                        "message": "Barcode matched.",
                        "line": line,
                    }

                cursor.execute(
                    """
                    INSERT INTO Inventory_Count_Lines
                    (Session_ID, Batch_ID, Product_ID, Internal_Barcode,
                     Program_Qty_Snapshot, Counted_Qty, Difference_Qty,
                     Line_Status, Last_Scanned_At)
                    VALUES (%s, NULL, NULL, %s, 0, %s, %s, 'UNKNOWN', NOW())
                    """,
                    (session_id, barcode, qty_decimal, qty_decimal)
                )
                line_id = cursor.lastrowid
                cursor.execute(
                    """
                    INSERT INTO Inventory_Count_Scans
                    (Session_ID, Line_ID, Scanned_Barcode, Qty, Scan_Status, Scanned_By)
                    VALUES (%s, %s, %s, %s, 'UNKNOWN', %s)
                    """,
                    (session_id, line_id, barcode, qty_decimal, user_id)
                )
                return {
                    "success": True,
                    "status": "UNKNOWN",
                    "message": "Barcode was not found in the session snapshot.",
                    "line": {
                        "Line_ID": line_id,
                        "Session_ID": session_id,
                        "Internal_Barcode": barcode,
                        "Program_Qty_Snapshot": Decimal("0"),
                        "Counted_Qty": qty_decimal,
                        "Difference_Qty": qty_decimal,
                        "Line_Status": "UNKNOWN",
                    },
                }

        except mysql.connector.Error as err:
            logging.error(f"Error scanning inventory barcode: {err}", exc_info=True)
            return {"success": False, "status": "ERROR", "message": str(err), "line": None}

    def get_session_line_by_barcode(self, session_id, barcode) -> Optional[Dict]:
        barcode = self._normalize_barcode(barcode)
        if not barcode:
            return None

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                return self._fetch_count_line_by_barcode(cursor, session_id, barcode)
        except mysql.connector.Error as err:
            logging.error(f"Error fetching inventory count line by barcode: {err}", exc_info=True)
            return None

    def set_counted_quantity(self, line_id, counted_qty) -> Dict | bool:
        counted_qty = self._to_decimal(counted_qty)
        if counted_qty < 0:
            return False

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT *
                    FROM Inventory_Count_Lines
                    WHERE Line_ID = %s
                    """,
                    (line_id,)
                )
                line = cursor.fetchone()
                if not line:
                    return False

                if line.get("Line_Status") == "UNKNOWN":
                    difference = counted_qty
                    status = "UNKNOWN"
                else:
                    difference = self._difference(line["Program_Qty_Snapshot"], counted_qty)
                    status = self._line_status(line["Program_Qty_Snapshot"], counted_qty)

                cursor.execute(
                    """
                    UPDATE Inventory_Count_Lines
                    SET Counted_Qty = %s,
                        Difference_Qty = %s,
                        Line_Status = %s
                    WHERE Line_ID = %s
                    """,
                    (counted_qty, difference, status, line_id)
                )
                line.update({"Counted_Qty": counted_qty, "Difference_Qty": difference, "Line_Status": status})
                return {"success": True, "message": "Counted quantity updated.", "line": line}

        except mysql.connector.Error as err:
            logging.error(f"Error updating counted quantity: {err}", exc_info=True)
            return False

    def get_sessions(self, status=None, limit=100) -> List[Dict]:
        try:
            limit = max(1, min(int(limit or 100), 1000))
        except (TypeError, ValueError):
            limit = 100

        params = []
        where = ""
        if status:
            where = "WHERE s.Status = %s"
            params.append(status)
        params.append(limit)

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    f"""
                    SELECT
                        s.*,
                        COUNT(l.Line_ID) AS Total_Lines,
                        SUM(CASE WHEN l.Line_Status = 'OK' THEN 1 ELSE 0 END) AS OK_Count,
                        SUM(CASE WHEN l.Line_Status = 'SHORT' THEN 1 ELSE 0 END) AS Short_Count,
                        SUM(CASE WHEN l.Line_Status = 'EXCESS' THEN 1 ELSE 0 END) AS Excess_Count,
                        SUM(CASE WHEN l.Line_Status = 'NOT_COUNTED' THEN 1 ELSE 0 END) AS Not_Counted_Count,
                        SUM(CASE WHEN l.Line_Status = 'UNKNOWN' THEN 1 ELSE 0 END) AS Unknown_Count
                    FROM Inventory_Count_Sessions s
                    LEFT JOIN Inventory_Count_Lines l ON s.Session_ID = l.Session_ID
                    {where}
                    GROUP BY s.Session_ID
                    ORDER BY s.Started_At DESC
                    LIMIT %s
                    """,
                    tuple(params)
                )
                return cursor.fetchall()
        except mysql.connector.Error as err:
            logging.error(f"Error fetching inventory count sessions: {err}", exc_info=True)
            return []

    def get_session_lines(self, session_id, status=None, search=None) -> List[Dict]:
        clauses = ["l.Session_ID = %s"]
        params = [session_id]

        if status:
            clauses.append("l.Line_Status = %s")
            params.append(status)

        if search:
            like = f"%{search}%"
            clauses.append(
                """
                (
                    p.Product_Name LIKE %s OR
                    l.Internal_Barcode LIKE %s OR
                    p.Barcode LIKE %s OR
                    p.Manuf_Cat_No LIKE %s OR
                    b.Lot_Number LIKE %s OR
                    loc.Location_Name LIKE %s OR
                    pf.Family_Name LIKE %s OR
                    m.Manuf_Name LIKE %s OR
                    a.Automate_Name LIKE %s
                )
                """
            )
            params.extend([like, like, like, like, like, like, like, like, like])

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    f"""
                    SELECT
                        l.*,
                        p.Product_Name,
                        p.Barcode AS Product_Barcode,
                        p.Manuf_Cat_No,
                        p.Stock_Unit,
                        p.Ordering_Unit,
                        p.Usage_Unit,
                        p.Usage_Qty_Per_Stock_Unit,
                        p.Minimum_Stock_Level,
                        p.Storage_Temp_Req,
                        pf.Family_Name,
                        m.Manuf_Name,
                        a.Automate_Name,
                        b.Lot_Number,
                        b.Expiry_Date,
                        b.Quantity_Current,
                        b.Quantity_Initial,
                        b.Status AS Batch_Status,
                        b.Reception_Note,
                        b.Unit_Price_Received,
                        loc.Location_Name
                    FROM Inventory_Count_Lines l
                    LEFT JOIN Inventory_Batches b ON l.Batch_ID = b.Batch_ID
                    LEFT JOIN Products_Master p ON COALESCE(l.Product_ID, b.Product_ID) = p.Product_ID
                    LEFT JOIN Product_Families pf ON p.Family_ID = pf.Family_ID
                    LEFT JOIN Manufacturers m ON p.Manuf_ID = m.Manuf_ID
                    LEFT JOIN Automates a ON p.Preferred_Automate_ID = a.Automate_ID
                    LEFT JOIN Locations loc ON b.Location_ID = loc.Location_ID
                    WHERE {" AND ".join(clauses)}
                    ORDER BY
                        CASE l.Line_Status
                            WHEN 'UNKNOWN' THEN 0
                            WHEN 'SHORT' THEN 1
                            WHEN 'EXCESS' THEN 2
                            WHEN 'NOT_COUNTED' THEN 3
                            ELSE 4
                        END,
                        p.Product_Name ASC,
                        b.Expiry_Date ASC
                    """,
                    tuple(params)
                )
                return cursor.fetchall()
        except mysql.connector.Error as err:
            logging.error(f"Error fetching inventory count lines: {err}", exc_info=True)
            return []

    def get_session_summary(self, session_id) -> Dict:
        summary = {
            "OK": 0,
            "SHORT": 0,
            "EXCESS": 0,
            "NOT_COUNTED": 0,
            "UNKNOWN": 0,
            "Total_Lines": 0,
            "Estimated_Variance_Value": Decimal("0"),
        }

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT Line_Status, COUNT(*) AS Count_Value
                    FROM Inventory_Count_Lines
                    WHERE Session_ID = %s
                    GROUP BY Line_Status
                    """,
                    (session_id,)
                )
                for row in cursor.fetchall():
                    status = row.get("Line_Status")
                    count_value = row.get("Count_Value") or 0
                    if status in summary:
                        summary[status] = count_value
                    summary["Total_Lines"] += count_value

                cursor.execute(
                    """
                    SELECT
                        COALESCE(SUM(ABS(l.Difference_Qty) * b.Unit_Price_Received), 0) AS Variance_Value
                    FROM Inventory_Count_Lines l
                    JOIN Inventory_Batches b ON l.Batch_ID = b.Batch_ID
                    WHERE l.Session_ID = %s
                    """,
                    (session_id,)
                )
                row = cursor.fetchone()
                summary["Estimated_Variance_Value"] = self._to_decimal(row.get("Variance_Value") if row else 0)
                return summary
        except mysql.connector.Error as err:
            logging.error(f"Error building inventory count summary: {err}", exc_info=True)
            return summary

    def mark_review(self, session_id) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE Inventory_Count_Sessions
                    SET Status = 'Review',
                        Completed_At = COALESCE(Completed_At, NOW())
                    WHERE Session_ID = %s
                      AND Status = 'Counting'
                    """,
                    (session_id,)
                )
                return cursor.rowcount > 0
        except mysql.connector.Error as err:
            logging.error(f"Error marking inventory count for review: {err}", exc_info=True)
            return False

    def cancel_session(self, session_id, user_id=None) -> Dict:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                session = self._fetch_session(cursor, session_id)
                if not session:
                    return {"success": False, "message": "Session not found."}
                if session.get("Status") == "Applied":
                    return {"success": False, "message": "Applied sessions cannot be cancelled."}
                if session.get("Status") == "Cancelled":
                    return {"success": True, "message": "Session is already cancelled."}

                cursor.execute(
                    """
                    UPDATE Inventory_Count_Sessions
                    SET Status = 'Cancelled',
                        Completed_At = COALESCE(Completed_At, NOW())
                    WHERE Session_ID = %s
                    """,
                    (session_id,)
                )
                return {"success": True, "message": "Session cancelled."}
        except mysql.connector.Error as err:
            logging.error(f"Error cancelling inventory count session: {err}", exc_info=True)
            return {"success": False, "message": str(err)}

    def apply_session(self, session_id, user_id=None, allow_unknown=False) -> Dict:
        conn = None
        cursor = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT *
                FROM Inventory_Count_Sessions
                WHERE Session_ID = %s
                FOR UPDATE
                """,
                (session_id,)
            )
            session = cursor.fetchone()
            if not session:
                conn.rollback()
                return {"success": False, "applied_count": 0, "conflicts": [], "message": "Session not found."}

            session_status = session.get("Status")
            if session_status == "Applied":
                conn.rollback()
                return {
                    "success": False,
                    "applied_count": 0,
                    "conflicts": [],
                    "message": "Session is already applied.",
                }
            if session_status == "Cancelled":
                conn.rollback()
                return {
                    "success": False,
                    "applied_count": 0,
                    "conflicts": [],
                    "message": "Cancelled sessions cannot be applied.",
                }
            if not self._can_apply_status(session_status):
                conn.rollback()
                return {
                    "success": False,
                    "applied_count": 0,
                    "conflicts": [],
                    "message": "Only Counting or Review sessions can be applied.",
                }

            cursor.execute(
                """
                SELECT COUNT(*) AS Total_Lines
                FROM Inventory_Count_Lines
                WHERE Session_ID = %s
                """,
                (session_id,)
            )
            total_lines = (cursor.fetchone() or {}).get("Total_Lines") or 0
            if total_lines == 0:
                conn.rollback()
                return {
                    "success": False,
                    "applied_count": 0,
                    "conflicts": [],
                    "message": "Session has no count lines to apply.",
                }

            cursor.execute(
                """
                SELECT COUNT(*) AS Unknown_Lines
                FROM Inventory_Count_Lines
                WHERE Session_ID = %s
                  AND Line_Status = 'UNKNOWN'
                """,
                (session_id,)
            )
            unknown_lines = (cursor.fetchone() or {}).get("Unknown_Lines") or 0

            cursor.execute(
                """
                SELECT COUNT(*) AS Unknown_Scans
                FROM Inventory_Count_Scans
                WHERE Session_ID = %s
                  AND Scan_Status = 'UNKNOWN'
                """,
                (session_id,)
            )
            unknown_scans = (cursor.fetchone() or {}).get("Unknown_Scans") or 0
            if (unknown_lines or unknown_scans) and not allow_unknown:
                conn.rollback()
                return {
                    "success": False,
                    "applied_count": 0,
                    "conflicts": [],
                    "message": (
                        "Unknown scanned barcodes must be resolved or explicitly ignored. "
                        f"Lines: {unknown_lines}, scans: {unknown_scans}."
                    ),
                }

            cursor.execute(
                """
                SELECT *
                FROM Inventory_Count_Lines
                WHERE Session_ID = %s
                  AND Batch_ID IS NOT NULL
                  AND Difference_Qty <> 0
                ORDER BY Line_ID
                """,
                (session_id,)
            )
            lines = cursor.fetchall()
            conflicts = []
            adjustments = []

            for line in lines:
                cursor.execute(
                    """
                    SELECT
                        b.Batch_ID,
                        b.Product_ID,
                        b.Internal_Barcode,
                        b.Quantity_Current,
                        b.Status,
                        p.Stock_Unit
                    FROM Inventory_Batches b
                    JOIN Products_Master p ON b.Product_ID = p.Product_ID
                    WHERE b.Batch_ID = %s
                    FOR UPDATE
                    """,
                    (line["Batch_ID"],)
                )
                batch = cursor.fetchone()
                if not batch:
                    conflicts.append(
                        {
                            "Batch_ID": line["Batch_ID"],
                            "barcode": line.get("Internal_Barcode"),
                            "snapshot_qty": line.get("Program_Qty_Snapshot"),
                            "current_qty": None,
                            "counted_qty": line.get("Counted_Qty"),
                            "reason": "Batch not found.",
                        }
                    )
                    continue

                snapshot_qty = self._to_decimal(line["Program_Qty_Snapshot"])
                current_qty = self._to_decimal(batch["Quantity_Current"])
                counted_qty = self._to_decimal(line["Counted_Qty"])
                if current_qty != snapshot_qty:
                    conflicts.append(
                        {
                            "Batch_ID": batch["Batch_ID"],
                            "barcode": batch.get("Internal_Barcode"),
                            "snapshot_qty": snapshot_qty,
                            "current_qty": current_qty,
                            "counted_qty": counted_qty,
                            "reason": "Stock changed after snapshot.",
                        }
                    )
                    continue

                adjustments.append(
                    {
                        "batch": batch,
                        "current_qty": current_qty,
                        "counted_qty": counted_qty,
                    }
                )

            if conflicts:
                conn.rollback()
                return {
                    "success": False,
                    "applied_count": 0,
                    "conflicts": conflicts,
                    "message": "Inventory changed after the count snapshot.",
                }

            applied_count = 0
            for adjustment_item in adjustments:
                batch = adjustment_item["batch"]
                current_qty = adjustment_item["current_qty"]
                counted_qty = adjustment_item["counted_qty"]
                adjustment = counted_qty - current_qty
                if adjustment == 0:
                    continue

                new_status = batch["Status"]
                if counted_qty == 0:
                    new_status = "Depleted"
                elif counted_qty > 0 and new_status == "Depleted":
                    new_status = "Available"

                cursor.execute(
                    """
                    UPDATE Inventory_Batches
                    SET Quantity_Current = %s,
                        Status = %s
                    WHERE Batch_ID = %s
                    """,
                    (counted_qty, new_status, batch["Batch_ID"])
                )

                movement_id = self.stock_movement_log.create_movement_log(
                    product_id=batch["Product_ID"],
                    movement_type="Adjustment",
                    qty_change=adjustment,
                    unit_used=batch.get("Stock_Unit") or "Unit",
                    batch_id=batch["Batch_ID"],
                    notes=f"Inventaire #{session_id} - ajustement apres comptage",
                    user_id=user_id,
                    external_cursor=cursor
                )
                if not movement_id:
                    conn.rollback()
                    return {
                        "success": False,
                        "applied_count": applied_count,
                        "conflicts": [],
                        "message": "Failed to write stock movement log.",
                    }
                applied_count += 1

            cursor.execute(
                """
                UPDATE Inventory_Count_Sessions
                SET Status = 'Applied',
                    Completed_At = COALESCE(Completed_At, NOW()),
                    Applied_At = NOW(),
                    Applied_By = %s
                WHERE Session_ID = %s
                """,
                (user_id, session_id)
            )
            conn.commit()
            return {
                "success": True,
                "applied_count": applied_count,
                "conflicts": [],
                "message": f"Inventory count applied. Adjusted batches: {applied_count}.",
            }

        except Exception as err:
            if conn:
                conn.rollback()
            logging.error(f"Error applying inventory count session: {err}", exc_info=True)
            return {"success": False, "applied_count": 0, "conflicts": [], "message": str(err)}
        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()

    def export_session_to_excel(self, session_id, output_path) -> Dict:
        try:
            if not output_path:
                return {"success": False, "message": "Output path is required."}
            output_path = Path(output_path)
            engine = self._excel_writer_engine()
            if not engine:
                return {
                    "success": False,
                    "message": "Excel export requires xlsxwriter or openpyxl.",
                }

            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                session = self._fetch_session(cursor, session_id)
                if not session:
                    return {"success": False, "message": "Inventory count session not found."}

                lines = self.get_session_lines(session_id)
                summary = self.get_session_summary(session_id)

                cursor.execute(
                    """
                    SELECT
                        s.Scanned_Barcode,
                        s.Qty,
                        s.Scan_Status,
                        s.Scanned_At,
                        s.Scanned_By
                    FROM Inventory_Count_Scans s
                    WHERE s.Session_ID = %s
                    ORDER BY s.Scanned_At DESC
                    """,
                    (session_id,)
                )
                scans = cursor.fetchall()

            def excel_value(value):
                if isinstance(value, Decimal):
                    return float(value)
                return value

            quantity_columns = {
                "Program_Qty_Snapshot",
                "Counted_Qty",
                "Difference_Qty",
                "Qty",
            }

            def excel_line_value(column, value):
                if column in quantity_columns:
                    return self._quantity_to_int(value)
                return excel_value(value)

            summary_df = pd.DataFrame(
                [
                    {
                        "Session_ID": session.get("Session_ID"),
                        "Session_Name": session.get("Session_Name"),
                        "Status": session.get("Status"),
                        "Started_At": session.get("Started_At"),
                        "Applied_At": session.get("Applied_At"),
                        "OK count": summary.get("OK", 0),
                        "SHORT count": summary.get("SHORT", 0),
                        "EXCESS count": summary.get("EXCESS", 0),
                        "NOT_COUNTED count": summary.get("NOT_COUNTED", 0),
                        "UNKNOWN count": summary.get("UNKNOWN", 0),
                        "estimated variance value": excel_value(summary.get("Estimated_Variance_Value", 0)),
                    }
                ]
            )

            line_columns = [
                "Product_Name",
                "Internal_Barcode",
                "Lot_Number",
                "Expiry_Date",
                "Location_Name",
                "Program_Qty_Snapshot",
                "Counted_Qty",
                "Difference_Qty",
                "Line_Status",
                "Comment",
            ]
            lines_df = pd.DataFrame(
                [
                    {column: excel_line_value(column, line.get(column)) for column in line_columns}
                    for line in lines
                ],
                columns=line_columns,
            )

            scan_columns = ["Scanned_Barcode", "Qty", "Scan_Status", "Scanned_At", "Scanned_By"]
            scans_df = pd.DataFrame(
                [
                    {column: excel_line_value(column, scan.get(column)) for column in scan_columns}
                    for scan in scans
                ],
                columns=scan_columns,
            )
            with pd.ExcelWriter(output_path, engine=engine) as writer:
                summary_df.to_excel(writer, sheet_name="Résumé", index=False)
                lines_df.to_excel(writer, sheet_name="Lignes", index=False)
                scans_df.to_excel(writer, sheet_name="Scans", index=False)

            return {"success": True, "message": f"Exported inventory count to {output_path}."}
        except Exception as err:
            logging.error(f"Error exporting inventory count session: {err}", exc_info=True)
            return {"success": False, "message": str(err)}
