# database/managers/user_manager.py

import mysql.connector
import logging
import json
from datetime import datetime
from typing import List, Dict, Optional
from .system_logger import log_methods 

@log_methods()
class UserManager:
    """إدارة عمليات جدول المستخدمين (Users) والصلاحيات."""

    def __init__(self, db_instance):
        self.db = db_instance

    def authenticate(self, username, password) -> Optional[Dict]:
        """التحقق من بيانات الدخول (مقارنة النصوص العادية بدون تشفير)."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                # استخدام password كما هي للمطابقة
                query = "SELECT * FROM Users WHERE Username = %s AND Password = %s AND Is_Active = 1"
                cursor.execute(query, (username, password))
                user = cursor.fetchone()
                
                if user:
                    # تحويل نص JSON للصلاحيات إلى قاموس (Dictionary)
                    if user.get('Permissions') and isinstance(user['Permissions'], str):
                        try:
                            user['Permissions'] = json.loads(user['Permissions'])
                        except json.JSONDecodeError:
                            user['Permissions'] = {}
                    elif not user.get('Permissions'):
                        user['Permissions'] = {}

                    logging.info(f"User '{username}' logged in successfully.")
                    return user
                else:
                    logging.warning(f"Login failed: No match for '{username}' with provided password.")
                    return None
        except mysql.connector.Error as e:
            logging.error(f"Database error during authentication: {e}")
            return None

    def add_user(self, username, password, role='Technician', full_name=None, permissions=None):
        """إضافة مستخدم جديد للنظام وتخزين كلمة المرور كنص عادي."""
        if permissions is None:
            permissions = {}
            
        try:
            # تحويل قاموس الصلاحيات إلى نص JSON
            perms_json = json.dumps(permissions)

            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Users (Username, Password, Role, Full_Name, Permissions) 
                    VALUES (%s, %s, %s, %s, %s)
                """
                # تمرير password مباشرة
                cursor.execute(query, (username, password, role, full_name, perms_json))
                user_id = cursor.lastrowid
                logging.info(f"User '{username}' created with ID {user_id}.")
                return user_id
        except mysql.connector.Error as err:
            if err.errno == 1062:
                logging.warning(f"Username '{username}' already exists.")
                return -1
            logging.error(f"Error adding user: {err}")
            return None

    def update_user(self, user_id, **kwargs):
        """تحديث بيانات المستخدم بشكل ديناميكي (الاسم، الدور، الحالة، كلمة المرور، الصلاحيات)."""
        updates = []
        params = []
        
        # الحقول المسموح بتحديثها
        allowed_fields = ['Username', 'Role', 'Full_Name', 'Is_Active', 'Password', 'Permissions']
        for key, value in kwargs.items():
            if key in allowed_fields:
                # معالجة خاصة للصلاحيات (تحويل إلى JSON)
                if key == 'Permissions':
                    if isinstance(value, dict):
                        value = json.dumps(value)

                # سيتم تمرير كلمة المرور الجديدة (إن وجدت) كما هي بدون تشفير
                updates.append(f"{key} = %s")
                params.append(value)
        
        if not updates: 
            return False
        
        params.append(user_id)
        query = f"UPDATE Users SET {', '.join(updates)} WHERE User_ID = %s"
        
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                return cursor.rowcount > 0
        except mysql.connector.Error as e:
            logging.error(f"Error updating user {user_id}: {e}")
            return False

    def get_all_users(self, include_inactive=False):
        """جلب قائمة المستخدمين لإدارة النظام مع جلب الصلاحيات."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT User_ID, Username, Role, Full_Name, Is_Active, Permissions, Created_At FROM Users"
                if not include_inactive:
                    query += " WHERE Is_Active = TRUE"
                query += " ORDER BY Username"
                cursor.execute(query)
                users = cursor.fetchall()

                # تحويل حقل الصلاحيات من JSON String إلى Dictionary لجميع المستخدمين
                for user in users:
                    if user.get('Permissions') and isinstance(user['Permissions'], str):
                        try:
                            user['Permissions'] = json.loads(user['Permissions'])
                        except json.JSONDecodeError:
                            user['Permissions'] = {}
                    elif not user.get('Permissions'):
                        user['Permissions'] = {}

                return users
        except mysql.connector.Error as e:
            logging.error(f"Error fetching users: {e}")
            return []

    def get_user_events(self, user_id, limit=100):
        """
        جلب سجل الأحداث (العمليات) التي قام بها مستخدم معين.
        تربط بين سجل الحركات وجدول المنتجات.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT sml.*, pm.Product_Name 
                    FROM Stock_Movement_Log sml
                    JOIN Products_Master pm ON sml.Product_ID = pm.Product_ID
                    WHERE sml.User_ID = %s
                    ORDER BY sml.Transaction_Date DESC
                    LIMIT %s
                """
                cursor.execute(query, (user_id, limit))
                return cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error(f"Error fetching events for user {user_id}: {e}")
            return []