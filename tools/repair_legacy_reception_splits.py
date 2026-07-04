"""Repair legacy reception rows that were created by old location transfers.

The old transfer algorithm sometimes created destination Inventory_Batches rows
with a positive Quantity_Initial. That makes the original reception voucher show
the same received product twice and inflates reception totals. The current stock
quantity is still useful, so this repair only resets Quantity_Initial to zero on
non-canonical split rows. Quantity_Current is not changed.

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


def _load_duplicate_groups(cursor, br_id: int, barcodes: list[str]):
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
            GROUP_CONCAT(DISTINCT b.Expiry_Date ORDER BY b.Expiry_Date SEPARATOR ', ') AS Expiry_Dates,
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


def _load_group_batches(cursor, group: dict[str, Any]):
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
            COALESCE(SUM(m.Qty_Change), 0) AS Movement_Total,
            COUNT(m.Movement_ID) AS Movement_Count,
            MIN(m.Transaction_Date) AS First_Movement,
            MAX(m.Transaction_Date) AS Last_Movement
        FROM Inventory_Batches b
        JOIN Products_Master p ON p.Product_ID = b.Product_ID
        LEFT JOIN Locations l ON l.Location_ID = b.Location_ID
        LEFT JOIN Stock_Movement_Log m ON m.Batch_ID = b.Batch_ID
        WHERE b.BR_ID = %s
          AND b.Product_ID = %s
          AND b.Internal_Barcode = %s
          AND COALESCE(b.Lot_Number, '') = COALESCE(%s, '')
        GROUP BY
            b.Batch_ID, b.BR_ID, b.PO_ID, b.Product_ID, p.Product_Name,
            b.Internal_Barcode, b.Location_ID, l.Location_Name, b.Lot_Number,
            b.Expiry_Date, b.Quantity_Initial, b.Quantity_Current, b.Status, b.Created_At
        ORDER BY b.Created_At, b.Batch_ID
        """,
        (
            group["BR_ID"],
            group["Product_ID"],
            group["Internal_Barcode"],
            group["Lot_Number"],
        ),
    )


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
        qty = Decimal(str(row["Quantity_Initial"] or 0))
        price = Decimal(str(row["Unit_Price_Received"] or 0))
        tax_rate = Decimal(str(row["Tax_Rate_Percent"] or 0)) / Decimal("100")
        discount_rate = Decimal(str(row["Discount_Percent"] or 0)) / Decimal("100")
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
    parser = argparse.ArgumentParser(description="Repair legacy transfer-created reception splits.")
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
        _print_rows("Duplicate groups to inspect", groups)

        repairs: list[dict[str, Any]] = []
        for group in groups:
            batches = _load_group_batches(cursor, group)
            if not batches:
                continue
            canonical = batches[0]
            for split in batches[1:]:
                if Decimal(str(split["Quantity_Initial"] or 0)) <= 0:
                    continue
                repairs.append(
                    {
                        "action": "reset_split_quantity_initial_to_zero",
                        "canonical_batch_id": canonical["Batch_ID"],
                        "split_batch_id": split["Batch_ID"],
                        "barcode": split["Internal_Barcode"],
                        "product_id": split["Product_ID"],
                        "product_name": split["Product_Name"],
                        "location": split["Location_Name"],
                        "old_quantity_initial": split["Quantity_Initial"],
                        "quantity_current_kept": split["Quantity_Current"],
                        "movement_total": split["Movement_Total"],
                    }
                )

        _print_rows("Planned repairs", repairs)
        if not repairs:
            conn.rollback()
            print("No repair needed.")
            return 0

        before_totals = _recalculate_reception_totals(cursor, args.br_id)
        print()
        print("Before totals:", json.dumps(before_totals, default=_json_default, sort_keys=True))

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
                "LegacyReceptionSplitRepair",
                "[UPDATE] reset_transfer_split_quantity_initial()",
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
