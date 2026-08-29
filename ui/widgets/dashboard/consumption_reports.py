import logging
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, 
    QHeaderView, QHBoxLayout, QComboBox, QLineEdit
)
from PySide6.QtCore import Qt, QDate, QTimer
from PySide6.QtGui import QColor, QFont

from ui.formatting import format_money, format_quantity


class ConsumptionReportSection(QFrame):
    def __init__(self, stats_manager):
        super().__init__()
        self.stats_manager = stats_manager
        self.d_from = QDate.currentDate().addDays(-30)
        self.d_to = QDate.currentDate()

        # مؤقت للبحث لتجنب كثرة الاستعلامات عند الكتابة السريعة
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)
        self.search_timer.timeout.connect(self.refresh_report)

        self.setStyleSheet("background: white; border: none;")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # --- 1. شريط العنوان ونوع التقرير ---
        top_bar = QHBoxLayout()
        header_lbl = QLabel("📊 Rapport de Consommation")
        header_lbl.setStyleSheet("font-weight: bold; font-size: 15px; color: #2c3e50;")

        self.filter_type = QComboBox()
        self.filter_type.addItems(["Produits Consommés", "Produits Supprimés (Rebut)"])
        self.filter_type.setFixedWidth(210)
        self.filter_type.setStyleSheet("QComboBox { padding: 4px; font-size: 13px; }")
        self.filter_type.currentIndexChanged.connect(self.refresh_report)

        top_bar.addWidget(header_lbl)
        top_bar.addStretch()
        top_bar.addWidget(self.filter_type)
        layout.addLayout(top_bar)

        # --- 2. شريط الفلاتر التفصيلية (العائلة، الماركة، والبحث باسم المنتج) ---
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(8)

        self.combo_family = QComboBox()
        self.combo_family.setMinimumWidth(160)
        self.combo_family.setStyleSheet("QComboBox { padding: 4px; font-size: 12px; }")
        self.combo_family.currentIndexChanged.connect(self.refresh_report)

        self.combo_manuf = QComboBox()
        self.combo_manuf.setMinimumWidth(160)
        self.combo_manuf.setStyleSheet("QComboBox { padding: 4px; font-size: 12px; }")
        self.combo_manuf.currentIndexChanged.connect(self.refresh_report)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher un produit...")
        self.search_input.setStyleSheet("QLineEdit { padding: 4px; font-size: 12px; }")
        self.search_input.textChanged.connect(self.on_search_text_changed)

        filter_bar.addWidget(QLabel("<b>Famille:</b>"))
        filter_bar.addWidget(self.combo_family)
        filter_bar.addWidget(QLabel("<b>Marque:</b>"))
        filter_bar.addWidget(self.combo_manuf)
        filter_bar.addWidget(self.search_input, stretch=1)

        layout.addLayout(filter_bar)

        # --- 3. جدول البيانات ---
        self.table = QTableWidget()
        cols = ["Désignation", "Famille", "Marque", "Qté (Unité Stock)", "Coût Total (TTC)"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)

        self.table.setSortingEnabled(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Désignation يأخذ المساحة المتبقية
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("border: none; gridline-color: #f5f7f9;")
        layout.addWidget(self.table)

        # تحميل خيارات العائلات والمصنعين
        self.load_filter_options()

    def load_filter_options(self):
        # 1. تحميل العائلات
        self.combo_family.blockSignals(True)
        self.combo_family.clear()
        self.combo_family.addItem("🏷️ Toutes les familles", None)
        try:
            families = self.stats_manager.get_all_families()
            for f in families:
                self.combo_family.addItem(f['Family_Name'], f['Family_ID'])
        except Exception as e:
            logging.error(f"Error loading families options in consumption report: {e}")
        self.combo_family.blockSignals(False)

        # 2. تحميل الماركات (المصنعين)
        self.combo_manuf.blockSignals(True)
        self.combo_manuf.clear()
        self.combo_manuf.addItem("🏭 Toutes les marques", None)
        try:
            manufacturers = self.stats_manager.get_all_manufacturers()
            for m in manufacturers:
                self.combo_manuf.addItem(m['Manuf_Name'], m['Manuf_ID'])
        except Exception as e:
            logging.error(f"Error loading manufacturers options in consumption report: {e}")
        self.combo_manuf.blockSignals(False)

    def on_search_text_changed(self):
        self.search_timer.start()

    def update_params(self, d1, d2):
        self.d_from = d1
        self.d_to = d2
        self.refresh_report()

    def refresh_report(self):
        self.table.setSortingEnabled(False)
        report_type = "consumed" if self.filter_type.currentIndex() == 0 else "waste"

        family_id = self.combo_family.currentData()
        manuf_id = self.combo_manuf.currentData()
        txt = self.search_input.text().strip()
        search_text = txt if txt else None

        data = self.stats_manager.get_detailed_consumption_report(
            self.d_from.toString("yyyy-MM-dd"),
            self.d_to.toString("yyyy-MM-dd"),
            report_type=report_type,
            family_id=family_id,
            manuf_id=manuf_id,
            search_text=search_text
        )

        self.table.setRowCount(0)

        for row, r in enumerate(data):
            self.table.insertRow(row)

            # 0. Désignation
            self.table.setItem(row, 0, QTableWidgetItem(str(r.get('Product_Name', '-'))))

            # 1. Famille
            self.table.setItem(row, 1, QTableWidgetItem(str(r.get('Family_Name', '-'))))

            # 2. Marque
            self.table.setItem(row, 2, QTableWidgetItem(str(r.get('Manuf_Name', '-'))))

            # 3. Qté (Unité Stock)
            unit = str(r.get('Stock_Unit') or "Unité")
            qty_str = format_quantity(r.get('total_qty_stock', 0), unit)
            qty_item = QTableWidgetItem(qty_str)
            qty_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, qty_item)

            # 4. Coût Total (TTC)
            cost_val = r.get('total_cost_ttc', 0)
            val_item = QTableWidgetItem(format_money(cost_val, "DA"))
            val_item.setTextAlignment(Qt.AlignCenter)
            val_item.setForeground(QColor("#007572"))
            val_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.table.setItem(row, 4, val_item)

        self.table.setSortingEnabled(True)
