import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QHeaderView, 
    QCompleter, QPushButton, QLabel, QLineEdit, QComboBox, 
    QDateEdit, QGroupBox, QSpinBox, QDoubleSpinBox, QMessageBox, 
    QTableWidgetItem, QFrame, QAbstractItemView
)
from PySide6.QtCore import Qt, QDate, Signal, QStringListModel, QTimer
from PySide6.QtGui import QColor, QFont
import qtawesome as qta


class BarcodeLineEdit(QLineEdit):
    """كلاس مخصص لدعم أجهزة المسح على لوحة مفاتيح AZERTY"""
    def keyPressEvent(self, event):
        # خريطة موسعة لدعم كافة أرقام AZERTY من 0-9
        azerty_map = {
            Qt.Key_Ampersand: "1", Qt.Key_Eacute: "2", Qt.Key_QuoteDbl: "3",
            Qt.Key_QuoteLeft: "4", Qt.Key_ParenLeft: "5", Qt.Key_Minus: "6",
            Qt.Key_Egrave: "7", Qt.Key_Underscore: "8", Qt.Key_Ccedilla: "9",
            Qt.Key_Agrave: "0"
        }
        # إذا ضغط الماسح (Shift+رقم) أو أرسل الرمز مباشرة
        if event.key() in azerty_map:
            self.insert(azerty_map[event.key()])
            event.accept()
        else:
            super().keyPressEvent(event)

