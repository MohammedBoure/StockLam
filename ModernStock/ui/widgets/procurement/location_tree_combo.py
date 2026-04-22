# ui/widgets/location_tree_combo.py

import qtawesome as qta # استيراد المكتبة الجديدة
from PySide6.QtWidgets import QComboBox, QTreeView, QFrame
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon
from PySide6.QtCore import Qt, QSize,QModelIndex
from PySide6.QtWidgets import QStyle

class LocationTreeComboBox(QComboBox):
    """
    مكون مخصص يظهر المواقع بشكل شجري هرمي مع أيقونات احترافية.
    """
    def __init__(self, location_manager, parent=None):
        super().__init__(parent)
        self.manager = location_manager
        
        # إعداد العرض ليكون شجرياً
        self.tree_view = QTreeView()
        self.tree_view.setFrameShape(QFrame.NoFrame)
        self.tree_view.setEditTriggers(QTreeView.NoEditTriggers)
        self.tree_view.setSelectionBehavior(QTreeView.SelectRows)
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setExpandsOnDoubleClick(True)
        self.tree_view.setAnimated(True)
        # زيادة المسافة البادئة قليلاً لتوضيح الهرمية
        self.tree_view.setIndentation(20)
        
        self.setView(self.tree_view)
        self.setModel(QStandardItemModel(self))
        
        # تحميل البيانات
        self.refresh_locations()
        
    def refresh_locations(self):
        self.clear()
        model = self.model()
        model.clear()
        
        # 1. خيار "الكل" مع أيقونة خريطة احترافية بلون Teal
        root_item = QStandardItem(" Tous les Emplacements")
        root_item.setData(None, Qt.UserRole)
        root_item.setIcon(qta.icon('fa5s.map-marked-alt', color='#007572'))
        model.appendRow(root_item)
        
        # جلب البيانات الهرمية من المدير
        try:
            if hasattr(self.manager, 'get_location_hierarchy'):
                hierarchy = self.manager.get_location_hierarchy()
                self._populate_tree(model.invisibleRootItem(), hierarchy)
            else:
                # Fallback (احتياط)
                flat = self.manager.get_all_locations_flat()
                for loc in flat:
                    item = QStandardItem(loc['Location_Name'])
                    item.setData(loc['Location_ID'], Qt.UserRole)
                    item.setIcon(qta.icon('fa5s.box', color='#007572'))
                    model.appendRow(item)
                    
        except Exception as e:
            print(f"Error loading location tree: {e}")

        self.tree_view.expandAll() 

    def _populate_tree(self, parent_item, children_list):
        """دالة تكرارية لبناء الشجرة مع توزيع الأيقونات حسب النوع"""
        for node in children_list:
            item = QStandardItem(node['Location_Name'])
            item.setData(node['Location_ID'], Qt.UserRole)
            
            # تحديد نوع الموقع لاختيار الأيقونة المناسبة (نفس المنطق المتبع في LocationsTab)
            loc_type = node.get('Type_Name', "")
            has_children = len(node.get('children', [])) > 0
            
            # منطق اختيار الأيقونة
            icon_name = 'fa5s.box' # الافتراضي: علبة/موقع تخزين
            if loc_type == "Bâtiment": 
                icon_name = 'fa5s.building'
            elif loc_type == "Salle": 
                icon_name = 'fa5s.door-open'
            elif loc_type in ["Réfrigérateur", "Congélateur"]: 
                icon_name = 'fa5s.snowflake'
            elif loc_type == "Étagère": 
                icon_name = 'fa5s.layer-group'
            elif has_children:
                # إذا كان مجلداً عادياً أو نوعاً غير محدد وله أبناء
                icon_name = 'fa5s.folder-open'
            
            # تعيين الأيقونة بلون Teal الموحد للبرنامج
            item.setIcon(qta.icon(icon_name, color='#007572'))
            parent_item.appendRow(item)
            
            # التكرار للأبناء
            if has_children:
                self._populate_tree(item, node['children'])

    def get_current_location_id(self):
        """إرجاع المعرف المحدد حالياً من الشجرة."""
        # البحث في الفهرس الحالي للـ TreeView لضمان جلب البيانات حتى لو كانت متداخلة
        index = self.tree_view.currentIndex()
        if index.isValid():
            return index.data(Qt.UserRole)
        return self.currentData(Qt.UserRole)

    def select_location_id(self, location_id):
        """تحديد الموقع برمجياً بالبحث داخل كافة مستويات الشجرة."""
        if location_id is None:
            self.setCurrentIndex(0)
            return

        model = self.model()
        # دالة بحث داخلية تكرارية
        def find_in_model(parent_index, target_id):
            for row in range(model.rowCount(parent_index)):
                idx = model.index(row, 0, parent_index)
                if idx.data(Qt.UserRole) == target_id:
                    return idx
                if model.hasChildren(idx):
                    result = find_in_model(idx, target_id)
                    if result: return result
            return None

        found_idx = find_in_model(QModelIndex(), location_id)
        if found_idx:
            self.tree_view.setCurrentIndex(found_idx)
            self.setRootModelIndex(found_idx.parent()) # لضمان ظهور النص في الـ ComboBox
            self.setCurrentIndex(found_idx.row())
            self.setRootModelIndex(QModelIndex()) # إعادة الجذر للوضع الطبيعي