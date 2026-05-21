# database/auto_backup_worker.py

import os
import sys
import json
import time
import logging
from PySide6.QtCore import QThread

def get_external_path(filename):
    """ضمان الوصول للمسار الصحيح لملف الإعدادات سواء في بيئة التطوير أو كملف تنفيذي"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(os.path.dirname(sys.executable), filename)
    return os.path.join(os.path.abspath("."), filename)

class AutoBackupWorker(QThread):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.config_file = get_external_path("config.json")
        self.running = True

    def run(self):
        # مهم جداً: إعادة تعيين المتغير إلى True في حال تم عمل Restart للـ Thread من الإعدادات
        self.running = True
        if not self.data_manager or not getattr(self.data_manager, 'db', None):
            logging.info("Auto-backup worker skipped: no database connection is available.")
            return

        logging.info("🔄 Auto-backup worker started in background.")

        while self.running:
            try:
                # 1. قراءة الإعدادات
                if not os.path.exists(self.config_file):
                    self._sleep_check(60)
                    continue

                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                # 2. استخراج قيم الحفظ التلقائي
                is_enabled = config.get("auto_backup_enabled", False)
                interval_mins = float(config.get("auto_backup_interval", 60.0))
                password = config.get("auto_backup_password", "")
                
                backup_paths = config.get("backup_paths", [])
                if not backup_paths and config.get("backup_path"):
                    backup_paths = [config["backup_path"]]

                # إذا كان مغلقاً أو لا يوجد مسار محدد، انتظر دقيقة وتحقق مجدداً
                if not is_enabled or not backup_paths:
                    self._sleep_check(60)
                    continue

                # 3. تنفيذ عملية الحفظ
                # (تم تصحيح الاستدعاء هنا)
                success, msg = self.data_manager.db.create_multi_backup(backup_paths, password, is_auto=True)
                
                if success:
                    logging.info(f"✅ Auto-backup success: {msg}")
                else:
                    logging.warning(f"⚠️ Auto-backup issue: {msg}")

                # 4. النوم للفترة المحددة في الإعدادات (تحويل الدقائق إلى ثواني)
                sleep_seconds = int(interval_mins * 60)
                self._sleep_check(sleep_seconds)

            except Exception as e:
                logging.error(f"❌ Critical error in auto-backup thread: {e}")
                self._sleep_check(60) # راحة دقيقة في حال حدوث خطأ كارثي لتجنب تجميد المعالج
                
    def _sleep_check(self, seconds):
        """
        دالة ذكية للنوم:
        تنام ثانية بثانية لتسمح بالتوقف الفوري للـ Thread عند إغلاق التطبيق
        بدلاً من تجميد الواجهة لوقت طويل.
        """
        for _ in range(seconds):
            if not self.running:
                break
            time.sleep(1)

    def stop(self):
        """إيقاف الـ Thread بأمان تام"""
        self.running = False
        self.wait()
