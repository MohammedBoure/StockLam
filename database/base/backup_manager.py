import os
import shutil
import zipfile
import logging
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from sqlalchemy import text, inspect as sa_inspect
import sqlalchemy

from .config import TABLE_IMPORT_ORDER


class BackupManagerMixin:
    """Mixin that provides CSV/Excel backup and restore methods to the Database class."""

    @staticmethod
    def _zip_info_is_encrypted(zip_info):
        return bool(zip_info.flag_bits & 0x1) or zip_info.compress_type == 99

    def _get_backup_zip_infos(self, input_zip_path):
        with zipfile.ZipFile(input_zip_path, 'r') as zip_ref:
            return zip_ref.infolist()

    def backup_zip_requires_password(self, input_zip_path):
        try:
            return any(self._zip_info_is_encrypted(info) for info in self._get_backup_zip_infos(input_zip_path))
        except Exception as e:
            logging.warning(f"Could not inspect backup zip encryption: {e}")
            return False

    def detect_backup_zip_format(self, input_zip_path):
        try:
            names = [info.filename.lower() for info in self._get_backup_zip_infos(input_zip_path)]
        except Exception as e:
            logging.warning(f"Could not inspect backup zip content: {e}")
            return "unknown"

        if any(name.endswith('.xlsx') for name in names):
            return "excel"
        if any(name.endswith('.csv') for name in names):
            return "csv"
        return "unknown"

    def _extract_backup_zip(self, input_zip_path, temp_dir, password=None):
        password_bytes = password.encode('utf-8') if password else None
        try:
            infos = self._get_backup_zip_infos(input_zip_path)
            encrypted = any(self._zip_info_is_encrypted(info) for info in infos)
            uses_aes = any(info.compress_type == 99 for info in infos)

            if encrypted and not password_bytes:
                return False, "BACKUP_PASSWORD_REQUIRED: this backup is encrypted."

            if uses_aes:
                try:
                    import pyzipper
                except ImportError:
                    return False, "pyzipper is required to restore encrypted AES backups. Install it with pip install pyzipper."

                with pyzipper.AESZipFile(input_zip_path, 'r') as zip_ref:
                    if password_bytes:
                        zip_ref.setpassword(password_bytes)
                    zip_ref.extractall(temp_dir, pwd=password_bytes)
            else:
                with zipfile.ZipFile(input_zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir, pwd=password_bytes)

            return True, ""
        except RuntimeError as e:
            msg = str(e)
            if "password" in msg.lower() or "bad password" in msg.lower():
                return False, "BACKUP_BAD_PASSWORD: invalid or missing backup password."
            return False, msg
        except Exception as e:
            return False, str(e)

    def restore_database_backup(self, input_zip_path, password=None):
        backup_format = self.detect_backup_zip_format(input_zip_path)
        if backup_format == "csv":
            return self.restore_database_csv(input_zip_path, password=password)
        if backup_format == "excel":
            return self.restore_database_excel(input_zip_path, password=password)
        return False, "Unsupported backup format. The ZIP must contain CSV or Excel files."

    @staticmethod
    def _quote_identifier(identifier):
        return f"`{str(identifier).replace('`', '``')}`"

    @staticmethod
    def _normalize_mysql_temporal_value(value, column_type):
        if value == '<NULL>' or pd.isna(value) or value == 'NaT' or value == '':
            return None

        mysql_type = str(column_type or '').lower().split('(', 1)[0].strip()
        if mysql_type not in {'date', 'datetime', 'timestamp'}:
            return value

        if isinstance(value, (pd.Timestamp, datetime)):
            parsed = value
        elif isinstance(value, date):
            parsed = datetime.combine(value, datetime.min.time())
        else:
            parsed = pd.to_datetime(str(value).strip(), errors='coerce')

        if pd.isna(parsed):
            return value

        if mysql_type == 'date':
            return parsed.strftime('%Y-%m-%d')
        return parsed.strftime('%Y-%m-%d %H:%M:%S')

    def _drop_inventory_global_barcode_unique(self, conn):
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SHOW INDEX FROM `Inventory_Batches` WHERE Key_name = %s",
                ("uq_inventory_internal_barcode",)
            )
            if cursor.fetchone():
                cursor.execute("ALTER TABLE `Inventory_Batches` DROP INDEX `uq_inventory_internal_barcode`")
                conn.commit()
                logging.info("Dropped obsolete unique index Inventory_Batches.uq_inventory_internal_barcode.")
        except Exception as e:
            logging.warning(f"Could not drop obsolete barcode unique index: {e}")
        finally:
            if cursor:
                cursor.close()

    # -------------------------------------------------------------------------
    # CSV BACKUP
    # -------------------------------------------------------------------------

    def backup_database_csv(self, output_zip_path):
        """تصدير كامل لقاعدة البيانات مع معالجة دقيقة للمسارات والاتصالات."""
        temp_dir = os.path.abspath('temp_backup_csv')
        conn_sqlalchemy = None

        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)

            try:
                conn_sqlalchemy = self.engine.connect()
            except Exception as e:
                logging.error(f"❌ SQLAlchemy Connection Failed: {e}")
                return False, f"فشل الاتصال بمحرك SQLAlchemy: {e}"

            inspector = sqlalchemy.inspect(self.engine)
            all_db_tables = inspector.get_table_names()

            if not all_db_tables:
                return False, "قاعدة البيانات فارغة، لا توجد جداول لتصديرها."

            tables_to_export = [tbl for tbl in TABLE_IMPORT_ORDER if tbl in all_db_tables]
            for tbl in all_db_tables:
                if tbl not in tables_to_export:
                    tables_to_export.append(tbl)

            exported_count = 0

            for table_name in tables_to_export:
                csv_path = os.path.join(temp_dir, f"{table_name}.csv")
                try:
                    df = pd.read_sql_query(
                        text(f"SELECT * FROM `{table_name}`"), conn_sqlalchemy
                    )

                    if df.empty:
                        df.to_csv(csv_path, index=False, encoding='utf-8', na_rep='<NULL>')
                        logging.info(f"⚪ Table {table_name} is empty, exported header only.")
                    else:
                        for col in df.select_dtypes(
                            include=['datetime64[ns]', 'datetime']
                        ).columns:
                            df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S').replace('NaT', None)

                        df.to_csv(csv_path, index=False, encoding='utf-8', na_rep='<NULL>')
                        exported_count += 1
                        logging.info(f"✅ Exported table: {table_name} ({len(df)} rows)")

                except Exception as e:
                    logging.warning(f"⚠️ Could not backup table {table_name}: {e}")

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
            if conn_sqlalchemy:
                conn_sqlalchemy.close()
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    # -------------------------------------------------------------------------
    # CSV RESTORE
    # -------------------------------------------------------------------------

    def restore_database_csv(self, input_zip_path, password=None):
        """
        استعادة آمنة: لا تقوم بمسح البيانات إلا إذا كان الملف البديل يحتوي على بيانات فعلاً.
        """
        temp_dir = 'temp_restore_csv'
        conn = None
        cursor = None
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            extracted, extract_msg = self._extract_backup_zip(input_zip_path, temp_dir, password=password)
            if not extracted:
                return False, extract_msg

            conn = self.get_raw_connection()
            self._drop_inventory_global_barcode_unique(conn)
            conn.start_transaction()
            cursor = conn.cursor()
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

            cursor.execute("SHOW TABLES")
            existing_db_tables = [row[0] for row in cursor.fetchall()]
            existing_table_by_lower = {table.lower(): table for table in existing_db_tables}

            backup_files = [f for f in os.listdir(temp_dir) if f.lower().endswith('.csv')]
            csv_file_by_table = {}
            tables_to_restore_data = []

            logging.info("🔍 Pre-checking backup files...")

            for file_name in backup_files:
                table_name = os.path.splitext(file_name)[0]
                table_match = existing_table_by_lower.get(table_name.lower())
                if not table_match:
                    logging.warning(f"Backup file '{file_name}' does not match an existing table. Skipping.")
                    continue

                csv_path = os.path.join(temp_dir, file_name)
                try:
                    df_check = pd.read_csv(csv_path, nrows=1)
                    if df_check.empty:
                        logging.warning(
                            f"⚠️ Backup file for '{table_name}' is EMPTY. "
                            f"Skipping restore for this table to preserve current data."
                        )
                        continue
                    tables_to_restore_data.append(table_match)
                    csv_file_by_table[table_match] = csv_path
                except Exception as e:
                    logging.warning(f"⚠️ Error checking file {file_name}: {e}")
                    continue

            if not tables_to_restore_data:
                logging.warning("🛑 No data found in the backup file. Operation aborted to protect database.")
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
                return False, "ملف النسخة الاحتياطية فارغ! لم يتم تغيير أي شيء في قاعدة البيانات."

            logging.info(f"🧹 Cleaning existing data for {len(tables_to_restore_data)} tables...")

            for table_to_clean in tables_to_restore_data:
                try:
                    cursor.execute(f"DELETE FROM {self._quote_identifier(table_to_clean)}")
                    logging.info(f"   - Cleared table: {table_to_clean}")
                except Exception as e:
                    logging.warning(f"   - Failed to clear {table_to_clean}: {e}")

            logging.info("📥 Restoring data...")

            tables_by_lower = {table.lower(): table for table in tables_to_restore_data}
            ordered_tables = [
                tables_by_lower[t.lower()]
                for t in TABLE_IMPORT_ORDER
                if t.lower() in tables_by_lower
            ]
            ordered_lower = {table.lower() for table in ordered_tables}
            remaining_tables = [
                table for table in tables_to_restore_data
                if table.lower() not in ordered_lower
            ]
            final_restore_list = ordered_tables + remaining_tables

            for table_name in final_restore_list:
                csv_file = csv_file_by_table.get(table_name)
                if not csv_file:
                    continue
                try:
                    df = pd.read_csv(
                        csv_file, keep_default_na=False, na_values=['<NULL>', 'nan', 'NaN']
                    )
                except Exception:
                    continue

                df = df.replace({np.nan: None})
                df.columns = df.columns.astype(str)
                df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]

                with self.engine.connect() as conn_inner:
                    try:
                        result = conn_inner.execute(text(f"SHOW COLUMNS FROM {self._quote_identifier(table_name)}"))
                        db_column_rows = result.fetchall()
                        db_columns = [row[0] for row in db_column_rows]
                        db_column_types = {row[0]: row[1] for row in db_column_rows}
                    except Exception:
                        continue

                common_cols = [col for col in df.columns if col in db_columns]
                if not common_cols:
                    continue

                df = df[common_cols]
                cols = ",".join([f"`{col}`" for col in common_cols])
                placeholders = ",".join(["%s"] * len(common_cols))
                sql = f"INSERT INTO {self._quote_identifier(table_name)} ({cols}) VALUES ({placeholders})"

                cleaned_data = []
                for row in df.values.tolist():
                    new_row = []
                    for col, val in zip(common_cols, row):
                        normalized_val = self._normalize_mysql_temporal_value(
                            val, db_column_types.get(col)
                        )
                        if normalized_val is None:
                            new_row.append(None)
                        else:
                            new_row.append(normalized_val)
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
            if conn:
                conn.rollback()
            logging.error(f"❌ Restore failed: {e}")
            return False, str(e)
        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    # -------------------------------------------------------------------------
    # EXCEL BACKUP
    # -------------------------------------------------------------------------

    def backup_database_excel(self, output_zip_path):
        """تصدير كامل لقاعدة البيانات بصيغة Excel مضغوطة."""
        temp_dir = 'temp_backup_excel'
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            with self.engine.connect() as conn:
                inspector = sa_inspect(self.engine)
                all_db_tables = inspector.get_table_names()

                for table_name in all_db_tables:
                    excel_path = os.path.join(temp_dir, f"{table_name}.xlsx")
                    try:
                        df = pd.read_sql(text(f"SELECT * FROM `{table_name}`"), conn)
                        df.to_excel(excel_path, index=False, engine='openpyxl')
                        logging.info(f"✅ Exported: {table_name}")
                    except Exception as e:
                        logging.warning(f"⚠️ Could not backup table {table_name}: {e}")

            with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        zipf.write(os.path.join(root, file), file)

            return True, "Success"
        except Exception as e:
            logging.error(f"❌ Backup failed: {e}")
            return False, str(e)
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    # -------------------------------------------------------------------------
    # EXCEL RESTORE
    # -------------------------------------------------------------------------

    def restore_database_excel(self, input_zip_path, password=None):
        """
        استعادة قاعدة البيانات من ملفات Excel مع معالجة ذكية للقيم الفارغة (NULL).
        """
        temp_dir = 'temp_restore_excel'
        conn = None
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            extracted, extract_msg = self._extract_backup_zip(input_zip_path, temp_dir, password=password)
            if not extracted:
                return False, extract_msg

            conn = self.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

            excel_files = [f for f in os.listdir(temp_dir) if f.endswith('.xlsx')]
            if not excel_files:
                csv_files = [f for f in os.listdir(temp_dir) if f.endswith('.csv')]
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
                conn.rollback()
                if csv_files:
                    return False, "This backup contains CSV files. Use restore_database_backup for automatic restore."
                return False, "No Excel files were found in this backup."

            EXCEL_IMPORT_ORDER = [
                'Users', 'Location_Types', 'Product_Families', 'Packaging_Units',
                'Manufacturers', 'Suppliers', 'External_Partners', 'Locations',
                'Automates', 'Waste_Reasons', 'Products_Master', 'Purchase_Orders',
                'PO_Details', 'Reception_Log', 'Reception_Details', 'Inventory_Batches',
                'Supplier_Credit_Notes', 'Credit_Note_Details'
            ]

            ordered_files = [f"{t}.xlsx" for t in EXCEL_IMPORT_ORDER if f"{t}.xlsx" in excel_files]
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
                            if col == 'Lot_Number' and (pd.isna(val) or str(val).strip() == ''):
                                row_list.append("NON_DEFINI")
                            elif pd.isna(val) or str(val).strip() == 'None' or str(val).strip() == 'NaT':
                                row_list.append(None)
                            else:
                                row_list.append(val)
                        cleaned_data.append(tuple(row_list))

                    cols_str = ", ".join([f"`{c}`" for c in df.columns])
                    placeholders = ", ".join(["%s"] * len(df.columns))
                    sql = f"INSERT INTO `{table_name}` ({cols_str}) VALUES ({placeholders})"

                    if cleaned_data:
                        cursor.executemany(sql, cleaned_data)
                        logging.info(f"✅ Restored {len(cleaned_data)} rows to {table_name}")

                except Exception as table_err:
                    logging.error(f"❌ Error restoring table {table_name}: {table_err}")

            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            conn.commit()
            logging.info("🚀 Database restoration completed successfully.")
            return True, "تمت استعادة قاعدة البيانات بنجاح من ملفات Excel."

        except Exception as e:
            if conn:
                conn.rollback()
            logging.error(f"❌ Global Restore Failure: {e}")
            return False, f"فشلت عملية الاستعادة: {str(e)}"

        finally:
            if conn and conn.is_connected():
                conn.close()
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    # -------------------------------------------------------------------------
    # ARCHIVE (Export & Purge old logs)
    # -------------------------------------------------------------------------

    def export_and_purge_tables(self, output_zip_path, days_to_keep=365):
        tables_to_archive = ['Stock_Movement_Log', 'Reception_Log']
        cutoff_date = date.today() - timedelta(days=days_to_keep)
        temp_dir = 'temp_archive_logs'

        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
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
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    # -------------------------------------------------------------------------
    # RESTORE SINGLE TABLE
    # -------------------------------------------------------------------------

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
        
    # -------------------------------------------------------------------------
    # MULTI-PATH BACKUP (AUTO & MANUAL)
    # -------------------------------------------------------------------------

    def create_multi_backup(self, target_paths: list, password: str = "", is_auto: bool = True):
        """
        يقوم بتوليد النسخة الاحتياطية ونسخها إلى جميع المسارات المحددة في القائمة.
        إذا كان is_auto=True: يضعها في مجلد Auto_Backups ويحذف النسخ القديمة.
        إذا كان is_auto=False: يضعها مباشرة في المسار المحدد بدون حذف القديم.
        """
        import datetime
        import shutil
        import os
        
        if not target_paths:
            return False, "لم يتم تحديد أي مسار للنسخ الاحتياطي."
            
        try:
            import pyzipper
            has_pyzipper = True
        except ImportError:
            has_pyzipper = False
            logging.warning("⚠️ Module 'pyzipper' non installé. Le mot de passe ne sera pas appliqué.")

        # 1. تحضير أسماء الملفات
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        prefix = "AutoBackup" if is_auto else "ManualBackup"
        zip_filename = f"{prefix}_{timestamp}.zip"
        
        master_zip_path = os.path.abspath(f'temp_{zip_filename}')
        temp_csv_dir = os.path.abspath('temp_export_csv')

        try:
            # 2. إنشاء المجلد المؤقت واستخراج البيانات
            if os.path.exists(temp_csv_dir):
                shutil.rmtree(temp_csv_dir)
            os.makedirs(temp_csv_dir)

            with self.engine.connect() as conn_sa:
                inspector = sqlalchemy.inspect(self.engine)
                for table_name in inspector.get_table_names():
                    try:
                        df = pd.read_sql_query(text(f"SELECT * FROM `{table_name}`"), conn_sa)
                        
                        # معالجة تنسيق التواريخ لمنع الأخطاء عند الاستعادة
                        if not df.empty:
                            for col in df.select_dtypes(include=['datetime64[ns]', 'datetime']).columns:
                                df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S').replace('NaT', None)
                                
                        df.to_csv(os.path.join(temp_csv_dir, f"{table_name}.csv"), index=False, encoding='utf-8', na_rep='<NULL>')
                    except Exception as e:
                        logging.warning(f"⚠️ Export error {table_name}: {e}")

            if password:
                if not has_pyzipper:
                    return False, "فشل التشفير: مكتبة 'pyzipper' غير مثبتة. يرجى تثبيتها (pip install pyzipper)."
                
                with pyzipper.AESZipFile(master_zip_path, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zipf:
                    zipf.setpassword(password.encode('utf-8'))
                    for root, _, files in os.walk(temp_csv_dir):
                        for file in files:
                            zipf.write(os.path.join(root, file), file)
            else:
                # إنشاء ملف عادي بدون كلمة مرور
                with zipfile.ZipFile(master_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, _, files in os.walk(temp_csv_dir):
                        for file in files:
                            zipf.write(os.path.join(root, file), file)
            # 4. توزيع الملف الماستر على جميع المسارات المحددة
            success_count = 0
            for base_path in target_paths:
                try:
                    # التوجيه الذكي: إذا كان المسار هو C:\ مباشرة، نقوم بإنشاء مجلد فرعي لتجنب Permission Denied
                    if os.path.abspath(base_path) == os.path.abspath("C:\\"):
                        base_path = os.path.join("C:\\", "System_Backups")
                        logging.info(f"⚠️ Redirection automatique vers {base_path} pour éviter l'erreur de permission.")

                    # تحديد المجلد الوجهة
                    dest_dir = os.path.join(base_path, "Auto_Backups") if is_auto else base_path
                    os.makedirs(dest_dir, exist_ok=True)
                    
                    # حذف النسخ التلقائية القديمة في هذا المسار
                    if is_auto:
                        for file_name in os.listdir(dest_dir):
                            if file_name.endswith('.zip') and file_name.startswith('AutoBackup'):
                                try: 
                                    os.remove(os.path.join(dest_dir, file_name))
                                except Exception: 
                                    pass
                                
                    # نسخ الملف إلى الوجهة النهائية
                    final_path = os.path.join(dest_dir, zip_filename)
                    shutil.copy2(master_zip_path, final_path)
                    success_count += 1
                    logging.info(f"✅ Sauvegarde copiée vers : {final_path}")
                except Exception as e:
                    logging.error(f"❌ Impossible de copier vers {base_path}: {e}")

            if success_count > 0:
                return True, f"نجاح ({success_count}/{len(target_paths)})"
            return False, "فشلت جميع محاولات النسخ."

        except Exception as e:
            logging.error(f"❌ Backup Error: {e}")
            return False, str(e)
        finally:
            # 5. تنظيف الملفات المؤقتة
            if os.path.exists(temp_csv_dir):
                shutil.rmtree(temp_csv_dir)
            if os.path.exists(master_zip_path):
                os.remove(master_zip_path)

    # -------------------------------------------------------------------------
    # ALIASES (backward compatibility)
    # -------------------------------------------------------------------------

    def export_all_tables_to_csv_zip(self, output_zip_path='backup_csv.zip'):
        return self.backup_database_csv(output_zip_path)

    def restore_from_archive_zip_destructive(self, input_zip_path, tables_to_restore=None):
        return self.restore_database_csv(input_zip_path)

    def get_available_archives(self):
        return []

    def truncate_all_tables(self):
        return False, "Not Implemented"
