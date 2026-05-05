import mysql.connector
from mysql.connector import errorcode, pooling
import logging
from contextlib import contextmanager
from datetime import datetime, date, timedelta
import os
import shutil
from decimal import Decimal
import pandas as pd
import sys
import codecs
import zipfile
import json
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import functools
import logging
import sqlalchemy


try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except (AttributeError, TypeError):
    try:
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except Exception as e:
        print(f"Warning: Could not force console to UTF-8. {e}")


logger = logging.getLogger("MODERNLAM")

TABLE_IMPORT_ORDER = [
    'Users', 'Location_Types', 'Product_Families', 'Packaging_Units', 
    'Manufacturers', 'Suppliers', 'External_Partners', 'Locations', 'Automates', 'Waste_Reasons', # Added External_Partners
    'Products_Master', 'Product_Documents', 'Purchase_Orders', 'PO_Details', 
    'Reception_Log', 'Reception_Details', 'Inventory_Batches', 
    'Active_Containers', 'External_Transfer_Log', 'External_Transfer_Details', 'Stock_Movement_Log',
    'Supplier_Credit_Notes','Credit_Note_Details','Supplier_Payments'
]

ARCHIVE_VIEW_FLAG_FILE = 'archive_view.flag'

def get_external_path(filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(os.path.dirname(sys.executable), filename)
    return os.path.join(os.path.abspath("."), filename)

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


log_file = get_external_path("app.log")

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)


