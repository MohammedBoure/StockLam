# database/schema_initializer.py

import mysql.connector
import logging
import json
import hashlib

# =============================================================================
# 1. PERMISSIONS DEFINITION (Granular Control)
# =============================================================================
_ALL_PERMISSIONS = [
    "nav_dashboard",
    "nav_data",
    "nav_procurement",
    "nav_inventory",
    "nav_services",
    "nav_history",
    "nav_inventaire",
    "nav_settings",
    "nav_market",

    "tab_dash_overview",
    "tab_dash_reception",
    "tab_dash_consumption",
    "tab_dash_valuation",
    "tab_dash_waste",
    "tab_dash_alerts",

    # --- تبويبات البيانات الأساسية (Master Data) ---
    "tab_data_products",
    "tab_data_families",
    "tab_data_units",
    "tab_data_suppliers",
    "tab_data_manufacturers",
    "tab_data_partners",
    "tab_data_automates",
    "tab_data_locations",
    "tab_data_waste_reasons",

    # --- تبويبات المشتريات (Procurement) ---
    "tab_proc_po",
    "tab_proc_reception",
    "tab_proc_credit",
    "tab_proc_reclamation",

    # --- تبويبات المخزن (Inventory) ---
    "tab_inv_list",
    "tab_inv_dispatch",
    "tab_inv_financials",

    # --- تبويبات السجل والتتبع (History) ---
    "tab_inv_history", # سجل حركات المخزون

    # --- تبويبات المالية (Finance) ---

    # --- تبويبات الإعدادات (Settings) ---
    "tab_config",
    "tab_set_db",
    "tab_set_printer",
    "tab_set_system",
    "tab_system_logs",
    "tab_set_pdf",
    "tab_users",

    # --- الإجراءات (Actions) ---
    "act_add_product",
    "act_edit_product",
    "act_delete_product",
    "act_create_po",
    "act_approve_po",
    "act_receive_po",
    "act_inventory_create",
    "act_inventory_scan",
    "act_inventory_apply",
    "act_inventory_cancel",
    "act_inventory_export"
]
# =============================================================================
# 2. SCHEMA QUERIES (With Inline Alters)
# =============================================================================
SCHEMA_QUERIES = [

    """CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY 'root';""",
    """GRANT ALL PRIVILEGES ON Lab_Inventory_Enterprise_DB.* TO 'root'@'%';""",
    """FLUSH PRIVILEGES;""",

    # --- 1. Users & Auth ---
    """CREATE TABLE IF NOT EXISTS Users (
        User_ID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        Username VARCHAR(50) NOT NULL UNIQUE,
        Password VARCHAR(255) NOT NULL,
        Role ENUM('Admin', 'Manager', 'Technician', 'Viewer') DEFAULT 'Technician',
        Full_Name VARCHAR(100),
        Is_Active BOOLEAN DEFAULT TRUE,
        Permissions JSON DEFAULT NULL,
        Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );""",

    # [Migration]: Ensure Permissions column exists for older DBs
    """ALTER TABLE Users ADD COLUMN Permissions JSON DEFAULT NULL;""",

    # --- 1.1 Settings ---
    """CREATE TABLE IF NOT EXISTS Company_Settings (
        Settings_ID INT PRIMARY KEY DEFAULT 1,
        Settings_Data JSON,
        Banner_Image LONGBLOB
    );""",

    # --- 2. Master Data ---
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

    # --- 3. Procurement Cycle ---
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

    # [Migration]: Purchase_Orders
    """ALTER TABLE Purchase_Orders ADD COLUMN Supplier_Invoice_Ref VARCHAR(150) NULL;""",
    """ALTER TABLE Purchase_Orders ADD COLUMN Deleted_At DATETIME NULL;""",

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
    );""",

    # --- 4. Inventory & Reception ---
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

    # [Migration]: Reception_Log
    """ALTER TABLE Reception_Log ADD COLUMN Variance_Notes TEXT NULL;""",
    """ALTER TABLE Reception_Log ADD COLUMN Total_Discount DECIMAL(15,2) DEFAULT 0.00;""",

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

    """ALTER TABLE Inventory_Batches DROP INDEX uq_inventory_internal_barcode;""",

    """CREATE TABLE IF NOT EXISTS Inventory_Count_Sessions (
        Session_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Session_Name VARCHAR(150) NOT NULL,
        Scope_Type ENUM('ALL', 'LOCATION', 'FAMILY', 'PRODUCT') NOT NULL DEFAULT 'ALL',
        Scope_ID BIGINT UNSIGNED NULL,
        Status ENUM('Draft', 'Counting', 'Review', 'Applied', 'Cancelled') NOT NULL DEFAULT 'Draft',
        Started_At DATETIME DEFAULT CURRENT_TIMESTAMP,
        Completed_At DATETIME NULL,
        Applied_At DATETIME NULL,
        Created_By INT UNSIGNED NULL,
        Applied_By INT UNSIGNED NULL,
        Notes TEXT NULL,
        FOREIGN KEY (Created_By) REFERENCES Users(User_ID) ON DELETE SET NULL ON UPDATE CASCADE,
        FOREIGN KEY (Applied_By) REFERENCES Users(User_ID) ON DELETE SET NULL ON UPDATE CASCADE
    );""",

    """ALTER TABLE Inventory_Count_Sessions ADD COLUMN Applied_At DATETIME NULL;""",
    """ALTER TABLE Inventory_Count_Sessions ADD COLUMN Applied_By INT UNSIGNED NULL;""",

    """CREATE TABLE IF NOT EXISTS Inventory_Count_Lines (
        Line_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Session_ID BIGINT UNSIGNED NOT NULL,
        Batch_ID BIGINT UNSIGNED NULL,
        Product_ID INT UNSIGNED NULL,
        Internal_Barcode VARCHAR(100) NULL,
        Program_Qty_Snapshot DECIMAL(15, 2) NOT NULL DEFAULT 0,
        Counted_Qty DECIMAL(15, 2) NOT NULL DEFAULT 0,
        Difference_Qty DECIMAL(15, 2) NOT NULL DEFAULT 0,
        Line_Status ENUM('OK', 'SHORT', 'EXCESS', 'NOT_COUNTED', 'UNKNOWN') NOT NULL DEFAULT 'NOT_COUNTED',
        Last_Scanned_At DATETIME NULL,
        Comment TEXT NULL,
        FOREIGN KEY (Session_ID) REFERENCES Inventory_Count_Sessions(Session_ID) ON DELETE CASCADE ON UPDATE CASCADE,
        FOREIGN KEY (Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON DELETE SET NULL ON UPDATE CASCADE,
        FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON DELETE SET NULL ON UPDATE CASCADE,
        UNIQUE KEY uq_inventory_count_line_batch (Session_ID, Batch_ID)
    );""",

    """CREATE TABLE IF NOT EXISTS Inventory_Count_Scans (
        Scan_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Session_ID BIGINT UNSIGNED NOT NULL,
        Line_ID BIGINT UNSIGNED NULL,
        Scanned_Barcode VARCHAR(100) NOT NULL,
        Qty DECIMAL(15, 2) NOT NULL DEFAULT 1,
        Scan_Status ENUM('MATCHED', 'UNKNOWN', 'IGNORED') NOT NULL DEFAULT 'MATCHED',
        Scanned_At DATETIME DEFAULT CURRENT_TIMESTAMP,
        Scanned_By INT UNSIGNED NULL,
        FOREIGN KEY (Session_ID) REFERENCES Inventory_Count_Sessions(Session_ID) ON DELETE CASCADE ON UPDATE CASCADE,
        FOREIGN KEY (Line_ID) REFERENCES Inventory_Count_Lines(Line_ID) ON DELETE SET NULL ON UPDATE CASCADE,
        FOREIGN KEY (Scanned_By) REFERENCES Users(User_ID) ON DELETE SET NULL ON UPDATE CASCADE
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

    # --- 5. External & Transfers ---
    """CREATE TABLE IF NOT EXISTS External_Transfer_Log (
        Transfer_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Transaction_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
        Partner_ID INT UNSIGNED NOT NULL,
        Transfer_Type ENUM('Outbound', 'Return', 'Free', 'Paid') DEFAULT 'Outbound',
        Total_Amount DECIMAL(15, 2) DEFAULT 0.00,
        Status ENUM('Draft', 'Completed', 'Cancelled') DEFAULT 'Draft',
        Notes TEXT,
        Ref_Transfer_ID INT UNSIGNED NULL DEFAULT NULL,
        Created_By INT UNSIGNED,
        FOREIGN KEY (Partner_ID) REFERENCES External_Partners(Partner_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Ref_Transfer_ID) REFERENCES External_Transfer_Log(Transfer_ID) ON DELETE SET NULL,
        FOREIGN KEY (Created_By) REFERENCES Users(User_ID)
    );""",
    """ALTER TABLE external_partners MODIFY COLUMN Partner_Type ENUM('Laboratory', 'Doctor', 'Hospital', 'Pharmacy', 'CareRoom', 'Clinic', 'Other');""",

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

    # --- 6. Audit Trail ---
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
            'External_Transfer', 'Transfer_Return', 'Return_To_Supplier', 'Sale'
        ) NOT NULL,
        Reason_ID INT UNSIGNED NULL,
        Qty_Change DECIMAL(10, 2) NOT NULL,
        Unit_Used VARCHAR(50) NOT NULL,
        Notes TEXT NULL,
        Stock_After DECIMAL(15, 2) DEFAULT NULL,
        FOREIGN KEY (User_ID) REFERENCES Users(User_ID),
        FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Container_ID) REFERENCES Active_Containers(Container_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Reason_ID) REFERENCES Waste_Reasons(Reason_ID) ON DELETE SET NULL ON UPDATE CASCADE
    );""",

    """CREATE TABLE IF NOT EXISTS Supplier_Credit_Notes (
        Credit_Note_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Credit_Note_Ref VARCHAR(150) NOT NULL,
        Supplier_ID INT UNSIGNED NOT NULL,
        BR_ID INT UNSIGNED NULL,
        Credit_Date DATE NOT NULL,
        Type ENUM('Return_Goods', 'Price_Correction', 'Billing_Error') DEFAULT 'Return_Goods',
        Status ENUM('Draft', 'Validated', 'Used') DEFAULT 'Draft',
        Total_Amount_HT DECIMAL(15, 2) DEFAULT 0.00,
        Total_TVA DECIMAL(15, 2) DEFAULT 0.00,
        Total_Amount_TTC DECIMAL(15, 2) DEFAULT 0.00,
        Notes TEXT NULL,
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
        Batch_ID BIGINT UNSIGNED NULL,
        Lot_Number VARCHAR(100) NULL,
        Expiry_Date DATE NULL,
        Qty_Returned DECIMAL(10, 2) DEFAULT 0.00,
        Unit_Price DECIMAL(10, 2) NOT NULL,
        Line_Total DECIMAL(15, 2) NOT NULL,
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

    # [Migration]: Supplier_Payments
    """ALTER TABLE Supplier_Payments ADD COLUMN BR_ID INT UNSIGNED NULL;""",
    """ALTER TABLE Supplier_Payments ADD CONSTRAINT fk_payment_br FOREIGN KEY (BR_ID) REFERENCES Reception_Log(BR_ID) ON DELETE SET NULL;""",

    """CREATE TABLE IF NOT EXISTS SystemLogs (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT UNSIGNED,
        log_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        module VARCHAR(50),
        action VARCHAR(100),
        details TEXT,
        ip_address VARCHAR(50),
        FOREIGN KEY (user_id) REFERENCES Users(User_ID) ON DELETE SET NULL
    );"""
]

