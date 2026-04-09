# product_document_manager.py

import mysql.connector
import logging
from datetime import datetime
import os 
from typing import List, Optional
import sys
import shutil
import uuid

def get_external_path(folder_name):
    """جلب مسار المجلدات الخارجية بجانب ملف الـ EXE أو ملف السكريبت"""
    if hasattr(sys, '_MEIPASS'):
        # عند التشغيل كملف EXE، نأخذ مسار المجلد الذي يحتوي على EXE
        return os.path.join(os.path.dirname(sys.executable), folder_name)
    # عند التشغيل كسكريبت عادي، نأخذ المجلد الحالي للمشروع
    return os.path.join(os.path.abspath("."), folder_name)

# تعريف مسار تخزين الوثائق ليكون مجلد "documents" في نفس مجلد البرنامج
DEFAULT_FILE_STORAGE_PATH = get_external_path("documents")

# التأكد من إنشاء المجلد تلقائياً إذا لم يكن موجوداً
if not os.path.exists(DEFAULT_FILE_STORAGE_PATH):
    try:
        os.makedirs(DEFAULT_FILE_STORAGE_PATH)
    except Exception as e:
        import logging
        logging.error(f"Could not create storage directory: {e}")
from .system_logger import log_methods 

@log_methods()
class ProductDocumentManager:
    """إدارة عمليات جدول وثائق المنتجات (Product_Documents) الضرورية للامتثال والجودة."""

    def __init__(self, db_instance):
        self.db = db_instance

    def add_document(self, product_id: int, doc_type: str, source_file_path: str, user_id: Optional[int] = None):
        """
        يقوم بنسخ الملف إلى مجلد البرنامج ثم حفظ المسار الجديد في قاعدة البيانات.
        """
        valid_types = ['COA', 'MSDS', 'Package Insert', 'Contract']
        if doc_type not in valid_types:
            return None

        if not os.path.exists(source_file_path):
            logging.error("Source file does not exist.")
            return None

        try:
            file_ext = os.path.splitext(source_file_path)[1] # .pdf, .jpg
            unique_filename = f"{product_id}_{doc_type}_{uuid.uuid4().hex[:8]}{file_ext}"
            
            destination_path = os.path.join(DEFAULT_FILE_STORAGE_PATH, unique_filename)

            shutil.copy2(source_file_path, destination_path)
            logging.info(f"File copied to internal storage: {destination_path}")

            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Product_Documents 
                    (Product_ID, Doc_Type, File_Path, Upload_Date) 
                    VALUES (%s, %s, %s, %s)
                """
                params = (product_id, doc_type, destination_path, datetime.now())
                cursor.execute(query, params)
                return cursor.lastrowid

        except Exception as err:
            logging.error(f"Error handling document upload: {err}")
            return None
    def get_documents_by_product(self, product_id: int) -> List[dict]:
        """
        جلب جميع الوثائق المرتبطة بمنتج معين.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT d.*, p.Product_Name 
                    FROM Product_Documents d
                    JOIN Products_Master p ON d.Product_ID = p.Product_ID
                    WHERE d.Product_ID = %s
                    ORDER BY d.Doc_Type, d.Upload_Date DESC
                """
                cursor.execute(query, (product_id,))
                documents = cursor.fetchall()
                logging.info(f"Fetched {len(documents)} documents for Product ID {product_id}.")
                return documents
        except mysql.connector.Error as e:
            logging.error(f"Error fetching documents for Product {product_id}: {e}")
            raise

    def delete_document(self, doc_id: int, delete_file_on_server: bool = False) -> bool:
        """
        حذف سجل الوثيقة من قاعدة البيانات، مع خيار لحذف الملف الفعلي من الخادم.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()

                # 1. جلب مسار الملف قبل الحذف
                cursor.execute("SELECT File_Path FROM Product_Documents WHERE Doc_ID = %s", (doc_id,))
                result = cursor.fetchone()
                if not result:
                    logging.warning(f"No document found with ID {doc_id} for deletion.")
                    return False
                
                file_path_to_delete = result[0]

                # 2. حذف السجل من قاعدة البيانات
                cursor.execute("DELETE FROM Product_Documents WHERE Doc_ID = %s", (doc_id,))
                
                if cursor.rowcount > 0:
                    logging.info(f"Document {doc_id} record deleted from database.")

                    # 3. حذف الملف الفعلي (اختياري)
                    if delete_file_on_server and os.path.exists(file_path_to_delete):
                        try:
                            os.remove(file_path_to_delete)
                            logging.info(f"Physical file deleted: {file_path_to_delete}")
                        except Exception as e:
                            logging.error(f"Failed to delete physical file {file_path_to_delete}: {e}")
                            # لا نرجع خطأ، لأن السجل تم حذفه من DB بنجاح
                            
                    return True
                return False
                
        except mysql.connector.Error as e:
            logging.error(f"Database error while deleting document {doc_id}: {e}")
            return False

    def get_document_by_id(self, doc_id: int) -> Optional[dict]:
        """
        جلب تفاصيل وثيقة واحدة بناءً على معرف الوثيقة.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM Product_Documents WHERE Doc_ID = %s"
                cursor.execute(query, (doc_id,))
                return cursor.fetchone()
        except mysql.connector.Error as e:
            logging.error(f"Error fetching document {doc_id}: {e}")
            return None