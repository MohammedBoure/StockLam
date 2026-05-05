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

from database.system_logger import active_user_id




# ==============================================================================
# 3. قائمة العرض (List)
# ==============================================================================
class CreditNoteList(QWidget):
    request_edit = Signal(int) 
    request_new = Signal() # إشارة جديدة لطلب إنشاء جديد

    def __init__(self, data_manager):
        super().__init__()
        self.manager = data_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # --- شريط الفلترة العلوي ---
        filter_group = QGroupBox("🔍 Recherche et Filtres")
        filter_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #ccc; border-radius: 5px; margin-top: 5px; }")
        filter_layout = QHBoxLayout(filter_group)
        
        self.date_from = QDateEdit(QDate.currentDate().addMonths(-1)) 
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        
        btn_search = QPushButton("Rechercher")
        btn_search.setIcon(qta.icon("fa5s.search"))
        btn_search.setStyleSheet("background-color: #2980b9; color: white; padding: 5px 15px;")
        btn_search.clicked.connect(self.load_data)

        # زر إنشاء جديد
        btn_new = QPushButton("➕ Nouveau Avoir")
        btn_new.setStyleSheet("background-color: #27ae60; color: white; padding: 5px 15px; font-weight: bold;")
        btn_new.clicked.connect(self.request_new.emit)

        filter_layout.addWidget(QLabel("Du:"))
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(QLabel("Au:"))
        filter_layout.addWidget(self.date_to)
        filter_layout.addWidget(btn_search)
        filter_layout.addStretch() 
        filter_layout.addWidget(btn_new) # إضافة الزر هنا
        
        layout.addWidget(filter_group)

        self.table = QTableWidget()
        cols = ["ID", "Réf. Avoir", "Fournisseur", "Date", "Type", "Montant TTC"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setColumnHidden(0, True) 
        
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.doubleClicked.connect(self.trigger_edit)
        
        layout.addWidget(self.table)
        
        self.load_data()

    def show_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid(): return

        menu = QMenu(self)
        action_edit = QAction("Modifier", self)
        action_edit.triggered.connect(self.trigger_edit)
        menu.addAction(action_edit)

        action_delete = QAction(" Supprimer", self)
        action_delete.triggered.connect(self.trigger_delete)
        menu.addAction(action_delete)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def get_selected_id(self):
        row = self.table.currentRow()
        if row < 0: return None
        item = self.table.item(row, 0)
        return int(item.text()) if item else None

    def get_current_user_id(self):
        user_id = active_user_id.get()
        if user_id:
            return user_id

        parent_widget = self.parent()
        while parent_widget:
            current_user = getattr(parent_widget, 'current_user', None)
            if isinstance(current_user, dict):
                return current_user.get('User_ID') or current_user.get('id')
            parent_widget = parent_widget.parent()
        return None

    def trigger_edit(self):
        cn_id = self.get_selected_id()
        if cn_id:
            self.request_edit.emit(cn_id)

    def trigger_delete(self):
        cn_id = self.get_selected_id()
        if not cn_id: return
        
        reply = QMessageBox.question(
            self, "Confirmation", 
            "Voulez-vous vraiment supprimer cet Avoir ?\n\n"
            "⚠️ Attention : Si c'est un retour marchandise, le stock sera restauré.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if hasattr(self.manager.credit_notes, 'delete_credit_note'):
                success, msg = self.manager.credit_notes.delete_credit_note(
                    cn_id, user_id=self.get_current_user_id()
                )
                if success:
                    self.load_data()
                else:
                    QMessageBox.critical(self, "Erreur", msg)

    def load_data(self):
        try:
            self.table.setRowCount(0)
            d_start = self.date_from.date().toString("yyyy-MM-dd")
            d_end = self.date_to.date().toString("yyyy-MM-dd")
            
            notes = []
            if hasattr(self.manager.credit_notes, 'get_credit_notes_by_date'):
                notes = self.manager.credit_notes.get_credit_notes_by_date(d_start, d_end)
            elif hasattr(self.manager.credit_notes, 'get_all_credit_notes'):
                all_notes = self.manager.credit_notes.get_all_credit_notes()
                for n in all_notes:
                    if d_start <= str(n['Credit_Date']) <= d_end:
                        notes.append(n)
            
            for row, note in enumerate(notes):
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(str(note['Credit_Note_ID'])))
                self.table.setItem(row, 1, QTableWidgetItem(str(note['Credit_Note_Ref'])))
                self.table.setItem(row, 2, QTableWidgetItem(str(note.get('Supplier_Name', '---'))))
                self.table.setItem(row, 3, QTableWidgetItem(str(note['Credit_Date'])))
                
                type_map = {"Return_Goods": "Retour Marchandise", "Price_Correction": "Correction Prix"}
                type_display = type_map.get(note['Type'], note['Type'])
                
                self.table.setItem(row, 4, QTableWidgetItem(type_display))
                
                amt = float(note.get('Total_Amount_TTC') or 0)
                amt_item = QTableWidgetItem(f"{amt:,.2f} DA")
                amt_item.setForeground(QBrush(QColor("#c0392b")))
                self.table.setItem(row, 5, amt_item)

        except Exception as e:
            logging.error(f"Error loading credit notes: {e}")
            QMessageBox.warning(self, "Erreur", f"Erreur de chargement: {e}")
