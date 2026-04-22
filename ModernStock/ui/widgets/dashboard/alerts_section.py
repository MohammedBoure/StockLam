import logging
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                               QButtonGroup, QComboBox, QDialog, QTextEdit, QDialogButtonBox)
from PySide6.QtGui import QColor, QFont, QBrush, QIcon
from PySide6.QtCore import Qt

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
        info_layout.addWidget(QLabel(f"<b>Type d'Alerte :</b> {alert_data.get('Type')}"))
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
        # تخصيص نص زر الإغلاق
        close_btn = btn_box.button(QDialogButtonBox.Close)
        close_btn.setText("Fermer")
        layout.addWidget(btn_box)


# =====================================================================
# 2. الواجهة الرئيسية للتنبيهات
# =====================================================================
class AlertsSection(QFrame):
    def __init__(self, data_manager=None):
        super().__init__()
        self.all_data = [] 
        self.active_filter = "All"
        self.init_ui()

    def init_ui(self):
        self.setObjectName("AlertsSection")
        self.setStyleSheet("""
            #AlertsSection { background: white; border-radius: 12px; border: 1px solid #ecf0f1; }
            QTableWidget { border: none; gridline-color: #f8f9fa; selection-background-color: #e0f2f1; selection-color: #000; }
            QHeaderView::section { background-color: #f8f9fa; border: none; font-weight: bold; color: #7f8c8d; padding: 10px; }
            QLineEdit, QComboBox { border: 1px solid #dcdde1; border-radius: 6px; padding: 6px; background: #fdfdfd; }
            QPushButton { padding: 6px 12px; border-radius: 15px; font-weight: bold; border: 1px solid #dcdde1; background: #f8f9fa; color: #7f8c8d; }
            QPushButton:checked { background: #007572; color: white; border: none; }
            QPushButton#btn_urgent:checked { background: #c0392b; }
            QPushButton#btn_anticip:checked { background: #d35400; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # --- أزرار الفلاتر ---
        type_layout = QHBoxLayout()
        self.btn_group = QButtonGroup(self)
        self.btn_all = QPushButton("Tout")
        self.btn_urgent = QPushButton("Urgents 🚨"); self.btn_urgent.setObjectName("btn_urgent")
        self.btn_anticip = QPushButton("Anticipés ⏳"); self.btn_anticip.setObjectName("btn_anticip")
        self.btn_stock = QPushButton("Stocks 📦")

        for i, btn in enumerate([self.btn_all, self.btn_urgent, self.btn_anticip, self.btn_stock]):
            btn.setCheckable(True)
            self.btn_group.addButton(btn, i)
        self.btn_all.setChecked(True)
        self.btn_group.idClicked.connect(self.on_filter_clicked)
        
        type_layout.addWidget(self.btn_all)
        type_layout.addWidget(self.btn_urgent)
        type_layout.addWidget(self.btn_anticip)
        type_layout.addWidget(self.btn_stock)
        type_layout.addStretch()
        layout.addLayout(type_layout)

        # --- فلاتر البحث المتقدم ---
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
        self.table.setColumnCount(5) 
        self.table.setHorizontalHeaderLabels(["PRODUIT", "FAMILLE", "TYPE", "VALEUR", "DÉTAILS & LOGIQUE"])
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
        header.setSectionResizeMode(4, QHeaderView.Stretch)       
        
        layout.addWidget(self.table)

    # =====================================================================
    # مولد الشرح الرياضي للتلميحات (ToolTips) والنافذة (Dialog)
    # =====================================================================
    def generate_math_explanation(self, alert_data):
        type_str = alert_data.get('Type', '')
        raw_val = alert_data.get('RawValue', 0)
        details = alert_data.get('Details', '')

        explanation = f"--- DONNÉES BRUTES ---\n{details}\n\n"
        explanation += "--- CALCUL MATHÉMATIQUE ---\n"

        if "Péremption" in type_str:
            explanation += (
                f"Jours Restants (Valeur actuelle) = {raw_val} jours.\n\n"
                f"Équation Système :\n"
                f"Alerte déclenchée si : [Jours Restants] <= ([Quantité en Stock] × [Jours d'alerte par produit])\n\n"
            )
            if "Anticipée" in type_str:
                explanation += "Conclusion Dynamique : \nLe système vous alerte tôt car vous avez une quantité importante en stock, nécessitant plus de temps pour être consommée avant la date d'expiration."
            else:
                explanation += "Conclusion Urgente : \nLe produit est très proche de sa date d'expiration absolue. Action immédiate requise."
                
        elif "Stock" in type_str:
            explanation += (
                f"Stock Actuel (Valeur) = {raw_val} unités.\n\n"
                f"Équation Système :\n"
                f"Alerte déclenchée si : [Stock Actuel] <= [Niveau de Stock Minimum Configuré]\n\n"
                f"Conclusion : \nLa quantité disponible ne couvre plus le seuil de sécurité."
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
        
        fams = sorted(list(set(a.get('Family', '') for a in self.all_data if a.get('Family'))))
        brands = sorted(list(set(a.get('Brand', '') for a in self.all_data if a.get('Brand'))))
        
        self.combo_fam.addItems(fams)
        self.combo_brand.addItems(brands)
        
        if self.combo_fam.findText(current_fam) >= 0:
            self.combo_fam.setCurrentText(current_fam)
        if self.combo_brand.findText(current_brand) >= 0:
            self.combo_brand.setCurrentText(current_brand)
        
        self.combo_fam.blockSignals(False)
        self.combo_brand.blockSignals(False)

    def on_filter_clicked(self, id):
        filters = ["All", "Urgente", "Anticipée", "Stock"]
        self.active_filter = filters[id]
        self.refresh_table_view()

    def update_alerts(self, alerts):
        self.all_data = alerts
        self.update_filters_lists()
        self.refresh_table_view()

    def refresh_table_view(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        
        txt = self.search_box.text().lower()
        fam = self.combo_fam.currentText()
        brand = self.combo_brand.currentText()
        
        filtered = []
        for a in self.all_data:
            if self.active_filter != "All" and self.active_filter not in a['Type']: continue
            if txt and txt not in a['Product'].lower(): continue
            if fam != "Toutes Familles" and a.get('Family') != fam: continue
            if brand != "Toutes Marques" and a.get('Brand') != brand: continue
            filtered.append(a)
        
        filtered.sort(key=lambda x: x.get('RawValue', 9999))

        for row, a in enumerate(filtered):
            self.table.insertRow(row)
            
            type_str = a['Type']
            details_str = a['Details']
            if "Anticipée" in type_str:
                details_str += " ➔ (Calcul Dynamique)"
            
            p_item = QTableWidgetItem(a['Product'])
            p_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            # حفظ كامل القاموس داخل الخلية الأولى لاستدعائه عند الضغط المزدوج
            p_item.setData(Qt.UserRole, a)
            
            fam_item = QTableWidgetItem(a.get('Family', '-'))
            t_item = QTableWidgetItem(type_str)
            t_item.setTextAlignment(Qt.AlignCenter)
            v_item = QTableWidgetItem()
            v_item.setData(Qt.EditRole, a['RawValue'])
            v_item.setTextAlignment(Qt.AlignCenter)
            d_item = QTableWidgetItem(details_str)

            # توليد الشرح الرياضي ليُعرض عند مرور الماوس (ToolTip)
            math_explanation = self.generate_math_explanation(a)
            
            text_color = QColor("#2c3e50")
            bg_color = QColor(Qt.white)

            if "Urgente" in type_str:
                text_color = QColor("#c0392b")
                bg_color = QColor("#fdedec")
            elif "Anticipée" in type_str:
                text_color = QColor("#d35400")
                bg_color = QColor("#fff5e6")
            elif "Stock" in type_str:
                text_color = QColor("#c2185b")
                bg_color = QColor("#fce4ec")

            # تطبيق الألوان والتلميحات
            for item in [p_item, fam_item, t_item, v_item, d_item]:
                item.setForeground(QBrush(text_color))
                item.setBackground(QBrush(bg_color))
                item.setToolTip(f"<b>{a['Product']}</b>\n\n{math_explanation}")

            self.table.setItem(row, 0, p_item)
            self.table.setItem(row, 1, fam_item)
            self.table.setItem(row, 2, t_item)
            self.table.setItem(row, 3, v_item)
            self.table.setItem(row, 4, d_item)

        self.table.setSortingEnabled(True)

    # =====================================================================
    # حدث الضغط المزدوج لفتح النافذة
    # =====================================================================
    def on_row_double_clicked(self, row, column):
        """يتم استدعاؤها عند الضغط المزدوج على أي صف"""
        # جلب البيانات المخزنة في الخلية الأولى من الصف المضغوط
        product_item = self.table.item(row, 0)
        if product_item:
            alert_data = product_item.data(Qt.UserRole)
            if alert_data:
                # توليد الشرح وفتح النافذة
                explanation = self.generate_math_explanation(alert_data)
                dialog = AlertDetailDialog(alert_data, explanation, self)
                dialog.exec()