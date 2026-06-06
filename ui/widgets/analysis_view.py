import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, 
    QDateEdit, QPushButton, QTabWidget, QTableWidget, 
    QTableWidgetItem, QHeaderView, QSplitter
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtCharts import QChart, QChartView, QPieSeries, QPieSlice

from ui.formatting import format_money, format_quantity

# =============================================================================
# 1. TAB: VALORISATION DU STOCK (Jard)
# يعرض قيمة المخزون الحالية بالتفصيل (عدد العلب + عدد الفحوصات + القيمة المالية)
# =============================================================================
class StockValuationTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # ملخص سريع في الأعلى
        self.lbl_summary = QLabel("Valeur Totale: 0.00 DA")
        self.lbl_summary.setStyleSheet("font-size: 16px; font-weight: bold; color: #27ae60; margin-bottom: 10px;")
        layout.addWidget(self.lbl_summary)

        # الجدول
        self.table = QTableWidget()
        cols = ["Produit", "Stock (Boîtes)", "Unités d'Usage (Tests)", "Valeur HT (DA)"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        
        # تنسيق الجدول
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents) # اسم المنتج
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setStyleSheet("border: 1px solid #dcdde1; gridline-color: #ecf0f1;")
        
        layout.addWidget(self.table)

    def refresh(self, stats_manager):
        """جلب البيانات من get_stock_valuation_detailed"""
        try:
            self.table.setSortingEnabled(False)
            data = stats_manager.get_stock_valuation_detailed()
            self.table.setRowCount(0)
            
            total_value = 0
            
            for row, item in enumerate(data):
                self.table.insertRow(row)
                
                # 1. Product Name
                self.table.setItem(row, 0, QTableWidgetItem(str(item['Product_Name'])))
                
                # 2. Stock Boxes (Stock Unit)
                box_unit = item['Stock_Unit'] or "U"
                boxes = item['total_boxes']
                self.table.setItem(row, 1, QTableWidgetItem(format_quantity(boxes, box_unit)))
                
                # 3. Usage Units (Tests) - ميزة قوية للمختبرات
                usage_unit = item['Usage_Unit'] or "Tests"
                tests = item['total_tests']
                item_tests = QTableWidgetItem(format_quantity(tests, usage_unit))
                item_tests.setForeground(QColor("#2980b9")) # أزرق
                item_tests.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.table.setItem(row, 2, item_tests)
                
                # 4. Financial Value
                val = float(item['total_value_ht'])
                total_value += val
                item_val = QTableWidgetItem(format_money(val))
                item_val.setForeground(QColor("#27ae60")) # أخضر
                self.table.setItem(row, 3, item_val)

            self.lbl_summary.setText(f"💰 Valeur Totale du Stock : {format_money(total_value, 'DA')}")
            self.table.setSortingEnabled(True)
            
        except Exception as e:
            logging.error(f"Valuation Tab Error: {e}")

# =============================================================================
# 2. TAB: ANALYSE DES PERTES (Waste Analysis)
# يعرض أسباب التلف وتكلفتها (رسم بياني + جدول)
# =============================================================================
class WasteAnalysisTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        
        # --- الجانب الأيسر: الرسم البياني (Pie Chart) ---
        chart_frame = QFrame()
        chart_layout = QVBoxLayout(chart_frame)
        
        self.chart = QChart()
        self.chart.setTitle("Répartition des Pertes (Par Coût)")
        self.chart.setTitleFont(QFont("Segoe UI", 10, QFont.Bold))
        self.chart.setAnimationOptions(QChart.SeriesAnimations)
        self.chart.legend().setVisible(True)
        self.chart.legend().setAlignment(Qt.AlignBottom)
        
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        chart_layout.addWidget(self.chart_view)
        
        # --- الجانب الأيمن: جدول التفاصيل ---
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Motif (Raison)", "Fréquence", "Perte Estimée (DA)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        
        # تقسيم الشاشة
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(chart_frame)
        splitter.addWidget(self.table)
        splitter.setSizes([400, 600]) # نسبة العرض
        
        layout.addWidget(splitter)

    def refresh(self, stats_manager, d_from, d_to):
        """جلب البيانات من get_waste_analysis"""
        try:
            data = stats_manager.get_waste_analysis(d_from, d_to)
            
            # 1. تحديث الجدول
            self.table.setRowCount(0)
            series = QPieSeries()
            
            for row, item in enumerate(data):
                self.table.insertRow(row)
                
                reason = item['Reason_Name'] or "Inconnu"
                freq = item['frequency']
                loss = float(item['estimated_loss'])
                
                self.table.setItem(row, 0, QTableWidgetItem(reason))
                self.table.setItem(row, 1, QTableWidgetItem(str(freq)))
                
                val_item = QTableWidgetItem(format_money(loss))
                val_item.setForeground(QColor("#c0392b")) # أحمر
                self.table.setItem(row, 2, val_item)
                
                # إضافة للرسم البياني
                if loss > 0:
                    slice_obj = series.append(reason, loss)
                    slice_obj.setLabel(f"{reason} ({loss:,.0f})")
            
            # إظهار أكبر قطعة في الكعكة (Explode)
            if series.count() > 0:
                slices = series.slices()
                # البحث عن أكبر شريحة
                max_slice = max(slices, key=lambda s: s.value())
                max_slice.setExploded(True)
                max_slice.setLabelVisible(True)
            
            self.chart.removeAllSeries()
            self.chart.addSeries(series)
            
        except Exception as e:
            logging.error(f"Waste Tab Error: {e}")

