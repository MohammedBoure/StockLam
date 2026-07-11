import json
import logging
from .base import Database

class CompanySettingsManager:
    def __init__(self, db_instance: Database):
        self.db = db_instance
        self.sync_to_local()

    def sync_to_local(self):
        """
        Synchronise les paramètres de la base de données vers le fichier local pdf_settings.json
        et enregistre l'image du banner localement pour la rétrocompatibilité avec d'autres systèmes.
        """
        import os
        try:
            cwd = os.getcwd()
            json_path = os.path.join(cwd, "pdf_settings.json")
            image_path = os.path.join(cwd, "banner_downloaded.png")
            
            settings = self.get_settings()
            image_bytes = self.get_banner_image()
            
            if image_bytes:
                with open(image_path, "wb") as f:
                    f.write(image_bytes)
                settings["banner_path"] = image_path
                
            if settings:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(settings, f, ensure_ascii=False, indent=4)
                    
            logging.info("🔄 pdf_settings.json synchronisé avec succès depuis la BD.")
        except Exception as e:
            logging.error(f"Erreur lors de la synchronisation locale des paramètres PDF: {e}")

    def get_settings(self):
        """Returns the settings as a dictionary."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT Settings_Data FROM Company_Settings WHERE Settings_ID = 1;")
                result = cursor.fetchone()
                if result and result['Settings_Data']:
                    data = result['Settings_Data']
                    if isinstance(data, str):
                        return json.loads(data)
                    return data
        except Exception as e:
            logging.error(f"Error fetching company settings: {e}")
        return {}

    def update_settings(self, settings_dict, image_bytes=None):
        """Updates the settings and optionally the banner image."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT COUNT(*) as count FROM Company_Settings WHERE Settings_ID = 1;")
                count = cursor.fetchone()['count']
                
                settings_json = json.dumps(settings_dict)
                
                if count == 0:
                    if image_bytes:
                        cursor.execute(
                            "INSERT INTO Company_Settings (Settings_ID, Settings_Data, Banner_Image) VALUES (1, %s, %s);",
                            (settings_json, image_bytes)
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO Company_Settings (Settings_ID, Settings_Data) VALUES (1, %s);",
                            (settings_json,)
                        )
                else:
                    if image_bytes:
                        cursor.execute(
                            "UPDATE Company_Settings SET Settings_Data = %s, Banner_Image = %s WHERE Settings_ID = 1;",
                            (settings_json, image_bytes)
                        )
                    else:
                        cursor.execute(
                            "UPDATE Company_Settings SET Settings_Data = %s WHERE Settings_ID = 1;",
                            (settings_json,)
                        )
                
                self.sync_to_local()
                return True
        except Exception as e:
            logging.error(f"Error updating company settings: {e}")
            return False

    def get_banner_image(self):
        """Returns the banner image as bytes."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT Banner_Image FROM Company_Settings WHERE Settings_ID = 1;")
                result = cursor.fetchone()
                if result and result.get('Banner_Image'):
                    return result['Banner_Image']
        except Exception as e:
            logging.error(f"Error fetching banner image: {e}")
        return None
