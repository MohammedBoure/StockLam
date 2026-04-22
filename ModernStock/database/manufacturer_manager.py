# manufacturer_manager.py

import mysql.connector
import logging
from datetime import datetime
from .system_logger import log_methods 

@log_methods()
class ManufacturerManager:
    """إدارة عمليات جدول الشركات المصنعة (Manufacturers)."""

    def __init__(self, db_instance):
        self.db = db_instance

    def add_manufacturer(self, name, country_of_origin=None, website=None):
        """
        إضافة شركة مصنعة جديدة.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Manufacturers 
                    (Manuf_Name, Country_of_Origin, Website) 
                    VALUES (%s, %s, %s)
                """
                params = (name, country_of_origin, website)
                cursor.execute(query, params)
                manufacturer_id = cursor.lastrowid
                logging.info(f"Manufacturer '{name}' added with ID {manufacturer_id}.")
                return manufacturer_id
        except mysql.connector.Error as err:
            if err.errno == 1062:
                logging.warning(f"Manufacturer '{name}' already exists (Duplicate entry).")
            else:
                logging.error(f"Database error while adding manufacturer '{name}': {err}")
            return None

    def update_manufacturer(self, manufacturer_id, name=None, country_of_origin=None, website=None):
        """
        تحديث معلومات الشركة المصنعة بشكل ديناميكي.
        """
        updates = []
        params = []
        
        if name is not None:
            updates.append("Manuf_Name = %s")
            params.append(name)
            
        if country_of_origin is not None:
            updates.append("Country_of_Origin = %s")
            params.append(country_of_origin)
            
        if website is not None:
            updates.append("Website = %s")
            params.append(website)
            
        if not updates:
            logging.warning(f"No fields provided for manufacturer update (ID: {manufacturer_id}).")
            return False

        params.append(manufacturer_id)
        query = f"UPDATE Manufacturers SET {', '.join(updates)} WHERE Manuf_ID = %s AND Deleted_At IS NULL"
        
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                if cursor.rowcount > 0:
                    logging.info(f"Manufacturer {manufacturer_id} updated successfully.")
                    return True
                logging.warning(f"No active manufacturer found with ID {manufacturer_id} for update.")
                return False
        except mysql.connector.Error as e:
            logging.error(f"Error updating manufacturer {manufacturer_id}: {e}")
            raise

    def get_all_manufacturers(self, include_deleted=False):
        """
        جلب جميع الشركات المصنعة، مع خيار لتضمين الشركات المحذوفة منطقياً.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                query = "SELECT * FROM Manufacturers"
                if not include_deleted:
                    query += " WHERE Deleted_At IS NULL"
                query += " ORDER BY Manuf_Name"
                
                cursor.execute(query)
                manufacturers = cursor.fetchall()
                logging.info(f"Fetched {len(manufacturers)} manufacturers.")
                return manufacturers
        except mysql.connector.Error as e:
            logging.error(f"Error fetching manufacturers: {e}")
            raise

    def soft_delete_manufacturer(self, manufacturer_id):
        """
        حذف منطقي (Soft Delete) لشركة مصنعة عن طريق تحديد تاريخ الحذف.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # التحقق أولاً مما إذا كانت الشركة مستخدمة في أي منتجات نشطة
                cursor.execute("SELECT COUNT(*) FROM Products_Master WHERE Manuf_ID = %s AND Deleted_At IS NULL", (manufacturer_id,))
                if cursor.fetchone()[0] > 0:
                    logging.error(f"Cannot soft delete manufacturer {manufacturer_id}. It is currently linked to active products.")
                    return False
                
                # تنفيذ الحذف المنطقي
                query = "UPDATE Manufacturers SET Deleted_At = %s WHERE Manuf_ID = %s AND Deleted_At IS NULL"
                params = (datetime.now(), manufacturer_id)
                cursor.execute(query, params)
                
                if cursor.rowcount > 0:
                    logging.info(f"Manufacturer {manufacturer_id} soft deleted successfully.")
                    return True
                logging.warning(f"No active manufacturer found with ID {manufacturer_id} for soft deletion.")
                return False
        except mysql.connector.Error as e:
            logging.error(f"Database error while soft deleting manufacturer {manufacturer_id}: {e}")
            return False

    def reactivate_manufacturer(self, manufacturer_id):
        """
        إعادة تفعيل (Un-delete) شركة مصنعة محذوفة منطقياً.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "UPDATE Manufacturers SET Deleted_At = NULL WHERE Manuf_ID = %s AND Deleted_At IS NOT NULL"
                cursor.execute(query, (manufacturer_id,))
                
                if cursor.rowcount > 0:
                    logging.info(f"Manufacturer {manufacturer_id} reactivated successfully.")
                    return True
                logging.warning(f"No soft-deleted manufacturer found with ID {manufacturer_id} for reactivation.")
                return False
        except mysql.connector.Error as e:
            logging.error(f"Database error while reactivating manufacturer {manufacturer_id}: {e}")
            return False

    def get_manufacturer_usage_stats(self):
        """
        جلب إحصائيات استخدام كل شركة مصنعة (عدد المنتجات النشطة المرتبطة).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        m.Manuf_ID, 
                        m.Manuf_Name, 
                        m.Country_of_Origin,
                        COUNT(p.Product_ID) AS active_product_count
                    FROM Manufacturers m
                    LEFT JOIN Products_Master p ON m.Manuf_ID = p.Manuf_ID AND p.Deleted_At IS NULL
                    WHERE m.Deleted_At IS NULL
                    GROUP BY m.Manuf_ID, m.Manuf_Name, m.Country_of_Origin
                    ORDER BY active_product_count DESC, m.Manuf_Name
                """
                cursor.execute(query)
                results = cursor.fetchall()
                logging.info(f"Fetched usage stats for {len(results)} manufacturers.")
                return results
        except mysql.connector.Error as e:
            logging.error(f"Error fetching manufacturer usage stats: {e}")
            raise