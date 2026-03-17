import logging
import random
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QLabel, QInputDialog, QDoubleSpinBox,
    QLineEdit, QComboBox, QDateEdit, QTableWidget, QGroupBox,
    QTableWidgetItem, QSpinBox, QPushButton, QMessageBox, 
    QFrame, QHeaderView, QCheckBox, QCompleter, QScrollArea, QAbstractItemView
)
from PySide6.QtCore import Qt, QDate, QTimer, QLocale
from PySide6.QtGui import QFont, QColor, QGuiApplication
from ui.widgets.master_data.dialogs import BaseDialog
from PySide6.QtCore import Qt, QDate, QTimer, QLocale
import qtawesome as qta

from .location_tree_combo import LocationTreeComboBox
from .bulk_barcode_selection_dialog import BulkBarcodeSelectionDialog


class AutoSelectSpinBox(QSpinBox):
    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self._safe_select_all)

    def _safe_select_all(self):
        try:
            if self.isVisible(): 
                self.selectAll()
        except RuntimeError:
            pass


class AutoSelectLineEdit(QLineEdit):
    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self._safe_select_all)

    def _safe_select_all(self):
        try:
            if self.isVisible():
                self.selectAll()
        except RuntimeError:
            pass


class AutoSelectDoubleSpinBox(QDoubleSpinBox):
    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self._safe_select_all)

    def _safe_select_all(self):
        try:
            if self.isVisible():
                self.selectAll()
        except RuntimeError:
            pass


