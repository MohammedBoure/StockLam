 # ui/widgets/inventory/inventory_view.py

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget)
from .tabs_batches import BatchesTab
from ..history import MovementHistoryTab
from .tabs_dispatch import DispatchTab
import logging

class InventoryTab(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        self.batches_tab = BatchesTab(self.data_manager)
        self.dispatch_tab = DispatchTab(self.data_manager)
        self.history_tab = MovementHistoryTab(self.data_manager)
        
        self.tabs.addTab(self.batches_tab, "📦 1. Stock Actuel")
        self.tabs.addTab(self.dispatch_tab, "🚚 2. Transfert & Consommation") 
        
        self.dispatch_tab.data_changed.connect(self.batches_tab.load_data)
        self.dispatch_tab.data_changed.connect(self.history_tab.load_data)
        self.batches_tab.data_changed.connect(self.dispatch_tab.load_inventory_data)
        
        layout.addWidget(self.tabs)

    def apply_role_permissions(self, role):
        """
        تخصيص المخزن بناءً على الدور.
        """
        is_technician = (role == 'Technician')
        is_consumer = (role == 'Manager') # المستهلك
        
        # -----------------------------------------------------------
        # [تعديل] قمنا بإيقاف إخفاء السجل لكي تتمكن من تجربته
        # -----------------------------------------------------------
        
        # كان الكود القديم يحذف التبويب هنا:
        # if is_technician or is_consumer:
        #     for i in range(self.tabs.count()):
        #         if "Historique" in self.tabs.tabText(i):
        #             self.tabs.removeTab(i)
        #             break
        
        # -----------------------------------------------------------

        # 2. وضع القراءة فقط للمستهلك (إخفاء أزرار الإضافة في BatchesTab)
        if is_consumer:
            if hasattr(self.batches_tab, 'btn_add_batch'):
                self.batches_tab.btn_add_batch.setVisible(False)
            if hasattr(self.batches_tab, 'btn_import'):
                self.batches_tab.btn_import.setVisible(False)
        
        # التقني يرى الأزرار بشكل طبيعي
        elif is_technician:
            if hasattr(self.batches_tab, 'btn_add_batch'):
                self.batches_tab.btn_add_batch.setVisible(True)