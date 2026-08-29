# ui/widgets/reclamation/reclamation_tab.py

import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QHeaderView, 
                               QTableWidgetItem, QMessageBox, QLabel, QHBoxLayout, QPushButton,
                               QAbstractItemView, QDateEdit, QFrame)
from PySide6.QtCore import Qt, QDate
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
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Toolbar
        top_frame = QFrame()
        top_frame.setStyleSheet("QFrame { background-color: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 6px; }")
        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(10, 5, 10, 5)
        
        # --- [جديد] إضافة حقول النطاق التاريخي ---
        self.date_from = QDateEdit(QDate.currentDate().addMonths(-3)) # الافتراضي: آخر 3 أشهر
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.dateChanged.connect(self.load_data)

        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.dateChanged.connect(self.load_data)
        # -----------------------------------------

        btn_refresh = QPushButton("Actualiser")
        btn_refresh.setIcon(qta.icon("fa5s.sync-alt"))
        btn_refresh.clicked.connect(self.load_data)
        
        top_layout.addStretch()
        
        # إضافة الفلاتر للتخطيط
        top_layout.addWidget(QLabel("Du:"))
        top_layout.addWidget(self.date_from)
        top_layout.addWidget(QLabel("Au:"))
        top_layout.addWidget(self.date_to)
        top_layout.addSpacing(10)
        
        top_layout.addWidget(btn_refresh)
        layout.addWidget(top_frame)

        # Table
        self.table = QTableWidget()
        columns = ["ID (BR)", "Fournisseur", "Date", "Type Problème", "Statut"]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        # منع التعديل المباشر عند النقر المزدوج
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers) 
        
        self.table.doubleClicked.connect(self.open_details)
        
        layout.addWidget(self.table)
        self.load_data()

    def showEvent(self, event):
        super().showEvent(event)
        self.load_data()

    def load_data(self):
        try:
            self.table.setSortingEnabled(False) # تعطيل الفرز أثناء التحديث
            self.table.setRowCount(0)
            
            if hasattr(self.manager.reception, 'get_receptions_with_issues'):
                data = self.manager.reception.get_receptions_with_issues()
            else:
                return 

            # [جديد] الحصول على تواريخ الفلترة كنصوص للمقارنة
            start_date_str = self.date_from.date().toString("yyyy-MM-dd")
            end_date_str = self.date_to.date().toString("yyyy-MM-dd")

            for item in data:
                # [جديد] معالجة التاريخ والفلترة
                raw_date = str(item.get('Reception_Date', ''))
                # نأخذ أول 10 أحرف فقط (YYYY-MM-DD) لإزالة الوقت
                display_date = raw_date[:10] 
                
                # تخطي السجل إذا كان خارج النطاق الزمني
                if not (start_date_str <= display_date <= end_date_str):
                    continue

                header_note = str(item.get('Variance_Notes') or '').strip()
                if header_note.lower() in ('none', 'null'):
                    header_note = ''

                prod_issues = item.get('Product_Issues_Count', 0)
                
                # تصنيف المشكلة
                issue_desc = []
                if header_note: issue_desc.append("Facture/BL")
                if prod_issues > 0: issue_desc.append(f"{prod_issues} Produit(s)")
                
                # إذا لم تكن هناك أي مشكلة حقيقية، نتخطى هذا السجل
                if not issue_desc:
                    continue

                # إضافة سطر جديد (نستخدم rowCount لأننا قد نتخطى بعض السجلات في الفلترة)
                row = self.table.rowCount()
                self.table.insertRow(row)

                final_issue = " + ".join(issue_desc)

                self.table.setItem(row, 0, QTableWidgetItem(str(item['BR_ID'])))
                self.table.setItem(row, 1, QTableWidgetItem(item.get('Supplier_Name', '')))
                
                # [معدل] عرض التاريخ بدون وقت
                self.table.setItem(row, 2, QTableWidgetItem(display_date))
                
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
            
            # تحديث الجدول بعد الإغلاق
            self.load_data()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir les détails: {e}")
