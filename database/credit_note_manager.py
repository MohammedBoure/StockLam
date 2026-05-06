# database/managers/credit_note_manager.py

import mysql.connector
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional, Tuple

# استيراد مدير الحركات لتسجيل خروج البضاعة
from .stock_movement_log_manager import StockMovementLogManager
from .system_logger import log_methods 

@log_methods()
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

    def _delete_credit_note_without_stock_restore_legacy(self, credit_note_id):
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
        



    def _insert_credit_note_header(self, cursor, header_data: Dict, user_id: Optional[int] = None) -> int:
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
        return cursor.lastrowid

    def create_credit_note_header(self, header_data: Dict, user_id: Optional[int] = None) -> Tuple[bool, str, Optional[int]]:
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
            credit_note_id = self._insert_credit_note_header(cursor, header_data, user_id)
            conn.commit()
            return True, f"Avoir enregistre avec succes (ID: {credit_note_id})", credit_note_id
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Error creating credit note header: {e}")
            return False, str(e), None
        finally:
            if conn: conn.close()

    def create_credit_note(self, header_data: Dict, items: List[Dict], user_id: Optional[int] = None) -> Tuple[bool, str]:
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)

            # 1. إدخال رأس الإشعار
            note_type = header_data.get('Type', 'Return_Goods')
            credit_note_id = self._insert_credit_note_header(cursor, header_data, user_id)

            # 2. معالجة تفاصيل المنتجات
            for item in items:
                product_id = item['Product_ID']
                qty_return = Decimal(str(item.get('Qty_Returned', 0)))
                lot_number = item.get('Lot_Number')
                
                # استخراج Batch_ID الذي يأتي من الواجهة
                batch_id_from_ui = item.get('Batch_ID')
                
                batch_id = None
                
                # --- خصم المخزون إذا كان "إرجاع بضاعة" ---
                if note_type == 'Return_Goods' and qty_return > 0:
                    batch_id = self._process_stock_return(
                        cursor, product_id, qty_return, lot_number, 
                        user_id, credit_note_id, header_data['Credit_Note_Ref'],
                        batch_id_from_ui # تمرير المعرف الدقيق
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

    def _process_stock_return(self, cursor, product_id, qty, lot_number, user_id, cn_id, cn_ref, specific_batch_id=None):
        """
        البحث عن الباتش وخصم الكمية منه بدقة.
        """
        # إذا تم تمرير Batch_ID، نبحث بدقة تامة (هذا هو الحل)
        if specific_batch_id:
            query_find_batch = """
                SELECT Batch_ID, Quantity_Current 
                FROM Inventory_Batches 
                WHERE Batch_ID = %s AND Product_ID = %s AND Quantity_Current >= %s
                FOR UPDATE
            """
            cursor.execute(query_find_batch, (specific_batch_id, product_id, qty))
        else:
            # بحث احتياطي (الوضع القديم)
            if not lot_number: return None
            query_find_batch = """
                SELECT Batch_ID, Quantity_Current 
                FROM Inventory_Batches 
                WHERE Product_ID = %s AND Lot_Number = %s AND Quantity_Current >= %s
                LIMIT 1
                FOR UPDATE
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
                movement_type='Return_To_Supplier', 
                qty_change= -qty, 
                unit_used='Unit',
                batch_id=batch_id,
                user_id=user_id,
                notes=f"Retour Fournisseur Avoir #{cn_ref}",
                external_cursor=cursor
            )
            
            return batch_id
        else:
            return None
    def get_all_credit_notes(self, limit=100):
        """
        تم التعديل: جلب آخر 100 إشعار فقط بشكل افتراضي لتسريع التحميل الأولي.
        إذا أراد المستخدم المزيد، يجب عليه استخدام البحث بالتاريخ.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                # تم إضافة LIMIT %s لمنع جلب قاعدة البيانات بالكامل
                query = """
                    SELECT cn.*, s.Supplier_Name 
                    FROM Supplier_Credit_Notes cn
                    JOIN Suppliers s ON cn.Supplier_ID = s.Supplier_ID
                    ORDER BY cn.Credit_Date DESC, cn.Credit_Note_ID DESC
                    LIMIT %s
                """
                cursor.execute(query, (limit,))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching credit notes: {e}")
            return []
        
    def delete_credit_note(self, credit_note_id, user_id=None):
        """
        حذف Avoir مع إعادة المخزون إذا كان نوعه إرجاع بضاعة.
        """
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)

            # 1. جلب تفاصيل الـ Avoir قبل الحذف لمعرفة الكميات والباتشات
            cursor.execute("SELECT Type FROM Supplier_Credit_Notes WHERE Credit_Note_ID = %s", (credit_note_id,))
            header = cursor.fetchone()
            if not header:
                return False, "Avoir introuvable."

            if header['Type'] == 'Return_Goods':
                cursor.execute("SELECT * FROM Credit_Note_Details WHERE Credit_Note_ID = %s", (credit_note_id,))
                details = cursor.fetchall()

                # 2. إعادة الكميات للمخزون
                for item in details:
                    if item['Batch_ID'] and item['Qty_Returned'] > 0:
                        # إعادة الكمية للباتش
                        # ملاحظة: نعيد الحالة إلى Available إذا كانت Depleted
                        sql_restore = """
                            UPDATE Inventory_Batches 
                            SET Quantity_Current = Quantity_Current + %s,
                                Status = CASE WHEN Status = 'Depleted' THEN 'Available' ELSE Status END
                            WHERE Batch_ID = %s
                        """
                        cursor.execute(sql_restore, (item['Qty_Returned'], item['Batch_ID']))

                        # تسجيل حركة تصحيحية (Ajustement أو Annulation Retour)
                        self.movement_manager.create_movement_log(
                            product_id=item['Product_ID'],
                            movement_type='Adjustment', # أو نوع مخصص Cancellation
                            qty_change=item['Qty_Returned'], # بالموجب لأننا أعدناها
                            unit_used='Unit',
                            batch_id=item['Batch_ID'],
                            user_id=user_id,
                            notes=f"Annulation Avoir #{credit_note_id}",
                            external_cursor=cursor
                        )

            # 3. حذف التفاصيل والرأس
            cursor.execute("DELETE FROM Credit_Note_Details WHERE Credit_Note_ID = %s", (credit_note_id,))
            cursor.execute("DELETE FROM Supplier_Credit_Notes WHERE Credit_Note_ID = %s", (credit_note_id,))

            conn.commit()
            return True, "Avoir supprimé avec succès (Stock restauré)."

        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Delete Error: {e}")
            return False, str(e)
        finally:
            if conn: conn.close()

    def _restore_stock(self, cursor, batch_id, qty, user_id, reason):
        """إعادة كمية للمخزون وتسجيلها كحركة موجبة"""
        cursor.execute("SELECT Product_ID FROM Inventory_Batches WHERE Batch_ID = %s", (batch_id,))
        batch_row = cursor.fetchone()
        if not batch_row:
            raise ValueError(f"Batch introuvable: {batch_id}")
        product_id = batch_row['Product_ID'] if isinstance(batch_row, dict) else batch_row[0]

        cursor.execute("""
            UPDATE Inventory_Batches 
            SET Quantity_Current = Quantity_Current + %s,
                Status = CASE WHEN Status = 'Depleted' THEN 'Available' ELSE Status END
            WHERE Batch_ID = %s
        """, (qty, batch_id))
        
        # نسجل الحركة كـ +Return_To_Supplier لتظهر كتصحيح موجب
        self.movement_manager.create_movement_log(
            product_id=product_id,
            movement_type='Return_To_Supplier', 
            qty_change=qty, # كمية موجبة
            unit_used='Unit', batch_id=batch_id, user_id=user_id,
            notes=reason, external_cursor=cursor
        )

    def _apply_stock_difference(self, cursor, product_id, batch_id, diff, user_id, ref):
        """
        معالجة الفرق (Delta) في المخزون:
        - إذا كان diff موجباً (+): يعني زدنا الكمية المرجعة -> نخصم المزيد من المخزون.
        - إذا كان diff سالباً (-): يعني أنقصنا الكمية المرجعة -> نعيد الفرق للمخزون.
        """
        if not batch_id: return 

        if diff > 0:
            # زيادة في الإرجاع (خصم إضافي من المخزون)
            # يجب التأكد من توفر الرصيد
            cursor.execute("SELECT Quantity_Current FROM Inventory_Batches WHERE Batch_ID = %s FOR UPDATE", (batch_id,))
            curr = cursor.fetchone()
            if not curr or curr['Quantity_Current'] < diff:
                raise ValueError(f"Stock insuffisant pour augmenter le retour de {diff}")
            
            new_stock = curr['Quantity_Current'] - diff
            cursor.execute("UPDATE Inventory_Batches SET Quantity_Current = %s, Status = IF(%s=0, 'Depleted', Status) WHERE Batch_ID = %s", 
                           (new_stock, new_stock, batch_id))
            
            # تسجيل الفرق بالسالب (خروج إضافي)
            self.movement_manager.create_movement_log(
                product_id=product_id, movement_type='Return_To_Supplier', qty_change=-diff,
                unit_used='Unit', batch_id=batch_id, user_id=user_id,
                notes=f"Modif Avoir #{ref} (Ajout)", external_cursor=cursor
            )

        elif diff < 0:
            # نقص في الإرجاع (إعادة للمخزون)
            restore_qty = abs(diff) 
            self._restore_stock(cursor, batch_id, restore_qty, user_id, f"Modif Avoir #{ref} (Réduction)")

    def _deduct_stock_initial(self, cursor, product_id, qty, lot_number, user_id, ref, specific_batch_id=None):
        """خصم أولي (عند الإنشاء لأول مرة أو التعديل)"""
        if specific_batch_id:
            cursor.execute("""
                SELECT Batch_ID, Quantity_Current FROM Inventory_Batches 
                WHERE Batch_ID = %s AND Product_ID = %s AND Quantity_Current >= %s 
                FOR UPDATE
            """, (specific_batch_id, product_id, qty))
        else:
            cursor.execute("""
                SELECT Batch_ID, Quantity_Current FROM Inventory_Batches 
                WHERE Product_ID = %s AND Lot_Number = %s AND Quantity_Current >= %s 
                LIMIT 1
                FOR UPDATE
            """, (product_id, lot_number, qty))
            
        batch = cursor.fetchone()
        
        if batch:
            batch_id = batch['Batch_ID']
            new_qty = batch['Quantity_Current'] - qty
            cursor.execute("UPDATE Inventory_Batches SET Quantity_Current = %s, Status = IF(%s=0, 'Depleted', Status) WHERE Batch_ID = %s", 
                           (new_qty, new_qty, batch_id))
            
            self.movement_manager.create_movement_log(
                product_id=product_id, movement_type='Return_To_Supplier', qty_change=-qty,
                unit_used='Unit', batch_id=batch_id, user_id=user_id,
                notes=f"Retour Avoir #{ref}", external_cursor=cursor
            )
            return batch_id
        else:
            raise ValueError(f"Stock insuffisant (Lot: {lot_number})")

    def _insert_credit_note_item(self, cursor, cn_id, item, note_type, user_id, ref):
        """مساعد لإدخال سطر جديد تماماً مع خصم المخزون"""
        batch_id = item.get('Batch_ID')
        qty = Decimal(str(item.get('Qty_Returned', 0)))
        
        if note_type == 'Return_Goods' and qty > 0:
            batch_id = self._deduct_stock_initial(cursor, item['Product_ID'], qty, item.get('Lot_Number'), user_id, ref, batch_id)
        
        item['Batch_ID'] = batch_id
        self._insert_detail_row(cursor, cn_id, item)

    def _insert_detail_row(self, cursor, cn_id, item):
        qty = Decimal(str(item.get('Qty_Returned', 0)))
        unit_price = Decimal(str(item.get('Unit_Price', 0)))
        cursor.execute("""
            INSERT INTO Credit_Note_Details
            (Credit_Note_ID, Product_ID, Batch_ID, Lot_Number, Expiry_Date,
             Qty_Returned, Unit_Price, Line_Total)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            cn_id,
            item['Product_ID'],
            item.get('Batch_ID'),
            item.get('Lot_Number'),
            item.get('Expiry_Date'),
            qty,
            unit_price,
            qty * unit_price
        ))

    @staticmethod
    def _credit_note_item_key(item):
        batch_id = item.get('Batch_ID')
        if batch_id:
            return ('batch', int(batch_id))
        return ('product_lot', item.get('Product_ID'), item.get('Lot_Number'))

    def update_credit_note(self, credit_note_id, header_data, new_items, user_id):
        """
        تحديث ذكي يحسب الفرق (Delta) بدلاً من الحذف الكامل وإعادة الإدخال.
        يضمن عدم تضخيم سجل الحركات.
        """
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)

            # 1. جلب النوع القديم للتحقق
            cursor.execute("SELECT Type, Credit_Note_Ref FROM Supplier_Credit_Notes WHERE Credit_Note_ID = %s", (credit_note_id,))
            old_header = cursor.fetchone()
            if not old_header:
                raise ValueError("Avoir introuvable.")
            
            note_type = header_data.get('Type', 'Return_Goods')
            old_note_type = old_header['Type']
            ref = header_data['Credit_Note_Ref']

            # 2. جلب التفاصيل القديمة لمقارنتها
            cursor.execute("SELECT * FROM Credit_Note_Details WHERE Credit_Note_ID = %s", (credit_note_id,))
            old_items_list = cursor.fetchall()
            
            # خريطة للمقارنة: Key = (Product_ID, Lot_Number)
            old_items_map = {}
            for it in old_items_list:
                key = self._credit_note_item_key(it)
                old_items_map[key] = it

            if old_note_type == 'Return_Goods' and note_type != 'Return_Goods':
                for old_item in old_items_list:
                    qty_to_restore = Decimal(str(old_item['Qty_Returned']))
                    if qty_to_restore > 0 and old_item['Batch_ID']:
                        self._restore_stock(cursor, old_item['Batch_ID'], qty_to_restore, user_id, f"Changement type Avoir #{ref}")

            # 3. حذف التفاصيل من الجدول (سنعيد إدخالها لاحقاً، لكن المخزون نعالجه بالفروقات)
            cursor.execute("DELETE FROM Credit_Note_Details WHERE Credit_Note_ID = %s", (credit_note_id,))

            # 4. تحديث رأس الوثيقة (Header)
            sql_update_header = """
                UPDATE Supplier_Credit_Notes 
                SET Supplier_ID=%s, Credit_Note_Ref=%s, Credit_Date=%s, Type=%s, 
                    Total_Amount_HT=%s, Total_TVA=%s, Total_Amount_TTC=%s, Notes=%s
                WHERE Credit_Note_ID=%s
            """
            cursor.execute(sql_update_header, (
                header_data['Supplier_ID'], ref, header_data['Credit_Date'],
                note_type, header_data['Total_Amount_HT'], header_data.get('Total_TVA', 0), header_data['Total_Amount_TTC'],
                header_data.get('Notes', ''), credit_note_id
            ))

            # 5. معالجة العناصر الجديدة وحساب الفروقات
            processed_keys = set()

            for new_item in new_items:
                p_id = new_item['Product_ID']
                lot = new_item.get('Lot_Number')
                new_qty = Decimal(str(new_item.get('Qty_Returned', 0)))
                
                key = self._credit_note_item_key(new_item)
                processed_keys.add(key)
                
                # أ) هل هذا السطر (نفس المنتج واللوت) كان موجوداً؟
                if key in old_items_map and old_note_type == 'Return_Goods' and note_type == 'Return_Goods':
                    old_item = old_items_map[key]
                    old_qty = Decimal(str(old_item['Qty_Returned']))
                    batch_id = old_item['Batch_ID'] # نستخدم نفس الباتش القديم
                    
                    diff = new_qty - old_qty # الفرق: (الجديد - القديم)
                    
                    if diff != 0:
                        # تطبيق الفرق فقط على المخزون
                        self._apply_stock_difference(cursor, p_id, batch_id, diff, user_id, ref)
                    
                    # إدخال السطر الجديد في قاعدة البيانات
                    new_item['Batch_ID'] = batch_id 
                    self._insert_detail_row(cursor, credit_note_id, new_item)

                # ب) سطر جديد كلياً (أو لوت مختلف)
                elif note_type == 'Return_Goods':
                    self._insert_credit_note_item(cursor, credit_note_id, new_item, note_type, user_id, ref)
                else:
                    self._insert_detail_row(cursor, credit_note_id, new_item)

            # 6. معالجة العناصر المحذوفة (كانت موجودة ولم تعد موجودة)
            for key, old_item in old_items_map.items():
                if key not in processed_keys and old_note_type == 'Return_Goods' and note_type == 'Return_Goods':
                    # إعادة الكمية كاملة للمخزون
                    qty_to_restore = Decimal(str(old_item['Qty_Returned']))
                    if qty_to_restore > 0 and old_item['Batch_ID']:
                        self._restore_stock(cursor, old_item['Batch_ID'], qty_to_restore, user_id, f"Suppression ligne Avoir #{ref}")

            conn.commit()
            return True, "Avoir modifié avec succès (Mouvements ajustés)."

        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Update Error: {e}")
            return False, str(e)
        finally:
            if conn: conn.close()

    def get_credit_notes_by_date(self, start_date, end_date):
        """
        جلب الإشعارات (Avoirs) ضمن نطاق زمني محدد فقط.
        هذا يمنع تحميل آلاف السجلات دفعة واحدة ويسرع البرنامج.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT cn.*, s.Supplier_Name 
                    FROM Supplier_Credit_Notes cn
                    JOIN Suppliers s ON cn.Supplier_ID = s.Supplier_ID
                    WHERE cn.Credit_Date BETWEEN %s AND %s
                    ORDER BY cn.Credit_Date DESC, cn.Credit_Note_ID DESC
                """
                cursor.execute(query, (start_date, end_date))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching credit notes by date: {e}")
            return []

    
