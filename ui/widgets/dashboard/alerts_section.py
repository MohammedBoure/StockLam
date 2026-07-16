import logging
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QHBoxLayout, QLabel, QLineEdit,
                               QComboBox, QDialog, QTextEdit, QDialogButtonBox)
from PySide6.QtGui import QColor, QFont, QBrush, QIcon, QCursor
from PySide6.QtCore import Qt

def is_stock_alert(alert_data):
    """Return True when an alert represents a low-stock condition."""
    return (
        isinstance(alert_data, dict)
        and "stock" in str(alert_data.get("Type", "")).lower()
    )

# =====================================================================
# 1. نافذة التفاصيل المنبثقة (Dialog)
# =====================================================================
class AlertDetailDialog(QDialog):
    def __init__(self, alert_data, math_explanation, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Détails de l'alerte : {alert_data.get('Product', 'Inconnu')}")
        self.setMinimumSize(500, 400)
        self.setStyleSheet("""
            QDialog { background-color: #ffffff; }
            QLabel { font-size: 14px; color: #2c3e50; }
            QTextEdit { 
                background-color: #f8f9fa; 
                border: 1px solid #dcdde1; 
                border-radius: 8px; 
                padding: 10px; 
                font-family: Consolas, 'Courier New', monospace;
                font-size: 13px;
                color: #34495e;
            }
            QPushButton { 
                padding: 8px 15px; 
                border-radius: 6px; 
                background: #007572; 
                color: white; 
                font-weight: bold;
            }
            QPushButton:hover { background: #005a58; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # --- معلومات المنتج الأساسية ---
        info_layout = QVBoxLayout()
        lbl_title = QLabel(f"<b>Produit :</b> {alert_data.get('Product')}")
        lbl_title.setFont(QFont("Segoe UI", 12))
        info_layout.addWidget(lbl_title)
        
        info_layout.addWidget(QLabel(f"<b>Famille :</b> {alert_data.get('Family')} | <b>Marque :</b> {alert_data.get('Brand')}"))
        
        type_lbl = QLabel(f"<b>Type d'Alerte :</b> {alert_data.get('Type')}")
        crit_color = "#c0392b" if alert_data.get('Criticality') == 'High' else "#d35400"
        type_lbl.setStyleSheet(f"color: {crit_color}; font-size: 14px;")
        info_layout.addWidget(type_lbl)
        
        layout.addLayout(info_layout)

        # --- قسم الشرح الرياضي ---
        layout.addWidget(QLabel("<b>Logique Mathématique et Détails :</b>"))
        
        txt_details = QTextEdit()
        txt_details.setReadOnly(True)
        txt_details.setPlainText(math_explanation)
        layout.addWidget(txt_details)

        # --- زر الإغلاق ---
        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(self.reject)
        close_btn = btn_box.button(QDialogButtonBox.Close)
        close_btn.setText("Fermer")
        close_btn.setCursor(QCursor(Qt.PointingHandCursor))
        layout.addWidget(btn_box)


# =====================================================================
# 2. الواجهة الرئيسية للتنبيهات
# =====================================================================
class AlertsSection(QFrame):
    def __init__(self, data_manager=None):
        super().__init__()
        self.all_data = [] 
        self.init_ui()

    def init_ui(self):
        self.setObjectName("AlertsSection")
        self.setStyleSheet("""
            #AlertsSection { background: white; border-radius: 12px; border: 1px solid #ecf0f1; }
            QTableWidget { border: none; gridline-color: #f8f9fa; selection-background-color: #e0f2f1; selection-color: #000; }
            QHeaderView::section { background-color: #f8f9fa; border: none; font-weight: bold; color: #7f8c8d; padding: 10px; }
            QLineEdit, QComboBox { border: 1px solid #dcdde1; border-radius: 6px; padding: 6px; background: #fdfdfd; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # --- Filtres de recherche ---

        filters_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Recherche par nom...")
        self.search_box.setFixedWidth(200)
        self.search_box.textChanged.connect(self.refresh_table_view)
        
        self.combo_fam = QComboBox()
        self.combo_fam.addItem("Toutes Familles")
        self.combo_fam.setFixedWidth(180)
        self.combo_fam.currentTextChanged.connect(self.refresh_table_view)
        
        self.combo_brand = QComboBox()
        self.combo_brand.addItem("Toutes Marques")
        self.combo_brand.setFixedWidth(180)
        self.combo_brand.currentTextChanged.connect(self.refresh_table_view)

        filters_layout.addWidget(self.search_box)
        filters_layout.addWidget(QLabel("Famille:"))
        filters_layout.addWidget(self.combo_fam)
        filters_layout.addWidget(QLabel("Marque:"))
        filters_layout.addWidget(self.combo_brand)
        filters_layout.addStretch()
        layout.addLayout(filters_layout)

        # --- الجدول ---
        self.table = QTableWidget()
        self.table.setColumnCount(4) 
        self.table.setHorizontalHeaderLabels(["PRODUIT", "FAMILLE", "MARQUE", "QUANTITÉ"])
        self.table.setAlternatingRowColors(False) 
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        
        # ربط حدث الضغط المزدوج
        self.table.cellDoubleClicked.connect(self.on_row_double_clicked)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)       
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) 
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents) 
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents) 
        
        layout.addWidget(self.table)

    # =====================================================================
    # مولد الشرح الرياضي للتلميحات (ToolTips) والنافذة (Dialog)
    # =====================================================================
    def generate_math_explanation(self, alert_data):
        details = alert_data.get('Details', '')
        total_qty = alert_data.get('TotalQty', 0)
        explanation = f'--- DONN\u00c9ES BRUTES ---\n{details}\n\n'
        explanation += '--- CALCUL MATH\u00c9MATIQUE ---\n'
        explanation += (
            f'Quantit\u00e9 Totale = {total_qty} unit\u00e9s.\n\n'
            'Alerte d\u00e9clench\u00e9e si : [Quantit\u00e9 Totale] <= [Niveau de Stock Minimum Configur\u00e9]\n\n'
            'Conclusion :\nLa quantit\u00e9 disponible est inf\u00e9rieure ou \u00e9gale au seuil de s\u00e9curit\u00e9.'
        )
        return explanation

    # =====================================================================
    # وظائف التحكم والجدول
    # =====================================================================
    def update_filters_lists(self):
        current_fam = self.combo_fam.currentText()
        current_brand = self.combo_brand.currentText()
        
        self.combo_fam.blockSignals(True)
        self.combo_brand.blockSignals(True)
        
        self.combo_fam.clear()
        self.combo_brand.clear()
        
        self.combo_fam.addItem("Toutes Familles")
        self.combo_brand.addItem("Toutes Marques")
        
        fams = sorted(list(set(a.get('Family') for a in self.all_data if a.get('Family'))))
        brands = set()
        for a in self.all_data:
            b_list = a.get('Brand', '').split(',')
            for b in b_list:
                b = b.strip()
                if b: brands.add(b)
        brands = sorted(list(brands))
        
        self.combo_fam.addItems(fams)
        self.combo_brand.addItems(brands)
        
        if current_fam in fams: self.combo_fam.setCurrentText(current_fam)
        if current_brand in brands: self.combo_brand.setCurrentText(current_brand)
        
        self.combo_fam.blockSignals(False)
        self.combo_brand.blockSignals(False)

    def update_alerts(self, alerts_data):
        """يتم استدعاؤها من المكون الأب عند جلب البيانات الجديدة"""
        self.all_data = [
            alert for alert in (alerts_data or [])
            if is_stock_alert(alert)
        ]
        self.update_filters_lists()
        self.refresh_table_view()

    def refresh_table_view(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        
        txt = self.search_box.text().strip().lower()
        fam = self.combo_fam.currentText()
        brand = self.combo_brand.currentText()
        
        filtered = []
        for a in self.all_data:
            if txt and txt not in a['Product'].lower(): continue
            if fam != "Toutes Familles" and a.get('Family') != fam: continue
            
            # Since brand can be a comma separated list now (grouped by product)
            b_list = [x.strip() for x in a.get('Brand', '').split(',')]
            if brand != "Toutes Marques" and brand not in b_list: continue
            
            filtered.append(a)
        
        filtered.sort(key=lambda x: x.get('RawValue', 9999))

        for row, a in enumerate(filtered):
            self.table.insertRow(row)
            
            total_qty = a.get('TotalQty', 0)
            
            p_item = QTableWidgetItem(a['Product'])
            p_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            p_item.setData(Qt.UserRole, a)
            
            fam_item = QTableWidgetItem(a.get('Family', '-'))
            marq_item = QTableWidgetItem(a.get('Brand', '-'))
            
            # Qty Column
            v_item = QTableWidgetItem()
            v_item.setData(Qt.EditRole, float(total_qty))
            v_item.setTextAlignment(Qt.AlignCenter)
            v_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            
            math_explanation = self.generate_math_explanation(a)
            
            text_color = QColor("#c2185b")
            bg_color = QColor("#fce4ec")

            for item in [p_item, fam_item, marq_item, v_item]:
                item.setForeground(QBrush(text_color))
                item.setBackground(QBrush(bg_color))
                item.setToolTip(f"<b>{a['Product']}</b>\n\n{math_explanation}")

            self.table.setItem(row, 0, p_item)
            self.table.setItem(row, 1, fam_item)
            self.table.setItem(row, 2, marq_item)
            self.table.setItem(row, 3, v_item)

        self.table.setSortingEnabled(True)

    # =====================================================================
    # حدث الضغط المزدوج لفتح النافذة
    # =====================================================================
    def on_row_double_clicked(self, row, column):
        product_item = self.table.item(row, 0)
        if product_item:
            alert_data = product_item.data(Qt.UserRole)
            if alert_data:
                explanation = self.generate_math_explanation(alert_data)
                dialog = AlertDetailDialog(alert_data, explanation, self)
                dialog.exec()