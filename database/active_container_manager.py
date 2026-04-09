# database/managers/active_container_manager.py

import mysql.connector
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from decimal import Decimal
from .system_logger import log_methods 

@log_methods()
class ActiveContainerManager:
    """
    Gère les opérations pour la table Active_Containers.
    Gère l'expiration secondaire, le suivi précis de la consommation (Test/QC), et l'enregistrement des déchets.
    Assure que tous les changements d'état sont journalisés dans Stock_Movement_Log.
    """

    def __init__(self, db_instance):
        self.db = db_instance

    def get_active_containers_with_details(self) -> List[Dict]:
        """
        Récupère tous les conteneurs actifs avec les détails du Produit, de l'Emplacement et du Lot pour l'IU.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT
                        ac.*,
                        p.Product_Name,
                        p.Usage_Unit,
                        p.Barcode,
                        b.Internal_Barcode,
                        l.Location_Name,
                        b.Lot_Number
                    FROM Active_Containers ac
                    JOIN Products_Master p ON ac.Product_ID = p.Product_ID
                    LEFT JOIN Locations l ON ac.Current_Location_ID = l.Location_ID
                    LEFT JOIN Inventory_Batches b ON ac.Parent_Batch_ID = b.Batch_ID
                    WHERE ac.Status = 'In_Use'
                    ORDER BY ac.Date_Opened DESC
                """
                cursor.execute(query)
                containers = cursor.fetchall()
                logging.info(f"Récupéré {len(containers)} conteneurs actifs.")
                return containers
        except Exception as e:
            logging.error(f"Erreur lors de la récupération des conteneurs actifs : {e}")
            return []

    def calculate_open_expiration_date(self, parent_batch_id: int, date_opened: datetime) -> Optional[date]:
        """
        Calcule la date d'expiration secondaire basée sur l'expiration officielle et les jours de stabilité.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT b.Expiry_Date AS official_expiry, p.Open_Vial_Stability_Days
                    FROM Inventory_Batches b
                    JOIN Products_Master p ON b.Product_ID = p.Product_ID
                    WHERE b.Batch_ID = %s
                """
                cursor.execute(query, (parent_batch_id,))
                result = cursor.fetchone()
               
                if not result:
                    logging.error(f"Impossible de calculer l'expiration : ID du Lot Parent {parent_batch_id} non trouvé.")
                    return None
                   
                official = result['official_expiry']
                stability = result['Open_Vial_Stability_Days']
               
                # Si les jours de stabilité sont définis, calculer la nouvelle date
                if stability and stability > 0:
                    calculated = date_opened.date() + timedelta(days=stability)
                    # Retourner la plus proche des deux dates
                    return min(official, calculated) if official else calculated
               
                return official

        except Exception as e:
            logging.error(f"Erreur lors du calcul de l'expiration pour le lot {parent_batch_id} : {e}")
            return None

    def open_new_container(self, parent_batch_id: int, initial_usage_qty: Decimal, date_opened: datetime) -> Optional[int]:
        """
        Ouvre un nouveau conteneur. NOTE : Cette logique est généralement gérée dans open_pack_transaction de InventoryBatchManager
        pour assurer que la déduction de stock se fasse de manière atomique.
        Cette fonction est conservée pour une utilisation autonome si nécessaire.
        """
        open_expiry_date = self.calculate_open_expiration_date(parent_batch_id, date_opened)
        if open_expiry_date is None:
            return None

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)

                # Obtenir l'ID du Produit
                cursor.execute("SELECT Product_ID FROM Inventory_Batches WHERE Batch_ID = %s", (parent_batch_id,))
                res = cursor.fetchone()
                if not res: return None
                product_id = res['Product_ID']
               
                insert_query = """
                    INSERT INTO Active_Containers
                    (Parent_Batch_ID, Product_ID, Date_Opened, Open_Expiration_Date,
                     Initial_Usage_Qty, Remaining_Usage_Qty, Status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'In_Use')
                """
                params = (parent_batch_id, product_id, date_opened, open_expiry_date,
                          initial_usage_qty, initial_usage_qty)
                cursor.execute(insert_query, params)
                container_id = cursor.lastrowid
               
                logging.info(f"Conteneur {container_id} ouvert via ActiveManager.")
                return container_id
               
        except mysql.connector.Error as err:
            logging.error(f"Erreur base de données lors de l'ouverture du conteneur : {err}")
            return None

    def consume_usage_quantity(self, container_id: int, quantity_consumed: Decimal) -> bool:
        """
        Enregistre la consommation (Patient_Test/QC), déduit la quantité, et journalise le mouvement de manière transactionnelle.
        """
        conn = None
        try:
            # Utiliser une connexion brute pour un contrôle manuel des transactions
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()
           
            # 1. Verrouiller et Récupérer les Infos Actuelles
            cursor.execute("""
                SELECT
                    ac.Product_ID, ac.Parent_Batch_ID, ac.Remaining_Usage_Qty,
                    ac.Open_Expiration_Date, p.Usage_Unit
                FROM Active_Containers ac
                JOIN Products_Master p ON ac.Product_ID = p.Product_ID
                WHERE ac.Container_ID = %s AND ac.Status = 'In_Use'
                FOR UPDATE
            """, (container_id,))
           
            current_info = cursor.fetchone()
           
            if not current_info:
                logging.warning(f"Échec Consommation : Conteneur {container_id} non trouvé ou inactif.")
                conn.rollback()
                return False
           
            product_id, batch_id, remaining_qty, open_expiry, unit_used = current_info
           
            # Validation : Vérifier l'Expiration
            if open_expiry and datetime.now().date() > open_expiry:
                logging.warning(f"Échec Consommation : Conteneur {container_id} expiré le {open_expiry}.")
                conn.rollback()
                return False
               
            # Validation : Vérifier la Quantité
            if float(remaining_qty) < float(quantity_consumed):
                logging.warning(f"Échec Consommation : Stock insuffisant dans le Conteneur {container_id}. A {remaining_qty}, Tentative {quantity_consumed}.")
                conn.rollback()
                return False
           
            # 2. Mettre à jour Active_Containers
            new_remaining = float(remaining_qty) - float(quantity_consumed)
            new_status = 'Empty' if new_remaining <= 0 else 'In_Use'
           
            cursor.execute("""
                UPDATE Active_Containers
                SET Remaining_Usage_Qty = %s, Status = %s
                WHERE Container_ID = %s
            """, (new_remaining, new_status, container_id))

            # 3. Journaliser le Mouvement (Quantité négative pour consommation)
            insert_log = """
                INSERT INTO Stock_Movement_Log
                (Product_ID, Batch_ID, Container_ID, Movement_Type, Qty_Change, Unit_Used, Transaction_Date)
                VALUES (%s, %s, %s, 'Patient_Test', %s, %s, NOW())
            """
            cursor.execute(insert_log, (product_id, batch_id, container_id, -float(quantity_consumed), unit_used))
           
            conn.commit()
            logging.info(f"✅ Consommé {quantity_consumed} {unit_used} du Conteneur {container_id}. Restant : {new_remaining}")
            return True
               
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"❌ Erreur base de données lors de la consommation : {e}")
            return False
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()

    def discard_container(self, container_id: int, reason_id: Optional[int] = None, notes: str = "") -> bool:
        """
        Jette la quantité restante dans un conteneur (Déchet) et la journalise de manière transactionnelle.
        """
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()
           
            # 1. Verrouiller et Récupérer les Infos
            cursor.execute("""
                SELECT
                    ac.Product_ID, ac.Parent_Batch_ID, ac.Remaining_Usage_Qty,
                    p.Usage_Unit
                FROM Active_Containers ac
                JOIN Products_Master p ON ac.Product_ID = p.Product_ID
                WHERE ac.Container_ID = %s AND ac.Status = 'In_Use'
                FOR UPDATE
            """, (container_id,))
           
            current_info = cursor.fetchone()
            if not current_info:
                logging.warning(f"Échec Jet : Conteneur {container_id} ne peut pas être jeté (Non trouvé/inactif).")
                conn.rollback()
                return False
               
            product_id, batch_id, remaining_qty, unit_used = current_info
            wasted_qty = float(remaining_qty)
           
            # 2. Mettre à jour le Statut à Discarded
            cursor.execute("""
                UPDATE Active_Containers
                SET Remaining_Usage_Qty = 0, Status = 'Discarded'
                WHERE Container_ID = %s
            """, (container_id,))
           
            # 3. Journaliser le Mouvement Déchet
            insert_log = """
                INSERT INTO Stock_Movement_Log
                (Product_ID, Batch_ID, Container_ID, Movement_Type, Reason_ID, Qty_Change, Unit_Used, Notes, Transaction_Date)
                VALUES (%s, %s, %s, 'Waste', %s, %s, %s, %s, NOW())
            """
            cursor.execute(insert_log, (
                product_id, batch_id, container_id,
                reason_id, -wasted_qty, unit_used, notes
            ))
           
            conn.commit()
            logging.info(f"✅ Conteneur {container_id} jeté. Déchet : {wasted_qty} {unit_used}.")
            return True
           
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"❌ Erreur lors du jet du conteneur {container_id} : {e}")
            return False
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()

    def get_active_containers_by_expiry_and_location(self, location_id: Optional[int] = None) -> List[Dict]:
        """
        Récupère les conteneurs actifs triés par FEFO (First Expired First Out).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
               
                query = """
                    SELECT
                        ac.*,
                        p.Product_Name,
                        p.Usage_Unit,
                        l.Location_Name
                    FROM Active_Containers ac
                    JOIN Products_Master p ON ac.Product_ID = p.Product_ID
                    LEFT JOIN Locations l ON ac.Current_Location_ID = l.Location_ID
                    WHERE ac.Status = 'In_Use'
                """
                params = []
                if location_id is not None:
                    query += " AND ac.Current_Location_ID = %s"
                    params.append(location_id)
                   
                query += " ORDER BY ac.Open_Expiration_Date ASC, ac.Date_Opened ASC"
               
                cursor.execute(query, tuple(params))
                containers = cursor.fetchall()
                return containers
        except Exception as e:
            logging.error(f"Erreur lors de la récupération des conteneurs actifs (FEFO) : {e}")
            return []

    # --- Fonctions Wrapper pour les Appels IU ---
   
    def record_consumption_transaction(self, data: Dict) -> bool:
        """Appelée depuis ConsumptionDialog IU."""
        return self.consume_usage_quantity(
            container_id=data['Container_ID'],
            quantity_consumed=data['Qty_Used']
        )
       
    def waste_container_transaction(self, data: Dict) -> bool:
        """Appelée depuis WasteDialog IU."""
        return self.discard_container(
            container_id=data['Source_ID'],
            reason_id=data.get('Reason_ID'),
            notes=data.get('Notes', '')
        )