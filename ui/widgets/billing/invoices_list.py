import os
import logging
from datetime import datetime
from xml.sax.saxutils import escape as escape_xml
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QHeaderView, QPushButton, QLabel, QLineEdit,
    QComboBox, QDateEdit, QGroupBox, QTableWidgetItem,
    QAbstractItemView, QMessageBox, QFileDialog, QMenu,
    QFrame
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QFont, QColor
import qtawesome as qta
import json
from branding import get_banner_path
from ui.formatting import format_quantity, format_money

# ReportLab Imports
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

from ui.widgets.settings.pdf.pdf_stamp import (
    FOOTER_TITLE_HEIGHT_CM,
    fit_stamp_size_cm,
    get_active_stamp,
    SignatureFooter,
    draw_stamp_image,
)
from ui.widgets.settings.local_settings import get_local_settings_store

class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        if other is None:
            return False
        v1 = self.data(Qt.UserRole)
        v2 = other.data(Qt.UserRole)
        if v1 is not None and v2 is not None:
            try:
                return float(v1) < float(v2)
            except (ValueError, TypeError):
                pass
        return super().__lt__(other)

class InvoicesListWidget(QWidget):
    """
    Interface for the list of invoices/delivery notes.
    Supports filtering, professional PDF export, and stock-safe deletion.
    """
    request_new = Signal(object)
    request_new_return = Signal(object)
    request_edit = Signal(int)
    request_pdf = Signal(int)
    request_delete = Signal(int)
    
    request_view_partner = Signal(int)
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # --- 1. Filter Bar ---
        filter_group = QFrame()
        filter_group.setStyleSheet("QFrame { background-color: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 6px; }")
        filter_layout = QHBoxLayout(filter_group)
        filter_layout.setContentsMargins(10, 5, 10, 5)

        self.date_from = QDateEdit(QDate.currentDate().addDays(-30))
        self.date_from.setCalendarPopup(True)
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)

        self.combo_filter_partner = QComboBox()
        self.load_partners()

        btn_filter = QPushButton(" Appliquer")
        btn_filter.setIcon(qta.icon("fa5s.filter", color="white"))
        btn_filter.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; padding: 5px 15px;")
        btn_filter.clicked.connect(self.load_data)

        filter_layout.addWidget(QLabel("Du :"))
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(QLabel("Au :"))
        filter_layout.addWidget(self.date_to)
        filter_layout.addWidget(QLabel("Client :"))
        filter_layout.addWidget(self.combo_filter_partner, stretch=1)
        filter_layout.addWidget(btn_filter)
        layout.addWidget(filter_group)

        # --- 2. Action Bar ---
        actions_bar = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher par ID ou par Client...")
        self.search_input.setMinimumHeight(35)
        self.search_input.textChanged.connect(self.filter_table)

        self.btn_new = QPushButton(" Nouveau BL")
        self.btn_new.setIcon(qta.icon("fa5s.file-export", color="white"))
        self.btn_new.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; border-radius: 4px; padding: 8px 15px;")
        self.btn_new.clicked.connect(self.on_new_clicked)

        self.btn_new_return = QPushButton(" Nouveau Retour")
        self.btn_new_return.setIcon(qta.icon("fa5s.file-import", color="white"))
        self.btn_new_return.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; border-radius: 4px; padding: 8px 15px;")
        self.btn_new_return.clicked.connect(self.on_new_return_clicked)

        self.btn_edit = QPushButton(" Modifier")
        self.btn_edit.setIcon(qta.icon("fa5s.edit", color="white"))
        self.btn_edit.setEnabled(False)
        self.btn_edit.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; border-radius: 4px; padding: 8px 15px;")
        self.btn_edit.clicked.connect(self.on_edit_clicked)

        self.btn_pdf = QPushButton(" Imprimer PDF")
        self.btn_pdf.setIcon(qta.icon("fa5s.file-pdf", color="white"))
        self.btn_pdf.setEnabled(False)
        self.btn_pdf.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; border-radius: 4px; padding: 8px 15px;")
        self.btn_pdf.clicked.connect(self.on_pdf_clicked)

        self.btn_delete = QPushButton(" Supprimer")
        self.btn_delete.setIcon(qta.icon("fa5s.trash-alt", color="white"))
        self.btn_delete.setEnabled(False)
        self.btn_delete.setStyleSheet("background-color: #d35400; color: white; font-weight: bold; border-radius: 4px; padding: 8px 15px;")
        self.btn_delete.clicked.connect(self.on_delete_clicked)

        actions_bar.addWidget(self.search_input, stretch=1)
        actions_bar.addWidget(self.btn_new)
        actions_bar.addWidget(self.btn_new_return)
        actions_bar.addWidget(self.btn_edit)
        actions_bar.addWidget(self.btn_pdf)
        actions_bar.addWidget(self.btn_delete)
        layout.addLayout(actions_bar)

        # --- 3. Table ---
        self.table = QTableWidget(0, 5)
        columns = ["ID Trans.", "Type", "Date & Heure", "Client / Sous-Traitant", "Montant (DA)"]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        header.setSectionsClickable(True)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.cellDoubleClicked.connect(lambda r, c: self.on_edit_clicked())

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        layout.addWidget(self.table)
        filter_group.raise_()

    def on_new_clicked(self):
        partner_id = self.combo_filter_partner.currentData()
        self.request_new.emit(partner_id)

    def on_new_return_clicked(self):
        partner_id = self.get_selected_partner_id() or self.combo_filter_partner.currentData()
        if not partner_id:
            QMessageBox.warning(self, "Attention", "Selectionnez un BL ou filtrez par partenaire avant de creer un bon de retour.")
            return
        self.request_new_return.emit({'partner_id': partner_id, 'ref_transfer_id': None})

    def format_id(self, raw_id, date_str):
        """تحويل ID الرقمي إلى تنسيق YYYY/NNN"""
        try:
            # استخراج السنة من تاريخ المعاملة (YYYY-MM-DD ...)
            year = date_str.split('-')[0] if date_str else str(datetime.now().year)
            return f"{year}/{int(raw_id):03d}"
        except:
            return str(raw_id)

    # =========================================================================
    # Logic & Handlers
    # =========================================================================

    def on_selection_changed(self):
        has_selection = len(self.table.selectedItems()) > 0
        self.btn_edit.setEnabled(has_selection)
        self.btn_pdf.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)

    def get_selected_id(self):
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                # نأخذ الـ ID الأصلي المخزن في UserRole
                return item.data(Qt.UserRole)
        return None



    def show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item: return
        row = item.row()
        
        # جلب البيانات المخزنة في السطر الحالي
        tid = self.table.item(row, 0).data(Qt.UserRole)
        partner_id = self.table.item(row, 0).data(Qt.UserRole + 1)
        transfer_type_text = self.table.item(row, 1).text()
        ref_transfer_id = self.table.item(row, 0).data(Qt.UserRole + 2)

        menu = QMenu(self)
        
        # 1. إذا كان السطر المحدد عبارة عن وصل تسليم BL
        if transfer_type_text == "BL (Sortie)":
            action_return = menu.addAction("Créer un Bon de Retour pour ce BL")
            action_return.setIcon(qta.icon("fa5s.file-import", color="#8e44ad"))
            action_return.triggered.connect(lambda: self.request_new_return.emit({'partner_id': partner_id, 'ref_transfer_id': tid}))
            
            menu.addSeparator() # خط فاصل للتنظيم
            
            action_partner = menu.addAction("Consulter le Sous-traitant (Profil)")
            action_partner.setIcon(qta.icon("fa5s.user-tie", color="#2980b9"))
            action_partner.triggered.connect(lambda: self.request_view_partner.emit(partner_id))

        # 2. إذا كان السطر المحدد عبارة عن وصل إرجاع (Retour)
        elif transfer_type_text == "Retour":
            # خيار الانتقال إلى الـ BL الأصلي (يظهر فقط إذا كان مربوطاً بـ BL)
            if ref_transfer_id:
                action_orig = menu.addAction("Consulter le BL d'origine")
                action_orig.setIcon(qta.icon("fa5s.file-invoice", color="#27ae60"))
                action_orig.triggered.connect(lambda: self.request_edit.emit(ref_transfer_id))
            
            # خيار الانتقال مباشرة إلى ملف المقاول / الشريك (يظهر دائماً)
            action_partner = menu.addAction("Consulter le Sous-traitant (Profil)")
            action_partner.setIcon(qta.icon("fa5s.user-tie", color="#2980b9"))
            action_partner.triggered.connect(lambda: self.request_view_partner.emit(partner_id))
        
        # إظهار القائمة في موقع مؤشر الفأرة
        if not menu.isEmpty():
            menu.exec(self.table.viewport().mapToGlobal(pos))
    def get_selected_partner_id(self):
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                return item.data(Qt.UserRole + 1)
        return None

    def on_edit_clicked(self):
        tid = self.get_selected_id()
        if tid: self.request_edit.emit(tid)

    def on_pdf_clicked(self):
        tid = self.get_selected_id()
        if tid:
            # سنقوم بإرسال الإشارة للأب (BillingTab) كما يتوقع
            self.request_pdf.emit(tid)
            # وأيضاً يمكنك تشغيل الدالة الداخلية التي أضفناها سابقاً إذا أردت
            self.export_transfer_to_pdf(tid)

    def on_delete_clicked(self):
        tid = self.get_selected_id()
        if not tid: return

        reply = QMessageBox.question(
            self, "Confirmation",
            f"Voulez-vous vraiment supprimer la transaction N° {tid} ?\n"
            "Cette action restaurera les quantités dans le stock.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # استدعاء دالة الحذف واسترجاع المخزون من المدير
                success, msg = self.manager.external_transfers.delete_transfer_and_restore_stock(tid)
                if success:
                    QMessageBox.information(self, "Succès", msg)
                    self.load_data()
                else:
                    QMessageBox.warning(self, "Erreur", msg)
            except Exception as e:
                logging.error(f"Error deleting transfer: {e}")
                QMessageBox.critical(self, "Erreur", str(e))

    def load_partners(self):
        self.combo_filter_partner.clear()
        self.combo_filter_partner.addItem("Tous les partenaires", None)
        if hasattr(self.manager, 'partners'):
            for p in self.manager.partners.get_all_partners():
                self.combo_filter_partner.addItem(p['Partner_Name'], p['Partner_ID'])

    def load_data(self):
        start = self.date_from.date().toString("yyyy-MM-dd")
        end = self.date_to.date().toString("yyyy-MM-dd") + " 23:59:59"
        p_id = self.combo_filter_partner.currentData()

        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        if hasattr(self.manager, 'external_transfers'):
            transfers = self.manager.external_transfers.get_transfers_filtered(start, end, p_id, None)
            for row, t in enumerate(transfers):
                self.table.insertRow(row)

                formatted_ref = t.get('Display_Ref') or self.format_id(t['Transfer_ID'], str(t.get('Transaction_Date', '')))
                id_item = QTableWidgetItem(formatted_ref)
                id_item.setTextAlignment(Qt.AlignCenter)
                id_item.setData(Qt.UserRole, t['Transfer_ID']) # حفظ الـ ID الحقيقي في الـ Data للعمليات البرمجية
                id_item.setData(Qt.UserRole + 1, t.get('Partner_ID'))
                id_item.setData(Qt.UserRole + 2, t.get('Ref_Transfer_ID'))

                raw_date = t.get('Transaction_Date')
                if hasattr(raw_date, 'strftime'):
                    date_text = raw_date.strftime("%Y-%m-%d %H:%M")
                elif isinstance(raw_date, str) and raw_date:
                    date_text = raw_date[:16]
                else:
                    date_text = str(raw_date or "")

                date_item = QTableWidgetItem(date_text)
                date_item.setTextAlignment(Qt.AlignCenter)

                partner_text = t.get('Partner_Name') or t.get('City') or "-"
                partner_item = QTableWidgetItem(str(partner_text))

                amount = float(t.get('Total_Amount') or 0)
                amount_item = NumericTableWidgetItem(format_money(amount, 'DA'))
                amount_item.setData(Qt.UserRole, amount)
                amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                font_bold = QFont()
                font_bold.setBold(True)
                amount_item.setFont(font_bold)

                t_type = t.get('Transfer_Type', 'Outbound') or 'Outbound'
                type_str = "Retour" if t_type == 'Return' else "BL (Sortie)"
                type_item = QTableWidgetItem(type_str)
                type_item.setTextAlignment(Qt.AlignCenter)
                type_item.setFont(font_bold)
                if t_type == 'Return':
                    type_item.setForeground(QColor("#8e44ad"))
                else:
                    type_item.setForeground(QColor("#27ae60"))

                self.table.setItem(row, 0, id_item)
                self.table.setItem(row, 1, type_item)
                self.table.setItem(row, 2, date_item)
                self.table.setItem(row, 3, partner_item)
                self.table.setItem(row, 4, amount_item)

        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.on_selection_changed()
        self.filter_table(self.search_input.text())

    def filter_table(self, text):
        for r in range(self.table.rowCount()):
            match = any(text.lower() in (self.table.item(r, col).text().lower() if self.table.item(r, col) else "") for col in [0, 2, 3])
            self.table.setRowHidden(r, not match)

    @staticmethod
    def _pdf_setting_enabled(settings, key, default=True):
        value = settings.get(key, default)
        if isinstance(value, str):
            return value.strip().lower() not in {"0", "false", "no", "non", "off", ""}
        return bool(value)

    @staticmethod
    def _partner_value(partner_info, *field_names):
        # Read Master Data fields while tolerating DB-driver key casing.
        if not isinstance(partner_info, dict):
            return ""
        values_by_lower_name = {str(key).lower(): value for key, value in partner_info.items()}
        for field_name in field_names:
            value = values_by_lower_name.get(str(field_name).lower())
            if value not in (None, ""):
                return value
        return ""

    @classmethod
    def _partner_pdf_lines(cls, partner_info, settings):
        value = cls._partner_value
        lines = []

        def text(raw):
            if raw is None:
                return ""
            result = str(raw).replace("\n", " ").replace("\r", " ").strip()
            return "" if result.lower() in {"none", "null", "n/a", "-", "."} else result

        def add(label, raw):
            cleaned = text(raw)
            if cleaned:
                lines.append((label, cleaned))

        def show(field_key, legacy_group_key=None):
            legacy_default = cls._pdf_setting_enabled(settings, legacy_group_key, True) if legacy_group_key else True
            return cls._pdf_setting_enabled(settings, field_key, legacy_default)

        if show("partner_show_contact_person", "partner_show_contact"):
            add("Contact :", value(partner_info, "Contact_Person", "Contact", "Correspondant"))
        if show("partner_show_phone", "partner_show_contact"):
            add("Tél. :", value(partner_info, "Phone", "Telephone", "Mobile"))
        if show("partner_show_email", "partner_show_contact"):
            add("Email :", value(partner_info, "Email", "E_mail"))
        if show("partner_show_website", "partner_show_contact"):
            add("Site web :", value(partner_info, "Website", "WebSite"))

        if show("partner_show_address_line1", "partner_show_address"):
            add("Adresse :", value(partner_info, "Address_Line1", "Address"))
        if show("partner_show_address_line2", "partner_show_address"):
            add("Adresse (complément) :", value(partner_info, "Address_Line2"))
        if show("partner_show_postal_code", "partner_show_address"):
            add("Code postal :", value(partner_info, "Postal_Code", "Zip_Code"))
        if show("partner_show_city", "partner_show_address"):
            add("Ville :", value(partner_info, "City"))

        if show("partner_show_type", "partner_show_identity"):
            add("Type :", value(partner_info, "Partner_Type"))
        if show("partner_show_agrement", "partner_show_identity"):
            add("Agrément :", value(partner_info, "Agrement_Number", "Agreement_Number"))
        if show("partner_show_tax_id", "partner_show_identity"):
            add("NIF :", value(partner_info, "Tax_ID_Number", "Tax_ID", "NIF"))
        if show("partner_show_commercial_reg", "partner_show_identity"):
            add("Reg. Commerce :", value(partner_info, "Commercial_Reg_No", "RC"))

        if show("partner_show_bank_name", "partner_show_bank"):
            add("Banque :", value(partner_info, "Bank_Name"))
        if show("partner_show_iban", "partner_show_bank"):
            add("RIB :", value(partner_info, "Bank_Account_IBAN", "IBAN"))

        return lines

    # =========================================================================
    # PDF Export Logic - PROFESSIONNAL & DYNAMIC (BL / BON DE RETOUR)
    # =========================================================================
    def export_transfer_to_pdf(self, transfer_id):
        """
        توليد ملف PDF احترافي يدعم كلاً من (Bon de Livraison) و (Bon de Retour)
        مع تنسيق وتصميم مخصص لكل حالة.
        """
        print("\n" + "🚀" * 10 + " PDF EXPORT START " + "🚀" * 10)

        if not HAS_REPORTLAB:
            QMessageBox.warning(self, "Erreur", "La bibliothèque 'reportlab' est manquante.")
            return

        # 1. تحديد المسارات وتحميل الإعدادات
        try:
            local_store = get_local_settings_store(self.manager)
            settings = local_store.load_merged_pdf_settings()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Configuration error: {str(e)}")
            return

        # 2. جلب البيانات من قاعدة البيانات
        try:
            mgr = self.manager.external_transfers
            header_data = mgr.get_transfer_by_id(transfer_id)
            if not header_data:
                transfers = mgr.get_all_transfers()
                header_data = next((t for t in transfers if t['Transfer_ID'] == transfer_id), None)

            if not header_data:
                QMessageBox.warning(self, "Erreur", "Données introuvables.")
                return

            details_data = mgr.get_transfer_details(transfer_id)
            partner_info = self.manager.partners.get_partner_by_id(header_data['Partner_ID']) or {}
        except Exception as e:
            QMessageBox.critical(self, "Erreur BD", str(e))
            return

        # --- التمييز بين الإرجاع والبيع ---
        transfer_type = header_data.get('Transfer_Type', 'Outbound')
        is_return = (transfer_type == 'Return')
        document_title = settings.get('doc_title_rt', 'Retourné à Sous-Traitant') if is_return else settings.get('doc_title_bl', 'BON DE LIVRAISON')
        
        # استخراج المرجع المنسق
        raw_date = str(header_data.get('Transaction_Date', ''))
        try:
            year_val = raw_date.split('-')[0] if '-' in raw_date else str(datetime.now().year)
            formatted_ref = header_data.get('Display_Ref') or f"{year_val}/{int(transfer_id):03d}"
        except:
            formatted_ref = str(transfer_id)

        ref_bl_text = ""
        ref_id = header_data.get('Ref_Transfer_ID')
        if is_return and ref_id:
            ref_transfer = mgr.get_transfer_by_id(ref_id)
            if ref_transfer:
                ref_bl_display = ref_transfer.get('Display_Ref') or f"{year_val}/{int(ref_id):03d}"
                ref_bl_text = f"<br/><font color='#e67e22'><b>Réf. BL d'origine : {ref_bl_display}</b></font>"

        # 3. حوار حفظ الملف
        partner_clean = str(header_data.get('Partner_Name', 'Client')).replace(" ", "_")
        safe_ref_for_filename = formatted_ref.replace("/", "-")
        prefix_name = "BR" if is_return else "BL"
        default_name = f"{prefix_name}_{partner_clean}_{safe_ref_for_filename}.pdf"

        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer PDF", default_name, "PDF Files (*.pdf)")
        if not path: return

        # 4. بناء المستند (ReportLab)
        try:
            PAGE_WIDTH, PAGE_HEIGHT = A4
            # تغيير لون الثيم بناءً على النوع (استخدام الثيم المحدد للجميع)
            default_color = settings.get('theme_color', '#0b666a')
            primary_color = colors.HexColor(default_color)
            banner_h_cm = settings.get('banner_height_cm', 4.8)

            elements = []
            styles = getSampleStyleSheet()

            current_time = datetime.now().strftime('%d/%m/%Y %H:%M')

            # --- الترويسة العلوية (المعلومات) ---
            lab_addr = settings.get('lab_address', '')
            lab_nif = settings.get('lab_nif', '')
            lab_rc = settings.get('lab_rc', '')

            lab_info_lines = [
                f"<font size=14 color='{default_color}'><b>{escape_xml(str(document_title))} N°: {escape_xml(str(formatted_ref))}</b></font>{ref_bl_text}<br/>"
            ]
            def clean_str(val):
                if not val: return ""
                v = str(val).replace('\n', '').replace('\r', '').strip()
                if v.lower() in ["none", "n/a", "null", "nan", "-", "", "."]:
                    return ""
                return v

            def safe_markup(val):
                return escape_xml(clean_str(val))

            if clean_str(lab_addr): lab_info_lines.append(f"<font size=9>{safe_markup(lab_addr)}</font>")
            if clean_str(lab_nif): lab_info_lines.append(f"<font size=9>NIF : {safe_markup(lab_nif)}</font>")
            if clean_str(lab_rc): lab_info_lines.append(f"<font size=9>RC : {safe_markup(lab_rc)}</font>")
            
            bank_name = settings.get('bank_name', '')
            bank_acc = settings.get('bank_acc', '')
            
            if clean_str(bank_name): lab_info_lines.append(f"<font size=9>Banque : {safe_markup(bank_name)}</font>")
            if clean_str(bank_acc): lab_info_lines.append(f"<font size=9>RIB : {safe_markup(bank_acc)}</font>")

            raw_date = header_data.get('Transaction_Date')
            if hasattr(raw_date, 'strftime'):
                bon_date = raw_date.strftime("%d/%m/%Y %H:%M")
            else:
                bon_date = str(raw_date or "")
                
            creation_date_text = f"Date de création : {current_time}"
            if bon_date:
                creation_date_text = f"Date du Bon : {bon_date}    |    {creation_date_text}"

            left_text_top = "<br/>".join(lab_info_lines)

            p_name = self._partner_value(partner_info, 'Partner_Name', 'Name') or 'Inconnu'
            label_key = 'dest_label_rt' if is_return else 'dest_label_bl'
            dest_label = clean_str(settings.get(label_key, ''))
            if dest_label.lower() in {'destinataire :', 'destinataire:', 'retourné à (sous-traitant) :'}:
                dest_label = 'Correspondant :'
            if not dest_label:
                dest_label = 'Correspondant :'

            right_text_lines = [
                f"<b>{safe_markup(dest_label)}</b>",
                "",
            ]
            if self._pdf_setting_enabled(settings, "partner_show_name", True):
                right_text_lines.append(f"<font size=11><b>{safe_markup(p_name)}</b></font>")
            for label, value in self._partner_pdf_lines(partner_info, settings):
                right_text_lines.append(f"{safe_markup(label)} {safe_markup(value)}")

            right_text = "<br/>".join(right_text_lines)

            header_info_x_cm = float(settings.get('header_info_x_cm', 1.0))
            header_info_y_cm = float(settings.get('header_info_y_cm', 5.4))
            header_info_w_cm = float(settings.get('header_info_w_cm', 9.5))
            creation_date_x_cm = float(settings.get('creation_date_x_cm', 1.0))
            creation_date_y_cm = float(settings.get('creation_date_y_cm', 9.3))
            date_p = Paragraph(f"<font size=9>{safe_markup(creation_date_text)}</font>", styles["Normal"])
            date_w, date_h = date_p.wrap(10.0 * cm, 1.0 * cm)

            left_p = Paragraph(left_text_top, styles["Normal"])
            left_w, left_h = left_p.wrap(header_info_w_cm * cm, 6.0 * cm)
            right_p = Paragraph(right_text, styles["Normal"])
            dest_w_cm = float(settings.get('dest_box_w_cm', 8.0))
            right_w, right_h = right_p.wrap(max(1.0, dest_w_cm - 0.5) * cm, 10.0 * cm)
            configured_dest_h_cm = float(settings.get('dest_box_h_cm', 6.5))
            dest_box_h = max(right_h + 1.0 * cm, configured_dest_h_cm * cm, 2.5 * cm)

            requested_table_y_cm = float(settings.get('table_start_y_cm', 10.5))
            safe_table_y_cm = max(
                requested_table_y_cm,
                header_info_y_cm + left_h / cm + 0.35,
                creation_date_y_cm + date_h / cm + 0.35,
                float(settings.get('dest_box_y_cm', 5.4)) + dest_box_h / cm + 0.35,
            )
            table_start_x_cm = float(settings.get('table_start_x_cm', 1.0))

            doc = SimpleDocTemplate(
                path, pagesize=A4, rightMargin=1.0 * cm, leftMargin=1.0 * cm,
                topMargin=safe_table_y_cm * cm, bottomMargin=50
            )

            def draw_header_compact(canvas, doc):
                canvas.saveState()
                img_x = settings.get('banner_img_x_cm', 0.0) * cm
                img_w = settings.get('banner_img_w_cm', 21.0) * cm
                img_h = settings.get('banner_img_h_cm', 4.8) * cm
                y_offset = settings.get('banner_img_y_cm', 0.2) * cm
                img_y = PAGE_HEIGHT - img_h - y_offset

                img_bytes = local_store.load_banner_bytes(settings)
                if img_bytes:
                    from reportlab.lib.utils import ImageReader
                    import io
                    img = ImageReader(io.BytesIO(img_bytes))
                    canvas.drawImage(img, img_x, img_y, width=img_w, height=img_h)
                else:
                    canvas.setStrokeColor(colors.red)
                    canvas.rect(img_x, img_y, img_w, img_h, stroke=1)
                    
                left_p.drawOn(
                    canvas,
                    header_info_x_cm * cm,
                    PAGE_HEIGHT - header_info_y_cm * cm - left_h,
                )

                dest_x = settings.get('dest_box_x_cm', 11.5) * cm
                dest_y_abs = PAGE_HEIGHT - settings.get('dest_box_y_cm', 5.4) * cm
                dest_w = dest_w_cm * cm
                box_h = dest_box_h

                canvas.setFillColor(colors.HexColor("#f8f9fa"))
                canvas.setStrokeColor(colors.lightgrey)
                canvas.setLineWidth(0.5)
                canvas.rect(dest_x, dest_y_abs - box_h, dest_w, box_h, fill=1, stroke=1)
                
                right_p.drawOn(canvas, dest_x + 0.25*cm, dest_y_abs - right_h - 0.5*cm)
                date_p.drawOn(
                    canvas,
                    creation_date_x_cm * cm,
                    PAGE_HEIGHT - creation_date_y_cm * cm - date_h,
                )
                canvas.restoreState()

            # --- جدول المنتجات ---
            header_col1 = settings.get('col1_name', 'Désignation Produit')
            header_col2 = settings.get('qty_header_rt', 'Qté Rtr.') if is_return else settings.get('qty_header_bl', 'Qté')
            header_col3 = settings.get('col3_name', 'P.U')
            header_col4 = settings.get('col4_name', 'Total / Obs')
            table_data = [[header_col1, header_col2, header_col3, header_col4]]
            
            grand_total = 0.0
            for item in details_data:
                is_billable = bool(item.get('Is_Billable', False))
                qty = item.get('Qty_Transferred', 0)
                qty_numeric = float(qty or 0)
                price = float(item.get('Unit_Price', 0))
                line_val = (qty_numeric * price) if is_billable else 0.0
                grand_total += line_val

                pu_text = format_money(price) if is_billable else "/"
                obs_text = format_money(line_val) if is_billable else "<font color='red'>Gratuit</font>"
                lot_info = item.get('Lot_Number', '-')
                exp_info = str(item.get('Expiry_Date', '-'))[:10]
                p_info = f"<b>{item.get('Product_Name', '-')}</b><br/><font size=8 color='#555555'>Lot: {lot_info} | Exp: {exp_info}</font>"

                table_data.append([
                    Paragraph(p_info, styles["Normal"]), 
                    format_quantity(qty), 
                    pu_text, 
                    Paragraph(obs_text, styles["Normal"])
                ])

            total_label = settings.get('total_label_rt', 'VALEUR TOTALE DU RETOUR') if is_return else settings.get('total_label_bl', 'MONTANT TOTAL À PAYER')
            table_data.append([Paragraph(f"<b>{total_label}</b>", styles["Normal"]), "", "", format_money(grand_total, 'DA')])

            items_table = Table(table_data, colWidths=[9.5*cm, 2.0*cm, 2.5*cm, 4.0*cm])
            items_table.hAlign = 'LEFT'
            items_table.leftIndent = max(0.0, table_start_x_cm * cm - doc.leftMargin)
            items_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), primary_color),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
                ('ALIGN', (1,0), (2,-1), 'CENTER'),
                ('ALIGN', (3,0), (3,-1), 'RIGHT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('SPAN', (0, -1), (2, -1)), # دمج خلايا المجموع
                ('PADDING', (0,0), (-1,-1), 6),
                ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#f4f6f6")), # لون خلفية للمجموع
            ]))
            elements.append(items_table)
            footer_y_offset = settings.get('footer_y_offset_cm', 1.5)
            elements.append(Spacer(1, footer_y_offset * cm))

            # --- التوقيعات ---
            if is_return:
                f_left = settings.get('footer_left_rt', 'Signature Magasin / Expéditeur')
                f_right = settings.get('footer_right_rt', 'Accusé de Réception (Fournisseur)')
            else:
                f_left = settings.get('footer_left_bl', 'Responsable Stock')
                f_right = settings.get('footer_right_bl', 'Accusé de réception (Client)')

            footer_height = settings.get('footer_height_cm', 2.5)
            left_x = settings.get('footer_left_x_cm', 1.0)
            right_x = settings.get('footer_right_x_cm', 12.0)
            stamp_gap = float(settings.get('footer_stamp_gap_cm', 0.3))
            stamp_area_w = float(settings.get('footer_stamp_area_w_cm', 6.0))
            stamp_area_h = float(settings.get('footer_stamp_area_h_cm', 3.5))
            footer_height = max(
                float(footer_height),
                FOOTER_TITLE_HEIGHT_CM + stamp_gap + stamp_area_h,
            )
            stamp_provider = getattr(self.manager, "company_settings", None) or local_store
            active_stamp = get_active_stamp(stamp_provider)
            
            footer = SignatureFooter(
                f_left,
                f_right,
                left_x,
                right_x,
                footer_height,
                active_stamp,
                stamp_gap,
                stamp_area_w,
                stamp_area_h,
            )
            elements.append(footer)

            doc.build(elements, onFirstPage=draw_header_compact, onLaterPages=draw_header_compact)

            # فتح الملف تلقائياً
            if os.name == 'nt': os.startfile(path)
            else: os.system(f'xdg-open "{path}"')

        except Exception as e:
            QMessageBox.critical(self, "Erreur PDF", f"Échec de création du PDF: {str(e)}")

        print("="*50 + " PDF EXPORT END " + "="*50)
