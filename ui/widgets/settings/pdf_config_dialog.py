from PySide6.QtWidgets import QDialog, QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout

from .pdf_config_tab import PdfConfigWidget
from .local_settings import LocalSettingsStore


class PdfConfigDialog(QDialog):
    """Full-screen PDF settings workspace with explicit local/DB operations."""

    def __init__(
        self,
        data_manager,
        current_user=None,
        can_manage_stamps=None,
        local_store=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Configuration PDF locale")
        self.setMinimumSize(1250, 780)
        self.resize(1500, 900)
        self.local_store = local_store or LocalSettingsStore(current_user)
        self.config_widget = PdfConfigWidget(
            data_manager,
            current_user=current_user,
            can_manage_stamps=can_manage_stamps,
            local_store=self.local_store,
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self.config_widget, stretch=1)

        actions = QHBoxLayout()
        self.btn_load_db = QPushButton("Charger un aperçu depuis la base de données")
        self.btn_save_local = QPushButton("Enregistrer localement pour cet utilisateur")
        self.btn_close = QPushButton("Fermer")
        self.btn_load_db.setToolTip(
            "Charge les paramètres PDF et les cachets sans modifier les fichiers locaux avant l'enregistrement."
        )
        self.btn_save_local.setStyleSheet(
            "background-color: #27ae60; color: white; font-weight: bold; padding: 8px;"
        )
        actions.addWidget(self.btn_load_db)
        actions.addStretch()
        actions.addWidget(self.btn_save_local)
        actions.addWidget(self.btn_close)
        layout.addLayout(actions)

        self.btn_load_db.clicked.connect(self.load_from_database)
        self.btn_save_local.clicked.connect(self.save_local)
        self.btn_close.clicked.connect(self.close)

    def load_from_database(self):
        if self.config_widget.load_from_database():
            QMessageBox.information(
                self,
                "Configuration PDF",
                "Les réglages ont été chargés en mémoire depuis la base de données. "
                "Cliquez sur « Enregistrer localement » pour les conserver sur cet appareil.",
            )

    def save_local(self):
        try:
            self.config_widget.save_settings()
            QMessageBox.information(
                self,
                "Configuration PDF",
                "Les réglages PDF et les cachets ont été enregistrés localement.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Configuration PDF", str(exc))
