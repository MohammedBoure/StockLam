# ui/widgets/procurement/reception_dialog_parts.py

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLineEdit, QTreeWidget, 
                               QTreeWidgetItem, QDialogButtonBox)
from PySide6.QtCore import Qt

class LocationTreeDialog(QDialog):
    """نافذة منبثقة لعرض المواقع بشكل شجري واختيار أحدها."""
    def __init__(self, locations_flat_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sélectionner un Emplacement")
        self.resize(400, 500)
        self.selected_location_id = None
        self.selected_location_name = None
        
        layout = QVBoxLayout(self)
        
        # شريط بحث سريع
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filtrer (ex: Frigo, Salle A)...")
        self.search_input.textChanged.connect(self.filter_tree)
        layout.addWidget(self.search_input)

        # شجرة المواقع
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Structure des Emplacements")
        self.tree.itemDoubleClicked.connect(self.accept_selection)
        layout.addWidget(self.tree)
        
        self.flat_list = locations_flat_list
        self.build_tree(locations_flat_list)
        
        # أزرار التأكيد والإلغاء
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept_selection)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def build_tree(self, flat_list):
        """بناء هيكل الشجرة من قائمة مسطحة."""
        self.tree.clear()
        nodes = {}
        # 1. إنشاء العناصر
        for loc in flat_list:
            item = QTreeWidgetItem([loc['Location_Name']])
            item.setData(0, Qt.UserRole, loc) 
            nodes[loc['Location_ID']] = item

        # 2. ربط الأبناء بالآباء
        root_items = []
        for loc in flat_list:
            node = nodes[loc['Location_ID']]
            parent_id = loc.get('Parent_Location_ID')
            
            if parent_id and parent_id in nodes:
                nodes[parent_id].addChild(node)
            else:
                root_items.append(node)

        self.tree.addTopLevelItems(root_items)
        self.tree.expandAll()

    def filter_tree(self, text):
        """إخفاء العناصر التي لا تطابق كلمة البحث."""
        search_term = text.lower()
        def create_match_flags(item):
            text_match = search_term in item.text(0).lower()
            child_match = False
            for i in range(item.childCount()):
                if create_match_flags(item.child(i)):
                    child_match = True
            
            should_show = text_match or child_match
            item.setHidden(not should_show)
            if should_show:
                item.setExpanded(True)
            return should_show

        for i in range(self.tree.topLevelItemCount()):
            create_match_flags(self.tree.topLevelItem(i))

    def accept_selection(self):
        """تأكيد الاختيار وإرسال البيانات للنافذة الرئيسية."""
        item = self.tree.currentItem()
        if not item:
            return
        
        data = item.data(0, Qt.UserRole)
        self.selected_location_id = data['Location_ID']
        self.selected_location_name = data.get('Location_Name_Flat', data['Location_Name'])
        self.accept()