class ReceptionDialog(BaseDialog):
    def __init__(self, po_data, locations_list, location_manager, manager, printer_manager, 
                 parent=None, edit_mode=False, reception_data=None, target_batch_id=None):
        """
        Initialisation complète de la fenêtre de réception.
        """
        self.po_data = po_data
        self.locations = locations_list
        self.location_manager = location_manager 
        self.manager = manager
        self.printer = printer_manager
        self.edit_mode = edit_mode
        self.reception_data = reception_data
        self.target_batch_id = target_batch_id 
        self.current_editing_row = -1
        
        # تهيئة متغيرات الحساب
        self.total_ht_val = 0.0
        self.total_tva_val = 0.0
        self.total_remise_val = 0.0
        self.total_ttc_val = 0.0

        # --- تصحيح الخطأ: تعريف br_id فوراً في البداية ---
        self.br_id = None
        if self.edit_mode and self.reception_data:
            self.br_id = self.reception_data.get('Header', {}).get('BR_ID')
        # --------------------------------------------------

        title = f"Réception #{po_data.get('PO_ID', 'N/A')} - {po_data.get('Supplier_Name', 'N/A')}"
        super().__init__(title, parent)

        # إخفاء أزرار BaseDialog السفلية تلقائياً
        if hasattr(self, 'buttons'):
            self.buttons.hide()

        self.adjust_screen_size()
        
        # 1. إنشاء العناصر أولاً
        self.create_widgets()
        # 2. ربط الأحداث
        self.setup_connections()
        # 3. ترتيب الواجهة
        self.init_ui()

        # 4. الآن يمكننا تعطيل الحقول بأمان (لأنها أصبحت موجودة)
        # هذا يحقق طلبك: الحقول تظهر disabled في البداية
        self.toggle_inputs_state(False)

        # تحميل البيانات إذا كنا في وضع التعديل
        if self.edit_mode and self.reception_data:
            self.load_reception_data()
            # إذا كنا نعدل فاتورة موجودة بالفعل، نعيد تفعيل الحقول
            if self.br_id:
                self.toggle_inputs_state(True)
            
            if self.target_batch_id:
                QTimer.singleShot(100, self.highlight_target_row)

        self.showMaximized()


    def adjust_screen_size(self):
        """
        ضبط حجم النافذة مع ترك هامش لشريط المهام (Taskbar).
        """
        screen_geo = QGuiApplication.primaryScreen().availableGeometry()
        
        # نأخذ 90% من العرض والارتفاع المتاحين فقط
        target_width = int(screen_geo.width() * 0.90)
        target_height = int(screen_geo.height() * 0.90)
        
        self.resize(target_width, target_height)
        
        # تمركز النافذة في وسط الشاشة
        self.move(screen_geo.center() - self.rect().center())

    def update_totals(self):
        self.total_ht_val = 0.0
        self.total_tva_val = 0.0
        self.total_remise_val = 0.0
        self.total_ttc_val = 0.0

        for r in range(self.table_items.rowCount()):
            item = self.table_items.item(r, 0)
            if not item: continue
            meta = item.data(Qt.UserRole)
            if not meta: continue

            qty = float(meta.get('Qty_Received', 0))
            price = float(meta.get('Unit_Price_Received', 0.0))
            disc_amt = float(meta.get('Discount_Val', 0.0))
            tax_rate = float(meta.get('Tax_Rate_Percent', 0)) / 100.0

            line_ht = qty * price
            line_net_ht = line_ht - disc_amt
            line_tva = line_net_ht * tax_rate
            line_ttc = line_net_ht + line_tva

            self.total_ht_val += line_ht
            self.total_remise_val += disc_amt
            self.total_tva_val += line_tva
            self.total_ttc_val += line_ttc

        self.lbl_total_ht.setText(f"{self.total_ht_val:,.2f} DA")
        self.lbl_total_remise.setText(f"{self.total_remise_val:,.2f} DA")
        self.lbl_total_tva.setText(f"{self.total_tva_val:,.2f} DA")
        self.lbl_total_ttc.setText(f"{self.total_ttc_val:,.2f} DA")

    def load_reception_data(self):
        """
        Chargement des données de réception en mode édition.
        """
        if not self.reception_data or not self.reception_data.get('Header'): 
            return

        # عند فتح فاتورة موجودة: قفل الحقول وإظهار زر التعديل
        if self.br_id:
            self.invoice_ref.setReadOnly(True)
            self.bl_ref.setReadOnly(True)
            self.reception_date.setReadOnly(True)
            
            self.btn_validate_ref.setText(" Validé")
            self.btn_validate_ref.setEnabled(False)
            self.btn_validate_ref.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; border: none;")
            
            self.btn_unlock_header.setVisible(True)

        self.table_items.setSortingEnabled(False)

        header = self.reception_data['Header']
        inv_ref = header.get('Supplier_Invoice_Ref') or ''
        self.invoice_ref.setText(inv_ref)
        self.bl_ref.setText(header.get('Supplier_BL_Ref') or '')
        
        if header.get('Reception_Date'):
            r_date = header['Reception_Date']
            try:
                if isinstance(r_date, str):
                    clean_date_str = r_date[:10] 
                    qdate = QDate.fromString(clean_date_str, "yyyy-MM-dd")
                    if qdate.isValid():
                        self.reception_date.setDate(qdate)
                elif hasattr(r_date, 'year'):
                    self.reception_date.setDate(QDate(r_date.year, r_date.month, r_date.day))
            except Exception:
                pass

        self.table_items.setRowCount(0)
        
        for batch in self.reception_data.get('Batches', []):
            row = self.table_items.rowCount()
            self.table_items.insertRow(row)
            
            qty = float(batch.get('Quantity_Initial', 0))
            price = float(batch.get('Unit_Price_Received', 0))
            tax_pct = float(batch.get('Tax_Rate_Percent', 0))
            disc_pct = float(batch.get('Discount_Percent', 0))
            
            base_ht = qty * price
            disc_amt = base_ht * (disc_pct / 100)
            net_ht = base_ht - disc_amt
            tva_amt = net_ht * (tax_pct / 100)
            total_ttc = net_ht + tva_amt
            pu_ttc = (total_ttc / qty) if qty > 0 else 0

            meta = {
                'Batch_ID': batch.get('Batch_ID'),
                'Product_ID': batch.get('Product_ID'), 
                'Location_ID': batch.get('Location_ID'),
                'Location_Name': batch.get('Location_Name', '---'),
                'Lot_Number': batch.get('Lot_Number', 'N/A'), 
                'Expiry_Date': str(batch.get('Expiry_Date', '')),
                'Qty_Received': qty, 
                'Unit_Price_Received': price,
                'Discount_Val': disc_amt, 
                'Discount_Percent': disc_pct,
                'Tax_Rate_Percent': tax_pct, 
                'Internal_Barcode': batch.get('Internal_Barcode', '---'),
                'Line_Note': batch.get('Reception_Note', ''),
                'Unit_Label': batch.get('Stock_Unit', 'U'),
                'factor': 1.0
            }

            display_values = [
                batch.get('Product_Name', '---'),
                batch.get('Internal_Barcode', '---'),
                batch.get('Stock_Unit', 'U'),
                f"{qty:g}",
                meta['Lot_Number'],
                meta['Expiry_Date'],
                batch.get('Location_Name', '---'),
                f"{price:,.2f} DA",
                f"{disc_amt:,.2f} DA",
                f"{net_ht:,.2f} DA",
                f"{tva_amt:,.2f} DA",
                f"{pu_ttc:,.2f} DA",
                f"{total_ttc:,.2f} DA"
            ]

            for col, value in enumerate(display_values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignCenter)
                self.table_items.setItem(row, col, item)
            
            self.table_items.item(row, 0).setData(Qt.UserRole, meta)
        
        self.update_totals()
        self.table_items.setSortingEnabled(True)
        
    def create_widgets(self):
        self.invoice_ref = AutoSelectLineEdit()
        self.invoice_ref.setPlaceholderText("Ex: FACT-2024-001")
        
        self.bl_ref = AutoSelectLineEdit()
        self.bl_ref.setPlaceholderText("Ex: BL-2024-001")
        
        self.btn_validate_ref = QPushButton(" Valider & Verrouiller")
        self.btn_validate_ref.setIcon(qta.icon('fa5s.check-circle', color='white'))
        self.btn_validate_ref.setCursor(Qt.PointingHandCursor)
        self.btn_validate_ref.setToolTip("Valider les références pour commencer")
        self.btn_validate_ref.setStyleSheet("""
            QPushButton {
                background-color: #2980b9; 
                color: white; 
                font-weight: bold; 
                padding: 6px 15px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #3498db; }
            QPushButton:disabled { 
                background-color: #27ae60; 
                color: white;
                border: 1px solid #2ecc71;
            }
        """)

        # --- زر التعديل الجديد (Modifier) ---
        # يظهر فقط عندما تكون الحقول مقفلة
        self.btn_unlock_header = QPushButton("")
        self.btn_unlock_header.setIcon(qta.icon('fa5s.pen', color='white'))
        self.btn_unlock_header.setToolTip("Modifier les informations de l'en-tête")
        self.btn_unlock_header.setCursor(Qt.PointingHandCursor)
        self.btn_unlock_header.setVisible(False) # مخفي في البداية
        self.btn_unlock_header.setFixedSize(30, 30)
        self.btn_unlock_header.setStyleSheet("""
            QPushButton {
                background-color: #f39c12; 
                color: white; 
                border-radius: 4px; 
                padding: 4px;
            }
            QPushButton:hover { background-color: #d35400; }
        """)

        self.reception_date = QDateEdit(QDate.currentDate())
        self.reception_date.setCalendarPopup(True)

        self.cb_product = QComboBox()
        self.cb_product.setEditable(True)
        self.cb_product.completer().setFilterMode(Qt.MatchContains)
        self.cb_product.completer().setCompletionMode(QCompleter.PopupCompletion)
        
        all_products = []
        tab_parent = self.parent()
        if tab_parent and hasattr(tab_parent, 'manager'):
            all_products = tab_parent.manager.products.get_all_products()

        self.cb_product.addItem("", None)
        for p in all_products:
            brand = p.get('Manuf_Name') or "---"
            self.cb_product.addItem(f"{p['Product_Name']} ({brand})", p)

        self.cb_unit_type = QComboBox()
        self.inp_qty = AutoSelectSpinBox()
        self.inp_qty.setRange(1, 999999)
        self.inp_lot = AutoSelectLineEdit()
        self.inp_expiry = QDateEdit(QDate.currentDate().addYears(2))
        self.cb_location = LocationTreeComboBox(self.location_manager)
        
        self.inp_price = AutoSelectDoubleSpinBox()
        self.inp_price.setRange(0, 99999999.99)
        self.inp_price.setDecimals(2)
        self.inp_price.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.inp_price.setLocale(QLocale.c())
        self.inp_price.setGroupSeparatorShown(True)

        self.inp_remise = AutoSelectDoubleSpinBox()
        self.inp_remise.setRange(0, 99999999.99)
        self.inp_remise.setDecimals(2)
        self.inp_remise.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.inp_remise.setLocale(QLocale.c())
        self.inp_remise.setGroupSeparatorShown(True)

        self.cb_remise_type = QComboBox()
        self.cb_remise_type.addItems(["%", "DZD"])
        
        self.chk_tva = QCheckBox("TVA 19%")
        self.chk_tva.setChecked(True)
        self.inp_observation = AutoSelectLineEdit()
        self.lbl_item_ttc = QLabel("TTC : 0.00 DA")
        self.lbl_conversion_logic = QLabel("")

        self.btn_add = QPushButton(qta.icon('fa5s.plus', color='white'), " Ajouter")
        self.btn_modify = QPushButton(qta.icon('fa5s.edit', color='white'), " Modifier")
        self.btn_delete = QPushButton(qta.icon('fa5s.trash-alt', color='white'), " Supprimer")
        self.btn_print = QPushButton(qta.icon('fa5s.print', color='white'), " Imprimer")


        self.btn_print_all = QPushButton(qta.icon('fa5s.copy', color='white'), " Imprimer Tout")
        self.btn_print_all.setToolTip("Imprimer les étiquettes pour tous les articles de la liste")
        self.btn_print_all.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold;")

        # إعدادات الجدول
        self.table_items = QTableWidget(0, 14)
        headers = [
            "Produit", "Code", "Unité", "Qté", "Lot", "Date Exp",
            "Stock", "Prix U", "Remise", "Prix HT", "TVA (DA)",
            "P.U TTC", "Total TTC", "Meta"
        ]
        self.table_items.setHorizontalHeaderLabels(headers)
        self.table_items.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table_items.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_items.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_items.setAlternatingRowColors(True)
        self.table_items.setSortingEnabled(True)
        header = self.table_items.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_items.setColumnHidden(13, True)

        self.lbl_total_ht = QLabel("0.00 DA")
        self.lbl_total_remise = QLabel("0.00 DA")
        self.lbl_total_tva = QLabel("0.00 DA")
        self.lbl_total_ttc = QLabel("0.00 DA")
        self.lbl_conversion_logic.setStyleSheet("color: #7f8c8d; font-style: italic; font-size: 12px;")

    def on_product_selected(self):
        p = self.cb_product.currentData()
        self.cb_unit_type.clear()
        
        if not p:
            return
            
        self.cb_unit_type.addItem(p.get('Stock_Unit', 'U'), 1.0)
        if p.get('Ordering_Unit') and p['Ordering_Unit'] != p.get('Stock_Unit'):
            self.cb_unit_type.addItem(p['Ordering_Unit'], float(p.get('Stock_Qty_Per_Order_Unit', 1.0)))
    
    def calculate_live_item_ttc(self):
        try:
            if not hasattr(self, 'inp_qty') or not self.inp_qty:
                return

            qty = float(self.inp_qty.value())
            price = self.inp_price.value()
            rem_val = self.inp_remise.value()
            rem_type = self.cb_remise_type.currentText()
            factor = float(self.cb_unit_type.currentData() or 1.0)
            
            base_ht = qty * factor * price
            rem_amt = base_ht * (rem_val / 100) if rem_type == "%" else rem_val
            net_ht = base_ht - rem_amt
            tax = net_ht * 0.19 if self.chk_tva.isChecked() else 0
            ttc = net_ht + tax
            
            self.lbl_item_ttc.setText(f"TTC : {ttc:,.2f} DA")
            
            if factor > 1:
                p_data = self.cb_product.currentData()
                stock_u = p_data.get('Stock_Unit', 'U') if p_data else 'U'
                self.lbl_conversion_logic.setText(f"💡 {qty} {self.cb_unit_type.currentText()} = {int(qty*factor)} {stock_u} en stock.")
            else:
                self.lbl_conversion_logic.setText("💡 Saisie directe en unité de stockage.")
        except RuntimeError:
            pass 

    def enable_header_editing(self):
        """إعادة فتح حقول الرأس للتعديل."""
        self.invoice_ref.setReadOnly(False)
        self.bl_ref.setReadOnly(False)
        self.reception_date.setReadOnly(False)
        
        self.btn_validate_ref.setText(" Enregistrer")
        self.btn_validate_ref.setEnabled(True)
        self.btn_validate_ref.setStyleSheet("""
            QPushButton {
                background-color: #2980b9; 
                color: white; 
                font-weight: bold; 
                padding: 6px 15px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #3498db; }
        """)
        
        self.btn_unlock_header.setVisible(False)
        
        self.toggle_inputs_state(False)
        
        self.invoice_ref.setFocus()


    def validate_header_and_create(self):
        """
        التحقق من الرأس، الحفظ، ثم فتح الحقول بالقوة.
        """
        # 1. التحقق من المدخلات
        inv_ref = self.invoice_ref.text().strip()
        bl_ref = self.bl_ref.text().strip()

        if not inv_ref and not bl_ref:
            QMessageBox.warning(self, "Manquant", "Veuillez saisir Facture ou BL.")
            return False

        try:
            # تعطيل الزر لتجنب التكرار
            self.btn_validate_ref.setEnabled(False)
            self.btn_validate_ref.repaint() # تحديث الواجهة فوراً

            u_id = self.get_current_user_id()
            mgr = self.manager.reception if hasattr(self.manager, 'reception') else self.manager

            header_data = {
                "PO_ID": self.po_data.get('PO_ID'),
                "Supplier_ID": self.po_data.get('Supplier_ID'),
                "Supplier_Invoice_Ref": inv_ref,
                "Supplier_BL_Ref": bl_ref,
                "Reception_Date": self.reception_date.date().toPyDate(),
                "Created_By": u_id
            }

            # 2. الحفظ في قاعدة البيانات
            if not self.br_id:
                new_id = mgr.create_new_reception_header(header_data)
                if not new_id:
                    self.btn_validate_ref.setEnabled(True)
                    QMessageBox.critical(self, "Erreur", "Référence existante !")
                    return False
                self.br_id = new_id
            else:
                mgr.update_reception_header_info(self.br_id, header_data)

            # 3. تحديث حالة PO
            po_id = self.po_data.get('PO_ID')
            if po_id:
                with mgr.db.get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE Purchase_Orders SET Status = 'Partial' WHERE PO_ID = %s", (po_id,))
                    conn.commit()

            # 4. تحديث الواجهة (المنطقة الحرجة)
            self.invoice_ref.setReadOnly(True)
            self.bl_ref.setReadOnly(True)
            self.reception_date.setReadOnly(True)
            
            self.btn_validate_ref.setText(" Validé")
            self.btn_validate_ref.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
            self.btn_unlock_header.setVisible(True)

            # --- [الحل الجذري] فتح الحقول يدوياً واحداً تلو الآخر للتأكد ---
            self.cb_product.setEnabled(True)
            self.cb_unit_type.setEnabled(True)
            self.inp_qty.setEnabled(True)
            self.inp_lot.setEnabled(True)
            self.inp_expiry.setEnabled(True)
            self.cb_location.setEnabled(True)
            self.inp_price.setEnabled(True)
            self.inp_remise.setEnabled(True)
            self.cb_remise_type.setEnabled(True)
            self.chk_tva.setEnabled(True)
            self.inp_observation.setEnabled(True)
            
            self.btn_add.setEnabled(True)
            self.btn_modify.setEnabled(True)
            self.btn_delete.setEnabled(True)
            self.table_items.setEnabled(True)
            # -------------------------------------------------------------

            # وضع المؤشر في حقل المنتج
            self.cb_product.setFocus()
            
            return True

        except Exception as e:
            self.btn_validate_ref.setEnabled(True)
            QMessageBox.critical(self, "Erreur", str(e))
            return False
        
    def validate_header_and_create(self):
        """
        التحقق من الرأس، الحفظ، ثم فتح حقول المنتجات (تصحيح المشكلة).
        """
        # 1. التحقق من المدخلات
        inv_ref = self.invoice_ref.text().strip()
        bl_ref = self.bl_ref.text().strip()

        if not inv_ref and not bl_ref:
            QMessageBox.warning(
                self, 
                "Données manquantes", 
                "Veuillez saisir au moins une référence (Facture ou BL) avant de valider."
            )
            self.invoice_ref.setFocus()
            return False

        try:
            # تعطيل الزر مؤقتاً
            self.btn_validate_ref.setEnabled(False)
            
            u_id = self.get_current_user_id()
            mgr = self.manager.reception if hasattr(self.manager, 'reception') else self.manager

            header_data = {
                "PO_ID": self.po_data.get('PO_ID'),
                "Supplier_ID": self.po_data.get('Supplier_ID'),
                "Supplier_Invoice_Ref": inv_ref,
                "Supplier_BL_Ref": bl_ref,
                "Reception_Date": self.reception_date.date().toPyDate(),
                "Created_By": u_id
            }

            # 2. إنشاء أو تحديث الرأس في قاعدة البيانات
            if not self.br_id:
                new_id = mgr.create_new_reception_header(header_data)
                if not new_id:
                    self.btn_validate_ref.setEnabled(True)
                    QMessageBox.critical(self, "Erreur Doublon", "Cette référence existe déjà.")
                    return False
                self.br_id = new_id
            else:
                mgr.update_reception_header_info(self.br_id, header_data)

            # 3. تحديث حالة PO
            po_id = self.po_data.get('PO_ID')
            if po_id:
                with mgr.db.get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE Purchase_Orders SET Status = 'Completed' WHERE PO_ID = %s", (po_id,))
                    conn.commit()
                logging.info(f"PO #{po_id} marked as Completed immediately after validation.")

            # 4. تحديث الواجهة (الخطوة المصححة)
            self.invoice_ref.setReadOnly(True)
            self.bl_ref.setReadOnly(True)
            self.reception_date.setReadOnly(True)
            
            self.btn_validate_ref.setText(" Validé (Commande Complétée)")
            # لا نعيد تفعيل زر التحقق لأنه انتهى دوره
            self.btn_validate_ref.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; border: none;")
            
            # إظهار زر التعديل (القلم) في حال أراد المستخدم تغيير الرأس لاحقاً
            self.btn_unlock_header.setVisible(True)

            # ---------------------------------------------------------
            # [الحل]: تفعيل حقول المنتجات الآن
            # ---------------------------------------------------------
            self.toggle_inputs_state(True)
            
            # وضع المؤشر في قائمة المنتجات مباشرة
            self.cb_product.setFocus()

            return True

        except Exception as e:
            logging.error(f"Validation error: {e}")
            # في حالة الخطأ، نعيد تفعيل الزر ليحاول المستخدم مرة أخرى
            self.btn_validate_ref.setEnabled(True)
            QMessageBox.critical(self, "Erreur Système", str(e))
            return False
        

    def open_bulk_print_dialog(self):
        """Ouvre la fenêtre de sélection et lance l'impression en masse."""
        if self.table_items.rowCount() == 0:
            QMessageBox.information(self, "Info", "La liste est vide.")
            return

        # 1. Collecter les données du tableau
        items_to_process = []
        for row in range(self.table_items.rowCount()):
            item_0 = self.table_items.item(row, 0)
            if not item_0: continue
            meta = item_0.data(Qt.UserRole)
            if meta:
                # On ajoute le nom du produit manquant dans meta parfois
                meta['Product_Name'] = item_0.text() 
                items_to_process.append(meta)

        # 2. Ouvrir la fenêtre de dialogue
        dlg = BulkBarcodeSelectionDialog(items_to_process, self)
        if dlg.exec():
            selected = dlg.get_items_to_print()
            
            # 3. Boucle d'impression
            total_labels = 0
            for index, item in enumerate(selected):
                qty = int(item.get('Qty_Received', 1))
                name = item.get('Product_Name', 'Inconnu')
                barcode = item.get('Internal_Barcode', '')
                lot = item.get('Lot_Number', '')
                expiry = str(item.get('Expiry_Date', ''))
                
                # Impression des étiquettes produits
                if qty > 0:
                    self.printer.print_label(name, barcode, lot, expiry, qty)
                    total_labels += qty
                
                # 4. Impression du séparateur (Sauf après le dernier produit)
                if index < len(selected) - 1:
                    # On imprime une étiquette "Vide" ou avec un trait
                    # Astuce : On envoie des chaines vides ou des tirets
                    self.printer.print_label("----------------", "   ", "---", "---", 1)

            QMessageBox.information(self, "Terminé", f"Ordre d'impression envoyé pour {total_labels} étiquettes.")

    def setup_connections(self):
        self.cb_product.currentIndexChanged.connect(self.on_product_selected)
        
        for w in [self.inp_qty, self.inp_price, self.inp_remise]:
            w.valueChanged.connect(self.calculate_live_item_ttc)
        self.cb_remise_type.currentIndexChanged.connect(self.calculate_live_item_ttc)
        self.chk_tva.stateChanged.connect(self.calculate_live_item_ttc)
        
        self.btn_validate_ref.clicked.connect(self.validate_header_and_create)
        self.btn_unlock_header.clicked.connect(self.enable_header_editing)
        
        self.btn_add.clicked.connect(self.add_item_to_table)
        self.btn_modify.clicked.connect(self.load_item_for_edit)
        self.btn_delete.clicked.connect(self.delete_selected_row)
        self.btn_print.clicked.connect(self.print_selected_labels)
        self.btn_print_all.clicked.connect(self.open_bulk_print_dialog)

        self.table_items.cellDoubleClicked.connect(self.load_item_for_edit)

    def select_location_id(self, location_id):
        try:
            if location_id is None:
                return False

            for i in range(self.cb_location.count()):
                if self.cb_location.itemData(i) == location_id:
                    self.cb_location.setCurrentIndex(i)
                    return True
            return False
        except Exception:
            return False

    def load_item_for_edit(self):
        try:
            row = self.table_items.currentRow()
            if row < 0:
                QMessageBox.warning(self, "Attention", "Veuillez sélectionner une ligne.")
                return

            item_0 = self.table_items.item(row, 0)
            if not item_0: return
            meta = item_0.data(Qt.UserRole)
            if not meta: return

            p_id = meta.get('Product_ID')
            for i in range(self.cb_product.count()):
                p_data = self.cb_product.itemData(i)
                if p_data and p_data.get('Product_ID') == p_id:
                    self.cb_product.setCurrentIndex(i)
                    break
            
            factor = float(meta.get('factor', 1.0))
            qty_display = float(meta.get('Qty_Received', 0)) / factor
            self.inp_qty.setValue(int(qty_display))
            
            idx_unit = self.cb_unit_type.findText(meta.get('Unit_Label', ''))
            if idx_unit >= 0:
                self.cb_unit_type.setCurrentIndex(idx_unit)

            self.inp_price.setValue(float(meta.get('Unit_Price_Received', 0.0)))
            
            if float(meta.get('Discount_Percent', 0)) > 0:
                self.cb_remise_type.setCurrentText("%")
                self.inp_remise.setValue(float(meta['Discount_Percent']))
            else:
                self.cb_remise_type.setCurrentText("DZD")
                self.inp_remise.setValue(float(meta.get('Discount_Val', 0.0)))

            self.inp_lot.setText(str(meta.get('Lot_Number', '')))
            exp_date_str = str(meta.get('Expiry_Date', ''))
            if exp_date_str and exp_date_str not in ['None', 'N/A', '']:
                q_date = QDate.fromString(exp_date_str, "yyyy-MM-dd")
                if q_date.isValid():
                    self.inp_expiry.setDate(q_date)

            location_name = meta.get('Location_Name', '---')
            if meta.get('Location_ID'):
                if not self.select_location_id(meta['Location_ID']):
                    self.cb_location.setCurrentText(location_name)
            else:
                self.cb_location.setCurrentText(location_name)

            self.inp_observation.setText(str(meta.get('Line_Note', '')))
            self.chk_tva.setChecked(float(meta.get('Tax_Rate_Percent', 0)) > 0)

            self.current_editing_row = row
            self.btn_add.setText("💾 Enregistrer Modif.")
            self.btn_add.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold;")
            self.calculate_live_item_ttc()

        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur de chargement: {str(e)}")

    def init_ui(self):
        main_layout = QVBoxLayout(self.form_widget)
        main_layout.setContentsMargins(10, 5, 10, 5)
        main_layout.setSpacing(8)

        header_info = QLabel(
            f"<b>Fournisseur:</b> {self.po_data.get('Supplier_Name', 'N/A')} | <b>N°BC:</b> #{self.po_data.get('PO_ID', 'N/A')}"
        )
        header_info.setStyleSheet("font-size: 14px; color: #2c3e50; background: #ecf0f1; padding: 8px; border-radius: 4px; border-left: 4px solid #3498db;")
        main_layout.addWidget(header_info)

        # --- الشريط العلوي ---
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("<b>Date:</b>"))
        top_layout.addWidget(self.reception_date)
        top_layout.addSpacing(15)
        top_layout.addWidget(QLabel("<b>Facture:</b>"))
        top_layout.addWidget(self.invoice_ref)
        top_layout.addWidget(QLabel("<b>BL:</b>"))
        top_layout.addWidget(self.bl_ref)
        top_layout.addSpacing(10)
        
        # إضافة الزرين جنباً إلى جنب
        top_layout.addWidget(self.btn_validate_ref)
        top_layout.addWidget(self.btn_unlock_header) 
        
        main_layout.addLayout(top_layout)
        
        # خط فاصل
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line)

        entry_layout = QVBoxLayout()
        entry_layout.setSpacing(5)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("<b>Produit:</b>"))
        row1.addWidget(self.cb_product, 4)
        row1.addWidget(QLabel("<b>Unité:</b>"))
        row1.addWidget(self.cb_unit_type, 1)
        row1.addWidget(QLabel("<b>Qté:</b>"))
        row1.addWidget(self.inp_qty, 1)
        row1.addWidget(QLabel("<b>Lot:</b>"))
        row1.addWidget(self.inp_lot, 2)
        row1.addWidget(QLabel("<b>Exp:</b>"))
        row1.addWidget(self.inp_expiry, 2)
        entry_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("<b>Stock:</b>"))
        row2.addWidget(self.cb_location, 2)
        row2.addWidget(QLabel("<b>Prix U:</b>"))
        row2.addWidget(self.inp_price, 2)
        row2.addWidget(QLabel("<b>Remise:</b>"))
        row2.addWidget(self.inp_remise, 1)
        row2.addWidget(self.cb_remise_type, 1)
        row2.addWidget(self.chk_tva)
        row2.addWidget(self.lbl_item_ttc)
        row2.addWidget(QLabel("<b>Réclamation:</b>"))
        row2.addWidget(self.inp_observation, 3)
        entry_layout.addLayout(row2)

        entry_layout.addWidget(self.lbl_conversion_logic)
        main_layout.addLayout(entry_layout)

        ctrl_bar = QHBoxLayout()
        fin_layout = QHBoxLayout()
        fin_layout.addWidget(QLabel("<b>HT:</b>"))
        fin_layout.addWidget(self.lbl_total_ht)
        fin_layout.addWidget(QLabel("<b>Remise:</b>"))
        fin_layout.addWidget(self.lbl_total_remise)
        fin_layout.addWidget(QLabel("<b>TVA:</b>"))
        fin_layout.addWidget(self.lbl_total_tva)
        fin_layout.addWidget(QLabel("<b style='color: #007572;'>TTC:</b>"))
        self.lbl_total_ttc.setStyleSheet("font-weight: bold; color: #007572;")
        fin_layout.addWidget(self.lbl_total_ttc)
        ctrl_bar.addLayout(fin_layout)
        
        ctrl_bar.addStretch(1)
        ctrl_bar.addWidget(self.btn_add)
        ctrl_bar.addWidget(self.btn_modify)
        ctrl_bar.addWidget(self.btn_delete)
        ctrl_bar.addWidget(self.btn_print)
        ctrl_bar.addWidget(self.btn_print_all)
        main_layout.addLayout(ctrl_bar)

        main_layout.addWidget(self.table_items, 1)
        self.table_items.horizontalHeader().setSortIndicator(1, Qt.DescendingOrder)

    def get_reception_mgr(self):
        """الوصول الصحيح لمدير الاستلام."""
        return self.manager.reception if hasattr(self.manager, 'reception') else self.manager

    def get_current_user_id(self):
        """جلب معرف المستخدم الحالي من مستويات النافذة."""
        u_id = None
        parent_widget = self.parent()
        while parent_widget:
            if hasattr(parent_widget, 'current_user') and isinstance(parent_widget.current_user, dict):
                u_id = parent_widget.current_user.get('User_ID')
                break
            parent_widget = parent_widget.parent()
        if u_id is None and hasattr(self.manager, 'current_user_id'):
            u_id = self.manager.current_user_id
        return u_id

    def load_items_from_db(self):
        """تحديث الجدول من قاعدة البيانات مباشرة لضمان المزامنة."""
        if not hasattr(self, 'br_id') or not self.br_id:
            return
        
        reception_mgr = self.manager.reception if hasattr(self.manager, 'reception') else self.manager
        details = reception_mgr.get_reception_full_details(self.br_id)
        
        if details:
            self.reception_data = details
            self.load_reception_data() # الدالة الأصلية التي تعيد ملء الجدول

    

    def _recalculate_reception_totals(self, br_id: int):
        """
        إعادة حساب المجاميع المالية للفاتورة وتحديث حالة أمر الشراء (PO).
        التعديل: منع النظام من إرجاع حالة PO إلى Partial إذا كان بالفعل Completed.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # 1. جلب PO_ID المرتبط بهذا الاستلام
                cursor.execute("SELECT PO_ID FROM Reception_Log WHERE BR_ID = %s", (br_id,))
                res = cursor.fetchone()
                po_id = res['PO_ID'] if res else None

                # 2. حساب مجاميع الفاتورة (BR)
                query = """
                    SELECT Quantity_Initial, Unit_Price_Received, Tax_Rate_Percent, Discount_Percent
                    FROM Inventory_Batches 
                    WHERE BR_ID = %s
                """
                cursor.execute(query, (br_id,))
                batches = cursor.fetchall()

                t_ht, t_tva, t_disc = 0.0, 0.0, 0.0
                
                for b in batches:
                    qty = float(b['Quantity_Initial'] or 0)
                    price = float(b['Unit_Price_Received'] or 0)
                    tax_rate = float(b['Tax_Rate_Percent'] or 0) / 100.0
                    disc_rate = float(b['Discount_Percent'] or 0) / 100.0
                    
                    line_ht = qty * price
                    line_disc = line_ht * disc_rate
                    line_net_ht = line_ht - line_disc
                    line_tva = line_net_ht * tax_rate
                    
                    t_ht += line_ht
                    t_disc += line_disc
                    t_tva += line_tva

                t_ttc = (t_ht - t_disc) + t_tva

                # تحديث رأس الفاتورة (BR) - يبقى Completed دائماً عند التعديل
                update_query = """
                    UPDATE Reception_Log 
                    SET Invoice_Total_HT = %s, Invoice_Total_TVA = %s, 
                        Invoice_Total_TTC = %s, Total_Discount = %s,
                        Status = 'Completed'
                    WHERE BR_ID = %s
                """
                cursor.execute(update_query, (t_ht, t_tva, t_ttc, t_disc, br_id))
                
                # -------------------------------------------------------------
                # 3. تحديث حالة أمر الشراء (PO Status Logic) - الجزء المعدل
                # -------------------------------------------------------------
                if po_id:
                    # أ) جلب الحالة الحالية للطلب
                    cursor.execute("SELECT Status FROM Purchase_Orders WHERE PO_ID = %s", (po_id,))
                    current_po_row = cursor.fetchone()
                    current_status = current_po_row['Status'] if current_po_row else 'Draft'

                    # ب) حساب الكميات
                    check_po_query = """
                        SELECT 
                            (SELECT COALESCE(SUM(Qty_Ordered), 0) FROM PO_Details WHERE PO_ID = %s) as Total_Ordered,
                            (SELECT COALESCE(SUM(Quantity_Initial), 0) FROM Inventory_Batches WHERE PO_ID = %s) as Total_Received
                    """
                    cursor.execute(check_po_query, (po_id, po_id))
                    po_stats = cursor.fetchone()
                    
                    total_ordered = float(po_stats['Total_Ordered'])
                    total_received = float(po_stats['Total_Received'])

                    # ج) تحديد الحالة الجديدة
                    new_po_status = 'Sent' # الافتراضي
                    
                    # القاعدة الذهبية: إذا كان مكتمل سابقاً، يبقى مكتمل (إلا إذا أردت فتحه يدوياً)
                    if current_status == 'Completed':
                        new_po_status = 'Completed'
                    else:
                        # الحساب التلقائي العادي
                        if total_received >= total_ordered and total_ordered > 0:
                            new_po_status = 'Completed'
                        elif total_received > 0:
                            new_po_status = 'Partial'

                    # د) تحديث الحالة فقط إذا تغيرت (أو للتأكيد)
                    cursor.execute("UPDATE Purchase_Orders SET Status = %s WHERE PO_ID = %s", (new_po_status, po_id))
                    logging.info(f"PO #{po_id} logic applied. Old: {current_status} -> New: {new_po_status}")

                conn.commit()
                logging.info(f"Totals updated for BR #{br_id}: TTC={t_ttc:,.2f}")
        except Exception as e:
            logging.error(f"Error recalculating totals: {e}")


    def toggle_inputs_state(self, enabled: bool):
        self.cb_product.setEnabled(enabled)
        self.cb_unit_type.setEnabled(enabled)
        self.inp_qty.setEnabled(enabled)
        self.inp_lot.setEnabled(enabled)
        self.inp_expiry.setEnabled(enabled)
        self.cb_location.setEnabled(enabled)
        self.inp_price.setEnabled(enabled)
        self.inp_remise.setEnabled(enabled)
        self.cb_remise_type.setEnabled(enabled)
        self.chk_tva.setEnabled(enabled)
        self.inp_observation.setEnabled(enabled)
        
        self.btn_add.setEnabled(enabled)
        self.btn_modify.setEnabled(enabled)
        self.btn_delete.setEnabled(enabled)
        self.btn_print.setEnabled(enabled)
        
        self.table_items.setEnabled(enabled)


    def add_item_to_table(self):
        """إضافة أو تعديل سطر في الجدول وقاعدة البيانات مع حفظ PO_ID."""
        try:
            if not self.br_id:
                QMessageBox.warning(self, "Action Requise", "Veuillez valider l'en-tête (Bouton Valider) avant d'ajouter des produits.")
                self.invoice_ref.setFocus()
                return

            p_data = self.cb_product.currentData()
            loc_id = self.cb_location.get_current_location_id()
            
            if not p_data or loc_id is None:
                QMessageBox.warning(self, "Attention", "Veuillez sélectionner un produit et un emplacement.")
                return

            u_id = self.get_current_user_id()
            mgr = self.manager.reception if hasattr(self.manager, 'reception') else self.manager

            qty = float(self.inp_qty.value())
            factor = float(self.cb_unit_type.currentData() or 1.0)
            effective_qty = qty * factor
            
            # معالجة الباركود
            barcode_to_save = None
            if self.current_editing_row != -1:
                old_meta = self.table_items.item(self.current_editing_row, 0).data(Qt.UserRole)
                barcode_to_save = old_meta.get('Internal_Barcode')
            else:
                barcode_to_save = self.generate_internal_barcode()

            # --- [FIX] جلب PO_ID من بيانات الطلب المخزنة في الذاكرة ---
            current_po_id = self.po_data.get('PO_ID')
            # ---------------------------------------------------------

            line_data = {
                "BR_ID": self.br_id,
                "PO_ID": current_po_id,  # <--- إضافة هذا السطر ضروري جداً
                "Product_ID": p_data['Product_ID'],
                "Location_ID": loc_id,
                "Quantity_Initial": effective_qty,
                "Quantity_Current": effective_qty,
                "Unit_Price_Received": self.inp_price.value(),
                "Tax_Rate_Percent": 19.0 if self.chk_tva.isChecked() else 0.0,
                "Discount_Percent": self.inp_remise.value() if self.cb_remise_type.currentText() == "%" else 0,
                "Lot_Number": self.inp_lot.text() or "N/A",
                "Expiry_Date": self.inp_expiry.date().toPyDate(),
                "Batch_Note": self.inp_observation.text().strip(),
                "Internal_Barcode": barcode_to_save,
                "Created_By": u_id
            }

            # التنفيذ
            if self.current_editing_row != -1:
                meta = self.table_items.item(self.current_editing_row, 0).data(Qt.UserRole)
                success, msg = mgr.update_reception_line(meta['Batch_ID'], line_data)
            else:
                success, msg = mgr.add_reception_line(line_data)

            if success:
                mgr._recalculate_reception_totals(self.br_id)
                self.load_items_from_db()
                self.clear_inputs()
            else:
                QMessageBox.critical(self, "Erreur", msg)

        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))
            
    def delete_selected_row(self):
        """حذف السطر مباشرة من قاعدة البيانات."""
        row = self.table_items.currentRow()
        if row < 0: return

        meta = self.table_items.item(row, 0).data(Qt.UserRole)
        batch_id = meta.get('Batch_ID')

        if QMessageBox.question(self, "Confirmation", "Supprimer définitivement cet article du stock ?", 
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            mgr = self.manager.reception if hasattr(self.manager, 'reception') else self.manager
            success, msg = mgr.delete_reception_line(batch_id)
            if success:
                mgr._recalculate_reception_totals(self.br_id)
                self.load_items_from_db()
            else:
                QMessageBox.warning(self, "Erreur", msg)

    def reject(self):
        """يتم استدعاؤها عند الضغط على Cancel أو زر الإغلاق X أو ESC"""
        # نتحقق فقط إذا كان المستخدم كتب بيانات في الحقول ولم يضغط "Ajouter"
        if self.is_input_dirty():
            reply = QMessageBox.question(
                self, "Quitter", 
                "Il y a des informations saisies non ajoutées à la liste. Voulez-vous vraiment quitter ?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        # إذا كانت الحقول فارغة أو وافق المستخدم على الخروج، نغلق فوراً دون أي رسائل حفظ
        super().reject()

    def accept(self):
        """
        زر الموافقة النهائي: لم يعد له دور في الحفظ (لأن الحفظ فوري)، 
        لذا نقوم فقط بإغلاق النافذة بنجاح.
        """
        super().accept()

    def clear_inputs(self):
        
        self.cb_product.setCurrentIndex(0)  
        self.cb_unit_type.clear()
        self.cb_location.setCurrentIndex(0) 
        
        self.inp_lot.clear()
        self.inp_qty.setValue(1)
        self.inp_price.setValue(0.0)
        self.inp_remise.setValue(0.0)
        self.inp_observation.clear()
        
        self.inp_expiry.setDate(QDate.currentDate().addYears(2))
        
        self.current_editing_row = -1
        self.btn_add.setText(" Ajouter")
        self.btn_add.setStyleSheet("") 
        
        self.cb_product.setFocus()

    def is_input_dirty(self):
        """التحقق مما إذا كان هناك بيانات مكتوبة في الحقول ولم تُضف للجدول بعد."""
        return (self.cb_product.currentIndex() > 0 or 
                self.inp_lot.text().strip() != "" or 
                self.inp_price.value() > 0)


    def delete_selected_row(self):
        row = self.table_items.currentRow()
        if row < 0: return

        item_0 = self.table_items.item(row, 0)
        meta = item_0.data(Qt.UserRole)
        batch_id = meta.get('Batch_ID')

        if not batch_id: return

        reply = QMessageBox.question(self, "Confirmation", 
                                    "Supprimer définitivement ce produit du stock ?", 
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            mgr = self.get_reception_mgr()
            success, msg = mgr.delete_reception_line(batch_id)
            if success:
                mgr._recalculate_reception_totals(self.br_id)
                self.load_items_from_db()
            else:
                QMessageBox.warning(self, "Action Impossible", msg)

    def print_selected_labels(self):
        rows = set(index.row() for index in self.table_items.selectedIndexes())
        if not rows: return

        for row in rows:
            meta = self.table_items.item(row, 0).data(Qt.UserRole)
            
            product_name = self.table_items.item(row, 0).text()
            
            barcode_val = self.table_items.item(row, 1).text()
            lot = self.table_items.item(row, 4).text() 
            expiry = self.table_items.item(row, 5).text()
            
            qty = int(meta.get('Qty_Received', 1))

            copies, ok = QInputDialog.getInt(self, "Impression", f"Copies pour {product_name}", qty, 1, 1000)
            if ok:
                self.printer.print_label(product_name, barcode_val, lot, expiry, copies)


    def is_barcode_exists_in_table(self, barcode):
        """دالة مساعدة للتحقق من وجود الباركود في الجدول"""
        for row in range(self.table_items.rowCount()):
            # العمود رقم 1 هو الذي يحتوي على الباركود الظاهر
            item = self.table_items.item(row, 1)
            if item and item.text() == barcode:
                return True
                
            # تحقق إضافي من البيانات المخفية (Meta) للتأكد التام
            meta_item = self.table_items.item(row, 0)
            if meta_item:
                meta = meta_item.data(Qt.UserRole)
                if meta and meta.get('Internal_Barcode') == barcode:
                    return True
        return False

    def generate_internal_barcode(self):
        """
        توليد باركود فريد للسطر الجديد بدون تجميد الواجهة.
        """
        po_id = self.po_data.get('PO_ID', '0')
        
        # 1. جلب المدير المسؤول عن المخزون
        batch_mgr = self.manager.batches if hasattr(self.manager, 'batches') else None
        if not batch_mgr:
            # طريقة احتياطية إذا لم يتم إيجاد المدير
            from database.inventory_batch_manager import InventoryBatchManager
            batch_mgr = InventoryBatchManager(self.manager.db)

        # 2. جلب الباركود المقترح من قاعدة البيانات
        next_barcode = batch_mgr.get_next_smart_barcode(po_id)
        
        # 3. التأكد من أنه غير موجود في الجدول الحالي للواجهة (لأن السطور لم تُحفظ بعد)
        # إذا وجدناه في الجدول، نزيد الرقم حتى نجد رقماً فارغاً
        base_prefix = str(po_id)
        serial = int(next_barcode[len(base_prefix):])
        
        while self.is_barcode_exists_in_table(next_barcode):
            serial += 1
            next_barcode = f"{base_prefix}{str(serial).zfill(3)}"
            
        return next_barcode
    
    def get_reception_data(self):
        """
        تجلب الحالة الراهنة لعملية الاستقبال.
        مفيدة إذا كنت تريد إرسال النتائج للنافذة الرئيسية أو للطباعة.
        """
        # إذا كان الجدول فارغاً، نعيد None
        if self.table_items.rowCount() == 0:
            return None

        # تجهيز بيانات الرأس (Header)
        invoice_ref = self.invoice_ref.text().strip()
        bl_ref = self.bl_ref.text().strip()

        # تحديد نوع المستند
        doc_type = "None"
        if invoice_ref and bl_ref: doc_type = "Both"
        elif invoice_ref: doc_type = "Facture"
        elif bl_ref: doc_type = "BL"

        # جمع الأصناف من الجدول
        items = []
        for r in range(self.table_items.rowCount()):
            meta = self.table_items.item(r, 0).data(Qt.UserRole)
            if meta:
                items.append(meta)

        # تحديث المجاميع لضمان الدقة
        self.update_totals()

        header_data = {
            "BR_ID": self.br_id, # مهم لمعرفة أي سجل نعدل
            "PO_ID": self.po_data.get('PO_ID'),
            "Supplier_ID": self.po_data.get('Supplier_ID'),
            "Supplier_Invoice_Ref": invoice_ref or None,
            "Supplier_BL_Ref": bl_ref or None,
            "Document_Type": doc_type,
            "Reception_Date": self.reception_date.date().toPyDate(),
            "Invoice_Total_HT": round(self.total_ht_val, 2),
            "Invoice_Total_TVA": round(self.total_tva_val, 2),
            "Invoice_Total_TTC": round(self.total_ttc_val, 2),
            "Total_Discount": round(self.total_remise_val, 2)
        }

        return header_data, items

    def accept(self):
        """إغلاق النافذة فقط لأن البيانات تُحفظ تلقائياً عند إضافة كل سطر."""
        super().accept()

    def reject(self):
        """التحقق من وجود بيانات عالقة في الحقول قبل الخروج."""
        if self.is_input_dirty():
            reply = QMessageBox.question(self, "Quitter", 
                "Il y a des données non ajoutées dans les champs de saisie. Voulez-vous vraiment quitter ?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return
        super().reject()

    
        
    def closeEvent(self, event):
        """تأكيد الخروج عند الضغط على X الزاوية"""
        if self.is_input_dirty():
            reply = QMessageBox.question(
                self, "Données non ajoutées", 
                "Vous avez saisi des informations sans.\nVoulez-vous vraiment quitter ?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def reject(self):
        """
        عند الضغط على ESC أو Cancel:
        - إذا اخترت حفظ: نحاول الحفظ، وإذا نجح نغلق النافذة يدوياً.
        """
        if self.table_items.rowCount() == 0:
            super().reject()
            return

        msg_box = QMessageBox(self) 
        msg_box.setWindowTitle("Modifications en cours")
        msg_box.setText("La liste contient des éléments non enregistrés.\n\nVoulez-vous enregistrer avant de quitter ?")
        msg_box.setIcon(QMessageBox.Question)

        btn_save = msg_box.addButton("Enregistrer", QMessageBox.AcceptRole)
        btn_discard = msg_box.addButton("Rejeter", QMessageBox.DestructiveRole)
        btn_cancel = msg_box.addButton("Annuler", QMessageBox.RejectRole)
        
        msg_box.setDefaultButton(btn_save)
        msg_box.exec()

        clicked_button = msg_box.clickedButton()

        if clicked_button == btn_save:
            # إذا نجح الحفظ، نغلق النافذة
            if self.accept():
                super().accept()
                
        elif clicked_button == btn_discard:
            super().reject()
            
        else:
            return


    def highlight_target_row(self):
        """
        البحث عن السطر الذي يحتوي على Batch_ID المستهدف، تلوينه بالأخضر، والتمرير إليه.
        """
        if not self.target_batch_id:
            return

        found_row = -1
        
        # البحث في الجدول
        for row in range(self.table_items.rowCount()):
            item = self.table_items.item(row, 0)
            if not item: continue
            
            meta = item.data(Qt.UserRole)
            if meta and meta.get('Batch_ID') == self.target_batch_id:
                found_row = row
                break
        
        if found_row != -1:
            self.table_items.selectRow(found_row)
            
            self.table_items.scrollToItem(
                self.table_items.item(found_row, 0),
                QAbstractItemView.PositionAtCenter
            )
            
            green_brush = QColor("#d4edda") # لون أخضر فاتح مريح للعين
            
            for col in range(self.table_items.columnCount()):
                cell = self.table_items.item(found_row, col)
                if cell:
                    cell.setBackground(green_brush)
                    # اختياري: جعل الخط عريضاً
                    f = cell.font()
                    f.setBold(True)
                    cell.setFont(f)