# ui/widgets/dashboard/statistics_tabs.py

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, 
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, 
    QSplitter, QLineEdit, QAbstractItemView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QBrush
from PySide6.QtCharts import QChart, QChartView, QPieSeries, QPieSlice

from ui.formatting import format_money, format_quantity

# =============================================================================
# Helper: دالة البحث في الجدول (لتقليل تكرار الكود)
# =============================================================================
def filter_table_rows(table_widget, search_text):
    """إخفاء الصفوف التي لا تحتوي على النص المطلوب"""
    search_text = search_text.lower()
    for row in range(table_widget.rowCount()):
        match = False
        for col in range(table_widget.columnCount()):
            item = table_widget.item(row, col)
            if item and search_text in item.text().lower():
                match = True
                break
        table_widget.setRowHidden(row, not match)

# =============================================================================
# 1. TAB: VALORISATION DU STOCK (مع البحث)
# =============================================================================
class StockValuationTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header with Search
        top_layout = QHBoxLayout()
        self.lbl_summary = QLabel("Valeur Totale: 0.00 DA")
        self.lbl_summary.setStyleSheet("font-size: 16px; font-weight: bold; color: #27ae60;")
        
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Rechercher un produit / code...")
        self.txt_search.setFixedWidth(300)
        self.txt_search.setStyleSheet("padding: 5px; border-radius: 5px; border: 1px solid #ccc;")
        self.txt_search.textChanged.connect(lambda text: filter_table_rows(self.table, text))
        
        top_layout.addWidget(self.lbl_summary)
        top_layout.addStretch()
        top_layout.addWidget(self.txt_search)
        layout.addLayout(top_layout)

        # Table
        self.table = QTableWidget()
        cols = ["Produit", "Stock (Boîtes)", "Unités (Tests)", "Valeur HT (DA)"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setStyleSheet("border: 1px solid #dcdde1; gridline-color: #f0f0f0;")
        
        layout.addWidget(self.table)

    def refresh(self, stats_manager):
        try:
            self.table.setSortingEnabled(False)
            data = stats_manager.get_stock_valuation_detailed()
            self.table.setRowCount(0)
            
            total_value = 0
            for row, item in enumerate(data):
                self.table.insertRow(row)
                
                # Product Name
                self.table.setItem(row, 0, QTableWidgetItem(str(item['Product_Name'])))
                
                # Stock (Boxes)
                box_unit = item['Stock_Unit'] or "U"
                boxes = item['total_boxes']
                self.table.setItem(row, 1, QTableWidgetItem(format_quantity(boxes, box_unit)))
                
                # Usage Units (Tests)
                usage_unit = item['Usage_Unit'] or "Tests"
                tests = item['total_tests']
                item_tests = QTableWidgetItem(format_quantity(tests, usage_unit))
                item_tests.setForeground(QColor("#2980b9"))
                item_tests.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.table.setItem(row, 2, item_tests)
                
                # Value
                val = float(item['total_value_ht'])
                total_value += val
                item_val = QTableWidgetItem(format_money(val))
                item_val.setForeground(QColor("#27ae60"))
                self.table.setItem(row, 3, item_val)

            self.lbl_summary.setText(f"💰 Valeur Totale : {format_money(total_value, 'DA')}")
            self.table.setSortingEnabled(True)
            
            if self.txt_search.text():
                filter_table_rows(self.table, self.txt_search.text())
                
        except Exception as e:
            logging.error(f"Valuation Error: {e}")

# =============================================================================
# 2. TAB: RAPPORT CONSOMMATION (مع البحث)
# =============================================================================
class FullConsumptionTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Search Bar
        search_layout = QHBoxLayout()
        search_layout.addStretch()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Filtrer les résultats...")
        self.txt_search.setFixedWidth(300)
        self.txt_search.setStyleSheet("padding: 5px; border-radius: 5px; border: 1px solid #ccc;")
        self.txt_search.textChanged.connect(lambda text: filter_table_rows(self.table, text))
        search_layout.addWidget(self.txt_search)
        layout.addLayout(search_layout)

        # Table
        self.table = QTableWidget()
        cols = ["Produit", "Unité Usage", "Qté Consommée", "Coût Total TTC (DA)"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setSortingEnabled(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("border: 1px solid #dcdde1;")
        
        layout.addWidget(self.table)

    def refresh(self, stats_manager, d_from, d_to):
        try:
            self.table.setSortingEnabled(False)
            data = stats_manager.get_detailed_consumption_report(d_from, d_to)
            self.table.setRowCount(0)
            
            for row, item in enumerate(data):
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(str(item['Product_Name'])))
                self.table.setItem(row, 1, QTableWidgetItem(str(item['Usage_Unit'])))
                
                qty = item['total_qty_consumed']
                self.table.setItem(row, 2, QTableWidgetItem(format_quantity(qty)))
                
                cost = float(item['total_cost_ttc'])
                cost_item = QTableWidgetItem(format_money(cost))
                cost_item.setForeground(QColor("#007572"))
                cost_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.table.setItem(row, 3, cost_item)
                
            self.table.setSortingEnabled(True)
            if self.txt_search.text():
                filter_table_rows(self.table, self.txt_search.text())
        except Exception as e:
            logging.error(f"Consumption Tab Error: {e}")

# =============================================================================
# 3. TAB: AUDIT & PRODUITS SUPPRIMÉS (الجديد كلياً)
# =============================================================================
class DeletedProductsAuditTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # --- Section 1: Stock Fantôme (Zombie Stock) ---
        # هذه أخطر مشكلة: منتج محذوف لكنه مازال في المخزون
        lbl_zombie = QLabel("⚠️ STOCK FANTÔME (Produits supprimés avec stock positif)")
        lbl_zombie.setStyleSheet("color: #c0392b; font-weight: bold; font-size: 14px;")
        layout.addWidget(lbl_zombie)
        
        self.table_zombie = QTableWidget()
        self.table_zombie.setColumnCount(5)
        self.table_zombie.setHorizontalHeaderLabels(["Produit", "Lot", "Qté Restante", "Emplacement", "Action Requise"])
        self.table_zombie.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_zombie.setFixedHeight(180) 
        self.table_zombie.setStyleSheet("border: 2px solid #e74c3c;") # إطار أحمر للتحذير
        layout.addWidget(self.table_zombie)

        # --- Section 2: Consommation des produits supprimés ---
        # لعرض المنتجات المحذوفة التي ظهرت في تقارير الاستهلاك
        header_hist = QHBoxLayout()
        lbl_hist = QLabel("📜 Historique de consommation des produits supprimés")
        lbl_hist.setStyleSheet("color: #7f8c8d; font-weight: bold; font-size: 14px;")
        
        # بحث للجدول السفلي
        self.txt_search_audit = QLineEdit()
        self.txt_search_audit.setPlaceholderText("🔍 Filtrer l'historique...")
        self.txt_search_audit.setFixedWidth(250)
        self.txt_search_audit.textChanged.connect(lambda text: filter_table_rows(self.table_hist, text))
        
        header_hist.addWidget(lbl_hist)
        header_hist.addStretch()
        header_hist.addWidget(self.txt_search_audit)
        layout.addLayout(header_hist)

        self.table_hist = QTableWidget()
        self.table_hist.setColumnCount(4)
        self.table_hist.setHorizontalHeaderLabels(["Produit Supprimé", "Date Suppression", "Qté Consommée", "Valeur (DA)"])
        self.table_hist.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_hist.setAlternatingRowColors(True)
        layout.addWidget(self.table_hist)

    def refresh(self, stats_manager, d_from, d_to):
        try:
            # 1. Zombie Stock (Get directly from DB)
            zombies = stats_manager.get_zombie_stock()
            self.table_zombie.setRowCount(0)
            for row, z in enumerate(zombies):
                self.table_zombie.insertRow(row)
                self.table_zombie.setItem(row, 0, QTableWidgetItem(str(z['Product_Name'])))
                self.table_zombie.setItem(row, 1, QTableWidgetItem(str(z['Lot_Number'])))
                self.table_zombie.setItem(row, 2, QTableWidgetItem(format_quantity(z['Quantity_Current'])))
                self.table_zombie.setItem(row, 3, QTableWidgetItem(str(z['Location_Name'])))
                
                item_action = QTableWidgetItem("VIDER LE STOCK (Waste)")
                item_action.setForeground(QColor("red"))
                item_action.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.table_zombie.setItem(row, 4, item_action)

            # 2. Historical Consumption
            history = stats_manager.get_deleted_products_consumption(d_from, d_to)
            self.table_hist.setRowCount(0)
            for row, h in enumerate(history):
                self.table_hist.insertRow(row)
                self.table_hist.setItem(row, 0, QTableWidgetItem(str(h['Product_Name'])))
                
                del_date = str(h['Deleted_At']) if h['Deleted_At'] else "N/A"
                self.table_hist.setItem(row, 1, QTableWidgetItem(del_date))
                
                self.table_hist.setItem(row, 2, QTableWidgetItem(format_quantity(h['qty_consumed'])))
                
                val = float(h['value_consumed'])
                self.table_hist.setItem(row, 3, QTableWidgetItem(format_money(val)))
                
            if self.txt_search_audit.text():
                filter_table_rows(self.table_hist, self.txt_search_audit.text())
                
        except Exception as e:
            logging.error(f"Audit Tab Error: {e}")

# =============================================================================
# 4. WIDGET: ANALYSE DES PERTES (Waste)
# =============================================================================
# =============================================================================
# 4. WIDGET: ANALYSE DES PERTES (Waste) - Version Améliorée
# =============================================================================
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QFrame, QTableWidget, 
                               QTableWidgetItem, QHeaderView, QSplitter)
from PySide6.QtCharts import QChart, QChartView, QPieSeries
from PySide6.QtGui import QFont, QColor, QPainter, QBrush
from PySide6.QtCore import Qt
import logging

class WasteAnalysisTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # --- Zone Graphique (Chart) ---
        chart_frame = QFrame()
        chart_frame.setStyleSheet("background: white; border-radius: 8px;")
        chart_layout = QVBoxLayout(chart_frame)
        
        self.chart = QChart()
        self.chart.setTitle("Répartition des Coûts par Motif")
        self.chart.setTitleFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # تحسين وسيلة الإيضاح (Legend)
        self.chart.legend().setVisible(True)
        self.chart.legend().setAlignment(Qt.AlignRight)
        self.chart.legend().setFont(QFont("Segoe UI", 9))
        self.chart.setBackgroundVisible(False)
        
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        chart_layout.addWidget(self.chart_view)
        
        # --- Zone Tableau (Table) ---
        table_container = QFrame()
        table_container.setStyleSheet("background: white; border-radius: 8px;")
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Motif de Perte", "Fréquence", "Coût Total (DA)"])
        
        # تنسيق الجدول
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setStyleSheet("""
            QTableWidget { border: none; }
            QHeaderView::section { background-color: #f8f9fa; border: none; padding: 5px; font-weight: bold; }
        """)
        table_layout.addWidget(self.table)
        
        # --- Splitter (تقسيم الشاشة) ---
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(chart_frame)
        splitter.addWidget(table_container)
        splitter.setSizes([450, 450]) # توازن مبدئي بين الجزئين
        splitter.setHandleWidth(10)
        
        layout.addWidget(splitter)

    def refresh(self, stats_manager, d_from, d_to):
        try:
            # جلب البيانات من المدير
            data = stats_manager.get_waste_analysis(d_from, d_to)
            
            self.table.setSortingEnabled(False)
            self.table.setRowCount(0)
            self.chart.removeAllSeries()
            
            series = QPieSeries()
            total_loss = sum(float(item['estimated_loss']) for item in data) if data else 0
            
            for row, item in enumerate(data):
                self.table.insertRow(row)
                
                # 1. السبب (Motif)
                reason_name = item['Reason_Name'] if item['Reason_Name'] else "Autre / Non spécifié"
                
                # 2. التكرار (Fréquence)
                freq = item['frequency']
                
                # 3. الخسارة المالية (Loss)
                loss = float(item['estimated_loss'])
                
                # تعبئة الجدول
                self.table.setItem(row, 0, QTableWidgetItem(reason_name))
                
                freq_item = QTableWidgetItem(str(freq))
                freq_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 1, freq_item)
                
                val_item = QTableWidgetItem(format_money(loss, "DA").replace(',', ' '))
                val_item.setForeground(QColor("#c0392b")) # أحمر للخسارة
                val_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                val_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, 2, val_item)
                
                # إضافة البيانات للمخطط فقط إذا كانت القيمة > 0
                if loss > 0:
                    # حساب النسبة المئوية للعرض
                    percentage = (loss / total_loss * 100) if total_loss > 0 else 0
                    label = f"{reason_name} ({percentage:.1f}%)"
                    slice_obj = series.append(label, loss)
                    
                    # تمييز الشريحة الأكبر (Explode)
                    if percentage > 40:  # إذا كانت تمثل أكثر من 40%
                        slice_obj.setExploded(True)
                        slice_obj.setLabelVisible(True)
            
            # إذا لم تكن هناك بيانات
            if not data or total_loss == 0:
                series.append("Aucune Perte", 1)
                slice_0 = series.slices()[0]
                slice_0.setBrush(QColor("#ecf0f1"))
                slice_0.setLabelVisible(True)
                self.chart.setTitle("Aucune donnée pour cette période")
            else:
                self.chart.setTitle(f"Répartition des Pertes (Total: {format_money(total_loss, 'DA')})")

            self.chart.addSeries(series)
            self.table.setSortingEnabled(True)
            
        except Exception as e:
            logging.error(f"Erreur Refresh Waste Analysis: {e}")
