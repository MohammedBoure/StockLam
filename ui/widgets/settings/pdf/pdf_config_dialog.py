from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabBar,
    QVBoxLayout,
)

from .pdf_config_tab import PdfConfigWidget
from ..local_settings import LocalSettingsStore


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
        self.setWindowTitle("Configuration PDF")
        self.setMinimumSize(1250, 780)
        self.setWindowState(Qt.WindowMaximized)
        self.local_store = local_store or LocalSettingsStore(current_user)
        self.config_widget = PdfConfigWidget(
            data_manager,
            current_user=current_user,
            can_manage_stamps=can_manage_stamps,
            local_store=self.local_store,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_top_bar())
        layout.addWidget(self.config_widget, stretch=1)
        layout.addWidget(self._build_action_bar())

        self.btn_back.clicked.connect(self.reject)
        self.btn_load_db.clicked.connect(self.load_from_database)
        self.btn_save_local.clicked.connect(self.save_local)
        self.btn_save_db.clicked.connect(self.save_to_database)

        manager = getattr(data_manager, "company_settings", None)
        if manager is None or not hasattr(manager, "update_settings"):
            self.btn_save_db.setEnabled(False)
            self.btn_save_db.setToolTip("La base de données PDF n'est pas disponible.")

    def _build_top_bar(self):
        top_bar = QFrame()
        top_bar.setObjectName("pdfTopBar")
        
        row = QHBoxLayout(top_bar)
        row.setContentsMargins(12, 6, 12, 6)
        row.setSpacing(10)

        self.btn_back = QPushButton("← Retour")
        self.btn_back.setMinimumHeight(38)
        
        title = QLabel("Configuration PDF")

        self.top_tabs = QTabBar()
        self.top_tabs.setExpanding(True)
        self.top_tabs.setElideMode(Qt.ElideRight)
        self.top_tabs.setUsesScrollButtons(True)
        for index in range(self.config_widget.tabs.count()):
            self.top_tabs.addTab(self.config_widget.tabs.tabText(index))
        self.top_tabs.currentChanged.connect(self._show_pdf_tab)
        self.config_widget.tabs.currentChanged.connect(self._show_top_tab)
        self.top_tabs.setCurrentIndex(self.config_widget.tabs.currentIndex())

        row.addWidget(self.btn_back)
        row.addWidget(title)
        row.addWidget(self.top_tabs, stretch=1)
        return top_bar

    def _build_action_bar(self):
        action_bar = QFrame()
        action_bar.setStyleSheet("background: #f5f7f9; border-top: 1px solid #ccd6dd;")
        actions = QHBoxLayout(action_bar)
        actions.setContentsMargins(18, 10, 18, 10)
        actions.setSpacing(10)

        self.btn_load_db = QPushButton("Charger depuis la base de données")
        self.btn_save_local = QPushButton("Enregistrer localement")
        self.btn_save_db = QPushButton("Enregistrer dans la base de données")
        self.btn_load_db.setToolTip(
            "Charge les réglages PDF depuis la base sans modifier les fichiers locaux."
        )
        self.btn_save_local.setToolTip(
            "Enregistre les réglages PDF et les cachets pour cet utilisateur sur cet appareil."
        )
        self.btn_save_db.setToolTip(
            "Enregistre le modèle PDF et le bandeau partagé dans la base de données."
        )
        self.btn_save_local.setStyleSheet(
            "background-color: #27ae60; color: white; font-weight: bold; padding: 9px 14px;"
        )
        self.btn_save_db.setStyleSheet(
            "background-color: #2877ad; color: white; font-weight: bold; padding: 9px 14px;"
        )

        actions.addWidget(self.btn_load_db)
        actions.addStretch()
        actions.addWidget(self.btn_save_local)
        actions.addWidget(self.btn_save_db)
        return action_bar

    def _show_pdf_tab(self, index):
        if index >= 0 and self.config_widget.tabs.currentIndex() != index:
            self.config_widget.tabs.setCurrentIndex(index)

    def _show_top_tab(self, index):
        if index >= 0 and self.top_tabs.currentIndex() != index:
            self.top_tabs.setCurrentIndex(index)

    def load_from_database(self):
        if self.config_widget.load_from_database():
            QMessageBox.information(
                self,
                "Configuration PDF",
                "Les réglages ont été chargés en mémoire depuis la base de données. "
                "Utilisez « Enregistrer localement » ou « Enregistrer dans la base de données » selon votre besoin.",
            )

    def save_local(self):
        try:
            self.config_widget.save_settings()
            QMessageBox.information(
                self,
                "Configuration PDF",
                "Les réglages PDF et les cachets ont été enregistrés localement pour cet utilisateur.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Configuration PDF", str(exc))

    def save_to_database(self):
        try:
            self.config_widget.save_to_database()
            QMessageBox.information(
                self,
                "Configuration PDF",
                "Le modèle PDF et le bandeau ont été enregistrés dans la base de données. "
                "Les cachets locaux restent propres à cet utilisateur.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Configuration PDF", str(exc))
