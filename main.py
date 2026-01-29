# main.py

import sys
import os
import logging
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
# 1. إضافة QLockFile و QDir للاستيراد
from PySide6.QtCore import Qt, QSettings, QLockFile, QDir 
from database.base import Database
from database import LabDataManager
from ui.main_window import MainWindow
from ui.login_dialog import LoginDialog 

# إعدادات التسجيل (Logging)
os.environ["QT_LOGGING_RULES"] = "*.warning=false"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def check_env_file():
    """التحقق من وجود ملف إعدادات البيئة"""
    if not os.path.exists(".env"):
        logging.critical("FATAL: .env file not found.")
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "Erreur Fatale", "Le fichier .env est introuvable.\nVeuillez configurer la base de données.")
        return False
    return True

def main():
    if not check_env_file():
        return

    app = QApplication(sys.argv)
    
    # =========================================================================
    # [بداية التعديل] : منع تشغيل البرنامج مرتين (Single Instance)
    # =========================================================================
    # تحديد مسار ملف القفل في المجلد المؤقت للنظام
    lock_file_path = os.path.join(QDir.tempPath(), 'modernlam_stockmanager.lock')
    lock_file = QLockFile(lock_file_path)
    
    # نحاول قفل الملف، إذا فشل (رجع False) فهذا يعني أن البرنامج مفتوح مسبقاً
    # نستخدم مهلة 100 ميلي ثانية للتأكد
    if not lock_file.tryLock(100):
        QMessageBox.warning(
            None, 
            "Déjà ouvert", 
            "Le programme est déjà en cours d'exécution !\n(Impossible d'ouvrir une seconde instance)"
        )
        sys.exit(1) # إغلاق النسخة الثانية فوراً
    # =========================================================================
    # [نهاية التعديل] : سيظل lock_file محجوزاً طالما البرنامج يعمل
    # =========================================================================

    # إعدادات لحفظ الجلسة (اسم المستخدم وكلمة المرور)
    settings = QSettings("ModernLam", "StockManager")
    
    while True:
        data_manager = None
        connection_error = None
        current_user = None

        # 1. محاولة الاتصال بقاعدة البيانات
        try:
            db = Database()
            data_manager = LabDataManager(db)
        except Exception as e:
            connection_error = str(e)
            logging.error(f"Database connection failed: {e}")

        # 2. التحقق من الجلسة المحفوظة (Auto-Login)
        saved_user = settings.value("saved_username")
        saved_pass = settings.value("saved_password")

        if data_manager and saved_user and saved_pass:
            try:
                # [هام] نستخدم دالة authenticate وليس select مباشرة
                user_found = data_manager.users.authenticate(saved_user, saved_pass)
                
                if user_found:
                    logging.info(f"Auto-login successful for user: {saved_user}")
                    current_user = user_found
                else:
                    logging.warning("Auto-login failed. Clearing session.")
                    settings.remove("saved_username")
                    settings.remove("saved_password")
                    current_user = None
            except Exception as e:
                logging.error(f"Session recovery error: {e}")
                current_user = None

        # 3. إظهار نافذة الدخول إذا لم يتم التعرف على المستخدم تلقائياً
        if data_manager and not current_user:
            login_dlg = LoginDialog(data_manager)
            if login_dlg.exec() == QDialog.Accepted:
                current_user = login_dlg.user_data
                
                if login_dlg.remember_me.isChecked():
                    settings.setValue("saved_username", current_user['Username'])
                    settings.setValue("saved_password", login_dlg.password_input.text().strip())
                else:
                    settings.remove("saved_username")
                    settings.remove("saved_password")
            else:
                return 

        # نمرر connection_error لكي تظهر رسالة خطأ داخل النافذة إذا لم تنجح قاعدة البيانات
        window = MainWindow(data_manager, current_user, connection_error)
        window.showMaximized() 
        
        exit_code = app.exec()
        
        # 5. منطق تسجيل الخروج وإعادة التشغيل
        if hasattr(window, 'want_logout') and window.want_logout:
            logging.info("User requested logout. Restarting login process...")
            
            # عند تسجيل الخروج يدوياً، نمسح الإعدادات لكي لا يدخل تلقائياً مرة أخرى
            settings.remove("saved_username")
            settings.remove("saved_password")
            
            del window
            continue  # يعيد الحلقة while True من البداية
        else:
            sys.exit(exit_code)

if __name__ == "__main__":
    main()