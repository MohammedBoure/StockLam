# database/location_manager.py

import mysql.connector
import logging
from typing import List, Dict, Optional
from .system_logger import log_methods 

@log_methods()
class LocationManager:
    def __init__(self, db_instance):
        self.db = db_instance

    # ============================================================
    #  1. دوال العرض والبحث (View & Fetch)
    # ============================================================

    def get_all_locations(self) -> List[Dict]:
        """
        جلب جميع المواقع بتنسيق مسطح مع المسار الكامل للاسم.
        مثال: 'Bâtiment A > Salle 1 > Frigo 2'
        هذه الدالة هي التي كانت تسبب الخطأ سابقاً.
        """
        return self.get_all_locations_flat()

    def get_location_by_id(self, location_id: int) -> Optional[Dict]:
        """جلب تفاصيل موقع واحد."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT l.*, lt.Type_Name 
                    FROM Locations l
                    LEFT JOIN Location_Types lt ON l.Type_ID = lt.Type_ID
                    WHERE l.Location_ID = %s AND l.Deleted_At IS NULL
                """
                cursor.execute(query, (location_id,))
                return cursor.fetchone()
        except mysql.connector.Error as e:
            logging.error(f"Error fetching location by ID {location_id}: {e}")
            return None

    def _fetch_all_raw_locations(self) -> List[Dict]:
        """جلب البيانات الخام من قاعدة البيانات."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT l.*, t.Type_Name 
                    FROM Locations l
                    LEFT JOIN Location_Types t ON l.Type_ID = t.Type_ID
                    WHERE l.Deleted_At IS NULL 
                    ORDER BY l.Location_Name ASC
                """
                cursor.execute(query)
                return cursor.fetchall()
        except mysql.connector.Error: return []

    def get_all_locations_flat(self) -> List[Dict]:
        """
        بناء قائمة مسطحة حيث يتم تعديل الاسم ليحتوي على المسار الكامل.
        مثال: الابن يصبح 'الأب > الابن'
        """
        raw_list = self._fetch_all_raw_locations()
        if not raw_list: return []

        # إنشاء قواميس للبحث السريع
        id_to_name = {item['Location_ID']: item['Location_Name'] for item in raw_list}
        id_to_parent = {item['Location_ID']: item['Parent_Location_ID'] for item in raw_list}

        # بناء المسار لكل عنصر
        for item in raw_list:
            path = item['Location_Name']
            parent_id = item['Parent_Location_ID']
            depth = 0
            
            # الصعود للأعلى حتى 10 مستويات كحد أقصى لمنع التكرار اللانهائي
            while parent_id and parent_id in id_to_name and depth < 10:
                parent_name = id_to_name[parent_id]
                path = f"{parent_name} > {path}"
                parent_id = id_to_parent[parent_id]
                depth += 1
                
            item['Location_Name'] = path # تحديث الاسم ليكون المسار الكامل

        # إعادة ترتيب القائمة أبجدياً حسب المسار الجديد
        return sorted(raw_list, key=lambda x: x['Location_Name'])

    def get_location_hierarchy(self) -> List[Dict]:
        """بناء هيكل شجري (للـ TreeView)."""
        raw_list = self._fetch_all_raw_locations()
        node_map = {item['Location_ID']: item for item in raw_list}
        for item in raw_list: item['children'] = []
        
        roots = []
        for item in raw_list:
            parent_id = item.get('Parent_Location_ID')
            if parent_id and parent_id in node_map:
                node_map[parent_id]['children'].append(item)
            else:
                roots.append(item)
        return roots

    # ============================================================
    #  2. إدارة أنواع المواقع (Location Types CRUD)
    # ============================================================
    def get_all_location_types(self) -> List[Dict]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM Location_Types ORDER BY Type_Name")
                return cursor.fetchall()
        except mysql.connector.Error as err:
            logging.error(f"Error fetching location types: {err}")
            return []

    def add_location_type(self, type_name: str) -> Optional[int]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO Location_Types (Type_Name) VALUES (%s)", (type_name,))
                return cursor.lastrowid
        except mysql.connector.Error as err:
            logging.error(f"Error adding location type: {err}")
            return None

    def update_location_type(self, type_id: int, new_name: str) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE Location_Types SET Type_Name = %s WHERE Type_ID = %s", (new_name, type_id))
                return cursor.rowcount > 0
        except mysql.connector.Error as err:
            logging.error(f"Error updating location type: {err}")
            return False

    def delete_location_type(self, type_id: int) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM Locations WHERE Type_ID = %s AND Deleted_At IS NULL", (type_id,))
                if cursor.fetchone()[0] > 0:
                    logging.warning(f"Cannot delete Type {type_id}: It is used by active locations.")
                    return False
                cursor.execute("DELETE FROM Location_Types WHERE Type_ID = %s", (type_id,))
                return True
        except mysql.connector.Error as err:
            logging.error(f"Error deleting location type: {err}")
            return False

    # ============================================================
    #  3. إدارة المواقع (Locations CRUD)
    # ============================================================
    def add_location(self, name: str, type_id: int, temperature_zone: str, parent_id: Optional[int] = None) -> Optional[int]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Locations (Location_Name, Type_ID, Temperature_Zone, Parent_Location_ID) 
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(query, (name, type_id, temperature_zone, parent_id))
                return cursor.lastrowid
        except mysql.connector.Error as err:
            logging.error(f"Error adding location: {err}")
            return None

    def update_location(self, location_id: int, name: str, type_id: int, temperature_zone: str, parent_id: Optional[int] = None) -> bool:
        if parent_id is not None:
            if location_id == parent_id: return False
            if self._is_descendant(location_id, parent_id): return False

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    UPDATE Locations 
                    SET Location_Name = %s, Type_ID = %s, Temperature_Zone = %s, Parent_Location_ID = %s
                    WHERE Location_ID = %s
                """
                cursor.execute(query, (name, type_id, temperature_zone, parent_id, location_id))
                return True
        except mysql.connector.Error as err:
            logging.error(f"Error updating location: {err}")
            return False

    def delete_location(self, location_id: int) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # التحقق من الأبناء
                cursor.execute("SELECT COUNT(*) FROM Locations WHERE Parent_Location_ID = %s AND Deleted_At IS NULL", (location_id,))
                if cursor.fetchone()[0] > 0: return False
                
                # التحقق من المخزون
                cursor.execute("SELECT COUNT(*) FROM Inventory_Batches WHERE Location_ID = %s AND Quantity_Current > 0", (location_id,))
                if cursor.fetchone()[0] > 0: return False
                
                # حذف منطقي (Soft Delete)
                cursor.execute("UPDATE Locations SET Deleted_At = NOW() WHERE Location_ID = %s", (location_id,))
                return True
        except mysql.connector.Error: return False

    def _is_descendant(self, ancestor_id: int, descendant_id: int) -> bool:
        """
        التحقق مما إذا كان descendant_id هو ابن (أو حفيد) لـ ancestor_id.
        لمنع الدورات (Cycles) في الشجرة.
        """
        current_id = descendant_id
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # أقصى عمق 20 لتجنب الحلقات اللانهائية
                for _ in range(20):
                    if not current_id: return False
                    
                    query = "SELECT Parent_Location_ID FROM Locations WHERE Location_ID = %s"
                    cursor.execute(query, (current_id,))
                    res = cursor.fetchone()
                    
                    if not res or not res['Parent_Location_ID']:
                        return False
                        
                    parent = res['Parent_Location_ID']
                    if parent == ancestor_id:
                        return True
                        
                    current_id = parent
            return False
        except Exception as e:
            logging.error(f"Error in _is_descendant: {e}")
            return False