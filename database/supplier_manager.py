# supplier_manager.py

import mysql.connector
import logging
from datetime import datetime
from .system_logger import log_methods 

@log_methods()
class SupplierManager:
    """إدارة عمليات جدول الموردين (Suppliers)، مع التركيز على المتطلبات المالية والقانونية للمختبرات."""

    def __init__(self, db_instance):
        self.db = db_instance


    def add_supplier(self, Supplier_Name, Contact_Person=None, Phone=None, Email=None, Website=None, 
                    Address_Line1=None, Address_Line2=None, City=None, Postal_Code=None, 
                    Tax_ID_Number=None, Commercial_Reg_No=None, Bank_Name=None, Bank_Account_IBAN=None):
        """
        إضافة مورد جديد مع مطابقة أسماء المتغيرات تماماً مع مفاتيح القاموس القادمة من واجهة المستخدم.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Suppliers 
                    (Supplier_Name, Contact_Person, Phone, Email, Website, 
                    Address_Line1, Address_Line2, City, Postal_Code, 
                    Tax_ID_Number, Commercial_Reg_No, Bank_Name, Bank_Account_IBAN) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                # استخدام المتغيرات بالأسماء الجديدة المتوافقة مع واجهة المستخدم
                params = (
                    Supplier_Name, Contact_Person, Phone, Email, Website, 
                    Address_Line1, Address_Line2, City, Postal_Code, 
                    Tax_ID_Number, Commercial_Reg_No, Bank_Name, Bank_Account_IBAN
                )
                cursor.execute(query, params)
                supplier_id = cursor.lastrowid
                logging.info(f"Supplier '{Supplier_Name}' added with ID {supplier_id}.")
                return supplier_id
        except mysql.connector.Error as err:
            if err.errno == 1062:
                logging.warning(f"Supplier '{Supplier_Name}' already exists.")
            else:
                logging.error(f"Database error: {err}")
            return None

    def update_supplier(self, supplier_id, **kwargs):
        """
        تحديث معلومات المورد بشكل ديناميكي بناءً على الحقول المُمررة.
        
        **kwargs يمكن أن تشمل: Supplier_Name, Contact_Person, Phone, Email, Website, 
                            Address_Line1, City, Tax_ID_Number, Bank_Account_IBAN, ...
        """
        updates = []
        params = []
        
        # قائمة بالحقول المسموح بتحديثها
        allowed_fields = [
            'Supplier_Name', 'Contact_Person', 'Phone', 'Email', 'Website',
            'Address_Line1', 'Address_Line2', 'City', 'Postal_Code',
            'Tax_ID_Number', 'Commercial_Reg_No', 'Bank_Name', 'Bank_Account_IBAN'
        ]

        for key, value in kwargs.items():
            if key in allowed_fields:
                updates.append(f"{key} = %s")
                params.append(value)
            
        if not updates:
            logging.warning(f"No valid fields provided for supplier update (ID: {supplier_id}).")
            return False

        params.append(supplier_id)
        query = f"UPDATE Suppliers SET {', '.join(updates)} WHERE Supplier_ID = %s AND Deleted_At IS NULL"
        
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                if cursor.rowcount > 0:
                    logging.info(f"Supplier {supplier_id} updated successfully.")
                    return True
                logging.warning(f"No active supplier found with ID {supplier_id} for update.")
                return False
        except mysql.connector.Error as e:
            logging.error(f"Error updating supplier {supplier_id}: {e}")
            raise

    def get_all_suppliers(self, include_deleted=False):
        """
        جلب جميع الموردين مع جميع تفاصيلهم، مع خيار لتضمين الشركات المحذوفة منطقياً.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                query = "SELECT * FROM Suppliers"
                if not include_deleted:
                    query += " WHERE Deleted_At IS NULL"
                query += " ORDER BY Supplier_Name"
                
                cursor.execute(query)
                suppliers = cursor.fetchall()
                logging.info(f"Fetched {len(suppliers)} suppliers.")
                return suppliers
        except mysql.connector.Error as e:
            logging.error(f"Error fetching suppliers: {e}")
            raise

    def soft_delete_supplier(self, supplier_id):
        """
        حذف منطقي (Soft Delete) لمورد عن طريق تحديد تاريخ الحذف.
        يمنع الحذف إذا كان المورد مرتبطًا بطلبات شراء نشطة (Draft/Sent/Partial_Received).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # 1. التحقق من وجود طلبات شراء نشطة
                cursor.execute("""
                    SELECT COUNT(*) FROM Purchase_Orders 
                    WHERE Supplier_ID = %s 
                    AND Status IN ('Draft', 'Pending_Approval', 'Approved', 'Sent', 'Partial_Received')
                """, (supplier_id,))
                
                if cursor.fetchone()[0] > 0:
                    logging.error(f"Cannot soft delete supplier {supplier_id}. It is currently linked to active Purchase Orders.")
                    return False
                
                # 2. تنفيذ الحذف المنطقي
                query = "UPDATE Suppliers SET Deleted_At = %s WHERE Supplier_ID = %s AND Deleted_At IS NULL"
                params = (datetime.now(), supplier_id)
                cursor.execute(query, params)
                
                if cursor.rowcount > 0:
                    logging.info(f"Supplier {supplier_id} soft deleted successfully.")
                    return True
                logging.warning(f"No active supplier found with ID {supplier_id} for soft deletion.")
                return False
        except mysql.connector.Error as e:
            logging.error(f"Database error while soft deleting supplier {supplier_id}: {e}")
            return False

    def reactivate_supplier(self, supplier_id):
        """
        إعادة تفعيل (Un-delete) مورد محذوف منطقياً.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "UPDATE Suppliers SET Deleted_At = NULL WHERE Supplier_ID = %s AND Deleted_At IS NOT NULL"
                cursor.execute(query, (supplier_id,))
                
                if cursor.rowcount > 0:
                    logging.info(f"Supplier {supplier_id} reactivated successfully.")
                    return True
                logging.warning(f"No soft-deleted supplier found with ID {supplier_id} for reactivation.")
                return False
        except mysql.connector.Error as e:
            logging.error(f"Database error while reactivating supplier {supplier_id}: {e}")
            return False

    def get_supplier_purchase_stats(self, supplier_id=None):
        """
        جلب إحصائيات المشتريات: إجمالي عدد الطلبات، آخر طلب، وإجمالي المبلغ (TTC) لكل مورد.
        إذا تم تمرير supplier_id، يتم جلب الإحصائيات لمورد واحد.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        s.Supplier_ID, 
                        s.Supplier_Name, 
                        COUNT(po.PO_ID) AS total_orders,
                        SUM(po.Total_Amount_TTC) AS total_spent_ttc,
                        MAX(po.Order_Date) AS last_order_date
                    FROM Suppliers s
                    LEFT JOIN Purchase_Orders po ON s.Supplier_ID = po.Supplier_ID
                    WHERE s.Deleted_At IS NULL
                """
                params = []
                
                if supplier_id:
                    query += " AND s.Supplier_ID = %s"
                    params.append(supplier_id)
                    
                query += " GROUP BY s.Supplier_ID, s.Supplier_Name ORDER BY total_spent_ttc DESC"
                
                cursor.execute(query, tuple(params))
                results = cursor.fetchall()
                logging.info(f"Fetched purchase stats for {len(results)} suppliers.")
                return results
        except mysql.connector.Error as e:
            logging.error(f"Error fetching supplier purchase stats: {e}")
            raise

    # database/managers/supplier_manager.py

    def add_payment(self, payment_data):
        """تسجيل دفعة جديدة مع إمكانية الربط بـ BR"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Supplier_Payments 
                    (Supplier_ID, Payment_Date, Amount, Payment_Method, Reference, Notes, Created_By, BR_ID) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                params = (
                    payment_data['Supplier_ID'],
                    payment_data['Payment_Date'],
                    payment_data['Amount'],
                    payment_data['Payment_Method'],
                    payment_data.get('Reference'),
                    payment_data.get('Notes'),
                    payment_data.get('Created_By'),
                    payment_data.get('BR_ID')  # <--- الحقل الجديد
                )
                cursor.execute(query, params)
                conn.commit()
                return True, "Paiement enregistré avec succès."
        except Exception as e:
            logging.error(f"Error adding payment: {e}")
            return False, str(e)

    def get_supplier_receptions_for_linking(self, supplier_id):
        """جلب قائمة الاستلامات (BR) الخاصة بمورد معين لربطها بالدفع"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT BR_ID, Supplier_Invoice_Ref, Invoice_Total_TTC, Reception_Date
                    FROM Reception_Log 
                    WHERE Supplier_ID = %s 
                    ORDER BY Reception_Date DESC
                    LIMIT 50
                """
                cursor.execute(query, (supplier_id,))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching supplier receptions: {e}")
            return []

    def get_supplier_account_statement(self, supplier_id, start_date=None, end_date=None):
        """تحديث دالة كشف الحساب لإظهار تفاصيل الربط"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # 1. Receptions
                query_receptions = """
                    SELECT 
                        Reception_Date as Date_Op,
                        'Facture' as Type_Op,
                        Invoice_Total_TTC as Montant_Achat,
                        0 as Montant_Versement,
                        COALESCE(Supplier_Invoice_Ref, Supplier_BL_Ref, CONCAT('BR #', BR_ID)) as Observation
                    FROM Reception_Log
                    WHERE Supplier_ID = %s AND Status != 'Pending Audit'
                """
                params = [supplier_id]
                if start_date:
                    query_receptions += " AND Reception_Date >= %s"
                    params.append(start_date)
                if end_date:
                    query_receptions += " AND Reception_Date <= %s"
                    params.append(end_date)

                # 2. Payments (تم التحديث لإظهار الربط)
                query_payments = """
                    SELECT 
                        sp.Payment_Date as Date_Op,
                        'Paiement' as Type_Op,
                        0 as Montant_Achat,
                        sp.Amount as Montant_Versement,
                        CONCAT(
                            sp.Payment_Method, 
                            IF(sp.Reference IS NOT NULL AND sp.Reference != '', CONCAT(' - ', sp.Reference), ''),
                            IF(rl.Supplier_Invoice_Ref IS NOT NULL, CONCAT(' (Lien: ', rl.Supplier_Invoice_Ref, ')'), '')
                        ) as Observation
                    FROM Supplier_Payments sp
                    LEFT JOIN Reception_Log rl ON sp.BR_ID = rl.BR_ID
                    WHERE sp.Supplier_ID = %s
                """
                params_pay = [supplier_id]
                if start_date:
                    query_payments += " AND Payment_Date >= %s"
                    params_pay.append(start_date)
                if end_date:
                    query_payments += " AND Payment_Date <= %s"
                    params_pay.append(end_date)

                full_query = f"({query_receptions}) UNION ALL ({query_payments}) ORDER BY Date_Op ASC"
                cursor.execute(full_query, tuple(params + params_pay))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error statement: {e}")
            return []