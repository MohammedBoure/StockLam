import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, 
    QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QMessageBox, 
    QFrame, QCompleter, QTabWidget, QAbstractItemView
)
from PySide6.QtCore import Qt, QDate, QStringListModel
from PySide6.QtGui import QColor, QFont, QBrush
import qtawesome as qta

from ui.widgets.inventory.dialogs import BarcodeLineEdit, NumericSpinBox

class CreditNoteForm(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.manager = data_manager
        
        # قوائم التخزين المؤقت
        self.all_products_cache = []       # كل المنتجات (للوضع العادي)
        self.reception_batches_cache = []  # منتجات الـ Bon المحدد (للوضع المقيد)
        self.current_reception_mode = False # هل نحن بصدد إنشاء avoir لـ bon محدد؟
        
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
        self.lbl_search_info = QLabel("Recherche (Global):") # سيتغير النص ديناميكياً
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
        self.spin_qty.setRange(0, 99999) # السماح بـ 0 وأعداد عشرية
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
        main_layout.addWidget(self.table)

        # --- Footer ---
        footer_frame = QFrame()
        footer_frame.setStyleSheet("background-color: #ecf0f1; border-radius: 6px; padding: 5px;")
        footer_layout = QHBoxLayout(footer_frame)
        
        self.btn_reset = QPushButton("Réinitialiser Mode")
        self.btn_reset.setStyleSheet("background-color: #95a5a6; color: white;")
        self.btn_reset.clicked.connect(self.reset_form)
        
        self.lbl_total = QLabel("Total TTC: 0.00 DA")
        self.lbl_total.setStyleSheet("font-size: 18px; font-weight: 900; color: #c0392b;")
        
        self.btn_save = QPushButton("💾 Valider l'Avoir")
        self.btn_save.setIcon(qta.icon("fa5s.save", color="white"))
        self.btn_save.setStyleSheet("background-color: #2980b9; color: white; padding: 10px 20px; font-size: 14px; font-weight: bold;")
        self.btn_save.clicked.connect(self.save_credit_note)

        footer_layout.addWidget(self.btn_reset)
        footer_layout.addStretch()
        footer_layout.addWidget(self.lbl_total)
        footer_layout.addSpacing(20)
        footer_layout.addWidget(self.btn_save)
        main_layout.addWidget(footer_frame)

    def load_initial_data(self):
        """تحميل الموردين والمنتجات العامة"""
        if hasattr(self.manager, 'suppliers'):
            suppliers = self.manager.suppliers.get_all_suppliers()
            self.combo_supplier.clear()
            for s in suppliers:
                self.combo_supplier.addItem(s['Supplier_Name'], s['Supplier_ID'])
        
        if hasattr(self.manager, 'products'):
            self.all_products_cache = self.manager.products.get_all_products()
            self.update_completer(self.all_products_cache)

    def update_completer(self, product_list):
        """تحديث قائمة الاكمال التلقائي بناءً على المصدر (الكل أو الاستلام المحدد)"""
        search_list = []
        seen = set()
        for p in product_list:
            # نتأكد من عدم تكرار الأسماء في القائمة
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
        """
        البحث الذكي:
        - إذا كنا في وضع (Avoir sur Bon): نبحث فقط في self.reception_batches_cache
        - إذا كنا في وضع عادي: نبحث في self.all_products_cache
        """
        found = None
        query = query.lower()
        
        # تحديد المصدر
        source_list = self.reception_batches_cache if self.current_reception_mode else self.all_products_cache
        
        for p in source_list:
            p_name = str(p.get('Product_Name', '')).lower()
            p_code = str(p.get('Barcode', '')).lower()
            p_code2 = str(p.get('Internal_Barcode', '')).lower()
            
            if query == p_code or query == p_code2 or query == p_name:
                found = p
                break
        
        if found:
            self.selected_product = found
            self.lbl_product_name.setText(f"✅ {found['Product_Name']}")
            
            if self.current_reception_mode:
                # في وضع الاستلام: نجبر المستخدم على استخدام نفس اللوت والسعر
                lot = found.get('Lot_Number', '')
                price = float(found.get('Unit_Price_Received', 0))
                expiry_str = str(found.get('Expiry_Date', ''))[:10]
                
                self.txt_lot.setText(lot)
                self.txt_lot.setReadOnly(True) # منع تغيير اللوت
                self.txt_lot.setStyleSheet("background-color: #ecf0f1; color: #7f8c8d;")
                
                if expiry_str:
                    self.date_expiry.setDate(QDate.fromString(expiry_str, "yyyy-MM-dd"))
                    self.date_expiry.setReadOnly(True)
                
                self.spin_price.setValue(price)
                self.spin_price.setReadOnly(True) # منع تغيير السعر
                
                # الكمية الافتراضية 1، ولكن لا تتجاوز الكمية المستلمة (اختياري)
                # max_qty = float(found.get('Quantity_Initial', 9999))
                # self.spin_qty.setValue(min(1.0, max_qty))
                self.spin_qty.setFocus()
                self.spin_qty.selectAll()
            else:
                # الوضع العادي
                self.txt_lot.setReadOnly(False)
                self.txt_lot.setStyleSheet("")
                self.date_expiry.setReadOnly(False)
                self.spin_price.setReadOnly(False)
                self.spin_price.setValue(float(found.get('Purchase_Price', 0)))
                self.spin_qty.setFocus()

        else:
            self.selected_product = None
            self.lbl_product_name.setText("❌ Produit introuvable" + (" (dans ce Bon)" if self.current_reception_mode else ""))
            self.clear_entry_fields(keep_search=True)

    def toggle_stock_fields(self):
        is_return = (self.combo_type.currentData() == "Return_Goods")
        self.txt_lot.setEnabled(is_return)
        self.date_expiry.setEnabled(is_return)
        if self.current_reception_mode:
            self.txt_lot.setReadOnly(True) # يبقى مقفلاً في وضع البون

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

        row = self.table.rowCount()
        self.table.insertRow(row)
        
        self.table.setItem(row, 0, QTableWidgetItem(str(self.selected_product['Product_ID'])))
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
        self.table.removeRow(row)
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

    def reset_form(self):
        """إعادة تعيين النموذج إلى الوضع الافتراضي"""
        self.table.setRowCount(0)
        self.txt_ref.clear()
        self.calculate_total()
        self.combo_supplier.setEnabled(True)
        self.current_reception_mode = False
        self.reception_batches_cache = []
        self.lbl_search_info.setText("Recherche (Global):")
        self.lbl_search_info.setStyleSheet("color: black;")
        
        # إعادة تفعيل الحقول وتفريغها
        self.txt_lot.setReadOnly(False)
        self.date_expiry.setReadOnly(False)
        self.spin_price.setReadOnly(False)
        self.txt_lot.setStyleSheet("")
        
        # إعادة تحميل المنتجات العامة في البحث
        self.update_completer(self.all_products_cache)

    def populate_from_reception(self, data):
        """
        تجهيز الواجهة لعمل Avoir بناءً على Reception محدد.
        لا نقوم بملء الجدول، بل نقيد البحث بمنتجات هذا الاستلام.
        """
        header = data.get('Header', {})
        batches = data.get('Batches', [])

        if not batches:
            QMessageBox.warning(self, "Vide", "Cette réception ne contient aucun produit.")
            return

        # 1. تفعيل الوضع المقيد
        self.current_reception_mode = True
        self.reception_batches_cache = batches
        
        # 2. تحديث واجهة المستخدم
        supplier_id = header.get('Supplier_ID')
        idx = self.combo_supplier.findData(supplier_id)
        if idx >= 0: 
            self.combo_supplier.setCurrentIndex(idx)
            self.combo_supplier.setEnabled(False) # قفل المورد

        orig_ref = header.get('Supplier_Invoice_Ref', '') or str(header.get('BR_ID'))
        self.txt_ref.setText(f"AVOIR-{orig_ref}")
        
        # ضبط النوع على إرجاع
        idx_type = self.combo_type.findData("Return_Goods")
        self.combo_type.setCurrentIndex(idx_type)

        # 3. تحديث البحث ليظهر فقط منتجات هذا البون
        self.update_completer(self.reception_batches_cache)
        self.lbl_search_info.setText(f"Recherche (Limité au Bon #{header.get('BR_ID')}):")
        self.lbl_search_info.setStyleSheet("color: #d35400; font-weight: bold;")
        
        self.table.setRowCount(0) # تفريغ الجدول
        self.calculate_total()
        
        QMessageBox.information(self, "Mode Avoir", 
            "Mode création d'Avoir activé pour ce Bon de Réception.\n\n"
            "Veuillez scanner ou rechercher les produits à retourner.\n"
            "Seuls les produits de ce Bon seront acceptés.")
        
        self.txt_search.setFocus()

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
            'Total_Amount_HT': total_ttc, # يمكن تعديله لحساب الضرائب
            'Notes': "Saisie via Interface Avoir"
        }

        items = []
        for r in range(self.table.rowCount()):
            items.append({
                'Product_ID': int(self.table.item(r, 0).text()),
                'Lot_Number': self.table.item(r, 2).text(),
                'Expiry_Date': self.table.item(r, 3).text() if self.table.item(r, 3).text() != "---" else None,
                'Qty_Returned': float(self.table.item(r, 4).text()),
                'Unit_Price': float(self.table.item(r, 5).text())
            })

        try:
            # هنا نفترض وجود current_user_id في مكان ما، سنضع 1 كمثال
            success, msg = self.manager.credit_notes.create_credit_note(header_data, items, user_id=1)
            if success:
                QMessageBox.information(self, "Succès", msg)
                self.reset_form()
                if self.parent() and hasattr(self.parent(), 'refresh_history'):
                    self.parent().refresh_history()
            else:
                QMessageBox.critical(self, "Erreur", f"Échec: {msg}")
        except Exception as e:
            logging.error(f"Save Error: {e}")
            QMessageBox.critical(self, "Erreur", str(e))

