# ui/managers/packaging_unit_manager.py

import mysql.connector
import logging
from datetime import datetime
from .system_logger import log_methods 

@log_methods()
class PackagingUnitManager:
    """
    إدارة عمليات جدول وحدات التغليف والتخزين (Packaging_Units).
    يستخدم لتحديد وحدات مثل: Carton, Box, Kit, Test, Trest...
    """

    def __init__(self, db_instance):
        self.db = db_instance

    def add_unit(self, name, description=None):
        """
        إضافة وحدة تخزين جديدة.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "INSERT INTO Packaging_Units (Unit_Name, Description) VALUES (%s, %s)"
                cursor.execute(query, (name, description))
                unit_id = cursor.lastrowid
                logging.info(f"Packaging Unit '{name}' added with ID {unit_id}.")
                return unit_id
        except mysql.connector.Error as err:
            if err.errno == 1062:
                logging.warning(f"Unit '{name}' already exists.")
                return -1 # رمز للخطأ (مكرر)
            else:
                logging.error(f"Database error while adding unit '{name}': {err}")
            return None

    def update_unit(self, unit_id, name, description=None):
        """
        تحديث اسم أو وصف الوحدة.
        """
        updates = []
        params = []
        
        if name:
            updates.append("Unit_Name = %s")
            params.append(name)
        if description is not None:
            updates.append("Description = %s")
            params.append(description)
            
        if not updates: return False
        
        params.append(unit_id)
        query = f"UPDATE Packaging_Units SET {', '.join(updates)} WHERE Unit_ID = %s AND Deleted_At IS NULL"

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                return cursor.rowcount > 0
        except mysql.connector.Error as e:
            logging.error(f"Error updating unit {unit_id}: {e}")
            return False

    def get_all_units(self, include_deleted=False):
        """
        جلب جميع الوحدات لملء القوائم المنسدلة (ComboBox).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM Packaging_Units"
                if not include_deleted:
                    query += " WHERE Deleted_At IS NULL"
                query += " ORDER BY Unit_Name"
                
                cursor.execute(query)
                return cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error(f"Error fetching packaging units: {e}")
            raise

    def soft_delete_unit(self, unit_id, unit_name_for_check=None):
        """
        حذف منطقي للوحدة. 
        يقوم بالتحقق مما إذا كانت هذه الوحدة مستخدمة كنص في جدول المنتجات قبل الحذف.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # التحقق من الاستخدام في جدول المنتجات (إذا كانت الوحدة مستخدمة)
                # ملاحظة: هذا التحقق يعتمد على أنك ما زلت تخزن الاسم كـ VARCHAR في المنتجات
                # أو إذا قمت بترقية المنتجات لتستخدم ID، فسنبحث عن الـ ID.
                if unit_name_for_check:
                    # تحقق إذا كان الاسم مستخدماً في أي من أعمدة الوحدات الثلاثة
                    check_query = """
                        SELECT COUNT(*) FROM Products_Master 
                        WHERE (Ordering_Unit = %s OR Stock_Unit = %s OR Usage_Unit = %s)
                        AND Deleted_At IS NULL
                    """
                    cursor.execute(check_query, (unit_name_for_check, unit_name_for_check, unit_name_for_check))
                    count = cursor.fetchone()[0]
                    if count > 0:
                        logging.warning(f"Cannot delete Unit '{unit_name_for_check}': Used in {count} products.")
                        return False, f"لا يمكن الحذف: هذه الوحدة مستخدمة في {count} منتج."

                # تنفيذ الحذف
                query = "UPDATE Packaging_Units SET Deleted_At = %s WHERE Unit_ID = %s"
                cursor.execute(query, (datetime.now(), unit_id))
                
                if cursor.rowcount > 0:
                    return True, "تم الحذف بنجاح."
                return False, "الوحدة غير موجودة."
                
        except mysql.connector.Error as e:
            logging.error(f"Database error deleting unit {unit_id}: {e}")
            return False, str(e)