INDEX_QUERIES = [
    "CREATE INDEX idx_product_barcode ON Products_Master(Barcode);",
    "CREATE INDEX idx_batch_expiry ON Inventory_Batches(Expiry_Date);",
    "CREATE INDEX idx_batch_lot ON Inventory_Batches(Lot_Number);",
    "CREATE INDEX idx_internal_barcode ON Inventory_Batches(Internal_Barcode);",
    "CREATE UNIQUE INDEX idx_barcode_location ON Inventory_Batches(Internal_Barcode, Location_ID);",
    "CREATE INDEX idx_inventory_count_session_status ON Inventory_Count_Sessions(Status);",
    "CREATE INDEX idx_inventory_count_session_started ON Inventory_Count_Sessions(Started_At);",
    "CREATE INDEX idx_inventory_count_line_session_status ON Inventory_Count_Lines(Session_ID, Line_Status);",
    "CREATE INDEX idx_inventory_count_line_barcode ON Inventory_Count_Lines(Internal_Barcode);",
    "CREATE INDEX idx_inventory_count_line_batch ON Inventory_Count_Lines(Batch_ID);",
    "CREATE INDEX idx_inventory_count_scan_session_status ON Inventory_Count_Scans(Session_ID, Scan_Status);",
    "CREATE INDEX idx_inventory_count_scan_barcode ON Inventory_Count_Scans(Scanned_Barcode);",
    "CREATE INDEX idx_reception_invoice_ref ON Reception_Log(Supplier_Invoice_Ref);",
    "CREATE INDEX idx_reception_po_id ON Reception_Log(PO_ID);",
    "CREATE INDEX idx_movement_date ON Stock_Movement_Log(Transaction_Date);",
    "CREATE INDEX idx_movement_type ON Stock_Movement_Log(Movement_Type);",
    "CREATE INDEX idx_reception_details_br ON Reception_Details(BR_ID);",
    "CREATE INDEX idx_reception_details_product ON Reception_Details(Product_ID);",
    "CREATE INDEX idx_partner_name ON External_Partners(Partner_Name);",
    "CREATE INDEX idx_transfer_date ON External_Transfer_Log(Transaction_Date);",
    "CREATE INDEX idx_transfer_partner ON External_Transfer_Log(Partner_ID);"
]

