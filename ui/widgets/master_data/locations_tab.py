# ui/widgets/master_data/locations_tab.py

import logging
import os
import qtawesome as qta
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, 
                               QTreeWidgetItem, QSplitter, QLabel, QPushButton, 
                               QFrame, QFormLayout, QMenu, QMessageBox, QLineEdit, 
                               QHeaderView, QTreeWidgetItemIterator)
from PySide6.QtCore import Qt, QSize, QTimer 
from PySide6.QtGui import QAction, QFont, QColor, QBrush, QIcon

from .dialogs import LocationDialog
from .location_types_manager import LocationTypesManagerDialog

class LocationsTab(QWidget):
    def __init__(self, location_manager):
        super().__init__()
        self.manager = location_manager 
        self.init_ui()
        self.load_tree_data()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # --- 1. Header Toolbar ---
        toolbar = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher un emplacement...")
        self.search_input.textChanged.connect(self.filter_tree)
        self.search_input.setFixedHeight(36)

        # زر إدارة الأنواع مع أيقونة Tags
        btn_manage_types = QPushButton(" Gérer les Types")
        btn_manage_types.setIcon(qta.icon('fa5s.tags', color='#2c3e50'))
        btn_manage_types.setCursor(Qt.PointingHandCursor)
        btn_manage_types.setFixedHeight(36)
        btn_manage_types.clicked.connect(self.open_types_manager)

        # زر التحديث مع أيقونة Sync
        btn_refresh = QPushButton(" Actualiser")
        btn_refresh.setIcon(qta.icon('fa5s.sync-alt', color='#2c3e50'))
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setFixedHeight(36)
        btn_refresh.clicked.connect(self.load_tree_data)
        
        # زر الإضافة الرئيسي مع أيقونة Plus بيضاء
        btn_add_root = QPushButton(" Racine")
        btn_add_root.setIcon(qta.icon('fa5s.plus', color='white'))
        btn_add_root.setCursor(Qt.PointingHandCursor)
        btn_add_root.setFixedHeight(36)
        btn_add_root.setProperty("class", "primary") 
        btn_add_root.clicked.connect(self.add_root_location)

        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(btn_manage_types)
        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_add_root)
        
        main_layout.addLayout(toolbar)

        # --- 2. Main Content (Splitter) ---
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)

        # === A. The Tree Widget ===
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Structure Hiérarchique", "Type", "Conditions"])
        self.tree.setColumnWidth(0, 350)
        self.tree.setIndentation(25)
        self.tree.setDragDropMode(QTreeWidget.InternalMove)
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_context_menu)

        # === B. Details Panel ===
        self.details_panel = QFrame()
        self.details_panel.setProperty("class", "card")
        self.details_layout = QVBoxLayout(self.details_panel)
        self.details_layout.setContentsMargins(20, 20, 20, 20)
        self.setup_details_panel()

        splitter.addWidget(self.tree)
        splitter.addWidget(self.details_panel)
        splitter.setStretchFactor(0, 65) 
        splitter.setStretchFactor(1, 35)
        main_layout.addWidget(splitter)

    def setup_details_panel(self):
        header_lbl = QLabel("INFORMATIONS")
        header_lbl.setProperty("class", "header")
        self.details_layout.addWidget(header_lbl)
        
        self.lbl_selected_name = QLabel("Sélectionnez un emplacement")
        self.lbl_selected_name.setWordWrap(True)
        self.details_layout.addWidget(self.lbl_selected_name)
        
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #f8f9fa; border-radius: 6px; padding: 10px;")
        info_layout = QFormLayout(info_frame)
        self.lbl_id = QLabel("-")
        self.lbl_type = QLabel("-")
        self.lbl_zone = QLabel("-")
        self.lbl_parent = QLabel("-")
        info_layout.addRow("ID:", self.lbl_id)
        info_layout.addRow("Type:", self.lbl_type)
        info_layout.addRow("Zone:", self.lbl_zone)
        info_layout.addRow("Parent:", self.lbl_parent)
        self.details_layout.addWidget(info_frame)
        self.details_layout.addStretch()

        actions_lbl = QLabel("ACTIONS")
        actions_lbl.setProperty("class", "header")
        self.details_layout.addWidget(actions_lbl)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(10)

        # أزرار الإجراءات مع أيقونات qta
        self.btn_add_child = QPushButton(" Ajouter Sous-Emplacement")
        self.btn_add_child.setIcon(qta.icon('fa5s.plus-circle', color='#2c3e50'))
        
        self.btn_edit = QPushButton(" Modifier les détails")
        self.btn_edit.setIcon(qta.icon('fa5s.edit', color='#2c3e50'))
        
        self.btn_delete = QPushButton(" Supprimer cet emplacement")
        self.btn_delete.setIcon(qta.icon('fa5s.trash-alt', color='white'))
        self.btn_delete.setProperty("class", "danger")

        self.btn_add_child.clicked.connect(self.add_child_location)
        self.btn_edit.clicked.connect(self.edit_location)
        self.btn_delete.clicked.connect(self.delete_location)

        btn_layout.addWidget(self.btn_add_child)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_delete)
        self.details_layout.addLayout(btn_layout)
        self.set_actions_enabled(False)

    def populate_tree_recursive(self, parent_widget, data_list):
        for item_data in data_list:
            item = QTreeWidgetItem(parent_widget)
            loc_type = item_data.get('Type_Name') or "N/A"
            
            # تحديد الأيقونة بناءً على النوع بلون Teal
            icon_name = 'fa5s.box'
            if loc_type == "Bâtiment": icon_name = 'fa5s.building'
            elif loc_type == "Salle": icon_name = 'fa5s.door-open'
            elif loc_type == "Réfrigérateur": icon_name = 'fa5s.snowflake'
            elif loc_type == "Congélateur": icon_name = 'fa5s.snowflake'
            elif loc_type == "Étagère": icon_name = 'fa5s.layer-group'
            
            item.setIcon(0, qta.icon(icon_name, color='#007572'))
            item.setText(0, item_data['Location_Name'])
            item.setText(1, loc_type)
            item.setText(2, item_data['Temperature_Zone'])
            item.setData(0, Qt.UserRole, item_data)

            if item_data.get('children'):
                self.populate_tree_recursive(item, item_data['children'])

    # ... (باقي الدوال CRUD و Filter و DragDrop تظل كما هي في المصدر الأصلي) ...
    def open_types_manager(self):
        dialog = LocationTypesManagerDialog(self.manager, self)
        dialog.exec()
        self.load_tree_data()

    def load_tree_data(self):
        self.tree.clear()
        try:
            hierarchy = self.manager.get_location_hierarchy()
            self.populate_tree_recursive(self.tree, hierarchy)
            self.tree.expandAll()
        except Exception as e:
            logging.error(f"Error loading tree: {e}")

    def on_item_clicked(self, item, column):
        data = item.data(0, Qt.UserRole)
        if not data: return
        self.lbl_id.setText(str(data['Location_ID']))
        self.lbl_selected_name.setText(data['Location_Name'])
        self.lbl_type.setText(data.get('Type_Name', 'Non défini'))
        self.lbl_zone.setText(data['Temperature_Zone'])
        parent_item = item.parent()
        self.lbl_parent.setText(parent_item.text(0) if parent_item else "Racine (Aucun)")
        self.set_actions_enabled(True)

    def set_actions_enabled(self, enabled):
        self.btn_add_child.setEnabled(enabled)
        self.btn_edit.setEnabled(enabled)
        self.btn_delete.setEnabled(enabled)
        if not enabled:
            self.lbl_selected_name.setText("Aucune sélection")
            self.lbl_id.setText("-")
            self.lbl_type.setText("-")
            self.lbl_zone.setText("-")
            self.lbl_parent.setText("-")

    def _get_types_for_dialog(self):
        return self.manager.get_all_location_types()

    def open_context_menu(self, position):
        item = self.tree.itemAt(position)
        if not item: return
        menu = QMenu()
        menu.setStyleSheet("QMenu::item:selected { background-color: #007572; color: white; }")
        act_add = QAction("➕ Ajouter Sous-Emplacement", self)
        act_edit = QAction("✏️ Modifier", self)
        act_del = QAction("🗑️ Supprimer", self)
        act_add.triggered.connect(self.add_child_location)
        act_edit.triggered.connect(self.edit_location)
        act_del.triggered.connect(self.delete_location)
        menu.addAction(act_add)
        menu.addAction(act_edit)
        menu.addSeparator()
        menu.addAction(act_del)
        menu.exec(self.tree.viewport().mapToGlobal(position))

    def add_root_location(self):
        types = self._get_types_for_dialog()
        dialog = LocationDialog(location_types=types, parent=self)
        if dialog.exec():
            data = dialog.get_data()
            if data:
                self.manager.add_location(data['Location_Name'], data['Type_ID'], data['Temperature_Zone'], None)
                self.load_tree_data()

    def add_child_location(self):
        current_item = self.tree.currentItem()
        if not current_item: return
        parent_data = current_item.data(0, Qt.UserRole)
        types = self._get_types_for_dialog()
        dialog = LocationDialog(location_types=types, parent=self, parent_name=parent_data['Location_Name'])
        if dialog.exec():
            data = dialog.get_data()
            if data:
                self.manager.add_location(data['Location_Name'], data['Type_ID'], data['Temperature_Zone'], parent_data['Location_ID'])
                self.load_tree_data()

    def edit_location(self):
        current_item = self.tree.currentItem()
        if not current_item: return
        data = current_item.data(0, Qt.UserRole)
        types = self._get_types_for_dialog()
        dialog = LocationDialog(location_types=types, parent=self, data=data)
        if dialog.exec():
            new_data = dialog.get_data()
            if new_data:
                self.manager.update_location(data['Location_ID'], new_data['Location_Name'], new_data['Type_ID'], new_data['Temperature_Zone'], data.get('Parent_Location_ID'))
                self.load_tree_data()

    def delete_location(self):
        current_item = self.tree.currentItem()
        if not current_item: return
        data = current_item.data(0, Qt.UserRole)
        if current_item.childCount() > 0:
            QMessageBox.warning(self, "Attention", "Cet emplacement contient des sous-emplacements.")
            return
        if self.manager.delete_location(data['Location_ID']):
            self.load_tree_data()
            self.set_actions_enabled(False)
        else:
            QMessageBox.warning(self, "Erreur", "Impossible de supprimer.")

    def filter_tree(self, text):
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            match = text.lower() in item.text(0).lower()
            item.setHidden(not match)
            if match:
                p = item.parent()
                while p: 
                    p.setHidden(False)
                    p.setExpanded(True)
                    p = p.parent()
            it += 1

    def dropEvent(self, event):
        source_item = self.tree.currentItem()
        destination_item = self.tree.itemAt(event.position().toPoint())
        success = False
        if source_item and destination_item and source_item != destination_item:
            source_data = source_item.data(0, Qt.UserRole)
            dest_data = destination_item.data(0, Qt.UserRole)
            success = self.manager.update_location(source_data['Location_ID'], source_data['Location_Name'], source_data['Type_ID'], source_data['Temperature_Zone'], dest_data['Location_ID'])
        elif source_item and not destination_item:
             source_data = source_item.data(0, Qt.UserRole)
             success = self.manager.update_location(source_data['Location_ID'], source_data['Location_Name'], source_data['Type_ID'], source_data['Temperature_Zone'], None)
        if success:
            event.accept()
            QTimer.singleShot(0, self.load_tree_data)
        else:
            event.ignore()