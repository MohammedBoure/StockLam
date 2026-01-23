# database/managers/credit_note_manager.py

import mysql.connector
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional, Tuple

# استيراد مدير الحركات لتسجيل خروج البضاعة
from .stock_movement_log_manager import StockMovementLogManager

class CreditNoteManager:
    """
    إدارة إشعارات الدائن (Avoirs) من الموردين.
    يعالج الجانب المالي + الجانب المخزني (إرجاع البضاعة).
    """

    def __init__(self, db_instance):
        self.db = db_instance
        self.movement_manager = StockMovementLogManager(db_instance)


    def get_credit_note_details(self, credit_note_id):
        """جلب تفاصيل إشعار محدد."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # Header
                cursor.execute("""
                    SELECT cn.*, s.Supplier_Name 
                    FROM Supplier_Credit_Notes cn
                    JOIN Suppliers s ON cn.Supplier_ID = s.Supplier_ID
                    WHERE cn.Credit_Note_ID = %s
                """, (credit_note_id,))
                header = cursor.fetchone()
                
                if not header: return None

                # Details
                cursor.execute("""
                    SELECT d.*, p.Product_Name, p.Stock_Unit
                    FROM Credit_Note_Details d
                    JOIN Products_Master p ON d.Product_ID = p.Product_ID
                    WHERE d.Credit_Note_ID = %s
                """, (credit_note_id,))
                details = cursor.fetchall()
                
                return {"Header": header, "Details": details}
        except Exception as e:
            logging.error(f"Error fetching credit note details: {e}")
            return None

    def delete_credit_note(self, credit_note_id):
        """
        حذف إشعار (بحذر). 
        ملاحظة: لا نقوم بإعادة المخزون تلقائياً في الحذف لتفادي التعقيد، 
        يفضل إلغاء الإشعار بإنشاء فاتورة جديدة، أو يتم الأمر يدوياً.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                # التحقق من الحالة أولاً إذا أردت تقييد الحذف
                
                cursor.execute("DELETE FROM Credit_Note_Details WHERE Credit_Note_ID = %s", (credit_note_id,))
                cursor.execute("DELETE FROM Supplier_Credit_Notes WHERE Credit_Note_ID = %s", (credit_note_id,))
                conn.commit()
                return True, "Supprimé avec succès."
        except Exception as e:
            return False, str(e)
        



    def create_credit_note(self, header_data: Dict, items: List[Dict], user_id: Optional[int] = None) -> Tuple[bool, str]:
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)

            # 1. إدخال رأس الإشعار
            query_header = """
                INSERT INTO Supplier_Credit_Notes 
                (Credit_Note_Ref, Supplier_ID, BR_ID, Credit_Date, Type, Status, 
                 Total_Amount_HT, Total_TVA, Total_Amount_TTC, Notes, Created_By, Created_At)
                VALUES (%s, %s, %s, %s, %s, 'Validated', %s, %s, %s, %s, %s, NOW())
            """
            
            note_type = header_data.get('Type', 'Return_Goods')
            
            params_header = (
                header_data['Credit_Note_Ref'],
                header_data['Supplier_ID'],
                header_data.get('BR_ID'),
                header_data['Credit_Date'],
                note_type,
                header_data.get('Total_Amount_HT', 0),
                header_data.get('Total_TVA', 0),
                header_data.get('Total_Amount_TTC', 0),
                header_data.get('Notes', ''),
                user_id
            )
            
            cursor.execute(query_header, params_header)
            credit_note_id = cursor.lastrowid

            # 2. معالجة تفاصيل المنتجات
            for item in items:
                product_id = item['Product_ID']
                qty_return = Decimal(str(item.get('Qty_Returned', 0)))
                lot_number = item.get('Lot_Number')
                
                batch_id = None
                
                # --- خصم المخزون إذا كان "إرجاع بضاعة" ---
                if note_type == 'Return_Goods' and qty_return > 0:
                    batch_id = self._process_stock_return(
                        cursor, product_id, qty_return, lot_number, 
                        user_id, credit_note_id, header_data['Credit_Note_Ref']
                    )
                    
                    # إذا فشل العثور على الباتش أو الكمية غير كافية، نوقف العملية
                    if batch_id is None:
                        raise ValueError(f"Impossible de retourner le produit ID {product_id} (Lot: {lot_number}). Stock insuffisant ou lot introuvable.")

                # 3. إدخال سطر التفاصيل
                query_detail = """
                    INSERT INTO Credit_Note_Details 
                    (Credit_Note_ID, Product_ID, Batch_ID, Lot_Number, Expiry_Date, 
                     Qty_Returned, Unit_Price, Line_Total)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                unit_price = Decimal(str(item.get('Unit_Price', 0)))
                line_total = qty_return * unit_price

                cursor.execute(query_detail, (
                    credit_note_id,
                    product_id,
                    batch_id,
                    lot_number,
                    item.get('Expiry_Date'),
                    qty_return,
                    unit_price,
                    line_total
                ))

            conn.commit()
            return True, f"Avoir enregistré avec succès (ID: {credit_note_id})"

        except ValueError as ve:
            if conn: conn.rollback()
            return False, str(ve)
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"❌ Error creating credit note: {e}")
            return False, str(e)
        finally:
            if conn: conn.close()

    def _process_stock_return(self, cursor, product_id, qty, lot_number, user_id, cn_id, cn_ref):
        """
        البحث عن الباتش وخصم الكمية منه بدقة.
        """
        if not lot_number:
            return None

        # البحث عن باتش يطابق المنتج واللوت، ويحتوي على كمية كافية
        query_find_batch = """
            SELECT Batch_ID, Quantity_Current 
            FROM Inventory_Batches 
            WHERE Product_ID = %s AND Lot_Number = %s AND Quantity_Current >= %s
            LIMIT 1
        """
        cursor.execute(query_find_batch, (product_id, lot_number, qty))
        batch = cursor.fetchone()

        if batch:
            batch_id = batch['Batch_ID']
            current_qty = batch['Quantity_Current']
            
            # خصم الكمية
            new_qty = current_qty - qty
            
            # تحديث الباتش (تحويل حالته لـ Depleted إذا وصل للصفر)
            cursor.execute(
                "UPDATE Inventory_Batches SET Quantity_Current = %s, Status = IF(%s=0, 'Depleted', Status) WHERE Batch_ID = %s",
                (new_qty, new_qty, batch_id)
            )

            # تسجيل الحركة
            self.movement_manager.create_movement_log(
                product_id=product_id,
                movement_type='Return_To_Supplier', # تأكد من وجود هذا النوع في قاعدة البيانات
                qty_change= -qty, 
                unit_used='Unit',
                batch_id=batch_id,
                user_id=user_id,
                notes=f"Retour Fournisseur Avoir #{cn_ref}",
                external_cursor=cursor
            )
            
            return batch_id
        else:
            return None # سيرفع خطأ في الدالة الرئيسية

    def get_all_credit_notes(self):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT cn.*, s.Supplier_Name 
                    FROM Supplier_Credit_Notes cn
                    JOIN Suppliers s ON cn.Supplier_ID = s.Supplier_ID
                    ORDER BY cn.Credit_Date DESC
                """
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching credit notes: {e}")
            return []
        
