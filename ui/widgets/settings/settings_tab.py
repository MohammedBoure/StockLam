# ui/widgets/settings/settings_tab.py

import json
import os
import logging
import win32print 
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QGroupBox, QFormLayout, 
                               QSpinBox, QMessageBox, QFileDialog, QTabWidget,
                               QComboBox, QInputDialog)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
import mysql.connector
import sys

from .pdf_config_tab import PdfConfigWidget # تأكد من المسار الصحيح

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def get_external_path(filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(os.path.dirname(sys.executable), filename)
    return os.path.join(os.path.abspath("."), filename)

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
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        
        # 1. Général + Gestion des données
        self.tab_general = QWidget()
        self._setup_general_tab()
        self.tabs.addTab(self.tab_general, "🏢 Général / Gestion des données")
        
        # 2. Base de données
        self.tab_db = QWidget()
        self._setup_database_tab()
        self.tabs.addTab(self.tab_db, "🗄️ Base de données")
        
        # 3. Imprimante
        self.tab_printer = QWidget()
        self._setup_printer_tab()
        self.tabs.addTab(self.tab_printer, "🖨️ Imprimante")
        
        # 4. Système
        self.tab_system = QWidget()
        self._setup_system_tab()
        self.tabs.addTab(self.tab_system, "⚙️ Système")
        
        main_layout.addWidget(self.tabs)

        self.tab_pdf_config = PdfConfigWidget(self.settings)
        self.tabs.addTab(self.tab_pdf_config, "🎨 Configuration PDF")

        # Boutons du bas
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
        layout = QVBoxLayout(self.tab_general)
        
        # A) Informations du laboratoire
        grp_info = QGroupBox("📋 Informations du laboratoire")
        form_info = QFormLayout()
        self.txt_lab_name = QLineEdit(self.settings["lab_name"])
        self.txt_lab_address = QLineEdit(self.settings["lab_address"])
        form_info.addRow("Nom du laboratoire :", self.txt_lab_name)
        form_info.addRow("Adresse :", self.txt_lab_address)
        grp_info.setLayout(form_info)
        layout.addWidget(grp_info)

        # ---------------------------------------------------------
        # B) Paramètres d'alerte (الجزء المفقود الذي سبب الخطأ)
        # ---------------------------------------------------------
        grp_alerts = QGroupBox("⚠️ Paramètres d'alerte & Seuils")
        form_alerts = QFormLayout()

        # 1. SpinBox لانتهاء الصلاحية
        self.spin_expiry = QSpinBox()
        self.spin_expiry.setRange(1, 3650)
        self.spin_expiry.setValue(int(self.settings.get("expiry_warning_days", 30)))
        self.spin_expiry.setSuffix(" jours")

        # 2. SpinBox لنقص المخزون
        self.spin_stock = QSpinBox()
        self.spin_stock.setRange(1, 1000)
        self.spin_stock.setValue(int(self.settings.get("low_stock_threshold", 5)))
        self.spin_stock.setSuffix(" unités")

        form_alerts.addRow("Alerte péremption (avant) :", self.spin_expiry)
        form_alerts.addRow("Seuil stock critique :", self.spin_stock)
        
        grp_alerts.setLayout(form_alerts)
        layout.addWidget(grp_alerts)
        # ---------------------------------------------------------
        
        # C) Gestion des données et archives
        grp_data = QGroupBox("💾 Gestion des données & Archives")
        data_layout = QVBoxLayout()
        
        # Ligne 1 : Sauvegarde et restauration complète
        row1 = QHBoxLayout()
        btn_backup = QPushButton("📦 Sauvegarde complète de la base")
        btn_backup.setToolTip("Exporter toute la base de données en ZIP")
        btn_backup.clicked.connect(self.perform_backup)
        
        btn_restore = QPushButton("♻️ Restauration complète")
        btn_restore.setToolTip("Restaurer la base et supprimer les données actuelles !")
        btn_restore.setStyleSheet("color: #c0392b;")
        btn_restore.clicked.connect(self.perform_restore)
        
        row1.addWidget(btn_backup)
        row1.addWidget(btn_restore)
        data_layout.addLayout(row1)
        
        # Ligne 2 : Archivage des historiques uniquement
        row2 = QHBoxLayout()
        btn_archive = QPushButton("🧹 Archiver les historiques")
        btn_archive.setToolTip("Déplacer les anciens enregistrements vers l'archive pour accélérer le système")
        btn_archive.clicked.connect(self.perform_archive_logs)
        row2.addWidget(btn_archive)
        data_layout.addLayout(row2)
        
        # Ligne 3 : Mode aperçu archive
        self.grp_view_mode = QGroupBox("👁️ Mode aperçu archive (lecture seule)")
        self.grp_view_mode.setStyleSheet("QGroupBox { border: 1px solid orange; margin-top: 10px; }")
        view_layout = QVBoxLayout()
        
        self.lbl_mode_status = QLabel("Mode actuel : ✅ Données en direct")
        self.lbl_mode_status.setStyleSheet("color: green; font-weight: bold; font-size: 14px;")
        self.lbl_mode_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.btn_toggle_view = QPushButton("📂 Ouvrir un fichier archive pour aperçu")
        self.btn_toggle_view.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold;")
        self.btn_toggle_view.clicked.connect(self.toggle_archive_view)
        
        view_layout.addWidget(self.lbl_mode_status)
        view_layout.addWidget(self.btn_toggle_view)
        self.grp_view_mode.setLayout(view_layout)
        
        data_layout.addWidget(self.grp_view_mode)
        
        grp_data.setLayout(data_layout)
        layout.addWidget(grp_data)
        
        layout.addStretch()
    def _setup_database_tab(self):
        layout = QVBoxLayout(self.tab_db)
        grp_conn = QGroupBox("Connexion MySQL")
        form_conn = QFormLayout()
        
        self.txt_db_host = QLineEdit(self.settings["db_host"])
        self.spin_db_port = QSpinBox()
        self.spin_db_port.setRange(1, 65535)
        self.spin_db_port.setValue(int(self.settings["db_port"]))
        self.txt_db_user = QLineEdit(self.settings["db_user"])
        self.txt_db_pass = QLineEdit(self.settings["db_password"])
        self.txt_db_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_db_name = QLineEdit(self.settings["db_name"])
        
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
        self.spin_width.setValue(int(self.settings["label_width"]))
        
        self.spin_height = QSpinBox()
        self.spin_height.setRange(10, 150)
        self.spin_height.setValue(int(self.settings["label_height"]))
        
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
        self.combo_env.setCurrentText(self.settings["flask_env"])
        self.txt_secret = QLineEdit(self.settings["secret_key"])
        self.spin_max_len = QSpinBox()
        self.spin_max_len.setRange(1024, 99999999)
        self.spin_max_len.setValue(int(self.settings["max_content_length"]))
        
        form_sys.addRow("FLASK_ENV :", self.combo_env)
        form_sys.addRow("SECRET_KEY :", self.txt_secret)
        form_sys.addRow("MAX_CONTENT_LENGTH :", self.spin_max_len)
        grp_sys.setLayout(form_sys)
        layout.addWidget(grp_sys)
        layout.addStretch()

    # --- Fonctions ---
    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.settings.update(data)
            except: pass

    def save_settings(self):
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
        pdf_updates = self.tab_pdf_config.get_updated_settings()
        self.settings.update(pdf_updates)
        
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
            if hasattr(self.data_manager, 'printer'):
                self.data_manager.printer.reload_settings()
            QMessageBox.information(self, "Succès", "Paramètres enregistrés avec succès.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec de l'enregistrement des paramètres : {e}")

    def export_to_env_file(self):
        try:
            with open(ENV_FILE, 'w', encoding='utf-8') as f:
                f.write(f"FLASK_ENV={self.combo_env.currentText()}\n")
                f.write(f"SECRET_KEY={self.txt_secret.text()}\n")
                f.write(f"MAX_CONTENT_LENGTH={self.spin_max_len.value()}\n\n")
                f.write(f"DB_HOST={self.txt_db_host.text()}\n")
                f.write(f"DB_PORT={self.spin_db_port.value()}\n")
                f.write(f"DB_USER={self.txt_db_user.text()}\n")
                f.write(f"DB_PASSWORD={self.txt_db_pass.text()}\n")
                f.write(f"DB_NAME={self.txt_db_name.text()}\n")
            QMessageBox.information(self, "Succès", "Fichier .env exporté avec succès.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))

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
                auth_plugin='mysql_native_password'
            )
            
            if conn.is_connected():
                msg = "✅ Connexion réussie ! Authentification validée."
                logging.info(msg)
                QMessageBox.information(self, "Succès", msg)
                conn.close()
                
        except mysql.connector.Error as err:
            error_msg = f"❌ Erreur base de données : {err.msg} (Code : {err.errno})"
            logging.error(error_msg)
            QMessageBox.critical(self, "Échec", error_msg)
        except Exception as e:
            error_msg = f"⚠️ Erreur inattendue : {str(e)}"
            logging.error(error_msg)
            QMessageBox.critical(self, "Échec", error_msg)
    
    def perform_backup(self):
        # تغيير الاسم الافتراضي للملف ليشير إلى Excel
        filename = f"sauvegarde_excel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer la sauvegarde (Excel)", filename, "Fichiers ZIP (*.zip)")
        
        if path:
            # التأكد من استدعاء الدالة الجديدة backup_database_excel
            if hasattr(self.data_manager.db, 'backup_database_excel'):
                success, msg = self.data_manager.db.backup_database_excel(path)
                if success: 
                    QMessageBox.information(self, "Terminé", "La sauvegarde Excel a été créée")
                else: 
                    QMessageBox.critical(self, "Erreur", msg)
            else:
                QMessageBox.critical(self, "Erreur", "La fonction de sauvegarde Excel est introuvable.")

    def perform_restore(self):
        confirm = QMessageBox.warning(
            self, 
            "Attention - Restauration", 
            "Toutes les données actuelles seront supprimées و remplaçées par celles du fichier Excel ! \n\nÊtes-vous sûr ?", 
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            path, _ = QFileDialog.getOpenFileName(self, "Sélectionner le fichier de sauvegarde Excel", "", "Fichiers ZIP (*.zip)")
            if path:
                # التأكد من استدعاء الدالة الجديدة restore_database_excel
                if hasattr(self.data_manager.db, 'restore_database_excel'):
                    success, msg = self.data_manager.db.restore_database_excel(path)
                    if success: 
                        QMessageBox.information(self, "Terminé", "Restauration terminée avec succès.")
                    else: 
                        QMessageBox.critical(self, "Échec", msg)
                else:
                    QMessageBox.critical(self, "Erreur", "La fonction de restauration Excel est introuvable.")

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
        self.save_settings()  # Enregistre d'abord les nouveaux paramètres imprimante
        if hasattr(self.data_manager, 'printer'):
            success, msg = self.data_manager.printer.print_label(
                "Réactif Test", "1234567890", "LOT-01", "2025-12-31"
            )
            if success: 
                QMessageBox.information(self, "Succès", msg)
            else: 
                QMessageBox.warning(self, "Erreur", msg)