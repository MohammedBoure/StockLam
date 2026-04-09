# automate_manager.py

import mysql.connector
import logging
from datetime import datetime
from .system_logger import log_methods 

@log_methods()
class AutomateManager:
    """إدارة عمليات جدول أجهزة التحليل (Automates)، مع تتبع الموقع والتفاصيل الفنية."""

    def __init__(self, db_instance):
        self.db = db_instance

    def add_automate(self, name, model_number=None, serial_number=None, date_of_purchase=None, location_id=None):
        """
        إضافة جهاز تحليل جديد.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Automates 
                    (Automate_Name, Model_Number, Serial_Number, Date_of_Purchase, Location_ID) 
                    VALUES (%s, %s, %s, %s, %s)
                """
                params = (name, model_number, serial_number, date_of_purchase, location_id)
                cursor.execute(query, params)
                automate_id = cursor.lastrowid
                logging.info(f"Automate '{name}' added with ID {automate_id}.")
                return automate_id
        except mysql.connector.Error as err:
            if err.errno == 1062:
                logging.warning(f"Automate '{name}' already exists (Duplicate entry).")
            else:
                logging.error(f"Database error while adding automate '{name}': {err}")
            return None

    def update_automate(self, automate_id, name=None, model_number=None, serial_number=None, date_of_purchase=None, location_id=None):
        """
        تحديث معلومات الجهاز بشكل ديناميكي.
        """
        updates = []
        params = []
        
        if name is not None:
            updates.append("Automate_Name = %s")
            params.append(name)
            
        if model_number is not None:
            updates.append("Model_Number = %s")
            params.append(model_number)
            
        if serial_number is not None:
            updates.append("Serial_Number = %s")
            params.append(serial_number)
            
        if date_of_purchase is not None:
            updates.append("Date_of_Purchase = %s")
            params.append(date_of_purchase)
            
        if location_id is not None:
            updates.append("Location_ID = %s")
            params.append(location_id)
            
        if not updates:
            logging.warning(f"No fields provided for automate update (ID: {automate_id}).")
            return False

        params.append(automate_id)
        query = f"UPDATE Automates SET {', '.join(updates)} WHERE Automate_ID = %s AND Deleted_At IS NULL"
        
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                if cursor.rowcount > 0:
                    logging.info(f"Automate {automate_id} updated successfully.")
                    return True
                logging.warning(f"No active automate found with ID {automate_id} for update.")
                return False
        except mysql.connector.Error as e:
            logging.error(f"Error updating automate {automate_id}: {e}")
            raise

    def get_all_automates(self, include_deleted=False):
        """
        جلب جميع أجهزة التحليل مع تفاصيل الموقع (Location Name)، مع خيار لتضمين الأجهزة المحذوفة منطقياً.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                query = """
                    SELECT 
                        a.*, 
                        l.Location_Name 
                    FROM Automates a
                    LEFT JOIN Locations l ON a.Location_ID = l.Location_ID
                """
                if not include_deleted:
                    query += " WHERE a.Deleted_At IS NULL"
                query += " ORDER BY a.Automate_Name"
                
                cursor.execute(query)
                automates = cursor.fetchall()
                logging.info(f"Fetched {len(automates)} automates.")
                return automates
        except mysql.connector.Error as e:
            logging.error(f"Error fetching automates: {e}")
            raise

    def soft_delete_automate(self, automate_id):
        """
        حذف منطقي (Soft Delete) لجهاز تحليل.
        يمنع الحذف إذا كان الجهاز مرتبطًا كـ 'Preferred Automate' بأي منتج نشط.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # 1. التحقق من وجود منتجات نشطة تعتبر هذا الجهاز كجهاز مفضل
                cursor.execute("""
                    SELECT COUNT(*) FROM Products_Master 
                    WHERE Preferred_Automate_ID = %s AND Deleted_At IS NULL
                """, (automate_id,))
                
                if cursor.fetchone()[0] > 0:
                    logging.error(f"Cannot soft delete automate {automate_id}. It is set as the preferred machine for active products.")
                    return False
                
                # 2. تنفيذ الحذف المنطقي
                query = "UPDATE Automates SET Deleted_At = %s WHERE Automate_ID = %s AND Deleted_At IS NULL"
                params = (datetime.now(), automate_id)
                cursor.execute(query, params)
                
                if cursor.rowcount > 0:
                    logging.info(f"Automate {automate_id} soft deleted successfully.")
                    return True
                logging.warning(f"No active automate found with ID {automate_id} for soft deletion.")
                return False
        except mysql.connector.Error as e:
            logging.error(f"Database error while soft deleting automate {automate_id}: {e}")
            return False

    def reactivate_automate(self, automate_id):
        """
        إعادة تفعيل (Un-delete) جهاز تحليل محذوف منطقياً.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "UPDATE Automates SET Deleted_At = NULL WHERE Automate_ID = %s AND Deleted_At IS NOT NULL"
                cursor.execute(query, (automate_id,))
                
                if cursor.rowcount > 0:
                    logging.info(f"Automate {automate_id} reactivated successfully.")
                    return True
                logging.warning(f"No soft-deleted automate found with ID {automate_id} for reactivation.")
                return False
        except mysql.connector.Error as e:
            logging.error(f"Database error while reactivating automate {automate_id}: {e}")
            return False

    def get_automate_product_summary(self, automate_id):
        """
        جلب قائمة بالمنتجات (الكواشف) النشطة التي تستخدم هذا الجهاز كجهاز مفضل.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        p.Product_ID, 
                        p.Product_Name, 
                        p.Family_Category,
                        m.Manuf_Name
                    FROM Products_Master p
                    JOIN Manufacturers m ON p.Manuf_ID = m.Manuf_ID
                    WHERE p.Preferred_Automate_ID = %s AND p.Deleted_At IS NULL
                    ORDER BY p.Family_Category, p.Product_Name
                """
                cursor.execute(query, (automate_id,))
                results = cursor.fetchall()
                logging.info(f"Fetched {len(results)} active products linked to Automate ID {automate_id}.")
                return results
        except mysql.connector.Error as e:
            logging.error(f"Error fetching product summary for automate {automate_id}: {e}")
            raise