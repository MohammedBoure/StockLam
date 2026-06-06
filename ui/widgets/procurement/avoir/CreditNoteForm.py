import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, 
    QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QMessageBox, 
    QFrame, QCompleter, QTabWidget, QAbstractItemView, QMenu, QDialog, QDialogButtonBox
)
from PySide6.QtCore import Qt, QDate, QStringListModel, Signal
import qtawesome as qta

from ui.widgets.inventory.dialogs import BarcodeLineEdit, NumericSpinBox
from database.system_logger import active_user_id
from .BatchSelectionDialog import BatchSelectionDialog
from ui.formatting import format_money, format_quantity, quantity_to_int

# ==============================================================================
# 2. نموذج الإدخال والتعديل (Form)
# ==============================================================================
class CreditNoteForm(QWidget):
    saved_successfully = Signal()
    request_back = Signal()

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
        
        self.linked_br_id = None  # [NOUVEAU] متغير لتخزين معرف وصل الاستلام المرتبط
        
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

        # [NOUVEAU] إضافة حقل وزر البحث عن وصل الاستلام
        self.txt_search_br = QLineEdit()
        self.txt_search_br.setPlaceholderText("N° Facture ou N° BL...")
        self.btn_search_br = QPushButton("🔍 Lier BR")
        self.btn_search_br.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; padding: 4px 10px; border-radius: 4px;")
        self.btn_search_br.clicked.connect(self.search_and_link_br)

        layout_br_search = QHBoxLayout()
        layout_br_search.setContentsMargins(0, 0, 0, 0)
        layout_br_search.addWidget(self.txt_search_br)
        layout_br_search.addWidget(self.btn_search_br)

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
        form_left.addRow("Lier Réception:", layout_br_search) # [NOUVEAU] إدراج البحث هنا
        form_left.addRow("Réf. Avoir:", self.txt_ref)
        
        form_right = QFormLayout()
        form_right.addRow("Date:", self.date_edit)
        form_right.addRow("Type:", self.combo_type)
        
        self.btn_validate_header = QPushButton("✅ Valider l'En-tête")
        self.btn_validate_header.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
        self.btn_validate_header.clicked.connect(self.handle_header_click)
        form_right.addRow("", self.btn_validate_header)

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
        
        self.btn_back = QPushButton("⬅ Retour à la liste")
        self.btn_back.setStyleSheet("background-color: #34495e; color: white; padding: 10px; font-weight: bold; border-radius: 4px;")
        self.btn_back.clicked.connect(self.request_back.emit)
        
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
        self.btn_save.hide()

        footer_layout.addWidget(self.btn_back) 
        footer_layout.addWidget(self.btn_reset)
        footer_layout.addWidget(self.btn_cancel_edit)
        footer_layout.addStretch()
        footer_layout.addWidget(self.lbl_total)
        footer_layout.addSpacing(20)
        footer_layout.addWidget(self.btn_save)
        main_layout.addWidget(footer_frame)

    def search_and_link_br(self):
        """البحث عن وصل الاستلام وربطه دون قفل الرأس لترك المجال لكتابة المرجع"""
        ref = self.txt_search_br.text().strip()
        if not ref:
            QMessageBox.warning(self, "Attention", "Veuillez entrer le N° de Facture ou BL.")
            return

        try:
            br_data = self.manager.reception.get_reception_with_batches_by_ref(ref)
            
            if not br_data or not br_data.get('Batches'):
                QMessageBox.warning(self, "Introuvable", f"Aucune réception trouvée pour la référence: {ref}")
                return

            self.linked_br_id = br_data['Header']['BR_ID']
            self.populate_from_reception(br_data)
            
            # [تم الحذف] أزلنا كود القفل التلقائي من هنا لتتمكن من كتابة المرجع براحتك
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la recherche: {str(e)}")
    def load_initial_data(self):
        if hasattr(self.manager, 'suppliers'):
            suppliers = self.manager.suppliers.get_all_suppliers()
            self.combo_supplier.clear()
            for s in suppliers:
                self.combo_supplier.addItem(s['Supplier_Name'], s['Supplier_ID'])
        
        if hasattr(self.manager, 'products'):
            self.all_products_cache = self.manager.products.get_all_products()
            self.update_completer(self.all_products_cache)

    def get_current_user_id(self):
        user_id = active_user_id.get()
        if user_id:
            return user_id

        parent_widget = self.parent()
        while parent_widget:
            current_user = getattr(parent_widget, 'current_user', None)
            if isinstance(current_user, dict):
                return current_user.get('User_ID') or current_user.get('id')
            parent_widget = parent_widget.parent()
        return None

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

    def is_reception_scoped(self):
        return bool(self.linked_br_id) or self.current_reception_mode

    def apply_reception_scope(self, data):
        header = data.get('Header', {}) if data else {}
        batches = data.get('Batches', []) if data else []

        self.current_reception_mode = True
        self.reception_batches_cache = batches
        self.linked_br_id = header.get('BR_ID') or self.linked_br_id

        supplier_id = header.get('Supplier_ID')
        idx = self.combo_supplier.findData(supplier_id)
        if idx >= 0:
            self.combo_supplier.setCurrentIndex(idx)
            self.combo_supplier.setEnabled(False)

        br_ref = header.get('Supplier_Invoice_Ref') or header.get('Supplier_BL_Ref') or str(self.linked_br_id or "")
        self.txt_search_br.setText(br_ref)
        self.txt_search_br.setStyleSheet("border: 2px solid #27ae60; background-color: #e8f8f5;")

        self.update_completer(self.reception_batches_cache)
        self.lbl_search_info.setText(f"Recherche (Limitee au Bon #{self.linked_br_id}):")
        self.lbl_search_info.setStyleSheet("color: #d35400; font-weight: bold;")

    def on_barcode_scanned(self):
        text = self.txt_search.text().strip()
        if text: self.find_product(text)

    def on_completer_activated(self, text):
        self.find_product(text)

    def find_product(self, query):
        matches = []
        query = query.lower().strip()
        reception_scoped = self.is_reception_scoped()
        source_list = self.reception_batches_cache if reception_scoped else self.all_products_cache
        
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
            self.lbl_product_name.setText("❌ Produit introuvable" + (" (dans ce Bon)" if reception_scoped else ""))
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
        
        if self.is_reception_scoped():
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
        if self.is_reception_scoped():
            self.txt_lot.setReadOnly(True)

    def load_line_data(self, row, col):
        if col == 7: return 

        item_id = self.table.item(row, 0)
        if not item_id: return

        product_data = item_id.data(Qt.UserRole)
        if not product_data:
            p_id = int(item_id.text())
            source = self.reception_batches_cache if self.is_reception_scoped() else self.all_products_cache
            product_data = next((p for p in source if p['Product_ID'] == p_id), None)
        
        if product_data:
            self.selected_product = product_data
            self.lbl_product_name.setText(f"✏️ MODIFICATION: {product_data['Product_Name']}")
            
            self.txt_lot.setText(self.table.item(row, 2).text().replace("---", ""))
            
            expiry_txt = self.table.item(row, 3).text()
            if expiry_txt and expiry_txt != "---":
                self.date_expiry.setDate(QDate.fromString(expiry_txt, "yyyy-MM-dd"))
            
            self.spin_qty.setValue(quantity_to_int(self.table.item(row, 4).text().replace(",", "")))
            self.spin_price.setValue(float(self.table.item(row, 5).text().replace(",", "")))
            
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

        batch_id = self.selected_product.get('Batch_ID')
        current_qty = self.selected_product.get('Quantity_Current')
        if is_return and batch_id and current_qty is not None and qty > float(current_qty):
            QMessageBox.warning(
                self,
                "Stock insuffisant",
                f"Quantité disponible pour ce lot: {format_quantity(current_qty)}."
            )
            self.spin_qty.setFocus()
            self.spin_qty.selectAll()
            return

        if not self.ensure_credit_note_header_saved():
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
            self.table.item(row, 4).setText(format_quantity(qty))
            self.table.item(row, 5).setText(format_money(price))
            self.table.item(row, 6).setText(format_money(total_line))
            
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
            self.table.setItem(row, 4, QTableWidgetItem(format_quantity(qty)))
            self.table.setItem(row, 5, QTableWidgetItem(format_money(price)))
            self.table.setItem(row, 6, QTableWidgetItem(format_money(total_line)))
            
            btn_del = QPushButton("✖")
            btn_del.setStyleSheet("color: red; border: none; font-weight: bold;")
            btn_del.clicked.connect(lambda checked=False, b=btn_del: self.remove_line(self.row_for_delete_button(b)))
            self.table.setCellWidget(row, 7, btn_del)
        
        self.calculate_total()
        if not self.persist_current_credit_note():
            return
        self.clear_entry_fields()

    def remove_line(self, row):
        if row is None or row < 0 or row >= self.table.rowCount():
            return

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
        self.persist_current_credit_note()

    def row_for_delete_button(self, button):
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 7) is button:
                return row
        return -1

    def calculate_total(self):
        total = 0.0
        for r in range(self.table.rowCount()):
            try:
                total += float(self.table.item(r, 6).text().replace(",", ""))
            except: pass
        self.lbl_total.setText(f"Total TTC: {total:,.2f} DA")

    def clear_entry_fields(self, keep_search=False):
        if not keep_search:
            self.txt_search.clear()
            self.lbl_product_name.setText("---")
            self.selected_product = None
        
        if not self.is_reception_scoped():
            self.txt_lot.clear()
        
        self.spin_qty.setValue(0)
        
        if not self.is_reception_scoped():
            self.spin_price.setValue(0)
            
        self.txt_search.setFocus()
        if self.editing_row is None:
             self.btn_add_line.setText("Ajouter")
             self.btn_add_line.setStyleSheet("background-color: #27ae60; color: white; border-radius: 4px; padding: 10px; font-weight: bold;")

    def reset_form(self):
        self.table.setRowCount(0)
        self.txt_ref.clear()
        self.linked_br_id = None
        self.current_edit_id = None
        self.editing_row = None
        self.selected_product = None
        self.btn_save.setText(" Valider l'Avoir")
        self.btn_save.setStyleSheet("background-color: #2980b9; color: white; padding: 10px 20px; font-size: 14px; font-weight: bold;")
        self.btn_save.hide()
        self.btn_cancel_edit.hide()
        self.txt_search_br.clear()
        self.txt_search_br.setStyleSheet("")
        
        # إعادة تفعيل الحقول
        self.set_header_enabled(True)
        
        self.calculate_total()
        self.current_reception_mode = False
        self.reception_batches_cache = []
        self.lbl_search_info.setText("Recherche (Global):")
        self.lbl_search_info.setStyleSheet("color: black;")
        
        # إعادة نظام البحث الشامل
        self.update_completer(self.all_products_cache)

    def populate_from_reception(self, data):
        """تستقبل البيانات وتجهز النموذج مع ترك حقل المرجع مفتوحاً"""
        try:
            self.reset_form() 
            
            header = data.get('Header', {})
            batches = data.get('Batches', [])

            if not batches:
                QMessageBox.warning(self, "Vide", "Cette réception ne contient aucun produit.")
                return

            self.apply_reception_scope(data)
            # [تعديل] تصفير حقل المرجع ليتم إدخاله يدوياً من الورقة
            self.txt_ref.setText("") 
            self.txt_ref.setPlaceholderText("Saisissez la Réf Avoir ici...")
            
            idx_type = self.combo_type.findData("Return_Goods")
            self.combo_type.setCurrentIndex(idx_type)

            self.lbl_search_info.setText(f"Recherche (Limité au Bon #{header.get('BR_ID')}):")

            QMessageBox.information(self, "Liaison Réussie", 
                f"L'Avoir a été lié au Bon de Réception #{self.linked_br_id}.\n"
                "Veuillez saisir la Réf Avoir manuellement puis cliquez sur 'Valider l'En-tête'.")
                
            # [جديد] نقل المؤشر (Focus) مباشرة إلى حقل Réf Avoir لتسهيل الكتابة الفورية
            self.txt_ref.setFocus()

        except Exception as e:
            logging.error(f"Erreur populate_from_reception: {e}")
            QMessageBox.critical(self, "Erreur", f"Échec du chargement: {str(e)}")

            
    def load_for_edit(self, credit_note_id):
        """تحميل بيانات الإشعار للتعديل وقفل الرأس"""
        try:
            data = self.manager.credit_notes.get_credit_note_details(credit_note_id)
            if not data:
                QMessageBox.warning(self, "Erreur", "Impossible de charger les données.")
                return

            self.reset_form()
            
            header = data['Header']
            details = data['Details']
            
            self.current_edit_id = credit_note_id
            self.linked_br_id = header.get('BR_ID')
            
            self.btn_save.setText("💾 Modifier l'Avoir")
            self.btn_save.setStyleSheet("background-color: #d35400; color: white; padding: 10px 20px; font-weight: bold;")
            self.btn_save.hide()
            self.btn_cancel_edit.show()
            
            idx_supp = self.combo_supplier.findData(header['Supplier_ID'])
            if idx_supp >= 0: self.combo_supplier.setCurrentIndex(idx_supp)
            
            self.txt_ref.setText(header['Credit_Note_Ref'])
            if header.get('Credit_Date'):
                self.date_edit.setDate(QDate.fromString(str(header['Credit_Date']), "yyyy-MM-dd"))
            
            idx_type = self.combo_type.findData(header['Type'])
            if idx_type >= 0: self.combo_type.setCurrentIndex(idx_type)

            if self.linked_br_id:
                br_data = self.manager.reception.get_reception_with_batches_by_id(self.linked_br_id)
                if br_data:
                    self.apply_reception_scope(br_data)
                else:
                    reception_info = self.manager.reception.get_reception_by_id(self.linked_br_id)
                    if reception_info:
                        br_ref = reception_info.get('Supplier_Invoice_Ref') or reception_info.get('Supplier_BL_Ref')
                        self.txt_search_br.setText(br_ref)

            for item in details:
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                item_id = QTableWidgetItem(str(item['Product_ID']))
                item_id.setData(Qt.UserRole, item) 
                
                self.table.setItem(row, 0, item_id)
                self.table.setItem(row, 1, QTableWidgetItem(str(item['Product_Name'])))
                self.table.setItem(row, 2, QTableWidgetItem(item.get('Lot_Number') or "---"))
                self.table.setItem(row, 3, QTableWidgetItem(str(item.get('Expiry_Date')) if item.get('Expiry_Date') else "---"))
                self.table.setItem(row, 4, QTableWidgetItem(format_quantity(item['Qty_Returned'])))
                self.table.setItem(row, 5, QTableWidgetItem(format_money(item['Unit_Price'])))
                self.table.setItem(row, 6, QTableWidgetItem(format_money(item['Line_Total'])))
                
                btn_del = QPushButton("✖")
                btn_del.setStyleSheet("color: red; border: none; font-weight: bold;")
                btn_del.clicked.connect(lambda checked=False, b=btn_del: self.remove_line(self.row_for_delete_button(b)))
                self.table.setCellWidget(row, 7, btn_del)

            self.calculate_total()
            
            # قفل الرأس فور التحميل لمنع التعديل إلا بالضغط على Modifier
            self.set_header_enabled(False)

        except Exception as e:
            logging.error(f"Load Edit Error: {e}")
            QMessageBox.critical(self, "Erreur", str(e))

    def cancel_edit_mode(self):
        self.current_edit_id = None
        self.btn_save.setText("Valider l'Avoir")
        self.btn_save.setStyleSheet("background-color: #2980b9; color: white; padding: 10px 20px; font-weight: bold;")
        self.btn_cancel_edit.hide()

    def build_header_data(self):
        supplier_id = self.combo_supplier.currentData()
        ref = self.txt_ref.text().strip()

        if not supplier_id or not ref:
            QMessageBox.warning(self, "Manquant", "Fournisseur et Reference obligatoires.")
            return None

        total_ttc = float(self.lbl_total.text().replace("Total TTC:", "").replace("DA", "").replace(",", "").strip())
        return {
            'Supplier_ID': supplier_id,
            'Credit_Note_Ref': ref,
            'Credit_Date': self.date_edit.date().toString("yyyy-MM-dd"),
            'Type': self.combo_type.currentData(),
            'Total_Amount_TTC': total_ttc,
            'Total_Amount_HT': total_ttc,
            'Total_TVA': 0,
            'Notes': "Saisie via Interface Avoir",
            'BR_ID': self.linked_br_id
        }

    def build_items_data(self):
        items = []
        for r in range(self.table.rowCount()):
            exp_str = self.table.item(r, 3).text()
            expiry_val = exp_str if exp_str != "---" and exp_str != "None" else None

            item_data = self.table.item(r, 0).data(Qt.UserRole)
            batch_id = item_data.get('Batch_ID') if item_data else None

            items.append({
                'Product_ID': int(self.table.item(r, 0).text()),
                'Batch_ID': batch_id,
                'Lot_Number': self.table.item(r, 2).text(),
                'Expiry_Date': expiry_val,
                'Qty_Returned': float(self.table.item(r, 4).text().replace(",", "")),
                'Unit_Price': float(self.table.item(r, 5).text().replace(",", ""))
            })
        return items

    def mark_credit_note_saved(self, credit_note_id):
        self.current_edit_id = credit_note_id
        self.btn_save.setText("Modifier l'Avoir")
        self.btn_save.setStyleSheet("background-color: #d35400; color: white; padding: 10px 20px; font-weight: bold;")
        self.btn_save.hide()
        self.btn_cancel_edit.hide()

    def save_header_only(self, show_message=True):
        header_data = self.build_header_data()
        if not header_data:
            return False

        try:
            user_id = self.get_current_user_id()
            if self.current_edit_id:
                success, msg = self.manager.credit_notes.update_credit_note(
                    self.current_edit_id, header_data, self.build_items_data(), user_id=user_id
                )
                credit_note_id = self.current_edit_id
            else:
                success, msg, credit_note_id = self.manager.credit_notes.create_credit_note_header(
                    header_data, user_id=user_id
                )

            if success:
                if credit_note_id:
                    self.mark_credit_note_saved(credit_note_id)
                self.set_header_enabled(False)
                if show_message:
                    QMessageBox.information(self, "Succes", "L'en-tete de l'Avoir a ete enregistre.")
                return True

            QMessageBox.critical(self, "Erreur", f"Echec: {msg}")
            return False

        except Exception as e:
            logging.error(f"Header Save Error: {e}")
            QMessageBox.critical(self, "Erreur", str(e))
            return False

    def ensure_credit_note_header_saved(self):
        if self.current_edit_id:
            return True
        return self.save_header_only(show_message=False)

    def reload_current_credit_note(self):
        if self.current_edit_id:
            credit_note_id = self.current_edit_id
            self.load_for_edit(credit_note_id)

    def persist_current_credit_note(self):
        if not self.current_edit_id:
            return self.save_header_only(show_message=False)

        header_data = self.build_header_data()
        if not header_data:
            self.reload_current_credit_note()
            return False

        try:
            user_id = self.get_current_user_id()
            success, msg = self.manager.credit_notes.update_credit_note(
                self.current_edit_id, header_data, self.build_items_data(), user_id=user_id
            )
            if success:
                return True

            QMessageBox.critical(self, "Erreur", f"Echec: {msg}")
            self.reload_current_credit_note()
            return False
        except Exception as e:
            logging.error(f"Immediate Avoir Save Error: {e}")
            QMessageBox.critical(self, "Erreur", str(e))
            self.reload_current_credit_note()
            return False

    def save_credit_note(self):
        header_data = self.build_header_data()
        if not header_data:
            return

        items = self.build_items_data()

        try:
            user_id = self.get_current_user_id()
            if self.current_edit_id:
                success, msg = self.manager.credit_notes.update_credit_note(
                    self.current_edit_id, header_data, items, user_id=user_id
                )
            else:
                success, msg = self.manager.credit_notes.create_credit_note(
                    header_data, items, user_id=user_id
                )

            if success:
                QMessageBox.information(self, "Succes", "L'Avoir a ete enregistre avec succes.")
                self.saved_successfully.emit()
                self.reset_form()
            else:
                QMessageBox.critical(self, "Erreur", f"Echec: {msg}")

        except Exception as e:
            logging.error(f"Save Error: {e}")
            QMessageBox.critical(self, "Erreur", str(e))

    def set_header_enabled(self, enabled: bool):
        """قفل أو فتح حقول رأس الصفحة وتغيير شكل الزر"""
        self.combo_supplier.setEnabled(enabled)
        self.txt_search_br.setEnabled(enabled)
        self.btn_search_br.setEnabled(enabled)
        self.txt_ref.setEnabled(enabled)
        self.date_edit.setEnabled(enabled)
        self.combo_type.setEnabled(enabled)
        
        if enabled:
            self.btn_validate_header.setText("✅ Valider l'En-tête")
            self.btn_validate_header.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
        else:
            self.btn_validate_header.setText("✏️ Modifier l'En-tête")
            self.btn_validate_header.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
    def handle_header_click(self):
        """تبديل حالة الرأس بين التعديل والتأكيد"""
        if "Modifier" in self.btn_validate_header.text():
            # إذا ضغط على Modifier، نفتح الحقول
            self.set_header_enabled(True)
            self.txt_ref.setFocus()
        else:
            # إذا ضغط على Valider، نتحقق من البيانات ثم نقفلها
            if not self.txt_ref.text().strip():
                QMessageBox.warning(self, "Attention", "Veuillez remplir la référence (Réf Avoir).")
                return
            
            self.save_header_only()