class Database:
    _instance = None
    _pool = None 

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Database, cls).__new__(cls, *args, **kwargs)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, 'db_config'):
            return
        
        env_path = get_external_path(".env")
        load_dotenv(env_path)
        
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_NAME'), 
            'port': int(os.getenv('DB_PORT', 3306))
        }
        
        if not all([self.db_config['user'], self.db_config['password'], self.db_config['database']]):
            raise ValueError("Database configuration is missing in .env file.")

        self._ensure_database_exists()

        if Database._pool is None:
            try:
                Database._pool = pooling.MySQLConnectionPool(
                    pool_name="modernlam_pool",
                    pool_size=32, 
                    pool_reset_session=True,
                    use_pure=True,
                    auth_plugin='mysql_native_password',
                    **self.db_config
                )
                logging.info("🚀 Connection Pool initialized successfully (Size: 3).")
            except Exception as e:
                logging.error(f"❌ Failed to initialize Connection Pool: {e}")
                raise

        try:
            db_url = (f"mysql+mysqlconnector://{self.db_config['user']}:{self.db_config['password']}"
                      f"@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")
            self.engine = create_engine(db_url, connect_args={'use_pure': True, 'auth_plugin': 'mysql_native_password'}, echo=False)
        except Exception as e:
            logging.error(f"Failed to create SQLAlchemy engine: {e}")

        is_local = self.db_config['host'] in ['127.0.0.1', 'localhost']
        if is_local:
            self._initialize_schema()

    def _ensure_database_exists(self):
        try:
            conn_config = self.db_config.copy()
            db_name = conn_config.pop('database')
            conn_config['use_pure'] = True
            conn_config['auth_plugin'] = 'mysql_native_password'

            with mysql.connector.connect(**conn_config) as conn:
                cursor = conn.cursor()
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        except mysql.connector.Error as err:
            logging.error(f"❌ Could not verify/create database: {err}")
            raise

    @contextmanager
    def get_db_connection(self):
        conn = None
        try:
            conn = Database._pool.get_connection()
            yield conn
            conn.commit()
        except mysql.connector.Error as err:
            logging.error(f"Database error: {err}")
            if conn: conn.rollback()
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    def get_raw_connection(self):
        return Database._pool.get_connection()
    
    def _initialize_schema(self): 
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SHOW TABLES LIKE 'Users'")
                if cursor.fetchone():
                    logging.info("⚡ Schema exists. Skipping initialization checks.")
                    return
        except:
            pass      
        schema_queries = [    

            """CREATE USER 'root'@'%' IDENTIFIED BY 'root';
            GRANT ALL PRIVILEGES ON Lab_Inventory_Enterprise_DB.* TO 'root'@'%';
            FLUSH PRIVILEGES;
            """,   
            # --- 1. Users & Auth ---
            """CREATE TABLE IF NOT EXISTS Users (
                User_ID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                Username VARCHAR(50) NOT NULL UNIQUE,
                Password VARCHAR(255) NOT NULL,
                Role ENUM('Admin', 'Manager', 'Technician') DEFAULT 'Technician',
                Full_Name VARCHAR(100),
                Is_Active BOOLEAN DEFAULT TRUE,
                Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );""",
            
            """INSERT IGNORE INTO Users (Username, Password, Role, Full_Name) 
            VALUES ('admin', 'admin123', 'Admin', 'Administrateur Système');""",

            # --- 2. MASTER DATA ---
            """CREATE TABLE IF NOT EXISTS Location_Types (
                Type_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Type_Name VARCHAR(50) NOT NULL UNIQUE,
                Description VARCHAR(150) NULL
            );""",

            """CREATE TABLE IF NOT EXISTS Product_Families (
                Family_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Family_Name VARCHAR(100) NOT NULL UNIQUE,
                Deleted_At DATETIME NULL
            );""",

            """CREATE TABLE IF NOT EXISTS Packaging_Units (
                Unit_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Unit_Name VARCHAR(50) NOT NULL UNIQUE,
                Description VARCHAR(150) NULL,
                Deleted_At DATETIME NULL
            );""",

            """CREATE TABLE IF NOT EXISTS Manufacturers (
                Manuf_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Manuf_Name VARCHAR(150) NOT NULL UNIQUE,
                Country_of_Origin VARCHAR(100) NULL,
                Website VARCHAR(200) NULL,
                Deleted_At DATETIME NULL
            );""",
            
            """CREATE TABLE IF NOT EXISTS Suppliers (
                Supplier_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Supplier_Name VARCHAR(255) NOT NULL UNIQUE,
                Contact_Person VARCHAR(150) NULL,
                Phone VARCHAR(50) NULL,
                Email VARCHAR(150) NULL,
                Website VARCHAR(200) NULL,
                Address_Line1 VARCHAR(255) NULL,
                Address_Line2 VARCHAR(255) NULL,
                City VARCHAR(100) NULL,
                Postal_Code VARCHAR(20) NULL,
                Tax_ID_Number VARCHAR(100) NULL,
                Commercial_Reg_No VARCHAR(100) NULL,
                Bank_Name VARCHAR(150) NULL,
                Bank_Account_IBAN VARCHAR(150) NULL,
                Deleted_At DATETIME NULL
            );""",
            
            """CREATE TABLE IF NOT EXISTS External_Partners (
                Partner_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Partner_Name VARCHAR(255) NOT NULL UNIQUE,
                Partner_Type ENUM('Laboratory', 'Doctor', 'Hospital', 'Other') DEFAULT 'Laboratory',
                Agrement_Number VARCHAR(100) NULL,
                Contact_Person VARCHAR(150) NULL,
                Phone VARCHAR(50) NULL,
                Email VARCHAR(150) NULL,
                Website VARCHAR(200) NULL,
                Address_Line1 VARCHAR(255) NULL,
                Address_Line2 VARCHAR(255) NULL,
                City VARCHAR(100) NULL,
                Postal_Code VARCHAR(20) NULL,
                Tax_ID_Number VARCHAR(100) NULL,
                Commercial_Reg_No VARCHAR(100) NULL,
                Bank_Name VARCHAR(150) NULL,
                Bank_Account_IBAN VARCHAR(150) NULL,
                Deleted_At DATETIME NULL
            );""",

            """CREATE TABLE IF NOT EXISTS Locations (
                Location_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Location_Name VARCHAR(100) NOT NULL, 
                Parent_Location_ID INT UNSIGNED NULL,
                Type_ID INT UNSIGNED NULL,
                Temperature_Zone ENUM('Room Temp', 'Refrigerated 2-8', 'Frozen -20', 'Deep Freeze -80') NOT NULL DEFAULT 'Room Temp',
                Deleted_At DATETIME NULL,
                FOREIGN KEY (Parent_Location_ID) REFERENCES Locations(Location_ID) ON DELETE SET NULL ON UPDATE CASCADE,
                FOREIGN KEY (Type_ID) REFERENCES Location_Types(Type_ID) ON DELETE SET NULL ON UPDATE CASCADE
            );""",
            
            """INSERT IGNORE INTO Location_Types (Type_Name) VALUES 
               ('Bâtiment'), ('Étage'), ('Salle'), ('Réfrigérateur'), ('Congélateur'), ('Étagère'), ('Boîte');""",
            
            """CREATE TABLE IF NOT EXISTS Automates (
                Automate_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Automate_Name VARCHAR(150) NOT NULL UNIQUE,
                Model_Number VARCHAR(100) NULL,
                Serial_Number VARCHAR(100) NULL,
                Date_of_Purchase DATE NULL,
                Location_ID INT UNSIGNED NULL,
                Deleted_At DATETIME NULL,
                FOREIGN KEY (Location_ID) REFERENCES Locations(Location_ID) ON DELETE SET NULL ON UPDATE CASCADE
            );""",
            
            """CREATE TABLE IF NOT EXISTS Waste_Reasons (
                Reason_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Reason_Name VARCHAR(100) NOT NULL,
                Is_Active BOOLEAN DEFAULT TRUE
            );""",
            
            """CREATE TABLE IF NOT EXISTS Products_Master (
                Product_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Product_Name VARCHAR(255) NOT NULL,
                Family_ID INT UNSIGNED NOT NULL DEFAULT 1, 
                Barcode VARCHAR(100) NULL,
                Ordering_Unit VARCHAR(50) NOT NULL DEFAULT 'Carton',
                Stock_Unit VARCHAR(50) NOT NULL DEFAULT 'Box/Kit',
                Stock_Qty_Per_Order_Unit INT UNSIGNED NOT NULL DEFAULT 1,
                Usage_Unit VARCHAR(50) NOT NULL DEFAULT 'Test',
                Usage_Qty_Per_Stock_Unit DECIMAL(10, 2) NOT NULL DEFAULT 1.00,
                Manuf_Cat_No VARCHAR(100) NULL,
                Minimum_Stock_Level INT UNSIGNED NOT NULL DEFAULT 5,
                Alert_Before_Expiry_Days INT UNSIGNED DEFAULT 30,
                Open_Vial_Stability_Days INT UNSIGNED NULL,
                Manuf_ID INT UNSIGNED NOT NULL,
                Preferred_Automate_ID INT UNSIGNED NULL,
                Storage_Temp_Req VARCHAR(50) NULL,
                Is_Billable BOOLEAN DEFAULT FALSE, 
                Deleted_At DATETIME NULL,
                FOREIGN KEY (Family_ID) REFERENCES Product_Families(Family_ID) ON UPDATE CASCADE,
                FOREIGN KEY (Manuf_ID) REFERENCES Manufacturers(Manuf_ID) ON UPDATE CASCADE,
                FOREIGN KEY (Preferred_Automate_ID) REFERENCES Automates(Automate_ID) ON DELETE SET NULL ON UPDATE CASCADE
            );""",

            """CREATE TABLE IF NOT EXISTS Product_Documents (
                Doc_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Product_ID INT UNSIGNED NOT NULL,
                Doc_Type ENUM('COA', 'MSDS', 'Package Insert', 'Contract') NOT NULL,
                File_Path VARCHAR(255) NOT NULL,
                Upload_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON DELETE CASCADE ON UPDATE CASCADE
            );""",
            
            # --- 3. PROCUREMENT CYCLE ---
            # تم التحديث بناءً على Dump (إضافة Invoice_Ref و Deleted_At و Status Enum الصحيح)
            """
            CREATE TABLE IF NOT EXISTS Purchase_Orders (
                PO_ID BIGINT UNSIGNED PRIMARY KEY, 
                Supplier_ID INT UNSIGNED NOT NULL,
                Order_Date DATE NOT NULL,
                Expected_Delivery_Date DATE,
                Status ENUM('Draft', 'Sent', 'Partial_Received', 'Completed', 'Cancelled') DEFAULT 'Draft',
                Notes TEXT,
                Created_By INT UNSIGNED,
                Total_Amount_HT DECIMAL(15, 2) DEFAULT 0.00,
                Total_Tax_Amount DECIMAL(15, 2) DEFAULT 0.00,
                Total_Amount_TTC DECIMAL(15, 2) DEFAULT 0.00,
                Supplier_Invoice_Ref VARCHAR(150) NULL,
                Reception_Date DATETIME NULL,
                Updated_At DATETIME NULL,
                Deleted_At DATETIME NULL,
                FOREIGN KEY (Supplier_ID) REFERENCES Suppliers(Supplier_ID) ON UPDATE CASCADE,
                FOREIGN KEY (Created_By) REFERENCES Users(User_ID)
            );
            """,
            
            """CREATE TABLE IF NOT EXISTS PO_Details (
                ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                PO_ID BIGINT UNSIGNED NOT NULL, 
                Product_ID INT UNSIGNED NOT NULL,
                Qty_Ordered INT UNSIGNED NOT NULL,
                Ordering_Unit VARCHAR(50) DEFAULT NULL,
                Unit_Price_HT DECIMAL(10, 2) DEFAULT 0.00,
                Discount_Percent DECIMAL(5, 2) DEFAULT 0.00,
                Tax_Rate_Percent DECIMAL(5, 2) DEFAULT 0.00,
                Line_Total_HT DECIMAL(15, 2) DEFAULT 0.00,
                Line_Total_TTC DECIMAL(15, 2) DEFAULT 0.00,
                Item_Note VARCHAR(255) NULL, 
                FOREIGN KEY (PO_ID) REFERENCES Purchase_Orders(PO_ID) ON DELETE CASCADE ON UPDATE CASCADE,
                FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE
            );"""
            
            # --- 4. INVENTORY & RECEPTION ---
            # تم التحديث بناءً على Dump (إضافة Status, Variance_Notes, Total_Discount)
            """
            CREATE TABLE IF NOT EXISTS Reception_Log (
                BR_ID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                PO_ID BIGINT UNSIGNED DEFAULT NULL,
                Supplier_Invoice_Ref VARCHAR(150) NULL,
                Supplier_BL_Ref VARCHAR(150) NULL,
                Document_Type ENUM('Facture', 'BL', 'Both', 'None') NOT NULL DEFAULT 'Facture',
                Reception_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
                Supplier_ID INT UNSIGNED DEFAULT NULL,
                Invoice_Total_HT DECIMAL(15, 2) DEFAULT 0.00,
                Invoice_Total_TVA DECIMAL(15, 2) DEFAULT 0.00,
                Invoice_Total_TTC DECIMAL(15, 2) DEFAULT 0.00,
                Status ENUM('Completed', 'Variance Detected', 'Pending Audit') DEFAULT 'Completed',
                Variance_Notes TEXT NULL,
                Receiver_User_ID INT UNSIGNED DEFAULT NULL, 
                Received_By INT UNSIGNED DEFAULT NULL, 
                Total_Discount DECIMAL(15, 2) DEFAULT 0.00,
                UNIQUE KEY uq_supplier_bl (Supplier_ID, Supplier_BL_Ref),
                UNIQUE KEY uq_supplier_invoice (Supplier_ID, Supplier_Invoice_Ref),
                FOREIGN KEY (PO_ID) REFERENCES Purchase_Orders(PO_ID) ON DELETE SET NULL ON UPDATE CASCADE,
                FOREIGN KEY (Supplier_ID) REFERENCES Suppliers(Supplier_ID) ON UPDATE CASCADE,
                FOREIGN KEY (Received_By) REFERENCES Users(User_ID)
            );
            """,

            """CREATE TABLE IF NOT EXISTS Reception_Details (
                Detail_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                BR_ID INT UNSIGNED NOT NULL,
                PO_Detail_ID INT UNSIGNED NULL,
                Product_ID INT UNSIGNED NOT NULL,
                Qty_Ordered INT UNSIGNED NULL,
                Qty_Received INT UNSIGNED NOT NULL,
                Unit_Price_Received DECIMAL(10, 2) DEFAULT 0.00,
                Line_Note TEXT NULL,
                FOREIGN KEY (BR_ID) REFERENCES Reception_Log(BR_ID) ON DELETE CASCADE ON UPDATE CASCADE,
                FOREIGN KEY (PO_Detail_ID) REFERENCES PO_Details(ID) ON DELETE SET NULL ON UPDATE CASCADE,
                FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE
            );""",
            
            """CREATE TABLE IF NOT EXISTS Inventory_Batches (
                Batch_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                Internal_Barcode VARCHAR(50) NULL,
                Product_ID INT UNSIGNED NOT NULL,
                Location_ID INT UNSIGNED NOT NULL,
                Lot_Number VARCHAR(100) NOT NULL,
                Expiry_Date DATE NULL,
                Quantity_Initial INT UNSIGNED NOT NULL,
                Quantity_Current INT UNSIGNED NOT NULL,
                Unit_Price_Received DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
                Tax_Rate_Percent DECIMAL(5, 2) DEFAULT 0.00,
                Discount_Percent DECIMAL(5, 2) DEFAULT 0.00,
                PO_ID BIGINT UNSIGNED NULL,
                BR_ID INT UNSIGNED NULL,
                Status ENUM('Available', 'Quarantined', 'Expired', 'Depleted') DEFAULT 'Available',
                Reception_Note TEXT NULL, 
                Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (Batch_ID),
                FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE,
                FOREIGN KEY (Location_ID) REFERENCES Locations(Location_ID) ON UPDATE CASCADE,
                FOREIGN KEY (PO_ID) REFERENCES Purchase_Orders(PO_ID) ON DELETE SET NULL ON UPDATE CASCADE,
                FOREIGN KEY (BR_ID) REFERENCES Reception_Log(BR_ID) ON DELETE SET NULL ON UPDATE CASCADE
            );""",
            
            """CREATE TABLE IF NOT EXISTS Active_Containers (
                Container_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Parent_Batch_ID BIGINT UNSIGNED NOT NULL,
                Product_ID INT UNSIGNED NOT NULL,
                Date_Opened DATETIME DEFAULT CURRENT_TIMESTAMP,
                Open_Expiration_Date DATE NOT NULL,
                Initial_Usage_Qty DECIMAL(10, 2) NOT NULL,
                Remaining_Usage_Qty DECIMAL(10, 2) NOT NULL,
                Current_Location_ID INT UNSIGNED NULL,
                Status ENUM('In_Use', 'Empty', 'Discarded') DEFAULT 'In_Use',
                FOREIGN KEY (Parent_Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON UPDATE CASCADE,
                FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE,
                FOREIGN KEY (Current_Location_ID) REFERENCES Locations(Location_ID) ON DELETE SET NULL ON UPDATE CASCADE
            );""",

            # --- 5. EXTERNAL & TRANSFERS ---
            """CREATE TABLE IF NOT EXISTS External_Transfer_Log (
                Transfer_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Transaction_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
                Partner_ID INT UNSIGNED NOT NULL,
                Transfer_Type ENUM('Free', 'Paid') DEFAULT 'Free', 
                Total_Amount DECIMAL(15, 2) DEFAULT 0.00, 
                Status ENUM('Draft', 'Completed', 'Cancelled') DEFAULT 'Draft',
                Notes TEXT,
                Created_By INT UNSIGNED,
                FOREIGN KEY (Partner_ID) REFERENCES External_Partners(Partner_ID) ON UPDATE CASCADE,
                FOREIGN KEY (Created_By) REFERENCES Users(User_ID)
            );""",

            """CREATE TABLE IF NOT EXISTS External_Transfer_Details (
                Detail_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Transfer_ID INT UNSIGNED NOT NULL,
                Product_ID INT UNSIGNED NOT NULL,
                Batch_ID BIGINT UNSIGNED NOT NULL,
                Qty_Transferred DECIMAL(10, 2) NOT NULL,
                Unit_Price DECIMAL(10, 2) DEFAULT 0.00,
                Line_Total DECIMAL(15, 2) DEFAULT 0.00,
                Line_Note TEXT NULL,
                FOREIGN KEY (Transfer_ID) REFERENCES External_Transfer_Log(Transfer_ID) ON DELETE CASCADE,
                FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE,
                FOREIGN KEY (Batch_ID) REFERENCES Inventory_Batches(Batch_ID)
            );""",
            
            # --- 6. AUDIT TRAIL ---
            # تم التحديث ليشمل External_Transfer في Enum
            """CREATE TABLE IF NOT EXISTS Stock_Movement_Log (
                Movement_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Transaction_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
                User_ID INT UNSIGNED DEFAULT NULL,
                Product_ID INT UNSIGNED NOT NULL,
                Batch_ID BIGINT UNSIGNED NULL,
                Container_ID BIGINT UNSIGNED NULL,
                Movement_Type ENUM(
                    'Purchase_Receive', 'Open_Pack', 'Patient_Test', 'QC_Run', 
                    'Calibration', 'Adjustment', 'Waste', 'Transfer', 
                    'External_Transfer', 'Return_To_Supplier'
                ) NOT NULL,
                Reason_ID INT UNSIGNED NULL,
                Qty_Change DECIMAL(10, 2) NOT NULL,
                Unit_Used VARCHAR(50) NOT NULL,
                Notes TEXT NULL,
                Stock_After DECIMAL(15, 2) DEFAULT NULL, -- [العمود المفقود تم إضافته هنا]
                FOREIGN KEY (User_ID) REFERENCES Users(User_ID),
                FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE,
                FOREIGN KEY (Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON UPDATE CASCADE,
                FOREIGN KEY (Container_ID) REFERENCES Active_Containers(Container_ID) ON UPDATE CASCADE,
                FOREIGN KEY (Reason_ID) REFERENCES Waste_Reasons(Reason_ID) ON DELETE SET NULL ON UPDATE CASCADE
            );""",

            """CREATE TABLE IF NOT EXISTS Supplier_Credit_Notes (
                Credit_Note_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Credit_Note_Ref VARCHAR(150) NOT NULL,  -- مثال: C3918/2025
                Supplier_ID INT UNSIGNED NOT NULL,      -- يربط مع UMC LAB PLUS
                BR_ID INT UNSIGNED NULL,                -- ربط اختياري مع وصل الاستلام الأصلي
                Credit_Date DATE NOT NULL,              -- مثال: 30/12/2025
                
                -- نوع الـ Avoir: هل هو إرجاع بضاعة أم تصحيح مالي فقط؟
                Type ENUM('Return_Goods', 'Price_Correction', 'Billing_Error') DEFAULT 'Return_Goods',
                
                Status ENUM('Draft', 'Validated', 'Used') DEFAULT 'Draft',
                
                -- المبالغ المالية
                Total_Amount_HT DECIMAL(15, 2) DEFAULT 0.00,
                Total_TVA DECIMAL(15, 2) DEFAULT 0.00,
                Total_Amount_TTC DECIMAL(15, 2) DEFAULT 0.00, -- مثال: 62307.21
                
                Notes TEXT NULL,                        -- ملاحظات إضافية (مثل اسم البائع: RACHA SIRINE)
                Created_By INT UNSIGNED NULL,
                Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (Supplier_ID) REFERENCES Suppliers(Supplier_ID) ON UPDATE CASCADE,
                FOREIGN KEY (BR_ID) REFERENCES Reception_Log(BR_ID) ON DELETE SET NULL,
                FOREIGN KEY (Created_By) REFERENCES Users(User_ID)
            );""",


            """CREATE TABLE IF NOT EXISTS Credit_Note_Details (
                Detail_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Credit_Note_ID INT UNSIGNED NOT NULL,
                Product_ID INT UNSIGNED NOT NULL,
                
                -- الربط مع المخزون (هام جداً بناءً على الصورة)
                Batch_ID BIGINT UNSIGNED NULL,          -- لربطها بالباتش في النظام لدينا
                Lot_Number VARCHAR(100) NULL,           -- لتخزين "032535A" كما في الصورة
                Expiry_Date DATE NULL,                  -- لتخزين "01/05/28" كما في الصورة
                
                Qty_Returned DECIMAL(10, 2) DEFAULT 0.00, -- الكمية المرجعة (مثال: 10)
                
                Unit_Price DECIMAL(10, 2) NOT NULL,       -- سعر الوحدة في الـ Avoir
                Line_Total DECIMAL(15, 2) NOT NULL,       -- المجموع للسطر
                
                FOREIGN KEY (Credit_Note_ID) REFERENCES Supplier_Credit_Notes(Credit_Note_ID) ON DELETE CASCADE,
                FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID),
                FOREIGN KEY (Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON DELETE SET NULL
            );""",

            """CREATE TABLE IF NOT EXISTS Supplier_Payments (
                Payment_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Supplier_ID INT UNSIGNED NOT NULL,
                Payment_Date DATE NOT NULL,
                Amount DECIMAL(15, 2) NOT NULL,
                Payment_Method ENUM('Espèce', 'Chèque', 'Virement', 'Versement', 'Autre') DEFAULT 'Espèce',
                Reference VARCHAR(100) NULL, 
                Notes TEXT NULL,
                Created_By INT UNSIGNED NULL,
                Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (Supplier_ID) REFERENCES Suppliers(Supplier_ID) ON UPDATE CASCADE,
                FOREIGN KEY (Created_By) REFERENCES Users(User_ID)
            );""",


        ]
        
        index_queries = [
            "CREATE INDEX idx_product_barcode ON Products_Master(Barcode);",
            "CREATE INDEX idx_batch_expiry ON Inventory_Batches(Expiry_Date);",
            "CREATE INDEX idx_batch_lot ON Inventory_Batches(Lot_Number);",
            "CREATE INDEX idx_internal_barcode ON Inventory_Batches(Internal_Barcode);",
            "CREATE UNIQUE INDEX uq_inventory_internal_barcode ON Inventory_Batches(Internal_Barcode);",
            "CREATE UNIQUE INDEX idx_barcode_location ON Inventory_Batches(Internal_Barcode, Location_ID);",
            "CREATE INDEX idx_reception_invoice_ref ON Reception_Log(Supplier_Invoice_Ref);",
            "CREATE INDEX idx_reception_po_id ON Reception_Log(PO_ID);",
            "CREATE INDEX idx_movement_date ON Stock_Movement_Log(Transaction_Date);",
            "CREATE INDEX idx_movement_type ON Stock_Movement_Log(Movement_Type);",
            "CREATE INDEX idx_reception_details_br ON Reception_Details(BR_ID);",
            "CREATE INDEX idx_reception_details_product ON Reception_Details(Product_ID);",
            "CREATE INDEX idx_partner_name ON External_Partners(Partner_Name);",
            "CREATE INDEX idx_transfer_date ON External_Transfer_Log(Transaction_Date);",
            "CREATE INDEX idx_transfer_partner ON External_Transfer_Log(Partner_ID);",
        ]

        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                # تعطيل فحص القيود مؤقتاً لتجنب مشاكل ترتيب الإنشاء
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
                
                logging.info("Initializing schema tables...")
                for query in schema_queries:
                    try:
                        cursor.execute(query)
                        while cursor.nextset(): pass
                    except mysql.connector.Error as err:
                        logging.warning(f"Schema warning: {err}")
                
                # --- AUTO MIGRATIONS (Safety net for future updates) ---
                
                # 1. Purchase_Orders: Ensure columns exist
                try:
                    cursor.execute("SHOW COLUMNS FROM Purchase_Orders LIKE 'Supplier_Invoice_Ref'")
                    if not cursor.fetchone():
                        cursor.execute("ALTER TABLE Purchase_Orders ADD COLUMN Supplier_Invoice_Ref VARCHAR(150) NULL;")
                    
                    cursor.execute("SHOW COLUMNS FROM Purchase_Orders LIKE 'Deleted_At'")
                    if not cursor.fetchone():
                        cursor.execute("ALTER TABLE Purchase_Orders ADD COLUMN Deleted_At DATETIME NULL;")
                except Exception: pass

                # 2. Reception_Log: Ensure columns exist
                try:
                    cursor.execute("SHOW COLUMNS FROM Reception_Log LIKE 'Variance_Notes'")
                    if not cursor.fetchone():
                        cursor.execute("ALTER TABLE Reception_Log ADD COLUMN Variance_Notes TEXT NULL;")
                    
                    cursor.execute("SHOW COLUMNS FROM Reception_Log LIKE 'Total_Discount'")
                    if not cursor.fetchone():
                        cursor.execute("ALTER TABLE Reception_Log ADD COLUMN Total_Discount DECIMAL(15,2) DEFAULT 0.00;")
                except Exception: pass
                
                # 3. Create Indexes
                logging.info("Creating performance indexes...")
                for query in index_queries:
                    try:
                        cursor.execute(query)
                        while cursor.nextset(): pass
                    except mysql.connector.Error:
                        continue 

                try:
                    cursor.execute("SHOW COLUMNS FROM Supplier_Payments LIKE 'BR_ID'")
                    if not cursor.fetchone():
                        logging.info("Migration: Adding BR_ID to Supplier_Payments...")
                        cursor.execute("ALTER TABLE Supplier_Payments ADD COLUMN BR_ID INT UNSIGNED NULL;")
                        cursor.execute("ALTER TABLE Supplier_Payments ADD CONSTRAINT fk_payment_br FOREIGN KEY (BR_ID) REFERENCES Reception_Log(BR_ID) ON DELETE SET NULL;")
                except Exception as e:
                    logging.warning(f"Migration error (Supplier_Payments): {e}")
                
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
                logging.info("✅ Schema initialized successfully.")


                


        except mysql.connector.Error as err:
            logging.error(f"❌ Failed to initialize schema: {err}")

    def backup_database_csv(self, output_zip_path):
        """تصدير كامل لقاعدة البيانات مع معالجة دقيقة للمسارات والاتصالات."""
        # استخدام مسار مطلق للمجلد المؤقت لتجنب مشاكل الصلاحيات
        temp_dir = os.path.abspath('temp_backup_csv')
        conn_sqlalchemy = None
        
        try:
            # 1. تنظيف وتجهيز المجلد المؤقت
            if os.path.exists(temp_dir): 
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)

            # 2. التأكد من أن محرك SQLAlchemy يعمل
            try:
                conn_sqlalchemy = self.engine.connect()
            except Exception as e:
                logging.error(f"❌ SQLAlchemy Connection Failed: {e}")
                return False, f"فشل الاتصال بمحرك SQLAlchemy: {e}"

            # 3. جلب قائمة الجداول الفعلية من قاعدة البيانات
            inspector = sqlalchemy.inspect(self.engine)
            all_db_tables = inspector.get_table_names()
            
            if not all_db_tables:
                return False, "قاعدة البيانات فارغة، لا توجد جداول لتصديرها."

            # 4. دمج قائمة الترتيب مع الجداول المتبقية
            tables_to_export = [tbl for tbl in TABLE_IMPORT_ORDER if tbl in all_db_tables]
            for tbl in all_db_tables:
                if tbl not in tables_to_export:
                    tables_to_export.append(tbl)

            exported_count = 0

            # 5. عملية التصدير
            for table_name in tables_to_export:
                csv_path = os.path.join(temp_dir, f"{table_name}.csv")
                try:
                    # قراءة الجدول باستخدام Pandas
                    # استخدام SQL المباشر مع SQLAlchemy لتجنب مشاكل التنسيق
                    df = pd.read_sql_query(text(f"SELECT * FROM `{table_name}`"), conn_sqlalchemy)
                    
                    if df.empty:
                        # إنشاء ملف فارغ بالأعمدة فقط للحفاظ على الهيكل عند الاستعادة
                        df.to_csv(csv_path, index=False, encoding='utf-8', na_rep='<NULL>')
                        logging.info(f"⚪ Table {table_name} is empty, exported header only.")
                    else:
                        # معالجة التواريخ لضمان عدم تحولها لنصوص غير مفهومة
                        for col in df.select_dtypes(include=['datetime64[ns]', 'datetime']).columns:
                            df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S').replace('NaT', None)

                        # الحفظ بتنسيق CSV
                        df.to_csv(csv_path, index=False, encoding='utf-8', na_rep='<NULL>')
                        exported_count += 1
                        logging.info(f"✅ Exported table: {table_name} ({len(df)} rows)")

                except Exception as e:
                    logging.warning(f"⚠️ Could not backup table {table_name}: {e}")

            # 6. ضغط الملفات في ملف ZIP واحد
            if exported_count >= 0:
                with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, _, files in os.walk(temp_dir):
                        for file in files:
                            zipf.write(os.path.join(root, file), file)
                
                return True, f"تم إنشاء النسخة الاحتياطية بنجاح: {os.path.basename(output_zip_path)}"
            else:
                return False, "فشل تصدير أي بيانات."

        except Exception as e:
            logging.error(f"❌ Backup failed: {e}")
            return False, f"خطأ غير متوقع أثناء النسخ الاحتياطي: {str(e)}"
        
        finally:
            # إغلاق الاتصال وتنظيف الملفات المؤقتة
            if conn_sqlalchemy:
                conn_sqlalchemy.close()
            if os.path.exists(temp_dir): 
                shutil.rmtree(temp_dir)

    def restore_database_csv(self, input_zip_path):
        """
        استعادة آمنة: لا تقوم بمسح البيانات إلا إذا كان الملف البديل يحتوي على بيانات فعلاً.
        """
        import numpy as np
        
        temp_dir = 'temp_restore_csv'
        conn = None
        try:
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            with zipfile.ZipFile(input_zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            conn = self.get_raw_connection()
            conn.start_transaction() 
            cursor = conn.cursor()
            
            # تعطيل القيود مؤقتاً
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            
            # تحديد الجداول الموجودة في النسخة الاحتياطية
            backup_files = [f for f in os.listdir(temp_dir) if f.endswith('.csv')]
            
            # قائمة الجداول التي سيتم استعادتها فعلياً (التي تحتوي على بيانات فقط)
            tables_to_restore_data = []

            logging.info("🔍 Pre-checking backup files...")

            # 1. فحص الملفات قبل الحذف (Safety Check)
            for file_name in backup_files:
                table_name = file_name.replace('.csv', '')
                csv_path = os.path.join(temp_dir, file_name)
                
                try:
                    # قراءة سريعة للتأكد هل الملف فارغ أم لا
                    df_check = pd.read_csv(csv_path, nrows=1) 
                    if df_check.empty:
                        logging.warning(f"⚠️ Backup file for '{table_name}' is EMPTY. Skipping restore for this table to preserve current data.")
                        continue # تخطي هذا الجدول، لن نمسح البيانات الحالية
                    
                    # إذا وصلنا هنا، فالملف يحتوي على بيانات، نضيفه للقائمة
                    tables_to_restore_data.append(table_name)
                    
                except Exception as e:
                    logging.warning(f"⚠️ Error checking file {file_name}: {e}")
                    continue

            if not tables_to_restore_data:
                logging.warning("🛑 No data found in the backup file. Operation aborted to protect database.")
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
                return False, "ملف النسخة الاحتياطية فارغ! لم يتم تغيير أي شيء في قاعدة البيانات."

            # 2. مرحلة التنظيف (Cleaning Phase) - فقط للجداول التي لها بديل
            logging.info(f"🧹 Cleaning existing data for {len(tables_to_restore_data)} tables...")
            
            cursor.execute("SHOW TABLES")
            existing_db_tables = [row[0] for row in cursor.fetchall()]

            for table_to_clean in tables_to_restore_data:
                # التحقق من وجود الجدول في القاعدة
                match = next((t for t in existing_db_tables if t.lower() == table_to_clean.lower()), None)
                if match:
                    try:
                        cursor.execute(f"DELETE FROM `{match}`")
                        logging.info(f"   - Cleared table: {match}")
                    except Exception as e:
                        logging.warning(f"   - Failed to clear {match}: {e}")

            # 3. مرحلة الاستعادة (Restore Phase)
            logging.info("📥 Restoring data...")
            
            # ترتيب الاستعادة حسب الأهمية
            ordered_tables = [t for t in TABLE_IMPORT_ORDER if t in tables_to_restore_data]
            remaining_tables = [t for t in tables_to_restore_data if t not in TABLE_IMPORT_ORDER]
            final_restore_list = ordered_tables + remaining_tables

            for table_name in final_restore_list:
                csv_file = os.path.join(temp_dir, f"{table_name}.csv")
                
                try:
                    df = pd.read_csv(csv_file, keep_default_na=False, na_values=['<NULL>', 'nan', 'NaN'])
                except:
                    continue

                df = df.replace({np.nan: None})
                
                # تنظيف الأعمدة
                df.columns = df.columns.astype(str)
                df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]
                
                # مطابقة الأعمدة مع قاعدة البيانات
                with self.engine.connect() as conn_inner:
                    try:
                        result = conn_inner.execute(text(f"SHOW COLUMNS FROM `{table_name}`"))
                        db_columns = [row[0] for row in result.fetchall()]
                    except:
                        continue

                common_cols = [col for col in df.columns if col in db_columns]
                if not common_cols: continue

                df = df[common_cols]
                
                cols = ",".join([f"`{col}`" for col in common_cols])
                placeholders = ",".join(["%s"] * len(common_cols))
                sql = f"INSERT INTO `{table_name}` ({cols}) VALUES ({placeholders})"

                cleaned_data = []
                for row in df.values.tolist():
                    new_row = []
                    for val in row:
                        if val == '<NULL>' or pd.isna(val) or val == 'NaT' or val == '':
                            new_row.append(None)
                        else:
                            new_row.append(val)
                    cleaned_data.append(tuple(new_row))

                batch_size = 1000
                for i in range(0, len(cleaned_data), batch_size):
                    batch = cleaned_data[i:i + batch_size]
                    cursor.executemany(sql, batch)
                
                logging.info(f"✅ Restored {len(cleaned_data)} rows to {table_name}")

            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            conn.commit()
            return True, "Database restored successfully (Empty files were skipped)."

        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"❌ Restore failed: {e}")
            return False, str(e)
        finally:
            if conn and conn.is_connected(): conn.close()
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir)

    def backup_database_excel(self, output_zip_path):
        """تصدير كامل لقاعدة البيانات بصيغة Excel مضغوطة."""
        import os
        import shutil
        import zipfile
        import pandas as pd
        from sqlalchemy import text

        temp_dir = 'temp_backup_excel'
        try:
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            with self.engine.connect() as conn:
                # جلب كافة الجداول الفعلية
                from sqlalchemy import inspect
                inspector = inspect(self.engine)
                all_db_tables = inspector.get_table_names()

                for table_name in all_db_tables:
                    excel_path = os.path.join(temp_dir, f"{table_name}.xlsx")
                    try:
                        # قراءة البيانات
                        df = pd.read_sql(text(f"SELECT * FROM `{table_name}`"), conn)
                        
                        # حفظ كملف Excel باستخدام engine 'openpyxl'
                        df.to_excel(excel_path, index=False, engine='openpyxl')
                        logging.info(f"✅ Exported: {table_name}")
                    except Exception as e:
                        logging.warning(f"⚠️ Could not backup table {table_name}: {e}")
            
            # ضغط الملفات
            with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        zipf.write(os.path.join(root, file), file)
            
            return True, "Success"
        except Exception as e:
            logging.error(f"❌ Backup failed: {e}")
            return False, str(e)
        finally:
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir)

    def restore_database_excel(self, input_zip_path):
        """
        استعادة قاعدة البيانات من ملفات Excel مع معالجة ذكية للقيم الفارغة (NULL)
        لتجنب خطأ Column 'Lot_Number' cannot be null.
        """
        import os
        import shutil
        import zipfile
        import pandas as pd
        import numpy as np
        from sqlalchemy import text

        temp_dir = 'temp_restore_excel'
        conn = None
        try:
            if os.path.exists(temp_dir): 
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            with zipfile.ZipFile(input_zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            conn = self.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()
            
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            
            excel_files = [f for f in os.listdir(temp_dir) if f.endswith('.xlsx')]
            
            TABLE_IMPORT_ORDER = [
                'Users', 'Location_Types', 'Product_Families', 'Packaging_Units', 
                'Manufacturers', 'Suppliers', 'External_Partners', 'Locations', 
                'Automates', 'Waste_Reasons', 'Products_Master', 'Purchase_Orders', 
                'PO_Details', 'Reception_Log', 'Reception_Details', 'Inventory_Batches',
                'Supplier_Credit_Notes','Credit_Note_Details'
            ]

            ordered_files = [f"{t}.xlsx" for t in TABLE_IMPORT_ORDER if f"{t}.xlsx" in excel_files]
            other_files = [f for f in excel_files if f not in ordered_files]
            
            for file_name in (ordered_files + other_files):
                table_name = file_name.replace('.xlsx', '')
                file_path = os.path.join(temp_dir, file_name)
                
                try:
                    df = pd.read_excel(file_path, engine='openpyxl')
                    
                    df.columns = df.columns.astype(str)
                    df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]
                    
                    if df.empty:
                        logging.info(f"⚪ Skipping empty table: {table_name}")
                        continue

                    cursor.execute(f"DELETE FROM `{table_name}`")
                    
                    cleaned_data = []
                    for _, row_data in df.iterrows():
                        row_list = []
                        for col in df.columns:
                            val = row_data[col]
                            
                            # معالجة خاصة لعمود رقم اللوت (Lot_Number)
                            # إذا كانت القيمة فارغة، نضع قيمة افتراضية لمنع الخطأ 1048
                            if col == 'Lot_Number' and (pd.isna(val) or str(val).strip() == ''):
                                row_list.append("NON_DEFINI") 
                            elif pd.isna(val) or str(val).strip() == 'None' or str(val).strip() == 'NaT':
                                row_list.append(None)
                            else:
                                row_list.append(val)
                        cleaned_data.append(tuple(row_list))

                    # 5. بناء استعلام الإدخال
                    cols_str = ", ".join([f"`{c}`" for c in df.columns])
                    placeholders = ", ".join(["%s"] * len(df.columns))
                    sql = f"INSERT INTO `{table_name}` ({cols_str}) VALUES ({placeholders})"
                    
                    # تنفيذ الإدخال بالجملة (Bulk Insert)
                    if cleaned_data:
                        cursor.executemany(sql, cleaned_data)
                        logging.info(f"✅ Restored {len(cleaned_data)} rows to {table_name}")

                except Exception as table_err:
                    logging.error(f"❌ Error restoring table {table_name}: {table_err}")
                    # في حال حدوث خطأ في جدول واحد، نواصل العمل مع الباقي أو نتراجع حسب الحاجة

            # 6. إعادة تفعيل القيود وحفظ التغييرات
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            conn.commit()
            logging.info("🚀 Database restoration completed successfully.")
            return True, "تمت استعادة قاعدة البيانات بنجاح من ملفات Excel."

        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"❌ Global Restore Failure: {e}")
            return False, f"فشلت عملية الاستعادة: {str(e)}"
        
        finally:
            if conn and conn.is_connected(): 
                conn.close()
            if os.path.exists(temp_dir): 
                shutil.rmtree(temp_dir)

    def export_and_purge_tables(self, output_zip_path, days_to_keep=365):
        tables_to_archive = ['Stock_Movement_Log', 'Reception_Log']
        cutoff_date = date.today() - timedelta(days=days_to_keep)
        temp_dir = 'temp_archive_logs'
        
        try:
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)
            
            has_data = False
            with self.engine.connect() as conn:
                for table in tables_to_archive:
                    col_date = 'Transaction_Date' if table == 'Stock_Movement_Log' else 'Reception_Date'
                    query = text(f"SELECT * FROM {table} WHERE {col_date} < :cutoff")
                    df = pd.read_sql(query, conn, params={"cutoff": cutoff_date})
                    
                    if not df.empty:
                        has_data = True
                        csv_path = os.path.join(temp_dir, f"{table}.csv")
                        df.to_csv(csv_path, index=False, encoding='utf-8')
            
            if has_data:
                with self.get_db_connection() as del_conn:
                    del_cursor = del_conn.cursor()
                    for table in tables_to_archive:
                         col_date = 'Transaction_Date' if table == 'Stock_Movement_Log' else 'Reception_Date'
                         del_query = f"DELETE FROM {table} WHERE {col_date} < %s"
                         del_cursor.execute(del_query, (cutoff_date,))
                    del_conn.commit()

                with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, _, files in os.walk(temp_dir):
                        for file in files:
                            zipf.write(os.path.join(root, file), file)
                return True, f"تمت أرشفة وحذف السجلات القديمة بنجاح في:\n{output_zip_path}"
            else:
                return False, "لا توجد سجلات قديمة تتجاوز المدة المحددة للأرشفة."

        except Exception as e:
            logging.error(f"Archive Log Error: {e}")
            return False, str(e)
        finally:
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
    def restore_table_from_file(self, table_name, file_path):
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)

            df.columns = df.columns.astype(str)
            df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]
            valid_cols = [c for c in df.columns if c.lower() != 'nan' and c.strip() != '']
            df = df[valid_cols]
            df = df.where(pd.notnull(df), None)

            with self.engine.begin() as conn:
                df.to_sql(
                    name=table_name,
                    con=conn,
                    if_exists='append',
                    index=False
                )
                
            logging.info(f"✅ Successfully restored {len(df)} rows to {table_name}")
            return True

        except Exception as e:
            logging.error(f"❌ Restore Failed for {table_name}: {e}")
            return False
    def activate_archive_view(self, input_zip_path):
        temp_dir = 'temp_view_archive'
        archive_prefix = "ARCHIVE_VIEW_"
        
        try:
            if hasattr(self, 'is_archive_mode') and self.is_archive_mode:
                return False, "النظام بالفعل في وضع الأرشيف."

            if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            with zipfile.ZipFile(input_zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            conn = self.get_raw_connection()
            cursor = conn.cursor()
            
            files = [f for f in os.listdir(temp_dir) if f.endswith('.csv')]
            if not files:
                return False, "الملف المحدد لا يحتوي على بيانات CSV صالحة."

            self.table_map = {}

            for csv_file in files:
                original_table = os.path.splitext(csv_file)[0]
                archive_table = f"{archive_prefix}{original_table}"
                
                cursor.execute(f"DROP TABLE IF EXISTS {archive_table}")
                cursor.execute(f"CREATE TABLE {archive_table} LIKE {original_table}")
                
                csv_path = os.path.join(temp_dir, csv_file)
                df = pd.read_csv(csv_path)
                
                df.columns = df.columns.astype(str)
                df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]
                valid_cols = [c for c in df.columns if c.lower() != 'nan' and c.strip() != '']
                df = df[valid_cols]
                df = df.where(pd.notnull(df), None)
                
                if not df.empty:
                    cols = ",".join([f"`{col}`" for col in df.columns])
                    placeholders = ",".join(["%s"] * len(df.columns))
                    sql = f"INSERT INTO {archive_table} ({cols}) VALUES ({placeholders})"
                    data = [tuple(x) for x in df.to_numpy()]
                    cursor.executemany(sql, data)
                
                self.table_map[original_table] = archive_table

            conn.commit()
            conn.close()
            
            self.is_archive_mode = True
            with open(ARCHIVE_VIEW_FLAG_FILE, 'w') as f: f.write('1')
            
            return True, "تم تفعيل وضع الأرشيف (Read-Only). يمكنك الآن تصفح السجلات القديمة."

        except Exception as e:
            self.deactivate_archive_view()
            return False, f"فشل تحميل الأرشيف: {e}"
        finally:
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
    def deactivate_archive_view(self):
        try:
            conn = self.get_raw_connection()
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES LIKE 'ARCHIVE_VIEW_%'")
            tables = cursor.fetchall()
            for (tbl,) in tables:
                cursor.execute(f"DROP TABLE IF EXISTS {tbl}")
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error cleaning archive views: {e}")
        
        self.table_map = {} 
        self.is_archive_mode = False
        if os.path.exists(ARCHIVE_VIEW_FLAG_FILE):
            os.remove(ARCHIVE_VIEW_FLAG_FILE)
        return True, "تم إغلاق الأرشيف والعودة للبيانات الحية."

    def get_table(self, table_name):
        if hasattr(self, 'is_archive_mode') and self.is_archive_mode:
            return self.table_map.get(table_name, table_name)
        return table_name
    
    def export_all_tables_to_csv_zip(self, output_zip_path='backup_csv.zip'): return self.backup_database_csv(output_zip_path)
    def restore_from_archive_zip_destructive(self, input_zip_path, tables_to_restore=None): return self.restore_database_csv(input_zip_path)
    def get_available_archives(self): return []
    def truncate_all_tables(self): return False, "Not Implemented"
    def is_archive_view_mode(self): return os.path.exists(ARCHIVE_VIEW_FLAG_FILE)
    def get_archive_view_tables(self): return getattr(self, 'table_map', {})
    def get_archive_view_status(self): return {"active": self.is_archive_view_mode(), "file": None}
