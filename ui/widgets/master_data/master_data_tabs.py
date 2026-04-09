# ui/widgets/master_data/master_data_tabs.py

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget)

from .products_tab import ProductsTab
from .suppliers_tab import SuppliersTab
from .manufacturers_tab import ManufacturersTab
from .locations_tab import LocationsTab
from .automates_tab import AutomatesTab
from .waste_reasons_tab import WasteReasonsTab
from .product_families_tab import ProductFamiliesTab
from .packaging_units_tab import PackagingUnitsTab
from .external_partners_tab import ExternalPartnersTab 

class MasterDataTabs(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        # 1. تهيئة الواجهات فقط
        self.tab_products = ProductsTab(self.data_manager)
        self.tab_families = ProductFamiliesTab(self.data_manager)
        self.tab_units = PackagingUnitsTab(self.data_manager)
        self.tab_suppliers = SuppliersTab(self.data_manager.suppliers)
        self.tab_manufacturers = ManufacturersTab(self.data_manager.manufacturers)
        self.tab_locations = LocationsTab(self.data_manager.locations)
        self.tab_automates = AutomatesTab(self.data_manager.automates, self.data_manager.locations)
        self.tab_waste = WasteReasonsTab(self.data_manager.waste_reasons)
        self.tab_partners = ExternalPartnersTab(self.data_manager.partners) 


        layout.addWidget(self.tabs)