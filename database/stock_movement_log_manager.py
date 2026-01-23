# database/managers/stock_movement_log_manager.py

import mysql.connector
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Any
from decimal import Decimal

class StockMovementLogManager:
    """
    إدارة عمليات جدول سجل حركات المخزون (Stock_Movement_Log).
    يسجل كل عملية تؤثر على المخزون (دخول، خروج، تلف، تعديل) لتوفير سجل تدقيق كامل.
    """

    def __init__(self, db_instance):
        self.db = db_instance

    def create_movement_log(self, product_id: int, movement_type: str, qty_change: Decimal, unit_used: str, 
                    batch_id: Optional[int] = None, container_id: Optional[int] = None, 
                    reason_id: Optional[int] = None, notes: Optional[str] = None, 
                    user_id: Optional[int] = None, 
                    external_cursor=None) -> Optional[int]:
        """
        إنشاء سجل حركة مخزون. تم تصحيحها لتدعم 'External_Transfer'.
        """
        valid_movements = [
            'Purchase_Receive', 'Open_Pack', 'Patient_Test', 'QC_Run', 
            'Calibration', 'Adjustment', 'Waste', 'Transfer', 'External_Transfer'
        ]
        
        if movement_type not in valid_movements:
            logging.error(f"⚠️ Type de mouvement invalide: {movement_type}")
            return None

        query = """
            INSERT INTO Stock_Movement_Log 
            (Product_ID, Batch_ID, Container_ID, Movement_Type, Reason_ID, 
            Qty_Change, Unit_Used, Notes, User_ID, Transaction_Date) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        params = (product_id, batch_id, container_id, movement_type, reason_id, 
                qty_change, unit_used, notes, user_id)
        
        try:
            if external_cursor:
                external_cursor.execute(query, params)
                return external_cursor.lastrowid

            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                movement_id = cursor.lastrowid
                conn.commit()
                return movement_id
        except Exception as e:
            logging.error(f"❌ Erreur Stock_Movement_Log: {e}")
            return None
    def get_log_by_batch_or_container(self, item_id: int, is_batch: bool = True) -> List[Dict]:
        """جلب حركات مخزون مادة معينة مع اسم المستخدم المسؤول."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                field = "Batch_ID" if is_batch else "Container_ID"

                query = f"""
                    SELECT 
                        sml.*, 
                        r.Reason_Name, 
                        p.Product_Name,
                        COALESCE(u.Full_Name, 'Système') as Operator_Name
                    FROM Stock_Movement_Log sml
                    LEFT JOIN Waste_Reasons r ON sml.Reason_ID = r.Reason_ID
                    JOIN Products_Master p ON sml.Product_ID = p.Product_ID
                    LEFT JOIN Users u ON sml.User_ID = u.User_ID
                    WHERE sml.{field} = %s
                    ORDER BY sml.Transaction_Date DESC
                """
                cursor.execute(query, (item_id,))
                return cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error(f"Error fetching log: {e}")
            raise

    def get_movement_summary_by_type(self, start_date: date, end_date: date, movement_type: Optional[str] = None) -> List[Dict]:
        """جلب ملخص إحصائي للحركات حسب النوع للفترة المحددة."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        sml.Movement_Type,
                        COUNT(sml.Movement_ID) AS Total_Events,
                        SUM(sml.Qty_Change) AS Total_Qty_Change
                    FROM Stock_Movement_Log sml
                    WHERE DATE(sml.Transaction_Date) BETWEEN %s AND %s
                """
                params = [start_date, end_date]
                
                if movement_type:
                    query += " AND sml.Movement_Type = %s"
                    params.append(movement_type)
                
                query += " GROUP BY sml.Movement_Type ORDER BY Total_Events DESC"
                
                cursor.execute(query, tuple(params))
                return cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error(f"Error fetching movement summary: {e}")
            raise

    def get_waste_summary(self, start_date: date, end_date: date) -> List[Dict]:
        """جلب ملخص التلف."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        r.Reason_Name,
                        p.Product_Name,
                        sml.Unit_Used,
                        SUM(ABS(sml.Qty_Change)) AS Total_Wasted_Qty,
                        COUNT(sml.Movement_ID) AS Total_Waste_Events
                    FROM Stock_Movement_Log sml
                    JOIN Products_Master p ON sml.Product_ID = p.Product_ID
                    LEFT JOIN Waste_Reasons r ON sml.Reason_ID = r.Reason_ID
                    WHERE sml.Movement_Type IN ('Waste', 'Adjustment')
                      AND sml.Qty_Change < 0 
                      AND DATE(sml.Transaction_Date) BETWEEN %s AND %s
                    GROUP BY r.Reason_Name, p.Product_Name, sml.Unit_Used
                    ORDER BY Total_Wasted_Qty DESC
                """
                params = (start_date, end_date)
                cursor.execute(query, params)
                results = cursor.fetchall()
                return results
        except mysql.connector.Error as e:
            logging.error(f"Error fetching waste summary: {e}")
            raise

    def get_movements_log(self, limit=1000, product_id=None, movement_type=None) -> List[Dict]:
        """
        جلب سجل الحركات مع كافة التفاصيل المطلوبة للعرض والنقر المزدوج.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        m.Movement_ID, 
                        m.Movement_ID AS Log_ID,  -- مهم جداً لنافذة التفاصيل
                        m.Transaction_Date, 
                        m.Movement_Type, 
                        m.Qty_Change,
                        m.Unit_Used, 
                        m.Notes, 
                        m.User_ID,                -- لإظهار معرف المستخدم
                        m.Product_ID,             -- لإظهار معرف المنتج
                        m.Batch_ID,               -- لإظهار معرف الدفعة
                        
                        -- تفاصيل المنتج
                        p.Product_Name, 
                        p.Barcode AS Product_Barcode, -- باركود المصنع
                        
                        -- تفاصيل الدفعة
                        b.Lot_Number, 
                        b.Internal_Barcode AS Batch_Barcode,
                        b.Quantity_Current, 
                        
                        -- الموقع
                        COALESCE(l.Location_Name, '---') as Location_Name,
                        
                        -- سبب الحركة (Motif)
                        wr.Reason_Name,
                        
                        -- اسم المستخدم (يظهر 'Système' إذا كان NULL)
                        COALESCE(u.Full_Name, 'Système') as Operator_Name 
                        
                    FROM Stock_Movement_Log m
                    JOIN Products_Master p ON m.Product_ID = p.Product_ID
                    LEFT JOIN Inventory_Batches b ON m.Batch_ID = b.Batch_ID
                    LEFT JOIN Locations l ON b.Location_ID = l.Location_ID
                    LEFT JOIN Waste_Reasons wr ON m.Reason_ID = wr.Reason_ID
                    LEFT JOIN Users u ON m.User_ID = u.User_ID 
                    WHERE 1=1
                """
                params = []
                if product_id:
                    query += " AND m.Product_ID = %s"; params.append(product_id)
                if movement_type:
                    query += " AND m.Movement_Type = %s"; params.append(movement_type)
                
                query += " ORDER BY m.Transaction_Date DESC LIMIT %s"
                params.append(limit)
                
                cursor.execute(query, tuple(params))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching movement log: {e}")
            return []


    def get_kpi_summary(self):
        """حساب KPIs المالية."""
        stats = {
            'total_products': 0,
            'total_value': 0.0,
            'critical_alerts': 0,
            'pending_orders': 0
        }
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM Products_Master WHERE Deleted_At IS NULL")
                stats['total_products'] = cursor.fetchone()[0]

                query_val = """
                    SELECT SUM(
                        Quantity_Current * (
                            Unit_Price_Received * (1 - Discount_Percent / 100) * (1 + Tax_Rate_Percent / 100)
                        )
                    ) 
                    FROM Inventory_Batches 
                    WHERE Quantity_Current > 0 
                      AND Status = 'Available'
                """
                cursor.execute(query_val)
                val = cursor.fetchone()[0]
                stats['total_value'] = float(val) if val else 0.0

                cursor.execute("""
                    SELECT COUNT(*) FROM Purchase_Orders 
                    WHERE Status IN ('Sent', 'Partial', 'Approved')
                """)
                stats['pending_orders'] = cursor.fetchone()[0]

                alerts = self.get_active_alerts()
                stats['critical_alerts'] = sum(1 for a in alerts if a['Criticality'] == 'High')

                return stats
        except Exception as e:
            logging.error(f"Erreur KPIs (Calcul TTC): {e}")
            return stats

    def get_total_consumed_value(self, start_date, end_date):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT SUM(
                        ABS(sml.Qty_Change) * (
                            b.Unit_Price_Received * (1 - b.Discount_Percent / 100) * (1 + b.Tax_Rate_Percent / 100)
                        )
                    ) as total_val
                    FROM Stock_Movement_Log sml
                    JOIN Inventory_Batches b ON sml.Batch_ID = b.Batch_ID
                    WHERE sml.Movement_Type IN ('Patient_Test', 'QC_Run')
                      AND DATE(sml.Transaction_Date) BETWEEN %s AND %s
                """
                cursor.execute(query, (start_date, end_date))
                res = cursor.fetchone()
                return float(res['total_val']) if res and res['total_val'] else 0.0
        except Exception as e:
            logging.error(f"Error calculating TTC consumed value: {e}")
            return 0.0

    def get_consumption_trend(self, start_date, end_date):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        DATE(sml.Transaction_Date) as date,
                        SUM(ABS(sml.Qty_Change)) as daily_qty,
                        SUM(ABS(sml.Qty_Change) * (
                            b.Unit_Price_Received * (1 - b.Discount_Percent / 100) * (1 + b.Tax_Rate_Percent / 100)
                        )) as daily_value
                    FROM Stock_Movement_Log sml
                    JOIN Inventory_Batches b ON sml.Batch_ID = b.Batch_ID
                    WHERE sml.Movement_Type IN ('Patient_Test', 'QC_Run')
                      AND DATE(sml.Transaction_Date) BETWEEN %s AND %s
                    GROUP BY DATE(sml.Transaction_Date)
                    ORDER BY date ASC
                """
                cursor.execute(query, (start_date, end_date))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error in trend TTC calculation: {e}")
            return []

    def get_detailed_consumption_report(self, start_date, end_date):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        p.Product_ID, p.Product_Name, p.Usage_Unit,
                        SUM(ABS(sml.Qty_Change)) as total_qty,
                        SUM(ABS(sml.Qty_Change) * (
                            b.Unit_Price_Received * (1 - b.Discount_Percent / 100) * (1 + b.Tax_Rate_Percent / 100)
                        )) as total_value
                    FROM Stock_Movement_Log sml
                    JOIN Products_Master p ON sml.Product_ID = p.Product_ID
                    JOIN Inventory_Batches b ON sml.Batch_ID = b.Batch_ID
                    WHERE sml.Movement_Type IN ('Patient_Test', 'QC_Run', 'Waste')
                      AND DATE(sml.Transaction_Date) BETWEEN %s AND %s
                    GROUP BY p.Product_ID, p.Product_Name, p.Usage_Unit
                """
                cursor.execute(query, (start_date, end_date))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error in detailed TTC report: {e}")
            return []

    def get_total_consumed_quantity(self, start_date, end_date):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT SUM(ABS(Qty_Change)) as total_qty
                    FROM Stock_Movement_Log
                    WHERE Movement_Type IN ('Patient_Test', 'QC_Run', 'Waste')
                      AND DATE(Transaction_Date) BETWEEN %s AND %s
                """
                cursor.execute(query, (start_date, end_date))
                res = cursor.fetchone()
                return float(res['total_qty']) if res and res['total_qty'] else 0.0
        except Exception as e:
            logging.error(f"Error fetching total qty: {e}")
            return 0.0

    def get_active_alerts(self):
        alerts = []
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                today = datetime.now().date()
                
                query_expiry = """
                    SELECT b.Batch_ID, p.Product_Name, b.Lot_Number, b.Expiry_Date, b.Quantity_Current, p.Alert_Before_Expiry_Days
                    FROM Inventory_Batches b
                    JOIN Products_Master p ON b.Product_ID = p.Product_ID
                    WHERE b.Quantity_Current > 0 AND b.Expiry_Date IS NOT NULL
                      AND DATE_ADD(CURDATE(), INTERVAL COALESCE(p.Alert_Before_Expiry_Days, 30) DAY) >= b.Expiry_Date
                    ORDER BY b.Expiry_Date ASC
                """
                cursor.execute(query_expiry)
                for item in cursor.fetchall():
                    days_diff = (item['Expiry_Date'] - today).days
                    crit = "High" if days_diff <= 7 else "Medium"
                    alerts.append({
                        "Product": item['Product_Name'],
                        "Type": "Péremption",
                        "Details": f"Lot: {item['Lot_Number']} | Exp: {item['Expiry_Date']}",
                        "Criticality": crit
                    })

                query_stock = """
                    SELECT p.Product_Name, p.Minimum_Stock_Level, COALESCE(SUM(b.Quantity_Current), 0) as Total_Stock
                    FROM Products_Master p
                    LEFT JOIN Inventory_Batches b ON p.Product_ID = b.Product_ID
                    WHERE p.Deleted_At IS NULL
                    GROUP BY p.Product_ID, p.Product_Name, p.Minimum_Stock_Level
                    HAVING Total_Stock <= p.Minimum_Stock_Level
                """
                cursor.execute(query_stock)
                for item in cursor.fetchall():
                    current = float(item['Total_Stock'])
                    alerts.append({
                        "Product": item['Product_Name'],
                        "Type": "Stock Faible",
                        "Details": f"Stock: {current} (Seuil: {item['Minimum_Stock_Level']})",
                        "Criticality": "High" if current == 0 else "Medium"
                    })
            return alerts
        except Exception as e:
            logging.error(f"Alerts Error: {e}")
            return []