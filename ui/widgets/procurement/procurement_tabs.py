import logging
import os
import sys
import json
from datetime import datetime, date

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget, QPushButton, 
                               QHBoxLayout, QMessageBox, QLabel, QFileDialog, 
                               QFrame, QDateEdit) 
from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtGui import QColor

# --- ReportLab Imports for PDF ---
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.units import cm

from .dialogs import PurchaseOrderDialog
from .reception_tab import ReceptionTab
from .reception_history_tab import ReceptionHistoryTab
from .avoir import CreditNoteTab
from .reclamation_tab import ReclamationTab 
from ui.widgets.procurement.po_list_view import PurchaseOrderListView
from ui.formatting import format_quantity


def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class ProcurementTab(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #dcdcdc; background: white; }
            QTabBar::tab { padding: 10px 20px; font-weight: bold; color: #555; }
            QTabBar::tab:selected { color: #1abc9c; border-bottom: 2px solid #1abc9c; background: #fff; }
        """)
        
        # تهيئة الواجهات فقط دون إضافتها
        self.po_tab = PurchaseOrdersTab(self.data_manager)
        self.rec_tab = ReceptionTab(self.data_manager) 
        self.history_tab = ReceptionHistoryTab(self.data_manager)
        self.credit_tab = CreditNoteTab(self.data_manager)
        self.reclamation_tab = ReclamationTab(self.data_manager)
        
        # ❌ تم حذف أسطر self.tabs.addTab من هنا
        
        self.po_tab.data_changed.connect(self.rec_tab.load_pending_pos)
        self.tabs.currentChanged.connect(self.on_tab_change)
        
        self.history_tab.request_create_avoir.connect(self.open_credit_note_tab)
        self.po_tab.po_view.view_receptions_requested.connect(self.on_view_receptions_requested)
        
        layout.addWidget(self.tabs)

    def showEvent(self, event):
        super().showEvent(event)
        self.on_tab_change(self.tabs.currentIndex())

    def on_tab_change(self, index):
        # البحث عن الواجهة النشطة حالياً بدلاً من الاعتماد على الرقم الثابت
        current_widget = self.tabs.currentWidget()
        
        if current_widget == self.po_tab:
            self.po_tab.refresh_orders()
        elif current_widget == self.history_tab:
            self.history_tab.load_data()
        elif current_widget == self.credit_tab:
            if hasattr(self.credit_tab, 'refresh_history'):
                self.credit_tab.refresh_history()
        elif current_widget == self.reclamation_tab:
            if hasattr(self.reclamation_tab, 'load_data'):
                self.reclamation_tab.load_data()
        # ملاحظة: إذا تم تفعيل rec_tab يوماً ما، يمكنك إضافة تحديثه هنا

    def open_credit_note_tab(self, reception_data):
        # ✅ تعديل: التحقق من وجود التبويب قبل الانتقال إليه
        idx = self.tabs.indexOf(self.credit_tab)
        if idx != -1:
            self.tabs.setCurrentIndex(idx)
            if hasattr(self.credit_tab, 'populate_from_reception'):
                self.credit_tab.populate_from_reception(reception_data)

    def on_view_receptions_requested(self, po_id):
        # ✅ تعديل: التحقق من وجود التبويب قبل الانتقال إليه
        idx = self.tabs.indexOf(self.history_tab)
        if idx != -1:
            self.tabs.setCurrentIndex(idx)
            self.history_tab.show_history_for_po(po_id)


# --- الكلاس PurchaseOrdersTab يبقى كما هو (لا يحتاج تعديل) ---
class PurchaseOrdersTab(QWidget):
    data_changed = Signal() 
    def __init__(self, manager):
        super().__init__()
        self.manager = manager 
        self.btn_style = """
            QPushButton {
                background-color: #1abc9c; color: white; font-weight: bold; 
                border-radius: 4px; padding: 8px 15px; border: none;
            }
            QPushButton:hover { background-color: #16a085; }
        """
        self.sent_btn_style = self.btn_style.replace("#1abc9c", "#e67e22").replace("#16a085", "#d35400")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        toolbar_frame = QFrame()
        toolbar_frame.setStyleSheet("QFrame { background-color: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 6px; }")
        controls = QHBoxLayout(toolbar_frame)
        
        today = QDate.currentDate()
        start_of_year = QDate(today.year(), 1, 1)
        end_of_year = QDate(today.year(), 12, 31)

        lbl_du = QLabel("📅 Du:")
        lbl_du.setStyleSheet("font-weight: bold; color: #555;")
        
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.setDate(start_of_year)
        self.date_from.setFixedWidth(110)
        self.date_from.dateChanged.connect(self.refresh_orders)

        lbl_au = QLabel("Au:")
        lbl_au.setStyleSheet("font-weight: bold; color: #555;")

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setDate(end_of_year)
        self.date_to.setFixedWidth(110)
        self.date_to.dateChanged.connect(self.refresh_orders)

        btn_add = QPushButton("➕ Créer Commande")
        btn_add.clicked.connect(self.open_add_dialog)
        btn_add.setStyleSheet(self.btn_style)

        btn_mark_sent = QPushButton("🚚 Soumettez la demande")
        btn_mark_sent.setStyleSheet(self.sent_btn_style)
        btn_mark_sent.clicked.connect(self.confirm_order_sent)
        
        btn_pdf = QPushButton("📄 Bon de Commande (PDF)")
        btn_pdf.clicked.connect(self.export_po_pdf)
        btn_pdf.setStyleSheet(self.btn_style)

        btn_refresh = QPushButton("🔄 Actualiser")
        btn_refresh.clicked.connect(self.refresh_orders)
        btn_refresh.setStyleSheet(self.btn_style)
        
        controls.addWidget(lbl_du)
        controls.addWidget(self.date_from)
        controls.addWidget(lbl_au)
        controls.addWidget(self.date_to)
        
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        controls.addWidget(line)
        
        controls.addWidget(btn_add)
        controls.addWidget(btn_mark_sent)
        controls.addSpacing(20) 
        controls.addWidget(btn_pdf)
        controls.addStretch() 
        controls.addWidget(btn_refresh)
        
        layout.addWidget(toolbar_frame)
        
        # هنا يتم إنشاء po_view الذي يحتوي على الإشارة الجديدة
        self.po_view = PurchaseOrderListView(self.manager)
        layout.addWidget(self.po_view)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_orders()

    def refresh_orders(self):
        start_date = self.date_from.date().toString("yyyy-MM-dd")
        end_date = self.date_to.date().toString("yyyy-MM-dd")
        self.po_view.refresh_data(start_date=start_date, end_date=end_date)

    def confirm_order_sent(self):
        order = self.po_view.get_selected_order()
        if not order:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner une commande.")
            return

        if order['Status'] != 'Draft':
            QMessageBox.warning(self, "État", "Seules les commandes 'Draft' peuvent être marquées كـ Envoyée.")
            return

        confirm = QMessageBox.question(self, "Confirmation", 
                                     f"Marquer la commande #{order['PO_ID']} 'Envoyée' ?",
                                     QMessageBox.Yes | QMessageBox.No)
        
        if confirm == QMessageBox.Yes:
            try:
                if self.manager.po.update_status(order['PO_ID'], 'Sent'):
                    self.refresh_orders()
                    self.data_changed.emit()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Échec : {e}")

    def open_add_dialog(self):
        try:
            suppliers = self.manager.suppliers.get_all_suppliers() 
            products = self.manager.products.get_all_products()
            dialog = PurchaseOrderDialog(suppliers, products, self)
            if dialog.exec():
                data = dialog.get_data()
                if data:
                    po_id = self.manager.po.create_purchase_order(
                        supplier_id=data['Supplier_ID'],
                        order_date=data['Order_Date'],
                        expected_delivery_date=data['Expected_Delivery_Date'],
                        notes=data['Notes']
                    )
                    if po_id:
                        data['PO_ID'] = po_id
                        self.manager.po.update_full_order(po_id, data)
                        self.refresh_orders()
                        self.data_changed.emit()
        except Exception as e:
            logging.error(f"Error: {e}")

    def export_po_pdf(self):
        order_summary = self.po_view.get_selected_order()
        if not order_summary:
            QMessageBox.warning(self, "Avertissement", "Veuillez sélectionner une commande.")
            return

        po_id = order_summary['PO_ID']
        full_data = self.manager.po.get_full_order_details(po_id)

        if not full_data or not full_data.get('Details'):
            QMessageBox.warning(self, "Avertissement", "Aucun détail trouvé.")
            return

        raw_po_id = str(po_id).strip()
        if raw_po_id.isdigit() and len(raw_po_id) >= 3:
            year_short = raw_po_id[:2]
            bon_number = raw_po_id[2:]
            full_year = f"20{year_short}"
            formatted_po_id = f"{bon_number}/{full_year}"
        else:
            formatted_po_id = raw_po_id

        cwd = os.getcwd()
        settings_path = os.path.join(cwd, "config.json")

        try:
            if not os.path.exists(settings_path):
                raise FileNotFoundError(f"Settings file not found at {settings_path}")
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load settings: {e}")
            return

        safe_po_id = formatted_po_id.replace(" | ", "_")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer PDF",
            f"BC_MODERNLAM_{safe_po_id}.pdf",
            "PDF Files (*.pdf)"
        )
        if not path:
            return

        try:
            PAGE_WIDTH, PAGE_HEIGHT = A4
            primary_color = colors.HexColor(settings.get('theme_color', '#0b666a'))
            logo_path = os.path.normpath(settings.get('banner_path', ''))
            banner_h_cm = settings.get('banner_height_cm', 4.8)

            doc = SimpleDocTemplate(
                path,
                pagesize=A4,
                rightMargin=30,
                leftMargin=30,
                topMargin=(banner_h_cm + 0.5) * cm,
                bottomMargin=40
            )

            elements = []
            styles = getSampleStyleSheet()

            def draw_header_compact(canvas, doc):
                canvas.saveState()
                img_x = settings.get('banner_img_x_cm', 0.0) * cm
                img_w = settings.get('banner_img_w_cm', 21.0) * cm
                img_h = settings.get('banner_img_h_cm', 4.8) * cm
                img_y = PAGE_HEIGHT - img_h - (settings.get('banner_img_y_cm', 0.0) * cm)

                if os.path.exists(logo_path):
                    canvas.drawImage(
                        logo_path, img_x, img_y,
                        width=img_w, height=img_h, mask='auto'
                    )
                else:
                    canvas.setFont("Helvetica-Bold", 10)
                    canvas.drawCentredString(
                        PAGE_WIDTH / 2,
                        PAGE_HEIGHT - 1 * cm,
                        "LOGO NOT FOUND"
                    )
                canvas.restoreState()

            title_style = ParagraphStyle(
                'Title',
                parent=styles['Heading1'],
                alignment=1,
                fontSize=18,
                textColor=primary_color
            )

            elements.append(Paragraph("BON DE COMMANDE", title_style))
            elements.append(Spacer(1, 0.3 * cm))

            summary_data = [[
                Paragraph(
                    f"<b>FOURNISSEUR :</b><br/>{full_data.get('Supplier_Name')}",
                    styles["Normal"]
                ),
                Paragraph(
                    f"<b>BC N° :</b> {formatted_po_id}<br/>"
                    f"<b>Date :</b> {full_data.get('Order_Date')}<br/>"
                    f"<b>Livraison :</b> {full_data.get('Expected_Delivery_Date') or '---'}",
                    styles["Normal"]
                )
            ]]

            summary_table = Table(summary_data, colWidths=[9.2 * cm, 9.2 * cm])
            summary_table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('PADDING', (0, 0), (-1, -1), 6),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#fafafa"))
            ]))

            elements.append(summary_table)
            elements.append(Spacer(1, 0.6 * cm))

            table_headers = ["Désignation", "Marque", "Qté", "Pack", "Note"]
            table_data = [table_headers]

            for item in full_data['Details']:
                table_data.append([
                    Paragraph(f"<b>{item.get('Product_Name')}</b>", styles["Normal"]),
                    item.get('Manuf_Name') or "---",
                    format_quantity(item.get('Qty_Ordered')),
                    item.get('Ordering_Unit') or "U",
                    Paragraph(item.get('Item_Note') or "", styles["Normal"])
                ])

            items_table = Table(
                table_data,
                colWidths=[7.5 * cm, 3.5 * cm, 1.5 * cm, 2 * cm, 4 * cm]
            )

            items_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), primary_color),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.1, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1),
                [colors.white, colors.HexColor("#f8f8f8")]),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
            ]))

            elements.append(items_table)

            elements.append(Spacer(1, 2 * cm))
            footer_label = settings.get('footer_left_label', 'Signature et Cachet')

            sig_table = Table(
                [[Paragraph(f"<b>{footer_label}</b>", styles["Normal"])]],
                colWidths=[18.4 * cm]
            )
            sig_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT')
            ]))

            elements.append(sig_table)

            doc.build(
                elements,
                onFirstPage=draw_header_compact,
                onLaterPages=draw_header_compact
            )

            if os.name == 'nt':
                os.startfile(path)
            else:
                os.system(f'xdg-open "{path}"')

        except Exception as e:
            logging.error(f"Erreur PDF: {e}")
            QMessageBox.critical(self, "Erreur", f"Erreur: {str(e)}")
