# database/system_log_manager.py

import json
import logging
import mysql.connector
from typing import List, Dict, Optional

logger = logging.getLogger("JEWELLERY_SYS")

class SystemLogManager:
    """
    Manager for reading and filtering SystemLogs.
    Designed to be used by the UI to display Audit Trails.
    """

    def __init__(self, db_instance):
        self.db = db_instance

    def get_logs(self, 
                 user_id: Optional[int] = None, 
                 module_name: Optional[str] = None, 
                 action_name: Optional[str] = None, 
                 action_type: Optional[str] = None,
                 start_date: Optional[str] = None, 
                 end_date: Optional[str] = None, 
                 search_text: Optional[str] = None,
                 limit: int = 100, 
                 offset: int = 0) -> List[Dict]:
        """Fetches logs sorted by date descending (Newest first)."""
        logs = []
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # Corrected query syntax
                query = """
                    SELECT 
                        sl.id, 
                        sl.user_id, 
                        COALESCE(u.username, 'System/Deleted') AS username,
                        sl.log_date, 
                        sl.module, 
                        sl.action, 
                        sl.details, 
                        sl.ip_address
                    FROM SystemLogs sl
                    LEFT JOIN Users u ON sl.user_id = u.User_ID
                    WHERE 1=1
                """
                params = []

                if user_id:
                    query += " AND sl.user_id = %s"
                    params.append(user_id)
                if module_name:
                    query += " AND sl.module = %s"
                    params.append(module_name)
                if action_name:
                    query += " AND sl.action = %s"
                    params.append(action_name)
                if action_type:
                    query += " AND sl.action LIKE %s"
                    params.append(f"[{action_type}]%")
                if start_date:
                    query += " AND DATE(sl.log_date) >= %s"
                    params.append(start_date)
                if end_date:
                    query += " AND DATE(sl.log_date) <= %s"
                    params.append(end_date)
                if search_text:
                    query += " AND (sl.action LIKE %s OR sl.details LIKE %s OR sl.module LIKE %s)"
                    search_pattern = f"%{search_text}%"
                    params.extend([search_pattern, search_pattern, search_pattern])

                # Ensuring DESC order for newest logs
                query += " ORDER BY sl.log_date DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])

                cursor.execute(query, tuple(params))
                raw_logs = cursor.fetchall()

                for row in raw_logs:
                    if row['details']:
                        try:
                            row['details_dict'] = json.loads(row['details'])
                        except json.JSONDecodeError:
                            row['details_dict'] = {"raw": row['details']}
                    else:
                        row['details_dict'] = {}
                    logs.append(row)

        except mysql.connector.Error as e:
            logger.error(f"Error fetching system logs: {e}")
            
        return logs
    def get_total_logs_count(self, **filters) -> int:
        """
        Returns the total number of logs matching the filters.
        Crucial for calculating total pages in UI pagination.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT COUNT(*) FROM SystemLogs sl WHERE 1=1"
                params = []

                if filters.get('user_id'):
                    query += " AND sl.user_id = %s"
                    params.append(filters['user_id'])
                if filters.get('module_name'):
                    query += " AND sl.module = %s"
                    params.append(filters['module_name'])
                
                # 🟢 تطبيق الفلتر الجديد في دالة العد أيضاً ليكون الترقيم (Pagination) دقيقاً
                if filters.get('action_type'):
                    query += " AND sl.action LIKE %s"
                    params.append(f"[{filters['action_type']}]%")

                if filters.get('start_date'):
                    query += " AND DATE(sl.log_date) >= %s"
                    params.append(filters['start_date'])
                if filters.get('end_date'):
                    query += " AND DATE(sl.log_date) <= %s"
                    params.append(filters['end_date'])

                cursor.execute(query, tuple(params))
                return cursor.fetchone()[0]
        except mysql.connector.Error as e:
            logger.error(f"Error counting system logs: {e}")
            return 0

    def get_available_modules(self) -> List[str]:
        """
        Fetches distinct module names to populate a ComboBox filter in the UI.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT module FROM SystemLogs WHERE module IS NOT NULL ORDER BY module")
                return [row[0] for row in cursor.fetchall()]
        except mysql.connector.Error:
            return []

    def get_available_actions(self, module_name: Optional[str] = None) -> List[str]:
        """
        Fetches distinct actions, optionally filtered by module. Useful for a dependent ComboBox.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT DISTINCT action FROM SystemLogs WHERE action IS NOT NULL"
                params = []
                
                if module_name:
                    query += " AND module = %s"
                    params.append(module_name)
                    
                query += " ORDER BY action"
                
                cursor.execute(query, tuple(params))
                return [row[0] for row in cursor.fetchall()]
        except mysql.connector.Error:
            return []