import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, 
    QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QMessageBox, 
    QFrame, QCompleter, QTabWidget, QAbstractItemView, QMenu, QDialog, QDialogButtonBox
)
from PySide6.QtCore import Qt, QDate, QStringListModel, Signal
from PySide6.QtGui import QColor, QFont, QBrush, QAction
import qtawesome as qta

from ui.widgets.inventory.dialogs import BarcodeLineEdit, NumericSpinBox
from .CreditNoteForm import CreditNoteForm
from .CreditNoteList import CreditNoteList


class CreditNoteTab(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.manager = data_manager
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        
        self.tabs.tabBar().hide() 
        
        self.tabs.setStyleSheet("QTabWidget::pane { border: 0; }")
        
        self.form_tab = CreditNoteForm(data_manager)
        self.list_tab = CreditNoteList(data_manager)
        
        self.tabs.addTab(self.list_tab, "📜 Avoirs")  # Index 0
        self.tabs.addTab(self.form_tab, "📝 Saisie Avoir") # Index 1
        
        self.list_tab.request_edit.connect(self.handle_edit_request)
        self.list_tab.request_new.connect(self.handle_new_request)
        self.form_tab.saved_successfully.connect(self.on_save_success)
        
        self.form_tab.request_back.connect(self.on_back_request)
        
        self.tabs.currentChanged.connect(self.on_tab_change)
        layout.addWidget(self.tabs)

    def on_back_request(self):
        self.tabs.setCurrentIndex(0)

    def on_tab_change(self, index):
        if index == 0: self.list_tab.load_data()

    def refresh_history(self):
        self.list_tab.load_data()

    def handle_edit_request(self, credit_note_id):
        self.tabs.setCurrentIndex(1) 
        self.form_tab.load_for_edit(credit_note_id)

    def handle_new_request(self):
        self.form_tab.reset_form()
        self.tabs.setCurrentIndex(1)

    def on_save_success(self):
        self.list_tab.load_data()
        self.tabs.setCurrentIndex(0) 

    def populate_from_reception(self, data):
        self.tabs.setCurrentIndex(1) 
        self.form_tab.populate_from_reception(data)