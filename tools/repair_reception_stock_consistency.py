"""Repair transfer-created duplicate rows in a reception voucher.

Inventory_Batches is used by two screens:
- Bon de reception should show only real received lines.
- Stock should keep showing the useful initial quantity for moved batches.

The legacy transfer flow copied BR_ID onto destination batches. When those
destination batches kept a positive Quantity_Initial, the Bon showed the same
barcode twice and totals were inflated. This repair resets Quantity_Initial to
zero only on duplicate rows whose first movement is a Transfer. Quantity_Current
is never changed, and the stock screen can still display the moved batch initial
quantity from Stock_Movement_Log.

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


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _print_rows(title: str, rows: list[dict[str, Any]]) -> None:
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)
    print(f"rows={len(rows)}")
    for row in rows:
        print(json.dumps(row, ensure_ascii=False, default=_json_default, sort_keys=True))


def _load_duplicate_groups(cursor, br_id: int, barcodes: list[str]) -> list[dict[str, Any]]:
    barcode_filter = ""
    params: list[Any] = [br_id]
    if barcodes:
        barcode_filter = "AND b.Internal_Barcode IN (" + ",".join(["%s"] * len(barcodes)) + ")"
        params.extend(barcodes)

    return _fetch(
        cursor,
        f"""
        SELECT
            b.BR_ID,
            b.Product_ID,
            p.Product_Name,
            b.Internal_Barcode,
            b.Lot_Number,
            COUNT(*) AS Batch_Count,
            SUM(b.Quantity_Initial) AS Total_Initial,
            SUM(b.Quantity_Current) AS Total_Current
        FROM Inventory_Batches b
        JOIN Products_Master p ON p.Product_ID = b.Product_ID
        WHERE b.BR_ID = %s
          AND b.Quantity_Initial > 0
          {barcode_filter}
        GROUP BY b.BR_ID, b.Product_ID, b.Internal_Barcode, b.Lot_Number
        HAVING COUNT(*) > 1
        ORDER BY b.Internal_Barcode, b.Product_ID
        """,
        params,
    )


def _load_group_batches(cursor, group: dict[str, Any]) -> list[dict[str, Any]]:
    return _fetch(
        cursor,
        """
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
            b.Status,
            b.Created_At,
            (
                SELECT m.Movement_Type
                FROM Stock_Movement_Log m
                WHERE m.Batch_ID = b.Batch_ID
                ORDER BY m.Transaction_Date ASC, m.Movement_ID ASC
                LIMIT 1
            ) AS First_Movement_Type,
            (
                SELECT m.Qty_Change
                FROM Stock_Movement_Log m
                WHERE m.Batch_ID = b.Batch_ID
                ORDER BY m.Transaction_Date ASC, m.Movement_ID ASC
                LIMIT 1
            ) AS First_Movement_Qty,
            (
                SELECT m.Transaction_Date
                FROM Stock_Movement_Log m
                WHERE m.Batch_ID = b.Batch_ID
                ORDER BY m.Transaction_Date ASC, m.Movement_ID ASC
                LIMIT 1
            ) AS First_Movement_Date
        FROM Inventory_Batches b
        JOIN Products_Master p ON p.Product_ID = b.Product_ID
        LEFT JOIN Locations l ON l.Location_ID = b.Location_ID
        WHERE b.BR_ID = %s
          AND b.Product_ID = %s
          AND b.Internal_Barcode = %s
          AND COALESCE(b.Lot_Number, '') = COALESCE(%s, '')
          AND b.Quantity_Initial > 0
        ORDER BY b.Created_At, b.Batch_ID
        """,
        (
            group["BR_ID"],
            group["Product_ID"],
            group["Internal_Barcode"],
            group["Lot_Number"],
        ),
    )


def _plan_repairs(cursor, groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    repairs: list[dict[str, Any]] = []
    for group in groups:
        batches = _load_group_batches(cursor, group)
        if len(batches) < 2:
            continue

        purchase_batches = [
            b for b in batches
            if str(b.get("First_Movement_Type") or "").lower() != "transfer"
        ]
        if not purchase_batches:
            continue

        canonical = purchase_batches[0]
        for batch in batches:
            if batch["Batch_ID"] == canonical["Batch_ID"]:
                continue
            if str(batch.get("First_Movement_Type") or "").lower() != "transfer":
                continue
            if _decimal(batch.get("Quantity_Initial")) <= 0:
                continue
            repairs.append(
                {
                    "action": "hide_transfer_batch_from_reception",
                    "canonical_batch_id": canonical["Batch_ID"],
                    "split_batch_id": batch["Batch_ID"],
                    "barcode": batch["Internal_Barcode"],
                    "product_id": batch["Product_ID"],
                    "product_name": batch["Product_Name"],
                    "location": batch["Location_Name"],
                    "old_quantity_initial": batch["Quantity_Initial"],
                    "quantity_current_kept": batch["Quantity_Current"],
                    "first_movement_type": batch["First_Movement_Type"],
                    "first_movement_qty": batch["First_Movement_Qty"],
                    "first_movement_date": batch["First_Movement_Date"],
                }
            )
    return repairs


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
    parser = argparse.ArgumentParser(description="Repair transfer-created duplicate Bon rows.")
    parser.add_argument("--br-id", type=int, required=True)
    parser.add_argument("--barcodes", nargs="*", default=[])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--log-user-id", type=int, default=1)
    args = parser.parse_args()

    conn = _connect()
    conn.autocommit = False
    try:
        cursor = conn.cursor(dictionary=True)
        groups = _load_duplicate_groups(cursor, args.br_id, args.barcodes)
        repairs = _plan_repairs(cursor, groups)

        _print_rows("Duplicate positive reception groups", groups)
        _print_rows("Planned repairs", repairs)

        before_totals = _recalculate_reception_totals(cursor, args.br_id)
        print()
        print("Before totals:", json.dumps(before_totals, default=_json_default, sort_keys=True))

        if not repairs:
            conn.rollback()
            print("No repair needed.")
            return 0

        if not args.apply:
            conn.rollback()
            print("Dry-run only. Re-run with --apply to update Quantity_Initial and reception totals.")
            return 0

        for repair in repairs:
            cursor.execute(
                "UPDATE Inventory_Batches SET Quantity_Initial = 0 WHERE Batch_ID = %s",
                (repair["split_batch_id"],),
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
                "[UPDATE] hide_transfer_batches_from_reception()",
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
