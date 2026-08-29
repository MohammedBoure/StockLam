# ui/widgets/dashboard/statistics_tabs.py

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, 
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, 
    QSplitter, QLineEdit, QAbstractItemView
)
from PySide6.QtCore import Qt, QMargins
from PySide6.QtGui import QColor, QFont, QPainter, QBrush
from PySide6.QtCharts import QChart, QChartView, QPieSeries, QPieSlice

from ui.formatting import format_money, format_quantity

# =============================================================================
# Helper: دالة البحث في الجدول
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


class NumericTableWidgetItem(QTableWidgetItem):
    """Élément de tableau avec tri numérique réel"""
    def __init__(self, display_text, numeric_value):
        super().__init__(display_text)
        self.numeric_value = float(numeric_value) if numeric_value is not None else 0.0

    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self.numeric_value < other.numeric_value
        try:
            val_other = float(str(other.text()).replace(' ', '').replace('DA', '').replace(',', '.'))
            return self.numeric_value < val_other
        except Exception:
            return super().__lt__(other)


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
        self.lbl_summary = QLabel("Valeur Totale: 0,00 DA")
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
                item_val = NumericTableWidgetItem(format_money(val, 'DA'), val)
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
                self.table.setItem(row, 2, NumericTableWidgetItem(format_quantity(qty), qty))
                
                cost = float(item['total_cost_ttc'])
                cost_item = NumericTableWidgetItem(format_money(cost, 'DA'), cost)
                cost_item.setForeground(QColor("#007572"))
                cost_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.table.setItem(row, 3, cost_item)
                
            self.table.setSortingEnabled(True)
            if self.txt_search.text():
                filter_table_rows(self.table, self.txt_search.text())
        except Exception as e:
            logging.error(f"Consumption Tab Error: {e}")


# =============================================================================
# 3. TAB: AUDIT & PRODUITS SUPPRIMÉS
# =============================================================================
class DeletedProductsAuditTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # --- Section 1: Stock Fantôme (Zombie Stock) ---
        lbl_zombie = QLabel("⚠️ STOCK FANTÔME (Produits supprimés avec stock positif)")
        lbl_zombie.setStyleSheet("color: #c0392b; font-weight: bold; font-size: 14px;")
        layout.addWidget(lbl_zombie)
        
        self.table_zombie = QTableWidget()
        self.table_zombie.setColumnCount(5)
        self.table_zombie.setHorizontalHeaderLabels(["Produit", "Lot", "Qté Restante", "Emplacement", "Action Requise"])
        self.table_zombie.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_zombie.setFixedHeight(180) 
        self.table_zombie.setStyleSheet("border: 2px solid #e74c3c;")
        layout.addWidget(self.table_zombie)

        # --- Section 2: Consommation des produits supprimés ---
        header_hist = QHBoxLayout()
        lbl_hist = QLabel("📜 Historique de consommation des produits supprimés")
        lbl_hist.setStyleSheet("color: #7f8c8d; font-weight: bold; font-size: 14px;")
        
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
            # 1. Zombie Stock
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
                self.table_hist.setItem(row, 3, QTableWidgetItem(format_money(val, 'DA')))
                
            if self.txt_search_audit.text():
                filter_table_rows(self.table_hist, self.txt_search_audit.text())
                
        except Exception as e:
            logging.error(f"Audit Tab Error: {e}")


