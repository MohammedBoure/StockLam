from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
                               QLineEdit, QComboBox, QDialogButtonBox, QDateEdit, 
                               QTableWidget, QTableWidgetItem, QWidget, QLabel, 
                               QSpinBox, QPushButton, QHeaderView, QTextEdit, QFrame, 
                               QMessageBox, QCompleter, QGridLayout) 
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont

from ui.widgets.master_data.dialogs import BaseDialog

class PurchaseOrderDialog(BaseDialog):
    def __init__(self, suppliers_list, products_list, parent=None, data=None, read_only=False):
        self.read_only = read_only
        self.suppliers = suppliers_list
        self.products = products_list
        self.data = data
        
        self.batches_data = [] 

        if self.read_only:
            title = f"Détails de la Commande #{data.get('PO_ID', '---')} (Lecture seule)"
        elif data:
            title = "Modifier la Commande"
        else:
            title = "Nouvelle Commande d'Achat"

        super().__init__(title, parent)
        
        self.showMaximized() 
        self.setMinimumSize(1200, 800)
        
        self.init_ui()
        
        if self.data:
            self.populate_form()
            # En mode modification, on suppose que l'en-tête est valide, donc on le verrouille
            self.validate_header()
        else:
            # En mode création, on verrouille la partie détails au début
            self.toggle_inputs_state(False)
            
        if self.read_only:
            self.set_read_only_mode()

        self.editing_row = -1

    def init_ui(self):
        # استخدام التخطيط الرئيسي للنموذج الموجود في BaseDialog
        main_layout = QVBoxLayout(self.form_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # === 1. Informations Générales (En-tête) ===
        top_section = QGroupBox("Informations Générales")
        top_section.setStyleSheet("""
            QGroupBox { font-weight: bold; font-size: 13px; border: 1px solid #dcdcdc; border-radius: 8px; margin-top: 10px; padding-top: 5px; }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 5px; }
        """)
        top_grid = QGridLayout(top_section)
        top_grid.setContentsMargins(15, 10, 15, 10)
        top_grid.setHorizontalSpacing(20)
        top_grid.setVerticalSpacing(8)

        # السطر الأول: Fournisseur + Notes
        top_grid.addWidget(QLabel("Fournisseur * :"), 0, 0)
        self.supplier_combo = QComboBox()
        self.supplier_combo.setMinimumHeight(38)
        for s in self.suppliers:
            self.supplier_combo.addItem(s['Supplier_Name'], s['Supplier_ID'])
        top_grid.addWidget(self.supplier_combo, 0, 1)

        top_grid.addWidget(QLabel("Notes :"), 0, 2)
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Notes générales...")
        self.notes_input.setMinimumHeight(38)
        top_grid.addWidget(self.notes_input, 0, 3)

        # السطر الثاني: التواريخ
        top_grid.addWidget(QLabel("Date Commande :"), 1, 0)
        self.order_date = QDateEdit(QDate.currentDate())
        self.order_date.setCalendarPopup(True)
        self.order_date.setMinimumHeight(38)
        top_grid.addWidget(self.order_date, 1, 1)

        top_grid.addWidget(QLabel("Livraison Prévue :"), 1, 2)
        self.delivery_date = QDateEdit(QDate.currentDate().addDays(7))
        self.delivery_date.setCalendarPopup(True)
        self.delivery_date.setMinimumHeight(38)
        top_grid.addWidget(self.delivery_date, 1, 3)

        # السطر الثالث: أزرار التحكم في الرأس (Validation / Unlock)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 10, 0, 0)
        
        self.btn_validate_header = QPushButton("Valider & Verrouiller")
        self.btn_validate_header.setCursor(Qt.PointingHandCursor)
        self.btn_validate_header.setMinimumHeight(38)
        self.btn_validate_header.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; border-radius: 4px; padding: 0 15px;")
        self.btn_validate_header.clicked.connect(self.validate_header)
        
        self.btn_unlock_header = QPushButton("✏️ Modifier l'en-tête")
        self.btn_unlock_header.setCursor(Qt.PointingHandCursor)
        self.btn_unlock_header.setMinimumHeight(38)
        self.btn_unlock_header.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; border-radius: 4px; padding: 0 15px;")
        self.btn_unlock_header.setVisible(False)
        self.btn_unlock_header.clicked.connect(self.unlock_header)

        btn_layout.addWidget(self.btn_validate_header)
        btn_layout.addWidget(self.btn_unlock_header)
        btn_layout.addStretch() # لدفع الأزرار لليسار
        
        top_grid.addLayout(btn_layout, 2, 0, 1, 4)

        main_layout.addWidget(top_section, stretch=0)

        # === 2. Section Ajout / Modification (Groupée) ===
        self.add_group = QGroupBox("Ajout d'un Article")
        self.add_group.setStyleSheet("""
            QGroupBox { font-weight: bold; font-size: 13px; border: 1px solid #dcdcdc; border-radius: 8px; margin-top: 5px; padding-top: 5px; }
        """)
        add_layout = QVBoxLayout(self.add_group)
        
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Produit :"))
        self.product_search = QLineEdit()
        self.product_search.setPlaceholderText("🔍 Rechercher un produit...")
        self.product_search.setMinimumHeight(38)
        row1.addWidget(self.product_search, stretch=4)

        row1.addWidget(QLabel("Unité :"))
        self.unit_combo = QComboBox()
        self.unit_combo.setMinimumHeight(38)
        self.unit_combo.setFixedWidth(120)
        self.unit_combo.setEnabled(False)
        row1.addWidget(self.unit_combo)

        row1.addWidget(QLabel("Qté :"))
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 99999)
        self.qty_spin.setMinimumHeight(38)
        self.qty_spin.setFixedWidth(100)
        row1.addWidget(self.qty_spin)

        row1.addWidget(QLabel("Note :"))
        self.item_note_input = QLineEdit()
        self.item_note_input.setMinimumHeight(38)
        row1.addWidget(self.item_note_input, stretch=2)

        # أزرار الإضافة والتحكم
        self.add_or_save_btn = QPushButton("➕ Ajouter")
        self.btn_edit_line = QPushButton("✏️ Modifier")
        self.btn_delete_line = QPushButton("🗑️ Supprimer")
        
        for btn in [self.add_or_save_btn, self.btn_edit_line, self.btn_delete_line]:
            btn.setMinimumHeight(38)
            btn.setFixedWidth(120)
            row1.addWidget(btn)

        add_layout.addLayout(row1)
        main_layout.addWidget(self.add_group, stretch=0)

        # === 3. Tableau des Articles (Groupé) ===
        self.table_group = QGroupBox("Liste des Articles Commandés")
        self.table_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #dcdcdc; border-radius: 8px; }")
        table_layout = QVBoxLayout(self.table_group)

        self.lines_table = QTableWidget()
        cols = ["Désignation", "Marque", "Unité", "Qté", "Observation"]
        self.lines_table.setColumnCount(len(cols))
        self.lines_table.setHorizontalHeaderLabels(cols)

        header = self.lines_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)      
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Fixed)       
        header.setSectionResizeMode(3, QHeaderView.Fixed)       
        header.setSectionResizeMode(4, QHeaderView.Stretch)     
        
        self.lines_table.setColumnWidth(2, 120)
        self.lines_table.setColumnWidth(3, 100)

        self.lines_table.setAlternatingRowColors(True)
        self.lines_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.lines_table.setSelectionMode(QTableWidget.SingleSelection)
        
        table_layout.addWidget(self.lines_table)
        
        main_layout.addWidget(self.table_group, stretch=10) 

        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.product_search.setCompleter(self.completer)
        self.update_search_data(self.products)
        self.completer.activated.connect(self.on_completer_activated)
        self.add_or_save_btn.clicked.connect(self.handle_add_or_save)
        self.btn_edit_line.clicked.connect(self.edit_selected_line)
        self.btn_delete_line.clicked.connect(self.delete_selected_line)
        self.lines_table.selectionModel().selectionChanged.connect(self.update_action_buttons_state)
        
        self.update_action_buttons_state()

    def toggle_inputs_state(self, enabled):
        """Active ou désactive la zone de saisie des produits"""
        self.add_group.setEnabled(enabled)
        self.table_group.setEnabled(enabled)

    def validate_header(self):
        """Valide les informations de l'en-tête et déverrouille la saisie des produits"""
        if not self.supplier_combo.currentData():
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner un fournisseur.")
            return

        # Verrouiller l'en-tête
        self.supplier_combo.setEnabled(False)
        self.notes_input.setReadOnly(True)
        self.order_date.setReadOnly(True)
        self.delivery_date.setReadOnly(True)
        
        # Changer les boutons
        self.btn_validate_header.setVisible(False)
        self.btn_unlock_header.setVisible(True)
        
        # Déverrouiller la partie détails
        self.toggle_inputs_state(True)

    def unlock_header(self):
        """Déverrouille l'en-tête pour modification et verrouille la saisie des produits"""
        # Déverrouiller l'en-tête
        self.supplier_combo.setEnabled(True)
        self.notes_input.setReadOnly(False)
        self.order_date.setReadOnly(False)
        self.delivery_date.setReadOnly(False)
        
        # Changer les boutons
        self.btn_validate_header.setVisible(True)
        self.btn_unlock_header.setVisible(False)
        
        # Verrouiller la partie détails pour forcer la revalidation
        self.toggle_inputs_state(False)

    def update_search_data(self, products_list):
        self.product_data_map = {}
        suggestions = []
        for p in products_list:
            brand = p.get('Manuf_Name') or "---"
            display_name = f"{p['Product_Name']} ({brand})"
            self.product_data_map[display_name] = p
            suggestions.append(display_name)
        
        from PySide6.QtCore import QStringListModel
        self.completer.setModel(QStringListModel(suggestions))

    def handle_enter_pressed(self):
        text = self.product_search.text().strip()
        if not text:
            return
        if text in self.product_data_map:
            self.on_completer_activated(text)
        elif self.completer.completionCount() > 0:
            self.on_completer_activated(self.completer.currentCompletion())

    def on_completer_activated(self, text):
        product_data = self.product_data_map.get(text)
        if product_data:
            self.unit_combo.clear()
            # تجميع الوحدات المتاحة مع ضمان وجودها
            raw_units = [product_data.get('Ordering_Unit'), product_data.get('Stock_Unit'), product_data.get('Usage_Unit')]
            units = sorted(list(set([u for u in raw_units if u]))) # استخدام sorted لتوحيد الترتيب
            
            if not units:
                units = ['U']
                
            self.unit_combo.addItems(units)
            self.unit_combo.setCurrentIndex(0)
            self.unit_combo.setEnabled(True)
            self.qty_spin.setValue(1)
            self.item_note_input.clear()
            self.add_or_save_btn.setText("➕ Ajouter")
            self.editing_row = -1

    def handle_add_or_save(self):
        product_text = self.product_search.text().strip()
        if not product_text:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner un produit.")
            return

        product_data = self.product_data_map.get(product_text)
        if not product_data:
            QMessageBox.warning(self, "Attention", "Produit non reconnu.")
            return

        if not self.unit_combo.isEnabled() or self.unit_combo.count() == 0:
            QMessageBox.warning(self, "Attention", "Aucune unité disponible.")
            return

        qty = self.qty_spin.value()
        
        # [FIX] قراءة الوحدة الحالية والتأكد من أنها نص صالح
        unit = self.unit_combo.currentText().strip()
        note = self.item_note_input.text().strip()

        if self.editing_row == -1:
            self.add_line(product_data, qty, unit, note)
        else:
            self.update_line(self.editing_row, qty, unit, note)

        self.reset_input_fields()

    def reset_input_fields(self):
        self.product_search.clear()
        self.unit_combo.clear()
        self.unit_combo.setEnabled(False)
        self.qty_spin.setValue(1)
        self.item_note_input.clear()
        self.add_or_save_btn.setText("➕ Ajouter")
        self.editing_row = -1

    def add_line(self, product_data, qty=1, unit='', item_note=""):
        # التحقق من التكرار
        for r in range(self.lines_table.rowCount()):
            if self.lines_table.item(r, 0) and self.lines_table.item(r, 0).data(Qt.UserRole) == product_data['Product_ID']:
                QMessageBox.information(self, "Information", "Cet article est déjà ajouté.")
                return

        row = self.lines_table.rowCount()
        self.lines_table.insertRow(row)

        name_item = QTableWidgetItem(product_data['Product_Name'])
        name_item.setData(Qt.UserRole, product_data['Product_ID'])
        self.lines_table.setItem(row, 0, name_item)

        brand_text = product_data.get('Manuf_Name') or "---"
        self.lines_table.setItem(row, 1, QTableWidgetItem(brand_text))

        # --- [FIX CORE] منطق صارم لاختيار الوحدة ---
        final_unit_text = "U" # قيمة افتراضية للطوارئ
        
        # 1. إذا اختار المستخدم وحدة (تم تمريرها للدالة)، نستخدمها فوراً
        if unit and str(unit).strip():
            final_unit_text = str(unit).strip()
        # 2. إذا لم يختار (فارغة)، نستخدم الافتراضي من قاعدة البيانات
        elif product_data:
            final_unit_text = product_data.get('Ordering_Unit', 'U')
        # ---------------------------------------------------
        
        self.lines_table.setItem(row, 2, QTableWidgetItem(final_unit_text))

        qty_item = QTableWidgetItem(str(qty))
        qty_item.setTextAlignment(Qt.AlignCenter)
        qty_item.setFlags(qty_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.lines_table.setItem(row, 3, qty_item)

        self.lines_table.setItem(row, 4, QTableWidgetItem(item_note))

        self.lines_table.scrollToBottom()
        self.update_action_buttons_state()

    def edit_selected_line(self):
        row = self.lines_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Information", "Veuillez sélectionner un article.")
            return
        self.edit_line(row)

    def delete_selected_line(self):
        row = self.lines_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Information", "Veuillez sélectionner un article.")
            return

        reply = QMessageBox.question(self, "Confirmation", "Supprimer cet article ?")
        if reply == QMessageBox.Yes:
            self.lines_table.removeRow(row)
            self.update_action_buttons_state()
            if self.editing_row == row:
                self.reset_input_fields()

    def edit_line(self, row):
        product_item = self.lines_table.item(row, 0)
        if not product_item:
            return

        product_id = product_item.data(Qt.UserRole)
        product_data = next((p for p in self.products if p['Product_ID'] == product_id), None)
        if not product_data:
            return

        brand = product_data.get('Manuf_Name') or "---"
        self.product_search.setText(f"{product_data['Product_Name']} ({brand})")

        self.unit_combo.clear()
        raw_units = [product_data.get('Ordering_Unit'), product_data.get('Stock_Unit'), product_data.get('Usage_Unit')]
        units = sorted(list(set([u for u in raw_units if u])))
        if not units: units = ['U']
        self.unit_combo.addItems(units)
        
        # استرجاع الوحدة الحالية من الجدول
        current_unit = self.lines_table.item(row, 2).text()
        if current_unit:
            if self.unit_combo.findText(current_unit) == -1:
                self.unit_combo.addItem(current_unit)
            self.unit_combo.setCurrentText(current_unit)
            
        self.unit_combo.setEnabled(True)

        self.qty_spin.setValue(int(self.lines_table.item(row, 3).text() or 1))
        self.item_note_input.setText(self.lines_table.item(row, 4).text() or "")

        self.add_or_save_btn.setText("💾 Enregistrer")
        self.editing_row = row

    def update_line(self, row, qty, unit, note):
        # التحديث المباشر للجدول يضمن ظهور ما اختاره المستخدم
        self.lines_table.item(row, 2).setText(str(unit).strip())
        self.lines_table.item(row, 3).setText(str(qty))
        self.lines_table.item(row, 4).setText(note)

    def update_action_buttons_state(self):
        has_selection = self.lines_table.currentRow() >= 0
        self.btn_edit_line.setEnabled(has_selection)
        self.btn_delete_line.setEnabled(has_selection)

    def set_read_only_mode(self):
        self.supplier_combo.setEnabled(False)
        self.order_date.setReadOnly(True)
        self.delivery_date.setReadOnly(True)
        self.notes_input.setReadOnly(True)
        
        # Masquer les boutons de validation/modification en lecture seule
        self.btn_validate_header.setVisible(False)
        self.btn_unlock_header.setVisible(False)
        
        self.product_search.setEnabled(False)
        self.unit_combo.setEnabled(False)
        self.qty_spin.setEnabled(False)
        self.item_note_input.setEnabled(False)
        self.add_or_save_btn.setEnabled(False)
        self.btn_edit_line.setEnabled(False)
        self.btn_delete_line.setEnabled(False)
        self.lines_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        save_btn = self.buttons.button(QDialogButtonBox.Save)
        if save_btn: save_btn.setVisible(False)
        cancel_btn = self.buttons.button(QDialogButtonBox.Cancel)
        if cancel_btn: cancel_btn.setText("Fermer")

    def populate_form(self):
        if not self.data: return
        
        idx = self.supplier_combo.findData(self.data.get('Supplier_ID'))
        if idx >= 0: self.supplier_combo.setCurrentIndex(idx)
        
        if self.data.get('Order_Date'):
            self.order_date.setDate(QDate.fromString(str(self.data['Order_Date']), "yyyy-MM-dd"))
        if self.data.get('Expected_Delivery_Date'):
            self.delivery_date.setDate(QDate.fromString(str(self.data['Expected_Delivery_Date']), "yyyy-MM-dd"))
        
        self.notes_input.setText(self.data.get('Notes', ''))
        
        for item in self.data.get('Details', []):
            prod_id = item.get('Product_ID')
            full_prod = next((p for p in self.products if p['Product_ID'] == prod_id), None)
            if full_prod:
                self.add_line(
                    full_prod,
                    item.get('Qty_Ordered', 1),
                    item.get('Ordering_Unit', full_prod.get('Ordering_Unit', 'U')),
                    item.get('Item_Note', "")
                )

    def accept(self):
        data = self.get_data()
        if data is None:
            return
        super().accept()

    def get_data(self):
        if self.read_only: 
            return None

        # Pas besoin de vérifier le fournisseur ici car c'est déjà fait dans validate_header
        # Mais on vérifie si l'utilisateur a déverrouillé sans revalider ?
        # Logiquement, s'il a déverrouillé, la partie "détails" est désactivée,
        # donc il ne peut pas cliquer sur "Sauvegarder" si le bouton Sauvegarder est en dehors...
        # Le BaseDialog a ses boutons en bas.
        
        # Vérifions si l'en-tête est verrouillé (donc validé)
        if self.supplier_combo.isEnabled():
             QMessageBox.warning(self, "Attention", "Veuillez valider les informations de l'en-tête avant de sauvegarder.")
             return None

        items = []
        for row in range(self.lines_table.rowCount()):
            product_item = self.lines_table.item(row, 0)
            if not product_item: 
                continue

            qty_text = self.lines_table.item(row, 3).text()
            try:
                qty_val = int(qty_text)
                if qty_val <= 0:
                    raise ValueError
            except:
                QMessageBox.warning(self, "Attention", f"Quantité invalide à la ligne {row+1}.")
                return None

            unit_text = self.lines_table.item(row, 2).text() or "U"
            note_text = self.lines_table.item(row, 4).text() or ""

            items.append({
                "Product_ID": product_item.data(Qt.UserRole),
                "Qty_Ordered": qty_val,
                "Ordering_Unit": unit_text,
                "Item_Note": note_text,
                "Unit_Price_HT": 0.0,
                "Discount_Percent": 0.0,
                "Tax_Rate_Percent": 0.0
            })

        if not items:
            QMessageBox.warning(self, "Attention", "Veuillez ajouter au moins un article.")
            return None

        return {
            "Supplier_ID": self.supplier_combo.currentData(),
            "Order_Date": self.order_date.date().toString("yyyy-MM-dd"),
            "Expected_Delivery_Date": self.delivery_date.date().toString("yyyy-MM-dd"),
            "Notes": self.notes_input.text(),
            "Items": items,
            "PO_ID": self.data.get('PO_ID') if self.data else None
        }