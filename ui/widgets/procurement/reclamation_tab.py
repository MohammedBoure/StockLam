# ui/widgets/procurement/reclamation_tab.py

import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QHeaderView, 
                               QTableWidgetItem, QMessageBox, QLabel, QHBoxLayout, QPushButton,
                               QAbstractItemView) # <--- تأكد من استيراد QAbstractItemView
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QFont
import qtawesome as qta

from .reclamation_dialog import ReclamationDialog

class ReclamationTab(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        top_layout = QHBoxLayout()
        lbl_title = QLabel("⚠️ Suivi des Réclamations & Anomalies")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #c0392b;")
        
        btn_refresh = QPushButton("Actualiser")
        btn_refresh.setIcon(qta.icon("fa5s.sync-alt"))
        btn_refresh.clicked.connect(self.load_data)
        
        top_layout.addWidget(lbl_title)
        top_layout.addStretch()
        top_layout.addWidget(btn_refresh)
        layout.addLayout(top_layout)

        # Table
        self.table = QTableWidget()
        columns = ["ID (BR)", "Fournisseur", "Date", "Type Problème", "Statut"]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        # --- [إصلاح] منع التعديل المباشر عند النقر المزدوج ---
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers) 
        # ---------------------------------------------------
        
        self.table.doubleClicked.connect(self.open_details)
        
        layout.addWidget(self.table)
        self.load_data()

    def load_data(self):
        try:
            self.table.setSortingEnabled(False) # تعطيل الفرز أثناء التحديث لتجنب الأخطاء
            self.table.setRowCount(0)
            
            if hasattr(self.manager.reception, 'get_receptions_with_issues'):
                data = self.manager.reception.get_receptions_with_issues()
            else:
                return 

            for row, item in enumerate(data):
                self.table.insertRow(row)
                
                header_note = item.get('Variance_Notes', '')
                prod_issues = item.get('Product_Issues_Count', 0)
                
                # تصنيف المشكلة
                issue_desc = []
                if header_note: issue_desc.append("Facture/BL")
                if prod_issues > 0: issue_desc.append(f"{prod_issues} Produit(s)")
                
                final_issue = " + ".join(issue_desc)

                # استخدام دالة مساعدة لإنشاء الخلايا (اختياري، للترتيب)
                self.table.setItem(row, 0, QTableWidgetItem(str(item['BR_ID'])))
                self.table.setItem(row, 1, QTableWidgetItem(item.get('Supplier_Name', '')))
                self.table.setItem(row, 2, QTableWidgetItem(str(item.get('Reception_Date'))))
                
                item_issue = QTableWidgetItem(final_issue)
                item_issue.setForeground(QBrush(QColor("#c0392b")))
                item_issue.setFont(QFont("Arial", 9, QFont.Bold))
                self.table.setItem(row, 3, item_issue)
                
                self.table.setItem(row, 4, QTableWidgetItem(item.get('Status', '')))
                
                # تخزين البيانات المهمة
                self.table.item(row, 0).setData(Qt.UserRole, item['BR_ID'])
            
            self.table.setSortingEnabled(True)

        except Exception as e:
            logging.error(f"Error loading reclamations: {e}")

    def open_details(self):
        row = self.table.currentRow()
        if row < 0: return
        
        br_id = self.table.item(row, 0).data(Qt.UserRole)
        
        try:
            full_data = self.manager.reception.get_reception_details(br_id)
            if not full_data:
                raise ValueError("Données introuvables")

            # تمرير المدير (manager) للنافذة لتمكين الحفظ
            dialog = ReclamationDialog(full_data, self.manager, self)
            dialog.exec()
            
            # تحديث الجدول بعد الإغلاق (قد يكون النص تغير)
            self.load_data()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir les détails: {e}")