class SchemaInitializerMixin:
    """Mixin that provides _initialize_schema() to the Database class."""

    def _create_default_admin(self, cursor):
        cursor.execute("SELECT User_ID FROM Users WHERE Username = 'admin'")
        admin_exists = cursor.fetchone()

        perms_dict = {perm: True for perm in _ALL_PERMISSIONS}
        perms_json = json.dumps(perms_dict)

        plain_pw = "admin123"

        if not admin_exists:
            logging.info("Creating default Admin account...")
            query = """
                INSERT INTO Users (Username, Password, Role, Full_Name, Permissions)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(query, ('admin', plain_pw, 'Admin', 'Administrateur Système', perms_json))
        else:
            logging.info("Updating Admin permissions to include new modules...")
            query = "UPDATE Users SET Permissions = %s WHERE Username = 'admin'"
            cursor.execute(query, (perms_json,))

    def _initialize_schema(self):
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

                logging.info("Initializing schema tables and migrations...")

                # Execute all schema creation and migration queries in one go
                for query in SCHEMA_QUERIES:
                    try:
                        cursor.execute(query)
                        while cursor.nextset():
                            pass
                    except mysql.connector.Error as err:
                        # Log but ignore errors related to ALTER TABLE if column already exists
                        # Error 1060: Duplicate column name
                        # Error 1061/1826: Duplicate key/foreign-key name.
                        # Error 1091: Key does not exist during DROP INDEX migrations.
                        if err.errno in (1060, 1061, 1091, 1826):
                            pass
                        else:
                            logging.warning(f"Schema warning during query '{query[:30]}...': {err}")

                logging.info("Creating performance indexes...")
                for query in INDEX_QUERIES:
                    try:
                        cursor.execute(query)
                        while cursor.nextset():
                            pass
                    except mysql.connector.Error as err:
                        if err.errno == 1061: # Duplicate key name
                            pass
                        else:
                            logging.warning(f"Index creation warning: {err}")

                # Create Default Admin User
                self._create_default_admin(cursor)

                cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
                logging.info("✅ Schema initialized successfully.")

        except mysql.connector.Error as err:
            logging.error(f"❌ Failed to initialize schema: {err}")
