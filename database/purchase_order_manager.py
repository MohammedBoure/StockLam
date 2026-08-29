# database/purchase_order_manager.py

import mysql.connector
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Any
from .system_logger import log_methods 
from ui.formatting import format_money 

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
                self._recalculate_po_totals(conn, po_id) # تحديث الإجماليات
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
                # نحتاج لمعرفة po_id لتحديث المجموع
                cursor.execute("SELECT PO_ID FROM PO_Details WHERE ID=%s", (detail_id,))
                res = cursor.fetchone()
                if res:
                    self._recalculate_po_totals(conn, res[0])
                return True
        except Exception as e:
            logging.error(f"Error updating PO line: {e}")
            return False

    def delete_po_line(self, detail_id: int) -> bool:
        """حذف سطر."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT PO_ID FROM PO_Details WHERE ID = %s", (detail_id,))
                res = cursor.fetchone()
                po_id = res[0] if res else None

                cursor.execute("DELETE FROM PO_Details WHERE ID = %s", (detail_id,))
                conn.commit()
                
                if po_id:
                    self._recalculate_po_totals(conn, po_id)
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

    @staticmethod
    def calculate_unit_conversion_factor(line_unit: Optional[str], ordering_unit: Optional[str], 
                                         stock_unit: Optional[str], stock_qty_per_order_unit: Any = 1, 
                                         usage_unit: Optional[str] = None, 
                                         usage_qty_per_stock_unit: Any = 1) -> float:
        """
        Calcule le facteur de conversion pour convertir la quantité commandée en unités de stock.
        """
        l_unit = str(line_unit or '').strip().lower()
        o_unit = str(ordering_unit or '').strip().lower()
        s_unit = str(stock_unit or '').strip().lower()
        u_unit = str(usage_unit or '').strip().lower()

        if l_unit and o_unit and l_unit == o_unit and o_unit != s_unit:
            try:
                factor = float(stock_qty_per_order_unit or 1.0)
                return factor if factor > 0 else 1.0
            except (ValueError, TypeError):
                return 1.0
        elif l_unit and u_unit and l_unit == u_unit and u_unit != s_unit:
            try:
                u_factor = float(usage_qty_per_stock_unit or 1.0)
                return (1.0 / u_factor) if u_factor > 0 else 1.0
            except (ValueError, TypeError):
                return 1.0
        return 1.0

    def get_products_latest_stock_prices(self, product_ids: Optional[List[int]] = None) -> Dict[int, Dict]:
        """
        Récupère le dernier prix d'achat enregistré dans le stock (Inventory_Batches) pour chaque produit.
        Calcule le prix unitaire TTC en tenant compte des remises et de la TVA.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                query = """
                    SELECT 
                        ib.Product_ID,
                        ib.Unit_Price_Received AS Unit_Price_HT,
                        COALESCE(ib.Discount_Percent, 0) AS Discount_Percent,
                        COALESCE(ib.Tax_Rate_Percent, 0) AS Tax_Rate_Percent,
                        ib.Batch_ID,
                        ib.Created_At AS Date_Received
                    FROM Inventory_Batches ib
                    INNER JOIN (
                        SELECT Product_ID, MAX(Batch_ID) AS max_batch_id
                        FROM Inventory_Batches
                        WHERE Unit_Price_Received > 0
                """
                params = []
                if product_ids:
                    placeholders = ', '.join(['%s'] * len(product_ids))
                    query += f" AND Product_ID IN ({placeholders})"
                    params.extend(product_ids)
                    
                query += """
                        GROUP BY Product_ID
                    ) latest ON ib.Batch_ID = latest.max_batch_id
                """
                
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
                
                result = {}
                for r in rows:
                    p_id = r['Product_ID']
                    p_ht = float(r['Unit_Price_HT'] or 0)
                    d = float(r['Discount_Percent'] or 0) / 100.0
                    t = float(r['Tax_Rate_Percent'] or 0) / 100.0
                    p_ttc = p_ht * (1.0 - d) * (1.0 + t)
                    
                    result[p_id] = {
                        'Product_ID': p_id,
                        'Unit_Price_HT': p_ht,
                        'Discount_Percent': float(r['Discount_Percent'] or 0),
                        'Tax_Rate_Percent': float(r['Tax_Rate_Percent'] or 0),
                        'Unit_Price_TTC': p_ttc,
                        'Batch_ID': r['Batch_ID'],
                        'Date_Received': r['Date_Received']
                    }
                return result
        except Exception as e:
            logging.error(f"Error fetching latest stock prices: {e}")
            return {}

    def get_all_purchase_orders(self, months: int = 6, start_date=None, end_date=None) -> List[Dict]:
        """
        جلب أوامر الشراء مع حساب المبلغ الإجمالي المتوقع بناءً على آخر سعر مسجل في المخزون (TTC).
        - إذا كانت جميع المنتجات معروفة السعر: يعرض المبلغ كاملاً (مثال: 1,500.00 DA).
        - إذا كان بعضها معروفاً والبعض يطلب لأول مرة: يعرض المبلغ مسبوقاً بإشارة أكبر (مثال: > 1,250.00 DA).
        - إذا كانت كل المنتجات جديدة ولا يوجد لها سعر: يعرض '---'.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                query = """
                    SELECT 
                        po.PO_ID, 
                        po.Supplier_ID,
                        po.Order_Date, 
                        po.Expected_Delivery_Date, 
                        po.Status, 
                        po.Notes,
                        s.Supplier_Name
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
                po_list = cursor.fetchall()
                if not po_list:
                    return []

                po_ids = [p['PO_ID'] for p in po_list]
                po_estimates = {p['PO_ID']: {'total_items': 0, 'known_items': 0, 'total_amount_ttc': 0.0} for p in po_list}

                placeholders = ', '.join(['%s'] * len(po_ids))
                query_details = f"""
                    SELECT 
                        pd.PO_ID,
                        pd.Product_ID,
                        pd.Qty_Ordered,
                        COALESCE(pd.Ordering_Unit, pm.Ordering_Unit) AS Line_Unit,
                        pm.Ordering_Unit AS Prod_Ordering_Unit,
                        pm.Stock_Unit AS Prod_Stock_Unit,
                        COALESCE(pm.Stock_Qty_Per_Order_Unit, 1) AS Stock_Qty_Per_Order_Unit,
                        pm.Usage_Unit AS Prod_Usage_Unit,
                        COALESCE(pm.Usage_Qty_Per_Stock_Unit, 1) AS Usage_Qty_Per_Stock_Unit,
                        latest.Unit_Price_Received,
                        latest.Discount_Percent,
                        latest.Tax_Rate_Percent
                    FROM PO_Details pd
                    JOIN Products_Master pm ON pd.Product_ID = pm.Product_ID
                    LEFT JOIN (
                        SELECT ib.Product_ID, ib.Unit_Price_Received, ib.Discount_Percent, ib.Tax_Rate_Percent
                        FROM Inventory_Batches ib
                        INNER JOIN (
                            SELECT Product_ID, MAX(Batch_ID) AS max_batch_id
                            FROM Inventory_Batches
                            WHERE Unit_Price_Received > 0
                            GROUP BY Product_ID
                        ) m ON ib.Batch_ID = m.max_batch_id
                    ) latest ON pd.Product_ID = latest.Product_ID
                    WHERE pd.PO_ID IN ({placeholders})
                """
                cursor.execute(query_details, tuple(po_ids))
                detail_rows = cursor.fetchall()

                for row in detail_rows:
                    p_id_po = row['PO_ID']
                    if p_id_po not in po_estimates:
                        po_estimates[p_id_po] = {'total_items': 0, 'known_items': 0, 'total_amount_ttc': 0.0}
                    
                    po_estimates[p_id_po]['total_items'] += 1
                    p_ht = row.get('Unit_Price_Received')
                    if p_ht is not None and float(p_ht) > 0:
                        po_estimates[p_id_po]['known_items'] += 1
                        p = float(p_ht)
                        d = float(row.get('Discount_Percent') or 0) / 100.0
                        t = float(row.get('Tax_Rate_Percent') or 0) / 100.0
                        p_ttc = p * (1.0 - d) * (1.0 + t)

                        factor = self.calculate_unit_conversion_factor(
                            line_unit=row.get('Line_Unit'),
                            ordering_unit=row.get('Prod_Ordering_Unit'),
                            stock_unit=row.get('Prod_Stock_Unit'),
                            stock_qty_per_order_unit=row.get('Stock_Qty_Per_Order_Unit'),
                            usage_unit=row.get('Prod_Usage_Unit'),
                            usage_qty_per_stock_unit=row.get('Usage_Qty_Per_Stock_Unit')
                        )
                        qty = float(row.get('Qty_Ordered') or 0)
                        po_estimates[p_id_po]['total_amount_ttc'] += qty * factor * p_ttc

                for po in po_list:
                    po_id = po['PO_ID']
                    est = po_estimates.get(po_id, {'total_items': 0, 'known_items': 0, 'total_amount_ttc': 0.0})
                    total_items = est['total_items']
                    known_items = est['known_items']
                    amt_ttc = est['total_amount_ttc']

                    if total_items == 0 or known_items == 0:
                        po['Total_Amount_TTC'] = 0.0
                        po['Estimated_Amount_TTC'] = 0.0
                        po['Estimated_Amount_Display'] = "---"
                        po['Total_Amount_Display'] = "---"
                        po['Has_Estimated_Price'] = False
                        po['Is_Partial_Estimate'] = False
                    elif known_items < total_items:
                        po['Total_Amount_TTC'] = amt_ttc
                        po['Estimated_Amount_TTC'] = amt_ttc
                        po['Estimated_Amount_Display'] = f"> {format_money(amt_ttc, 'DA')}"
                        po['Total_Amount_Display'] = f"> {format_money(amt_ttc, 'DA')}"
                        po['Has_Estimated_Price'] = True
                        po['Is_Partial_Estimate'] = True
                    else:
                        po['Total_Amount_TTC'] = amt_ttc
                        po['Estimated_Amount_TTC'] = amt_ttc
                        po['Estimated_Amount_Display'] = format_money(amt_ttc, 'DA')
                        po['Total_Amount_Display'] = format_money(amt_ttc, 'DA')
                        po['Has_Estimated_Price'] = True
                        po['Is_Partial_Estimate'] = False

                return po_list
                
        except Exception as e:
            logging.error(f"Error fetching POs: {e}")
            return []
        
        
    def get_full_order_details(self, po_id: int) -> Optional[Dict]:
        """جلب بيانات الطلب والمنتجات والماركات والأسعار المقدرة من المخزون."""
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

                # 2. جلب التفاصيل مع دمج الماركة والوحدات وآخر سعر مسجل في المخزون
                query_details = """
                    SELECT 
                        pd.ID, pd.PO_ID, pd.Product_ID, pd.Qty_Ordered, 
                        pd.Unit_Price_HT, pd.Discount_Percent, pd.Tax_Rate_Percent, 
                        pd.Line_Total_HT, pd.Line_Total_TTC, pd.Item_Note,
                        
                        COALESCE(pd.Ordering_Unit, p.Ordering_Unit) as Ordering_Unit,
                        
                        p.Product_Name, 
                        m.Manuf_Name,
                        p.Ordering_Unit as Master_Ordering_Unit,
                        p.Stock_Unit,
                        COALESCE(p.Stock_Qty_Per_Order_Unit, 1) as Stock_Qty_Per_Order_Unit,
                        p.Usage_Unit,
                        COALESCE(p.Usage_Qty_Per_Stock_Unit, 1) as Usage_Qty_Per_Stock_Unit,
                        latest.Unit_Price_Received as Latest_Unit_Price_HT,
                        COALESCE(latest.Discount_Percent, 0) as Latest_Discount_Percent,
                        COALESCE(latest.Tax_Rate_Percent, 0) as Latest_Tax_Rate_Percent
                    FROM PO_Details pd
                    JOIN Products_Master p ON pd.Product_ID = p.Product_ID
                    LEFT JOIN Manufacturers m ON p.Manuf_ID = m.Manuf_ID
                    LEFT JOIN (
                        SELECT ib.Product_ID, ib.Unit_Price_Received, ib.Discount_Percent, ib.Tax_Rate_Percent
                        FROM Inventory_Batches ib
                        INNER JOIN (
                            SELECT Product_ID, MAX(Batch_ID) AS max_batch_id
                            FROM Inventory_Batches
                            WHERE Unit_Price_Received > 0
                            GROUP BY Product_ID
                        ) m_batch ON ib.Batch_ID = m_batch.max_batch_id
                    ) latest ON pd.Product_ID = latest.Product_ID
                    WHERE pd.PO_ID = %s
                """
                cursor.execute(query_details, (po_id,))
                details = cursor.fetchall() or []

                total_items = len(details)
                known_items = 0
                total_estimated_ttc = 0.0

                for line in details:
                    p_ht = line.get('Latest_Unit_Price_HT')
                    if p_ht is not None and float(p_ht) > 0:
                        known_items += 1
                        p = float(p_ht)
                        d = float(line.get('Latest_Discount_Percent') or 0) / 100.0
                        t = float(line.get('Latest_Tax_Rate_Percent') or 0) / 100.0
                        p_ttc = p * (1.0 - d) * (1.0 + t)

                        factor = self.calculate_unit_conversion_factor(
                            line_unit=line.get('Ordering_Unit'),
                            ordering_unit=line.get('Master_Ordering_Unit'),
                            stock_unit=line.get('Stock_Unit'),
                            stock_qty_per_order_unit=line.get('Stock_Qty_Per_Order_Unit'),
                            usage_unit=line.get('Usage_Unit'),
                            usage_qty_per_stock_unit=line.get('Usage_Qty_Per_Stock_Unit')
                        )
                        qty = float(line.get('Qty_Ordered') or 0)
                        line_total_ttc = qty * factor * p_ttc
                        
                        line['Estimated_Unit_Price_TTC'] = p_ttc * factor
                        line['Estimated_Line_Total_TTC'] = line_total_ttc
                        line['Has_Estimated_Price'] = True
                        total_estimated_ttc += line_total_ttc
                    else:
                        line['Estimated_Unit_Price_TTC'] = None
                        line['Estimated_Line_Total_TTC'] = None
                        line['Has_Estimated_Price'] = False

                header['Details'] = details
                header['Total_Items_Count'] = total_items
                header['Known_Items_Count'] = known_items

                if total_items == 0 or known_items == 0:
                    header['Estimated_Amount_TTC'] = 0.0
                    header['Estimated_Amount_Display'] = "---"
                    header['Total_Amount_Display'] = "---"
                    header['Has_Estimated_Price'] = False
                    header['Is_Partial_Estimate'] = False
                elif known_items < total_items:
                    header['Estimated_Amount_TTC'] = total_estimated_ttc
                    header['Estimated_Amount_Display'] = f"> {format_money(total_estimated_ttc, 'DA')}"
                    header['Total_Amount_Display'] = f"> {format_money(total_estimated_ttc, 'DA')}"
                    header['Has_Estimated_Price'] = True
                    header['Is_Partial_Estimate'] = True
                else:
                    header['Estimated_Amount_TTC'] = total_estimated_ttc
                    header['Estimated_Amount_Display'] = format_money(total_estimated_ttc, 'DA')
                    header['Total_Amount_Display'] = format_money(total_estimated_ttc, 'DA')
                    header['Has_Estimated_Price'] = True
                    header['Is_Partial_Estimate'] = False
                
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