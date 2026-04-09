# waste_reason_manager.py

import mysql.connector
import logging
from .system_logger import log_methods 

@log_methods()
class WasteReasonManager:
    """إدارة عمليات جدول أسباب التلف/الرفض (Waste_Reasons) لتوحيد أسباب خروج المخزون."""

    def __init__(self, db_instance):
        self.db = db_instance

    def add_reason(self, name):
        """
        إضافة سبب جديد للتلف أو التعديل.
        يتم تعيين Is_Active افتراضياً إلى True.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Waste_Reasons 
                    (Reason_Name, Is_Active) 
                    VALUES (%s, TRUE)
                """
                params = (name,)
                cursor.execute(query, params)
                reason_id = cursor.lastrowid
                logging.info(f"Waste Reason '{name}' added with ID {reason_id}.")
                return reason_id
        except mysql.connector.Error as err:
            if err.errno == 1062:
                logging.warning(f"Waste Reason '{name}' already exists.")
            else:
                logging.error(f"Database error while adding waste reason '{name}': {err}")
            return None

    def update_reason_name(self, reason_id, new_name):
        """
        تحديث اسم السبب (Reason_Name).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "UPDATE Waste_Reasons SET Reason_Name = %s WHERE Reason_ID = %s"
                params = (new_name, reason_id)
                cursor.execute(query, params)
                if cursor.rowcount > 0:
                    logging.info(f"Waste Reason {reason_id} name updated to '{new_name}'.")
                    return True
                logging.warning(f"No reason found with ID {reason_id} for name update.")
                return False
        except mysql.connector.Error as e:
            logging.error(f"Error updating waste reason name {reason_id}: {e}")
            raise

    def set_reason_active_status(self, reason_id, is_active: bool):
        """
        تفعيل أو إلغاء تفعيل السبب (Soft Delete/Reactivate).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "UPDATE Waste_Reasons SET Is_Active = %s WHERE Reason_ID = %s"
                params = (is_active, reason_id)
                cursor.execute(query, params)
                if cursor.rowcount > 0:
                    status = "activated" if is_active else "deactivated"
                    logging.info(f"Waste Reason {reason_id} status set to {status}.")
                    return True
                logging.warning(f"No reason found with ID {reason_id} for status change.")
                return False
        except mysql.connector.Error as e:
            logging.error(f"Error changing active status for reason {reason_id}: {e}")
            raise

    def get_all_reasons(self, include_inactive=False):
        """
        جلب جميع الأسباب، مع خيار لتضمين الأسباب غير النشطة.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                query = "SELECT * FROM Waste_Reasons"
                if not include_inactive:
                    query += " WHERE Is_Active = TRUE"
                query += " ORDER BY Reason_Name"
                
                cursor.execute(query)
                reasons = cursor.fetchall()
                logging.info(f"Fetched {len(reasons)} waste reasons.")
                return reasons
        except mysql.connector.Error as e:
            logging.error(f"Error fetching waste reasons: {e}")
            raise

    def get_reason_movement_summary(self):
        """
        جلب إحصائيات استخدام كل سبب (عدد حركات المخزون السلبية التي استخدمت هذا السبب).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                # نستخدم SUM(ABS(Qty_Change)) لإجمالي الكمية المتأثرة، و COUNT(Movement_ID) لعدد الحركات
                query = """
                    SELECT 
                        r.Reason_ID, 
                        r.Reason_Name, 
                        r.Is_Active,
                        COUNT(m.Movement_ID) AS total_movements_count,
                        COALESCE(SUM(ABS(m.Qty_Change)), 0) AS total_quantity_wasted
                    FROM Waste_Reasons r
                    LEFT JOIN Stock_Movement_Log m ON r.Reason_ID = m.Reason_ID
                    WHERE r.Is_Active = TRUE 
                      AND m.Movement_Type IN ('Waste', 'Adjustment') -- فقط الحركات السلبية ذات الصلة
                    GROUP BY r.Reason_ID, r.Reason_Name, r.Is_Active
                    ORDER BY total_quantity_wasted DESC
                """
                cursor.execute(query)
                results = cursor.fetchall()
                logging.info(f"Fetched movement summary for {len(results)} active waste reasons.")
                return results
        except mysql.connector.Error as e:
            logging.error(f"Error fetching reason movement summary: {e}")
            raise