# =============================================================================
# 3. TAB: RAPPORT CONSOMMATION DÉTAILLÉ
# النسخة الكاملة لتقرير الاستهلاك
# =============================================================================
class FullConsumptionTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        cols = ["Produit", "Unité Usage", "Qté Consommée", "Coût Total TTC (DA)"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table)

    def refresh(self, stats_manager, d_from, d_to):
        """جلب البيانات من get_detailed_consumption_report"""
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
        except Exception as e:
            logging.error(f"Consumption Tab Error: {e}")

# =============================================================================
# MAIN VIEW: ANALYSIS VIEW (CONTAINER)
# =============================================================================
class AnalysisView(QWidget):
    """
    الواجهة الرئيسية التي تجمع كل التبويبات الإحصائية.
    تحتوي على شريط تحكم بالتاريخ (مشترك) وزر تحديث.
    """
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.stats = manager.stats # الوصول السريع لـ StatisticsManager
        
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- 1. Top Toolbar (Controls) ---
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: white; border-bottom: 1px solid #dcdde1;")
        toolbar.setFixedHeight(70)
        tool_layout = QHBoxLayout(toolbar)
        
        lbl_title = QLabel("📊 ANALYSE & RAPPORTS")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: 900; color: #2c3e50;")
        
        self.date_from = QDateEdit(QDate.currentDate().addDays(-30))
        self.date_to = QDateEdit(QDate.currentDate())
        for d in [self.date_from, self.date_to]:
            d.setCalendarPopup(True)
            d.setFixedWidth(120)
            d.setStyleSheet("padding: 5px; border: 1px solid #bdc3c7; border-radius: 4px;")

        btn_refresh = QPushButton("ACTUALISER LES DONNÉES")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setIcon(qta.icon('fa5s.sync-alt', color='white') if 'qta' in globals() else None)
        btn_refresh.setStyleSheet("""
            QPushButton { 
                background-color: #2c3e50; color: white; font-weight: bold; 
                border-radius: 4px; padding: 8px 20px; border: none;
            }
            QPushButton:hover { background-color: #34495e; }
        """)
        btn_refresh.clicked.connect(self.refresh_all)

        tool_layout.addWidget(lbl_title)
        tool_layout.addStretch()
        tool_layout.addWidget(QLabel("Période du:"))
        tool_layout.addWidget(self.date_from)
        tool_layout.addWidget(QLabel("au:"))
        tool_layout.addWidget(self.date_to)
        tool_layout.addSpacing(10)
        tool_layout.addWidget(btn_refresh)
        
        main_layout.addWidget(toolbar)

        # --- 2. Content Tabs ---
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #dcdde1; background: #f9f9f9; }
            QTabBar::tab { 
                background: #ecf0f1; color: #7f8c8d; padding: 12px 30px; 
                font-weight: bold; margin-right: 2px;
            }
            QTabBar::tab:selected { 
                background: white; color: #2c3e50; border-top: 3px solid #2c3e50; 
            }
        """)
        
        # إنشاء التبويبات
        self.tab_valuation = StockValuationTab()
        self.tab_waste = WasteAnalysisTab()
        self.tab_consumption = FullConsumptionTab()
        
        self.tabs.addTab(self.tab_valuation, "💰 Valorisation du Stock")
        self.tabs.addTab(self.tab_waste, "🗑️ Analyse des Pertes (Déchets)")
        self.tabs.addTab(self.tab_consumption, "📉 Rapport Consommation")
        
        main_layout.addWidget(self.tabs)
        
        # تحميل البيانات الأولي
        self.refresh_all()

    def refresh_all(self):
        """تحديث جميع التبويبات دفعة واحدة"""
        d_from_str = self.date_from.date().toString("yyyy-MM-dd")
        d_to_str = self.date_to.date().toString("yyyy-MM-dd")
        
        # 1. تحديث تقييم المخزون (لا يعتمد على التاريخ، بل على الحالة الحالية)
        self.tab_valuation.refresh(self.stats)
        
        # 2. تحديث تحليل الهدر (يعتمد على التاريخ)
        self.tab_waste.refresh(self.stats, d_from_str, d_to_str)
        
        # 3. تحديث تقرير الاستهلاك (يعتمد على التاريخ)
        self.tab_consumption.refresh(self.stats, d_from_str, d_to_str)
