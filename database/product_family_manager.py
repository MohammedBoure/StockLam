# ui/managers/product_family_manager.py

import mysql.connector
import logging
from datetime import datetime
from .system_logger import log_methods 

@log_methods()
class ProductFamilyManager:
    def __init__(self, db_instance):
        self.db = db_instance

    def add_family(self, name):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "INSERT INTO Product_Families (Family_Name) VALUES (%s)"
                cursor.execute(query, (name,))
                family_id = cursor.lastrowid
                logging.info(f"Product Family '{name}' added with ID {family_id}.")
                return family_id
        except mysql.connector.Error as err:
            if err.errno == 1062:
                logging.warning(f"Family '{name}' already exists (Duplicate entry).")
            else:
                logging.error(f"Database error while adding family '{name}': {err}")
            return None

    def update_family(self, family_id, name):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "UPDATE Product_Families SET Family_Name = %s WHERE Family_ID = %s AND Deleted_At IS NULL"
                cursor.execute(query, (name, family_id))
                
                if cursor.rowcount > 0:
                    logging.info(f"Family ID {family_id} updated successfully.")
                    return True
                else:
                    logging.warning(f"No active family found with ID {family_id} to update.")
                    return False
        except mysql.connector.Error as e:
            logging.error(f"Error updating family {family_id}: {e}")
            return False

    def get_all_families(self, include_deleted=False):
        """
        جلب جميع العائلات لملء القوائم المنسدلة (Dropdowns).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM Product_Families"
                
                if not include_deleted:
                    query += " WHERE Deleted_At IS NULL"
                
                query += " ORDER BY Family_Name"
                
                cursor.execute(query)
                families = cursor.fetchall()
                logging.info(f"Fetched {len(families)} product families.")
                return families
        except mysql.connector.Error as e:
            logging.error(f"Error fetching families: {e}")
            raise

    def soft_delete_family(self, family_id):
        """
        حذف منطقي للعائلة. يمنع الحذف إذا كانت مرتبطة بمنتجات نشطة.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # 1. التحقق من الارتباط بالمنتجات
                cursor.execute("""
                    SELECT COUNT(*) FROM Products_Master 
                    WHERE Family_ID = %s AND Deleted_At IS NULL
                """, (family_id,))
                
                count = cursor.fetchone()[0]
                if count > 0:
                    logging.warning(f"Cannot delete Family {family_id}: Linked to {count} active products.")
                    return False, f"لا يمكن الحذف: هذه العائلة مرتبطة بـ {count} منتج."

                # 2. الحذف المنطقي
                query = "UPDATE Product_Families SET Deleted_At = %s WHERE Family_ID = %s"
                cursor.execute(query, (datetime.now(), family_id))
                
                if cursor.rowcount > 0:
                    logging.info(f"Family {family_id} soft deleted.")
                    return True, "تم الحذف بنجاح."
                return False, "العائلة غير موجودة."
                
        except mysql.connector.Error as e:
            logging.error(f"Database error deleting family {family_id}: {e}")
            return False, str(e)

    def reactivate_family(self, family_id):
        """إعادة تفعيل عائلة محذوفة"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE Product_Families SET Deleted_At = NULL WHERE Family_ID = %s", (family_id,))
                return cursor.rowcount > 0
        except mysql.connector.Error as e:
            logging.error(f"Error reactivating family {family_id}: {e}")
            return False