# =============================================================================
# 4. WIDGET: ANALYSE DES PERTES & DÉCHETS (Waste / Rebut)
# =============================================================================
class WasteAnalysisTab(QWidget):
    """
    Onglet d'analyse des pertes et rebuts :
    - Résumé KPI (Perte Totale TTC, Produits Touchés, Total Événements).
    - Tableau détaillé groupé STRICTEMENT par produit unique (1 ligne par produit).
    - Graphique et tableau de répartition par motif de perte.
    - Recherche en temps réel sans doublons de lots ou codes-barres.
    """
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 1. Bandeau supérieur : KPIs & Recherche
        top_bar = QFrame()
        top_bar.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #eef2f5;
                padding: 6px;
            }
        """)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(10, 8, 10, 8)
        top_layout.setSpacing(15)

        # Mini KPI 1: Perte Totale
        self.kpi_total_loss = self._create_mini_kpi("PERTE TOTALE (TTC)", "0,00 DA", "🗑️", "#c0392b", "#fef2f2", "#fecaca")
        # Mini KPI 2: Produits Distincts
        self.kpi_products_count = self._create_mini_kpi("PRODUITS AU REBUT", "0 Produit(s)", "📦", "#2c3e50", "#f8fafc", "#e2e8f0")
        # Mini KPI 3: Événements
        self.kpi_events_count = self._create_mini_kpi("DÉCLARATIONS REBUT", "0 Événement(s)", "📋", "#007572", "#e6f4f3", "#b2dfdb")

        top_layout.addWidget(self.kpi_total_loss)
        top_layout.addWidget(self.kpi_products_count)
        top_layout.addWidget(self.kpi_events_count)
        top_layout.addStretch()

        # Barre de recherche de produits
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Rechercher un produit, famille, motif...")
        self.txt_search.setFixedWidth(280)
        self.txt_search.setStyleSheet("""
            QLineEdit {
                padding: 6px 10px;
                border-radius: 6px;
                border: 1px solid #cbd5e1;
                font-size: 11px;
            }
            QLineEdit:hover, QLineEdit:focus { border-color: #007572; }
        """)
        self.txt_search.textChanged.connect(self._on_search_text_changed)
        top_layout.addWidget(self.txt_search)

        main_layout.addWidget(top_bar)

        # 2. Splitter : Graphique/Motifs à gauche, Tableau des produits à droite
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(8)

        # --- Panneau Gauche : Répartition par Motif ---
        left_container = QFrame()
        left_container.setStyleSheet("background: white; border-radius: 8px; border: 1px solid #eef2f5;")
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        lbl_left_title = QLabel("📊 Répartition par Motif de Perte")
        lbl_left_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #2c3e50;")
        left_layout.addWidget(lbl_left_title)

        self.chart = QChart()
        self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.chart.legend().setVisible(True)
        self.chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        self.chart.legend().setFont(QFont("Segoe UI", 9))
        self.chart.setBackgroundVisible(False)
        self.chart.setMargins(QMargins(0, 0, 0, 0))

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.chart_view.setMinimumHeight(220)
        left_layout.addWidget(self.chart_view, 1)

        # Table des Motifs
        self.table_reasons = QTableWidget()
        self.table_reasons.setColumnCount(3)
        self.table_reasons.setHorizontalHeaderLabels(["Motif de Perte", "Fréq.", "Coût (DA)"])
        self.table_reasons.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_reasons.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_reasons.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_reasons.setAlternatingRowColors(True)
        self.table_reasons.setShowGrid(False)
        self.table_reasons.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_reasons.setStyleSheet("""
            QTableWidget { border: 1px solid #f0f0f0; border-radius: 6px; font-size: 11px; }
            QHeaderView::section { background-color: #f8fafc; border: none; padding: 4px; font-weight: bold; font-size: 10.5px; }
        """)
        self.table_reasons.setMaximumHeight(160)
        left_layout.addWidget(self.table_reasons)

        splitter.addWidget(left_container)

        # --- Panneau Droit : Tableau Détaillé par Produit Unique ---
        right_container = QFrame()
        right_container.setStyleSheet("background: white; border-radius: 8px; border: 1px solid #eef2f5;")
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(8)

        right_header = QHBoxLayout()
        lbl_right_title = QLabel("📋 Détail des Produits Mis au Rebut (Unicité par Produit)")
        lbl_right_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #2c3e50;")
        
        self.lbl_products_summary = QLabel("0 produit(s)")
        self.lbl_products_summary.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b;")

        right_header.addWidget(lbl_right_title)
        right_header.addStretch()
        right_header.addWidget(self.lbl_products_summary)
        right_layout.addLayout(right_header)

        self.table_products = QTableWidget()
        cols = ["Produit", "Famille", "Quantité Perdue", "Événements", "Motifs de Rebut", "Perte Totale TTC (DA)"]
        self.table_products.setColumnCount(len(cols))
        self.table_products.setHorizontalHeaderLabels(cols)

        p_header = self.table_products.horizontalHeader()
        p_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        p_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        p_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        p_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        p_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        p_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        self.table_products.setAlternatingRowColors(True)
        self.table_products.setSortingEnabled(True)
        self.table_products.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_products.setStyleSheet("""
            QTableWidget { border: 1px solid #f0f0f0; border-radius: 6px; font-size: 11px; }
            QHeaderView::section { background-color: #f8fafc; border: none; padding: 6px; font-weight: bold; }
        """)
        right_layout.addWidget(self.table_products, 1)

        splitter.addWidget(right_container)
        splitter.setSizes([380, 620])

        main_layout.addWidget(splitter, 1)

    def _create_mini_kpi(self, title: str, value: str, icon: str, text_color: str, bg_color: str, border_color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 4px 10px;
            }}
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        lbl_icon = QLabel(icon)
        lbl_icon.setStyleSheet("font-size: 16px; border: none; background: transparent;")

        vbox = QVBoxLayout()
        vbox.setSpacing(1)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 9px; font-weight: 700; color: #64748b; border: none; background: transparent;")

        lbl_val = QLabel(value)
        lbl_val.setStyleSheet(f"font-size: 12px; font-weight: 800; color: {text_color}; border: none; background: transparent;")
        lbl_val.setObjectName("kpi_val")

        vbox.addWidget(lbl_title)
        vbox.addWidget(lbl_val)

        layout.addWidget(lbl_icon)
        layout.addLayout(vbox)
        return card

    def _on_search_text_changed(self, text: str):
        filter_table_rows(self.table_products, text)

    def refresh(self, stats_manager, d_from, d_to):
        """Actualise les analyses et le tableau des produits uniques au rebut"""
        try:
            # 1. Données par motif (pour le graphique et le petit tableau)
            reasons_data = stats_manager.get_waste_analysis(d_from, d_to)
            # 2. Données détaillées groupées par produit unique
            products_data = stats_manager.get_waste_products_detailed(d_from, d_to)

            # Calcul des totaux globaux
            total_loss = sum(float(item.get('total_loss_ttc', 0) or 0) for item in products_data)
            total_events = sum(int(item.get('frequency', 0) or 0) for item in products_data)
            distinct_products = len(products_data)

            # Mise à jour des mini-KPIs
            lbl_loss = self.kpi_total_loss.findChild(QLabel, "kpi_val")
            if lbl_loss:
                lbl_loss.setText(format_money(total_loss, 'DA'))

            lbl_prods = self.kpi_products_count.findChild(QLabel, "kpi_val")
            if lbl_prods:
                lbl_prods.setText(f"{distinct_products} Produit(s)")

            lbl_evts = self.kpi_events_count.findChild(QLabel, "kpi_val")
            if lbl_evts:
                lbl_evts.setText(f"{total_events} Événement(s)")

            self.lbl_products_summary.setText(f"{distinct_products} produit(s) impacté(s)")

            # --- Remplissage de la table des motifs & graphique ---
            self.table_reasons.setSortingEnabled(False)
            self.table_reasons.setRowCount(0)
            self.chart.removeAllSeries()
            series = QPieSeries()

            for row, item in enumerate(reasons_data):
                self.table_reasons.insertRow(row)
                r_name = str(item.get('Reason_Name') or "Autre / Non spécifié")
                freq = int(item.get('frequency', 0) or 0)
                loss_val = float(item.get('estimated_loss', 0) or 0)

                self.table_reasons.setItem(row, 0, QTableWidgetItem(r_name))
                it_freq = NumericTableWidgetItem(str(freq), freq)
                it_freq.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_reasons.setItem(row, 1, it_freq)

                it_val = NumericTableWidgetItem(format_money(loss_val, "DA"), loss_val)
                it_val.setForeground(QColor("#c0392b"))
                it_val.setFont(QFont("Segoe UI", 9, QFont.Bold))
                it_val.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table_reasons.setItem(row, 2, it_val)

                if loss_val > 0:
                    pct = (loss_val / total_loss * 100) if total_loss > 0 else 0
                    slice_obj = series.append(f"{r_name} ({pct:.1f}%)", loss_val)
                    if pct > 35:
                        slice_obj.setExploded(True)
                        slice_obj.setLabelVisible(True)

            if not reasons_data or total_loss == 0:
                series.append("Aucune Perte", 1)
                sl = series.slices()[0]
                sl.setBrush(QColor("#ecf0f1"))
                self.chart.setTitle("Aucun rebut sur cette période")
            else:
                self.chart.setTitle(f"Total Pertes : {format_money(total_loss, 'DA')}")

            self.chart.addSeries(series)
            self.table_reasons.setSortingEnabled(True)

            # --- Remplissage du tableau des produits uniques ---
            self.table_products.setSortingEnabled(False)
            self.table_products.setRowCount(0)

            for row, item in enumerate(products_data):
                self.table_products.insertRow(row)

                prod_name = str(item.get('Product_Name') or "")
                fam_name = str(item.get('Family_Name') or "Non définie")
                stock_unit = str(item.get('Stock_Unit') or "U")
                usage_unit = str(item.get('Usage_Unit') or "Tests")
                
                qty_stock = float(item.get('total_qty_stock', 0) or 0)
                qty_usage = float(item.get('total_qty_usage', 0) or 0)
                frequency = int(item.get('frequency', 0) or 0)
                reasons_str = str(item.get('reasons') or "Non spécifié")
                loss_ttc = float(item.get('total_loss_ttc', 0) or 0)

                # Formatage quantité perdue
                if qty_stock > 0 and qty_usage > 0 and stock_unit.lower() != usage_unit.lower():
                    qty_display = f"{format_quantity(qty_stock)} {stock_unit} ({format_quantity(qty_usage)} {usage_unit})"
                elif qty_stock > 0:
                    qty_display = f"{format_quantity(qty_stock)} {stock_unit}"
                else:
                    qty_display = f"{format_quantity(qty_usage)} {usage_unit}"

                # Colonne 0: Nom du Produit
                it_name = QTableWidgetItem(prod_name)
                it_name.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.table_products.setItem(row, 0, it_name)

                # Colonne 1: Famille
                self.table_products.setItem(row, 1, QTableWidgetItem(fam_name))

                # Colonne 2: Quantité Perdue
                it_qty = NumericTableWidgetItem(qty_display, qty_stock if qty_stock > 0 else qty_usage)
                it_qty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_products.setItem(row, 2, it_qty)

                # Colonne 3: Événements
                it_events = NumericTableWidgetItem(str(frequency), frequency)
                it_events.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_products.setItem(row, 3, it_events)

                # Colonne 4: Motifs de Rebut
                it_reasons = QTableWidgetItem(reasons_str)
                it_reasons.setForeground(QColor("#475569"))
                self.table_products.setItem(row, 4, it_reasons)

                # Colonne 5: Perte Totale TTC
                it_loss = NumericTableWidgetItem(format_money(loss_ttc, "DA"), loss_ttc)
                it_loss.setForeground(QColor("#c0392b"))
                it_loss.setFont(QFont("Segoe UI", 9, QFont.Bold))
                it_loss.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table_products.setItem(row, 5, it_loss)

            self.table_products.setSortingEnabled(True)
            # Ré-appliquer la recherche en cours si présente
            if self.txt_search.text():
                filter_table_rows(self.table_products, self.txt_search.text())

        except Exception as e:
            logging.error(f"Erreur Refresh Waste Analysis Tab: {e}", exc_info=True)
