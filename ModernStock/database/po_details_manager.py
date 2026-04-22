# database/managers/po_details_manager.py

import mysql.connector
import logging
from typing import List, Dict, Optional
from decimal import Decimal
from .system_logger import log_methods 

@log_methods()
class PODetailsManager:
    """
    Gestion des détails des commandes d'achat (PO_Details).
    Calcule automatiquement les totaux de ligne (HT, TTC) et met à jour l'en-tête de la commande.
    """

    def __init__(self, db_instance, po_manager_instance):
        self.db = db_instance
        self.po_manager = po_manager_instance # Instance de PurchaseOrderManager pour mettre à jour les totaux

    def _calculate_line_totals(self, qty, price, discount_pct, tax_pct):
        """
        Calcule les totaux de ligne avec précision Decimal pour éviter les erreurs d'arrondi.
        HT = Qté * Prix * (1 - Remise%)
        TTC = HT * (1 + TVA%)
        """
        try:
            q = Decimal(str(qty))
            p = Decimal(str(price))
            d = Decimal(str(discount_pct)) if discount_pct else Decimal('0')
            t = Decimal(str(tax_pct)) if tax_pct else Decimal('0')
            
            # Calcul HT avec remise
            line_ht = q * p * (1 - (d / Decimal('100')))
            
            # Calcul TTC avec TVA
            line_ttc = line_ht * (1 + (t / Decimal('100')))
            
            return line_ht, line_ttc
        except Exception as e:
            logging.error(f"Erreur calcul ligne : {e}")
            return Decimal('0.00'), Decimal('0.00')

    def add_po_detail_line(self, po_id: int, product_id: int, qty_ordered: int, unit_price_ht: Decimal, 
                           discount_percent: Decimal = Decimal('0.00'), tax_rate_percent: Decimal = Decimal('0.00'),
                           item_note: str = "") -> Optional[int]:
        """
        Ajoute une ligne de produit à la commande et met à jour les totaux globaux.
        """
        try:
            # 1. Calculer les totaux de la ligne AVANT l'insertion
            line_ht, line_ttc = self._calculate_line_totals(qty_ordered, unit_price_ht, discount_percent, tax_rate_percent)

            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                insert_query = """
                    INSERT INTO PO_Details 
                    (PO_ID, Product_ID, Qty_Ordered, Unit_Price_HT, Discount_Percent, 
                     Tax_Rate_Percent, Item_Note, Line_Total_HT, Line_Total_TTC) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                params = (
                    po_id, product_id, qty_ordered, unit_price_ht, 
                    discount_percent, tax_rate_percent, item_note, 
                    line_ht, line_ttc
                )
                cursor.execute(insert_query, params)
                detail_id = cursor.lastrowid
                
                logging.info(f"Ligne détail {detail_id} ajoutée au PO {po_id}.")
                
                # 2. Mettre à jour les totaux de l'en-tête de commande
                self.po_manager._recalculate_po_totals(conn, po_id)
                
                return detail_id
        except mysql.connector.Error as err:
            logging.error(f"Erreur DB lors de l'ajout détail PO {po_id}: {err}")
            return None

    def update_po_detail_line(self, detail_id: int, **kwargs) -> bool:
        """
        Met à jour une ligne existante (Qté, Prix, Remise...) et recalcule les totaux.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # 1. Récupérer les valeurs actuelles pour fusionner
                cursor.execute("SELECT * FROM PO_Details WHERE ID = %s", (detail_id,))
                current = cursor.fetchone()
                if not current:
                    logging.warning(f"Ligne détail {detail_id} introuvable.")
                    return False
                
                # 2. Déterminer les nouvelles valeurs (New vs Old)
                qty = kwargs.get('Qty_Ordered', current['Qty_Ordered'])
                price = kwargs.get('Unit_Price_HT', current['Unit_Price_HT'])
                disc = kwargs.get('Discount_Percent', current['Discount_Percent'])
                tax = kwargs.get('Tax_Rate_Percent', current['Tax_Rate_Percent'])
                note = kwargs.get('Item_Note', current['Item_Note'])
                
                # 3. Recalculer les totaux financiers
                line_ht, line_ttc = self._calculate_line_totals(qty, price, disc, tax)
                
                # 4. Construire la requête de mise à jour
                update_query = """
                    UPDATE PO_Details 
                    SET Qty_Ordered=%s, Unit_Price_HT=%s, Discount_Percent=%s, 
                        Tax_Rate_Percent=%s, Item_Note=%s, 
                        Line_Total_HT=%s, Line_Total_TTC=%s
                    WHERE ID=%s
                """
                params = (qty, price, disc, tax, note, line_ht, line_ttc, detail_id)
                
                cursor.execute(update_query, params)
                
                if cursor.rowcount > 0:
                    logging.info(f"Ligne détail {detail_id} mise à jour.")
                    # 5. Mettre à jour l'en-tête
                    self.po_manager._recalculate_po_totals(conn, current['PO_ID'])
                    return True
                
                return False
        except mysql.connector.Error as e:
            logging.error(f"Erreur update détail {detail_id}: {e}")
            return False

    def delete_po_detail_line(self, detail_id: int) -> bool:
        """
        Supprime une ligne et met à jour le total de la commande.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # 1. Récupérer l'ID de la commande avant suppression
                cursor.execute("SELECT PO_ID FROM PO_Details WHERE ID = %s", (detail_id,))
                res = cursor.fetchone()
                if not res: return False
                po_id = res[0]

                # 2. Supprimer la ligne
                cursor.execute("DELETE FROM PO_Details WHERE ID = %s", (detail_id,))
                
                if cursor.rowcount > 0:
                    logging.info(f"Ligne {detail_id} supprimée du PO {po_id}.")
                    # 3. Mettre à jour l'en-tête
                    self.po_manager._recalculate_po_totals(conn, po_id)
                    return True
                
                return False
        except mysql.connector.Error as e:
            logging.error(f"Erreur suppression détail {detail_id}: {e}")
            return False

    def get_details_by_po_id(self, po_id: int) -> List[Dict]:
        """
        Récupère toutes les lignes d'une commande avec les noms des produits.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        pd.*, 
                        pm.Product_Name,
                        pm.Ordering_Unit,
                        pm.Manuf_Cat_No
                    FROM PO_Details pd
                    JOIN Products_Master pm ON pd.Product_ID = pm.Product_ID
                    WHERE pd.PO_ID = %s
                    ORDER BY pd.ID ASC
                """
                cursor.execute(query, (po_id,))
                return cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error(f"Erreur récupération détails PO {po_id}: {e}")
            return []