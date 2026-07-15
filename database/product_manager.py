# database/product_manager.py

import mysql.connector
import logging
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from .system_logger import log_methods 

@log_methods()
class ProductManager:
    """
    Gestion des opérations sur la table des produits (Products_Master).
    Mise à jour : Protection désactivée pour permettre la correction des unités.
    Integration : Ajout du champ Is_Billable.
    """

    def __init__(self, db_instance):
        self.db = db_instance

    def add_product(self, product_data: Dict) -> bool:
        """
        Ajout d'un nouveau produit.
        """
        logging.info(f"ProduitManager: Tentative d'ajout d'un nouveau produit: {product_data.get('Product_Name')}")

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                # إضافة Is_Billable إلى الاستعلام
                query = """
                    INSERT INTO Products_Master 
                    (Product_Name, Family_ID, Barcode, Manuf_Cat_No, 
                     Ordering_Unit, Stock_Unit, Stock_Qty_Per_Order_Unit, 
                     Usage_Unit, Usage_Qty_Per_Stock_Unit, 
                     Minimum_Stock_Level, Alert_Before_Expiry_Days, 
                     Manuf_ID, Preferred_Automate_ID, Storage_Temp_Req,
                     Open_Vial_Stability_Days, Is_Billable, Show_In_Alerts)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                if 'Product_Name' not in product_data or 'Family_ID' not in product_data or 'Manuf_ID' not in product_data:
                    logging.error("add_product failed: Required fields missing.")
                    return False

                # إضافة القيمة إلى المعاملات (default False)
                params = (
                    product_data['Product_Name'],
                    product_data['Family_ID'],
                    product_data.get('Barcode'),
                    product_data.get('Manuf_Cat_No'),
                    product_data.get('Ordering_Unit', 'Carton'),
                    product_data.get('Stock_Unit', 'Box'),
                    product_data.get('Stock_Qty_Per_Order_Unit', 1),
                    product_data.get('Usage_Unit') or product_data.get('Stock_Unit', 'Box'),
                    Decimal(str(product_data.get('Usage_Qty_Per_Stock_Unit', 1))),
                    product_data.get('Minimum_Stock_Level', 5),
                    product_data.get('Alert_Before_Expiry_Days', 30),
                    product_data['Manuf_ID'],
                    product_data.get('Preferred_Automate_ID'),
                    product_data.get('Storage_Temp_Req'),
                    product_data.get('Open_Vial_Stability_Days', 0),
                    product_data.get('Is_Billable', False),
                    product_data.get('Show_In_Alerts', False)
                )
                cursor.execute(query, params)
                logging.info(f"Produit '{product_data['Product_Name']}' ajouté avec succès.")
                return True
        except mysql.connector.Error as err:
            logging.error(f"Erreur lors de l'ajout du produit: {err}", exc_info=True)
            return False

    def update_product(self, product_id: int, product_data: Dict) -> Tuple[bool, str]:
        """
        تحديث بيانات المنتج.
        تم تعطيل الحماية (Blocking) للسماح بتعديل الوحدات حتى مع وجود مخزون.
        """
        logging.info(f"ProduitManager: Tentative de mise à jour du produit ID: {product_id}")

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # 1. التحقق من وجود مخزون (للعلم فقط الآن)
                check_stock_query = "SELECT COUNT(*) AS StockCount FROM Inventory_Batches WHERE Product_ID = %s AND Quantity_Current > 0"
                cursor.execute(check_stock_query, (product_id,))
                stock_exists = cursor.fetchone()['StockCount'] > 0
                
                # 2. فحص الحقول الحساسة
                critical_fields = ['Stock_Unit', 'Usage_Unit', 'Usage_Qty_Per_Stock_Unit']
                is_critical_change_attempt = False
                
                current_product_details = self.get_product_by_id(product_id)
                
                for field in critical_fields:
                    if field in product_data:
                        old_value = current_product_details.get(field)
                        new_value = product_data.get(field)
                        
                        if field == 'Usage_Qty_Per_Stock_Unit':
                            old_value = Decimal(str(old_value)) if old_value is not None else None
                            new_value = Decimal(str(new_value)) if new_value is not None else None
                        
                        if old_value != new_value:
                            is_critical_change_attempt = True
                            logging.debug(f"Champ modifié: {field} ({old_value} -> {new_value})")
                            break
                
                # 3. [تعديل] السماح بالتغيير مع تسجيل تحذير فقط
                if stock_exists and is_critical_change_attempt:
                    logging.warning(f"⚠️ AVERTISSEMENT: Modification forcée des unités pour le produit {product_id} alors que du stock existe.")

                # 4. التحديث
                fields_to_update = []
                params = []
                
                # إضافة Is_Billable للـ Mapping
                mapping = {
                    'Product_Name': 'Product_Name',
                    'Family_ID': 'Family_ID',
                    'Barcode': 'Barcode',
                    'Manuf_Cat_No': 'Manuf_Cat_No',
                    'Ordering_Unit': 'Ordering_Unit',
                    'Stock_Unit': 'Stock_Unit',
                    'Stock_Qty_Per_Order_Unit': 'Stock_Qty_Per_Order_Unit',
                    'Usage_Unit': 'Usage_Unit',
                    'Usage_Qty_Per_Stock_Unit': 'Usage_Qty_Per_Stock_Unit',
                    'Minimum_Stock_Level': 'Minimum_Stock_Level',
                    'Alert_Before_Expiry_Days': 'Alert_Before_Expiry_Days',
                    'Manuf_ID': 'Manuf_ID',
                    'Preferred_Automate_ID': 'Preferred_Automate_ID',
                    'Storage_Temp_Req': 'Storage_Temp_Req',
                    'Open_Vial_Stability_Days': 'Open_Vial_Stability_Days',
                    'Is_Billable': 'Is_Billable',
                    'Show_In_Alerts': 'Show_In_Alerts'
                }

                for key, col in mapping.items():
                    if key in product_data:
                        fields_to_update.append(f"{col} = %s")
                        if key == 'Usage_Qty_Per_Stock_Unit':
                            params.append(Decimal(str(product_data[key])))
                        else:
                            params.append(product_data[key])
                
                if not fields_to_update:
                    return False, "Aucune donnée à modifier."
                    
                params.append(product_id)
                query = f"UPDATE Products_Master SET {', '.join(fields_to_update)} WHERE Product_ID = %s"
                
                cursor.execute(query, tuple(params))
                conn.commit()
                
                return True, "Mise à jour réussie (Attention: Vérifiez votre stock si vous avez changé les unités)."

        except mysql.connector.Error as err:
            logging.error(f"Erreur update_product {product_id}: {err}", exc_info=True)
            return False, str(err)
        except Exception as e:
            logging.error(f"Erreur inattendue update_product {product_id}: {e}", exc_info=True)
            return False, str(e)
            
    def get_all_products(self) -> List[Dict]:
        """
        يسترجع جميع المنتجات بما في ذلك الحقل الجديد Is_Billable تلقائياً عبر (p.*).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT p.*, m.Manuf_Name, pf.Family_Name, a.Automate_Name
                    FROM Products_Master p
                    LEFT JOIN Manufacturers m ON p.Manuf_ID = m.Manuf_ID
                    LEFT JOIN Product_Families pf ON p.Family_ID = pf.Family_ID
                    LEFT JOIN Automates a ON p.Preferred_Automate_ID = a.Automate_ID
                    WHERE p.Deleted_At IS NULL
                    ORDER BY p.Product_Name
                """
                cursor.execute(query)
                return cursor.fetchall()
        except mysql.connector.Error as err:
            logging.error(f"Erreur get_all_products: {err}", exc_info=True)
            return []

    def get_product_by_id(self, product_id: int) -> Optional[Dict]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT p.*, pf.Family_Name, m.Manuf_Name, a.Automate_Name
                    FROM Products_Master p
                    LEFT JOIN Product_Families pf ON p.Family_ID = pf.Family_ID
                    LEFT JOIN Manufacturers m ON p.Manuf_ID = m.Manuf_ID
                    LEFT JOIN Automates a ON p.Preferred_Automate_ID = a.Automate_ID
                    WHERE p.Product_ID = %s
                """
                cursor.execute(query, (product_id,))
                return cursor.fetchone()
        except mysql.connector.Error as err:
            logging.error(f"Erreur get_product_by_id {product_id}: {err}", exc_info=True)
            return None

    def delete_product(self, product_id: int) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM Inventory_Batches WHERE Product_ID = %s AND Quantity_Current > 0", (product_id,))
                if cursor.fetchone()[0] > 0:
                    logging.warning(f"Refus suppression produit {product_id}: stock existant.")
                    return False 
                
                cursor.execute("UPDATE Products_Master SET Deleted_At = NOW() WHERE Product_ID = %s", (product_id,))
                return True
        except mysql.connector.Error as err:
            logging.error(f"Erreur delete_product {product_id}: {err}", exc_info=True)
            return False

    def search_products(self, search_term: str, limit=None) -> List[Dict]:
        if search_term is None:
            products = self.get_all_products()
            if limit:
                try:
                    return products[:max(1, int(limit))]
                except (TypeError, ValueError):
                    return products
            return products
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                params = []
                query = """
                    SELECT p.*, m.Manuf_Name, pf.Family_Name, a.Automate_Name
                    FROM Products_Master p
                    LEFT JOIN Manufacturers m ON p.Manuf_ID = m.Manuf_ID
                    LEFT JOIN Product_Families pf ON p.Family_ID = pf.Family_ID
                    LEFT JOIN Automates a ON p.Preferred_Automate_ID = a.Automate_ID
                    WHERE p.Deleted_At IS NULL 
                    AND (
                        p.Product_Name LIKE %s OR 
                        p.Barcode LIKE %s OR 
                        p.Manuf_Cat_No LIKE %s OR
                        pf.Family_Name LIKE %s OR
                        a.Automate_Name LIKE %s
                    )
                    ORDER BY p.Product_Name
                """
                term = f"%{search_term}%"
                params.extend([term, term, term, term, term])
                if limit:
                    try:
                        limit_value = max(1, min(int(limit), 500))
                        query += " LIMIT %s"
                        params.append(limit_value)
                    except (TypeError, ValueError):
                        pass
                cursor.execute(query, tuple(params))
                return cursor.fetchall()
        except mysql.connector.Error as err:
            logging.error(f"Erreur search_products: {err}", exc_info=True)
            return []
