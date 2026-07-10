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

    def save_transfer_header_only(self, transfer_id, partner_id, transaction_date, user_id, transfer_type='Outbound'):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                if transfer_id:
                    cursor.execute(
                        "SELECT Partner_ID, IFNULL(Transfer_Type, 'Outbound') AS Transfer_Type FROM External_Transfer_Log WHERE Transfer_ID = %s",
                        (transfer_id,)
                    )
                    current_header = cursor.fetchone()
                    if current_header is None:
                        return False, "Transaction introuvable.", transfer_id
                    if current_header['Transfer_Type'] == 'Return' and int(current_header['Partner_ID']) != int(partner_id):
                        return False, "Le partenaire d'un bon de retour ne peut pas etre change.", transfer_id

                    cursor.execute(
                        """
                        UPDATE External_Transfer_Log
                        SET Partner_ID = %s, Transaction_Date = %s, Transfer_Type = %s
                        WHERE Transfer_ID = %s
                        """,
                        (partner_id, transaction_date, transfer_type, transfer_id)
                    )
                    conn.commit()
                    return True, "En-tete enregistre.", transfer_id

                cursor.execute(
                    """
                    INSERT INTO External_Transfer_Log
                    (Partner_ID, Transfer_Type, Status, Created_By, Transaction_Date)
                    VALUES (%s, %s, 'Draft', %s, %s)
                    """,
                    (partner_id, transfer_type, user_id, transaction_date)
                )
                conn.commit()
                return True, "En-tete enregistre.", cursor.lastrowid
        except Exception as e:
            logging.error(f"Error saving transfer header only: {e}")
            return False, str(e), transfer_id

    def get_all_transfers(self) -> List[Dict]:
        """جلب قائمة التحويلات للعرض."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT t.*, IFNULL(t.Transfer_Type, 'Outbound') as Transfer_Type_Fixed, p.Partner_Name, u.Full_Name as Created_By_Name
                    FROM External_Transfer_Log t
                    JOIN External_Partners p ON t.Partner_ID = p.Partner_ID
                    LEFT JOIN Users u ON t.Created_By = u.User_ID
                    ORDER BY t.Transaction_Date DESC
                """
                cursor.execute(query)
                transfers = cursor.fetchall()
                self.apply_display_references(transfers)
                return transfers
        except Exception as e:
            logging.error(f"Error getting transfers: {e}")
            return []


    def _get_transfer_year(self, transaction_date) -> int:
        if hasattr(transaction_date, 'year'):
            return int(transaction_date.year)

        raw_date = str(transaction_date or "")
        if "-" in raw_date:
            try:
                return int(raw_date.split("-")[0])
            except (TypeError, ValueError):
                pass
        return datetime.now().year

    def get_return_sequence_number(self, transfer_id: int, transaction_date=None) -> int:
        """Return BR numbering is independent from BL IDs and restarts every year."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)

                if transaction_date is None:
                    cursor.execute(
                        "SELECT Transaction_Date FROM External_Transfer_Log WHERE Transfer_ID = %s",
                        (transfer_id,)
                    )
                    row = cursor.fetchone()
                    if row:
                        transaction_date = row.get('Transaction_Date')

                year = self._get_transfer_year(transaction_date)
                start_date = f"{year}-01-01 00:00:00"
                end_date = f"{year + 1}-01-01 00:00:00"
                cursor.execute(
                    """
                    SELECT COUNT(*) AS Seq
                    FROM External_Transfer_Log
                    WHERE IFNULL(Transfer_Type, 'Outbound') = 'Return'
                      AND Transaction_Date >= %s
                      AND Transaction_Date < %s
                      AND (
                            Transaction_Date < %s
                            OR (Transaction_Date = %s AND Transfer_ID <= %s)
                      )
                    """,
                    (start_date, end_date, transaction_date, transaction_date, transfer_id)
                )
                row = cursor.fetchone()
                return int((row or {}).get('Seq') or 1)
        except Exception as e:
            logging.error(f"Error getting BR sequence for transfer {transfer_id}: {e}")
            return int(transfer_id)

    def format_transfer_reference(self, transfer: Dict) -> str:
        transfer_id = int(transfer.get('Transfer_ID'))
        transaction_date = transfer.get('Transaction_Date')
        transfer_type = transfer.get('Transfer_Type') or transfer.get('Transfer_Type_Fixed') or 'Outbound'
        year = self._get_transfer_year(transaction_date)

        if transfer_type == 'Return':
            seq = transfer.get('Return_Sequence')
            if seq is None:
                seq = self.get_return_sequence_number(transfer_id, transaction_date)
            return f"{year}/{int(seq):02d}"

        return f"{year}/{transfer_id:03d}"

    def apply_display_references(self, transfers: List[Dict]) -> None:
        for transfer in transfers:
            try:
                transfer['Display_Ref'] = self.format_transfer_reference(transfer)
            except Exception as e:
                logging.error(f"Error formatting transfer reference: {e}")
                transfer['Display_Ref'] = str(transfer.get('Transfer_ID', ''))

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
                transfers = cursor.fetchall()
                self.apply_display_references(transfers)
                return transfers
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

            # 1. جلب معلومات الوثيقة لمعرفة نوعها
            cursor.execute("SELECT Transfer_Type FROM External_Transfer_Log WHERE Transfer_ID = %s", (transfer_id,))
            transfer_row = cursor.fetchone()
            if not transfer_row:
                return False, "Transfert introuvable."
            transfer_type = transfer_row['Transfer_Type'] or 'Outbound'

            # 2. جلب السطور لاستعادة المخزون ومعرفة المستخدم
            cursor.execute("SELECT Product_ID, Batch_ID, Qty_Transferred FROM External_Transfer_Details WHERE Transfer_ID = %s", (transfer_id,))
            items = cursor.fetchall()

            for item in items:
                if transfer_type == 'Return':
                    # إلغاء إرجاع: نخصم من المخزون
                    cursor.execute("UPDATE Inventory_Batches SET Quantity_Current = Quantity_Current - %s WHERE Batch_ID = %s",
                                (item['Qty_Transferred'], item['Batch_ID']))
                    mov_note = f"Annulation de retour suite à suppression BR #{transfer_id}"
                    qty_c = Decimal(str(-item['Qty_Transferred']))
                else:
                    # إلغاء إرسال: نرجع للمخزون
                    cursor.execute("UPDATE Inventory_Batches SET Quantity_Current = Quantity_Current + %s WHERE Batch_ID = %s",
                                (item['Qty_Transferred'], item['Batch_ID']))
                    mov_note = f"Restoration suite à suppression BL #{transfer_id}"
                    qty_c = Decimal(str(item['Qty_Transferred']))

                # تسجيل حركة استعادة في السجل (Adjustment)
                self.movement_manager.create_movement_log(
                    product_id=item['Product_ID'], movement_type='Adjustment',
                    qty_change=qty_c, unit_used='Unit',
                    batch_id=item['Batch_ID'], user_id=None,
                    notes=mov_note,
                    external_cursor=cursor
                )

            # 3. حذف الفاتورة
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
        الدالة الذكية (Delta Logic):
        تحسب الفرق بين الكمية القديمة والجديدة وتسجل حركة المخزون للفرق فقط،
        مما يحافظ على نظافة ودقة سجل الحركات (Stock Movement Log).
        """
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)

            # 1. جلب اسم الشريك للملاحظات
            cursor.execute("SELECT Partner_Name FROM External_Partners WHERE Partner_ID = %s", (partner_id,))
            partner_row = cursor.fetchone()
            partner_name = partner_row['Partner_Name'] if partner_row else "Partenaire Inconnu"

            # 2. إعداد وتحضير البيانات القديمة
            old_items_dict = {}
            if transfer_id:
                cursor.execute("SELECT Detail_ID, Product_ID, Batch_ID, Qty_Transferred, Unit_Price, Line_Note FROM External_Transfer_Details WHERE Transfer_ID = %s", (transfer_id,))
                for row in cursor.fetchall():
                    old_items_dict[row['Batch_ID']] = row

                # تحديث رأس الوثيقة
                cursor.execute("UPDATE External_Transfer_Log SET Partner_ID = %s WHERE Transfer_ID = %s", (partner_id, transfer_id))
            else:
                cursor.execute("INSERT INTO External_Transfer_Log (Partner_ID, Status, Created_By, Transaction_Date) VALUES (%s, 'Draft', %s, NOW())", (partner_id, user_id))
                transfer_id = cursor.lastrowid

            grand_total = 0.0
            new_batch_ids = [int(item['batch_id']) for item in new_items]

            # 3. معالجة المنتجات التي تم حذفها من الفاتورة المعدلة (إرجاع كلي)
            for old_batch_id, old_data in old_items_dict.items():
                if old_batch_id not in new_batch_ids:
                    qty_to_restore = float(old_data['Qty_Transferred'])
                    # إرجاع للمخزون
                    cursor.execute("UPDATE Inventory_Batches SET Quantity_Current = Quantity_Current + %s WHERE Batch_ID = %s", (qty_to_restore, old_batch_id))
                    # تسجيل حركة إرجاع
                    self.movement_manager.create_movement_log(
                        product_id=old_data['Product_ID'], movement_type='Adjustment',
                        qty_change=Decimal(str(qty_to_restore)), unit_used='Unit',
                        batch_id=old_batch_id, user_id=user_id,
                        notes=f"Article retiré suite modification BL #{transfer_id}",
                        external_cursor=cursor
                    )
                    # حذف السطر
                    cursor.execute("DELETE FROM External_Transfer_Details WHERE Detail_ID = %s", (old_data['Detail_ID'],))

            # 4. معالجة المنتجات الجديدة والمعدلة
            for item in new_items:
                b_id = int(item['batch_id'])
                p_id = int(item['product_id'])
                new_qty = float(item['qty'])
                price = float(item['price'])
                line_total = new_qty * price
                grand_total += line_total
                note = item.get('note', '')

                if b_id in old_items_dict:
                    # ====== منتج موجود مسبقاً (تحديث الكمية والفرق) ======
                    old_data = old_items_dict[b_id]
                    old_qty = float(old_data['Qty_Transferred'])
                    delta_qty = new_qty - old_qty  # حساب الفرق

                    if abs(delta_qty) > 0.0001: # إذا تغيرت الكمية فعلاً
                        # التأكد من المخزون إذا كنا سنسحب المزيد
                        if delta_qty > 0:
                            cursor.execute("SELECT Quantity_Current FROM Inventory_Batches WHERE Batch_ID = %s FOR UPDATE", (b_id,))
                            res = cursor.fetchone()
                            if not res or float(res['Quantity_Current']) < delta_qty:
                                conn.rollback()
                                return False, f"Stock insuffisant pour le lot {b_id}."

                        # تحديث المخزون (بالفرق فقط)
                        cursor.execute("UPDATE Inventory_Batches SET Quantity_Current = Quantity_Current - %s WHERE Batch_ID = %s", (delta_qty, b_id))

                        # تحديد نوع الحركة بناءً على التغيير (+ أو -)
                        mov_type = 'External_Transfer' if delta_qty > 0 else 'Adjustment'
                        mov_note = f"Ajout suppl. BL #{transfer_id}" if delta_qty > 0 else f"Retour partiel BL #{transfer_id}"

                        # تسجيل الحركة للكمية المضافة/المنقوصة فقط!
                        self.movement_manager.create_movement_log(
                            product_id=p_id, movement_type=mov_type,
                            qty_change=Decimal(str(-delta_qty)), unit_used='Unit',
                            batch_id=b_id, user_id=user_id,
                            notes=mov_note, external_cursor=cursor
                        )

                    # تحديث السطر في تفاصيل الفاتورة (السعر والملاحظة والكمية)
                    cursor.execute("""
                        UPDATE External_Transfer_Details
                        SET Qty_Transferred = %s, Unit_Price = %s, Line_Total = %s, Line_Note = %s
                        WHERE Detail_ID = %s
                    """, (new_qty, price, line_total, note, old_data['Detail_ID']))

                else:
                    # ====== منتج جديد كلياً تمت إضافته للفاتورة ======
                    cursor.execute("SELECT Quantity_Current FROM Inventory_Batches WHERE Batch_ID = %s FOR UPDATE", (b_id,))
                    res = cursor.fetchone()
                    if not res or float(res['Quantity_Current']) < new_qty:
                        conn.rollback()
                        return False, f"Stock insuffisant pour le lot {b_id}."

                    cursor.execute("UPDATE Inventory_Batches SET Quantity_Current = Quantity_Current - %s WHERE Batch_ID = %s", (new_qty, b_id))

                    self.movement_manager.create_movement_log(
                        product_id=p_id, movement_type='External_Transfer',
                        qty_change=Decimal(str(-new_qty)), unit_used='Unit',
                        batch_id=b_id, user_id=user_id,
                        notes=f"Sortie vers {partner_name} (BL #{transfer_id})",
                        external_cursor=cursor
                    )

                    cursor.execute("""
                        INSERT INTO External_Transfer_Details (Transfer_ID, Product_ID, Batch_ID, Qty_Transferred, Unit_Price, Line_Total, Line_Note)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (transfer_id, p_id, b_id, new_qty, price, line_total, note))

            # 5. إنهاء وإغلاق
            cursor.execute("UPDATE External_Transfer_Log SET Status='Completed', Total_Amount=%s, Partner_ID=%s WHERE Transfer_ID=%s", (grand_total, partner_id, transfer_id))

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
                transfer = cursor.fetchone()
                if transfer:
                    transfer['Display_Ref'] = self.format_transfer_reference(transfer)
                return transfer
        except Exception as e:
            logging.error(f"Error getting transfer header {transfer_id}: {e}")
            return None

    def get_returnable_batches_for_partner(self, partner_id: int, exclude_return_transfer_id: Optional[int] = None) -> List[Dict]:
        """
        يتم حساب الكميات التي يمكن إرجاعها بناءً على ما تم إرساله وطرح ما تم إرجاعه مسبقاً.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT
                        d.Product_ID,
                        d.Batch_ID,
                        b.Lot_Number,
                        p.Product_Name,
                        b.Expiry_Date,
                        b.Location_ID,
                        b.Internal_Barcode,
                        p.Barcode,
                        b.Quantity_Current,
                        SUM(CASE WHEN IFNULL(t.Transfer_Type, 'Outbound') != 'Return' THEN d.Qty_Transferred ELSE 0 END) as Total_Sent,
                        SUM(CASE WHEN t.Transfer_Type = 'Return' AND (%s IS NULL OR t.Transfer_ID <> %s) THEN d.Qty_Transferred ELSE 0 END) as Total_Returned
                    FROM External_Transfer_Details d
                    JOIN External_Transfer_Log t ON d.Transfer_ID = t.Transfer_ID
                    JOIN Inventory_Batches b ON d.Batch_ID = b.Batch_ID
                    JOIN Products_Master p ON d.Product_ID = p.Product_ID
                    WHERE t.Partner_ID = %s AND t.Status = 'Completed'
                    GROUP BY d.Product_ID, d.Batch_ID, b.Lot_Number, p.Product_Name, b.Expiry_Date, b.Location_ID, b.Internal_Barcode, p.Barcode, b.Quantity_Current
                    HAVING (Total_Sent - Total_Returned) > 0
                """
                cursor.execute(query, (exclude_return_transfer_id, exclude_return_transfer_id, partner_id))
                results = cursor.fetchall()

                # إعداد النتيجة لتشبه الكاش العادي لكن مع حقل Available_To_Return
                for r in results:
                    r['Available_To_Return'] = r['Total_Sent'] - r['Total_Returned']
                return results
        except Exception as e:
            logging.error(f"Error get_returnable_batches_for_partner: {e}")
            return []

    def _get_returnable_quantities_for_partner(self, cursor, partner_id: int, batch_ids: List[int], exclude_return_transfer_id: Optional[int] = None) -> Dict[int, float]:
        if not batch_ids:
            return {}

        placeholders = ", ".join(["%s"] * len(batch_ids))
        query = f"""
            SELECT
                d.Batch_ID,
                SUM(CASE WHEN IFNULL(t.Transfer_Type, 'Outbound') != 'Return' THEN d.Qty_Transferred ELSE 0 END) as Total_Sent,
                SUM(CASE WHEN t.Transfer_Type = 'Return' AND (%s IS NULL OR t.Transfer_ID <> %s) THEN d.Qty_Transferred ELSE 0 END) as Total_Returned
            FROM External_Transfer_Details d
            JOIN External_Transfer_Log t ON d.Transfer_ID = t.Transfer_ID
            WHERE t.Partner_ID = %s
              AND t.Status = 'Completed'
              AND d.Batch_ID IN ({placeholders})
            GROUP BY d.Batch_ID
        """
        params = [exclude_return_transfer_id, exclude_return_transfer_id, partner_id] + batch_ids
        cursor.execute(query, params)

        quantities = {}
        for row in cursor.fetchall():
            sent = float(row.get('Total_Sent') or 0)
            returned = float(row.get('Total_Returned') or 0)
            quantities[int(row['Batch_ID'])] = sent - returned
        return quantities

    def save_and_sync_return_stock(self, transfer_id, partner_id, new_items, user_id):
        """
        الدالة الخاصة بحفظ وتحديث المخزون لمرتجعات الشركاء (Bon de Retour).
        نفس فكرة Delta Logic لكن بالعكس (الإرجاع يزيد المخزون).
        """
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT Partner_Name FROM External_Partners WHERE Partner_ID = %s", (partner_id,))
            partner_row = cursor.fetchone()
            partner_name = partner_row['Partner_Name'] if partner_row else "Partenaire Inconnu"

            old_items_dict = {}
            if transfer_id:
                cursor.execute("SELECT Partner_ID, IFNULL(Transfer_Type, 'Outbound') AS Transfer_Type FROM External_Transfer_Log WHERE Transfer_ID = %s", (transfer_id,))
                header_row = cursor.fetchone()
                if not header_row:
                    conn.rollback()
                    return False, "Bon de retour introuvable."
                if header_row['Transfer_Type'] == 'Return' and int(header_row['Partner_ID']) != int(partner_id):
                    conn.rollback()
                    return False, "Le partenaire d'un bon de retour ne peut pas etre change."

                cursor.execute("SELECT Detail_ID, Product_ID, Batch_ID, Qty_Transferred, Unit_Price, Line_Note FROM External_Transfer_Details WHERE Transfer_ID = %s", (transfer_id,))
                for row in cursor.fetchall():
                    old_items_dict[row['Batch_ID']] = row

                cursor.execute("UPDATE External_Transfer_Log SET Partner_ID = %s, Transfer_Type = 'Return' WHERE Transfer_ID = %s", (partner_id, transfer_id))
            else:
                cursor.execute("INSERT INTO External_Transfer_Log (Partner_ID, Transfer_Type, Status, Created_By, Transaction_Date) VALUES (%s, 'Return', 'Draft', %s, NOW())", (partner_id, user_id))
                transfer_id = cursor.lastrowid

            grand_total = 0.0
            new_batch_ids = [int(item['batch_id']) for item in new_items]
            requested_by_batch = {}
            for item in new_items:
                b_id = int(item['batch_id'])
                requested_by_batch[b_id] = requested_by_batch.get(b_id, 0.0) + float(item['qty'])

            allowed_by_batch = self._get_returnable_quantities_for_partner(
                cursor, partner_id, list(requested_by_batch.keys()), exclude_return_transfer_id=transfer_id
            )
            for b_id, requested_qty in requested_by_batch.items():
                allowed_qty = float(allowed_by_batch.get(b_id, 0.0))
                if requested_qty > allowed_qty + 0.0001:
                    conn.rollback()
                    return False, f"Le lot {b_id} n'est pas disponible pour ce partenaire. Max retour: {allowed_qty:g}."


            for old_batch_id, old_data in old_items_dict.items():
                if old_batch_id not in new_batch_ids:
                    qty_to_reverse = float(old_data['Qty_Transferred'])
                    # تراجع عن إرجاع: نخصم المخزون
                    cursor.execute("UPDATE Inventory_Batches SET Quantity_Current = Quantity_Current - %s WHERE Batch_ID = %s", (qty_to_reverse, old_batch_id))
                    self.movement_manager.create_movement_log(
                        product_id=old_data['Product_ID'], movement_type='Adjustment',
                        qty_change=Decimal(str(-qty_to_reverse)), unit_used='Unit',
                        batch_id=old_batch_id, user_id=user_id,
                        notes=f"Annulation retour suite modification BR #{transfer_id}",
                        external_cursor=cursor
                    )
                    cursor.execute("DELETE FROM External_Transfer_Details WHERE Detail_ID = %s", (old_data['Detail_ID'],))

            for item in new_items:
                b_id = int(item['batch_id'])
                p_id = int(item['product_id'])
                new_qty = float(item['qty'])
                price = float(item['price'])
                line_total = new_qty * price
                grand_total += line_total
                note = item.get('note', '')

                if b_id in old_items_dict:
                    old_data = old_items_dict[b_id]
                    old_qty = float(old_data['Qty_Transferred'])
                    delta_qty = new_qty - old_qty

                    if abs(delta_qty) > 0.0001:
                        # التغيير: نزيد المخزون بالفرق
                        cursor.execute("UPDATE Inventory_Batches SET Quantity_Current = Quantity_Current + %s WHERE Batch_ID = %s", (delta_qty, b_id))

                        mov_type = 'Transfer_Return' if delta_qty > 0 else 'Adjustment'
                        mov_note = f"Retour suppl. BR #{transfer_id}" if delta_qty > 0 else f"Annulation partiel retour BR #{transfer_id}"

                        self.movement_manager.create_movement_log(
                            product_id=p_id, movement_type=mov_type,
                            qty_change=Decimal(str(delta_qty)), unit_used='Unit',
                            batch_id=b_id, user_id=user_id,
                            notes=mov_note, external_cursor=cursor
                        )

                    cursor.execute("""
                        UPDATE External_Transfer_Details
                        SET Qty_Transferred = %s, Unit_Price = %s, Line_Total = %s, Line_Note = %s
                        WHERE Detail_ID = %s
                    """, (new_qty, price, line_total, note, old_data['Detail_ID']))

                else:
                    # منتج يتم إرجاعه لأول مرة في هذا الوصل
                    cursor.execute("UPDATE Inventory_Batches SET Quantity_Current = Quantity_Current + %s WHERE Batch_ID = %s", (new_qty, b_id))

                    self.movement_manager.create_movement_log(
                        product_id=p_id, movement_type='Transfer_Return',
                        qty_change=Decimal(str(new_qty)), unit_used='Unit',
                        batch_id=b_id, user_id=user_id,
                        notes=f"Retour de {partner_name} (BR #{transfer_id})",
                        external_cursor=cursor
                    )

                    cursor.execute("""
                        INSERT INTO External_Transfer_Details (Transfer_ID, Product_ID, Batch_ID, Qty_Transferred, Unit_Price, Line_Total, Line_Note)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (transfer_id, p_id, b_id, new_qty, price, line_total, note))

            cursor.execute("UPDATE External_Transfer_Log SET Status='Completed', Total_Amount=%s, Partner_ID=%s WHERE Transfer_ID=%s", (grand_total, partner_id, transfer_id))

            conn.commit()
            return True, "Enregistré avec succès."
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Save & Sync Return Error: {e}")
            return False, str(e)
        finally:
            if conn: conn.close()
