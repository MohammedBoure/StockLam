"""
complete_reception_repair.py
-------------------------------------------------------------------------
مُطور خصيصاً للمهندس أنس بوزياد لإصلاح مشكلة تكرار السطور الناتجة عن النقل.
يتكفل هذا السكربت بالمعالجة الكاملة وإعادة احتساب المجاميع بدقة في خطوة واحدة.
-------------------------------------------------------------------------
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

# إعداد المسارات لضمان قراءة ملف البيئة والمشروع بشكل صحيح
PROJECT_ROOT = Path(__file__).resolve().parents[0]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _connect():
    """تأسيس الاتصال بقاعدة البيانات اعتماداً على ملف الـ .env"""
    # البحث عن ملف البيئة في المجلد الخارجي أو الحالي
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        env_path = Path(os.getcwd()) / ".env"
        
    load_dotenv(env_path, override=True)
    
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


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _print_section(title: str) -> None:
    print("\n" + "=" * 100)
    print(f" {title} ")
    print("=" * 100)


def _load_duplicate_groups(cursor, br_id: int) -> list[dict[str, Any]]:
    """البحث عن المجموعات المكررة التي تحتوي على كميات ابتدائية موجبة لنفس الـ BR"""
    return _fetch(
        cursor,
        """
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
        GROUP BY b.BR_ID, b.Product_ID, b.Internal_Barcode, b.Lot_Number
        HAVING COUNT(*) > 1
        ORDER BY b.Internal_Barcode, b.Product_ID
        """,
        (br_id,),
    )


def _load_group_batches(cursor, group: dict[str, Any]) -> list[dict[str, Any]]:
    """جلب كافة الدفعات المرتبطة بالمجموعة المكررة مع تحديد نوع أول حركة مخزنية لها"""
    return _fetch(
        cursor,
        """
        SELECT
            b.Batch_ID,
            b.BR_ID,
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


def _recalculate_reception_totals(cursor, br_id: int) -> dict[str, Decimal]:
    """إعادة حساب إجمالي الفاتورة HT, TVA, TTC بناءً على السطور الحقيقية المتبقية فقط"""
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
    parser = argparse.ArgumentParser(description="Script مخصص لأنس بوزياد لإصلاح تكرار سطور الاستلام بالكامل.")
    parser.add_argument("--br-id", type=str, required=True, help="معرف BR_ID المراد فصحه وإصلاحه، أو 'all' لفحص جميع المستندات.")
    parser.add_argument("--apply", action="store_true", help="تطبيق الإصلاح الفعلي على قاعدة البيانات")
    parser.add_argument("--log-user-id", type=int, default=1, help="معرف المستخدم لتسجيل العمليات")
    args = parser.parse_args()

    conn = _connect()
    conn.autocommit = False
    try:
        cursor = conn.cursor(dictionary=True)
        if args.br_id.lower() == "all":
            rows = _fetch(cursor, "SELECT DISTINCT BR_ID FROM Inventory_Batches WHERE BR_ID IS NOT NULL")
            br_ids = [r["BR_ID"] for r in rows]
            _print_section("تم اختيار وضع 'all': سيتم فحص جميع المستندات في قاعدة البيانات")
        else:
            br_ids = [int(args.br_id)]

        total_repairs = 0
        
        for br_id in br_ids:
            _print_section(f"البدء في تحليل مستند الاستلام رقم: {br_id}")
            groups = _load_duplicate_groups(cursor, br_id)
            if not groups:
                print("قاعدة البيانات سليمة لهذا المستند.")
                continue
                
            print(f"تم العثور على {len(groups)} مجموعة تكرار مرشحة للفحص في {br_id}.")
            
            repairs: list[dict[str, Any]] = []
            for group in groups:
                batches = _load_group_batches(cursor, group)
                if len(batches) < 2:
                    continue
    
                # تحديد الدفعة الأصلية (التي لم تبدأ بحركة نقل)
                purchase_batches = [
                    b for b in batches
                    if str(b.get("First_Movement_Type") or "").lower() != "transfer"
                ]
                
                if not purchase_batches:
                    canonical = batches[0]
                else:
                    canonical = purchase_batches[0]
    
                for batch in batches:
                    if batch["Batch_ID"] == canonical["Batch_ID"]:
                        continue
                    if str(batch.get("First_Movement_Type") or "").lower() != "transfer":
                        continue
                    if _decimal(batch.get("Quantity_Initial")) <= 0:
                        continue
                        
                    repairs.append({
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
                    })
    
            if not repairs:
                print("لا توجد أي سطور مكررة ناتجة عن النقل لهذا المستند.")
                continue

            print(f"عدد السطور الوهمية المكتشفة والمراد إخفاؤها من الوصل: {len(repairs)}")
            for r in repairs:
                print(f" -> المنتج: {r['product_name']} | الكود: {r['barcode']} | المعرف المتضرر: {r['split_batch_id']} (الكمية القديمة: {r['old_quantity_initial']})")
    
            before_totals = _recalculate_reception_totals(cursor, br_id)
            print(f"\nالمجاميع الحالية: HT={before_totals['Invoice_Total_HT']} | TTC={before_totals['Invoice_Total_TTC']}")
    
            if not args.apply:
                print("[وضع المحاكاة Dry-Run]: لتطبيق التعديلات، استخدم --apply")
                continue
    
            for repair in repairs:
                cursor.execute(
                    "UPDATE Inventory_Batches SET Quantity_Initial = 0 WHERE Batch_ID = %s",
                    (repair["split_batch_id"],),
                )
                print(f" ✔ تم تصفير الكمية الابتدائية للدفعة رقم {repair['split_batch_id']}.")
    
            after_totals = _recalculate_reception_totals(cursor, br_id)
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
                    br_id,
                ),
            )
    
            log_details = {
                "br_id": br_id,
                "repairs_count": len(repairs),
                "repairs": repairs,
                "before_totals": before_totals,
                "after_totals": after_totals,
                "repaired_by": "Anis Bouziad Script Pipeline"
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
            
            total_repairs += len(repairs)
            print(f"المجاميع الجديدة بعد الإصلاح: HT={after_totals['Invoice_Total_HT']} | TTC={after_totals['Invoice_Total_TTC']}")
            print(f" 🎉 تم الانتهاء من إصلاح المستند {br_id}!")

        if args.apply:
            conn.commit()
            _print_section("النتيجة النهائية")
            print(f"تم تطبيق الإصلاحات بنجاح وحفظها في قاعدة البيانات! إجمالي السطور المصلحة: {total_repairs}")
        else:
            conn.rollback()
            _print_section("النتيجة النهائية")
            print("لم يتم حفظ أي تغييرات (Dry-Run).")
            
        return 0
        
    except Exception as e:
        conn.rollback()
        print(f"\n ❌ حدث خطأ غير متوقع أثناء معالجة البيانات: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())