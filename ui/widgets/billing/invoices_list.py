import os
import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
    QHeaderView, QPushButton, QLabel, QLineEdit, 
    QComboBox, QDateEdit, QGroupBox, QTableWidgetItem, 
    QAbstractItemView, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, QDate, Signal
import qtawesome as qta
import json
from branding import get_banner_path
from ui.formatting import format_quantity

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

class InvoicesListWidget(QWidget):
    """
    Interface for the list of invoices/delivery notes.
    Supports filtering, professional PDF export, and stock-safe deletion.
    """
    request_new = Signal()
    request_edit = Signal(int)
    request_pdf = Signal(int)   
    request_delete = Signal(int)

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # --- 1. Filter Bar ---
        filter_group = QGroupBox("Filtres & Recherche")
        filter_layout = QHBoxLayout(filter_group)
        
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
        
        self.btn_new = QPushButton(" Nouveau")
        self.btn_new.setIcon(qta.icon("fa5s.plus", color="white"))
        self.btn_new.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; border-radius: 4px; padding: 8px 15px;")
        self.btn_new.clicked.connect(self.request_new.emit)

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
        actions_bar.addWidget(self.btn_edit)
        actions_bar.addWidget(self.btn_pdf)
        actions_bar.addWidget(self.btn_delete)
        layout.addLayout(actions_bar)

        # --- 3. Table ---
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID Trans.", "Date", "Client / Partenaire", "Montant (DZD)"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.cellDoubleClicked.connect(lambda r, c: self.on_edit_clicked())
        
        layout.addWidget(self.table)

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
        
        self.table.setRowCount(0)
        if hasattr(self.manager, 'external_transfers'):
            transfers = self.manager.external_transfers.get_transfers_filtered(start, end, p_id, None)
            for row, t in enumerate(transfers):
                self.table.insertRow(row)
                
                # التعديل هنا: استخدام التنسيق الجديد للعرض
                formatted_ref = self.format_id(t['Transfer_ID'], str(t.get('Transaction_Date', '')))
                id_item = QTableWidgetItem(formatted_ref)
                id_item.setData(Qt.UserRole, t['Transfer_ID']) # حفظ الـ ID الحقيقي في الـ Data للعمليات البرمجية
                
                raw_date = t.get('Transaction_Date')
                if hasattr(raw_date, 'strftime'):
                    date_text = raw_date.strftime("%Y-%m-%d %H:%M")
                else:
                    date_text = str(raw_date or "")

                partner_text = t.get('Partner_Name') or t.get('City') or "-"
                amount = float(t.get('Total_Amount') or 0)
                amount_item = QTableWidgetItem(f"{amount:,.2f}")
                amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                self.table.setItem(row, 0, id_item)
                self.table.setItem(row, 1, QTableWidgetItem(date_text))
                self.table.setItem(row, 2, QTableWidgetItem(str(partner_text)))
                self.table.setItem(row, 3, amount_item)
        
        self.on_selection_changed()
        self.filter_table(self.search_input.text())

    def filter_table(self, text):
        for r in range(self.table.rowCount()):
            match = any(text.lower() in (self.table.item(r, col).text().lower() if self.table.item(r, col) else "") for col in [0, 2])
            self.table.setRowHidden(r, not match)

    # =========================================================================
    # PDF Export Logic - FIXED PATHS & FULL DEBUGGING
    # =========================================================================
    def export_transfer_to_pdf(self, transfer_id):
        """
        توليد ملف PDF احترافي مع ترقيم بنظام (السنة/الرقم) YYYY/NNN
        """
        print("\n" + "🚀" * 10 + " PDF DEBUG START " + "🚀" * 10)
        
        if not HAS_REPORTLAB:
            QMessageBox.warning(self, "Error", "The 'reportlab' library is missing.")
            return

        # 1. تحديد المسارات وتحميل الإعدادات
        cwd = os.getcwd()
        settings_path = os.path.join(cwd, "config.json")
        
        try:
            if not os.path.exists(settings_path):
                # محاولة البحث عن الملف في المجلد الأب إذا لم يوجد في cwd
                base_dir = os.path.dirname(os.path.abspath(__file__))
                settings_path = os.path.abspath(os.path.join(base_dir, "..", "..", "..", "pdf_settings.json"))

            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Configuration error: {str(e)}")
            return

        logo_path = settings.get('banner_path', '')
        if not os.path.exists(logo_path):
            logo_path = get_banner_path()

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
            partner_info = self.manager.partners.get_partner_by_id(header_data['Partner_ID'])
        except Exception as e:
            QMessageBox.critical(self, "DB Error", str(e))
            return

        # --- [تطبيق منطق الترقيم الجديد YYYY/000] ---
        # استخراج السنة من تاريخ المعاملة
        raw_date = str(header_data.get('Transaction_Date', ''))
        try:
            year_val = raw_date.split('-')[0] if '-' in raw_date else str(datetime.now().year)
            # تنسيق الرقم بـ 3 خانات (أو أكثر إذا لزم الأمر)
            formatted_ref = f"{year_val}/{int(transfer_id):03d}"
        except:
            formatted_ref = str(transfer_id)
        # --------------------------------------------

        # 3. حوار حفظ الملف (مع معالجة اسم الملف ليقبل الحفظ)
        partner_clean = str(header_data.get('Partner_Name', 'Client')).replace(" ", "_")
        # في اسم الملف نستبدل / بـ - لأن أنظمة التشغيل لا تقبل / في أسماء الملفات
        safe_ref_for_filename = formatted_ref.replace("/", "-")
        default_name = f"{settings.get('doc_title', 'BL')}_{partner_clean}_{safe_ref_for_filename}.pdf"
        
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer PDF", default_name, "PDF Files (*.pdf)")
        if not path: return

        # 4. بناء المستند (ReportLab)
        try:
            PAGE_WIDTH, PAGE_HEIGHT = A4
            primary_color = colors.HexColor(settings.get('theme_color', '#0b666a'))
            banner_h_cm = settings.get('banner_height_cm', 4.8)
            
            doc = SimpleDocTemplate(
                path, pagesize=A4, rightMargin=30, leftMargin=30, 
                topMargin=(banner_h_cm + 0.5) * cm, bottomMargin=50
            )

            elements = []
            styles = getSampleStyleSheet()

            def draw_header_compact(canvas, doc):
                canvas.saveState()
                img_x = settings.get('banner_img_x_cm', 0.0) * cm
                img_w = settings.get('banner_img_w_cm', 21.0) * cm
                img_h = settings.get('banner_img_h_cm', 4.8) * cm
                y_offset = settings.get('banner_img_y_cm', 0.2) * cm
                img_y = PAGE_HEIGHT - img_h - y_offset
                
                if os.path.exists(logo_path):
                    canvas.drawImage(logo_path, img_x, img_y, width=img_w, height=img_h)
                else:
                    canvas.setStrokeColor(colors.red)
                    canvas.rect(img_x, img_y, img_w, img_h, stroke=1)
                canvas.restoreState()

            # محتوى الترويسة (المعلومات البنكية والزبون)
            current_time = datetime.now().strftime('%d/%m/%Y %H:%M')
            
            # استخدام formatted_ref الجديد هنا ليظهر في ملف الـ PDF
            left_text = (
                f"<font size=14 color='{settings.get('theme_color')}'><b>{settings.get('doc_title')} N°: {formatted_ref}</b></font><br/><br/>"
                f"<b>Banque :</b> {settings.get('bank_name', 'N/A')}<br/>"
                f"<b>N° Compte :</b> {settings.get('bank_acc', 'N/A')}<br/>"
                f"<font size=9>Date d'édition : {current_time}</font>"
            )
            
            p_name = partner_info.get('Partner_Name', 'Inconnu')
            p_addr = partner_info.get('Address_Line1') or ""
            p_city = partner_info.get('City') or ""
            right_text = f"<b>Destinataire :</b><br/><font size=11><b>{p_name}</b></font><br/>{p_addr}<br/>{p_city}"

            info_table = Table([[Paragraph(left_text, styles["Normal"]), Paragraph(right_text, styles["Normal"])]], 
                               colWidths=[10*cm, 8.4*cm])
            info_table.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('BACKGROUND', (1,0), (1,0), colors.HexColor("#f8f9fa")),
                ('BOX', (1,0), (1,0), 0.5, colors.lightgrey),
                ('PADDING', (1,0), (1,0), 10),
            ]))
            elements.append(info_table)
            elements.append(Spacer(1, 0.8 * cm))

            # جدول المنتجات
            table_data = [["Désignation Produit", "Qté", "Observation"]]
            grand_total = 0.0

            for item in details_data:
                is_billable = item.get('Is_Billable', False)
                qty = item.get('Qty_Transferred', 0)
                qty_numeric = float(qty or 0)
                price = float(item.get('Unit_Price', 0))
                line_val = (qty_numeric * price) if is_billable else 0.0
                grand_total += line_val

                obs = f"{line_val:,.2f} DA" if is_billable else "<font color='red'>Gratuit</font>"
                p_info = f"<b>{item.get('Product_Name', '-')}</b><br/><font size=8 color='grey'>Lot: {item.get('Lot_Number','-')}</font>"
                
                table_data.append([Paragraph(p_info, styles["Normal"]), format_quantity(qty), Paragraph(obs, styles["Normal"])])

            table_data.append([Paragraph("<b>MONTANT TOTAL À PAYER</b>", styles["Normal"]), "", f"{grand_total:,.2f} DA"])

            items_table = Table(table_data, colWidths=[11.0*cm, 2.0*cm, 6.0*cm])
            items_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), primary_color),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('GRID', (0,0), (-1,-1), 0.1, colors.grey),
                ('ALIGN', (1,0), (1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('SPAN', (0, -1), (1, -1)),
                ('PADDING', (0,0), (-1,-1), 6),
            ]))
            elements.append(items_table)
            elements.append(Spacer(1, 1.5 * cm))

            # التوقيعات
            f_left = settings.get('footer_left_label', 'Responsable')
            f_right = settings.get('footer_right_label', 'Accusé Client')
            
            footer = Table([[Paragraph(f"<b>{f_left}</b>", styles["Normal"]), Paragraph(f"<b>{f_right}</b>", styles["Normal"])]], 
                           colWidths=[9.2*cm, 9.2*cm], rowHeights=[2.5*cm])
            footer.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (1,0), (1,-1), 40)]))
            elements.append(footer)

            doc.build(elements, onFirstPage=draw_header_compact, onLaterPages=draw_header_compact)

            # فتح الملف تلقائياً
            if os.name == 'nt': os.startfile(path)
            else: os.system(f'xdg-open "{path}"')
                
        except Exception as e:
            QMessageBox.critical(self, "Erreur PDF", f"Build failed: {str(e)}")
        
        print("="*50 + " DEBUG END " + "="*50)
