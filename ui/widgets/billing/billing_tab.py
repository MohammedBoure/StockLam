# ui/widgets/billing/billing_tab.py

import logging
from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from .invoices_list import InvoicesListWidget
from .invoice_editor import InvoiceEditorWidget

class BillingTab(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.manager = data_manager

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)

        # إنشاء الصفحات (هنا يحدث الاستيراد)
        self.list_view = InvoicesListWidget(self.manager)
        self.editor_view = InvoiceEditorWidget(self.manager)

        self.stack.addWidget(self.list_view)
        self.stack.addWidget(self.editor_view)

        # ربط الإشارات
        self.list_view.request_new.connect(self.open_new_invoice)
        self.list_view.request_new_return.connect(self.open_new_return)
        self.list_view.request_edit.connect(self.open_edit_invoice)
        self.list_view.request_pdf.connect(self.handle_pdf_request) # تأكد من وجود دالة handle_pdf_request أو ربطها بالـ PDF مباشرة

        self.editor_view.request_back.connect(self.show_list)

        self.show_list()

    def show_list(self):
        self.list_view.load_data()
        self.stack.setCurrentWidget(self.list_view)

    def open_new_invoice(self, partner_id=None):
        self.editor_view.transfer_type_mode = 'Outbound'
        self.editor_view.load_context(None)
        if partner_id:
            idx = self.editor_view.combo_partner.findData(partner_id)
            if idx >= 0:
                self.editor_view.combo_partner.setCurrentIndex(idx)
        self.stack.setCurrentWidget(self.editor_view)

    def open_new_return(self, data=None):
        if isinstance(data, dict):
            partner_id = data.get('partner_id')
            ref_transfer_id = data.get('ref_transfer_id')
        else:
            partner_id = data
            ref_transfer_id = None
        
        self.editor_view.transfer_type_mode = 'Return'
        self.editor_view.ref_transfer_id = ref_transfer_id
        self.editor_view.load_context(None, preselected_partner_id=partner_id)
        self.stack.setCurrentWidget(self.editor_view)

    def open_edit_invoice(self, transfer_id):
        # type is loaded inside load_context
        self.editor_view.load_context(transfer_id)
        self.stack.setCurrentWidget(self.editor_view)

    def handle_pdf_request(self, transfer_id):
        if hasattr(self, 'export_transfer_to_pdf'):
            self.export_transfer_to_pdf(transfer_id)
