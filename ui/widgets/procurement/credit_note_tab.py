import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, 
    QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QMessageBox, 
    QFrame, QCompleter, QTabWidget, QAbstractItemView, QMenu, QDialog, QDialogButtonBox
)
from PySide6.QtCore import Qt, QDate, QStringListModel, Signal
from PySide6.QtGui import QColor, QFont, QBrush, QAction
import qtawesome as qta

from ui.widgets.inventory.dialogs import BarcodeLineEdit, NumericSpinBox

# ==============================================================================
# 1. نافذة اختيار الدفعة (Batch Selection)
# ==============================================================================
class BatchSelectionDialog(QDialog):
    def __init__(self, matches, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sélectionner le Lot")
        self.resize(650, 300)
        self.selected_item = None
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Ce produit existe en plusieurs lots/dates.\nVeuillez choisir la ligne exacte à retourner :"))
        
        self.table = QTableWidget()
        cols = ["Désignation", "Lot", "Péremption", "Qté Reçue", "Prix Unitaire"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        
        self.table.setRowCount(len(matches))
        for i, item in enumerate(matches):
            self.table.setItem(i, 0, QTableWidgetItem(str(item.get('Product_Name'))))
            self.table.setItem(i, 1, QTableWidgetItem(str(item.get('Lot_Number'))))
            self.table.setItem(i, 2, QTableWidgetItem(str(item.get('Expiry_Date') or '---')))
            
            qty = item.get('Quantity_Initial') or item.get('Qty_Received') or 0
            self.table.setItem(i, 3, QTableWidgetItem(str(qty)))
            
            price = float(item.get('Unit_Price_Received') or item.get('Purchase_Price') or 0)
            self.table.setItem(i, 4, QTableWidgetItem(f"{price:.2f}"))
            
            # تخزين البيانات الكاملة لاستخدامها عند الاختيار
            self.table.item(i, 0).setData(Qt.UserRole, item)
            
        self.table.doubleClicked.connect(self.accept_selection)
        layout.addWidget(self.table)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def accept_selection(self):
        row = self.table.currentRow()
        if row >= 0:
            self.selected_item = self.table.item(row, 0).data(Qt.UserRole)
            self.accept()
        else:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner une ligne.")

# ==============================================================================
# 2. نموذج الإدخال والتعديل (Form)
# ==============================================================================
class CreditNoteForm(QWidget):
    # إشارة لإخبار القائمة بالعودة وتحديث البيانات بعد الحفظ الناجح
    saved_successfully = Signal()

    def __init__(self, data_manager):
        super().__init__()
        self.manager = data_manager
        
        # قوائم التخزين المؤقت
        self.all_products_cache = []       
        self.reception_batches_cache = []  
        self.current_reception_mode = False 
        
        self.current_edit_id = None 
        self.editing_row = None
        self.selected_product = None 
        
        self.init_ui()
        self.load_initial_data()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        # --- Header ---
        header_group = QGroupBox("📄 Informations Générales")
        header_group.setStyleSheet("QGroupBox { font-weight: bold; color: #2c3e50; border: 1px solid #bdc3c7; border-radius: 6px; margin-top: 10px; }")
        header_layout = QHBoxLayout(header_group)

        self.combo_supplier = QComboBox()
        self.combo_supplier.setPlaceholderText("Sélectionner un fournisseur...")
        self.combo_supplier.setMinimumWidth(250)

        self.txt_ref = QLineEdit()
        self.txt_ref.setPlaceholderText("Ex: AVOIR-2025/001")
        
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setFixedWidth(120)

        self.combo_type = QComboBox()
        self.combo_type.addItem("📦 Retour Marchandise (Avec Stock)", "Return_Goods")
        self.combo_type.addItem("💰 Correction Financière (Prix)", "Price_Correction")
        self.combo_type.currentIndexChanged.connect(self.toggle_stock_fields)

        form_left = QFormLayout()
        form_left.addRow("Fournisseur:", self.combo_supplier)
        form_left.addRow("Réf. Avoir:", self.txt_ref)
        
        form_right = QFormLayout()
        form_right.addRow("Date:", self.date_edit)
        form_right.addRow("Type:", self.combo_type)

        header_layout.addLayout(form_left)
        header_layout.addLayout(form_right)
        main_layout.addWidget(header_group)

        # --- Entry Area ---
        entry_group = QGroupBox("📦 Ajout des Lignes")
        entry_group.setStyleSheet("QGroupBox { font-weight: bold; color: #007572; border: 1px solid #007572; border-radius: 6px; margin-top: 10px; }")
        entry_layout = QHBoxLayout(entry_group)

        search_layout = QVBoxLayout()
        self.lbl_search_info = QLabel("Recherche (Global):")
        self.txt_search = BarcodeLineEdit()
        self.txt_search.setPlaceholderText("Scan ou tapez ici...")
        self.txt_search.returnPressed.connect(self.on_barcode_scanned)
        
        self.completer = QCompleter([])
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.completer.activated.connect(self.on_completer_activated)
        self.txt_search.setCompleter(self.completer)

        self.lbl_product_name = QLabel("---")
        self.lbl_product_name.setStyleSheet("color: #2980b9; font-weight: bold; font-size: 13px;")
        
        search_layout.addWidget(self.lbl_search_info)
        search_layout.addWidget(self.txt_search)
        search_layout.addWidget(self.lbl_product_name)
        
        stock_layout = QVBoxLayout()
        self.txt_lot = QLineEdit()
        self.txt_lot.setPlaceholderText("N° Lot")
        self.date_expiry = QDateEdit(QDate.currentDate().addYears(1))
        self.date_expiry.setCalendarPopup(True)
        self.date_expiry.setDisplayFormat("yyyy-MM-dd")
        
        stock_form = QFormLayout()
        stock_form.addRow("Lot:", self.txt_lot)
        stock_form.addRow("Péremption:", self.date_expiry)
        stock_layout.addLayout(stock_form)

        qty_layout = QVBoxLayout()
        self.spin_qty = NumericSpinBox() 
        self.spin_qty.setRange(0, 99999)
        self.spin_price = QDoubleSpinBox()
        self.spin_price.setRange(0, 99999999)
        self.spin_price.setDecimals(2)
        
        qty_form = QFormLayout()
        qty_form.addRow("Quantité:", self.spin_qty)
        qty_form.addRow("Prix Unitaire:", self.spin_price)
        qty_layout.addLayout(qty_form)

        self.btn_add_line = QPushButton("Ajouter")
        self.btn_add_line.setStyleSheet("background-color: #27ae60; color: white; border-radius: 4px; padding: 10px; font-weight: bold;")
        self.btn_add_line.clicked.connect(self.add_line_to_table)

        entry_layout.addLayout(search_layout, stretch=2)
        entry_layout.addLayout(stock_layout, stretch=1)
        entry_layout.addLayout(qty_layout, stretch=1)
        entry_layout.addWidget(self.btn_add_line)
        main_layout.addWidget(entry_group)

        # --- Table ---
        self.table = QTableWidget()
        cols = ["ID", "Désignation", "Lot", "Péremption", "Qté", "P.U (HT)", "Total Ligne", "Action"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnHidden(0, True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        self.table.cellClicked.connect(self.load_line_data)
        
        main_layout.addWidget(self.table)

        # --- Footer ---
        footer_frame = QFrame()
        footer_frame.setStyleSheet("background-color: #ecf0f1; border-radius: 6px; padding: 5px;")
        footer_layout = QHBoxLayout(footer_frame)
        
        self.btn_reset = QPushButton("Réinitialiser")
        self.btn_reset.setStyleSheet("background-color: #95a5a6; color: white;")
        self.btn_reset.clicked.connect(self.reset_form)
        
        self.btn_cancel_edit = QPushButton("Annuler Modif")
        self.btn_cancel_edit.setStyleSheet("background-color: #e74c3c; color: white;")
        self.btn_cancel_edit.clicked.connect(self.cancel_edit_mode)
        self.btn_cancel_edit.hide()
        
        self.lbl_total = QLabel("Total TTC: 0.00 DA")
        self.lbl_total.setStyleSheet("font-size: 18px; font-weight: 900; color: #c0392b;")
        
        self.btn_save = QPushButton(" Valider l'Avoir")
        self.btn_save.setIcon(qta.icon("fa5s.save", color="white"))
        self.btn_save.setStyleSheet("background-color: #2980b9; color: white; padding: 10px 20px; font-size: 14px; font-weight: bold;")
        self.btn_save.clicked.connect(self.save_credit_note)

        footer_layout.addWidget(self.btn_reset)
        footer_layout.addWidget(self.btn_cancel_edit)
        footer_layout.addStretch()
        footer_layout.addWidget(self.lbl_total)
        footer_layout.addSpacing(20)
        footer_layout.addWidget(self.btn_save)
        main_layout.addWidget(footer_frame)

    def load_initial_data(self):
        if hasattr(self.manager, 'suppliers'):
            suppliers = self.manager.suppliers.get_all_suppliers()
            self.combo_supplier.clear()
            for s in suppliers:
                self.combo_supplier.addItem(s['Supplier_Name'], s['Supplier_ID'])
        
        if hasattr(self.manager, 'products'):
            self.all_products_cache = self.manager.products.get_all_products()
            self.update_completer(self.all_products_cache)

    def update_completer(self, product_list):
        search_list = []
        seen = set()
        for p in product_list:
            name = p.get('Product_Name', '')
            barcode = p.get('Barcode') or p.get('Internal_Barcode')
            
            if name and name not in seen:
                search_list.append(name)
                seen.add(name)
            if barcode and barcode not in seen:
                search_list.append(str(barcode))
                seen.add(barcode)
                
        self.completer.setModel(QStringListModel(search_list))

    def on_barcode_scanned(self):
        text = self.txt_search.text().strip()
        if text: self.find_product(text)

    def on_completer_activated(self, text):
        self.find_product(text)

    def find_product(self, query):
        matches = []
        query = query.lower().strip()
        source_list = self.reception_batches_cache if self.current_reception_mode else self.all_products_cache
        
        for p in source_list:
            p_name = str(p.get('Product_Name', '')).lower()
            p_code = str(p.get('Barcode', '')).lower()
            p_code2 = str(p.get('Internal_Barcode', '')).lower()
            
            if query == p_code or query == p_code2 or query == p_name:
                matches.append(p)
            elif query in p_name and len(query) > 3:
                matches.append(p)

        if not matches:
            self.selected_product = None
            self.lbl_product_name.setText("❌ Produit introuvable" + (" (dans ce Bon)" if self.current_reception_mode else ""))
            self.clear_entry_fields(keep_search=True)
            return

        selected_match = None
        if len(matches) == 1:
            selected_match = matches[0]
        else:
            dialog = BatchSelectionDialog(matches, self)
            if dialog.exec():
                selected_match = dialog.selected_item
            else:
                return 

        if selected_match:
            self._apply_selected_product(selected_match)

    def _apply_selected_product(self, found):
        self.selected_product = found
        self.lbl_product_name.setText(f"✅ {found['Product_Name']}")
        
        lot = found.get('Lot_Number', '')
        price = float(found.get('Unit_Price_Received') or found.get('Purchase_Price') or found.get('Unit_Price', 0))
        
        raw_expiry = found.get('Expiry_Date')
        if raw_expiry and str(raw_expiry) != 'None' and str(raw_expiry) != '---':
            try:
                expiry_date = QDate.fromString(str(raw_expiry)[:10], "yyyy-MM-dd")
                self.date_expiry.setDate(expiry_date)
            except: pass
        
        if self.current_reception_mode:
            self.txt_lot.setText(lot)
            self.txt_lot.setReadOnly(True)
            self.txt_lot.setStyleSheet("background-color: #ecf0f1; color: #7f8c8d;")
            self.date_expiry.setReadOnly(True)
            self.spin_price.setValue(price)
            self.spin_price.setReadOnly(True)
        else:
            self.txt_lot.setText(lot) 
            self.txt_lot.setReadOnly(False)
            self.txt_lot.setStyleSheet("")
            self.date_expiry.setReadOnly(False)
            self.spin_price.setValue(price)
            self.spin_price.setReadOnly(False)
            
        self.spin_qty.setFocus()
        self.spin_qty.selectAll()

    def toggle_stock_fields(self):
        is_return = (self.combo_type.currentData() == "Return_Goods")
        self.txt_lot.setEnabled(is_return)
        self.date_expiry.setEnabled(is_return)
        if self.current_reception_mode:
            self.txt_lot.setReadOnly(True)

    def load_line_data(self, row, col):
        if col == 7: return 

        item_id = self.table.item(row, 0)
        if not item_id: return

        product_data = item_id.data(Qt.UserRole)
        if not product_data:
            p_id = int(item_id.text())
            source = self.reception_batches_cache if self.current_reception_mode else self.all_products_cache
            product_data = next((p for p in source if p['Product_ID'] == p_id), None)
        
        if product_data:
            self.selected_product = product_data
            self.lbl_product_name.setText(f"✏️ MODIFICATION: {product_data['Product_Name']}")
            
            self.txt_lot.setText(self.table.item(row, 2).text().replace("---", ""))
            
            expiry_txt = self.table.item(row, 3).text()
            if expiry_txt and expiry_txt != "---":
                self.date_expiry.setDate(QDate.fromString(expiry_txt, "yyyy-MM-dd"))
            
            self.spin_qty.setValue(float(self.table.item(row, 4).text()))
            self.spin_price.setValue(float(self.table.item(row, 5).text()))
            
            self.editing_row = row
            self.btn_add_line.setText("Modifier la ligne")
            self.btn_add_line.setStyleSheet("background-color: #f39c12; color: white; border-radius: 4px; padding: 10px; font-weight: bold;")
            
            self.spin_qty.setFocus()
            self.spin_qty.selectAll()

    def add_line_to_table(self):
        if not self.selected_product:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un produit.")
            return

        qty = self.spin_qty.value()
        if qty <= 0:
            QMessageBox.warning(self, "Erreur", "La quantité doit être supérieure à 0.")
            return

        price = self.spin_price.value()
        lot = self.txt_lot.text().strip()
        is_return = (self.combo_type.currentData() == "Return_Goods")
        
        if is_return and not lot:
            QMessageBox.warning(self, "Attention", "Le N° de Lot est obligatoire pour un retour.")
            self.txt_lot.setFocus()
            return
            
        expiry = self.date_expiry.date().toString("yyyy-MM-dd") if is_return else None
        total_line = qty * price

        if self.editing_row is not None:
            row = self.editing_row
            self.table.item(row, 0).setText(str(self.selected_product['Product_ID']))
            self.table.item(row, 0).setData(Qt.UserRole, self.selected_product)
            self.table.item(row, 1).setText(self.selected_product['Product_Name'])
            self.table.item(row, 2).setText(lot if is_return else "---")
            self.table.item(row, 3).setText(expiry if is_return else "---")
            self.table.item(row, 4).setText(str(qty))
            self.table.item(row, 5).setText(f"{price:.2f}")
            self.table.item(row, 6).setText(f"{total_line:.2f}")
            
            self.editing_row = None
            self.btn_add_line.setText("Ajouter")
            self.btn_add_line.setStyleSheet("background-color: #27ae60; color: white; border-radius: 4px; padding: 10px; font-weight: bold;")
            
        else:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            item_id = QTableWidgetItem(str(self.selected_product['Product_ID']))
            item_id.setData(Qt.UserRole, self.selected_product) 
            
            self.table.setItem(row, 0, item_id)
            self.table.setItem(row, 1, QTableWidgetItem(self.selected_product['Product_Name']))
            self.table.setItem(row, 2, QTableWidgetItem(lot if is_return else "---"))
            self.table.setItem(row, 3, QTableWidgetItem(expiry if is_return else "---"))
            self.table.setItem(row, 4, QTableWidgetItem(str(qty)))
            self.table.setItem(row, 5, QTableWidgetItem(f"{price:.2f}"))
            self.table.setItem(row, 6, QTableWidgetItem(f"{total_line:.2f}"))
            
            btn_del = QPushButton("✖")
            btn_del.setStyleSheet("color: red; border: none; font-weight: bold;")
            btn_del.clicked.connect(lambda checked=False, r=row: self.remove_line(r)) 
            self.table.setCellWidget(row, 7, btn_del)
        
        self.calculate_total()
        self.clear_entry_fields()

    def remove_line(self, row):
        confirm = QMessageBox.question(
            self, "Confirmation", 
            "Voulez-vous vraiment retirer cette ligne ?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.No:
            return

        self.table.removeRow(row)
        if self.editing_row == row:
            self.editing_row = None
            self.btn_add_line.setText("Ajouter")
            self.btn_add_line.setStyleSheet("background-color: #27ae60; color: white; border-radius: 4px; padding: 10px; font-weight: bold;")
            self.clear_entry_fields()
            
        self.calculate_total()

    def calculate_total(self):
        total = 0.0
        for r in range(self.table.rowCount()):
            try:
                total += float(self.table.item(r, 6).text())
            except: pass
        self.lbl_total.setText(f"Total TTC: {total:,.2f} DA")

    def clear_entry_fields(self, keep_search=False):
        if not keep_search:
            self.txt_search.clear()
            self.lbl_product_name.setText("---")
            self.selected_product = None
        
        if not self.current_reception_mode:
            self.txt_lot.clear()
        
        self.spin_qty.setValue(0)
        
        if not self.current_reception_mode:
            self.spin_price.setValue(0)
            
        self.txt_search.setFocus()
        if self.editing_row is None:
             self.btn_add_line.setText("Ajouter")
             self.btn_add_line.setStyleSheet("background-color: #27ae60; color: white; border-radius: 4px; padding: 10px; font-weight: bold;")

    def reset_form(self):
        self.table.setRowCount(0)
        self.txt_ref.clear()
        self.calculate_total()
        self.combo_supplier.setEnabled(True)
        self.current_reception_mode = False
        self.reception_batches_cache = []
        self.lbl_search_info.setText("Recherche (Global):")
        self.lbl_search_info.setStyleSheet("color: black;")
        
        self.txt_lot.setReadOnly(False)
        self.date_expiry.setReadOnly(False)
        self.spin_price.setReadOnly(False)
        self.txt_lot.setStyleSheet("")
        
        self.editing_row = None
        self.btn_add_line.setText("Ajouter")
        
        self.cancel_edit_mode() 
        self.update_completer(self.all_products_cache)

    def populate_from_reception(self, data):
        self.reset_form() 
        
        header = data.get('Header', {})
        batches = data.get('Batches', [])

        if not batches:
            QMessageBox.warning(self, "Vide", "Cette réception ne contient aucun produit.")
            return

        self.current_reception_mode = True
        self.reception_batches_cache = batches
        
        supplier_id = header.get('Supplier_ID')
        idx = self.combo_supplier.findData(supplier_id)
        if idx >= 0: 
            self.combo_supplier.setCurrentIndex(idx)
            self.combo_supplier.setEnabled(False)

        orig_ref = header.get('Supplier_Invoice_Ref', '') or str(header.get('BR_ID'))
        self.txt_ref.setText(f"AVOIR-{orig_ref}")
        
        idx_type = self.combo_type.findData("Return_Goods")
        self.combo_type.setCurrentIndex(idx_type)

        self.update_completer(self.reception_batches_cache)
        self.lbl_search_info.setText(f"Recherche (Limité au Bon #{header.get('BR_ID')}):")
        self.lbl_search_info.setStyleSheet("color: #d35400; font-weight: bold;")
        
        QMessageBox.information(self, "Mode Avoir", 
            "Mode création d'Avoir activé pour ce Bon de Réception.\n"
            "Veuillez scanner ou rechercher les produits à retourner.")
        
        self.txt_search.setFocus()

    def load_for_edit(self, credit_note_id):
        try:
            data = self.manager.credit_notes.get_credit_note_details(credit_note_id)
            if not data:
                QMessageBox.warning(self, "Erreur", "Impossible de charger les données.")
                return

            self.reset_form()
            
            header = data['Header']
            details = data['Details']
            
            self.current_edit_id = credit_note_id
            self.btn_save.setText("💾 Modifier l'Avoir")
            self.btn_save.setStyleSheet("background-color: #d35400; color: white; padding: 10px 20px; font-weight: bold;")
            self.btn_cancel_edit.show()
            
            idx_supp = self.combo_supplier.findData(header['Supplier_ID'])
            if idx_supp >= 0: self.combo_supplier.setCurrentIndex(idx_supp)
            
            self.txt_ref.setText(header['Credit_Note_Ref'])
            if header.get('Credit_Date'):
                self.date_edit.setDate(QDate.fromString(str(header['Credit_Date']), "yyyy-MM-dd"))
            
            idx_type = self.combo_type.findData(header['Type'])
            if idx_type >= 0: self.combo_type.setCurrentIndex(idx_type)

            for item in details:
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                lot = item.get('Lot_Number') or "---"
                expiry = str(item.get('Expiry_Date')) if item.get('Expiry_Date') else "---"
                
                item_id = QTableWidgetItem(str(item['Product_ID']))
                item_id.setData(Qt.UserRole, item) 
                
                self.table.setItem(row, 0, item_id)
                self.table.setItem(row, 1, QTableWidgetItem(str(item['Product_Name'])))
                self.table.setItem(row, 2, QTableWidgetItem(lot))
                self.table.setItem(row, 3, QTableWidgetItem(expiry))
                self.table.setItem(row, 4, QTableWidgetItem(str(item['Qty_Returned'])))
                self.table.setItem(row, 5, QTableWidgetItem(str(item['Unit_Price'])))
                self.table.setItem(row, 6, QTableWidgetItem(str(item['Line_Total'])))
                
                btn_del = QPushButton("✖")
                btn_del.setStyleSheet("color: red; border: none; font-weight: bold;")
                btn_del.clicked.connect(lambda checked=False, r=row: self.remove_line(r)) 
                self.table.setCellWidget(row, 7, btn_del)

            self.calculate_total()
            QMessageBox.information(self, "Mode Modification", f"Modification de l'Avoir #{credit_note_id}")

        except Exception as e:
            logging.error(f"Load Edit Error: {e}")
            QMessageBox.critical(self, "Erreur", str(e))

    def cancel_edit_mode(self):
        self.current_edit_id = None
        self.btn_save.setText("Valider l'Avoir")
        self.btn_save.setStyleSheet("background-color: #2980b9; color: white; padding: 10px 20px; font-weight: bold;")
        self.btn_cancel_edit.hide()

    def save_credit_note(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Vide", "Aucune ligne à enregistrer.")
            return
        
        supplier_id = self.combo_supplier.currentData()
        ref = self.txt_ref.text().strip()
        
        if not supplier_id or not ref:
            QMessageBox.warning(self, "Manquant", "Fournisseur et Référence obligatoires.")
            return

        total_ttc = float(self.lbl_total.text().replace("Total TTC:", "").replace("DA", "").replace(",", "").strip())
        
        header_data = {
            'Supplier_ID': supplier_id,
            'Credit_Note_Ref': ref,
            'Credit_Date': self.date_edit.date().toString("yyyy-MM-dd"),
            'Type': self.combo_type.currentData(),
            'Total_Amount_TTC': total_ttc,
            'Total_Amount_HT': total_ttc,
            'Notes': "Saisie via Interface Avoir"
        }

        items = []
        for r in range(self.table.rowCount()):
            exp_str = self.table.item(r, 3).text()
            expiry_val = exp_str if exp_str != "---" and exp_str != "None" else None

            item_data = self.table.item(r, 0).data(Qt.UserRole)
            batch_id = item_data.get('Batch_ID') if item_data else None
            # ---------------------------

            items.append({
                'Product_ID': int(self.table.item(r, 0).text()),
                'Batch_ID': batch_id, # الآن نرسل المعرف الدقيق لقاعدة البيانات!
                'Lot_Number': self.table.item(r, 2).text(),
                'Expiry_Date': expiry_val,
                'Qty_Returned': float(self.table.item(r, 4).text()),
                'Unit_Price': float(self.table.item(r, 5).text())
            })

        try:
            if self.current_edit_id:
                success, msg = self.manager.credit_notes.update_credit_note(
                    self.current_edit_id, header_data, items, user_id=1
                )
            else:
                success, msg = self.manager.credit_notes.create_credit_note(
                    header_data, items, user_id=1
                )

            if success:
                QMessageBox.information(self, "Succès", "L'Avoir a été enregistré avec succès.")
                self.saved_successfully.emit() # إبلاغ القائمة لتحديث نفسها
                self.reset_form()
            else:
                QMessageBox.critical(self, "Erreur", f"Échec: {msg}")

        except Exception as e:
            logging.error(f"Save Error: {e}")
            QMessageBox.critical(self, "Erreur", str(e))


# ==============================================================================
# 3. قائمة العرض (List)
# ==============================================================================
class CreditNoteList(QWidget):
    request_edit = Signal(int) 
    request_new = Signal() # إشارة جديدة لطلب إنشاء جديد

    def __init__(self, data_manager):
        super().__init__()
        self.manager = data_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # --- شريط الفلترة العلوي ---
        filter_group = QGroupBox("🔍 Recherche et Filtres")
        filter_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #ccc; border-radius: 5px; margin-top: 5px; }")
        filter_layout = QHBoxLayout(filter_group)
        
        self.date_from = QDateEdit(QDate.currentDate().addMonths(-1)) 
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        
        btn_search = QPushButton("Rechercher")
        btn_search.setIcon(qta.icon("fa5s.search"))
        btn_search.setStyleSheet("background-color: #2980b9; color: white; padding: 5px 15px;")
        btn_search.clicked.connect(self.load_data)

        # زر إنشاء جديد
        btn_new = QPushButton("➕ Nouveau Avoir")
        btn_new.setStyleSheet("background-color: #27ae60; color: white; padding: 5px 15px; font-weight: bold;")
        btn_new.clicked.connect(self.request_new.emit)

        filter_layout.addWidget(QLabel("Du:"))
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(QLabel("Au:"))
        filter_layout.addWidget(self.date_to)
        filter_layout.addWidget(btn_search)
        filter_layout.addStretch() 
        filter_layout.addWidget(btn_new) # إضافة الزر هنا
        
        layout.addWidget(filter_group)

        self.table = QTableWidget()
        cols = ["ID", "Réf. Avoir", "Fournisseur", "Date", "Type", "Montant TTC"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setColumnHidden(0, True) 
        
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.doubleClicked.connect(self.trigger_edit)
        
        layout.addWidget(self.table)
        
        self.load_data()

    def show_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid(): return

        menu = QMenu(self)
        action_edit = QAction("Modifier", self)
        action_edit.triggered.connect(self.trigger_edit)
        menu.addAction(action_edit)

        action_delete = QAction(" Supprimer", self)
        action_delete.triggered.connect(self.trigger_delete)
        menu.addAction(action_delete)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def get_selected_id(self):
        row = self.table.currentRow()
        if row < 0: return None
        item = self.table.item(row, 0)
        return int(item.text()) if item else None

    def trigger_edit(self):
        cn_id = self.get_selected_id()
        if cn_id:
            self.request_edit.emit(cn_id)

    def trigger_delete(self):
        cn_id = self.get_selected_id()
        if not cn_id: return
        
        reply = QMessageBox.question(
            self, "Confirmation", 
            "Voulez-vous vraiment supprimer cet Avoir ?\n\n"
            "⚠️ Attention : Si c'est un retour marchandise, le stock sera restauré.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if hasattr(self.manager.credit_notes, 'delete_credit_note'):
                success, msg = self.manager.credit_notes.delete_credit_note(cn_id, user_id=1)
                if success:
                    self.load_data()
                else:
                    QMessageBox.critical(self, "Erreur", msg)

    def load_data(self):
        try:
            self.table.setRowCount(0)
            d_start = self.date_from.date().toString("yyyy-MM-dd")
            d_end = self.date_to.date().toString("yyyy-MM-dd")
            
            notes = []
            if hasattr(self.manager.credit_notes, 'get_credit_notes_by_date'):
                notes = self.manager.credit_notes.get_credit_notes_by_date(d_start, d_end)
            elif hasattr(self.manager.credit_notes, 'get_all_credit_notes'):
                all_notes = self.manager.credit_notes.get_all_credit_notes()
                for n in all_notes:
                    if d_start <= str(n['Credit_Date']) <= d_end:
                        notes.append(n)
            
            for row, note in enumerate(notes):
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(str(note['Credit_Note_ID'])))
                self.table.setItem(row, 1, QTableWidgetItem(str(note['Credit_Note_Ref'])))
                self.table.setItem(row, 2, QTableWidgetItem(str(note.get('Supplier_Name', '---'))))
                self.table.setItem(row, 3, QTableWidgetItem(str(note['Credit_Date'])))
                
                type_map = {"Return_Goods": "Retour Marchandise", "Price_Correction": "Correction Prix"}
                type_display = type_map.get(note['Type'], note['Type'])
                
                self.table.setItem(row, 4, QTableWidgetItem(type_display))
                
                amt = float(note.get('Total_Amount_TTC') or 0)
                amt_item = QTableWidgetItem(f"{amt:,.2f} DA")
                amt_item.setForeground(QBrush(QColor("#c0392b")))
                self.table.setItem(row, 5, amt_item)

        except Exception as e:
            logging.error(f"Error loading credit notes: {e}")
            QMessageBox.warning(self, "Erreur", f"Erreur de chargement: {e}")

# ==============================================================================
# 4. الواجهة الرئيسية للتبويب (Main Tab)
# ==============================================================================
class CreditNoteTab(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.manager = data_manager
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabWidget::pane { border: 0; }")
        
        self.form_tab = CreditNoteForm(data_manager)
        self.list_tab = CreditNoteList(data_manager)
        
        # [تعديل] عكس الترتيب: القائمة (Historique) هي الأولى، والنموذج (Saisie) هو الثاني
        self.tabs.addTab(self.list_tab, "📜 Avoirs")  # Index 0
        self.tabs.addTab(self.form_tab, "📝 Saisie Avoir") # Index 1
        
        # ربط إشارة طلب التعديل
        self.list_tab.request_edit.connect(self.handle_edit_request)
        
        # [تعديل] ربط إشارة طلب الجديد
        self.list_tab.request_new.connect(self.handle_new_request)
        
        # [تعديل] ربط إشارة الحفظ الناجح للعودة للقائمة وتحديثها
        self.form_tab.saved_successfully.connect(self.on_save_success)
        
        self.tabs.currentChanged.connect(self.on_tab_change)
        layout.addWidget(self.tabs)

    def on_tab_change(self, index):
        # Index 0 هو الآن Historique
        if index == 0: self.list_tab.load_data()

    def refresh_history(self):
        self.list_tab.load_data()

    def handle_edit_request(self, credit_note_id):
        """التعامل مع طلب التعديل القادم من القائمة"""
        self.tabs.setCurrentIndex(1) # الانتقال لتبويب النموذج (Index 1)
        self.form_tab.load_for_edit(credit_note_id)

    def handle_new_request(self):
        """التعامل مع طلب إنشاء جديد"""
        self.form_tab.reset_form()
        self.tabs.setCurrentIndex(1) # الانتقال لتبويب النموذج

    def on_save_success(self):
        """العودة للقائمة بعد الحفظ"""
        self.list_tab.load_data()
        self.tabs.setCurrentIndex(0) # العودة للقائمة

    def populate_from_reception(self, data):
        """
        [تعديل] للحفاظ على التوافق مع الاستدعاء الخارجي.
        عند طلب إنشاء Avoir من استلام، نذهب للنموذج (Index 1) ونعبئه.
        """
        self.tabs.setCurrentIndex(1) 
        self.form_tab.populate_from_reception(data)