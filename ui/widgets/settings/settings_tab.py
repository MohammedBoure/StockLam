# ui/widgets/settings/settings_tab.py

import json
import os
import logging
import win32print 
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QGroupBox, QFormLayout, 
                               QSpinBox, QMessageBox, QFileDialog, QTabWidget,
                               QComboBox, QInputDialog, QCheckBox, QDoubleSpinBox,
                               QListWidget, QTextEdit)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
import mysql.connector
import sys
from dotenv import dotenv_values

from .pdf_config_tab import PdfConfigWidget 
from .system_logs_tab import SystemLogsTab

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def get_external_path(filename):
    """توحيد مسار الحفظ ليتطابق بنسبة 100% مع مسارات البرنامج الرئيسية"""
    if hasattr(sys, '_MEIPASS'):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, filename)

CONFIG_FILE = get_external_path("config.json") 
ENV_FILE = get_external_path(".env")

class SettingsTab(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        
        # Paramètres par défaut
        self.settings = {
            "lab_name": "Laboratoire Algérie",
            "lab_address": "Alger, Algérie",
            "expiry_warning_days": 30,
            "low_stock_threshold": 5,
            
            # --- Auto Backup Settings ---
            "auto_backup_enabled": False,
            "auto_backup_interval": 60.0,
            "auto_backup_password": "",
            "backup_paths": [],
            
            "db_host": "127.0.0.1",
            "db_port": 3306,
            "db_user": "root",
            "db_password": "root",
            "db_name": "Lab_Inventory_Enterprise_DB",
            
            "flask_env": "development",
            "secret_key": "change_me_key",
            "max_content_length": 16777216,
            
            "selected_printer": "",
            "label_width": 50,
            "label_height": 30,
            "gap": 2
        }
        
        self.load_settings()
        self.load_database_settings_from_env()
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        
        # Initialize widgets only
        self.tab_general = QWidget()
        self._setup_general_tab()
        
        self.tab_db = QWidget()
        self._setup_database_tab()
        
        self.tab_printer = QWidget()
        self._setup_printer_tab()
        
        self.tab_system = QWidget()
        self._setup_system_tab()

        self.tab_system_logs = SystemLogsTab(self.data_manager) if self.data_manager else QWidget()
        self.tab_pdf_config = PdfConfigWidget(self.settings)

        main_layout.addWidget(self.tabs)

        # Bottom buttons setup
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("💾 Enregistrer les paramètres")
        btn_save.setStyleSheet("background-color: #27ae60; color: white; padding: 10px; font-weight: bold;")
        btn_save.clicked.connect(self.save_settings)
        
        btn_export_env = QPushButton("📄 Exporter .env")
        btn_export_env.setStyleSheet("background-color: #2980b9; color: white; padding: 10px;")
        btn_export_env.clicked.connect(self.export_to_env_file)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_export_env)
        btn_layout.addWidget(btn_save)
        
        main_layout.addLayout(btn_layout)

    def _setup_general_tab(self):
        main_h_layout = QHBoxLayout(self.tab_general)
        left_col = QVBoxLayout()
        right_col = QVBoxLayout()

        # ---------------------------------------------------------
        # COLONNE GAUCHE
        # ---------------------------------------------------------
        
        grp_info = QGroupBox("📋 Informations du laboratoire")
        form_info = QFormLayout()
        self.txt_lab_name = QLineEdit(self.settings.get("lab_name", ""))
        self.txt_lab_address = QLineEdit(self.settings.get("lab_address", ""))
        form_info.addRow("Nom du laboratoire :", self.txt_lab_name)
        form_info.addRow("Adresse :", self.txt_lab_address)
        grp_info.setLayout(form_info)
        left_col.addWidget(grp_info)

        grp_alerts = QGroupBox("⚠️ Paramètres d'alerte & Seuils")
        form_alerts = QFormLayout()
        self.spin_expiry = QSpinBox()
        self.spin_expiry.setRange(1, 3650)
        self.spin_expiry.setValue(int(self.settings.get("expiry_warning_days", 30)))
        self.spin_expiry.setSuffix(" jours")
        self.spin_stock = QSpinBox()
        self.spin_stock.setRange(1, 1000)
        self.spin_stock.setValue(int(self.settings.get("low_stock_threshold", 5)))
        self.spin_stock.setSuffix(" unités")
        form_alerts.addRow("Alerte péremption (avant) :", self.spin_expiry)
        form_alerts.addRow("Seuil stock critique :", self.spin_stock)
        grp_alerts.setLayout(form_alerts)
        left_col.addWidget(grp_alerts)
        
        grp_data = QGroupBox("💾 Gestion Manuelle & Archives")
        data_layout = QVBoxLayout()
        row1 = QHBoxLayout()
        btn_backup = QPushButton("📦 Sauvegarde complète (Excel)")
        btn_backup.clicked.connect(self.perform_backup)
        btn_restore = QPushButton("♻️ Restauration complète")
        btn_restore.setStyleSheet("color: #c0392b;")
        btn_restore.clicked.connect(self.perform_restore)
        row1.addWidget(btn_backup)
        row1.addWidget(btn_restore)
        data_layout.addLayout(row1)
        
        btn_archive = QPushButton("🧹 Archiver les historiques")
        btn_archive.clicked.connect(self.perform_archive_logs)
        data_layout.addWidget(btn_archive)
        
        self.grp_view_mode = QGroupBox("👁️ Mode aperçu archive")
        view_layout = QVBoxLayout()
        self.lbl_mode_status = QLabel("Mode actuel : ✅ Données en direct")
        self.lbl_mode_status.setStyleSheet("color: green; font-weight: bold;")
        self.lbl_mode_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_toggle_view = QPushButton("📂 Ouvrir un fichier archive")
        self.btn_toggle_view.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold;")
        self.btn_toggle_view.clicked.connect(self.toggle_archive_view)
        view_layout.addWidget(self.lbl_mode_status)
        view_layout.addWidget(self.btn_toggle_view)
        self.grp_view_mode.setLayout(view_layout)
        data_layout.addWidget(self.grp_view_mode)
        grp_data.setLayout(data_layout)
        left_col.addWidget(grp_data)
        left_col.addStretch()

        # ---------------------------------------------------------
        # COLONNE DROITE
        # ---------------------------------------------------------
        
        grp_auto_backup = QGroupBox("⏱️ Sauvegarde Automatique (Arrière-plan)")
        auto_backup_layout = QVBoxLayout()
        form_auto = QFormLayout()

        self.chk_auto_backup = QCheckBox("Activer la sauvegarde automatique")
        # Ensure we are parsing the boolean properly
        self.chk_auto_backup.setChecked(bool(self.settings.get("auto_backup_enabled", False)))
        
        self.spin_auto_interval = QDoubleSpinBox()
        self.spin_auto_interval.setRange(0.1, 1440.0) 
        self.spin_auto_interval.setValue(float(self.settings.get("auto_backup_interval", 60.0)))
        self.spin_auto_interval.setSuffix(" min")
        
        self.txt_auto_pwd = QLineEdit(self.settings.get("auto_backup_password", ""))
        self.txt_auto_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_auto_pwd.setPlaceholderText("Laissez vide pour fichier ZIP normal")

        form_auto.addRow("", self.chk_auto_backup)
        form_auto.addRow("Intervalle :", self.spin_auto_interval)
        form_auto.addRow("Mot de passe ZIP :", self.txt_auto_pwd)
        auto_backup_layout.addLayout(form_auto)

        auto_backup_layout.addWidget(QLabel("Dossiers de destination (Cibles multiples) :"))
        self.list_backup_paths = QListWidget()
        
        paths = self.settings.get("backup_paths", [])
        if not paths and self.settings.get("backup_path"):
            paths = [self.settings.get("backup_path")]
        for p in paths:
            self.list_backup_paths.addItem(str(p))

        path_btns_layout = QHBoxLayout()
        btn_add_path = QPushButton("➕ Ajouter un dossier")
        btn_add_path.clicked.connect(self.add_backup_path)
        btn_rem_path = QPushButton("❌ Supprimer sélection")
        btn_rem_path.clicked.connect(self.remove_backup_path)
        path_btns_layout.addWidget(btn_add_path)
        path_btns_layout.addWidget(btn_rem_path)
        
        auto_backup_layout.addWidget(self.list_backup_paths)
        auto_backup_layout.addLayout(path_btns_layout)

        btn_force_auto = QPushButton("▶️ Forcer la sauvegarde maintenant")
        btn_force_auto.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; padding: 8px;")
        btn_force_auto.clicked.connect(self.force_manual_backup)
        auto_backup_layout.addWidget(btn_force_auto)

        grp_auto_backup.setLayout(auto_backup_layout)
        right_col.addWidget(grp_auto_backup)
        right_col.addStretch()

        main_h_layout.addLayout(left_col, 50)
        main_h_layout.addLayout(right_col, 50)

    def _setup_database_tab(self):
        layout = QVBoxLayout(self.tab_db)
        grp_conn = QGroupBox("Connexion MySQL")
        form_conn = QFormLayout()
        
        self.txt_db_host = QLineEdit(str(self.settings.get("db_host", "")))
        self.spin_db_port = QSpinBox()
        self.spin_db_port.setRange(1, 65535)
        self.spin_db_port.setValue(int(self.settings.get("db_port", 3306)))
        self.txt_db_user = QLineEdit(str(self.settings.get("db_user", "")))
        self.txt_db_pass = QLineEdit(str(self.settings.get("db_password", "")))
        self.txt_db_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_db_name = QLineEdit(str(self.settings.get("db_name", "")))
        
        form_conn.addRow("Hôte :", self.txt_db_host)
        form_conn.addRow("Port :", self.spin_db_port)
        form_conn.addRow("Utilisateur :", self.txt_db_user)
        form_conn.addRow("Mot de passe :", self.txt_db_pass)
        form_conn.addRow("Base de données :", self.txt_db_name)
        grp_conn.setLayout(form_conn)
        layout.addWidget(grp_conn)
        
        btn_test = QPushButton("🔌 Tester la connexion")
        btn_test.clicked.connect(self.test_db_connection)
        layout.addWidget(btn_test)

        self.grp_connection_error = QGroupBox("Derniere erreur de connexion")
        error_layout = QVBoxLayout(self.grp_connection_error)
        self.txt_connection_error = QTextEdit()
        self.txt_connection_error.setReadOnly(True)
        self.txt_connection_error.setMinimumHeight(130)
        error_layout.addWidget(self.txt_connection_error)
        self.grp_connection_error.setVisible(False)
        layout.addWidget(self.grp_connection_error)

        layout.addStretch()

    def _setup_printer_tab(self):
        layout = QVBoxLayout(self.tab_printer)
        grp_print = QGroupBox("Paramètres des étiquettes code-barres")
        form_print = QFormLayout()
        
        self.combo_printers = QComboBox()
        try:
            printers = win32print.EnumPrinters(2)
            printer_names = [p[2] for p in printers]
            self.combo_printers.addItems(printer_names)
        except:
            self.combo_printers.addItem("Erreur lors de la liste des imprimantes")

        current_p = self.settings.get("selected_printer", "")
        if current_p:
            idx = self.combo_printers.findText(current_p)
            if idx >= 0: self.combo_printers.setCurrentIndex(idx)
            
        self.spin_width = QSpinBox()
        self.spin_width.setRange(10, 150)
        self.spin_width.setValue(int(self.settings.get("label_width", 50)))
        
        self.spin_height = QSpinBox()
        self.spin_height.setRange(10, 150)
        self.spin_height.setValue(int(self.settings.get("label_height", 30)))
        
        self.spin_gap = QSpinBox()
        self.spin_gap.setRange(0, 10)
        self.spin_gap.setValue(int(self.settings.get("gap", 2)))
        
        form_print.addRow("Imprimante :", self.combo_printers)
        form_print.addRow("Largeur (mm) :", self.spin_width)
        form_print.addRow("Hauteur (mm) :", self.spin_height)
        form_print.addRow("Espacement (mm) :", self.spin_gap)
        grp_print.setLayout(form_print)
        layout.addWidget(grp_print)
        
        btn_test_print = QPushButton("🖨️ Imprimer une étiquette test")
        btn_test_print.clicked.connect(self.test_print_label)
        layout.addWidget(btn_test_print)
        layout.addStretch()

    def _setup_system_tab(self):
        layout = QVBoxLayout(self.tab_system)
        grp_sys = QGroupBox("Variables d'environnement")
        form_sys = QFormLayout()
        
        self.combo_env = QComboBox()
        self.combo_env.addItems(["development", "production"])
        self.combo_env.setCurrentText(self.settings.get("flask_env", "development"))
        self.txt_secret = QLineEdit(str(self.settings.get("secret_key", "")))
        self.spin_max_len = QSpinBox()
        self.spin_max_len.setRange(1024, 99999999)
        self.spin_max_len.setValue(int(self.settings.get("max_content_length", 16777216)))
        
        form_sys.addRow("FLASK_ENV :", self.combo_env)
        form_sys.addRow("SECRET_KEY :", self.txt_secret)
        form_sys.addRow("MAX_CONTENT_LENGTH :", self.spin_max_len)
        grp_sys.setLayout(form_sys)
        layout.addWidget(grp_sys)
        layout.addStretch()

    # --- Fonctions Auto-Backup ---
    
    def add_backup_path(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier de sauvegarde")
        if folder_path:
            existing_paths = [self.list_backup_paths.item(i).text() for i in range(self.list_backup_paths.count())]
            if folder_path not in existing_paths:
                self.list_backup_paths.addItem(folder_path)

    def remove_backup_path(self):
        selected_items = self.list_backup_paths.selectedItems()
        if not selected_items: return
        for item in selected_items:
            self.list_backup_paths.takeItem(self.list_backup_paths.row(item))

    def force_manual_backup(self):
        paths = [self.list_backup_paths.item(i).text() for i in range(self.list_backup_paths.count())]
        if not paths:
            QMessageBox.warning(self, "Attention", "Veuillez ajouter au moins un dossier de destination.")
            return
            
        password = self.txt_auto_pwd.text()
        
        if hasattr(self.data_manager.db, 'create_multi_backup'):
            success, msg = self.data_manager.db.create_multi_backup(paths, password, is_auto=False)
            if success:
                QMessageBox.information(self, "Succès", f"Sauvegarde forcée terminée !\n{msg}")
            else:
                QMessageBox.critical(self, "Erreur", f"Échec de la sauvegarde forcée :\n{msg}")
        else:
            QMessageBox.critical(self, "Erreur", "La fonction 'create_multi_backup' est introuvable.")

    # --- Fonctions Générales (Save & Load) ---
    def load_settings(self):
        """قراءة الإعدادات مع معالجة الأخطاء لتجنب فقدان البيانات السابقة"""
        logging.info(f"📁 Tentative de lecture du fichier : {CONFIG_FILE}")
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.settings.update(data)
                logging.info("✅ Paramètres chargés avec succès.")
            except Exception as e:
                logging.error(f"❌ Erreur de lecture du JSON: {e}")
                QMessageBox.warning(self, "Erreur Lecture", 
                                    f"Impossible de lire vos anciens paramètres.\nLe fichier {CONFIG_FILE} est peut-être corrompu.\n{e}")
        else:
            logging.warning("⚠️ Fichier config.json introuvable, utilisation des paramètres par défaut.")

    def load_database_settings_from_env(self):
        if not os.path.exists(ENV_FILE):
            return
        try:
            env_values = dotenv_values(ENV_FILE)
            env_mapping = {
                "DB_HOST": "db_host",
                "DB_USER": "db_user",
                "DB_PASSWORD": "db_password",
                "DB_NAME": "db_name",
            }
            for env_key, setting_key in env_mapping.items():
                if env_values.get(env_key) is not None:
                    self.settings[setting_key] = env_values[env_key]

            if env_values.get("DB_PORT") is not None:
                self.settings["db_port"] = int(env_values["DB_PORT"])
        except Exception as e:
            logging.warning(f"Impossible de lire les parametres DB depuis .env: {e}")

    def save_settings(self):
        # 1. جلب إعدادات PDF أولاً (الخطوة الحاسمة لعدم مسح البيانات الجديدة)
        if hasattr(self, 'tab_pdf_config'):
            try:
                pdf_updates = self.tab_pdf_config.get_updated_settings()
                self.settings.update(pdf_updates)
            except Exception as e:
                logging.error(f"Erreur avec tab_pdf_config: {e}")

        # 2. قراءة الإعدادات من الواجهة وتخزينها (تُكتب أخيراً لتكون لها الأولوية المطلقة)
        self.settings["lab_name"] = self.txt_lab_name.text()
        self.settings["lab_address"] = self.txt_lab_address.text()
        self.settings["expiry_warning_days"] = self.spin_expiry.value()
        self.settings["low_stock_threshold"] = self.spin_stock.value()
        
        self.settings["db_host"] = self.txt_db_host.text()
        self.settings["db_port"] = self.spin_db_port.value()
        self.settings["db_user"] = self.txt_db_user.text()
        self.settings["db_password"] = self.txt_db_pass.text()
        self.settings["db_name"] = self.txt_db_name.text()
        
        self.settings["selected_printer"] = self.combo_printers.currentText()
        self.settings["label_width"] = self.spin_width.value()
        self.settings["label_height"] = self.spin_height.value()
        self.settings["gap"] = self.spin_gap.value()
        
        self.settings["flask_env"] = self.combo_env.currentText()
        self.settings["secret_key"] = self.txt_secret.text()
        self.settings["max_content_length"] = self.spin_max_len.value()
        
        # --- إعدادات الحفظ التلقائي ---
        self.settings["auto_backup_enabled"] = self.chk_auto_backup.isChecked()
        self.settings["auto_backup_interval"] = self.spin_auto_interval.value()
        self.settings["auto_backup_password"] = self.txt_auto_pwd.text()
        self.settings["backup_paths"] = [self.list_backup_paths.item(i).text() for i in range(self.list_backup_paths.count())]
        
        # 3. الكتابة المباشرة في ملف config.json
        try:
            logging.info(f"💾 Sauvegarde vers : {CONFIG_FILE}")
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
                
            if hasattr(self.data_manager, 'printer'):
                self.data_manager.printer.reload_settings()
                
            # إعادة تشغيل مؤقت الحفظ التلقائي في الخلفية بالإعدادات الجديدة
            try:
                main_window = self.window()
                auto_backup_thread = getattr(main_window, 'auto_backup_thread', None)
                if auto_backup_thread:
                    auto_backup_thread.stop()
                    auto_backup_thread.wait(500)
                    auto_backup_thread.start()
            except Exception as thread_err:
                logging.error(f"Erreur thread: {thread_err}")

            # رسالة تشخيصية: ستظهر لك بالضبط ما تم كتابته داخل الملف لتكون مطمئناً
            msg = (
                f"Paramètres enregistrés avec succès dans :\n{CONFIG_FILE}\n\n"
                f"Auto-Backup Actif : {self.settings['auto_backup_enabled']}\n"
                f"Intervalle : {self.settings['auto_backup_interval']} min\n"
                f"Dossiers : {len(self.settings['backup_paths'])}"
            )
            QMessageBox.information(self, "Succès", msg)
            
        except Exception as e:
            logging.error(f"❌ Échec de la sauvegarde: {e}")
            QMessageBox.critical(self, "Erreur", f"Échec de l'enregistrement :\n{e}")

    # Rest of the functions remain the same
    def export_to_env_file(self):
        try:
            schema_check = "false"
            if os.path.exists(ENV_FILE):
                with open(ENV_FILE, 'r', encoding='utf-8') as existing_env:
                    for line in existing_env:
                        if line.strip().startswith("DB_SCHEMA_CHECK_ON_STARTUP="):
                            schema_check = line.strip().split("=", 1)[1] or "false"
                            break

            with open(ENV_FILE, 'w', encoding='utf-8') as f:
                f.write(f"FLASK_ENV={self.combo_env.currentText()}\n")
                f.write(f"SECRET_KEY={self.txt_secret.text()}\n")
                f.write(f"MAX_CONTENT_LENGTH={self.spin_max_len.value()}\n\n")
                f.write(f"DB_HOST={self.txt_db_host.text()}\n")
                f.write(f"DB_PORT={self.spin_db_port.value()}\n")
                f.write(f"DB_USER={self.txt_db_user.text()}\n")
                f.write(f"DB_PASSWORD={self.txt_db_pass.text()}\n")
                f.write(f"DB_NAME={self.txt_db_name.text()}\n")
                f.write(f"DB_SCHEMA_CHECK_ON_STARTUP={schema_check}\n")
            QMessageBox.information(self, "Succès", "Fichier .env exporté avec succès.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))

    def set_connection_error(self, error_text):
        if not hasattr(self, 'grp_connection_error'):
            return
        self.txt_connection_error.setPlainText(str(error_text))
        self.grp_connection_error.setVisible(True)

    def test_db_connection(self):
        logging.info(f"🚀 Tentative de connexion à {self.txt_db_host.text()}...")
        try:
            conn = mysql.connector.connect(
                host=self.txt_db_host.text(),
                port=self.spin_db_port.value(),
                user=self.txt_db_user.text(),
                password=self.txt_db_pass.text(),
                database=self.txt_db_name.text(),
                use_pure=True,
                auth_plugin='mysql_native_password',
                connection_timeout=5
            )
            if conn.is_connected():
                cursor = conn.cursor()
                cursor.execute("SELECT VERSION()")
                version = cursor.fetchone()[0]
                msg = "✅ Connexion réussie ! Authentification validée."
                msg = f"{msg}\nVersion MySQL: {version}"
                logging.info(msg)
                QMessageBox.information(self, "Succès", msg)
                conn.close()
        except mysql.connector.Error as err:
            error_msg = f"❌ Erreur base de données : {err.msg} (Code : {err.errno})"
            logging.error(error_msg)
            self.set_connection_error(error_msg)
            QMessageBox.critical(self, "Échec", error_msg)
        except Exception as e:
            error_msg = f"⚠️ Erreur inattendue : {str(e)}"
            logging.error(error_msg)
            self.set_connection_error(error_msg)
            QMessageBox.critical(self, "Échec", error_msg)
    
    def perform_backup(self):
        filename = f"sauvegarde_excel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer la sauvegarde (Excel)", filename, "Fichiers ZIP (*.zip)")
        if path:
            if hasattr(self.data_manager.db, 'backup_database_excel'):
                success, msg = self.data_manager.db.backup_database_excel(path)
                if success: QMessageBox.information(self, "Terminé", "La sauvegarde Excel a été créée")
                else: QMessageBox.critical(self, "Erreur", msg)
            else:
                QMessageBox.critical(self, "Erreur", "La fonction de sauvegarde Excel est introuvable.")

    def perform_restore(self):
        confirm = QMessageBox.warning(
            self, 
            "Attention - Restauration", 
            "Toutes les données actuelles seront supprimées et remplaçées par celles du fichier de sauvegarde ! \n\nÊtes-vous sûr ?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            path, _ = QFileDialog.getOpenFileName(self, "Sélectionner le fichier de sauvegarde", "", "Fichiers ZIP (*.zip)")
            if path:
                db_ref = self.data_manager.db
                password = None

                try:
                    if hasattr(db_ref, 'backup_zip_requires_password') and db_ref.backup_zip_requires_password(path):
                        password, ok = QInputDialog.getText(
                            self,
                            "Mot de passe sauvegarde",
                            "Cette sauvegarde est protégée. Entrez le mot de passe ZIP :",
                            QLineEdit.EchoMode.Password,
                            str(self.settings.get("auto_backup_password", ""))
                        )
                        if not ok:
                            return
                except Exception as e:
                    logging.warning(f"Impossible de vérifier le mot de passe de sauvegarde: {e}")

                if hasattr(db_ref, 'restore_database_backup'):
                    success, msg = db_ref.restore_database_backup(path, password=password)
                    if not success and str(msg).startswith("BACKUP_PASSWORD_REQUIRED"):
                        QMessageBox.warning(self, "Mot de passe requis", "Cette sauvegarde est chiffrée. Veuillez entrer le mot de passe.")
                        return
                    if not success and str(msg).startswith("BACKUP_BAD_PASSWORD"):
                        QMessageBox.critical(self, "Mot de passe incorrect", "Le mot de passe de la sauvegarde est incorrect.")
                        return
                    if success: QMessageBox.information(self, "Terminé", "Restauration terminée avec succès.")
                    else: QMessageBox.critical(self, "Échec", msg)
                elif hasattr(db_ref, 'restore_database_excel'):
                    success, msg = db_ref.restore_database_excel(path, password=password)
                    if success: QMessageBox.information(self, "Terminé", "Restauration terminée avec succès.")
                    else: QMessageBox.critical(self, "Échec", msg)
                else:
                    QMessageBox.critical(self, "Erreur", "La fonction de restauration est introuvable.")

    def perform_archive_logs(self):
        days, ok = QInputDialog.getInt(self, "Archiver les historiques", 
                                       "Archiver les enregistrements plus anciens que (jours) :", 
                                       365, 30, 3650)
        if ok:
            filename = f"logs_archive_{datetime.now().strftime('%Y%m%d')}.zip"
            path, _ = QFileDialog.getSaveFileName(self, "Enregistrer l'archive", filename, "Fichiers ZIP (*.zip)")
            if path:
                if hasattr(self.data_manager.db, 'export_and_purge_tables'):
                    success, msg = self.data_manager.db.export_and_purge_tables(path, days)
                    if success: QMessageBox.information(self, "Terminé", msg)
                    else: QMessageBox.information(self, "Information", msg)

    def toggle_archive_view(self):
        db_ref = self.data_manager.db
        if not getattr(db_ref, 'is_archive_mode', False):
            path, _ = QFileDialog.getOpenFileName(self, "Sélectionner le fichier archive pour aperçu", "", "Fichiers ZIP (*.zip)")
            if path:
                if hasattr(db_ref, 'activate_archive_view'):
                    success, msg = db_ref.activate_archive_view(path)
                    if success:
                        QMessageBox.information(self, "Succès", "Mode archive activé. Les données affichées sont désormais celles de l'archive.")
                        self._update_view_mode_style(True)
                    else:
                        QMessageBox.critical(self, "Erreur", msg)
        else:
            if hasattr(db_ref, 'deactivate_archive_view'):
                success, msg = db_ref.deactivate_archive_view()
                QMessageBox.information(self, "Terminé", msg)
                self._update_view_mode_style(False)

    def _update_view_mode_style(self, active):
        if active:
            self.lbl_mode_status.setText("⚠️ Mode actuel : Aperçu archive (lecture seule)")
            self.lbl_mode_status.setStyleSheet("color: red; font-weight: bold; font-size: 16px;")
            self.btn_toggle_view.setText("❌ Fermer l'archive et revenir")
            self.btn_toggle_view.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
            self.grp_view_mode.setStyleSheet("QGroupBox { border: 2px solid red; background-color: #fadbd8; }")
        else:
            self.lbl_mode_status.setText("✅ Mode actuel : Données en direct")
            self.lbl_mode_status.setStyleSheet("color: green; font-weight: bold; font-size: 14px;")
            self.btn_toggle_view.setText("📂 Ouvrir un fichier archive pour aperçu")
            self.btn_toggle_view.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold;")
            self.grp_view_mode.setStyleSheet("QGroupBox { border: 1px solid orange; margin-top: 10px; }")

    def test_print_label(self):
        self.save_settings() 
        if hasattr(self.data_manager, 'printer'):
            success, msg = self.data_manager.printer.print_label(
                "Réactif Test", "1234567890", "LOT-01", "2025-12-31"
            )
            if success: QMessageBox.information(self, "Succès", msg)
            else: QMessageBox.warning(self, "Erreur", msg)
