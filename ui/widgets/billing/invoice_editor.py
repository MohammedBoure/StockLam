import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QHeaderView,
    QCompleter, QPushButton, QLabel, QLineEdit, QComboBox,
    QDateEdit, QDateTimeEdit, QGroupBox, QSpinBox, QDoubleSpinBox, QMessageBox,
    QTableWidgetItem, QFrame, QAbstractItemView
)
from PySide6.QtCore import Qt, QDate, QDateTime, Signal, QStringListModel, QTimer
from PySide6.QtGui import QColor, QFont
import qtawesome as qta

from ui.formatting import quantity_to_int, format_quantity, format_money


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
        self.is_loading_transfer = False
        self.is_persisting_transfer = False
        self.last_persist_signature = None
        self.transfer_type_mode = 'Outbound'
        self.locked_return_partner_id = None
        self.allowed_return_batch_ids = set()

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

        self.inp_date = QDateTimeEdit(QDateTime.currentDateTime())
        self.inp_date.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.inp_date.setCalendarPopup(True)
        self.inp_date.setMinimumHeight(40)

        self.combo_partner = QComboBox()
        self.combo_partner.setMinimumHeight(40)
        self.btn_validate_header = QPushButton("Valider l'en-tete")
        self.btn_validate_header.setMinimumHeight(40)
        self.btn_validate_header.setCursor(Qt.PointingHandCursor)
        self.btn_validate_header.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; border-radius: 6px; padding: 0 16px;")
        self.btn_validate_header.clicked.connect(self.handle_header_click)
        self.combo_partner.setPlaceholderText("Sélectionner un client...")
        self.combo_partner.currentIndexChanged.connect(self.on_partner_changed)

        h_layout.addWidget(QLabel("Date :"))
        h_layout.addWidget(self.inp_date)
        h_layout.addSpacing(40)
        h_layout.addWidget(QLabel("Partenaire :"))
        h_layout.addWidget(self.combo_partner, stretch=1)
        h_layout.addWidget(self.btn_validate_header)
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
        self.table = QTableWidget(0, 7)
        headers = ["Article", "Source (Stock)", "Quantité", "P.U", "Observation", "Total", ""]
        self.table.setHorizontalHeaderLabels(headers)

        h_header = self.table.horizontalHeader()
        h_header.setSectionResizeMode(0, QHeaderView.Stretch)
        h_header.setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setColumnWidth(1, 250)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 110)
        self.table.setColumnWidth(5, 110)
        self.table.setColumnWidth(6, 40)

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

        self.lbl_total = QLabel("0,00 DA")
        self.lbl_total.setStyleSheet("font-size: 26px; font-weight: bold; color: #c0392b;")

        footer_layout.addWidget(QLabel("<b>MONTANT TOTAL À PAYER :</b>"))
        footer_layout.addWidget(self.lbl_total)
        footer_layout.addStretch()
        layout.addWidget(footer_frame)
        header_group.raise_()
        self.barcode_input.textChanged.connect(self.check_instant_barcode)

    # =========================================================================
    # منطق العمليات (Data Logic)
    # =========================================================================


    def is_return_mode(self):
        return getattr(self, 'transfer_type_mode', 'Outbound') == 'Return'

    def get_effective_return_partner_id(self):
        if not self.is_return_mode():
            return None

        partner_id = self.locked_return_partner_id or self.combo_partner.currentData()
        try:
            return int(partner_id) if partner_id else None
        except (TypeError, ValueError):
            return None

    def sync_return_partner_combo(self, partner_id):
        if not partner_id:
            return
        index = self.combo_partner.findData(partner_id)
        if index >= 0 and self.combo_partner.currentIndex() != index:
            previous_block = self.combo_partner.blockSignals(True)
            self.combo_partner.setCurrentIndex(index)
            self.combo_partner.blockSignals(previous_block)

    def on_partner_changed(self):
        if self.is_return_mode():
            partner_id = self.get_effective_return_partner_id()
            if partner_id and not self.locked_return_partner_id:
                self.locked_return_partner_id = partner_id
            self.sync_return_partner_combo(partner_id)
            self.refresh_batches_cache(include_zero=True)
            self.table.setRowCount(0)

    def load_transfer_data(self, transfer_id, details=None):
        try:
            mgr = self.manager.external_transfers
            all_transfers = mgr.get_all_transfers()
            header = next((t for t in all_transfers if t['Transfer_ID'] == transfer_id), None)

            if header:
                index = self.combo_partner.findData(header['Partner_ID'])
                if index >= 0:
                    previous_block = self.combo_partner.blockSignals(True)
                    self.combo_partner.setCurrentIndex(index)
                    self.combo_partner.blockSignals(previous_block)
                if header.get('Transaction_Date'):
                    dt_str = str(header['Transaction_Date'])
                    if len(dt_str) >= 16: # Format: YYYY-MM-DD HH:MM...
                        self.inp_date.setDateTime(QDateTime.fromString(dt_str[:16], "yyyy-MM-dd HH:mm"))
                    else:
                        self.inp_date.setDate(QDate.fromString(dt_str[:10], "yyyy-MM-dd"))

            if details is None:
                details = mgr.get_transfer_details(transfer_id)
            self.table.setRowCount(0)
            self.is_loading_transfer = True
            
            if header and header.get('Ref_Transfer_ID'):
                self.ref_transfer_id = header.get('Ref_Transfer_ID')

            for item in details:
                batch_data = next((b for b in self.batches_cache if b['Batch_ID'] == item['Batch_ID']), None)

                if batch_data:
                    # نمرر الكمية القديمة هنا ليتم احتسابها ضمن الحد الأقصى
                    saved_qty = int(item['Qty_Transferred'])
                    self.add_batch_to_invoice(batch_data, initial_qty=saved_qty)

                    # تحديث السعر والملاحظة للسطر المضاف
                    last_row = self.table.rowCount() - 1
                    self.table.cellWidget(last_row, 3).setValue(float(item['Unit_Price']))
                    self.table.cellWidget(last_row, 4).setText(item.get('Line_Note', ''))

            self.is_loading_transfer = False
            self.calc_totals()
            self.last_persist_signature = self.items_signature(self.build_items_data())
        except Exception as e:
            self.is_loading_transfer = False
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

    def load_context(self, transfer_id=None, preselected_partner_id=None):
        """تحميل الواجهة وتحديد هل نحتاج للمنتجات الصفرية أم لا."""
        self.current_id = transfer_id
        self.table.setRowCount(0)
        self.last_persist_signature = None
        self.locked_return_partner_id = None
        self.allowed_return_batch_ids = set()
        header = None

        if transfer_id:
            try:
                mgr = self.manager.external_transfers
                all_transfers = mgr.get_all_transfers()
                header = next((t for t in all_transfers if t['Transfer_ID'] == transfer_id), None)
                if header:
                    self.transfer_type_mode = header.get('Transfer_Type') or 'Outbound'
            except Exception as e:
                logging.error(f"Error fetching transfer type: {e}")

        ttype = getattr(self, 'transfer_type_mode', 'Outbound')
        partner_to_select = header.get('Partner_ID') if header else preselected_partner_id
        if ttype == 'Return' and partner_to_select:
            self.locked_return_partner_id = int(partner_to_select)

        self.prepare_transfer_scope(transfer_id)

        previous_block = self.combo_partner.blockSignals(True)
        self.load_partners()
        if partner_to_select:
            index = self.combo_partner.findData(partner_to_select)
            if index >= 0:
                self.combo_partner.setCurrentIndex(index)
        self.combo_partner.blockSignals(previous_block)

        include_zero = True if transfer_id else False
        self.refresh_batches_cache(include_zero=include_zero)

        if transfer_id:
            formatted_ref = self.format_id(transfer_id)
            if ttype == 'Return':
                self.lbl_title.setText(f"MODIFICATION BON DE RETOUR N° {formatted_ref}")
            else:
                self.lbl_title.setText(f"MODIFICATION TRANSACTION N° {formatted_ref}")
            self.load_transfer_data(transfer_id, self.current_transfer_details)
        else:
            if ttype == 'Return':
                self.lbl_title.setText("NOUVEAU BON DE RETOUR")
            else:
                self.lbl_title.setText("NOUVELLE TRANSACTION / BL")
            self.inp_date.setDate(QDate.currentDate())
        self.set_header_enabled(not bool(transfer_id))

        self.calc_totals()
        self.barcode_input.setFocus()

    def load_partners(self):
        self.combo_partner.clear()
        self.combo_partner.addItem("Sélectionner un client...", None)
        if hasattr(self.manager, 'partners'):
            for p in self.manager.partners.get_all_partners():
                self.combo_partner.addItem(f"{p['Partner_Name']} ({p.get('City', '-')})", p['Partner_ID'])

    def get_current_user_id(self):
        if hasattr(self.window(), 'current_user') and self.window().current_user:
            return self.window().current_user.get('User_ID', 1)
        return 1

    def set_header_enabled(self, enabled):
        self.inp_date.setEnabled(enabled)
        self.combo_partner.setEnabled(enabled and not self.locked_return_partner_id)
        if enabled:
            self.btn_validate_header.setText("Valider l'en-tete")
            self.btn_validate_header.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; border-radius: 6px; padding: 0 16px;")
        else:
            self.btn_validate_header.setText("Modifier l'en-tete")
            self.btn_validate_header.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold; border-radius: 6px; padding: 0 16px;")

    def save_header_only(self, show_message=True):
        transfer_type = getattr(self, 'transfer_type_mode', 'Outbound')
        partner_id = self.get_effective_return_partner_id() if transfer_type == 'Return' else self.combo_partner.currentData()
        if not partner_id:
            QMessageBox.warning(self, "Attention", "Veuillez selectionner un partenaire.")
            return False

        if transfer_type == 'Return':
            partner_id = int(partner_id)
            if self.locked_return_partner_id and partner_id != self.locked_return_partner_id:
                QMessageBox.warning(self, "Attention", "Le bon de retour doit garder le meme partenaire que le transfert d'origine.")
                return False
            self.locked_return_partner_id = partner_id
            self.sync_return_partner_combo(partner_id)

        if self.locked_return_partner_id and int(partner_id) != self.locked_return_partner_id:
            QMessageBox.warning(self, "Attention", "Le bon de retour doit garder le meme partenaire que le transfert d'origine.")
            return False

        transaction_date = self.inp_date.dateTime().toString("yyyy-MM-dd HH:mm:ss")
        success, msg, transfer_id = self.manager.external_transfers.save_transfer_header_only(
            self.current_id,
            partner_id,
            transaction_date,
            self.get_current_user_id(),
            transfer_type=transfer_type,
            ref_transfer_id=getattr(self, 'ref_transfer_id', None)
        )

        if not success:
            QMessageBox.critical(self, "Erreur", msg)
            return False

        self.current_id = transfer_id
        doc_label = "Retourné à Sous-Traitant" if transfer_type == 'Return' else "TRANSACTION / BL"
        self.lbl_title.setText(f"{doc_label} N° {self.format_id(transfer_id)}")
        self.set_header_enabled(False)
        if show_message:
            QMessageBox.information(self, "Succes", "L'en-tete a ete enregistre.")
        return True

    def handle_header_click(self):
        if "Modifier" in self.btn_validate_header.text():
            self.set_header_enabled(True)
            self.combo_partner.setFocus()
            return
        self.save_header_only()

    def check_instant_barcode(self, text):
        """التحقق من الباركود بمجرد الكتابة أو المسح"""
        clean_text = text.strip().lower()

        # إذا كان النص المكتوب يطابق تماماً أحد الأكواد في القاموس
        if clean_text in self.barcode_map:
            batch = self.barcode_map[clean_text]
            added = self.add_batch_to_invoice(batch)

            # منع التكرار الفوري الناتج عن سرعة الماسح
            self.barcode_input.blockSignals(True)
            # استدعاء دالة الإضافة الأصلية
            self.barcode_input.clear()
            self.barcode_input.blockSignals(False)

            # تأثير بصري للنجاح
            color = "#2ecc71" if added else "#e74c3c"
            self.barcode_input.setStyleSheet(f"border: 2px solid {color}; background-color: #e8f5e9;")
            QTimer.singleShot(500, lambda: self.barcode_input.setStyleSheet(""))

    def refresh_batches_cache(self, include_zero=False):
        """
        تحديث الكاش مع السماح بجلب الكميات الصفرية في حالة التعديل
        لضمان ظهور المنتجات المباعة بالكامل.
        """
        if hasattr(self.manager, 'batches'):
            # إذا كنا في وضع التعديل، نطلب من المدير جلب حتى المنتجات الصفرية
            ttype = getattr(self, 'transfer_type_mode', 'Outbound')
            if ttype == 'Return':
                partner_id = self.get_effective_return_partner_id()
                if partner_id:
                    self.sync_return_partner_combo(partner_id)
                    all_batches = self.manager.external_transfers.get_returnable_batches_for_partner(partner_id, exclude_return_transfer_id=self.current_id, ref_transfer_id=getattr(self, 'ref_transfer_id', None))
                    self.barcode_input.setPlaceholderText("🔎 Scanner le code-barres ou rechercher par Nom, Lot...")
                    self.barcode_input.setEnabled(True)
                else:
                    all_batches = []
                    self.barcode_input.setPlaceholderText("⚠️ Veuillez d'abord sélectionner un client pour le retour...")
                    self.barcode_input.setEnabled(False)
            else:
                self.barcode_input.setPlaceholderText("🔎 Scanner le code-barres ou rechercher par Nom, Lot...")
                self.barcode_input.setEnabled(True)
                all_batches = self.manager.batches.get_all_batches_with_details(
                    include_zero_stock=include_zero
                )
            self.batches_cache = self.filter_batches_for_transfer_scope(all_batches)
            self.allowed_return_batch_ids = set()

            suggestions = []
            self.search_map = {}
            self.barcode_map = {}

            for b in self.batches_cache:
                qty_source = b.get('Available_To_Return') if ttype == 'Return' else b.get('Quantity_Current')
                qty = quantity_to_int(qty_source or 0)
                batch_id = b.get('Batch_ID')
                is_current_transfer_batch = batch_id in self.current_transfer_batch_ids
                if ttype == 'Return':
                    if not self.is_return_batch_allowed(b, allow_zero=True):
                        continue
                    try:
                        self.allowed_return_batch_ids.add(int(batch_id))
                    except (TypeError, ValueError):
                        continue

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

    def is_return_batch_allowed(self, batch, allow_zero=False):
        if not self.is_return_mode():
            return True

        partner_id = self.get_effective_return_partner_id()
        if not partner_id or not batch:
            return False

        batch_partner_id = batch.get('Partner_ID')
        if batch_partner_id is not None:
            try:
                if int(batch_partner_id) != int(partner_id):
                    return False
            except (TypeError, ValueError):
                return False

        try:
            batch_id = int(batch.get('Batch_ID'))
        except (TypeError, ValueError):
            return False

        qty = quantity_to_int(batch.get('Available_To_Return') or 0)
        if allow_zero:
            return qty > 0 or batch_id in self.current_transfer_batch_ids

        return batch_id in self.allowed_return_batch_ids and (qty > 0 or batch_id in self.current_transfer_batch_ids)

    def filter_batches_for_transfer_scope(self, batches):
        if not self.current_id:
            return batches

        scoped_batches = []
        for batch in batches:
            batch_id = batch.get('Batch_ID')
            qty_source = batch.get('Available_To_Return') if getattr(self, 'transfer_type_mode', 'Outbound') == 'Return' else batch.get('Quantity_Current')
            qty = quantity_to_int(qty_source or 0)
            if qty > 0 or batch_id in self.current_transfer_batch_ids:
                scoped_batches.append(batch)
        return scoped_batches

    def on_search_selected(self, text):
        batch = self.search_map.get(text)
        if batch:
            if self.add_batch_to_invoice(batch):
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
            self.show_scan_feedback(self.add_batch_to_invoice(match))
        else:
            # إشعار المستخدم بعدم وجود المنتج
            self.show_scan_feedback(False)

        self.barcode_input.clear()
        self.barcode_input.setFocus()

    def build_items_data(self):
        items = []
        for r in range(self.table.rowCount()):
            table_item = self.table.item(r, 0)
            if not table_item:
                continue

            meta = table_item.data(Qt.UserRole)
            cb_source = self.table.cellWidget(r, 1)
            selected_batch = cb_source.currentData() if cb_source else None
            batch_id = selected_batch['Batch_ID'] if selected_batch else meta['batch_id']

            items.append({
                'product_id': meta['id'],
                'batch_id': batch_id,
                'qty': self.table.cellWidget(r, 2).value(),
                'price': self.table.cellWidget(r, 3).value(),
                'note': self.table.cellWidget(r, 4).text()
            })
        return items

    def items_signature(self, items):
        return tuple(
            (
                item['product_id'],
                item['batch_id'],
                float(item['qty']),
                float(item['price']),
                item.get('note', '')
            )
            for item in items
        )

    def update_current_transfer_scope_from_items(self, items):
        self.current_transfer_batch_ids = {item['batch_id'] for item in items}
        self.current_transfer_qty_by_batch = {
            item['batch_id']: float(item['qty'])
            for item in items
        }

    def on_line_changed(self):
        self.calc_totals()
        self.persist_current_transfer()

    def persist_current_transfer(self):
        if self.is_loading_transfer or self.is_persisting_transfer:
            return True

        if not self.save_header_only(show_message=False):
            return False

        items = self.build_items_data()
        if self.is_return_mode():
            invalid_batch_ids = [
                item['batch_id'] for item in items
                if item['batch_id'] not in self.allowed_return_batch_ids
                and item['batch_id'] not in self.current_transfer_batch_ids
            ]
            if invalid_batch_ids:
                QMessageBox.warning(self, "Attention", "Certains lots ne sont pas disponibles pour ce sous-traitant.")
                return False
        signature = self.items_signature(items)
        if signature == self.last_persist_signature:
            return True

        self.is_persisting_transfer = True
        try:
            transfer_type = getattr(self, 'transfer_type_mode', 'Outbound')
            if transfer_type == 'Return':
                success, result = self.manager.external_transfers.save_and_sync_return_stock(
                    self.current_id,
                    self.get_effective_return_partner_id(),
                    items,
                    self.get_current_user_id(),
                    ref_transfer_id=getattr(self, 'ref_transfer_id', None)
                )
            else:
                success, result = self.manager.external_transfers.save_and_sync_stock(
                    self.current_id,
                    self.combo_partner.currentData(),
                    items,
                    self.get_current_user_id()
                )
        finally:
            self.is_persisting_transfer = False

        if not success:
            QMessageBox.critical(self, "Erreur", f"Echec de l'enregistrement : {result}")
            return False

        self.last_persist_signature = signature
        self.update_current_transfer_scope_from_items(items)
        self.refresh_batches_cache(include_zero=bool(self.current_id))
        return True

    def add_batch_to_invoice(self, batch, initial_qty=1):
        if self.is_return_mode() and not self.is_return_batch_allowed(batch):
            QMessageBox.warning(self, "Attention", "Ce lot n'appartient pas au sous-traitant selectionne ou n'est plus disponible au retour.")
            return False

        if not self.is_loading_transfer and not self.save_header_only(show_message=False):
            return False
        """إضافة المنتج للجدول مع تصحيح أخطاء sb_qty وربط الحسابات"""
        # منع التكرار وزيادة الكمية فقط
        for r in range(self.table.rowCount()):
            cb = self.table.cellWidget(r, 1)
            if cb and cb.currentData() and cb.currentData().get('Batch_ID') == batch['Batch_ID']:
                sb = self.table.cellWidget(r, 2)
                if sb and sb.value() < sb.maximum():
                    sb.setValue(sb.value() + 1)
                    self.persist_current_transfer()
                    return True
                return False

        # استخراج حالة الفوترة والبيانات
        is_billable = batch.get('Is_Billable', False)
        status_tag = " [PAYANT]" if is_billable else " [GRATUIT]"
        row = self.table.rowCount()
        self.table.insertRow(row)

        barcode_display = batch.get('Barcode') or batch.get('Internal_Barcode', 'N/A')
        p_name = f"{batch['Product_Name']} (Code: {barcode_display}){status_tag}"
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
        if getattr(self, 'transfer_type_mode', 'Outbound') == 'Return':
            current_stock = quantity_to_int(batch.get('Available_To_Return', 0))
            max_allowed = current_stock
        else:
            current_stock = quantity_to_int(batch.get('Quantity_Current', 0))
            previous_qty = quantity_to_int(self.current_transfer_qty_by_batch.get(batch['Batch_ID'], 0))
            max_allowed = current_stock + previous_qty
        if max_allowed <= 0:
            QMessageBox.warning(self, "Stock insuffisant", "Ce lot n'est pas disponible pour cette transaction.")
            return False
        if initial_qty > max_allowed:
            initial_qty = max_allowed

        sb_qty = QSpinBox()
        sb_qty.setRange(1, max_allowed); sb_qty.setValue(initial_qty); sb_qty.setAlignment(Qt.AlignCenter)

        unit_price = float(batch.get('Unit_Price_Received', 0)) if is_billable else 0.0
        sb_price = QDoubleSpinBox()
        sb_price.setRange(0, 1000000); sb_price.setValue(unit_price); sb_price.setGroupSeparatorShown(True)
        if not is_billable:
            sb_price.setSpecialValueText("/")
            sb_price.setEnabled(False)

        txt_obs = QLineEdit()
        txt_obs.setPlaceholderText("Note...")

        lbl_line = QLabel("0.00")
        lbl_line.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_line.setStyleSheet("font-weight: bold; color: #2980b9; padding-right: 5px;")

        btn_del = QPushButton("✕")
        btn_del.setStyleSheet("color: #e74c3c; font-weight: bold; border: none;")
        btn_del.clicked.connect(lambda: self.remove_row_at_btn(btn_del))

        # --- Source Combo ---
        cb_source = QComboBox()
        cb_source.setStyleSheet("font-weight: bold; color: #2c3e50;")
        # Find all batches for this product
        available_batches = [b for b in self.batches_cache if b['Product_ID'] == batch['Product_ID']]
        if not available_batches:
            available_batches = [batch] # Fallback
            
        current_index = 0
        for i, b in enumerate(available_batches):
            loc_name = b.get('Location_Name') or 'Inconnu'
            lot_name = b.get('Lot_Number') or '-'
            if getattr(self, 'transfer_type_mode', 'Outbound') == 'Return':
                b_qty = quantity_to_int(b.get('Available_To_Return', 0))
            else:
                b_qty = quantity_to_int(b.get('Quantity_Current', 0))
            item_text = f"📍 {loc_name} | Lot: {lot_name} (Dispo: {format_quantity(b_qty)})"
            cb_source.addItem(item_text, b)
            if b['Batch_ID'] == batch['Batch_ID']:
                current_index = i
        cb_source.setCurrentIndex(current_index)
        
        def update_max_qty():
            selected_b = cb_source.currentData()
            if not selected_b: return
            if getattr(self, 'transfer_type_mode', 'Outbound') == 'Return':
                curr_stock = quantity_to_int(selected_b.get('Available_To_Return', 0))
                max_allow = curr_stock
            else:
                curr_stock = quantity_to_int(selected_b.get('Quantity_Current', 0))
                prev_qty = quantity_to_int(self.current_transfer_qty_by_batch.get(selected_b['Batch_ID'], 0))
                max_allow = curr_stock + prev_qty
            sb_qty.setRange(1, max(1, max_allow))
            self.persist_current_transfer()
            
        cb_source.currentIndexChanged.connect(update_max_qty)

        # وضع الـ Widgets في الجدول
        self.table.setCellWidget(row, 1, cb_source)
        self.table.setCellWidget(row, 2, sb_qty)
        self.table.setCellWidget(row, 3, sb_price)
        self.table.setCellWidget(row, 4, txt_obs)
        self.table.setCellWidget(row, 5, lbl_line)
        self.table.setCellWidget(row, 6, btn_del)

        # ربط الإشارات بالحسابات بعد بناء الصف
        sb_qty.valueChanged.connect(self.on_line_changed)
        sb_price.valueChanged.connect(self.on_line_changed)
        txt_obs.editingFinished.connect(self.persist_current_transfer)

        self.calc_totals()
        if not self.persist_current_transfer():
            self.table.removeRow(row)
            self.calc_totals()
            return False
        return True

    def remove_row_at_btn(self, btn):
        removed = False
        for r in range(self.table.rowCount()):
            if self.table.cellWidget(r, 6) == btn:
                self.table.removeRow(r)
                removed = True
                break
        self.calc_totals()
        if removed:
            self.persist_current_transfer()

    def format_id(self, raw_id):
        try:
            if hasattr(self.manager, 'external_transfers') and raw_id:
                transfer = self.manager.external_transfers.get_transfer_by_id(int(raw_id))
                if transfer and transfer.get('Display_Ref'):
                    return transfer['Display_Ref']
        except Exception as e:
            logging.error(f"Error formatting transfer id {raw_id}: {e}")

        year = self.inp_date.date().toString("yyyy")
        return f"{year}/{int(raw_id):03d}"

    def calc_totals(self):
        """حساب المجاميع مع حماية ضد NoneType"""
        grand = 0.0
        for r in range(self.table.rowCount()):
            table_item = self.table.item(r, 0)
            meta = table_item.data(Qt.UserRole) if table_item else {}
            is_billable = bool(meta.get('is_billable', True)) if isinstance(meta, dict) else True

            qty_widget = self.table.cellWidget(r, 2)
            price_widget = self.table.cellWidget(r, 3)
            total_label = self.table.cellWidget(r, 5)

            if qty_widget and price_widget and total_label:
                if is_billable:
                    line = qty_widget.value() * price_widget.value()
                    total_label.setText(format_money(line))
                    total_label.setStyleSheet("font-weight: bold; color: #2980b9; padding-right: 5px;")
                    grand += line
                else:
                    total_label.setText("Gratuit")
                    total_label.setStyleSheet("font-weight: bold; color: #e74c3c; padding-right: 5px;")

        self.lbl_total.setText(format_money(grand, 'DA'))

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
        if not self.save_header_only(show_message=False):
            return

        if self.table.rowCount() == 0:
            QMessageBox.warning(
                self,
                "Facture Vide",
                "Veuillez ajouter au moins un article à la liste."
            )
            return

        # 3. تجميع البيانات من الواجهة
        if self.persist_current_transfer():
            QMessageBox.information(
                self,
                "Succes",
                "La transaction a ete enregistree et le stock mis a jour avec succes."
            )
            self.request_back.emit()
        return

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
