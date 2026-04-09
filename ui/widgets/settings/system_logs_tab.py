# ui/widgets/settings/system_logs_tab.py

import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QGroupBox, QLineEdit, QComboBox, QDateEdit, QTableWidget, 
    QTableWidgetItem, QHeaderView, QAbstractItemView, QDialog, QTextEdit
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor
import qtawesome as qta

class LogDetailsDialog(QDialog):
    """نافذة منبثقة لعرض تفاصيل الـ JSON بشكل أنيق"""
    def __init__(self, action_name, details_json_str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Détails de l'action : {action_name}")
        self.setMinimumSize(550, 450)
        
        layout = QVBoxLayout(self)
        
        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setFont(QFont("Consolas", 11))
        self.text_view.setStyleSheet("background-color: #f8f9fa; color: #2c3e50; border: 1px solid #bdc3c7; padding: 10px;")
        self.text_view.setPlainText(details_json_str)
        
        layout.addWidget(self.text_view)
        
        btn_close = QPushButton(" Fermer")
        btn_close.setIcon(qta.icon("fa5s.times"))
        btn_close.clicked.connect(self.accept)
        btn_close.setMinimumHeight(40)
        btn_close.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; border-radius: 5px;")
        
        layout.addWidget(btn_close)

class SystemLogsTab(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.page_size = 50
        self.current_page = 1
        self.total_pages = 1
        self.current_logs_data = [] 
        
        self.init_ui()
        self.load_filters()
        self.load_data()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        filter_group = QGroupBox("Filtres de recherche")
        filter_layout = QHBoxLayout(filter_group)

        self.date_start = QDateEdit(QDate.currentDate().addDays(-7))
        self.date_start.setCalendarPopup(True)
        self.date_start.setDisplayFormat("yyyy-MM-dd")
        
        self.date_end = QDateEdit(QDate.currentDate())
        self.date_end.setCalendarPopup(True)
        self.date_end.setDisplayFormat("yyyy-MM-dd")

        self.combo_users = QComboBox()
        self.combo_modules = QComboBox()
        
        self.combo_action_types = QComboBox()
        self.combo_action_types.addItems(["Tous", "CREATE", "UPDATE", "DELETE", "READ", "OTHER"])
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Chercher...")

        btn_search = QPushButton(" Filtrer")
        btn_search.setIcon(qta.icon("fa5s.search", color="white"))
        btn_search.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; padding: 5px 15px;")
        btn_search.clicked.connect(self.on_search)

        btn_clear = QPushButton(" Réinitialiser")
        btn_clear.setIcon(qta.icon("fa5s.sync", color="#333"))
        btn_clear.clicked.connect(self.clear_filters)

        filter_layout.addWidget(QLabel("Du:"))
        filter_layout.addWidget(self.date_start)
        filter_layout.addWidget(QLabel("Au:"))
        filter_layout.addWidget(self.date_end)
        filter_layout.addWidget(QLabel("Utilisateur:"))
        filter_layout.addWidget(self.combo_users)
        filter_layout.addWidget(QLabel("Classe:"))
        filter_layout.addWidget(self.combo_modules)
        filter_layout.addWidget(QLabel("Type:"))
        filter_layout.addWidget(self.combo_action_types)
        filter_layout.addWidget(self.search_box)
        filter_layout.addWidget(btn_search)
        filter_layout.addWidget(btn_clear)

        main_layout.addWidget(filter_group)

        self.table = QTableWidget(0, 4) 
        self.table.setHorizontalHeaderLabels(["Date & Heure", "Utilisateur", "Action (Classe ➔ Fonction)", "Aperçu (Clic pour détails)"])
        header = self.table.horizontalHeader()
        
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents) 
        
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("QTableWidget::item { padding: 5px; } alternate-background-color: #f4f6f7;")
        self.table.setCursor(Qt.PointingHandCursor)
        self.table.cellClicked.connect(self.on_row_clicked)
        
        main_layout.addWidget(self.table)

        pagination_layout = QHBoxLayout()
        self.btn_prev = QPushButton("<< Précédent")
        self.btn_prev.clicked.connect(self.prev_page)
        
        self.lbl_page_info = QLabel("Page 1 / 1")
        self.lbl_page_info.setAlignment(Qt.AlignCenter)
        self.lbl_page_info.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        self.btn_next = QPushButton("Suivant >>")
        self.btn_next.clicked.connect(self.next_page)

        pagination_layout.addStretch()
        pagination_layout.addWidget(self.btn_prev)
        pagination_layout.addWidget(self.lbl_page_info)
        pagination_layout.addWidget(self.btn_next)
        pagination_layout.addStretch()

        main_layout.addLayout(pagination_layout)

    def load_filters(self):
        self.combo_users.clear()
        self.combo_modules.clear()
        
        self.combo_users.addItem("Tous", None)
        self.combo_modules.addItem("Tous", None)
        
        try:
            users = self.manager.users.get_all_users()
            for u in users:
                self.combo_users.addItem(u['username'], u['id'])
        except Exception:
            pass

        try:
            modules = self.manager.system_log.get_available_modules()
            for mod in modules:
                self.combo_modules.addItem(mod, mod)
        except Exception:
            pass

    def get_filter_params(self):
        params = {
            'start_date': self.date_start.date().toString("yyyy-MM-dd"),
            'end_date': self.date_end.date().toString("yyyy-MM-dd"),
            'limit': self.page_size,
            'offset': (self.current_page - 1) * self.page_size
        }
        
        user_id = self.combo_users.currentData()
        if user_id: params['user_id'] = user_id
            
        module = self.combo_modules.currentData()
        if module: params['module_name'] = module
            
        action_type = self.combo_action_types.currentText()
        if action_type != "Tous":
            params['action_type'] = action_type
            
        search = self.search_box.text().strip()
        if search: params['search_text'] = search
            
        return params

    def load_data(self):
        params = self.get_filter_params()
        
        try:
            self.current_logs_data = self.manager.system_log.get_logs(**params)
            total_logs = self.manager.system_log.get_total_logs_count(**params)
            
            self.total_pages = max(1, (total_logs + self.page_size - 1) // self.page_size)
            self.lbl_page_info.setText(f"Page {self.current_page} / {self.total_pages} (Total: {total_logs})")
            
            self.btn_prev.setEnabled(self.current_page > 1)
            self.btn_next.setEnabled(self.current_page < self.total_pages)

            self.table.setRowCount(0)
            for row_idx, log in enumerate(self.current_logs_data):
                self.table.insertRow(row_idx)
                
                action_display = f"📦 {log['module']} ➔ ⚙️ {log['action']}"

                preview_text = "{}"
                if log.get('details_dict'):
                    raw_json = json.dumps(log['details_dict'], ensure_ascii=False)
                    preview_text = (raw_json[:60] + '...') if len(raw_json) > 60 else raw_json

                self.table.setItem(row_idx, 0, QTableWidgetItem(str(log['log_date'])))
                self.table.setItem(row_idx, 1, QTableWidgetItem(f"👤 {log['username']}"))
                
                item_action = QTableWidgetItem(action_display)
                item_action.setFont(QFont("Arial", 10, QFont.Bold))
                self.table.setItem(row_idx, 2, item_action)
                
                item_preview = QTableWidgetItem(preview_text)
                item_preview.setForeground(QColor("#7f8c8d")) 
                self.table.setItem(row_idx, 3, item_preview)
                
            self.table.resizeColumnToContents(0)
            self.table.resizeColumnToContents(1)
            self.table.resizeColumnToContents(2)
        except Exception as e:
            print(f"Error loading logs: {e}")

    def on_row_clicked(self, row, column):
        log = self.current_logs_data[row]
        action_name = f"{log['module']} ➔ {log['action']}"
        
        details_text = "Aucun détail"
        if log.get('details_dict'):
            details_text = json.dumps(log['details_dict'], indent=4, ensure_ascii=False)
            
        dialog = LogDetailsDialog(action_name, details_text, self)
        dialog.exec()

    def on_search(self):
        self.current_page = 1
        self.load_data()

    def clear_filters(self):
        self.date_start.setDate(QDate.currentDate().addDays(-7))
        self.date_end.setDate(QDate.currentDate())
        self.combo_users.setCurrentIndex(0)
        self.combo_modules.setCurrentIndex(0)
        self.combo_action_types.setCurrentIndex(0)
        self.search_box.clear()
        self.on_search()

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_data()

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_data()