class CreditNoteList(QWidget):
    # ... (نفس الكود السابق لـ CreditNoteList بدون تغيير)
    def __init__(self, data_manager):
        super().__init__()
        self.manager = data_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        hbox = QHBoxLayout()
        btn_refresh = QPushButton("Actualiser")
        btn_refresh.setIcon(qta.icon("fa5s.sync-alt"))
        btn_refresh.clicked.connect(self.load_data)
        hbox.addStretch()
        hbox.addWidget(btn_refresh)
        layout.addLayout(hbox)

        self.table = QTableWidget()
        cols = ["ID", "Réf. Avoir", "Fournisseur", "Date", "Type", "Montant TTC", "Statut"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setColumnHidden(0, True) 
        
        layout.addWidget(self.table)
        self.load_data()

    def load_data(self):
        try:
            if not hasattr(self.manager.credit_notes, 'get_all_credit_notes'):
                return
            notes = self.manager.credit_notes.get_all_credit_notes()
            self.table.setRowCount(0)
            for row, note in enumerate(notes):
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(str(note['Credit_Note_ID'])))
                self.table.setItem(row, 1, QTableWidgetItem(str(note['Credit_Note_Ref'])))
                self.table.setItem(row, 2, QTableWidgetItem(str(note.get('Supplier_Name', '---'))))
                self.table.setItem(row, 3, QTableWidgetItem(str(note['Credit_Date'])))
                type_display = "Retour Marchandise" if note['Type'] == 'Return_Goods' else "Correction Prix"
                self.table.setItem(row, 4, QTableWidgetItem(type_display))
                amt = float(note.get('Total_Amount_TTC') or 0)
                amt_item = QTableWidgetItem(f"{amt:,.2f} DA")
                amt_item.setForeground(QBrush(QColor("#c0392b")))
                self.table.setItem(row, 5, amt_item)
                self.table.setItem(row, 6, QTableWidgetItem(str(note['Status'])))
        except Exception as e:
            logging.error(f"Error loading credit notes: {e}")

class CreditNoteTab(QWidget):
    # ... (نفس الكود السابق لـ CreditNoteTab بدون تغيير كبير، فقط populate_from_reception)
    def __init__(self, data_manager):
        super().__init__()
        self.manager = data_manager
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabWidget::pane { border: 0; }")
        
        self.form_tab = CreditNoteForm(data_manager)
        self.list_tab = CreditNoteList(data_manager)
        
        self.tabs.addTab(self.form_tab, "📝 Saisie Avoir")
        self.tabs.addTab(self.list_tab, "📜 Historique")
        self.tabs.currentChanged.connect(self.on_tab_change)
        layout.addWidget(self.tabs)

    def on_tab_change(self, index):
        if index == 1: self.list_tab.load_data()

    def refresh_history(self):
        self.list_tab.load_data()

    def populate_from_reception(self, data):
        self.tabs.setCurrentIndex(0)
        self.form_tab.populate_from_reception(data)