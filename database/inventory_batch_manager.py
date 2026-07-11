# database/inventory_batch_manager.py

import mysql.connector
import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
from decimal import Decimal

from .system_logger import log_methods 

@log_methods()
class InventoryBatchManager:
    """
    إدارة عمليات جدول دفعات المخزون (Inventory_Batches).
    """

    def __init__(self, db_instance):
        from .stock_movement_log_manager import StockMovementLogManager  # Add this import

        self.db = db_instance
        self.stock_movement_log = StockMovementLogManager(db_instance)

    @staticmethod
    def get_barcode_prefix_for_po(po_id):
        """
        Return the legacy reception barcode prefix.

        PO_ID already contains the two-digit year and the annual order number
        (example: 2618 for order 18 in 2026). Reception barcodes therefore use
        PO_ID + a zero-padded serial: 2618001, 2618002, ...
        """
        po_text = str(po_id or "").strip()
        if po_text and po_text != "0":
            return po_text
        return datetime.now().strftime('%y')

    @staticmethod
    def extract_smart_barcode_serial(barcode, prefix):
        barcode_text = str(barcode or "")
        prefix_text = str(prefix or "")
        if not prefix_text or not barcode_text.startswith(prefix_text):
            return None

        serial_text = barcode_text[len(prefix_text):]
        if not serial_text.isdigit():
            return None
        return int(serial_text)


    def _create_inventory_batch_legacy(self, product_id, br_id, lot_number, expiry_date, 
                               initial_stock_qty, location_id, date_received, 
                               po_id=None, unit_price=0.0, tax_rate=0.0, discount=0.0, 
                               item_index=1, internal_barcode=None):
        """
        تم دمج التعريفين في تعريف واحد قوي.
        """
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()

            final_barcode = internal_barcode
            if not final_barcode:
                prefix = self.get_barcode_prefix_for_po(po_id) if po_id else (f"BR{br_id}-" if br_id else "STK")
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

    def _get_next_smart_barcode_legacy(self, po_id):
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

    def _get_next_reception_barcode_legacy(self, br_id):
        """
        Generate a barcode in the scope of one reception voucher.

        A PO can have multiple BRs. Keeping the serial scoped to BR_ID prevents
        two reception vouchers for the same PO from competing for the same
        barcode sequence.
        """
        prefix = f"BR{br_id}-"

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT Internal_Barcode
                    FROM Inventory_Batches
                    WHERE BR_ID = %s AND Internal_Barcode LIKE %s
                    """,
                    (br_id, f"{prefix}%")
                )

                max_serial = 0
                for row in cursor.fetchall():
                    barcode = row[0]
                    if not barcode:
                        continue
                    try:
                        serial = int(str(barcode)[len(prefix):])
                        max_serial = max(max_serial, serial)
                    except (TypeError, ValueError):
                        continue

                next_serial = max_serial + 1
                next_barcode = self.generate_smart_barcode(prefix, next_serial)

                while self.is_barcode_exists_in_db(next_barcode):
                    next_serial += 1
                    next_barcode = self.generate_smart_barcode(prefix, next_serial)

                return next_barcode

        except Exception as e:
            logging.error(f"Error getting next reception barcode: {e}")
            return self.generate_smart_barcode(prefix, 1)

    def get_next_smart_barcode(self, po_id):
        """Return the next legacy barcode for a purchase order: PO_ID + 001."""
        prefix = self.get_barcode_prefix_for_po(po_id)
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT Internal_Barcode FROM Inventory_Batches WHERE Internal_Barcode LIKE %s",
                    (f"{prefix}%",)
                )

                max_serial = 0
                for row in cursor.fetchall():
                    barcode = row[0] if row else None
                    serial = self.extract_smart_barcode_serial(barcode, prefix)
                    if serial is not None:
                        max_serial = max(max_serial, serial)

                next_serial = max_serial + 1
                next_barcode = self.generate_smart_barcode(prefix, next_serial)
                while self.is_barcode_exists_in_db(next_barcode):
                    next_serial += 1
                    next_barcode = self.generate_smart_barcode(prefix, next_serial)
                return next_barcode

        except Exception as e:
            logging.error(f"Error getting next barcode: {e}")
            return self.generate_smart_barcode(prefix, 1)

    def get_next_reception_barcode(self, br_id, po_id=None):
        """
        Return the next barcode for a reception while preserving the old shape.

        The serial is first based on existing rows in the current BR, then it
        skips any value already used anywhere in Inventory_Batches. This keeps
        BR editing stable and prevents collisions across multiple BRs for the
        same PO.
        """
        prefix = None
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                if not po_id and br_id:
                    cursor.execute("SELECT PO_ID FROM Reception_Log WHERE BR_ID = %s", (br_id,))
                    row = cursor.fetchone()
                    po_id = row[0] if row else None

                prefix = self.get_barcode_prefix_for_po(po_id) if po_id else f"BR{br_id}-"
                cursor.execute(
                    """
                    SELECT Internal_Barcode
                    FROM Inventory_Batches
                    WHERE BR_ID = %s AND Internal_Barcode LIKE %s
                    """,
                    (br_id, f"{prefix}%")
                )

                max_serial = 0
                for row in cursor.fetchall():
                    barcode = row[0] if row else None
                    serial = self.extract_smart_barcode_serial(barcode, prefix)
                    if serial is not None:
                        max_serial = max(max_serial, serial)

                next_serial = max_serial + 1
                next_barcode = self.generate_smart_barcode(prefix, next_serial)
                while self.is_barcode_exists_in_db(next_barcode):
                    next_serial += 1
                    next_barcode = self.generate_smart_barcode(prefix, next_serial)
                return next_barcode

        except Exception as e:
            logging.error(f"Error getting next reception barcode: {e}")
            if not prefix:
                prefix = self.get_barcode_prefix_for_po(po_id) if po_id else f"BR{br_id}-"
            return self.generate_smart_barcode(prefix, 1)

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

    def update_batch_reception_note(self, batch_id: int, note: str) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE Inventory_Batches SET Reception_Note = %s WHERE Batch_ID = %s",
                    (note, batch_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Error updating reception note for batch {batch_id}: {e}")
            return False

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
            change = Decimal(str(quantity_change))
            with self.db.get_db_connection() as conn:
                conn.autocommit = False
                cursor = conn.cursor(dictionary=True)
                
                cursor.execute(
                    """
                    SELECT b.Product_ID, b.Quantity_Current, p.Stock_Unit
                    FROM Inventory_Batches b
                    LEFT JOIN Products_Master p ON b.Product_ID = p.Product_ID
                    WHERE b.Batch_ID = %s
                    FOR UPDATE
                    """,
                    (batch_id,)
                )
                res = cursor.fetchone()
                if not res:
                    conn.rollback()
                    return False
                product_id = res['Product_ID']
                new_quantity = Decimal(str(res['Quantity_Current'])) + change
                if new_quantity < 0:
                    conn.rollback()
                    return False

                cursor.execute("""
                    UPDATE Inventory_Batches
                    SET Quantity_Current = %s,
                        Status = CASE
                            WHEN %s = 0 THEN 'Depleted'
                            WHEN Status = 'Depleted' THEN 'Available'
                            ELSE Status
                        END
                    WHERE Batch_ID = %s
                """, (new_quantity, new_quantity, batch_id))

                movement_id = self.stock_movement_log.create_movement_log(
                    product_id=product_id,
                    movement_type=movement_type,
                    qty_change=change,
                    unit_used=res.get('Stock_Unit') or 'Unit',
                    batch_id=batch_id,
                    reason_id=reason_id,
                    user_id=user_id,
                    external_cursor=cursor
                )
                if not movement_id:
                    conn.rollback()
                    return False
                
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
        cursor = None
        try:
            qty_to_open = Decimal(str(data.get('Qty_To_Open', 0)))
            if qty_to_open <= 0:
                return False

            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("""
                SELECT b.Product_ID, b.Quantity_Current, b.Expiry_Date, b.Location_ID,
                       p.Open_Vial_Stability_Days, p.Stock_Unit
                FROM Inventory_Batches b
                JOIN Products_Master p ON b.Product_ID = p.Product_ID
                WHERE b.Batch_ID = %s
                FOR UPDATE
            """, (data['Batch_ID'],))
            batch = cursor.fetchone()
            if not batch or Decimal(str(batch['Quantity_Current'])) < qty_to_open:
                conn.rollback()
                return False

            open_expiry = data.get('Calculated_Open_Expiry')
            if not open_expiry:
                official_expiry = batch.get('Expiry_Date')
                if isinstance(official_expiry, datetime):
                    official_expiry = official_expiry.date()
                elif isinstance(official_expiry, str):
                    try:
                        official_expiry = datetime.strptime(official_expiry[:10], "%Y-%m-%d").date()
                    except ValueError:
                        official_expiry = None

                stability_days = int(batch.get('Open_Vial_Stability_Days') or 30)
                calculated_expiry = date.today() + timedelta(days=stability_days)
                open_expiry = min(official_expiry, calculated_expiry) if official_expiry else calculated_expiry

            # خصم من المخزن المغلق
            new_parent_qty = Decimal(str(batch['Quantity_Current'])) - qty_to_open
            parent_status = 'Depleted' if new_parent_qty <= 0 else batch.get('Status', 'Available')
            cursor.execute("""
                UPDATE Inventory_Batches
                SET Quantity_Current = %s,
                    Status = %s
                WHERE Batch_ID = %s
            """, (new_parent_qty, parent_status, data['Batch_ID']))

            # إنشاء الحاوية المفتوحة (المنطق المختصر)
            cursor.execute("""
                INSERT INTO Active_Containers
                (Parent_Batch_ID, Product_ID, Date_Opened, Open_Expiration_Date,
                 Initial_Usage_Qty, Remaining_Usage_Qty, Current_Location_ID, Status)
                VALUES (%s, %s, NOW(), %s, %s, %s, %s, 'In_Use')
            """, (
                data['Batch_ID'],
                batch['Product_ID'],
                open_expiry,
                qty_to_open,
                qty_to_open,
                data.get('Current_Location_ID') or batch.get('Location_ID')
            ))
            container_id = cursor.lastrowid

            # [التصحيح]: تسجيل الحركة مع User_ID
            movement_id = self.stock_movement_log.create_movement_log(
                product_id=batch['Product_ID'],
                movement_type='Open_Pack',
                qty_change=-abs(qty_to_open),
                unit_used=batch.get('Stock_Unit') or 'Stock_Unit',
                batch_id=data['Batch_ID'],
                container_id=container_id,
                user_id=user_id,
                notes="Ouverture de paquet",
                external_cursor=cursor
            )
            if not movement_id:
                conn.rollback()
                return False

            conn.commit(); return True
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Error in open_pack_transaction: {e}", exc_info=True)
            return False
        finally:
            if conn and conn.is_connected():
                if cursor:
                    cursor.close()
                conn.close()

    def direct_consume_batch_unit(self, batch_id: int, qty: int = 1, user_id: Optional[int] = None) -> bool:
        """
        تم تصحيح الخطأ Ambiguous Product_ID هنا عن طريق تحديد b.Product_ID
        """
        qty_to_consume = Decimal(str(qty))
        if qty_to_consume <= 0:
            return False

        try:
            with self.db.get_db_connection() as conn:
                conn.autocommit = False 
                cursor = conn.cursor()
                
                # تصحيح SQL: تحديد p أو b لمنع الغموض
                query = """
                    SELECT b.Product_ID, b.Quantity_Current, b.Status, p.Stock_Unit
                    FROM Inventory_Batches b 
                    JOIN Products_Master p ON b.Product_ID = p.Product_ID 
                    WHERE b.Batch_ID = %s
                    FOR UPDATE
                """
                cursor.execute(query, (batch_id,))
                res = cursor.fetchone()
                
                if not res:
                    logging.warning(f"Batch {batch_id} not found.")
                    conn.rollback()
                    return False
                
                product_id, current_qty, current_status, unit_used = res
                current_qty = Decimal(str(current_qty))
                if current_qty < qty_to_consume:
                    logging.warning(f"Insufficient quantity in batch {batch_id}")
                    conn.rollback()
                    return False
                
                # تنفيذ عملية الخصم
                new_qty = current_qty - qty_to_consume
                new_status = 'Depleted' if new_qty <= 0 else current_status
                update_query = """
                    UPDATE Inventory_Batches 
                    SET Quantity_Current = %s,
                        Status = %s
                    WHERE Batch_ID = %s
                """
                cursor.execute(update_query, (new_qty, new_status, batch_id))
                
                if cursor.rowcount == 0:
                    logging.warning(f"Insufficient quantity in batch {batch_id}")
                    conn.rollback()
                    return False

                # تسجيل الحركة في السجل
                movement_id = self.stock_movement_log.create_movement_log(
                    product_id=product_id,
                    movement_type='Patient_Test',
                    qty_change=-abs(qty_to_consume),
                    unit_used=unit_used if unit_used else 'Unit',
                    batch_id=batch_id,
                    user_id=user_id,
                    notes="Consommation Directe",
                    external_cursor=cursor
                )
                if not movement_id:
                    conn.rollback()
                    return False
                
                conn.commit()
                return True
                
        except Exception as e:
            logging.error(f"Error in direct_consume_batch_unit: {e}", exc_info=True)
            return False

    def _transfer_barcode_for_location(self, cursor, source_barcode, source_batch_id, target_location_id):
        stem = str(source_barcode or f"B{source_batch_id}").strip() or f"B{source_batch_id}"
        base = f"{stem}-L{target_location_id}"
        candidate = base[:50]
        serial = 1

        cursor.execute(
            """
            SELECT Internal_Barcode
            FROM Inventory_Batches
            WHERE Internal_Barcode = %s AND Location_ID = %s
            LIMIT 1
            """,
            (candidate, target_location_id)
        )
        existing_target = cursor.fetchone()
        if existing_target:
            if isinstance(existing_target, dict):
                return existing_target['Internal_Barcode']
            return existing_target[0]

        while True:
            cursor.execute(
                "SELECT Batch_ID FROM Inventory_Batches WHERE Internal_Barcode = %s LIMIT 1",
                (candidate,)
            )
            if not cursor.fetchone():
                return candidate

            suffix = f"-{serial}"
            candidate = f"{base[:50 - len(suffix)]}{suffix}"
            serial += 1

    def transfer_batch_location(self, batch_id: int, new_location_id: int, qty: int, user_id: Optional[int] = None) -> bool:
        """
        نقل كمية من موقع لآخر مع الحفاظ على الكود بار الأصلي والكمية الابتدائية.
        """
        if qty <= 0:
            return False

        try:
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

                    if int(original['Location_ID']) == int(new_location_id):
                        conn.rollback()
                        return False

                    # تعديل: استخدام الكود بار الأصلي مباشرة دون إضافة لاحقة الموقع
                    target_barcode = original['Internal_Barcode']
                    unit_label = original.get('Stock_Unit', 'U')

                    # 2. خصم الكمية من المصدر
                    source_new_qty = Decimal(str(original['Quantity_Current'])) - Decimal(str(qty))
                    source_status = 'Depleted' if source_new_qty <= 0 else original.get('Status', 'Available')
                    cursor.execute("""
                        UPDATE Inventory_Batches 
                        SET Quantity_Current = %s,
                            Status = %s
                        WHERE Batch_ID = %s
                    """, (source_new_qty, source_status, batch_id))

                    # 3. معالجة الوجهة (دمج أو إنشاء)
                    cursor.execute("""
                        SELECT Batch_ID 
                        FROM Inventory_Batches 
                        WHERE Internal_Barcode = %s AND Location_ID = %s
                        LIMIT 1 FOR UPDATE
                    """, (target_barcode, new_location_id))
                    
                    target_batch = cursor.fetchone()
                    final_target_id = None

                    if target_batch:
                        # دمج الكمية إذا كان المنتج موجوداً مسبقاً بنفس الكود بار في الموقع الجديد
                        final_target_id = target_batch['Batch_ID']
                        cursor.execute("""
                            UPDATE Inventory_Batches 
                            SET Quantity_Current = Quantity_Current + %s,
                                Status = CASE WHEN Status = 'Depleted' THEN 'Available' ELSE Status END
                            WHERE Batch_ID = %s
                        """, (qty, final_target_id))
                    else:
                        insert_query = """
                            INSERT INTO Inventory_Batches 
                            (Product_ID, Location_ID, Lot_Number, Expiry_Date, Quantity_Initial, 
                            Quantity_Current, PO_ID, BR_ID, Status, Internal_Barcode, 
                            Unit_Price_Received, Tax_Rate_Percent, Discount_Percent, Reception_Note, Created_At)
                            VALUES (%s, %s, %s, %s, 0, %s, %s, %s, 'Available', %s, %s, %s, %s, %s, NOW())
                        """
                        params = (
                            original['Product_ID'],
                            new_location_id,
                            original['Lot_Number'],
                            original['Expiry_Date'],
                            qty,  # هذه تعود لـ Quantity_Current
                            original['PO_ID'],
                            original['BR_ID'],
                            target_barcode,
                            original['Unit_Price_Received'],
                            original['Tax_Rate_Percent'],
                            original['Discount_Percent'],
                            original.get('Reception_Note', '')
                        )

                        cursor.execute(insert_query, params)
                        final_target_id = cursor.lastrowid

                    # 4. تسجيل الحركة في السجل
                    source_movement_id = self.stock_movement_log.create_movement_log(
                        product_id=original['Product_ID'],
                        movement_type='Transfer',
                        qty_change=Decimal(str(-abs(qty))),
                        unit_used=unit_label,
                        batch_id=batch_id,
                        user_id=user_id,
                        notes=f"Transfert: Loc {original['Location_ID']} -> {new_location_id}",
                        external_cursor=cursor
                    )

                    target_movement_id = self.stock_movement_log.create_movement_log(
                        product_id=original['Product_ID'],
                        movement_type='Transfer',
                        qty_change=Decimal(str(qty)),
                        unit_used=unit_label,
                        batch_id=final_target_id, 
                        user_id=user_id,
                        notes=f"Transfert: Loc {original['Location_ID']} -> {new_location_id}",
                        external_cursor=cursor
                    )
                    if not source_movement_id or not target_movement_id:
                        conn.rollback()
                        return False

                    conn.commit()
                    return True

                except Exception as inner_e:
                    conn.rollback()
                    logging.error(f"SQL Error in transfer: {inner_e}")
                    raise inner_e
                finally:
                    cursor.close()

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
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()

            # 1. توليد الباركود إذا لم يكن موجوداً
            prefix = self.get_barcode_prefix_for_po(po_id) if po_id else (f"BR{br_id}-" if br_id else "STK")
            final_barcode = internal_barcode
            barcode_was_provided = bool(final_barcode)
            if not final_barcode:
                # دالة التوليد (تأكد من وجودها)
                final_barcode = self.generate_smart_barcode(prefix, item_index)

            cursor.execute("""
                SELECT Batch_ID, Location_ID
                FROM Inventory_Batches
                WHERE Internal_Barcode = %s
                LIMIT 1
            """, (final_barcode,))
            barcode_owner = cursor.fetchone()
            if barcode_owner and int(barcode_owner[1]) != int(location_id) and not barcode_was_provided:
                next_serial = item_index + 1
                while True:
                    candidate = self.generate_smart_barcode(prefix, next_serial)
                    cursor.execute(
                        "SELECT Batch_ID FROM Inventory_Batches WHERE Internal_Barcode = %s LIMIT 1",
                        (candidate,)
                    )
                    if not cursor.fetchone():
                        final_barcode = candidate
                        break
                    next_serial += 1

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
        from .reception_log_manager import ReceptionLogManager
        return ReceptionLogManager(self.db).process_full_reception(
            header_data, items, user_id=user_id
        )

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
                        (
                            SELECT SUM(IB2.Quantity_Initial)
                            FROM Inventory_Batches IB2
                            WHERE IB2.Internal_Barcode = B.Internal_Barcode
                        ) AS Quantity_Initial,
                        B.Quantity_Initial AS Reception_Quantity_Initial,
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
                        B.Created_At AS Date_Received,
                        B.Reception_Note
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
