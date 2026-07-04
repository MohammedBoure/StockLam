"""Inspect all batches and movements for one reception barcode."""

from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

import mysql.connector
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.base.config import get_external_path


def _json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _connect():
    load_dotenv(get_external_path(".env"), override=True)
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        port=int(os.getenv("DB_PORT", 3306)),
        connection_timeout=int(os.getenv("DB_CONNECT_TIMEOUT", 5)),
        use_pure=True,
        auth_plugin="mysql_native_password",
    )


def _fetch(cursor, query: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    cursor.execute(query, tuple(params))
    return cursor.fetchall()


def _print_rows(title: str, rows: list[dict[str, Any]]) -> None:
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)
    print(f"rows={len(rows)}")
    for row in rows:
        print(json.dumps(row, ensure_ascii=False, default=_json_default, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect one reception barcode.")
    parser.add_argument("--br-id", type=int, required=True)
    parser.add_argument("--barcode", required=True)
    args = parser.parse_args()

    conn = _connect()
    try:
        cursor = conn.cursor(dictionary=True)

        rows = _fetch(
            cursor,
            """
            SELECT
                b.Batch_ID,
                b.BR_ID,
                b.PO_ID,
                b.Product_ID,
                p.Product_Name,
                p.Stock_Unit,
                b.Internal_Barcode,
                b.Location_ID,
                l.Location_Name,
                b.Lot_Number,
                b.Expiry_Date,
                b.Quantity_Initial,
                b.Quantity_Current,
                b.Status,
                b.Created_At,
                b.Unit_Price_Received,
                b.Tax_Rate_Percent,
                b.Discount_Percent,
                COALESCE(SUM(m.Qty_Change), 0) AS Movement_Total,
                COUNT(m.Movement_ID) AS Movement_Count,
                MIN(m.Transaction_Date) AS First_Movement,
                MAX(m.Transaction_Date) AS Last_Movement
            FROM Inventory_Batches b
            JOIN Products_Master p ON p.Product_ID = b.Product_ID
            LEFT JOIN Locations l ON l.Location_ID = b.Location_ID
            LEFT JOIN Stock_Movement_Log m ON m.Batch_ID = b.Batch_ID
            WHERE b.BR_ID = %s AND b.Internal_Barcode = %s
            GROUP BY
                b.Batch_ID, b.BR_ID, b.PO_ID, b.Product_ID, p.Product_Name,
                p.Stock_Unit, b.Internal_Barcode, b.Location_ID, l.Location_Name,
                b.Lot_Number, b.Expiry_Date, b.Quantity_Initial, b.Quantity_Current,
                b.Status, b.Created_At, b.Unit_Price_Received, b.Tax_Rate_Percent,
                b.Discount_Percent
            ORDER BY b.Product_ID, b.Lot_Number, b.Expiry_Date, b.Created_At, b.Batch_ID
            """,
            (args.br_id, args.barcode),
        )
        _print_rows("Batches", rows)

        batch_ids = [row["Batch_ID"] for row in rows]
        if batch_ids:
            placeholders = ",".join(["%s"] * len(batch_ids))
            movements = _fetch(
                cursor,
                f"""
                SELECT
                    m.Movement_ID,
                    m.Transaction_Date,
                    m.Batch_ID,
                    m.Product_ID,
                    p.Product_Name,
                    m.Movement_Type,
                    m.Qty_Change,
                    m.Unit_Used,
                    m.Stock_After,
                    u.Full_Name AS User_Name,
                    m.Notes
                FROM Stock_Movement_Log m
                JOIN Products_Master p ON p.Product_ID = m.Product_ID
                LEFT JOIN Users u ON u.User_ID = m.User_ID
                WHERE m.Batch_ID IN ({placeholders})
                ORDER BY m.Transaction_Date, m.Movement_ID
                """,
                batch_ids,
            )
            _print_rows("Movements", movements)

        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
