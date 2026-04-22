# database/managers/external_transfer_manager.py

import mysql.connector
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Tuple, Optional

# نحتاج StockMovementLogManager لتسجيل الحركات
from .stock_movement_log_manager import StockMovementLogManager
from .system_logger import log_methods 

@log_methods()
class ExternalTransferManager:
    """
    إدارة عمليات التحويل الخارجي للمنتجات (بيع، تبرع، تبادل).
    """

    def __init__(self, db_instance):
        self.db = db_instance
        self.movement_manager = StockMovementLogManager(db_instance)

    # --------------------------------------------------------------------------
    #  Header Operations (Log)
    # --------------------------------------------------------------------------
    def create_transfer_header(self, partner_id: int, transfer_type: str, notes: str, user_id: int) -> Optional[int]:
        """إنشاء رأس وثيقة التحويل (Draft)."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO External_Transfer_Log 
                    (Partner_ID, Transfer_Type, Status, Notes, Created_By, Transaction_Date)
                    VALUES (%s, %s, 'Draft', %s, %s, NOW())
                """
                cursor.execute(query, (partner_id, transfer_type, notes, user_id))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logging.error(f"Error creating transfer header: {e}")
            return None

    def update_transfer_header(self, transfer_id: int, data: Dict) -> bool:
        """تحديث بيانات التحويل (ما دام في حالة Draft)."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    UPDATE External_Transfer_Log 
                    SET Partner_ID = %s, Transfer_Type = %s, Notes = %s, Total_Amount = %s
                    WHERE Transfer_ID = %s AND Status = 'Draft'
                """
                cursor.execute(query, (
                    data['Partner_ID'], data['Transfer_Type'], 
                    data.get('Notes', ''), data.get('Total_Amount', 0), 
                    transfer_id
                ))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error updating transfer {transfer_id}: {e}")
            return False

    def get_all_transfers(self) -> List[Dict]:
        """جلب قائمة التحويلات للعرض."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT t.*, p.Partner_Name, u.Full_Name as Created_By_Name
                    FROM External_Transfer_Log t
                    JOIN External_Partners p ON t.Partner_ID = p.Partner_ID
                    LEFT JOIN Users u ON t.Created_By = u.User_ID
                    ORDER BY t.Transaction_Date DESC
                """
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error getting transfers: {e}")
            return []

    # --------------------------------------------------------------------------
    #  Details Operations (Items)
    # --------------------------------------------------------------------------
    def add_transfer_detail(self, transfer_id: int, product_id: int, batch_id: int, qty: float, price: float, note: str = "") -> bool:
        """
        إضافة منتج للتحويل مع الملاحظة.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                line_total = float(qty) * float(price)
                
                # تم تحديث الاستعلام ليشمل Line_Note
                query = """
                    INSERT INTO External_Transfer_Details 
                    (Transfer_ID, Product_ID, Batch_ID, Qty_Transferred, Unit_Price, Line_Total, Line_Note)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (transfer_id, product_id, batch_id, qty, price, line_total, note))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error adding transfer detail: {e}")
            return False

    def remove_transfer_detail(self, detail_id: int) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM External_Transfer_Details WHERE Detail_ID = %s", (detail_id,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error removing detail {detail_id}: {e}")
            return False

    def get_transfer_details(self, transfer_id: int) -> List[Dict]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT d.*, d.Line_Note, p.Product_Name, p.Is_Billable, -- تمت إضافة هذا الحقل
                        b.Lot_Number, b.Expiry_Date, b.Quantity_Current
                    FROM External_Transfer_Details d
                    JOIN Products_Master p ON d.Product_ID = p.Product_ID
                    JOIN Inventory_Batches b ON d.Batch_ID = b.Batch_ID
                    WHERE d.Transfer_ID = %s
                """
                cursor.execute(query, (transfer_id,))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching transfer details: {e}")
            return []
    # --------------------------------------------------------------------------
    #  Finalization (The Critical Part)
    # --------------------------------------------------------------------------
    def finalize_transfer(self, transfer_id: int, user_id: int) -> Tuple[bool, str]:
        """
        إتمام العملية: خصم المخزون وتسجيل الحركات.
        """
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)

            # 1. جلب معلومات التحويل
            cursor.execute("SELECT * FROM External_Transfer_Log WHERE Transfer_ID = %s", (transfer_id,))
            transfer = cursor.fetchone()
            if not transfer: return False, "Transfert introuvable."
            if transfer['Status'] == 'Completed': return False, "Déjà complété."

            partner_id = transfer['Partner_ID']
            # جلب اسم الشريك للملاحظات
            cursor.execute("SELECT Partner_Name FROM External_Partners WHERE Partner_ID = %s", (partner_id,))
            partner_name = cursor.fetchone()['Partner_Name']

            # 2. جلب التفاصيل
            cursor.execute("SELECT * FROM External_Transfer_Details WHERE Transfer_ID = %s", (transfer_id,))
            details = cursor.fetchall()

            if not details:
                return False, "Aucun article dans le transfert."

            # 3. معالجة كل سطر
            total_amount = 0.0
            
            for item in details:
                batch_id = item['Batch_ID']
                qty_needed = float(item['Qty_Transferred'])
                
                # أ. التحقق من توفر المخزون (وقفل السطر)
                cursor.execute("SELECT Quantity_Current, Product_ID FROM Inventory_Batches WHERE Batch_ID = %s FOR UPDATE", (batch_id,))
                batch = cursor.fetchone()
                
                if not batch:
                    conn.rollback()
                    return False, f"Lot ID {batch_id} introuvable."
                
                current_qty = float(batch['Quantity_Current'])
                
                if current_qty < qty_needed:
                    conn.rollback()
                    return False, f"Stock insuffisant pour le lot {batch_id}. Disponible: {current_qty}, Demandé: {qty_needed}."

                # ب. خصم الكمية
                new_qty = current_qty - qty_needed
                cursor.execute("UPDATE Inventory_Batches SET Quantity_Current = %s WHERE Batch_ID = %s", (new_qty, batch_id))

                # ج. تسجيل حركة المخزون (External_Transfer)
                # ملاحظة: Qty_Change بالسالب لأنها خروج
                self.movement_manager.create_movement_log(
                    product_id=item['Product_ID'],
                    movement_type='External_Transfer',
                    qty_change=Decimal(str(-qty_needed)),
                    unit_used='Unit', # أو جلب الوحدة من المنتج
                    batch_id=batch_id,
                    user_id=user_id,
                    notes=f"Vers: {partner_name} (ID: {transfer_id})",
                    external_cursor=cursor
                )
                
                total_amount += float(item['Line_Total'])

            # 4. تحديث حالة التحويل إلى مكتمل
            cursor.execute("""
                UPDATE External_Transfer_Log 
                SET Status = 'Completed', Total_Amount = %s 
                WHERE Transfer_ID = %s
            """, (total_amount, transfer_id))

            conn.commit()
            return True, "Transfert validé et stock mis à jour."

        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Finalize Transfer Error: {e}")
            return False, f"Erreur technique: {str(e)}"
        finally:
            if conn: conn.close()

    def cancel_transfer(self, transfer_id: int) -> bool:
        """إلغاء التحويل (فقط إذا كان مسودة)."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE External_Transfer_Log SET Status = 'Cancelled' WHERE Transfer_ID = %s AND Status = 'Draft'", (transfer_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Error cancelling transfer: {e}")
            return False
        
    # --------------------------------------------------------------------------
    #  Helper: FIFO Batch Allocation (Allocateur Automatique)
    # --------------------------------------------------------------------------
    def allocate_batches_fifo(self, product_id: int, qty_needed: float) -> Tuple[List[Dict], str]:
        """
        تقوم هذه الدالة بالبحث عن الدفعات المتوفرة للمنتج وترتيبها حسب تاريخ الانتهاء (الأقدم فالأحدث).
        تعيد قائمة بالدفعات والكمية التي يجب أخذها من كل دفعة.
        """
        allocations = []
        remaining_qty = Decimal(str(qty_needed))

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # جلب الدفعات المتوفرة (Available) والتي بها كمية > 0، مرتبة حسب تاريخ الانتهاء
                query = """
                    SELECT Batch_ID, Quantity_Current, Expiry_Date, Lot_Number
                    FROM Inventory_Batches
                    WHERE Product_ID = %s 
                      AND Quantity_Current > 0 
                      AND Status = 'Available'
                    ORDER BY Expiry_Date ASC, Created_At ASC
                """
                cursor.execute(query, (product_id,))
                batches = cursor.fetchall()

                # حساب المجموع المتوفر
                total_available = sum(b['Quantity_Current'] for b in batches)
                if total_available < remaining_qty:
                    return [], f"Stock insuffisant. Disponible: {total_available}, Demandé: {qty_needed}"

                # توزيع الكمية المطلوبة على الدفعات
                for batch in batches:
                    if remaining_qty <= 0:
                        break
                    
                    available_in_batch = Decimal(str(batch['Quantity_Current']))
                    
                    if available_in_batch >= remaining_qty:
                        # هذه الدفعة تكفي لما تبقى
                        allocations.append({
                            'Batch_ID': batch['Batch_ID'],
                            'Qty': float(remaining_qty),
                            'Lot': batch['Lot_Number']
                        })
                        remaining_qty = 0
                    else:
                        # نأخذ كل ما في الدفعة وننتقل للتالية
                        allocations.append({
                            'Batch_ID': batch['Batch_ID'],
                            'Qty': float(available_in_batch),
                            'Lot': batch['Lot_Number']
                        })
                        remaining_qty -= available_in_batch
            
            return allocations, None

        except Exception as e:
            logging.error(f"Allocation Error: {e}")
            return [], str(e)
        
    def get_transfers_filtered(self, start_date, end_date, partner_id=None, status=None):
        """
        جلب التحويلات بناءً على فلاتر لتقليل الحمل على قاعدة البيانات.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                query = """
                    SELECT t.*, p.Partner_Name, p.City
                    FROM External_Transfer_Log t
                    JOIN External_Partners p ON t.Partner_ID = p.Partner_ID
                    WHERE t.Transaction_Date BETWEEN %s AND %s
                """
                params = [start_date, end_date]

                if partner_id:
                    query += " AND t.Partner_ID = %s"
                    params.append(partner_id)
                
                if status and status != "Tous":
                    query += " AND t.Status = %s"
                    params.append(status)
                
                query += " ORDER BY t.Transaction_Date DESC"
                
                cursor.execute(query, params)
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error filtering transfers: {e}")
            return []

    def update_draft_details(self, transfer_id, new_details_list):
        """
        تحديث تفاصيل مسودة: حذف القديم وإدخال الجديد (مع الملاحظات).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # 1. حذف التفاصيل القديمة
                cursor.execute("DELETE FROM External_Transfer_Details WHERE Transfer_ID = %s", (transfer_id,))
                
                # 2. إضافة الجديدة
                for item in new_details_list:
                    # item يجب أن يحتوي على مفتاح 'note' القادم من الواجهة
                    note = item.get('note', '') 
                    
                    query = """
                        INSERT INTO External_Transfer_Details 
                        (Transfer_ID, Product_ID, Batch_ID, Qty_Transferred, Unit_Price, Line_Total, Line_Note)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(query, (
                        transfer_id, 
                        item['product_id'], 
                        item['batch_id'], 
                        item['qty'], 
                        item['price'], 
                        item['total'], 
                        note  # تخزين الملاحظة
                    ))
                
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error updating draft details: {e}")
            return False
            
    def finalize_transfer_with_stock_logic(self, transfer_id: int, user_id: int, new_items: List[Dict]) -> Tuple[bool, str]:
        """
        الدالة السحرية: تقارن بين المخزون الحالي في الوثيقة والطلب الجديد.
        1. إذا كانت الوثيقة جديدة: تخصم الكمية كاملة.
        2. إذا كانت تعديل: تحسب الفرق وتعدل المخزون صعوداً أو نزولاً.
        """
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)

            # 1. جلب البيانات القديمة للوثيقة (إن وجدت)
            cursor.execute("SELECT Status FROM External_Transfer_Log WHERE Transfer_ID = %s", (transfer_id,))
            old_status = cursor.fetchone()
            
            # جلب تفاصيل السطور القديمة المخزنة حالياً في قاعدة البيانات
            cursor.execute("SELECT Batch_ID, Qty_Transferred FROM External_Transfer_Details WHERE Transfer_ID = %s", (transfer_id,))
            old_details = {item['Batch_ID']: float(item['Qty_Transferred']) for item in cursor.fetchall()}

            # 2. إرجاع الكميات القديمة للمخزون مؤقتاً (لإعادة الحساب من الصفر)
            for b_id, q_old in old_details.items():
                cursor.execute("UPDATE Inventory_Batches SET Quantity_Current = Quantity_Current + %s WHERE Batch_ID = %s", (q_old, b_id))

            # 3. معالجة السطور الجديدة والتحقق من التوفر
            total_amount = 0.0
            # حذف التفاصيل القديمة من الجدول الوسيط لإعادة إدخال الجديدة
            cursor.execute("DELETE FROM External_Transfer_Details WHERE Transfer_ID = %s", (transfer_id,))

            for item in new_items:
                b_id = item['batch_id']
                qty_needed = float(item['qty'])
                price = float(item['price'])
                line_total = qty_needed * price
                total_amount += line_total

                # التحقق من المخزون بعد الإرجاع المؤقت
                cursor.execute("SELECT Quantity_Current, Product_ID FROM Inventory_Batches WHERE Batch_ID = %s FOR UPDATE", (b_id,))
                batch = cursor.fetchone()
                
                if not batch or float(batch['Quantity_Current']) < qty_needed:
                    conn.rollback()
                    return False, f"Stock insuffisant pour le lot {b_id}. Max: {batch['Quantity_Current'] if batch else 0}"

                # خصم الكمية الجديدة
                cursor.execute("UPDATE Inventory_Batches SET Quantity_Current = Quantity_Current - %s WHERE Batch_ID = %s", (qty_needed, b_id))

                # إدخال السطر الجديد في التفاصيل
                query_detail = """
                    INSERT INTO External_Transfer_Details 
                    (Transfer_ID, Product_ID, Batch_ID, Qty_Transferred, Unit_Price, Line_Total, Line_Note)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query_detail, (transfer_id, item['product_id'], b_id, qty_needed, price, line_total, item['note']))

                # تسجيل الحركة في الـ Log (اختياري: يمكن تحسينه ليسجل "تعديل" بدلاً من خروج جديد)
                self.movement_manager.create_movement_log(
                    product_id=item['product_id'], movement_type='External_Transfer',
                    qty_change=Decimal(str(-qty_needed)), unit_used='Unit',
                    batch_id=b_id, user_id=user_id, notes=f"Facture #{transfer_id} (Sync Stock)",
                    external_cursor=cursor
                )

            # 4. تحديث الرأس والحالة
            cursor.execute("""
                UPDATE External_Transfer_Log 
                SET Status = 'Completed', Total_Amount = %s 
                WHERE Transfer_ID = %s
            """, (total_amount, transfer_id))

            conn.commit()
            return True, "Success"

        except Exception as e:
            if conn: conn.rollback()
            return False, str(e)
        finally:
            if conn: conn.close()
    
    def delete_transfer_and_restore_stock(self, transfer_id: int):
        """حذف الوثيقة وإرجاع المخزون مع تسجيل الحركة في السجل"""
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)

            # 1. جلب السطور لاستعادة المخزون ومعرفة المستخدم (اختياري)
            cursor.execute("SELECT Product_ID, Batch_ID, Qty_Transferred FROM External_Transfer_Details WHERE Transfer_ID = %s", (transfer_id,))
            items = cursor.fetchall()

            for item in items:
                # إرجاع الكمية
                cursor.execute("UPDATE Inventory_Batches SET Quantity_Current = Quantity_Current + %s WHERE Batch_ID = %s", 
                            (item['Qty_Transferred'], item['Batch_ID']))
                
                # تسجيل حركة استعادة في السجل (Adjustment)
                self.movement_manager.create_movement_log(
                    product_id=item['Product_ID'], movement_type='Adjustment',
                    qty_change=Decimal(str(item['Qty_Transferred'])), unit_used='Unit',
                    batch_id=item['Batch_ID'], user_id=None,
                    notes=f"Restoration suite à suppression BL #{transfer_id}",
                    external_cursor=cursor
                )

            # 2. حذف الفاتورة
            cursor.execute("DELETE FROM External_Transfer_Log WHERE Transfer_ID = %s", (transfer_id,))
            
            conn.commit()
            return True, "Supprimé et stock restauré."
        except Exception as e:
            if conn: conn.rollback()
            return False, str(e)
        finally:
            if conn: conn.close()

    def save_and_sync_stock(self, transfer_id, partner_id, new_items, user_id):
        """
        الدالة المصححة بالكامل:
        1. تدعم التعديل (إرجاع المخزون القديم وتسجيل حركة تعديل).
        2. تدعم الإضافة (خصم المخزون وتسجيل حركة External_Transfer).
        3. تضمن سلامة البيانات (Transaction).
        """
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)

            # جلب اسم الشريك للملاحظات في السجل
            cursor.execute("SELECT Partner_Name FROM External_Partners WHERE Partner_ID = %s", (partner_id,))
            partner_row = cursor.fetchone()
            partner_name = partner_row['Partner_Name'] if partner_row else "Partenaire Inconnu"

            # --- المرحلة 1: معالجة البيانات القديمة (في حالة التعديل) ---
            if transfer_id:
                cursor.execute("SELECT Product_ID, Batch_ID, Qty_Transferred FROM External_Transfer_Details WHERE Transfer_ID = %s", (transfer_id,))
                old_items = cursor.fetchall()
                for old in old_items:
                    # إرجاع الكمية للمخزن
                    cursor.execute("UPDATE Inventory_Batches SET Quantity_Current = Quantity_Current + %s WHERE Batch_ID = %s",
                                (old['Qty_Transferred'], old['Batch_ID']))
                    # تسجيل حركة "إرجاع" في السجل (Adjustment)
                    self.movement_manager.create_movement_log(
                        product_id=old['Product_ID'], movement_type='Adjustment',
                        qty_change=Decimal(str(old['Qty_Transferred'])), unit_used='Unit',
                        batch_id=old['Batch_ID'], user_id=user_id,
                        notes=f"Retour suite modification BL #{transfer_id}",
                        external_cursor=cursor
                    )
                cursor.execute("DELETE FROM External_Transfer_Details WHERE Transfer_ID = %s", (transfer_id,))
            else:
                # إنشاء رأس جديد
                cursor.execute("INSERT INTO External_Transfer_Log (Partner_ID, Status, Created_By, Transaction_Date) VALUES (%s, 'Draft', %s, NOW())", 
                            (partner_id, user_id))
                transfer_id = cursor.lastrowid

            # --- المرحلة 2: معالجة العناصر الجديدة وخصم المخزون ---
            grand_total = 0.0
            for item in new_items:
                qty = float(item['qty'])
                price = float(item['price'])
                line_total = qty * price
                grand_total += line_total
                
                # قفل السطر للفحص (FOR UPDATE)
                cursor.execute("SELECT Quantity_Current FROM Inventory_Batches WHERE Batch_ID = %s FOR UPDATE", (item['batch_id'],))
                res = cursor.fetchone()
                if not res or res['Quantity_Current'] < qty:
                    conn.rollback()
                    return False, f"Stock insuffisant pour le lot {item['batch_id']}"

                # خصم المخزون
                cursor.execute("UPDATE Inventory_Batches SET Quantity_Current = Quantity_Current - %s WHERE Batch_ID = %s",
                            (qty, item['batch_id']))
                
                # *** تسجيل حركة خروج بـ External_Transfer (هام جداً) ***
                self.movement_manager.create_movement_log(
                    product_id=item['product_id'], movement_type='External_Transfer',
                    qty_change=Decimal(str(-qty)), # القيمة سالبة لأنها خروج
                    unit_used='Unit',
                    batch_id=item['batch_id'], user_id=user_id,
                    notes=f"Sortie vers {partner_name} (BL #{transfer_id})",
                    external_cursor=cursor
                )

                # تسجيل تفاصيل الفاتورة
                cursor.execute("""
                    INSERT INTO External_Transfer_Details (Transfer_ID, Product_ID, Batch_ID, Qty_Transferred, Unit_Price, Line_Total, Line_Note)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (transfer_id, item['product_id'], item['batch_id'], qty, price, line_total, item['note']))

            # تحديث حالة الرأس والمجموع
            cursor.execute("UPDATE External_Transfer_Log SET Status='Completed', Total_Amount=%s, Partner_ID=%s WHERE Transfer_ID=%s",
                        (grand_total, partner_id, transfer_id))

            conn.commit()
            return True, "Enregistré avec succès."
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Save & Sync Error: {e}")
            return False, str(e)
        finally:
            if conn: conn.close()

    def get_transfer_by_id(self, transfer_id: int) -> Optional[Dict]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM External_Transfer_Log WHERE Transfer_ID = %s"
                cursor.execute(query, (transfer_id,))
                return cursor.fetchone()
        except Exception as e:
            logging.error(f"Error getting transfer header {transfer_id}: {e}")
            return None