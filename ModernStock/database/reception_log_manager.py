# database/managers/reception_log_manager.py

import mysql.connector
import logging
from datetime import datetime
from typing import List, Dict, Optional, Union, Tuple
from decimal import Decimal

from .inventory_batch_manager import InventoryBatchManager
from .stock_movement_log_manager import StockMovementLogManager
from .system_logger import log_methods 

@log_methods()
class ReceptionLogManager:
    """
    إدارة عمليات جدول سجلات الاستلام (Reception_Log) وعمليات الاستلام المخزني.
    """

    def __init__(self, db_instance):
        self.db = db_instance
        self.stock_movement_log = StockMovementLogManager(db_instance)

    def create_new_reception_header(self, header_data: Dict) -> Optional[int]:
        """
        إنشاء سجل رأس استقبال جديد مع معالجة التكرار.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # التعامل مع القيم الفارغة كنصوص فارغة أو NULL حسب تصميم قاعدة البيانات
                inv_ref = header_data.get('Supplier_Invoice_Ref')
                bl_ref = header_data.get('Supplier_BL_Ref')
                
                # إذا كانت فارغة تماماً، نحولها لـ None لتفادي مشكلة السلاسل الفارغة مع القيد الفريد (Unique Key)
                if not inv_ref: inv_ref = None
                if not bl_ref: bl_ref = None

                query = """
                    INSERT INTO Reception_Log 
                    (PO_ID, Supplier_ID, Supplier_Invoice_Ref, Supplier_BL_Ref, 
                     Reception_Date, Invoice_Total_HT, Invoice_Total_TVA, 
                     Invoice_Total_TTC, Total_Discount, Received_By, Status) 
                    VALUES (%s, %s, %s, %s, %s, 0, 0, 0, 0, %s, 'Pending Audit')
                """
                
                params = (
                    header_data.get('PO_ID'),
                    header_data.get('Supplier_ID'),
                    inv_ref,
                    bl_ref,
                    header_data.get('Reception_Date'),
                    header_data.get('Created_By')
                )
                cursor.execute(query, params)
                conn.commit()
                return cursor.lastrowid

        except mysql.connector.Error as e:
            # معالجة الخطأ 1062 (Duplicate entry)
            if e.errno == 1062:
                logging.warning(f"Tentative de création de doublon (Facture/BL): {e}")
                return None # نرجع None لكي تفهم الواجهة أن هناك مشكلة تكرار
            else:
                logging.error(f"Error creating reception header: {e}")
                raise e # نعيد رفع الأخطاء الأخرى ليراها المطور

    def update_reception_header_info(self, br_id: int, data: Dict) -> bool:
        """تحديث المعلومات الوصفية للفاتورة (الرقم، التاريخ...)."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                updates = []
                params = []
                
                if 'Supplier_Invoice_Ref' in data:
                    updates.append("Supplier_Invoice_Ref = %s")
                    params.append(data['Supplier_Invoice_Ref'])
                
                if 'Supplier_BL_Ref' in data:
                    updates.append("Supplier_BL_Ref = %s")
                    params.append(data['Supplier_BL_Ref'])
                    
                if 'Reception_Date' in data:
                    updates.append("Reception_Date = %s")
                    params.append(data['Reception_Date'])

                if not updates: return True
                
                params.append(br_id)
                query = f"UPDATE Reception_Log SET {', '.join(updates)} WHERE BR_ID = %s"
                cursor.execute(query, tuple(params))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error updating header info: {e}")
            return False

    def _recalculate_reception_totals(self, br_id: int):
        """
        إعادة حساب المجاميع المالية للفاتورة وتحديث حالة أمر الشراء (PO) المرتبط.
        [FIX]: يمنع إعادة الحالة إلى Partial إذا كانت Completed بالفعل.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # 1. جلب PO_ID المرتبط بهذا الاستلام
                cursor.execute("SELECT PO_ID FROM Reception_Log WHERE BR_ID = %s", (br_id,))
                res = cursor.fetchone()
                po_id = res['PO_ID'] if res else None

                # 2. حساب مجاميع الفاتورة (BR)
                query = """
                    SELECT Quantity_Initial, Unit_Price_Received, Tax_Rate_Percent, Discount_Percent
                    FROM Inventory_Batches 
                    WHERE BR_ID = %s AND Quantity_Initial > 0
                """
                cursor.execute(query, (br_id,))
                batches = cursor.fetchall()

                t_ht, t_tva, t_disc = 0.0, 0.0, 0.0
                
                for b in batches:
                    qty = float(b['Quantity_Initial'] or 0)
                    price = float(b['Unit_Price_Received'] or 0)
                    tax_rate = float(b['Tax_Rate_Percent'] or 0) / 100.0
                    disc_rate = float(b['Discount_Percent'] or 0) / 100.0
                    
                    line_ht = qty * price
                    line_disc = line_ht * disc_rate
                    line_net_ht = line_ht - line_disc
                    line_tva = line_net_ht * tax_rate
                    
                    t_ht += line_ht
                    t_disc += line_disc
                    t_tva += line_tva

                t_ttc = (t_ht - t_disc) + t_tva

                # 3. تحديث رأس الفاتورة (BR)
                update_query = """
                    UPDATE Reception_Log 
                    SET Invoice_Total_HT = %s, Invoice_Total_TVA = %s, 
                        Invoice_Total_TTC = %s, Total_Discount = %s,
                        Status = 'Completed'
                    WHERE BR_ID = %s
                """
                cursor.execute(update_query, (t_ht, t_tva, t_ttc, t_disc, br_id))
                
                # -------------------------------------------------------------
                # 4. تحديث حالة الـ PO - (المنطق المصحح)
                # -------------------------------------------------------------
                if po_id:
                    # أ) جلب الحالة الحالية أولاً
                    cursor.execute("SELECT Status FROM Purchase_Orders WHERE PO_ID = %s", (po_id,))
                    current_po_row = cursor.fetchone()
                    current_status = current_po_row['Status'] if current_po_row else 'Draft'

                    # ب) إذا كان مكتمل سابقاً، نتركه مكتمل ولا نعيد الحساب
                    if current_status == 'Completed':
                         logging.info(f"PO #{po_id} is already Completed. Skipping status auto-update.")
                    else:
                        # ج) الحساب التلقائي (فقط إذا لم يكن مكتمل)
                        check_po_query = """
                            SELECT 
                                (SELECT COALESCE(SUM(Qty_Ordered), 0) FROM PO_Details WHERE PO_ID = %s) as Total_Ordered,
                                (SELECT COALESCE(SUM(Quantity_Initial), 0) FROM Inventory_Batches WHERE PO_ID = %s) as Total_Received
                        """
                        cursor.execute(check_po_query, (po_id, po_id))
                        po_stats = cursor.fetchone()
                        
                        total_ordered = float(po_stats['Total_Ordered'])
                        total_received = float(po_stats['Total_Received'])

                        new_po_status = 'Sent'
                        if total_ordered > 0 and total_received >= total_ordered:
                            new_po_status = 'Completed'
                        elif total_received > 0:
                            new_po_status = 'Partial'
                        
                        # تحديث الحالة فقط إذا تغيرت
                        if new_po_status != current_status:
                            cursor.execute("UPDATE Purchase_Orders SET Status = %s WHERE PO_ID = %s", (new_po_status, po_id))
                            logging.info(f"PO #{po_id} status auto-updated to: {new_po_status}")

                conn.commit()
                logging.info(f"Totals updated for BR #{br_id}: TTC={t_ttc:,.2f}")

        except Exception as e:
            logging.error(f"Error recalculating totals: {e}")
            

    def add_reception_line(self, line_data: Dict) -> Tuple[bool, str]:
        """إضافة سطر جديد (Batch) مع تسجيل PO_ID وحركة مخزنية."""
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()

            # --- [FIX] تمت إضافة PO_ID في جملة INSERT ---
            query = """
                INSERT INTO Inventory_Batches 
                (BR_ID, PO_ID, Product_ID, Location_ID, Quantity_Initial, Quantity_Current, 
                 Unit_Price_Received, Tax_Rate_Percent, Discount_Percent, 
                 Lot_Number, Expiry_Date, Reception_Note, Internal_Barcode, 
                 Status, Created_At)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Available', NOW())
            """
            
            # التأكد من وجود قيمة لـ PO_ID (حتى لو كانت None)
            po_id_val = line_data.get('PO_ID')
            
            params = (
                line_data['BR_ID'], 
                po_id_val,  # <--- تمرير القيمة هنا
                line_data['Product_ID'], 
                line_data['Location_ID'],
                line_data['Quantity_Initial'], 
                line_data['Quantity_Current'],
                line_data['Unit_Price_Received'], 
                line_data.get('Tax_Rate_Percent', 0),
                line_data.get('Discount_Percent', 0), 
                line_data.get('Lot_Number'),
                line_data.get('Expiry_Date'), 
                line_data.get('Batch_Note', ''),
                line_data.get('Internal_Barcode')
            )
            cursor.execute(query, params)
            batch_id = cursor.lastrowid

            # 2. تسجيل الحركة
            self.stock_movement_log.create_movement_log(
                product_id=line_data['Product_ID'],
                movement_type='Purchase_Receive',
                qty_change=Decimal(str(line_data['Quantity_Initial'])),
                unit_used='Unit',
                batch_id=batch_id,
                user_id=line_data.get('Created_By'),
                notes=f"Ajout ligne BR #{line_data['BR_ID']} (PO #{po_id_val})",
                external_cursor=cursor
            )

            conn.commit()
            return True, "Ajouté avec succès."
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Error adding line: {e}")
            return False, str(e)
        finally:
            if conn: conn.close()

    def update_reception_line(self, batch_id: int, line_data: Dict) -> Tuple[bool, str]:
        """تحديث سطر موجود (تعديل الكمية أو السعر)."""
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)

            # 1. جلب البيانات القديمة لحساب الفرق
            cursor.execute("SELECT Quantity_Initial, Quantity_Current FROM Inventory_Batches WHERE Batch_ID = %s", (batch_id,))
            old_data = cursor.fetchone()
            if not old_data:
                return False, "Lot introuvable."

            old_qty = float(old_data['Quantity_Initial'])
            new_qty = float(line_data['Quantity_Initial'])
            diff = new_qty - old_qty
            
            # تحديث Current بناءً على الفرق (مع مراعاة الاستهلاك)
            new_current = float(old_data['Quantity_Current']) + diff
            if new_current < 0:
                return False, "Impossible: Stock consommé."

            # 2. تحديث الباتش
            query = """
                UPDATE Inventory_Batches 
                SET Product_ID=%s, Location_ID=%s, Quantity_Initial=%s, Quantity_Current=%s,
                    Unit_Price_Received=%s, Tax_Rate_Percent=%s, Discount_Percent=%s,
                    Lot_Number=%s, Expiry_Date=%s, Reception_Note=%s, Internal_Barcode=%s
                WHERE Batch_ID=%s
            """
            params = (
                line_data['Product_ID'], line_data['Location_ID'], new_qty, new_current,
                line_data['Unit_Price_Received'], line_data.get('Tax_Rate_Percent', 0),
                line_data.get('Discount_Percent', 0), line_data.get('Lot_Number'),
                line_data.get('Expiry_Date'), line_data.get('Batch_Note', ''),
                line_data.get('Internal_Barcode'), batch_id
            )
            cursor.execute(query, params)

            # 3. تسجيل حركة التعديل (إذا تغيرت الكمية)
            if abs(diff) > 0.0001:
                self.stock_movement_log.create_movement_log(
                    product_id=line_data['Product_ID'],
                    movement_type='Adjustment', # أو Purchase_Receive
                    qty_change=Decimal(str(diff)),
                    unit_used='Unit',
                    batch_id=batch_id,
                    user_id=line_data.get('Created_By'),
                    notes=f"Correction BR #{line_data['BR_ID']}",
                    external_cursor=cursor
                )

            conn.commit()
            return True, "Mis à jour avec succès."
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Error updating line: {e}")
            return False, str(e)
        finally:
            if conn: conn.close()

    def delete_reception_line(self, batch_id: int) -> Tuple[bool, str]:
        """حذف سطر (باتش) بالكامل."""
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()

            # التحقق من الاستهلاك
            cursor.execute("SELECT Quantity_Initial, Quantity_Current FROM Inventory_Batches WHERE Batch_ID = %s", (batch_id,))
            row = cursor.fetchone() # returns tuple in raw cursor
            if not row: return False, "Introuvable"
            
            # row[0] -> Initial, row[1] -> Current
            if row[1] < row[0]:
                return False, "Impossible de supprimer : Article déjà consommé."

            # الحذف
            cursor.execute("DELETE FROM Stock_Movement_Log WHERE Batch_ID = %s", (batch_id,))
            cursor.execute("DELETE FROM Inventory_Batches WHERE Batch_ID = %s", (batch_id,))
            
            conn.commit()
            return True, "Supprimé avec succès."
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Error deleting line: {e}")
            return False, str(e)
        finally:
            if conn: conn.close()


    # --- (الدوال القديمة تبقى كما هي أدناه) ---

    def create_reception_log(self, po_id: Optional[int], supplier_invoice_ref: str, reception_date: datetime, 
                             supplier_id: int, receiver_user_id: Optional[int] = None,
                             financials: Dict = None) -> Optional[int]:
        """
        إنشاء سجل استلام جديد (دالة مساعدة).
        """
        try:
            # القيم الافتراضية
            fin = financials or {}
            total_ht = fin.get('total_ht', 0.0)
            total_tva = fin.get('total_tva', 0.0)
            total_ttc = fin.get('total_ttc', 0.0)

            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Reception_Log 
                    (PO_ID, Supplier_Invoice_Ref, Reception_Date, Supplier_ID, Receiver_User_ID, Status,
                     Invoice_Total_HT, Invoice_Total_TVA, Invoice_Total_TTC) 
                    VALUES (%s, %s, %s, %s, %s, 'Pending Audit', %s, %s, %s)
                """
                params = (
                    po_id, supplier_invoice_ref, reception_date, supplier_id, receiver_user_id,
                    total_ht, total_tva, total_ttc
                )
                cursor.execute(query, params)
                conn.commit()
                br_id = cursor.lastrowid
                logging.info(f"Reception Log (BR) ID {br_id} created for Invoice Ref: {supplier_invoice_ref}.")
                return br_id
        except mysql.connector.Error as err:
            if err.errno == 1062:
                logging.warning(f"Reception failed: Invoice reference '{supplier_invoice_ref}' already exists.")
            else:
                logging.error(f"Database error while creating reception log: {err}")
            return None

    def update_reception_status_and_notes(self, br_id: int, new_status: str, variance_notes: Optional[str] = None) -> bool:
        """تحديث حالة سجل الاستلام."""
        valid_statuses = ['Completed', 'Variance Detected', 'Pending Audit']
        if new_status not in valid_statuses:
            logging.error(f"Invalid status '{new_status}' provided for BR {br_id}.")
            return False

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    UPDATE Reception_Log 
                    SET Status = %s, Variance_Notes = %s 
                    WHERE BR_ID = %s
                """
                params = (new_status, variance_notes, br_id)
                cursor.execute(query, params)
                conn.commit()
                return cursor.rowcount > 0
        except mysql.connector.Error as e:
            logging.error(f"Error updating reception log status {br_id}: {e}")
            raise
    def check_invoice_exists(self, invoice_ref: str) -> bool:
        """تحقق مسبق إذا كان رقم الفاتورة موجوداً في النظام."""
        if not invoice_ref: return False
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT COUNT(*) FROM Reception_Log WHERE Supplier_Invoice_Ref = %s"
                cursor.execute(query, (invoice_ref,))
                count = cursor.fetchone()[0]
                return count > 0
        except Exception as e:
            logging.error(f"Error checking invoice existence: {e}")
            return False

    def process_reception_transaction(self, data):
        doc_type_map = {"Facture": "Facture", "Bon de Livraison (BL)": "BL", "Both": "Both", "None": "None"}
        db_doc_type = doc_type_map.get(data.get('Document_Type', 'Facture'), "Facture")

        invoice_ref = (data.get('Supplier_Invoice_Ref') or "").strip() or None
        bl_ref = (data.get('Supplier_BL_Ref') or "").strip() or None

        if invoice_ref and self.check_invoice_exists(invoice_ref):
            raise ValueError(f"La facture Nº {invoice_ref} a déjà été reçue.")

        po_id = data.get('PO_ID')
        supplier_id = data.get('Supplier_ID')

        t_ht, t_rem, t_tva = 0.0, 0.0, 0.0
        if 'Financials' in data:
            for f in data['Financials']:
                line_total = f.get('Unit_Price_HT', 0) * f.get('Qty_Factured', 0)
                t_ht += line_total
                t_rem += f.get('Discount_Val', 0)
                t_tva += (line_total - f.get('Discount_Val', 0)) * (f.get('Tax_Percent', 0)/100)
        t_ttc = (t_ht - t_rem) + t_tva

        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()

            query = """
                INSERT INTO Reception_Log 
                (PO_ID, Supplier_Invoice_Ref, Supplier_BL_Ref, Document_Type, Reception_Date, 
                 Supplier_ID, Status, Invoice_Total_HT, Invoice_Total_TVA, Invoice_Total_TTC) 
                VALUES (%s, %s, %s, %s, %s, %s, 'Completed', %s, %s, %s)
            """
            cursor.execute(query, (po_id, invoice_ref, bl_ref, db_doc_type, data.get('Reception_Date'), 
                                  supplier_id, t_ht, t_tva, t_ttc))
            br_id = cursor.lastrowid

            from .inventory_batch_manager import InventoryBatchManager

            for i, b in enumerate(data.get('Batches', [])):
                f = data.get('Financials', [])[i] if 'Financials' in data else {}
                
                # استخدام الكود القادم من الواجهة (الذي يحتوي على معرف الطلب)
                smart_barcode = b.get('Internal_Barcode')
                
                # إذا لم ترسل الواجهة باركود، نقوم بتوليده هنا كخطة بديلة
                if not smart_barcode:
                    prefix = po_id if po_id else br_id
                    smart_barcode = InventoryBatchManager.generate_smart_barcode(prefix, i + 1)

                batch_query = """
                    INSERT INTO Inventory_Batches 
                    (Product_ID, Location_ID, Lot_Number, Expiry_Date, Quantity_Initial, Quantity_Current, 
                     PO_ID, BR_ID, Status, Reception_Note, Unit_Price_Received, Tax_Rate_Percent, 
                     Discount_Percent, Internal_Barcode) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Available', %s, %s, %s, %s, %s)
                """
                
                disc_pct = f.get('Discount_Val', 0) / (f.get('Unit_Price_HT', 1) * b.get('Received_Qty', 1)) if f.get('Unit_Price_HT', 1) > 0 else 0
                
                cursor.execute(batch_query, (
                    b.get('Product_ID'), b.get('Location_ID'), b.get('Lot_Number'), b.get('Expiry_Date'),
                    b.get('Received_Qty'), b.get('Received_Qty'), po_id, br_id, 
                    b.get('Reception_Note', ''), f.get('Unit_Price_HT', 0), f.get('Tax_Percent', 0), 
                    disc_pct, smart_barcode
                ))
                # تم حذف سطر الـ UPDATE هنا لضمان عدم ضياع الباركود الذكي

            if po_id:
                cursor.execute("UPDATE Purchase_Orders SET Status = 'Completed' WHERE PO_ID = %s", (po_id,))

            conn.commit()
            return True
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Error process_reception: {e}")
            return False
        finally:
            if conn: conn.close()
            
    def get_reception_summary(self, br_id):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT rl.*, s.Supplier_Name 
                    FROM Reception_Log rl 
                    LEFT JOIN Suppliers s ON rl.Supplier_ID = s.Supplier_ID 
                    WHERE rl.BR_ID = %s
                """, (br_id,))
                header = cursor.fetchone()

                if not header:
                    logging.error(f"No reception header found for BR_ID: {br_id}")
                    return {"Header": {}, "Batches": []}

                query_batches = """
                    SELECT 
                        b.*, p.Product_Name, p.Stock_Unit, p.Ordering_Unit,
                        l.Location_Name, m.Manuf_Name AS Brand_Name, b.Reception_Note
                    FROM Inventory_Batches b
                    JOIN Products_Master p ON b.Product_ID = p.Product_ID
                    LEFT JOIN Locations l ON b.Location_ID = l.Location_ID
                    LEFT JOIN Manufacturers m ON p.Manuf_ID = m.Manuf_ID 
                    WHERE b.BR_ID = %s AND b.Quantity_Initial > 0
                """
                cursor.execute(query_batches, (br_id,))
                batches = cursor.fetchall()
                
                return {"Header": header, "Batches": batches}
        except Exception as e:
            logging.error(f"Error fetching reception summary: {e}")
            return {"Header": {}, "Batches": []}
        
    def get_batches_by_br(self, br_id):
        """
        جلب الدفعات (Batches) لعملية استلام محددة.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        b.*, p.Product_Name, b.Reception_Note,
                        b.Unit_Price_Received, b.Tax_Rate_Percent, b.Discount_Percent
                    FROM Inventory_Batches b
                    JOIN Products_Master p ON b.Product_ID = p.Product_ID
                    WHERE b.BR_ID = %s AND b.Quantity_Initial > 0
                """
                cursor.execute(query, (br_id,))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching batches for BR {br_id}: {e}")
            return []
        

    def get_all_reception_logs(self) -> List[Dict]:
        """
        جلب قائمة بكل عمليات الاستلام المكتملة للعرض في سجل التاريخ.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        rl.BR_ID,
                        rl.Supplier_Invoice_Ref,
                        rl.Reception_Date,
                        rl.Invoice_Total_TTC,
                        rl.Status,
                        s.Supplier_Name,
                        po.PO_ID
                    FROM Reception_Log rl
                    LEFT JOIN Suppliers s ON rl.Supplier_ID = s.Supplier_ID
                    LEFT JOIN Purchase_Orders po ON rl.PO_ID = po.PO_ID
                    ORDER BY rl.Reception_Date DESC, rl.BR_ID DESC
                """
                cursor.execute(query)
                return cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error(f"Error fetching reception logs: {e}")
            return []

    def get_reception_full_details(self, br_id: int) -> Dict:
        # نفس الكود الموجود في رسالتك السابقة (هو صحيح)
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query_header = "SELECT rl.*, s.Supplier_Name FROM Reception_Log rl LEFT JOIN Suppliers s ON rl.Supplier_ID = s.Supplier_ID WHERE rl.BR_ID = %s"
                cursor.execute(query_header, (br_id,))
                header = cursor.fetchone()
                if not header: return None
                
                query_batches = """
                    SELECT b.Batch_ID, b.Product_ID, b.Location_ID, b.Lot_Number, b.Expiry_Date, 
                           b.Quantity_Initial, b.Internal_Barcode, b.Unit_Price_Received, b.Tax_Rate_Percent, 
                           b.Discount_Percent, b.Reception_Note, 
                           p.Product_Name, p.Stock_Unit, l.Location_Name
                    FROM Inventory_Batches b
                    JOIN Products_Master p ON b.Product_ID = p.Product_ID
                    LEFT JOIN Locations l ON b.Location_ID = l.Location_ID
                    WHERE b.BR_ID = %s AND b.Quantity_Initial > 0
                """
                cursor.execute(query_batches, (br_id,))
                batches = cursor.fetchall()
                return {"Header": header, "Batches": batches}
        except Exception as e:
            logging.error(f"Error: {e}")
            return None
        
    def record_reception_transaction(self, data):
        conn = self.db.get_raw_connection()
        try:
            conn.start_transaction()
            cursor = conn.cursor()

            reception_query = """
                INSERT INTO Reception_Log 
                (PO_ID, Supplier_Invoice_Ref, Reception_Date, Variance_Notes, Status) 
                VALUES (%s, %s, %s, %s, 'Completed')
            """
            cursor.execute(reception_query, (data.get('PO_ID'), data.get('Supplier_Invoice_Ref'),
                                           data.get('Reception_Date'), data.get('Variance_Notes')))
            br_id = cursor.lastrowid 

            from .inventory_batch_manager import InventoryBatchManager

            for i, b in enumerate(data.get('Batches', [])):
                # توليد الباركود الذكي لكل منتج في الوصل
                smart_barcode = InventoryBatchManager.generate_smart_barcode(br_id, i + 1)

                batch_query = """
                    INSERT INTO Inventory_Batches 
                    (Product_ID, Location_ID, Lot_Number, Expiry_Date, 
                    Quantity_Initial, Quantity_Current, PO_ID, BR_ID, Status, Reception_Note, Internal_Barcode) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Available', %s, %s)
                """
                cursor.execute(batch_query, (b['Product_ID'], b['Location_ID'], b['Lot_Number'], 
                                           b['Expiry_Date'], b['Received_Qty'], b['Received_Qty'], 
                                           data.get('PO_ID'), br_id, b.get('Reception_Note', ''), smart_barcode))
                
                batch_id = cursor.lastrowid 
                
                cursor.execute("""
                    INSERT INTO Stock_Movement_Log 
                    (Product_ID, Batch_ID, Movement_Type, Qty_Change, Unit_Used, Transaction_Date, Notes)
                    VALUES (%s, %s, 'Purchase_Receive', %s, 'Stock_Unit', NOW(), %s)
                """, (b['Product_ID'], batch_id, b['Received_Qty'], f"Réception BR #{br_id}"))

            if data.get('PO_ID'):
                cursor.execute("UPDATE Purchase_Orders SET Status = 'Completed' WHERE PO_ID = %s", (data['PO_ID'],))

            conn.commit()
            return True
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Error recording reception: {e}")
            return False
        finally:
            if conn: conn.close()

    def process_full_reception(self, header_data, items, user_id=None):
        """
        حفظ عملية استلام جديدة وتسجيل الحركة في السجل.
        """
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()

            # 1. إدخال الرأس (Header)
            query_log = """
                INSERT INTO Reception_Log 
                (PO_ID, Supplier_ID, Supplier_Invoice_Ref, Supplier_BL_Ref, Document_Type, 
                Reception_Date, Invoice_Total_HT, Invoice_Total_TVA, Invoice_Total_TTC, 
                Total_Discount, Received_By, Status) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Completed')
            """
            cursor.execute(query_log, (
                header_data.get('PO_ID'), header_data.get('Supplier_ID'), 
                header_data.get('Supplier_Invoice_Ref'), header_data.get('Supplier_BL_Ref'), 
                header_data.get('Document_Type'), header_data.get('Reception_Date'),
                header_data.get('Invoice_Total_HT'), header_data.get('Invoice_Total_TVA'),
                header_data.get('Invoice_Total_TTC'), header_data.get('Total_Discount'),
                user_id  # <--- تسجيل المستخدم الذي قام بالاستلام
            ))
            receipt_id = cursor.lastrowid

            # 2. إدخال المنتجات (Batches)
            from .inventory_batch_manager import InventoryBatchManager
            po_id = header_data.get('PO_ID') or receipt_id

            for i, item in enumerate(items):
                # توليد باركود ذكي
                smart_barcode = item.get('Internal_Barcode')
                if not smart_barcode or smart_barcode == '---':
                    smart_barcode = InventoryBatchManager.generate_smart_barcode(po_id, i + 1)

                query_batch = """
                    INSERT INTO Inventory_Batches 
                    (Product_ID, Location_ID, Lot_Number, Expiry_Date, Quantity_Initial, 
                    Quantity_Current, PO_ID, BR_ID, Status, Internal_Barcode,
                    Unit_Price_Received, Tax_Rate_Percent, Discount_Percent, Reception_Note, Created_At) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Available', %s, %s, %s, %s, %s, NOW())
                """
                cursor.execute(query_batch, (
                    item['Product_ID'], item['Location_ID'], item.get('Lot_Number'),
                    item.get('Expiry_Date'), item['Qty_Received'], item['Qty_Received'],
                    header_data.get('PO_ID'), receipt_id, smart_barcode,
                    item.get('Unit_Price_Received', 0), item.get('Tax_Rate_Percent', 0),
                    item.get('Discount_Percent', 0), item.get('Line_Note', '')
                ))
                
                batch_id = cursor.lastrowid

                # 3. تسجيل الحركة في Stock_Movement_Log (الأهم للـ Historique)
                self.stock_movement_log.create_movement_log(
                    product_id=item['Product_ID'],
                    movement_type='Purchase_Receive',
                    qty_change=Decimal(str(item['Qty_Received'])),
                    unit_used=item.get('Unit_Label', 'U'),
                    batch_id=batch_id,
                    user_id=user_id,  # <--- المستخدم
                    notes=f"Réception Initiale BR #{receipt_id}",
                    external_cursor=cursor
                )

            # تحديث حالة الطلب
            if header_data.get('PO_ID'):
                cursor.execute("UPDATE Purchase_Orders SET Status = 'Completed' WHERE PO_ID = %s", (header_data['PO_ID'],))

            conn.commit()
            return True, "Réception enregistrée avec succès."
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Error process_full_reception: {e}")
            return False, str(e)
        finally:
            if conn: conn.close()

    def get_all_receptions(self):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT rl.BR_ID, rl.Supplier_Invoice_Ref, rl.Supplier_BL_Ref, 
                           s.Supplier_Name, rl.Reception_Date,
                           rl.Invoice_Total_HT, rl.Invoice_Total_TVA, rl.Invoice_Total_TTC, 
                           rl.Status, rl.PO_ID, rl.Total_Discount, rl.Variance_Notes
                    FROM Reception_Log rl
                    JOIN Suppliers s ON rl.Supplier_ID = s.Supplier_ID
                    WHERE rl.Status IN ('Completed', 'Variance Detected', 'Pending Audit') 
                    ORDER BY rl.Reception_Date DESC
                """
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching receptions: {e}")
            return []
        
    def get_reception_details(self, br_id: int) -> Dict:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                header_query = """
                    SELECT rl.*, s.Supplier_Name 
                    FROM Reception_Log rl JOIN Suppliers s ON rl.Supplier_ID = s.Supplier_ID 
                    WHERE rl.BR_ID = %s
                """
                cursor.execute(header_query, (br_id,))
                header = cursor.fetchone()
                if not header: return None
                
                batches_query = """
                    SELECT ib.*, pm.Product_Name, pm.Stock_Unit, l.Location_Name
                    FROM Inventory_Batches ib
                    JOIN Products_Master pm ON ib.Product_ID = pm.Product_ID
                    LEFT JOIN Locations l ON ib.Location_ID = l.Location_ID
                    WHERE ib.BR_ID = %s
                """
                cursor.execute(batches_query, (br_id,))
                return {'Header': header, 'Batches': cursor.fetchall()}
        except Exception as e:
            logging.error(f"Error fetching details: {e}")
            return None

    def update_reception(self, br_id: int, header_data: Dict, items: List[Dict], user_id=None) -> Tuple[bool, str]:
        """
        تحديث استلام سابق.
        المنطق الجديد: 
        1. نحافظ على السجلات القديمة كما هي (للتاريخ).
        2. نسجل حركة جديدة بالفرق (Delta) باسم المستخدم الجديد الذي قام بالتعديل.
        """
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)

            # 1. تحديث الرأس (Header) - يتم تحديثه لأنه يمثل الحالة الحالية للفاتورة
            query_update_header = """
                UPDATE Reception_Log 
                SET Supplier_Invoice_Ref = %s, Supplier_BL_Ref = %s, Document_Type = %s,
                    Reception_Date = %s, Invoice_Total_HT = %s, Invoice_Total_TVA = %s,
                    Invoice_Total_TTC = %s, Total_Discount = %s, Received_By = %s
                WHERE BR_ID = %s
            """
            cursor.execute(query_update_header, (
                header_data.get('Supplier_Invoice_Ref'), header_data.get('Supplier_BL_Ref'),
                header_data.get('Document_Type', 'Facture'), header_data['Reception_Date'], 
                header_data['Invoice_Total_HT'], header_data['Invoice_Total_TVA'], 
                header_data['Invoice_Total_TTC'], header_data.get('Total_Discount', 0),
                user_id, # المستخدم الأخير الذي عدل
                br_id
            ))

            # 2. جلب البيانات القديمة
            cursor.execute("SELECT Batch_ID, Quantity_Initial, Quantity_Current, Product_ID FROM Inventory_Batches WHERE BR_ID = %s", (br_id,))
            existing_batches = {row['Batch_ID']: row for row in cursor.fetchall()}
            
            incoming_ids = [int(item['Batch_ID']) for item in items if item.get('Batch_ID')]

            # 3. الحذف (Deletion)
            batches_to_delete = []
            for bid, b_data in existing_batches.items():
                if bid not in incoming_ids:
                    if b_data['Quantity_Current'] < b_data['Quantity_Initial']:
                        conn.rollback()
                        return False, f"Impossible de supprimer le produit ID {b_data['Product_ID']} : stock déjà consommé."
                    batches_to_delete.append(bid)

            # عند الحذف، هنا يمكننا إما حذف السجلات (كما في السابق) أو إضافة حركة عكسية.
            # للحفاظ على نظافة قاعدة البيانات في حال الحذف الكامل للسطر، سنحذفه (أو يمكنك تغيير المنطق لأرشفته).
            if batches_to_delete:
                format_strings = ','.join(['%s'] * len(batches_to_delete))
                cursor.execute(f"DELETE FROM Stock_Movement_Log WHERE Batch_ID IN ({format_strings})", tuple(batches_to_delete))
                cursor.execute(f"DELETE FROM Inventory_Batches WHERE Batch_ID IN ({format_strings})", tuple(batches_to_delete))

            # 4. التعديل والإضافة
            from .inventory_batch_manager import InventoryBatchManager
            po_id = header_data.get('PO_ID') or br_id
            edit_timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")

            for i, item in enumerate(items):
                current_batch_id = item.get('Batch_ID')

                if current_batch_id:
                    # === تعديل سطر موجود ===
                    bid = int(current_batch_id)
                    if bid not in existing_batches: continue 

                    old_data = existing_batches[bid]
                    old_initial = float(old_data['Quantity_Initial'])
                    old_current = float(old_data['Quantity_Current'])
                    new_initial = float(item['Qty_Received'])
                    
                    # حساب الفرق (Delta)
                    qty_delta = new_initial - old_initial
                    new_current = old_current + qty_delta

                    if new_current < 0:
                        conn.rollback()
                        return False, f"Stock insuffisant pour réduire la quantité (ID: {bid})."

                    # تحديث الباتش (Inventory_Batches) ليعكس الوضع الحالي
                    update_query = """
                        UPDATE Inventory_Batches 
                        SET Product_ID=%s, Location_ID=%s, Lot_Number=%s, Expiry_Date=%s, 
                            Quantity_Initial=%s, Quantity_Current=%s, Reception_Note=%s,
                            Unit_Price_Received=%s, Tax_Rate_Percent=%s, Discount_Percent=%s,
                            Internal_Barcode=%s
                        WHERE Batch_ID=%s
                    """
                    cursor.execute(update_query, (
                        item['Product_ID'], item['Location_ID'], item.get('Lot_Number'), item['Expiry_Date'],
                        new_initial, new_current, item.get('Line_Note', ''),
                        item['Unit_Price_Received'], item['Tax_Rate_Percent'], item.get('Discount_Percent', 0),
                        item.get('Internal_Barcode'), bid
                    ))

                    # === التغيير الجذري هنا: تسجيل الفرق كحركة جديدة ===
                    if abs(qty_delta) > 0.0001:
                        # صياغة ملاحظة توضح أن هذا تعديل
                        note = f"Correction BR #{br_id}: {old_initial:g} -> {new_initial:g}"
                        if item.get('Line_Note'): note += f" | {item.get('Line_Note')}"
                        
                        # إنشاء سجل جديد بالفرق فقط!
                        # لا نستخدم movement_type='Purchase_Receive' لكي لا يظن النظام أنه استلام جديد كلياً في التقارير، 
                        # بل نستخدم 'Adjustment' أو نبقيه 'Purchase_Receive' مع ملاحظة واضحة.
                        # سنبقيه 'Purchase_Receive' لكي يظهر عند فلترة الاستلامات، لكنه سيكون بتاريخ اليوم وباسم المستخدم الحالي.
                        self.stock_movement_log.create_movement_log(
                            product_id=item['Product_ID'],
                            movement_type='Purchase_Receive', # أو 'Adjustment'
                            qty_change=Decimal(str(qty_delta)), # نسجل الفرق فقط (+6 أو -2)
                            unit_used=item.get('Unit_Label', 'U'),
                            batch_id=bid,
                            user_id=user_id, # <--- هنا سيظهر اسمك أنت (المعدل)
                            notes=note,
                            external_cursor=cursor
                        )
                    elif item.get('Line_Note') != old_data.get('Reception_Note'):
                         # إذا تغيرت الملاحظة فقط دون الكمية، يمكننا إضافة سجل ملاحظة (اختياري)
                         pass

                else:
                    # === إضافة سطر جديد ===
                    smart_barcode = item.get('Internal_Barcode')
                    if not smart_barcode or smart_barcode == '---':
                         smart_barcode = InventoryBatchManager.generate_smart_barcode(po_id, i + 1)

                    batch_query = """
                        INSERT INTO Inventory_Batches 
                        (Product_ID, Location_ID, Lot_Number, Expiry_Date, Quantity_Initial, Quantity_Current, 
                        PO_ID, BR_ID, Status, Reception_Note, Unit_Price_Received, Tax_Rate_Percent, 
                        Discount_Percent, Internal_Barcode, Created_At) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Available', %s, %s, %s, %s, %s, NOW())
                    """
                    cursor.execute(batch_query, (
                        item['Product_ID'], item['Location_ID'], item.get('Lot_Number'), item['Expiry_Date'],
                        item['Qty_Received'], item['Qty_Received'], header_data.get('PO_ID'), br_id, 
                        item.get('Line_Note', ''), item['Unit_Price_Received'], item['Tax_Rate_Percent'], 
                        item.get('Discount_Percent', 0), smart_barcode
                    ))
                    new_batch_id = cursor.lastrowid

                    # تسجيل حركة جديدة
                    self.stock_movement_log.create_movement_log(
                        product_id=item['Product_ID'],
                        movement_type='Purchase_Receive',
                        qty_change=Decimal(str(item['Qty_Received'])),
                        unit_used=item.get('Unit_Label', 'U'),
                        batch_id=new_batch_id,
                        user_id=user_id, 
                        notes=f"Ajouté lors de correction ({edit_timestamp})",
                        external_cursor=cursor
                    )

            conn.commit()
            return True, "Mise à jour réussie (Historique conservé)."

        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Error update_reception: {e}")
            return False, str(e)
        finally:
            if conn: conn.close()

    def delete_reception(self, br_id: int) -> Tuple[bool, str]:
        # نفس الكود الموجود في رسالتك السابقة (هو صحيح)
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()
            
            check_usage = "SELECT Count(*) FROM Inventory_Batches WHERE BR_ID = %s AND Quantity_Current < Quantity_Initial"
            cursor.execute(check_usage, (br_id,))
            if cursor.fetchone()[0] > 0:
                conn.rollback()
                return False, "Impossible de supprimer : Des articles ont déjà été consommés."

            cursor.execute("DELETE sml FROM Stock_Movement_Log sml JOIN Inventory_Batches ib ON sml.Batch_ID = ib.Batch_ID WHERE ib.BR_ID = %s", (br_id,))
            cursor.execute("DELETE FROM Inventory_Batches WHERE BR_ID = %s", (br_id,))
            cursor.execute("DELETE FROM Reception_Log WHERE BR_ID = %s", (br_id,))
            
            conn.commit()
            return True, "Réception supprimée."
        except Exception as e:
            if conn: conn.rollback()
            return False, str(e)
        finally:
            if conn: conn.close()


    def is_barcode_exists_in_db(self, barcode):
        """التحقق مما إذا كان الباركود موجوداً في قاعدة البيانات"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT COUNT(*) FROM Inventory_Batches WHERE Internal_Barcode = %s"
                cursor.execute(query, (barcode,))
                count = cursor.fetchone()[0]
                return count > 0
        except Exception as e:
            logging.error(f"Error checking barcode existence: {e}")
            return True # نفترض وجوده لتجنب الأخطاء

            
    def get_last_barcode_for_po(self, po_id):
        """جلب آخر باركود تم توليده لهذا الطلب من المخزون."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT MAX(Internal_Barcode) FROM Inventory_Batches WHERE PO_ID = %s"
                cursor.execute(query, (po_id,))
                res = cursor.fetchone()
                return res[0] if res and res[0] else None
        except Exception as e:
            logging.error(f"Error fetching last barcode: {e}")
            return None
    def get_receptions_with_issues(self):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        rl.*, 
                        s.Supplier_Name,
                        (SELECT COUNT(*) FROM Inventory_Batches ib 
                         WHERE ib.BR_ID = rl.BR_ID AND ib.Reception_Note IS NOT NULL AND ib.Reception_Note != '') as Product_Issues_Count
                    FROM Reception_Log rl
                    JOIN Suppliers s ON rl.Supplier_ID = s.Supplier_ID
                    WHERE 
                        (rl.Variance_Notes IS NOT NULL AND rl.Variance_Notes != '')
                        OR 
                        EXISTS (SELECT 1 FROM Inventory_Batches ib 
                                WHERE ib.BR_ID = rl.BR_ID AND ib.Reception_Note IS NOT NULL AND ib.Reception_Note != '')
                    ORDER BY rl.Reception_Date DESC
                """
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching receptions with issues: {e}")
            return []
    def update_variance_note(self, br_id, note):
        """تحديث ملاحظة الشكوى (Variance Note) في رأس الاستلام."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE Reception_Log SET Variance_Notes = %s WHERE BR_ID = %s",
                    (note, br_id)
                )
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error updating variance note: {e}")
            return False
    def update_batch_note(self, batch_id, note):
        """تحديث ملاحظة منتج محدد (Reception_Note) في جدول الدفعات."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE Inventory_Batches SET Reception_Note = %s WHERE Batch_ID = %s",
                    (note, batch_id)
                )
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error updating batch note: {e}")
            return False
    
    def get_reception_with_batches_by_ref(self, ref):
        """
        البحث عن وصل الاستلام باستخدام رقم الفاتورة أو رقم الـ BL
        وجلب جميع المنتجات (الحصص) المرتبطة بهذا الوصل.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # 1. جلب المعلومات العامة للوصل (Header)
                query_header = """
                    SELECT * FROM Reception_Log 
                    WHERE Supplier_Invoice_Ref = %s OR Supplier_BL_Ref = %s
                    LIMIT 1
                """
                cursor.execute(query_header, (ref, ref))
                header = cursor.fetchone()
                
                if not header:
                    return None  # لم يتم العثور على الوصل
                    
                br_id = header['BR_ID']
                
                query_batches = """
                    SELECT 
                        b.Batch_ID, b.Product_ID, b.Lot_Number, b.Expiry_Date, 
                        b.Quantity_Current, b.Unit_Price_Received, b.Internal_Barcode,
                        p.Product_Name, p.Barcode
                    FROM Inventory_Batches b
                    JOIN Products_Master p ON b.Product_ID = p.Product_ID
                    WHERE b.BR_ID = %s AND b.Quantity_Initial > 0
                """
                cursor.execute(query_batches, (br_id,))
                batches = cursor.fetchall()
                
                return {
                    'Header': header,
                    'Batches': batches
                }
                
        except Exception as e:
            import logging
            logging.error(f"Erreur get_reception_with_batches_by_ref: {e}")
            raise e
    def get_reception_by_id(self, br_id):
        """جلب بيانات رأس وصل استلام محدد بواسطة معرفه"""
        with self.db.get_db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM Reception_Log WHERE BR_ID = %s", (br_id,))
            return cursor.fetchone()