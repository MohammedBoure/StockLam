r"""Repair BR stock/reception initial quantities from logs.

This repair keeps the business rule that the inventory batch Quantity_Initial is
also the quantity shown in Bon de reception. It does not zero transfer-created
rows. Instead it verifies each batch against the most reliable available source:

1. latest ReceptionLogManager update_reception_line SystemLogs entry for the
   same Batch_ID;
2. first positive Stock_Movement_Log entry for the batch only when the current
   Quantity_Initial is zero;
3. current Inventory_Batches.Quantity_Initial when no log source exists.

It then recalculates Reception_Log totals from Inventory_Batches.Quantity_Initial.
Default mode is dry-run. Pass --apply to update the database.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

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


def _fetch(cursor, query: str, params=()):
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


def _print_audit_summary(audit_rows: list[dict[str, Any]], repairs: list[dict[str, Any]]) -> None:
    print()
    print("=" * 100)
    print("Quantity_Initial audit summary")
    print("=" * 100)
    print(f"audited_batches={len(audit_rows)}")
    print(f"planned_repairs={len(repairs)}")
    source_counts: dict[str, int] = {}
    source_repairs: dict[str, int] = {}
    for row in audit_rows:
        source = str(row.get("source") or "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1
    for row in repairs:
        source = str(row.get("source") or "unknown")
        source_repairs[source] = source_repairs.get(source, 0) + 1
    print("sources:", json.dumps(source_counts, ensure_ascii=False, sort_keys=True))
    print("repair_sources:", json.dumps(source_repairs, ensure_ascii=False, sort_keys=True))

def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _load_batches(cursor, br_id: int, barcodes: list[str]) -> list[dict[str, Any]]:
    barcode_filter = ""
    params: list[Any] = [br_id]
    if barcodes:
        barcode_filter = "AND b.Internal_Barcode IN (" + ",".join(["%s"] * len(barcodes)) + ")"
        params.extend(barcodes)

    return _fetch(
        cursor,
        f"""
        SELECT
            b.Batch_ID,
            b.BR_ID,
            b.PO_ID,
            b.Product_ID,
            p.Product_Name,
            b.Internal_Barcode,
            b.Location_ID,
            l.Location_Name,
            b.Lot_Number,
            b.Expiry_Date,
            b.Quantity_Initial,
            b.Quantity_Current,
            b.Unit_Price_Received,
            b.Tax_Rate_Percent,
            b.Discount_Percent,
            b.Created_At,
            (
                SELECT m.Qty_Change
                FROM Stock_Movement_Log m
                WHERE m.Batch_ID = b.Batch_ID AND m.Qty_Change > 0
                ORDER BY m.Transaction_Date ASC, m.Movement_ID ASC
                LIMIT 1
            ) AS First_Positive_Qty,
            (
                SELECT m.Movement_Type
                FROM Stock_Movement_Log m
                WHERE m.Batch_ID = b.Batch_ID AND m.Qty_Change > 0
                ORDER BY m.Transaction_Date ASC, m.Movement_ID ASC
                LIMIT 1
            ) AS First_Positive_Type,
            (
                SELECT m.Transaction_Date
                FROM Stock_Movement_Log m
                WHERE m.Batch_ID = b.Batch_ID AND m.Qty_Change > 0
                ORDER BY m.Transaction_Date ASC, m.Movement_ID ASC
                LIMIT 1
            ) AS First_Positive_Date
        FROM Inventory_Batches b
        JOIN Products_Master p ON p.Product_ID = b.Product_ID
        LEFT JOIN Locations l ON l.Location_ID = b.Location_ID
        WHERE b.BR_ID = %s
          {barcode_filter}
        ORDER BY b.Internal_Barcode, b.Product_ID, b.Created_At, b.Batch_ID
        """,
        params,
    )


def _latest_reception_log_quantity(cursor, batch_id: int) -> tuple[Decimal | None, dict[str, Any] | None]:
    rows = _fetch(
        cursor,
        """
        SELECT id, log_date, details
        FROM SystemLogs
        WHERE module = 'ReceptionLogManager'
          AND action LIKE '%update_reception_line%'
          AND details LIKE %s
        ORDER BY log_date DESC, id DESC
        LIMIT 12
        """,
        (f'%"batch_id": {batch_id}%',),
    )
    for row in rows:
        try:
            details = json.loads(row.get("details") or "{}")
        except json.JSONDecodeError:
            continue
        if int(details.get("batch_id") or 0) != int(batch_id):
            continue
        line_data = details.get("line_data") or {}
        if "Quantity_Initial" not in line_data:
            continue
        return _decimal(line_data["Quantity_Initial"]), {
            "log_id": row["id"],
            "log_date": row["log_date"],
        }
    return None, None


def _expected_initial(cursor, batch: dict[str, Any]) -> tuple[Decimal, str, dict[str, Any]]:
    log_qty, log_meta = _latest_reception_log_quantity(cursor, int(batch["Batch_ID"]))
    if log_qty is not None:
        return log_qty, "latest_reception_update_log", log_meta or {}

    current = _decimal(batch.get("Quantity_Initial"))
    first_positive = batch.get("First_Positive_Qty")
    if current == 0 and first_positive is not None and _decimal(first_positive) > 0:
        return _decimal(first_positive), "first_positive_stock_movement_for_zero_initial", {
            "movement_type": batch.get("First_Positive_Type"),
            "movement_date": batch.get("First_Positive_Date"),
        }

    return current, "current_inventory_value", {}


def _recalculate_reception_totals(cursor, br_id: int) -> dict[str, Decimal]:
    rows = _fetch(
        cursor,
        """
        SELECT Quantity_Initial, Unit_Price_Received, Tax_Rate_Percent, Discount_Percent
        FROM Inventory_Batches
        WHERE BR_ID = %s AND Quantity_Initial > 0
        """,
        (br_id,),
    )
    total_ht = Decimal("0")
    total_discount = Decimal("0")
    total_tva = Decimal("0")
    for row in rows:
        qty = _decimal(row["Quantity_Initial"])
        price = _decimal(row["Unit_Price_Received"])
        tax_rate = _decimal(row["Tax_Rate_Percent"]) / Decimal("100")
        discount_rate = _decimal(row["Discount_Percent"]) / Decimal("100")
        line_ht = qty * price
        line_discount = line_ht * discount_rate
        line_net = line_ht - line_discount
        total_ht += line_ht
        total_discount += line_discount
        total_tva += line_net * tax_rate
    total_ttc = (total_ht - total_discount) + total_tva
    return {
        "Invoice_Total_HT": total_ht.quantize(Decimal("0.01")),
        "Invoice_Total_TVA": total_tva.quantize(Decimal("0.01")),
        "Invoice_Total_TTC": total_ttc.quantize(Decimal("0.01")),
        "Total_Discount": total_discount.quantize(Decimal("0.01")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair reception/stock Quantity_Initial consistency.")
    parser.add_argument("--br-id", type=int, required=True)
    parser.add_argument("--barcodes", nargs="*", default=[])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--log-user-id", type=int, default=1)
    parser.add_argument("--verbose-audit", action="store_true")
    args = parser.parse_args()

    conn = _connect()
    conn.autocommit = False
    try:
        cursor = conn.cursor(dictionary=True)
        batches = _load_batches(cursor, args.br_id, args.barcodes)

        audit_rows: list[dict[str, Any]] = []
        repairs: list[dict[str, Any]] = []
        for batch in batches:
            expected, source, source_meta = _expected_initial(cursor, batch)
            current = _decimal(batch.get("Quantity_Initial"))
            row = {
                "batch_id": batch["Batch_ID"],
                "barcode": batch.get("Internal_Barcode"),
                "product_id": batch.get("Product_ID"),
                "product_name": batch.get("Product_Name"),
                "location": batch.get("Location_Name"),
                "current_quantity_initial": current,
                "expected_quantity_initial": expected,
                "quantity_current_kept": batch.get("Quantity_Current"),
                "source": source,
                "source_meta": source_meta,
            }
            audit_rows.append(row)
            if current != expected:
                repairs.append({**row, "action": "set_quantity_initial_from_log_source"})

        _print_audit_summary(audit_rows, repairs)
        if args.verbose_audit:
            _print_rows("Quantity_Initial audit", audit_rows)
        _print_rows("Planned repairs", repairs)

        before_totals = _recalculate_reception_totals(cursor, args.br_id)
        print()
        print("Before totals:", json.dumps(before_totals, default=_json_default, sort_keys=True))

        if not repairs:
            conn.rollback()
            print("No quantity repair needed.")
            return 0

        if not args.apply:
            conn.rollback()
            print("Dry-run only. Re-run with --apply to update Quantity_Initial and reception totals.")
            return 0

        for repair in repairs:
            cursor.execute(
                "UPDATE Inventory_Batches SET Quantity_Initial = %s WHERE Batch_ID = %s",
                (repair["expected_quantity_initial"], repair["batch_id"]),
            )

        after_totals = _recalculate_reception_totals(cursor, args.br_id)
        cursor.execute(
            """
            UPDATE Reception_Log
            SET Invoice_Total_HT = %s,
                Invoice_Total_TVA = %s,
                Invoice_Total_TTC = %s,
                Total_Discount = %s
            WHERE BR_ID = %s
            """,
            (
                after_totals["Invoice_Total_HT"],
                after_totals["Invoice_Total_TVA"],
                after_totals["Invoice_Total_TTC"],
                after_totals["Total_Discount"],
                args.br_id,
            ),
        )

        log_details = {
            "br_id": args.br_id,
            "barcodes": args.barcodes,
            "repairs": repairs,
            "before_totals": before_totals,
            "after_totals": after_totals,
        }
        cursor.execute(
            """
            INSERT INTO SystemLogs (user_id, module, action, details, ip_address)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                args.log_user_id,
                "ReceptionStockConsistencyRepair",
                "[UPDATE] repair_quantity_initial_from_logs()",
                json.dumps(log_details, ensure_ascii=False, default=_json_default),
                "127.0.0.1",
            ),
        )

        conn.commit()
        print("After totals:", json.dumps(after_totals, default=_json_default, sort_keys=True))
        print("Repair applied.")
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
