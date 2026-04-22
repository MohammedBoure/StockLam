# seed_data.py - Version MODERNLAM (Numeric Barcodes & Correct Schema)

import logging
import random
from datetime import datetime, timedelta, date
from decimal import Decimal
from database.base import Database

# إعدادات البيانات
db = Database()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_po_id(order_date, counter):
    """توليد معرف الطلب بالتنسيق التاريخي YYYYMMDDxxx"""
    prefix = order_date.strftime('%Y%m%d')
    return int(f"{prefix}{counter:03d}")

def seed_everything():
    try:
        with db.get_db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

            logging.info("🧹 Nettoyage des tables...")
            tables = [
                "Stock_Movement_Log", "Active_Containers", "Inventory_Batches", 
                "PO_Details", "Reception_Log", "Purchase_Orders", "Product_Documents",
                "Products_Master", "Product_Families", "Manufacturers", "Suppliers", 
                "Automates", "Waste_Reasons", "Packaging_Units", "Locations", "Location_Types"
            ]
            for table in tables:
                cursor.execute(f"TRUNCATE TABLE {table}")

            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

            # --- 1. أنواع المواقع والعائلات ---
            loc_types = [('Bâtiment',), ('Salle',), ('Zone/Rayon',), ('Réfrigérateur',), ('Congélateur',), ('Étagère',)]
            cursor.executemany("INSERT IGNORE INTO Location_Types (Type_Name) VALUES (%s)", loc_types)

            families = ['Biochimie', 'Hématologie', 'Immunologie', 'Coagulation', 'Microbiologie', 'Consommables']
            family_ids = []
            for f in families:
                cursor.execute("INSERT INTO Product_Families (Family_Name) VALUES (%s)", (f,))
                family_ids.append(cursor.lastrowid)

            # --- 2. هيكلة المواقع (30+ موقع) ---
            cursor.execute("INSERT INTO Locations (Location_Name, Type_ID, Temperature_Zone) VALUES ('Laboratoire Central', 1, 'Room Temp')")
            root_id = cursor.lastrowid

            salles = [("Plateau Technique", 'Room Temp'), ("Stock Central", 'Room Temp'), ("Hémostase", 'Room Temp')]
            final_locations = []
            for s_name, s_temp in salles:
                cursor.execute("INSERT INTO Locations (Location_Name, Parent_Location_ID, Type_ID, Temperature_Zone) VALUES (%s, %s, 2, %s)", (s_name, root_id, s_temp))
                salle_id = cursor.lastrowid
                
                units = [("Frigo A1", 4, 'Refrigerated 2-8'), ("Congélateur B1", 5, 'Frozen -20'), ("Rayon Sec C1", 3, 'Room Temp')]
                for u_name, u_type, u_temp in units:
                    cursor.execute("INSERT INTO Locations (Location_Name, Parent_Location_ID, Type_ID, Temperature_Zone) VALUES (%s, %s, %s, %s)", (u_name, salle_id, u_type, u_temp))
                    unit_id = cursor.lastrowid
                    for i in range(1, 6):
                        sub_name = f"{u_name} - E{i}"
                        cursor.execute("INSERT INTO Locations (Location_Name, Parent_Location_ID, Type_ID, Temperature_Zone) VALUES (%s, %s, 6, %s)", (sub_name, unit_id, u_temp))
                        final_locations.append(cursor.lastrowid)

            # --- 3. الشركاء والمنتجات ---
            cursor.execute("INSERT INTO Manufacturers (Manuf_Name, Country_of_Origin) VALUES ('Roche Diagnostics', 'Germany')")
            manuf_id = cursor.lastrowid
            cursor.execute("INSERT INTO Suppliers (Supplier_Name, City) VALUES ('Labo-Dist Algeria', 'Alger')")
            supp_id = cursor.lastrowid

            # إضافة منتجات مع بيانات الاستخدام (Stability)
            products = [
                ('Glucose HK', family_ids[0], 'GLU-100', 'Boîte', 'Test', 100, 30),
                ('HbA1c Gen.3', family_ids[0], 'A1C-50', 'Kit', 'Test', 50, 15),
                ('Cleaner Solution', family_ids[1], 'CLN-99', 'Bidon', 'ml', 1000, 60)
            ]
            product_ids = []
            for name, fam, cat, unit_o, unit_u, ratio, stab in products:
                cursor.execute("""INSERT INTO Products_Master 
                    (Product_Name, Family_ID, Manuf_Cat_No, Ordering_Unit, Usage_Unit, Usage_Qty_Per_Stock_Unit, Open_Vial_Stability_Days, Manuf_ID) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", 
                    (name, fam, cat, unit_o, unit_u, ratio, stab, manuf_id))
                product_ids.append(cursor.lastrowid)

            # --- 4. توليد الطلبيات والدفعات (نظام الباركود الرقمي الجديد) ---
            logging.info("📝 Génération des batches avec Barcodes Numériques...")
            for i in range(1, 21): # توليد 20 طلبية
                order_date = date.today() - timedelta(days=i*2)
                po_id = generate_po_id(order_date, 1)
                
                cursor.execute("INSERT INTO Purchase_Orders (PO_ID, Supplier_ID, Order_Date, Status) VALUES (%s, %s, %s, 'Completed')", 
                               (po_id, supp_id, order_date))

                # إضافة منتجين لكل طلبية
                for p_id in random.sample(product_ids, 2):
                    qty = random.randint(2, 10)
                    price = Decimal(random.randint(5000, 25000))
                    lot = f"L{random.randint(1000, 9999)}"
                    expiry = order_date + timedelta(days=365)
                    
                    # 1. إدخال الدفعة (Batch)
                    cursor.execute("""INSERT INTO Inventory_Batches 
                        (Product_ID, Location_ID, Lot_Number, Expiry_Date, Quantity_Initial, Quantity_Current, 
                         PO_ID, Status, Unit_Price_Received, Created_At) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'Available', %s, %s)""",
                        (p_id, random.choice(final_locations), lot, expiry, qty, qty, po_id, price, order_date))
                    
                    batch_id = cursor.lastrowid
                    
                    # 2. تحديث الباركود الداخلي (رقمي فقط كما طلبتم لمقاس 40x20)
                    # التنسيق: 10 متبوعة بـ 6 أرقام للمعرف (مثال: 10000045)
                    numeric_barcode = f"10{batch_id:06d}"
                    cursor.execute("UPDATE Inventory_Batches SET Internal_Barcode = %s WHERE Batch_ID = %s", 
                                   (numeric_barcode, batch_id))

            conn.commit()
            logging.info(f"✅ Succès! Inventaire peuplé avec des codes-barres numériques (Format: 10XXXXXX).")

    except Exception as e:
        logging.error(f"❌ Erreur: {e}")
        raise

if __name__ == "__main__":
    seed_everything()