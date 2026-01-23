# database/inventory_batch_manager.py

import mysql.connector
import logging
from datetime import date, datetime
from typing import List, Dict, Optional
from decimal import Decimal


class InventoryBatchManager:
    """
    إدارة عمليات جدول دفعات المخزون (Inventory_Batches).
    """

    def __init__(self, db_instance):
        from .stock_movement_log_manager import StockMovementLogManager  # Add this import

        self.db = db_instance
        self.stock_movement_log = StockMovementLogManager(db_instance)


    def create_inventory_batch(self, product_id, br_id, lot_number, expiry_date, 
                               initial_stock_qty, location_id, date_received, 
                               po_id=None, unit_price=0.0, tax_rate=0.0, discount=0.0, 
                               item_index=1, internal_barcode=None):
        """
        تم دمج التعريفين في تعريف واحد قوي.
        """
        conn = None
        try:
            conn = self.db.get_db_connection()
            conn.autocommit = False
            cursor = conn.cursor()

            final_barcode = internal_barcode
            if not final_barcode:
                prefix = po_id if po_id else (br_id if br_id else "STK")
                final_barcode = self.generate_smart_barcode(prefix, item_index)

            # التحقق من وجود نفس الباركود في نفس الموقع لدمج الكمية
            cursor.execute("""
                SELECT Batch_ID FROM Inventory_Batches 
                WHERE Internal_Barcode = %s AND Location_ID = %s
            """, (final_barcode, location_id))
            
            existing = cursor.fetchone()
            if existing:
                logging.info(f"Mise à jour quantité pour code {final_barcode} loc {location_id}.")
                cursor.execute("""
                    UPDATE Inventory_Batches 
                    SET Quantity_Current = Quantity_Current + %s, Quantity_Initial = Quantity_Initial + %s
                    WHERE Batch_ID = %s
                """, (initial_stock_qty, initial_stock_qty, existing[0]))
                batch_id = existing[0]
            else:
                query = """
                    INSERT INTO Inventory_Batches 
                    (Product_ID, Location_ID, Lot_Number, Expiry_Date, 
                    Quantity_Initial, Quantity_Current, PO_ID, BR_ID, Status, Created_At,
                    Unit_Price_Received, Tax_Rate_Percent, Discount_Percent, Internal_Barcode) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Available', %s, %s, %s, %s, %s)
                """
                params = (product_id, location_id, lot_number, expiry_date, 
                        initial_stock_qty, initial_stock_qty, po_id, br_id, 
                        date_received, unit_price, tax_rate, discount, final_barcode)
                
                cursor.execute(query, params)
                batch_id = cursor.lastrowid 

            conn.commit()
            return batch_id

        except mysql.connector.Error as err:
            if conn: conn.rollback()
            logging.error(f"Database error in create_inventory_batch: {err}")
            return None
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()

    def get_next_smart_barcode(self, po_id):
        """
        تبحث في قاعدة البيانات عن آخر باركود لهذا الطلب وتعطي الرقم التالي مباشرة.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                # نبحث عن الباركودات التي تبدأ برقم الـ PO
                query = "SELECT MAX(Internal_Barcode) FROM Inventory_Batches WHERE Internal_Barcode LIKE %s"
                cursor.execute(query, (f"{po_id}%",))
                last_barcode = cursor.fetchone()[0]

                if last_barcode:
                    # إذا وجدنا مثلاً 252003، نستخرج 003 ونزيده 1
                    try:
                        # طول po_id مثلا 252 (3 أرقام)، نأخذ ما بعده
                        prefix_len = len(str(po_id))
                        last_serial = int(last_barcode[prefix_len:])
                        new_serial = last_serial + 1
                    except ValueError:
                        new_serial = 1
                else:
                    new_serial = 1

                return self.generate_smart_barcode(po_id, new_serial)
        except Exception as e:
            logging.error(f"Error getting next barcode: {e}")
            return f"{po_id}001"


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

    def update_batch_location_status(self, batch_id: int, location_id: Optional[int] = None, new_status: Optional[str] = None) -> bool:
        updates = []
        params = []
        
        if location_id is not None:
            updates.append("Location_ID = %s")
            params.append(location_id)
            
        if new_status is not None:
            valid_statuses = ['Available', 'Quarantined', 'Expired', 'Depleted']
            if new_status not in valid_statuses:
                logging.error(f"Invalid status '{new_status}' provided for batch {batch_id}.")
                return False
            updates.append("Status = %s")
            params.append(new_status)
            
        if not updates:
            return False

        params.append(batch_id)
        query = f"UPDATE Inventory_Batches SET {', '.join(updates)} WHERE Batch_ID = %s"
        
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                return cursor.rowcount > 0
        except mysql.connector.Error as e:
            logging.error(f"Error updating batch {batch_id}: {e}")
            raise

    def get_batches_by_product_id(self, product_id: int, min_qty: int = 1) -> List[Dict]:
        """جلب الدفعات مع معالجة حذر لأسماء الأعمدة."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        b.Batch_ID, b.Product_ID, b.Location_ID, b.Lot_Number, 
                        b.Expiry_Date, b.Quantity_Initial, b.Quantity_Current, 
                        b.Unit_Price_Received, b.Internal_Barcode, b.Status,
                        l.Location_Name, p.Product_Name, p.Stock_Unit
                    FROM Inventory_Batches b
                    JOIN Products_Master p ON b.Product_ID = p.Product_ID
                    LEFT JOIN Locations l ON b.Location_ID = l.Location_ID
                    WHERE b.Product_ID = %s AND b.Quantity_Current >= %s
                    ORDER BY b.Expiry_Date ASC
                """
                cursor.execute(query, (product_id, min_qty))
                return cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error(f"Error fetching batches: {e}")
            return []
            
    def adjust_batch_quantity(self, batch_id: int, quantity_change: int, movement_type: str, 
                               reason_id: Optional[int] = None, user_id: Optional[int] = None) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                conn.autocommit = False
                cursor = conn.cursor()
                
                cursor.execute("UPDATE Inventory_Batches SET Quantity_Current = Quantity_Current + %s WHERE Batch_ID = %s", 
                               (quantity_change, batch_id))
                
                if cursor.rowcount == 0: return False

                cursor.execute("SELECT Product_ID FROM Inventory_Batches WHERE Batch_ID = %s", (batch_id,))
                res = cursor.fetchone()
                if not res: return False
                product_id = res[0]

                insert_log_query = """
                    INSERT INTO Stock_Movement_Log 
                    (Product_ID, Batch_ID, Movement_Type, Reason_ID, Qty_Change, Unit_Used, User_ID, Transaction_Date)
                    VALUES (%s, %s, %s, %s, %s, 'Unit', %s, NOW())
                """
                cursor.execute(insert_log_query, (product_id, batch_id, movement_type, reason_id, quantity_change, user_id))
                
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error in adjust_batch_quantity: {e}")
            return False


    def get_batches_by_po_id(self, po_id: int) -> List[Dict]:
        """
        جلب جميع الباتشات المرتبطة بطلب شراء معين.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                # تم التحديث لجلب البيانات المالية أيضاً
                query = """
                    SELECT 
                        Product_ID, 
                        Quantity_Initial AS Received_Qty, 
                        Lot_Number, 
                        Expiry_Date, 
                        Location_ID,
                        Unit_Price_Received,
                        Tax_Rate_Percent,
                        Discount_Percent
                    FROM Inventory_Batches
                    WHERE PO_ID = %s
                """
                cursor.execute(query, (po_id,))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching batches for PO {po_id}: {e}")
            return []

    def open_pack_transaction(self, data: Dict, user_id: Optional[int] = None) -> bool:
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction(); cursor = conn.cursor()

            # خصم من المخزن المغلق
            cursor.execute("UPDATE Inventory_Batches SET Quantity_Current = Quantity_Current - %s WHERE Batch_ID = %s", 
                           (data['Qty_To_Open'], data['Batch_ID']))

            # إنشاء الحاوية المفتوحة (المنطق المختصر)
            # ... (كود Insert Active_Containers) ...
            container_id = cursor.lastrowid

            # [التصحيح]: تسجيل الحركة مع User_ID
            log_mov = """
                INSERT INTO Stock_Movement_Log 
                (Product_ID, Batch_ID, Container_ID, Movement_Type, Qty_Change, Unit_Used, User_ID, Transaction_Date)
                VALUES (%s, %s, %s, 'Open_Pack', %s, 'Stock_Unit', %s, NOW())
            """
            cursor.execute(log_mov, (data['Product_ID'], data['Batch_ID'], container_id, -int(data['Qty_To_Open']), user_id))

            conn.commit(); return True
        except Exception as e:
            if conn: conn.rollback()
            return False
        finally:
            if conn: conn.close()

    def direct_consume_batch_unit(self, batch_id: int, qty: int = 1, user_id: Optional[int] = None) -> bool:
        """
        تم تصحيح الخطأ Ambiguous Product_ID هنا عن طريق تحديد b.Product_ID
        """
        try:
            with self.db.get_db_connection() as conn:
                conn.autocommit = False 
                cursor = conn.cursor()
                
                # تصحيح SQL: تحديد p أو b لمنع الغموض
                query = """
                    SELECT b.Product_ID, p.Stock_Unit 
                    FROM Inventory_Batches b 
                    JOIN Products_Master p ON b.Product_ID = p.Product_ID 
                    WHERE b.Batch_ID = %s
                """
                cursor.execute(query, (batch_id,))
                res = cursor.fetchone()
                
                if not res:
                    logging.warning(f"Batch {batch_id} not found.")
                    return False
                
                product_id, unit_used = res
                
                # تنفيذ عملية الخصم
                update_query = """
                    UPDATE Inventory_Batches 
                    SET Quantity_Current = Quantity_Current - %s 
                    WHERE Batch_ID = %s AND Quantity_Current >= %s
                """
                cursor.execute(update_query, (qty, batch_id, qty))
                
                if cursor.rowcount == 0:
                    logging.warning(f"Insufficient quantity in batch {batch_id}")
                    return False

                # تسجيل الحركة في السجل
                self.stock_movement_log.create_movement_log(
                    product_id=product_id,
                    movement_type='Patient_Test',
                    qty_change=Decimal(str(-abs(qty))),
                    unit_used=unit_used if unit_used else 'Unit',
                    batch_id=batch_id,
                    user_id=user_id,
                    notes="Consommation Directe",
                    external_cursor=cursor
                )
                
                conn.commit()
                return True
                
        except Exception as e:
            logging.error(f"Error in direct_consume_batch_unit: {e}", exc_info=True)
            return False

            
    def transfer_batch_location(self, batch_id: int, new_location_id: int, qty: int, user_id: Optional[int] = None) -> bool:
        """
        نقل كمية من موقع لآخر مع إدارة دقيقة للاتصال (Context Manager Safe).
        """
        try:
            # 1. فتح الاتصال باستخدام Context Manager
            with self.db.get_db_connection() as conn:
                conn.autocommit = False # بدء المعاملة
                cursor = conn.cursor(dictionary=True)

                try:
                    # 1. جلب البيانات الأصلية وقفل السطر
                    cursor.execute("""
                        SELECT b.*, p.Stock_Unit 
                        FROM Inventory_Batches b 
                        JOIN Products_Master p ON b.Product_ID = p.Product_ID 
                        WHERE b.Batch_ID = %s FOR UPDATE
                    """, (batch_id,))
                    
                    original = cursor.fetchone()

                    if not original or float(original['Quantity_Current']) < qty:
                        logging.warning("Transfert échoué: Quantité insuffisante.")
                        conn.rollback()
                        return False

                    barcode = original['Internal_Barcode']
                    unit_label = original.get('Stock_Unit', 'U')

                    # 2. خصم الكمية من المصدر
                    cursor.execute("""
                        UPDATE Inventory_Batches 
                        SET Quantity_Current = Quantity_Current - %s 
                        WHERE Batch_ID = %s
                    """, (qty, batch_id))

                    # 3. معالجة الوجهة (دمج أو إنشاء)
                    cursor.execute("""
                        SELECT Batch_ID 
                        FROM Inventory_Batches 
                        WHERE Internal_Barcode = %s AND Location_ID = %s
                        LIMIT 1
                    """, (barcode, new_location_id))
                    
                    target_batch = cursor.fetchone()
                    final_target_id = None

                    if target_batch:
                        # دمج
                        final_target_id = target_batch['Batch_ID']
                        cursor.execute("""
                            UPDATE Inventory_Batches 
                            SET Quantity_Current = Quantity_Current + %s 
                            WHERE Batch_ID = %s
                        """, (qty, final_target_id))
                    else:
                        # إنشاء جديد
                        insert_query = """
                            INSERT INTO Inventory_Batches 
                            (Product_ID, Location_ID, Lot_Number, Expiry_Date, Quantity_Initial, 
                            Quantity_Current, PO_ID, BR_ID, Status, Internal_Barcode, 
                            Unit_Price_Received, Tax_Rate_Percent, Discount_Percent, Created_At)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Available', %s, %s, %s, %s, NOW())
                        """
                        params = (
                            original['Product_ID'], new_location_id, original['Lot_Number'], 
                            original['Expiry_Date'], qty, qty, original['PO_ID'], 
                            original['BR_ID'], barcode, # نفس الباركود
                            original['Unit_Price_Received'], original['Tax_Rate_Percent'], original['Discount_Percent']
                        )
                        cursor.execute(insert_query, params)
                        final_target_id = cursor.lastrowid

                    # 4. تسجيل الحركة (مع تمرير user_id)
                    self.stock_movement_log.create_movement_log(
                        product_id=original['Product_ID'],
                        movement_type='Transfer',
                        qty_change=Decimal(str(qty)),
                        unit_used=unit_label,
                        batch_id=final_target_id, 
                        user_id=user_id, # <--- هام جداً
                        notes=f"Transfert: Loc {original['Location_ID']} -> {new_location_id}",
                        external_cursor=cursor
                    )

                    conn.commit()
                    return True

                except Exception as inner_e:
                    conn.rollback()
                    logging.error(f"SQL Error in transfer: {inner_e}")
                    raise inner_e
                finally:
                    cursor.close() # إغلاق المؤشر دائماً

        except Exception as e:
            logging.error(f"Critical Error in transfer_batch_location: {e}", exc_info=True)
            return False

    def create_inventory_batch(self, product_id, br_id, lot_number, expiry_date, 
                               initial_stock_qty, location_id, date_received, 
                               po_id=None, unit_price=0.0, tax_rate=0.0, discount=0.0, 
                               item_index=1, internal_barcode=None, batch_id_override=None):
        """
        تم تحديث هذه الدالة لتكون آمنة مع القيود الجديدة.
        تقوم بإدراج دفعة جديدة، وإذا تم تمرير internal_barcode، تستخدمه.
        """
        conn = None
        try:
            conn = self.db.get_db_connection()
            conn.autocommit = False
            cursor = conn.cursor()

            # 1. توليد الباركود إذا لم يكن موجوداً
            final_barcode = internal_barcode
            if not final_barcode:
                prefix = po_id if po_id else (br_id if br_id else "STK")
                # دالة التوليد (تأكد من وجودها)
                final_barcode = self.generate_smart_barcode(prefix, item_index)

            # 2. التحقق مما إذا كان الباركود موجوداً في نفس الموقع (لتجنب الخطأ)
            cursor.execute("""
                SELECT Batch_ID FROM Inventory_Batches 
                WHERE Internal_Barcode = %s AND Location_ID = %s
            """, (final_barcode, location_id))
            
            existing = cursor.fetchone()
            if existing:
                # إذا وجدنا نفس الباركود في نفس الموقع، ندمج الكمية (في حالة الاستلام المتكرر)
                logging.info(f"Reception: Code-barres {final_barcode} existe déjà dans Loc {location_id}. Mise à jour de la quantité.")
                cursor.execute("""
                    UPDATE Inventory_Batches 
                    SET Quantity_Current = Quantity_Current + %s, Quantity_Initial = Quantity_Initial + %s
                    WHERE Batch_ID = %s
                """, (initial_stock_qty, initial_stock_qty, existing[0]))
                batch_id = existing[0]
            else:
                # إنشاء سطر جديد
                query = """
                    INSERT INTO Inventory_Batches 
                    (Product_ID, Location_ID, Lot_Number, Expiry_Date, 
                    Quantity_Initial, Quantity_Current, PO_ID, BR_ID, Status, Created_At,
                    Unit_Price_Received, Tax_Rate_Percent, Discount_Percent, Internal_Barcode) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Available', %s, %s, %s, %s, %s)
                """
                params = (product_id, location_id, lot_number, expiry_date, 
                        initial_stock_qty, initial_stock_qty, po_id, br_id, 
                        date_received, unit_price, tax_rate, discount, final_barcode)
                
                cursor.execute(query, params)
                batch_id = cursor.lastrowid 

            conn.commit()
            return batch_id

        except mysql.connector.Error as err:
            if conn: conn.rollback()
            logging.error(f"Database error in create_inventory_batch: {err}")
            return None
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
    @staticmethod
    def generate_smart_barcode(prefix, item_serial):
        """
        توليد باركود يعتمد على المعرف (PO_ID) + تسلسل.
        مثال: PO 252, Item 1 -> 252001
        """
        try:
            serial_formatted = str(item_serial).zfill(3)
            return f"{prefix}{serial_formatted}"
        except:
            current_year = datetime.now().strftime('%y')
            return f"{current_year}{item_serial}"
    

    def process_full_reception(self, header_data, items, user_id=None):
        """
        معالجة عملية استلام كاملة مع تسجيل معرف المستخدم.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()

                # 1. إنشاء رأس الاستلام (Header) مع ربطه بالمستخدم (Received_By)
                query_header = """
                    INSERT INTO Reception_Log 
                    (PO_ID, Supplier_ID, Supplier_Invoice_Ref, Supplier_BL_Ref, Document_Type, 
                    Reception_Date, Invoice_Total_HT, Invoice_Total_TVA, Invoice_Total_TTC, Total_Discount, Received_By)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query_header, (
                    header_data['PO_ID'], header_data['Supplier_ID'], header_data['Supplier_Invoice_Ref'],
                    header_data['Supplier_BL_Ref'], header_data['Document_Type'], header_data['Reception_Date'],
                    header_data['Invoice_Total_HT'], header_data['Invoice_Total_TVA'],
                    header_data['Invoice_Total_TTC'], header_data['Total_Discount'],
                    user_id  # تم إضافة تمرير المعرف هنا لقاعدة البيانات
                ))
                receipt_id = cursor.lastrowid

                # 2. إنشاء أسطر الدفعات (Batches)
                for item in items:
                    query_batch = """
                        INSERT INTO Inventory_Batches 
                        (Product_ID, Location_ID, Lot_Number, Expiry_Date, Quantity_Initial, 
                        Quantity_Current, Unit_Price_Received, Internal_Barcode, Stock_Unit, BR_ID, PO_ID)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(query_batch, (
                        item['Product_ID'], item['Location_ID'], item['Lot_Number'], item['Expiry_Date'],
                        item['Qty_Received'], item['Qty_Received'], item['Unit_Price_Received'],
                        item['Internal_Barcode'], item['Unit_Label'], receipt_id, header_data['PO_ID']
                    ))
                    batch_id = cursor.lastrowid

                    # 3. تسجيل الحركة في السجل التاريخي مع ربطها بالمستخدم
                    self.stock_movement_log.create_movement_log(
                        product_id=item['Product_ID'],
                        movement_type='Purchase_Receive',
                        qty_change=Decimal(str(item['Qty_Received'])),
                        unit_used=item['Unit_Label'],
                        batch_id=batch_id,
                        user_id=user_id,  # تمرير المعرف لحل مشكلة "System"
                        notes=f"Réception PO #{header_data['PO_ID']} - Ref: {header_data['Supplier_Invoice_Ref']}",
                        external_cursor=cursor
                    )

                conn.commit()
                return True, "Réception enregistrée avec succès."

        except Exception as e:
            if 'conn' in locals(): conn.rollback()
            logging.error(f"Erreur lors de la réception: {e}")
            return False, str(e)

    def get_all_batches_with_details(self, include_zero_stock=False) -> List[Dict]:
        """
        جلب جميع الدفعات مع تفاصيل المنتج والمورد (تم تصحيح جلب اسم المورد).
        """
        try:
            with self.db.get_db_connection() as conn:
                # التأكد من تحديث البيانات
                if conn.is_connected():
                    conn.commit() 

                cursor = conn.cursor(dictionary=True)
                
                # شرط استبعاد المنتجات المحذوفة
                where_clauses = ["P.Deleted_At IS NULL"] 
                
                if not include_zero_stock:
                    where_clauses.append("B.Quantity_Current > 0")
                
                where_str = " WHERE " + " AND ".join(where_clauses)
                
                # --- التعديل الجوهري في الاستعلام (JOIN) ---
                # نربط مع Reception_Log (RL) ثم مع Suppliers (S) لضمان ظهور المورد
                query = f"""
                    SELECT 
                        B.Batch_ID,
                        B.Product_ID,
                        P.Is_Billable,
                        B.Internal_Barcode,
                        P.Product_Name,
                        P.Manuf_Cat_No,
                        F.Family_Name,
                        P.Family_ID,
                        IFNULL(A.Automate_Name, 'Général') AS Automate_Name,
                        M.Manuf_Name,  
                        
                        -- جلب اسم المورد بدقة: الأولوية للمربوط بالاستلام، ثم المربوط بالطلب
                        COALESCE(S_RL.Supplier_Name, S_PO.Supplier_Name, '---') AS Supplier_Name,
                        
                        P.Manuf_ID,
                        P.Preferred_Automate_ID,
                        P.Minimum_Stock_Level,       
                        P.Alert_Before_Expiry_Days,
                        B.Lot_Number,
                        B.Expiry_Date,
                        B.Quantity_Current,
                        B.Quantity_Initial,
                        B.Unit_Price_Received,
                        B.Tax_Rate_Percent,
                        B.Discount_Percent,
                        P.Stock_Unit,
                        P.Barcode,
                        L.Location_Name,
                        B.Location_ID,
                        B.PO_ID,
                        B.BR_ID,
                        B.Status,
                        B.Created_At AS Date_Received
                    FROM 
                        Inventory_Batches B
                    INNER JOIN 
                        Products_Master P ON B.Product_ID = P.Product_ID
                    LEFT JOIN 
                        Product_Families F ON P.Family_ID = F.Family_ID
                    LEFT JOIN 
                        Manufacturers M ON P.Manuf_ID = M.Manuf_ID
                    LEFT JOIN 
                        Automates A ON P.Preferred_Automate_ID = A.Automate_ID
                    LEFT JOIN 
                        Locations L ON B.Location_ID = L.Location_ID
                    
                    -- الربط مع سجل الاستلام لجلب المورد
                    LEFT JOIN
                        Reception_Log RL ON B.BR_ID = RL.BR_ID
                    LEFT JOIN
                        Suppliers S_RL ON RL.Supplier_ID = S_RL.Supplier_ID
                        
                    -- الربط مع أمر الشراء (كخطة بديلة)
                    LEFT JOIN
                        Purchase_Orders PO ON B.PO_ID = PO.PO_ID
                    LEFT JOIN
                        Suppliers S_PO ON PO.Supplier_ID = S_PO.Supplier_ID
                    
                    {where_str}
                    
                    ORDER BY 
                        B.Quantity_Current > 0 DESC,
                        P.Product_Name ASC, 
                        B.Expiry_Date ASC;
                """
                
                cursor.execute(query)
                return cursor.fetchall()
                
        except Exception as e:
            logging.error(f"Error fetching all batches with details: {e}")
            return []
        
    def get_product_pricing_info(self):
        """
        جلب معلومات التسعير لكل منتج بناءً على المخزون الحالي.
        يحسب متوسط السعر المرجح (CUMP) للدفعات المتوفرة.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        Product_ID, 
                        SUM(Quantity_Current * Unit_Price_Received) / NULLIF(SUM(Quantity_Current), 0) as Avg_Price
                    FROM Inventory_Batches
                    WHERE Quantity_Current > 0
                    GROUP BY Product_ID
                """
                cursor.execute(query)
                return {row['Product_ID']: row['Avg_Price'] for row in cursor.fetchall()}
        except Exception as e:
            logging.error(f"Error calculating product pricing: {e}")
            return {}
        
    def get_products_stock_levels(self) -> Dict[int, float]:
        """
        جلب إجمالي المخزون المتوفر لكل منتج (مجموع الكميات في الدفعات الحالية).
        Returns: {Product_ID: Total_Quantity}
        """
        stock_map = {}
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                # نجمع الكميات للدفعات التي بها رصيد فقط
                query = """
                    SELECT Product_ID, SUM(Quantity_Current) 
                    FROM Inventory_Batches 
                    WHERE Quantity_Current > 0 
                    GROUP BY Product_ID
                """
                cursor.execute(query)
                results = cursor.fetchall()
                
                for row in results:
                    # row[0] = Product_ID, row[1] = Sum(Quantity)
                    stock_map[row[0]] = float(row[1])
                    
        except Exception as e:
            logging.error(f"Error fetching stock levels: {e}")
        
        return stock_map