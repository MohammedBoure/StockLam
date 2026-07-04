"""Read-only stock/reception audit helper.

This script follows one reception voucher through the batch table, movement
ledger, transfer/credit-note side tables, and automatic system logs. It is
intended for diagnosing legacy split-batch data before any repair is applied.
"""

from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal
from typing import Any, Iterable

import mysql.connector
from dotenv import load_dotenv

from database.base.config import get_external_path


def _json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _print_section(title: str) -> None:
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)


def _print_rows(rows: list[dict[str, Any]], limit: int | None = None) -> None:
    shown = rows if limit is None else rows[:limit]
    print(f"rows={len(rows)}")
    for row in shown:
        print(json.dumps(row, ensure_ascii=False, default=_json_default, sort_keys=True))
    if limit is not None and len(rows) > limit:
        print(f"... {len(rows) - limit} more rows omitted")


def _connect():
    load_dotenv(get_external_path(".env"), override=True)
    cfg = {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME"),
        "port": int(os.getenv("DB_PORT", 3306)),
        "connection_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", 5)),
        "use_pure": True,
        "auth_plugin": "mysql_native_password",
    }
    return mysql.connector.connect(**cfg)


def _fetch(cursor, query: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    cursor.execute(query, tuple(params))
    return cursor.fetchall()


def _build_like_clause(fields: list[str], terms: list[str]) -> tuple[str, list[str]]:
    clauses: list[str] = []
    params: list[str] = []
    for term in terms:
        for field in fields:
            clauses.append(f"{field} LIKE %s")
            params.append(f"%{term}%")
    if not clauses:
        return "1=0", []
    return "(" + " OR ".join(clauses) + ")", params


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit one reception voucher and related stock rows.")
    parser.add_argument("--br-id", type=int, required=True, help="Reception_Log.BR_ID to audit")
    parser.add_argument("--invoice-ref", default=None, help="Optional invoice reference for context")
    parser.add_argument("--barcodes", nargs="*", default=[], help="Internal barcodes to focus on")
    parser.add_argument("--system-log-limit", type=int, default=80)
    args = parser.parse_args()

    conn = _connect()
    try:
        cursor = conn.cursor(dictionary=True)

        _print_section("Reception header")
        header_rows = _fetch(
            cursor,
            """
            SELECT rl.*, s.Supplier_Name
            FROM Reception_Log rl
            LEFT JOIN Suppliers s ON s.Supplier_ID = rl.Supplier_ID
            WHERE rl.BR_ID = %s
               OR (%s IS NOT NULL AND rl.Supplier_Invoice_Ref = %s)
            ORDER BY rl.BR_ID
            """,
            (args.br_id, args.invoice_ref, args.invoice_ref),
        )
        _print_rows(header_rows)

        _print_section("Batches for BR")
        batch_rows = _fetch(
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
                b.Unit_Price_Received,
                b.Tax_Rate_Percent,
                b.Discount_Percent,
                b.Created_At,
                b.Reception_Note
            FROM Inventory_Batches b
            JOIN Products_Master p ON p.Product_ID = b.Product_ID
            LEFT JOIN Locations l ON l.Location_ID = b.Location_ID
            WHERE b.BR_ID = %s
            ORDER BY b.Internal_Barcode, b.Product_ID, b.Batch_ID
            """,
            (args.br_id,),
        )
        _print_rows(batch_rows)

        batch_ids = [row["Batch_ID"] for row in batch_rows]
        focused_batch_ids = [
            row["Batch_ID"]
            for row in batch_rows
            if not args.barcodes or str(row.get("Internal_Barcode")) in set(args.barcodes)
        ]
        focused_batch_ids = focused_batch_ids or batch_ids

        _print_section("Duplicate groups inside BR")
        duplicate_rows = _fetch(
            cursor,
            """
            SELECT
                b.BR_ID,
                b.Product_ID,
                p.Product_Name,
                b.Internal_Barcode,
                b.Lot_Number,
                b.Expiry_Date,
                COUNT(*) AS Batch_Count,
                GROUP_CONCAT(b.Batch_ID ORDER BY b.Batch_ID) AS Batch_IDs,
                GROUP_CONCAT(b.Location_ID ORDER BY b.Batch_ID) AS Location_IDs,
                GROUP_CONCAT(b.Quantity_Initial ORDER BY b.Batch_ID) AS Initial_Qtys,
                GROUP_CONCAT(b.Quantity_Current ORDER BY b.Batch_ID) AS Current_Qtys,
                SUM(b.Quantity_Initial) AS Total_Initial,
                SUM(b.Quantity_Current) AS Total_Current
            FROM Inventory_Batches b
            JOIN Products_Master p ON p.Product_ID = b.Product_ID
            WHERE b.BR_ID = %s
            GROUP BY b.BR_ID, b.Product_ID, b.Internal_Barcode, b.Lot_Number, b.Expiry_Date
            HAVING COUNT(*) > 1
            ORDER BY b.Internal_Barcode, b.Product_ID
            """,
            (args.br_id,),
        )
        _print_rows(duplicate_rows)

        _print_section("Batch quantities versus movement ledger")
        movement_summary_rows: list[dict[str, Any]] = []
        if batch_ids:
            placeholders = ",".join(["%s"] * len(batch_ids))
            movement_summary_rows = _fetch(
                cursor,
                f"""
                SELECT
                    b.Batch_ID,
                    b.Product_ID,
                    p.Product_Name,
                    b.Internal_Barcode,
                    b.Location_ID,
                    b.Quantity_Initial,
                    b.Quantity_Current,
                    COALESCE(SUM(m.Qty_Change), 0) AS Movement_Total,
                    COALESCE(SUM(CASE
                        WHEN m.Movement_Type IN ('Purchase_Receive', 'Adjustment', 'Transfer')
                        THEN m.Qty_Change ELSE 0 END), 0) AS InOut_Total,
                    COUNT(m.Movement_ID) AS Movement_Count,
                    MIN(m.Transaction_Date) AS First_Movement,
                    MAX(m.Transaction_Date) AS Last_Movement
                FROM Inventory_Batches b
                JOIN Products_Master p ON p.Product_ID = b.Product_ID
                LEFT JOIN Stock_Movement_Log m ON m.Batch_ID = b.Batch_ID
                WHERE b.Batch_ID IN ({placeholders})
                GROUP BY
                    b.Batch_ID, b.Product_ID, p.Product_Name, b.Internal_Barcode,
                    b.Location_ID, b.Quantity_Initial, b.Quantity_Current
                ORDER BY b.Internal_Barcode, b.Batch_ID
                """,
                batch_ids,
            )
        _print_rows(movement_summary_rows)

        _print_section("Focused movement timeline")
        movement_rows: list[dict[str, Any]] = []
        if focused_batch_ids:
            placeholders = ",".join(["%s"] * len(focused_batch_ids))
            movement_rows = _fetch(
                cursor,
                f"""
                SELECT
                    m.Movement_ID,
                    m.Transaction_Date,
                    m.Batch_ID,
                    m.Product_ID,
                    p.Product_Name,
                    b.Internal_Barcode,
                    b.Location_ID,
                    l.Location_Name,
                    m.Movement_Type,
                    m.Qty_Change,
                    m.Unit_Used,
                    m.Stock_After,
                    m.User_ID,
                    u.Full_Name AS User_Name,
                    m.Notes
                FROM Stock_Movement_Log m
                LEFT JOIN Inventory_Batches b ON b.Batch_ID = m.Batch_ID
                LEFT JOIN Products_Master p ON p.Product_ID = m.Product_ID
                LEFT JOIN Locations l ON l.Location_ID = b.Location_ID
                LEFT JOIN Users u ON u.User_ID = m.User_ID
                WHERE m.Batch_ID IN ({placeholders})
                ORDER BY m.Transaction_Date, m.Movement_ID
                """,
                focused_batch_ids,
            )
        _print_rows(movement_rows)

        _print_section("External transfers involving focused batches")
        transfer_rows: list[dict[str, Any]] = []
        if focused_batch_ids:
            placeholders = ",".join(["%s"] * len(focused_batch_ids))
            transfer_rows = _fetch(
                cursor,
                f"""
                SELECT
                    t.Transfer_ID,
                    t.Transaction_Date,
                    t.Status,
                    t.Transfer_Type,
                    d.Detail_ID,
                    d.Batch_ID,
                    d.Product_ID,
                    p.Product_Name,
                    d.Qty_Transferred,
                    d.Unit_Price,
                    d.Line_Note,
                    ep.Partner_Name
                FROM External_Transfer_Details d
                JOIN External_Transfer_Log t ON t.Transfer_ID = d.Transfer_ID
                LEFT JOIN Products_Master p ON p.Product_ID = d.Product_ID
                LEFT JOIN External_Partners ep ON ep.Partner_ID = t.Partner_ID
                WHERE d.Batch_ID IN ({placeholders})
                ORDER BY t.Transaction_Date, t.Transfer_ID, d.Detail_ID
                """,
                focused_batch_ids,
            )
        _print_rows(transfer_rows)

        _print_section("Credit notes involving focused batches")
        credit_rows: list[dict[str, Any]] = []
        if focused_batch_ids:
            placeholders = ",".join(["%s"] * len(focused_batch_ids))
            credit_rows = _fetch(
                cursor,
                f"""
                SELECT
                    cn.Credit_Note_ID,
                    cn.Credit_Note_Ref,
                    cn.Credit_Note_Date,
                    cn.Status,
                    cn.BR_ID,
                    d.Detail_ID,
                    d.Batch_ID,
                    d.Product_ID,
                    p.Product_Name,
                    d.Qty_Returned,
                    d.Unit_Price_HT,
                    d.Line_Note
                FROM Credit_Note_Details d
                JOIN Supplier_Credit_Notes cn ON cn.Credit_Note_ID = d.Credit_Note_ID
                LEFT JOIN Products_Master p ON p.Product_ID = d.Product_ID
                WHERE d.Batch_ID IN ({placeholders})
                ORDER BY cn.Credit_Note_Date, cn.Credit_Note_ID, d.Detail_ID
                """,
                focused_batch_ids,
            )
        _print_rows(credit_rows)

        _print_section("System logs matching BR/barcodes/batch IDs")
        terms = [str(args.br_id), *(args.barcodes or []), *[str(batch_id) for batch_id in focused_batch_ids]]
        where_clause, params = _build_like_clause(["sl.details", "sl.action", "sl.module"], terms)
        log_rows = _fetch(
            cursor,
            f"""
            SELECT
                sl.id,
                sl.log_date,
                sl.user_id,
                u.Full_Name AS User_Name,
                sl.module,
                sl.action,
                sl.details,
                sl.ip_address
            FROM SystemLogs sl
            LEFT JOIN Users u ON u.User_ID = sl.user_id
            WHERE {where_clause}
            ORDER BY sl.log_date, sl.id
            LIMIT %s
            """,
            [*params, args.system_log_limit],
        )
        _print_rows(log_rows)

        _print_section("Suggested interpretation")
        for row in duplicate_rows:
            print(
                "Duplicate reception row: "
                f"barcode={row.get('Internal_Barcode')} product={row.get('Product_Name')} "
                f"batch_ids={row.get('Batch_IDs')} initial={row.get('Initial_Qtys')} "
                f"current={row.get('Current_Qtys')} total_initial={row.get('Total_Initial')} "
                f"total_current={row.get('Total_Current')}"
            )
        for row in movement_summary_rows:
            qty_current = Decimal(str(row.get("Quantity_Current") or 0))
            movement_total = Decimal(str(row.get("Movement_Total") or 0))
            if qty_current != movement_total:
                print(
                    "Quantity_Current mismatch: "
                    f"batch={row.get('Batch_ID')} barcode={row.get('Internal_Barcode')} "
                    f"current={qty_current} movement_total={movement_total}"
                )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
