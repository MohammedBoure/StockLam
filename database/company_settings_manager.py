import json
import logging
from .base import Database

class CompanySettingsManager:
    def __init__(self, db_instance: Database):
        self.db = db_instance

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

    def update_settings(self, settings_dict, image_bytes=None, clear_banner=False):
        """Update the shared PDF template without touching local user settings."""
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
                    if clear_banner:
                        cursor.execute(
                            "UPDATE Company_Settings SET Settings_Data = %s, Banner_Image = NULL WHERE Settings_ID = 1;",
                            (settings_json,)
                        )
                    elif image_bytes:
                        cursor.execute(
                            "UPDATE Company_Settings SET Settings_Data = %s, Banner_Image = %s WHERE Settings_ID = 1;",
                            (settings_json, image_bytes)
                        )
                    else:
                        cursor.execute(
                            "UPDATE Company_Settings SET Settings_Data = %s WHERE Settings_ID = 1;",
                            (settings_json,)
                        )
                
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

    def get_stamps(self, include_image=True):
        """Return the independent PNG stamp library and each stamp's layout."""
        columns = "Stamp_ID, Stamp_Name, Position_X_CM, Position_Y_CM, Width_CM, Height_CM, Is_Active"
        if include_image:
            columns += ", Image_Data"

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    f"SELECT {columns} FROM Company_Stamps ORDER BY Stamp_Name, Stamp_ID"
                )
                return cursor.fetchall() or []
        except Exception as e:
            logging.error(f"Error fetching company stamps: {e}")
            return []

    def get_active_stamp(self):
        """Return the active stamp, or None when stamping is disabled."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT Stamp_ID, Stamp_Name, Image_Data,
                           Position_X_CM, Position_Y_CM, Width_CM, Height_CM,
                           Is_Active
                    FROM Company_Stamps
                    WHERE Is_Active = TRUE
                    ORDER BY Stamp_ID
                    LIMIT 1
                    """
                )
                return cursor.fetchone()
        except Exception as e:
            logging.error(f"Error fetching active company stamp: {e}")
            return None

    def add_stamp(
        self,
        stamp_name,
        image_bytes,
        position_x_cm=13.0,
        position_y_cm=22.0,
        width_cm=4.0,
        height_cm=4.0,
        is_active=False,
    ):
        """Add one shared PNG stamp without activating it implicitly."""
        if not stamp_name or not image_bytes:
            return None

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                should_activate = bool(is_active)
                if should_activate:
                    cursor.execute("UPDATE Company_Stamps SET Is_Active = FALSE")

                cursor.execute(
                    """
                    INSERT INTO Company_Stamps
                        (Stamp_Name, Image_Data, Position_X_CM, Position_Y_CM,
                         Width_CM, Height_CM, Is_Active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(stamp_name).strip()[:150],
                        image_bytes,
                        float(position_x_cm),
                        float(position_y_cm),
                        float(width_cm),
                        float(height_cm),
                        should_activate,
                    ),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logging.error(f"Error adding company stamp: {e}")
            return None

    def update_stamp(
        self,
        stamp_id,
        stamp_name,
        position_x_cm,
        position_y_cm,
        width_cm,
        height_cm,
    ):
        """Persist the selected stamp's name and independent layout."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE Company_Stamps
                    SET Stamp_Name = %s,
                        Position_X_CM = %s,
                        Position_Y_CM = %s,
                        Width_CM = %s,
                        Height_CM = %s
                    WHERE Stamp_ID = %s
                    """,
                    (
                        str(stamp_name).strip()[:150],
                        float(position_x_cm),
                        float(position_y_cm),
                        float(width_cm),
                        float(height_cm),
                        int(stamp_id),
                    ),
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Error updating company stamp: {e}")
            return False

    def set_active_stamp(self, stamp_id):
        """Make one stamp active for PDFs, or disable stamping with None."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE Company_Stamps SET Is_Active = FALSE")
                if stamp_id is not None:
                    cursor.execute(
                        "UPDATE Company_Stamps SET Is_Active = TRUE WHERE Stamp_ID = %s",
                        (int(stamp_id),),
                    )
                    if cursor.rowcount == 0:
                        conn.rollback()
                        return False
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error activating company stamp: {e}")
            return False

    def delete_stamp(self, stamp_id):
        """Delete a shared stamp without activating another one implicitly."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT Is_Active FROM Company_Stamps WHERE Stamp_ID = %s",
                    (int(stamp_id),),
                )
                stamp = cursor.fetchone()
                if not stamp:
                    return False

                cursor.execute("DELETE FROM Company_Stamps WHERE Stamp_ID = %s", (int(stamp_id),))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error deleting company stamp: {e}")
            return False
