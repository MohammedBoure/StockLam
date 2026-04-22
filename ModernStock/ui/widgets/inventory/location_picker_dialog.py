# ui/widgets/location_picker_dialog.py

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTreeView, QPushButton, 
                               QHBoxLayout, QLabel, QLineEdit)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QStyle

class LocationPickerDialog(QDialog):
    """
    نافذة اختيار الموقع (شجرة + بحث).
    """
    def __init__(self, location_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sélectionner un Emplacement")
        self.resize(600, 700)
        self.manager = location_manager
        self.selected_id = None
        self.selected_name = None
        
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        search_layout = QHBoxLayout()
        lbl_search = QLabel("🔍 Rechercher:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Tapez le nom de l'emplacement...")
        self.search_input.textChanged.connect(self.filter_tree) # ربط البحث
        
        search_layout.addWidget(lbl_search)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setEditTriggers(QTreeView.NoEditTriggers)
        self.tree_view.doubleClicked.connect(self.accept_selection)
        
        self.model = QStandardItemModel()
        self.tree_view.setModel(self.model)
        
        layout.addWidget(self.tree_view)

        btn_layout = QHBoxLayout()
        
        btn_clear = QPushButton("Tout Afficher / Désélectionner")
        btn_clear.clicked.connect(self.clear_selection)
        
        btn_cancel = QPushButton("Annuler")
        btn_cancel.clicked.connect(self.reject)
        
        btn_select = QPushButton("Sélectionner")
        btn_select.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold;")
        btn_select.clicked.connect(self.accept_selection)

        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_select)
        
        layout.addLayout(btn_layout)

    def load_data(self):
        try:
            hierarchy = self.manager.get_location_hierarchy()
            root = self.model.invisibleRootItem()
            self._populate_tree(root, hierarchy)
            self.tree_view.expandAll()
        except Exception as e:
            print(f"Error loading tree: {e}")

    def _populate_tree(self, parent_item, children_list):
        for node in children_list:
            item = QStandardItem(node['Location_Name'])
            item.setData(node['Location_ID'], Qt.UserRole)
            item.setEditable(False)
            
            has_children = len(node.get('children', [])) > 0
            if has_children:
                item.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
            else:
                item.setIcon(self.style().standardIcon(QStyle.SP_FileIcon))
            
            parent_item.appendRow(item)
            
            if has_children:
                self._populate_tree(item, node['children'])

    # --- منطق البحث والفلترة ---
    def filter_tree(self, text):
        """إخفاء العناصر التي لا تطابق البحث مع الحفاظ على الهيكلية"""
        search_text = text.lower().strip()
        root = self.model.invisibleRootItem()
        
        if not search_text:
            # إظهار الكل
            self._set_visible_recursive(root, True)
            self.tree_view.expandAll()
            return

        # إخفاء الكل أولاً، ثم إظهار المطابق
        self._set_visible_recursive(root, False)
        
        # البحث عن المطابق وإظهاره مع الآباء
        self._match_and_show(root, search_text)

    def _set_visible_recursive(self, item, visible):
        """تعيين الرؤية (الإخفاء) لجميع العناصر"""
        for row in range(item.rowCount()):
            child = item.child(row)
            self.tree_view.setRowHidden(row, item.index(), not visible)
            self._set_visible_recursive(child, visible)

    def _match_and_show(self, item, text):
        """دالة تكرارية للبحث وإظهار النتائج ومسارها"""
        match_found_in_branch = False
        
        for row in range(item.rowCount()):
            child = item.child(row)
            child_text = child.text().lower()
            
            # هل هذا العنصر يطابق؟
            is_match = text in child_text
            
            # هل يوجد تطابق في الأبناء؟
            child_has_match = self._match_and_show(child, text)
            
            if is_match or child_has_match:
                self.tree_view.setRowHidden(row, item.index(), False) # إظهار
                self.tree_view.setExpanded(item.index(), True) # توسيع الأب
                match_found_in_branch = True
                
        return match_found_in_branch

    def clear_selection(self):
        self.selected_id = None
        self.selected_name = "Tous les Emplacements"
        self.accept()

    def accept_selection(self):
        index = self.tree_view.currentIndex()
        if index.isValid():
            item = self.model.itemFromIndex(index)
            self.selected_id = item.data(Qt.UserRole)
            self.selected_name = item.text()
        else:
            if self.selected_id is None:
                self.selected_name = "Tous les Emplacements"
        
        self.accept()

    def get_selected_location(self):
        return self.selected_id, self.selected_name