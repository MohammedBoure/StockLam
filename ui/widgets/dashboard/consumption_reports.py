from PySide6.QtWidgets import (QFrame, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QHBoxLayout, QComboBox)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QFont

from ui.formatting import format_money, format_quantity

class ConsumptionReportSection(QFrame):
    def __init__(self, stats_manager):
        super().__init__()
        self.stats_manager = stats_manager
        self.d_from = QDate.currentDate().addDays(-30)
        self.d_to = QDate.currentDate()
        
        self.setStyleSheet("background: white; border: none;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        top_bar = QHBoxLayout()
        header_lbl = QLabel("📊 Rapport de Consommation")
        header_lbl.setStyleSheet("font-weight: bold; color: #2c3e50;")
        
        self.filter_type = QComboBox()
        self.filter_type.addItems(["Produits Consommés", "Produits Supprimés (Rebut)"])
        self.filter_type.setFixedWidth(200)
        self.filter_type.currentIndexChanged.connect(self.refresh_report)
        
        top_bar.addWidget(header_lbl)
        top_bar.addStretch()
        top_bar.addWidget(self.filter_type)
        layout.addLayout(top_bar)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Désignation", "Qté (Unité Stock)", "Coût Total (TTC)"])
        
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("border: none; gridline-color: #f5f7f9;")
        layout.addWidget(self.table)

    def update_params(self, d1, d2):
        self.d_from = d1
        self.d_to = d2
        self.refresh_report()

    def refresh_report(self):
        self.table.setSortingEnabled(False)
        report_type = "consumed" if self.filter_type.currentIndex() == 0 else "waste"
        
        data = self.stats_manager.get_detailed_consumption_report(
            self.d_from.toString("yyyy-MM-dd"), 
            self.d_to.toString("yyyy-MM-dd"),
            report_type=report_type
        )
        
        self.table.setRowCount(0)
        
        for row, r in enumerate(data):
            self.table.insertRow(row)
            
            self.table.setItem(row, 0, QTableWidgetItem(str(r['Product_Name'])))
            
            unit = str(r['Stock_Unit'] or "Unité") 
            qty_str = format_quantity(r.get('total_qty_stock', 0), unit)
                
            qty_item = QTableWidgetItem(qty_str)
            qty_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, qty_item)
            
            cost_val = r.get('total_cost_ttc', 0)
            val_item = QTableWidgetItem(format_money(cost_val, "DA").replace(',', ' '))
            val_item.setTextAlignment(Qt.AlignCenter)
            val_item.setForeground(QColor("#007572"))
            val_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.table.setItem(row, 2, val_item)

        self.table.setSortingEnabled(True)
