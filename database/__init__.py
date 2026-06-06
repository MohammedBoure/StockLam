# database\__init__.py
from .base import Database 
from .manufacturer_manager import ManufacturerManager
from .supplier_manager import SupplierManager
from .location_manager import LocationManager
from .automate_manager import AutomateManager
from .waste_reason_manager import WasteReasonManager
from .product_manager import ProductManager
from .product_document_manager import ProductDocumentManager
from .purchase_order_manager import PurchaseOrderManager
from .po_details_manager import PODetailsManager
from .reception_log_manager import ReceptionLogManager
from .inventory_batch_manager import InventoryBatchManager
from .active_container_manager import ActiveContainerManager
from .stock_movement_log_manager import StockMovementLogManager
from .statistics_manager import StatisticsManager
from .printer_manager import PrinterManager
from .product_family_manager import ProductFamilyManager
from .packaging_unit_manager import PackagingUnitManager
from .user_manager import UserManager
from .external_partners_manager import ExternalPartnersManager
from .external_transfer_manager import ExternalTransferManager
from .credit_note_manager import CreditNoteManager
from .inventory_count_manager import InventoryCountManager
from .system_log_manager import SystemLogManager
from .system_logger import active_user_id,log_methods
class LabDataManager:

    def __init__(self, db_instance: Database):
        self.db = db_instance
        
        # 1. Master Data Managers
        self.manufacturers = ManufacturerManager(db_instance)
        self.suppliers = SupplierManager(db_instance)
        self.locations = LocationManager(db_instance)
        self.automates = AutomateManager(db_instance)
        self.waste_reasons = WasteReasonManager(db_instance)
        self.families = ProductFamilyManager(db_instance)      
        self.packaging_units = PackagingUnitManager(db_instance) 
        
        # 2. Product/Document Managers
        self.products = ProductManager(db_instance)
        self.documents = ProductDocumentManager(db_instance)
        
        # 3. Procurement Managers
        self.po = PurchaseOrderManager(db_instance)
        self.po_details = PODetailsManager(db_instance, self.po) 
        self.reception = ReceptionLogManager(db_instance)
        
        # 4. Inventory Managers (Logic core)
        self.batches = InventoryBatchManager(db_instance)
        self.containers = ActiveContainerManager(db_instance) 
        self.movement = StockMovementLogManager(db_instance)

        # 5. Utilities & Reporting
        self.stats = StatisticsManager(db_instance)
        self.printer = PrinterManager(db_instance)

        self.users = UserManager(db_instance)

        self.partners = ExternalPartnersManager(self.db)
        self.external_transfers = ExternalTransferManager(self.db)

        self.credit_notes = CreditNoteManager(self.db)
        self.inventory_counts = InventoryCountManager(db_instance)

        self.system_log = SystemLogManager(db_instance)
