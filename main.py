# main.py

import sys
import os
import logging
from logging.handlers import RotatingFileHandler
import traceback
import threading
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

from dotenv import dotenv_values
from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
    QDialog,
)
from PySide6.QtCore import QSettings, QLockFile, QDir
from database.base import Database, get_external_path
from database import LabDataManager
from ui.main_window import MainWindow
from ui.login_dialog import LoginDialog 
from tools.inventory_mobile_api import build_server as build_inventory_mobile_server
from tools.inventory_mobile_api import build_discovery_server as build_inventory_discovery_server
from tools.mobile_barcode_bridge import MobileBarcodeBridge

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

DB_CONNECTION_ATTEMPTS = 2
_mobile_api_server = None
_mobile_api_thread = None
_mobile_discovery_server = None
_mobile_discovery_thread = None
_mobile_barcode_bridge = None

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
    env_path = get_external_path(".env")
    if not os.path.exists(env_path):
        logger.critical(f"FATAL: .env file not found at {env_path}.")
        app = QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Erreur Fatale",
            f"Le fichier .env est introuvable:\n{env_path}\n\nVeuillez configurer la base de donnees."
        )
        return False
    return True



def _get_runtime_db_config():
    env_path = get_external_path(".env")
    values = dotenv_values(env_path) if os.path.exists(env_path) else {}

    port_value = values.get("DB_PORT") or "3306"
    try:
        port = int(port_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"DB_PORT invalide dans .env: {port_value}") from exc

    config = {
        "host": values.get("DB_HOST") or "localhost",
        "port": port,
        "user": values.get("DB_USER"),
        "password": values.get("DB_PASSWORD"),
        "database": values.get("DB_NAME"),
    }
    missing = [key for key in ("user", "password", "database") if not config.get(key)]
    if missing:
        raise ValueError(f"Variables DB manquantes dans .env: {', '.join(missing)}")
    return env_path, config



def _format_connection_error(error):
    parts = [f"{error.__class__.__name__}: {error}"]
    for attr in ("errno", "sqlstate", "msg"):
        value = getattr(error, attr, None)
        if value:
            parts.append(f"{attr}: {value}")
    return "\n".join(parts)


def connect_to_database_with_retry(app):
    last_error = None
    for attempt in range(1, DB_CONNECTION_ATTEMPTS + 1):
        try:
            Database.reset_connection_state()
            env_path, db_config = _get_runtime_db_config()
            logger.info("Lecture configuration: %s", env_path)
            logger.info(
                "Cible MySQL: "
                f"{db_config['host']}:{db_config['port']} / "
                f"base={db_config['database']} / utilisateur={db_config['user']}"
            )

            db = Database()
            data_manager = LabDataManager(db)
            logger.info("Connexion MySQL et initialisation application OK.")
            return data_manager, None

        except Exception as error:
            Database.reset_connection_state()
            last_error = _format_connection_error(error)
            logger.warning(
                "Echec connexion base de donnees tentative %s/%s: %s",
                attempt,
                DB_CONNECTION_ATTEMPTS,
                last_error,
            )
            logger.debug("Database connection attempt failed.", exc_info=True)

    detailed_error = (
        "Impossible de se connecter a la base de donnees apres plusieurs tentatives.\n\n"
        f"{last_error or 'Erreur inconnue'}\n\n"
        f"Journal detaille: {log_file_path}"
    )
    QMessageBox.warning(
        None,
        "Connexion base de donnees impossible",
        "Connexion a la base de donnees impossible.\n\n"
        "Le programme va ouvrir les parametres de connexion.\n\n"
        f"{last_error or 'Erreur inconnue'}",
    )
    return None, detailed_error


def start_inventory_mobile_api(data_manager, window):
    global _mobile_api_server, _mobile_api_thread
    global _mobile_discovery_server, _mobile_discovery_thread, _mobile_barcode_bridge

    if not data_manager:
        return

    if _mobile_barcode_bridge is None:
        _mobile_barcode_bridge = MobileBarcodeBridge(window)
    else:
        _mobile_barcode_bridge.set_window(window)

    if _mobile_api_server is not None:
        _mobile_api_server.data_manager = data_manager
        return

    host = os.getenv("INVENTORY_MOBILE_API_HOST", "0.0.0.0")
    port = int(os.getenv("INVENTORY_MOBILE_API_PORT", "8787"))
    discovery_port = int(os.getenv("INVENTORY_MOBILE_DISCOVERY_PORT", "8788"))

    try:
        _mobile_api_server = build_inventory_mobile_server(
            host,
            port,
            data_manager=data_manager,
            remote_scan_callback=_mobile_barcode_bridge.submit,
        )
        _mobile_api_thread = threading.Thread(
            target=_mobile_api_server.serve_forever,
            name="InventoryMobileAPI",
            daemon=True,
        )
        _mobile_api_thread.start()
        logger.info("Inventory mobile API started on http://%s:%s", host, port)
    except OSError as error:
        _mobile_api_server = None
        _mobile_api_thread = None
        logger.warning("Inventory mobile API could not start on %s:%s: %s", host, port, error)
        return

    try:
        _mobile_discovery_server = build_inventory_discovery_server(
            host,
            discovery_port,
            port,
            device_name=_mobile_api_server.device_name,
            device_id=_mobile_api_server.device_id,
        )
        _mobile_discovery_thread = threading.Thread(
            target=_mobile_discovery_server.serve_forever,
            name="InventoryMobileDiscovery",
            daemon=True,
        )
        _mobile_discovery_thread.start()
        logger.info("Inventory mobile discovery started on UDP %s:%s", host, discovery_port)
    except OSError as error:
        _mobile_discovery_server = None
        _mobile_discovery_thread = None
        logger.warning(
            "Inventory mobile discovery could not start on UDP %s:%s: %s. Manual connection remains available.",
            host,
            discovery_port,
            error,
        )


def stop_inventory_mobile_api():
    global _mobile_api_server, _mobile_api_thread
    global _mobile_discovery_server, _mobile_discovery_thread, _mobile_barcode_bridge

    try:
        if _mobile_discovery_server is not None:
            _mobile_discovery_server.shutdown()
            _mobile_discovery_server.server_close()
            logger.info("Inventory mobile discovery stopped.")
        if _mobile_api_server is not None:
            _mobile_api_server.shutdown()
            _mobile_api_server.server_close()
            logger.info("Inventory mobile API stopped.")
    except Exception:
        logger.warning("Inventory mobile services stop failed.", exc_info=True)
    finally:
        _mobile_api_server = None
        _mobile_api_thread = None
        _mobile_discovery_server = None
        _mobile_discovery_thread = None
        _mobile_barcode_bridge = None


# =========================================================================
# 4. الدالة الرئيسية (Main)
# =========================================================================
def main():
    if not check_env_file():
        return

    app = QApplication(sys.argv)
    app.setApplicationName(branding.get_app_name())
    app.setOrganizationName(branding.get_organization_name())
    app.aboutToQuit.connect(stop_inventory_mobile_api)
    
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
        data_manager, connection_error = connect_to_database_with_retry(app)

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
        if data_manager and not connection_error:
            start_inventory_mobile_api(data_manager, window)
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
