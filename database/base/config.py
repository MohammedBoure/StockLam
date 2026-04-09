import sys
import codecs
import json
import logging
import os
from datetime import datetime, date
from decimal import Decimal


try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except (AttributeError, TypeError):
    try:
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except Exception as e:
        print(f"Warning: Could not force console to UTF-8. {e}")


logger = logging.getLogger("MODERNLAM")

TABLE_IMPORT_ORDER = [
    'Users', 'Location_Types', 'Product_Families', 'Packaging_Units',
    'Manufacturers', 'Suppliers', 'External_Partners', 'Locations', 'Automates', 'Waste_Reasons',
    'Products_Master', 'Product_Documents', 'Purchase_Orders', 'PO_Details',
    'Reception_Log', 'Reception_Details', 'Inventory_Batches',
    'Active_Containers', 'External_Transfer_Log', 'External_Transfer_Details', 'Stock_Movement_Log',
    'Supplier_Credit_Notes', 'Credit_Note_Details', 'Supplier_Payments', 'SystemLogs' # <-- تمت الإضافة هنا
]

ARCHIVE_VIEW_FLAG_FILE = 'archive_view.flag'


def get_external_path(filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(os.path.dirname(sys.executable), filename)
    return os.path.join(os.path.abspath("."), filename)


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)