class InvoiceEditorWidget(QWidget):
    """
    واجهة محرر الفواتير ووصولات التسليم الاحترافية.
    تتميز ببحث ذكي، تصميم بطاقات عصري، وتوافق كامل مع Excel-Style UI.
    """
    request_back = Signal()

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.current_id = None
        self.batches_cache = []
        self.search_map = {}
        self.barcode_map = {}
        self.current_transfer_batch_ids = set()
        self.current_transfer_qty_by_batch = {}
        self.current_transfer_details = []
        
        self.init_ui()
        self.apply_internal_styles()
        

    def apply_internal_styles(self):
        """تحسينات إضافية تتوافق مع ملف QSS الرئيسي"""
        self.setStyleSheet("""
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #cfd8dc;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 20px;
            }
            QGroupBox::title {
                color: #007572;
                font-weight: bold;
                left: 15px;
            }
            /* تنسيق حقل البحث الذكي المميز */
            QLineEdit#smart_search {
                border: 2px solid #3498db;
                border-radius: 22px;
                padding: 10px 20px;
                font-size: 15px;
                background-color: #f8f9fa;
            }
            QLineEdit#smart_search:focus {
                border: 2px solid #2ecc71;
                background-color: #ffffff;
            }
            /* تنسيق خاص للجدول لضمان عدم ضيق الحقول */
            QTableWidget::item {
                padding: 0px;
            }
        """)

    def init_ui(self):
        """النسخة المصححة لدالة بناء الواجهة لدعم الباركود الذكي"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 10, 20, 20)

        # --- 1. الشريط العلوي (العنوان والعودة) ---
        top_bar = QHBoxLayout()
        self.btn_back = QPushButton("  Retour à la liste")
        self.btn_back.setIcon(qta.icon("fa5s.arrow-left", color="#2c3e50"))
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.setStyleSheet("border: none; font-weight: bold; font-size: 14px; color: #2c3e50;")
        self.btn_back.clicked.connect(self.request_back.emit)
        
        self.lbl_title = QLabel("NOUVELLE FACTURE / BL")
        self.lbl_title.setStyleSheet("font-size: 18px; font-weight: 800; color: #007572;")
        
        top_bar.addWidget(self.btn_back)
        top_bar.addStretch()
        top_bar.addWidget(self.lbl_title)
        layout.addLayout(top_bar)

        # --- 2. بطاقة المعلومات العامة ---
        header_group = QGroupBox("Informations Générales")
        h_layout = QHBoxLayout(header_group)
        
        self.inp_date = QDateEdit(QDate.currentDate())
        self.inp_date.setCalendarPopup(True)
        self.inp_date.setMinimumHeight(40)
        
        self.combo_partner = QComboBox()
        self.combo_partner.setMinimumHeight(40)
        self.combo_partner.setPlaceholderText("Sélectionner un client...")
        
        h_layout.addWidget(QLabel("Date :"))
        h_layout.addWidget(self.inp_date)
        h_layout.addSpacing(40)
        h_layout.addWidget(QLabel("Partenaire :"))
        h_layout.addWidget(self.combo_partner, stretch=1)
        layout.addWidget(header_group)

        # --- 3. بطاقة البحث والجدول ---
        items_group = QGroupBox("Détails des Articles")
        items_layout = QVBoxLayout(items_group)

        # حقل البحث الذكي (تم التغيير إلى BarcodeLineEdit لدعم أجهزة المسح)
        self.barcode_input = BarcodeLineEdit() 
        self.barcode_input.setObjectName("smart_search")
        self.barcode_input.setPlaceholderText("🔎 Scanner le code-barres ou rechercher par Nom, Lot...")
        
        # إعداد الـ Completer
        self.completer = QCompleter(self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.barcode_input.setCompleter(self.completer)
        
        self.completer.activated.connect(self.on_search_selected)
        self.barcode_input.returnPressed.connect(self.handle_barcode_scan)
        
        items_layout.addWidget(self.barcode_input)

        # الجدول
        self.table = QTableWidget(0, 6)
        headers = ["Article / Lot / Stock", "Quantité", "P.U (DA)", "Observation", "Total", ""]
        self.table.setHorizontalHeaderLabels(headers)
        
        h_header = self.table.horizontalHeader()
        h_header.setSectionResizeMode(0, QHeaderView.Stretch)
        h_header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 130)
        self.table.setColumnWidth(4, 130)
        self.table.setColumnWidth(5, 40)
        
        self.table.verticalHeader().setDefaultSectionSize(45)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        items_layout.addWidget(self.table)
        layout.addWidget(items_group)

        # --- 4. الشريط السفلي (المجاميع والحفظ) ---
        footer_frame = QFrame()
        footer_frame.setStyleSheet("background-color: #ecf0f1; border-radius: 8px; padding: 10px;")
        footer_layout = QHBoxLayout(footer_frame)

        self.lbl_total = QLabel("0.00 DA")
        self.lbl_total.setStyleSheet("font-size: 26px; font-weight: bold; color: #c0392b;")
        
        self.btn_save = QPushButton("  VALIDER ET ENREGISTRER")
        self.btn_save.setIcon(qta.icon("fa5s.save", color="white"))
        self.btn_save.setMinimumHeight(50)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet("""
            QPushButton { background-color: #007572; color: white; border-radius: 25px; padding: 0 40px; font-size: 15px; font-weight: bold; }
            QPushButton:hover { background-color: #005f5c; }
        """)
        self.btn_save.clicked.connect(self.save_invoice)

        footer_layout.addWidget(QLabel("<b>MONTANT TOTAL À PAYER :</b>"))
        footer_layout.addWidget(self.lbl_total)
        footer_layout.addStretch()
        footer_layout.addWidget(self.btn_save)
        layout.addWidget(footer_frame)
        self.barcode_input.textChanged.connect(self.check_instant_barcode)

    # =========================================================================
    # منطق العمليات (Data Logic)
    # =========================================================================


    def load_transfer_data(self, transfer_id, details=None):
        try:
            mgr = self.manager.external_transfers
            all_transfers = mgr.get_all_transfers()
            header = next((t for t in all_transfers if t['Transfer_ID'] == transfer_id), None)
            
            if header:
                index = self.combo_partner.findData(header['Partner_ID'])
                if index >= 0: self.combo_partner.setCurrentIndex(index)
                # تعيين التاريخ ...

            if details is None:
                details = mgr.get_transfer_details(transfer_id)
            self.table.setRowCount(0)
            
            for item in details:
                batch_data = next((b for b in self.batches_cache if b['Batch_ID'] == item['Batch_ID']), None)
                
                if batch_data:
                    # نمرر الكمية القديمة هنا ليتم احتسابها ضمن الحد الأقصى
                    saved_qty = int(item['Qty_Transferred'])
                    self.add_batch_to_invoice(batch_data, initial_qty=saved_qty)
                    
                    # تحديث السعر والملاحظة للسطر المضاف
                    last_row = self.table.rowCount() - 1
                    self.table.cellWidget(last_row, 2).setValue(float(item['Unit_Price']))
                    self.table.cellWidget(last_row, 3).setText(item.get('Line_Note', ''))
            
            self.calc_totals()
        except Exception as e:
            logging.error(f"Error loading: {e}", exc_info=True)

    def prepare_transfer_scope(self, transfer_id):
        self.current_transfer_batch_ids = set()
        self.current_transfer_qty_by_batch = {}
        self.current_transfer_details = []

        if not transfer_id or not hasattr(self.manager, 'external_transfers'):
            return

        self.current_transfer_details = self.manager.external_transfers.get_transfer_details(transfer_id)
        for item in self.current_transfer_details:
            batch_id = item.get('Batch_ID')
            if batch_id is None:
                continue
            self.current_transfer_batch_ids.add(batch_id)
            self.current_transfer_qty_by_batch[batch_id] = float(item.get('Qty_Transferred') or 0)

    def load_context(self, transfer_id=None):
        """تحميل الواجهة وتحديد هل نحتاج للمنتجات الصفرية أم لا."""
        self.current_id = transfer_id
        self.table.setRowCount(0)
        
        # إذا كان هناك ID، فهذا يعني "تعديل"، لذا نحتاج لجلب المنتجات الصفرية
        self.prepare_transfer_scope(transfer_id)
        include_zero = True if transfer_id else False
        self.refresh_batches_cache(include_zero=include_zero)
        
        self.load_partners() #
        
        if transfer_id:
            # التعديل هنا: عرض المعرف المنسق في العنوان
            formatted_ref = self.format_id(transfer_id)
            self.lbl_title.setText(f"MODIFICATION TRANSACTION N° {formatted_ref}")
            self.load_transfer_data(transfer_id, self.current_transfer_details)
        else:
            self.lbl_title.setText("NOUVELLE TRANSACTION / BL")
            self.inp_date.setDate(QDate.currentDate())
        
        self.calc_totals() #
        self.barcode_input.setFocus()

    def load_partners(self):
        self.combo_partner.clear()
        self.combo_partner.addItem("Sélectionner un client...", None)
        if hasattr(self.manager, 'partners'):
            for p in self.manager.partners.get_all_partners():
                self.combo_partner.addItem(f"{p['Partner_Name']} ({p.get('City', '-')})", p['Partner_ID'])

    def check_instant_barcode(self, text):
        """التحقق من الباركود بمجرد الكتابة أو المسح"""
        clean_text = text.strip().lower()
        
        # إذا كان النص المكتوب يطابق تماماً أحد الأكواد في القاموس
        if clean_text in self.barcode_map:
            batch = self.barcode_map[clean_text]
            
            # منع التكرار الفوري الناتج عن سرعة الماسح
            self.barcode_input.blockSignals(True) 
            self.add_batch_to_invoice(batch) # استدعاء دالة الإضافة الأصلية
            self.barcode_input.clear()
            self.barcode_input.blockSignals(False)
            
            # تأثير بصري للنجاح
            self.barcode_input.setStyleSheet("border: 2px solid #2ecc71; background-color: #e8f5e9;")
            QTimer.singleShot(500, lambda: self.barcode_input.setStyleSheet(""))

    def refresh_batches_cache(self, include_zero=False):
        """
        تحديث الكاش مع السماح بجلب الكميات الصفرية في حالة التعديل 
        لضمان ظهور المنتجات المباعة بالكامل.
        """
        if hasattr(self.manager, 'batches'):
            # إذا كنا في وضع التعديل، نطلب من المدير جلب حتى المنتجات الصفرية
            all_batches = self.manager.batches.get_all_batches_with_details(
                include_zero_stock=include_zero
            )
            self.batches_cache = self.filter_batches_for_transfer_scope(all_batches)
            
            suggestions = []
            self.search_map = {}
            self.barcode_map = {}

            for b in self.batches_cache:
                qty = float(b['Quantity_Current'])
                batch_id = b.get('Batch_ID')
                is_current_transfer_batch = batch_id in self.current_transfer_batch_ids
                
                # بناء الفهارس للبحث السريع
                if b.get('Internal_Barcode'):
                    self.barcode_map[str(b['Internal_Barcode']).strip().lower()] = b
                if b.get('Barcode'):
                    self.barcode_map[str(b['Barcode']).strip().lower()] = b

                # في قائمة البحث (الاقتراحات)، نظهر فقط ما هو أكبر من الصفر 
                # لكي لا يختار المستخدم منتجاً منتهياً بالخطأ في فاتورة جديدة
                # Edit mode also keeps lots already present in this BL.
                if qty > 0 or is_current_transfer_batch:
                    barcode = b.get('Internal_Barcode') or b.get('Barcode') or "---"
                    txt = f"[{barcode}] {b['Product_Name']} | Lot: {b['Lot_Number']} | 📍 {b.get('Location_Name','-')}"
                    suggestions.append(txt)
                    self.search_map[txt] = b

            self.completer.setModel(QStringListModel(suggestions))

    def filter_batches_for_transfer_scope(self, batches):
        if not self.current_id:
            return batches

        scoped_batches = []
        for batch in batches:
            batch_id = batch.get('Batch_ID')
            qty = float(batch.get('Quantity_Current') or 0)
            if qty > 0 or batch_id in self.current_transfer_batch_ids:
                scoped_batches.append(batch)
        return scoped_batches

    def on_search_selected(self, text):
        batch = self.search_map.get(text)
        if batch:
            self.add_batch_to_invoice(batch)
            QTimer.singleShot(0, self.barcode_input.clear)


    def show_scan_feedback(self, success):
        """تأثير بصري (وميض) للحقل عند المسح"""
        color = "#2ecc71" if success else "#e74c3c" # أخضر للنجاح، أحمر للفشل
        self.barcode_input.setStyleSheet(f"border: 2px solid {color}; border-radius: 22px; padding: 10px 20px;")
        # العودة للتصميم الطبيعي بعد 300 ميلي ثانية
        QTimer.singleShot(300, lambda: self.barcode_input.setStyleSheet(""))

    def handle_barcode_scan(self):
        """التعامل مع إدخال الماسح الضوئي (Scanner)"""
        if self.completer.popup().isVisible(): 
            return
            
        raw_text = self.barcode_input.text().strip().lower()
        if not raw_text: 
            return

        # 1. البحث المباشر في خريطة الباركود (السرعة القصوى)
        match = self.barcode_map.get(raw_text)

        # 2. إذا لم يتم العثور على تطابق مباشر، نجرب تنظيف النص (Normalization)
        if not match:
            clean_input = raw_text.replace("-", "").replace(" ", "")
            # نبحث في القيم النظيفة داخل الماب
            for code, data in self.barcode_map.items():
                if code.replace("-", "").replace(" ", "") == clean_input:
                    match = data
                    break

        if match:
            # إضافة المنتج للجدول
            self.add_batch_to_invoice(match)
            self.show_scan_feedback(True)
        else:
            # إشعار المستخدم بعدم وجود المنتج
            self.show_scan_feedback(False)

        self.barcode_input.clear()
        self.barcode_input.setFocus()
        
    def add_batch_to_invoice(self, batch, initial_qty=1):
        """إضافة المنتج للجدول مع تصحيح أخطاء sb_qty وربط الحسابات"""
        # منع التكرار وزيادة الكمية فقط
        for r in range(self.table.rowCount()):
            table_item = self.table.item(r, 0)
            if table_item:
                data = table_item.data(Qt.UserRole)
                if data and data.get('batch_id') == batch['Batch_ID']:
                    sb = self.table.cellWidget(r, 1)
                    if sb and sb.value() < sb.maximum():
                        sb.setValue(sb.value() + 1)
                    return

        # استخراج حالة الفوترة والبيانات
        is_billable = batch.get('Is_Billable', False)
        status_tag = " [PAYANT]" if is_billable else " [GRATUIT]"
        row = self.table.rowCount()
        self.table.insertRow(row)

        p_name = f"{batch['Product_Name']} (Lot: {batch['Lot_Number']}){status_tag}"
        q_item = QTableWidgetItem(p_name)
        q_item.setData(Qt.UserRole, {
            'id': batch['Product_ID'], 
            'batch_id': batch['Batch_ID'],
            'is_billable': is_billable
        })
        if not is_billable:
            q_item.setForeground(QColor("#7f8c8d")) 
        self.table.setItem(row, 0, q_item)

        # بناء مربعات الإدخال
        current_stock = int(float(batch.get('Quantity_Current', 0)))
        previous_qty = int(float(self.current_transfer_qty_by_batch.get(batch['Batch_ID'], 0)))
        max_allowed = current_stock + previous_qty
        if max_allowed <= 0:
            QMessageBox.warning(self, "Stock insuffisant", "Ce lot n'est pas disponible pour cette transaction.")
            return
        if initial_qty > max_allowed:
            initial_qty = max_allowed
        
        sb_qty = QSpinBox()
        sb_qty.setRange(1, max_allowed); sb_qty.setValue(initial_qty); sb_qty.setAlignment(Qt.AlignCenter)
        
        unit_price = float(batch.get('Unit_Price_Received', 0))
        sb_price = QDoubleSpinBox()
        sb_price.setRange(0, 1000000); sb_price.setValue(unit_price); sb_price.setGroupSeparatorShown(True)

        txt_obs = QLineEdit()
        txt_obs.setPlaceholderText("Note...")

        lbl_line = QLabel("0.00")
        lbl_line.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_line.setStyleSheet("font-weight: bold; color: #2980b9; padding-right: 5px;")

        btn_del = QPushButton("✕")
        btn_del.setStyleSheet("color: #e74c3c; font-weight: bold; border: none;")
        btn_del.clicked.connect(lambda: self.remove_row_at_btn(btn_del))

        # وضع الـ Widgets في الجدول
        self.table.setCellWidget(row, 1, sb_qty)
        self.table.setCellWidget(row, 2, sb_price)
        self.table.setCellWidget(row, 3, txt_obs)
        self.table.setCellWidget(row, 4, lbl_line)
        self.table.setCellWidget(row, 5, btn_del)

        # ربط الإشارات بالحسابات بعد بناء الصف
        sb_qty.valueChanged.connect(self.calc_totals)
        sb_price.valueChanged.connect(self.calc_totals)

        self.calc_totals()

    def remove_row_at_btn(self, btn):
        for r in range(self.table.rowCount()):
            if self.table.cellWidget(r, 5) == btn:
                self.table.removeRow(r)
                break
        self.calc_totals()

    def format_id(self, raw_id):
        # إذا لم يتوفر التاريخ، نستخدم السنة الحالية
        year = self.inp_date.date().toString("yyyy")
        return f"{year}/{int(raw_id):03d}"

    def calc_totals(self):
        """حساب المجاميع مع حماية ضد NoneType"""
        grand = 0.0
        for r in range(self.table.rowCount()):
            qty_widget = self.table.cellWidget(r, 1)
            price_widget = self.table.cellWidget(r, 2)
            total_label = self.table.cellWidget(r, 4)
            
            if qty_widget and price_widget and total_label:
                line = qty_widget.value() * price_widget.value()
                total_label.setText(f"{line:,.2f}")
                grand += line
                
        self.lbl_total.setText(f"{grand:,.2f} DA")

    def save_invoice(self):
        """
        حفظ الفاتورة مع التحقق من اختيار الزبون ووجود سلع.
        تستدعي منطق المزامنة مع المخزون والـ Log.
        """
        partner_id = self.combo_partner.currentData()
        
        # 1. التحقق من اختيار الزبون (المطلب الجديد)
        if not partner_id:
            QMessageBox.warning(
                self, 
                "Attention", 
                "Veuillez sélectionner un client avant de valider la transaction."
            )
            return

        # 2. التحقق من وجود سلع في الجدول
        if self.table.rowCount() == 0:
            QMessageBox.warning(
                self, 
                "Facture Vide", 
                "Veuillez ajouter au moins un article à la liste."
            )
            return

        # 3. تجميع البيانات من الواجهة
        items = []
        for r in range(self.table.rowCount()):
            table_item = self.table.item(r, 0)
            if not table_item: continue
            
            meta = table_item.data(Qt.UserRole)
            items.append({
                'product_id': meta['id'],
                'batch_id': meta['batch_id'],
                'qty': self.table.cellWidget(r, 1).value(), # تم تصحيح .value() بدلاً من .val
                'price': self.table.cellWidget(r, 2).value(),
                'note': self.table.cellWidget(r, 3).text()
            })

        try:
            # الحصول على معرف المستخدم الحالي للتسجيل في الـ Log
            u_id = 1
            if hasattr(self.window(), 'current_user') and self.window().current_user:
                u_id = self.window().current_user.get('User_ID', 1)

            # استدعاء دالة المزامنة التي قمنا بتصحيحها سابقاً لتسجيل الـ Log
            #
            success, result = self.manager.external_transfers.save_and_sync_stock(
                self.current_id, partner_id, items, u_id
            )
            
            if success:
                QMessageBox.information(
                    self, 
                    "Succès", 
                    "La transaction a été enregistrée et le stock mis à jour avec succès."
                )
                self.request_back.emit() # العودة للقائمة
            else:
                QMessageBox.critical(self, "Erreur", f"Échec de l'enregistrement : {result}")
        except Exception as e:
            logging.error(f"Save Invoice Error: {e}")
            QMessageBox.critical(self, "Erreur Technique", str(e))
