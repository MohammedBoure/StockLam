import os
import shutil
import zipfile
import logging
import pandas as pd

from .config import ARCHIVE_VIEW_FLAG_FILE


class ArchiveViewManagerMixin:
    """Mixin that provides archive-view (read-only historical data) methods."""

    def activate_archive_view(self, input_zip_path):
        temp_dir = 'temp_view_archive'
        archive_prefix = "ARCHIVE_VIEW_"

        try:
            if hasattr(self, 'is_archive_mode') and self.is_archive_mode:
                return False, "النظام بالفعل في وضع الأرشيف."

            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
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
            with open(ARCHIVE_VIEW_FLAG_FILE, 'w') as f:
                f.write('1')

            return True, "تم تفعيل وضع الأرشيف (Read-Only). يمكنك الآن تصفح السجلات القديمة."

        except Exception as e:
            self.deactivate_archive_view()
            return False, f"فشل تحميل الأرشيف: {e}"
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

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

    def is_archive_view_mode(self):
        return os.path.exists(ARCHIVE_VIEW_FLAG_FILE)

    def get_archive_view_tables(self):
        return getattr(self, 'table_map', {})

    def get_archive_view_status(self):
        return {"active": self.is_archive_view_mode(), "file": None}
