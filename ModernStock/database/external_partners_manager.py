# database/managers/external_partners_manager.py

import mysql.connector
import logging
from typing import List, Dict, Optional
from .system_logger import log_methods 

@log_methods()
class ExternalPartnersManager:
    """
    Gestion des opérations sur la table External_Partners.
    Supporte toutes les informations : Identité, Contact, Adresse, Fiscalité, Banque.
    """

    def __init__(self, db_instance):
        self.db = db_instance

    def add_partner(self, partner_data: Dict) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # حذف Created_At من قائمة الأعمدة و NOW() من القيم لترك القاعدة تضع التاريخ الافتراضي
                query = """
                    INSERT INTO External_Partners 
                    (
                        Partner_Name, Partner_Type, Agrement_Number,
                        Tax_ID_Number, Commercial_Reg_No,
                        Contact_Person, Phone, Email, Website,
                        Address_Line1, Address_Line2, City, Postal_Code,
                        Bank_Name, Bank_Account_IBAN
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                params = (
                    partner_data['Partner_Name'],
                    partner_data.get('Partner_Type', 'Laboratory'),
                    partner_data.get('Agrement_Number'),
                    partner_data.get('Tax_ID_Number'),
                    partner_data.get('Commercial_Reg_No'),
                    partner_data.get('Contact_Person'),
                    partner_data.get('Phone'),
                    partner_data.get('Email'),
                    partner_data.get('Website'),
                    partner_data.get('Address_Line1'),
                    partner_data.get('Address_Line2'),
                    partner_data.get('City'),
                    partner_data.get('Postal_Code'),
                    partner_data.get('Bank_Name'),
                    partner_data.get('Bank_Account_IBAN')
                )
                
                cursor.execute(query, params)
                conn.commit()
                logging.info(f"Partenaire ajouté succès: {partner_data['Partner_Name']}")
                return True
                
        except mysql.connector.Error as e:
            logging.error(f"Erreur SQL add_partner: {e}", exc_info=True)
            return False

    def update_partner(self, partner_id: int, partner_data: Dict) -> bool:
        """
        Mettre à jour les données d'un partenaire existant.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                    UPDATE External_Partners 
                    SET 
                        Partner_Name = %s,
                        Partner_Type = %s,
                        Agrement_Number = %s,
                        
                        Tax_ID_Number = %s,
                        Commercial_Reg_No = %s,
                        
                        Contact_Person = %s,
                        Phone = %s,
                        Email = %s,
                        Website = %s,
                        
                        Address_Line1 = %s,
                        Address_Line2 = %s,
                        City = %s,
                        Postal_Code = %s,
                        
                        Bank_Name = %s,
                        Bank_Account_IBAN = %s
                    WHERE Partner_ID = %s
                """
                
                params = (
                    partner_data['Partner_Name'],
                    partner_data.get('Partner_Type', 'Laboratory'),
                    partner_data.get('Agrement_Number'),
                    
                    partner_data.get('Tax_ID_Number'),
                    partner_data.get('Commercial_Reg_No'),
                    
                    partner_data.get('Contact_Person'),
                    partner_data.get('Phone'),
                    partner_data.get('Email'),
                    partner_data.get('Website'),
                    
                    partner_data.get('Address_Line1'),
                    partner_data.get('Address_Line2'),
                    partner_data.get('City'),
                    partner_data.get('Postal_Code'),
                    
                    partner_data.get('Bank_Name'),
                    partner_data.get('Bank_Account_IBAN'),
                    
                    partner_id
                )
                
                cursor.execute(query, params)
                conn.commit()
                logging.info(f"Partenaire {partner_id} mis à jour avec succès.")
                return True
                
        except mysql.connector.Error as e:
            logging.error(f"Erreur SQL update_partner {partner_id}: {e}", exc_info=True)
            return False

    def delete_partner(self, partner_id: int) -> bool:
        """
        Suppression logique (Soft Delete).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                # التحقق أولاً إذا كان مرتبطًا بفواتير (اختياري ولكنه مفضل)
                # check_query = "SELECT COUNT(*) FROM Invoices WHERE Partner_ID = %s"
                # cursor.execute(check_query, (partner_id,))
                # if cursor.fetchone()[0] > 0:
                #     return False

                query = "UPDATE External_Partners SET Deleted_At = NOW() WHERE Partner_ID = %s"
                cursor.execute(query, (partner_id,))
                conn.commit()
                logging.info(f"Partenaire {partner_id} supprimé (Soft Delete).")
                return True
        except mysql.connector.Error as e:
            logging.error(f"Erreur delete_partner {partner_id}: {e}", exc_info=True)
            return False

    def get_all_partners(self) -> List[Dict]:
        """
        Récupère tous les champs pour l'affichage complet dans le Dialog.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                # استخدام * لضمان جلب كل الأعمدة الجديدة والقديمة
                query = """
                    SELECT * FROM External_Partners 
                    WHERE Deleted_At IS NULL 
                    ORDER BY Partner_Name ASC
                """
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur get_all_partners: {e}", exc_info=True)
            return []

    def get_partner_by_id(self, partner_id: int) -> Optional[Dict]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM External_Partners WHERE Partner_ID = %s"
                cursor.execute(query, (partner_id,))
                return cursor.fetchone()
        except Exception as e:
            logging.error(f"Erreur get_partner_by_id {partner_id}: {e}", exc_info=True)
            return None