# main.py

import sys
import os
import logging
from logging.handlers import RotatingFileHandler
import traceback
from datetime import datetime
import branding


def configure_runtime_brand(argv):
    configure_from_argv = getattr(branding, "configure_brand_from_argv", None)
    if callable(configure_from_argv):
        configure_from_argv(argv)
        return

    configure = getattr(branding, "configure_brand", None)
    if len(argv) > 1 and callable(configure):
        configure(argv[1])
        del argv[1]

try:
    configure_runtime_brand(sys.argv)
except ValueError as e:
    print(e)
    print("Usage: python main.py [stocklam|modernstock]")
    sys.exit(2)

import pandas as pd

from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
from PySide6.QtCore import Qt, QSettings, QLockFile, QDir 
from database.base import Database
from database import LabDataManager
from ui.main_window import MainWindow
from ui.login_dialog import LoginDialog 

# =========================================================================
# 1. إعدادات التسجيل (Logging) المتقدمة
# =========================================================================
os.environ["QT_LOGGING_RULES"] = "*.warning=false"

# مسار ملف السجل
log_file_path = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.abspath("."), "app.log")

# تدوير السجلات: 5 ميجابايت كحد أقصى، مع الاحتفاظ بـ 3 نسخ قديمة
file_handler = RotatingFileHandler(
    log_file_path, 
    maxBytes=5 * 1024 * 1024, # 5 MB
    backupCount=3,
    encoding='utf-8'
)
console_handler = logging.StreamHandler(sys.stdout)

# تنسيق السجل
formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)

# =========================================================================
# 2. صائد الأخطاء المفاجئة (Global Crash Handler)
# =========================================================================
def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("❌ Erreur Critique (Crash Système):", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = global_exception_handler

# =========================================================================
# 3. الدوال المساعدة
# =========================================================================
def check_env_file():
    """التحقق من وجود ملف إعدادات البيئة"""
    if not os.path.exists(".env"):
        logger.critical("FATAL: .env file not found.")
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "Erreur Fatale", "Le fichier .env est introuvable.\nVeuillez configurer la base de données.")
        return False
    return True

# =========================================================================
# 4. الدالة الرئيسية (Main)
# =========================================================================
def main():
    if not check_env_file():
        return

    app = QApplication(sys.argv)
    app.setApplicationName(branding.get_app_name())
    app.setOrganizationName(branding.get_organization_name())
    
    # --- منع تشغيل البرنامج مرتين (Single Instance) ---
    lock_file_path = os.path.join(QDir.tempPath(), branding.get_lock_file_name())
    lock_file = QLockFile(lock_file_path)
    
    if not lock_file.tryLock(100):
        QMessageBox.warning(
            None, 
            "Déjà ouvert", 
            "Le programme est déjà en cours d'exécution !\n(Impossible d'ouvrir une seconde instance)"
        )
        sys.exit(1)
    
    # إعدادات البرنامج
    settings = QSettings(branding.get_organization_name(), branding.get_settings_app_name())
    
    # --- الحماية ضد التلاعب بالتاريخ (Time-Travel Protection) ---
    current_date = datetime.now().date()
    last_run_str = settings.value("last_run_date")
    
    if last_run_str:
        try:
            last_run_date = datetime.strptime(last_run_str, "%Y-%m-%d").date()
            if current_date < last_run_date:
                error_msg = (
                    f"⚠️ Erreur Critique : Date Système Invalide\n\n"
                    f"La date actuelle de votre ordinateur ({current_date.strftime('%d/%m/%Y')}) "
                    f"est antérieure à la dernière utilisation du programme ({last_run_date.strftime('%d/%m/%Y')}).\n\n"
                    f"Cela peut corrompre la base de données. Veuillez corriger la date et l'heure de votre système avant de continuer."
                )
                logger.error(f"System date error: Current ({current_date}) < Last Run ({last_run_date})")
                QMessageBox.critical(None, "Erreur de Date", error_msg)
                sys.exit(1)
        except Exception as e:
            logger.error(f"Error parsing last_run_date: {e}")

    settings.setValue("last_run_date", current_date.strftime("%Y-%m-%d"))

    # --- حلقة التشغيل الرئيسية ---
    while True:
        data_manager = None
        connection_error = None
        current_user = None

        # محاولة الاتصال بقاعدة البيانات
        try:
            db = Database()
            data_manager = LabDataManager(db)
        except Exception as e:
            connection_error = str(e)
            logger.error(f"Database connection failed: {e}")

        # التحقق من الجلسة المحفوظة (Auto-Login)
        saved_user = settings.value("saved_username")
        saved_pass = settings.value("saved_password")

        if data_manager and saved_user and saved_pass:
            try:
                user_found = data_manager.users.authenticate(saved_user, saved_pass)
                if user_found:
                    logger.info(f"Auto-login successful for user: {saved_user}")
                    current_user = user_found
                else:
                    logger.warning("Auto-login failed. Clearing session.")
                    settings.remove("saved_username")
                    settings.remove("saved_password")
                    current_user = None
            except Exception as e:
                logger.error(f"Session recovery error: {e}")
                current_user = None

        # إظهار نافذة الدخول إذا لم يتم التعرف على المستخدم تلقائياً
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

        # تشغيل النافذة الرئيسية
        window = MainWindow(data_manager, current_user, connection_error)
        window.showMaximized() 
        
        exit_code = app.exec()
        
        # منطق تسجيل الخروج وإعادة التشغيل
        if hasattr(window, 'want_logout') and window.want_logout:
            logger.info("User requested logout. Restarting login process...")
            settings.remove("saved_username")
            settings.remove("saved_password")
            del window
            continue  
        else:
            sys.exit(exit_code)

if __name__ == "__main__":
    main()
