# database/purchase_order_manager.py

import mysql.connector
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Any
from .system_logger import log_methods 

@log_methods()
class PurchaseOrderManager:
    def __init__(self, db_instance):
        self.db = db_instance

    def generate_custom_po_id(self) -> Optional[int]:
        """
        توليد رقم طلب بصيغة YY + SequentialNumber يتجدد سنوياً.
        مثال: سنة 2025 -> 251, 252 ... 2510, 2511
        """
        current_year_prefix = datetime.now().strftime('%y') 
        
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                query = "SELECT MAX(PO_ID) FROM Purchase_Orders WHERE CAST(PO_ID AS CHAR) LIKE %s"
                cursor.execute(query, (f"{current_year_prefix}%",))
                max_id = cursor.fetchone()[0]
                
                if max_id:
                    str_max_id = str(max_id)
                    serial_part = str_max_id[2:]
                    
                    if serial_part == "": 
                        new_serial = 1
                    else:
                        new_serial = int(serial_part) + 1
                else:
                    new_serial = 1
                
                return int(f"{current_year_prefix}{new_serial}")
                
        except Exception as e:
            logging.error(f"Erreur lors de la génération du PO_ID annuel: {e}")
            import random
            return int(f"{current_year_prefix}{random.randint(100, 999)}")
        
    def create_po_header(self, header_data: Dict) -> Optional[int]:
        """إنشاء رأس الطلب فقط."""
        po_id = self.generate_custom_po_id()
        if not po_id: return None
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Purchase_Orders 
                    (PO_ID, Supplier_ID, Order_Date, Expected_Delivery_Date, Notes, Status, Created_By) 
                    VALUES (%s, %s, %s, %s, %s, 'Draft', %s)
                """
                cursor.execute(query, (
                    po_id, 
                    header_data['Supplier_ID'], 
                    header_data['Order_Date'], 
                    header_data.get('Expected_Delivery_Date'), 
                    header_data.get('Notes'),
                    header_data.get('Created_By') # تأكد من تمرير user_id
                ))
                conn.commit()
                return po_id
        except Exception as e:
            logging.error(f"Error creating PO header: {e}")
            return None
        
    def update_po_header(self, po_id: int, header_data: Dict) -> bool:
        """تحديث معلومات رأس الطلب."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    UPDATE Purchase_Orders 
                    SET Supplier_ID=%s, Order_Date=%s, Expected_Delivery_Date=%s, Notes=%s
                    WHERE PO_ID=%s
                """
                cursor.execute(query, (
                    header_data['Supplier_ID'], 
                    header_data['Order_Date'], 
                    header_data.get('Expected_Delivery_Date'), 
                    header_data.get('Notes'), 
                    po_id
                ))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error updating PO header: {e}")
            return False
        

    def add_po_line(self, po_id: int, item_data: Dict) -> bool:
        """إضافة سطر منتج للطلب."""
        try:
            with self.db.get_db_connection() as conn:
                if conn is None:
                    return False
                cursor = conn.cursor()
                query = """
                    INSERT INTO PO_Details 
                    (PO_ID, Product_ID, Qty_Ordered, Ordering_Unit, Item_Note, Unit_Price_HT)
                    VALUES (%s, %s, %s, %s, %s, 0)
                """
                cursor.execute(query, (
                    po_id, 
                    item_data['Product_ID'], 
                    item_data['Qty_Ordered'], 
                    item_data['Ordering_Unit'], 
                    item_data.get('Item_Note', '')
                ))
                conn.commit()
                self._recalculate_po_totals(None, po_id) # تحديث الإجماليات (ولو أنها 0 حالياً)
                return True
        except Exception as e:
            logging.error(f"Error adding PO line: {e}")
            return False
        

    def update_po_line(self, detail_id: int, item_data: Dict) -> bool:
        """تحديث سطر منتج موجود."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    UPDATE PO_Details 
                    SET Qty_Ordered=%s, Ordering_Unit=%s, Item_Note=%s
                    WHERE ID=%s
                """
                cursor.execute(query, (
                    item_data['Qty_Ordered'], 
                    item_data['Ordering_Unit'], 
                    item_data.get('Item_Note', ''), 
                    detail_id
                ))
                conn.commit()
                # نحتاج لمعرفة po_id لتحديث المجموع، يمكن جلبه أو تمريره
                return True
        except Exception as e:
            logging.error(f"Error updating PO line: {e}")
            return False

    def delete_po_line(self, detail_id: int) -> bool:
        """حذف سطر."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM PO_Details WHERE ID = %s", (detail_id,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error deleting PO line: {e}")
            return False

    def create_purchase_order(self, supplier_id: int, order_date: Any, expected_delivery_date: Optional[Any] = None, notes: Optional[str] = None) -> Optional[int]:
        new_po_id = self.generate_custom_po_id()
        if not new_po_id: return None
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """INSERT INTO Purchase_Orders (PO_ID, Supplier_ID, Order_Date, Expected_Delivery_Date, Notes, Status) 
                           VALUES (%s, %s, %s, %s, %s, 'Draft')"""
                cursor.execute(query, (new_po_id, supplier_id, order_date, expected_delivery_date, notes))
                conn.commit()
                return new_po_id
        except Exception as err:
            logging.error(f"Erreur DB: {err}")
            return None

    def get_all_purchase_orders(self, months: int = 6, start_date=None, end_date=None) -> List[Dict]:
        """
        جلب أوامر الشراء.
        - يدعم الفلترة بنطاق تاريخ محدد (start_date, end_date).
        - يدعم الفلترة بعدد الأشهر (months) للتوافق مع الكود القديم.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                query = """
                    SELECT 
                        po.PO_ID, 
                        po.Order_Date, 
                        po.Expected_Delivery_Date, 
                        po.Status, 
                        po.Notes,
                        s.Supplier_Name,
                        COALESCE((
                            SELECT SUM(Line_Total_TTC) 
                            FROM PO_Details 
                            WHERE PO_ID = po.PO_ID
                        ), 0) as Total_Amount_TTC
                    FROM Purchase_Orders po
                    LEFT JOIN Suppliers s ON po.Supplier_ID = s.Supplier_ID
                    WHERE po.Deleted_At IS NULL
                """
                
                params = []
                
                if start_date and end_date:
                    query += " AND po.Order_Date BETWEEN %s AND %s"
                    params.extend([start_date, end_date])
                
                elif months is not None:
                    query += " AND po.Order_Date >= DATE_SUB(CURDATE(), INTERVAL %s MONTH)"
                    params.append(months)
                
                query += " ORDER BY po.PO_ID DESC"
                
                cursor.execute(query, tuple(params))
                return cursor.fetchall()
                
        except Exception as e:
            logging.error(f"Error fetching POs: {e}")
            return []
        
        
    def get_full_order_details(self, po_id: int) -> Optional[Dict]:
        """جلب بيانات الطلب والمنتجات والماركات والملاحظات (تم التعديل لجلب الوحدة المحفوظة)."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # 1. جلب الرأس
                query_header = """
                    SELECT po.*, s.Supplier_Name 
                    FROM Purchase_Orders po
                    LEFT JOIN Suppliers s ON po.Supplier_ID = s.Supplier_ID
                    WHERE po.PO_ID = %s
                """
                cursor.execute(query_header, (po_id,))
                header = cursor.fetchone()
                if not header: return None

                # 2. جلب التفاصيل مع دمج الماركة (Brand) وملاحظة السطر (Item_Note)
                # [FIX] نستخدم COALESCE لإعطاء الأولوية للوحدة المحفوظة في السطر (pd.Ordering_Unit)
                # فإذا كانت NULL (للطلبات القديمة) نعود للوحدة الافتراضية للمنتج (p.Ordering_Unit)
                query_details = """
                    SELECT 
                        pd.ID, pd.PO_ID, pd.Product_ID, pd.Qty_Ordered, 
                        pd.Unit_Price_HT, pd.Discount_Percent, pd.Tax_Rate_Percent, 
                        pd.Line_Total_HT, pd.Line_Total_TTC, pd.Item_Note,
                        
                        COALESCE(pd.Ordering_Unit, p.Ordering_Unit) as Ordering_Unit,
                        
                        p.Product_Name, 
                        m.Manuf_Name
                    FROM PO_Details pd
                    JOIN Products_Master p ON pd.Product_ID = p.Product_ID
                    LEFT JOIN Manufacturers m ON p.Manuf_ID = m.Manuf_ID
                    WHERE pd.PO_ID = %s
                """
                cursor.execute(query_details, (po_id,))
                header['Details'] = cursor.fetchall() or []
                
                return header
        except Exception as e:
            logging.error(f"Error fetching full order {po_id}: {e}")
            return None

    def update_full_order(self, po_id: int, data: Dict) -> bool:
        """تحديث شامل للرأس والأسطر (تم التعديل لحفظ Ordering_Unit)."""
        try:
            with self.db.get_db_connection() as conn:
                conn.start_transaction()
                cursor = conn.cursor()

                # 1. تحديث الرأس
                cursor.execute("""
                    UPDATE Purchase_Orders 
                    SET Supplier_ID=%s, Order_Date=%s, Expected_Delivery_Date=%s, Notes=%s
                    WHERE PO_ID=%s
                """, (data['Supplier_ID'], data['Order_Date'], data.get('Expected_Delivery_Date'), data.get('Notes', ''), po_id))

                # 2. استبدال الأسطر
                cursor.execute("DELETE FROM PO_Details WHERE PO_ID = %s", (po_id,))

                for item in data.get('Items', []):
                    # حسابات مالية بسيطة للأسطر
                    qty = float(item['Qty_Ordered'])
                    price = float(item.get('Unit_Price_HT', 0))
                    discount = float(item.get('Discount_Percent', 0))
                    tax = float(item.get('Tax_Rate_Percent', 0))
                    
                    line_ht = qty * price * (1 - discount/100)
                    line_ttc = line_ht * (1 + tax/100)

                    # [FIX] إضافة Ordering_Unit لجملة الإدخال
                    insert_detail = """
                        INSERT INTO PO_Details 
                        (PO_ID, Product_ID, Qty_Ordered, Item_Note, Ordering_Unit,
                         Unit_Price_HT, Discount_Percent, Tax_Rate_Percent, Line_Total_HT, Line_Total_TTC)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_detail, (
                        po_id, item['Product_ID'], qty, item.get('Item_Note', ''),
                        item.get('Ordering_Unit', 'U'), # <--- حفظ الوحدة المختارة
                        price, discount, tax, line_ht, line_ttc
                    ))

                # 3. تحديث إجماليات الرأس
                self._recalculate_po_totals(conn, po_id)
                conn.commit()
                return True
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Error updating full order {po_id}: {e}")
            return False

    def update_status(self, po_id: int, new_status: str) -> bool:
        """تحديث حالة الطلب."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE Purchase_Orders SET Status = %s WHERE PO_ID = %s", (new_status, po_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error updating status: {e}")
            return False

    def _recalculate_po_totals(self, conn, po_id):
        cursor = conn.cursor()
        query = """
            UPDATE Purchase_Orders 
            SET Total_Amount_HT = COALESCE((SELECT SUM(Line_Total_HT) FROM PO_Details WHERE PO_ID = %s), 0),
                Total_Amount_TTC = COALESCE((SELECT SUM(Line_Total_TTC) FROM PO_Details WHERE PO_ID = %s), 0),
                Total_Tax_Amount = COALESCE((SELECT SUM(Line_Total_TTC - Line_Total_HT) FROM PO_Details WHERE PO_ID = %s), 0)
            WHERE PO_ID = %s
        """
        cursor.execute(query, (po_id, po_id, po_id, po_id))