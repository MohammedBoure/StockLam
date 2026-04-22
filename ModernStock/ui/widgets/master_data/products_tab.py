# ui/widgets/master_data/products_tab.py - Version Française Mise à Jour (Sans Code-barres ni Qté / Commande)

import logging
import traceback
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                               QTableWidgetItem, QHeaderView, QPushButton, QLineEdit, 
                               QMessageBox)
from PySide6.QtCore import Qt
from .dialogs import ProductDialog

class ProductsTab(QWidget):
    """
    Onglet de gestion du registre des produits (Master Data).
    Mise à jour : Suppression des colonnes "Code-barres" et "Qté / Commande" comme demandé.
    Affichage clair et utile des informations essentielles.
    """
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager 
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # --- Barre d'outils ---
        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher un produit (Nom, Famille, Marque, Unité...)")
        self.search_input.setMinimumHeight(35)
        self.search_input.textChanged.connect(self.load_products_data)

        self.btn_add = QPushButton("➕ Ajouter un Nouveau Produit")
        self.btn_add.setMinimumHeight(35)
        self.btn_add.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.btn_add.clicked.connect(self.open_add_dialog)

        self.btn_refresh = QPushButton("🔄 Actualiser")
        self.btn_refresh.setMinimumHeight(35)
        self.btn_refresh.clicked.connect(self.load_products_data)
        
        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_refresh)
        layout.addLayout(toolbar)

        # --- Tableau avec colonnes sélectionnées ---
        self.table = QTableWidget()
        columns = [
            "ID",                  # 0 - مخفية
            "Nom du Produit",      # 1
            "Famille",             # 2
            "Marque",              # 3
            "Unité Stock",         # 4  ← أصبحت الآن في العمود 4
            "Unité Commande",      # 5  ← أصبحت الآن في العمود 5
            "Seuil Min",           # 6
            "Température",         # 7
            "Automate Préféré"     # 8
        ]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)

        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(45)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setColumnHidden(0, True)  # إخفاء عمود ID

        self.table.doubleClicked.connect(self.open_edit_dialog)
        layout.addWidget(self.table)

        # --- Boutons d'actions ---
        actions = QHBoxLayout()
        self.btn_edit = QPushButton("✏️ Modifier le Produit Sélectionné")
        self.btn_edit.clicked.connect(self.open_edit_dialog)
        
        self.btn_delete = QPushButton("🗑️ Supprimer")
        self.btn_delete.setStyleSheet("color: #c0392b;")
        self.btn_delete.clicked.connect(self.delete_product)
        
        actions.addStretch()
        actions.addWidget(self.btn_edit)
        actions.addWidget(self.btn_delete)
        layout.addLayout(actions)

        self.load_products_data()

    def _create_centered_item(self, text, is_numeric=False):
        item = QTableWidgetItem(str(text) if text is not None else '---')
        item.setTextAlignment(Qt.AlignCenter)
        if is_numeric and text is not None:
            try:
                item.setData(Qt.EditRole, float(text))
            except:
                pass
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item
    
    def showEvent(self, event):
        super().showEvent(event)
        self.load_products_data()

    def load_products_data(self):
        try:
            self.table.setSortingEnabled(False)
            search_term = self.search_input.text().strip()
            products = self.data_manager.products.search_products(search_term)
            
            # جلب جميع الـ Automates مرة واحدة لتحسين الأداء وتجنب الخطأ
            all_automates = {}
            try:
                automates_list = self.data_manager.automates.get_all_automates()
                all_automates = {a['Automate_ID']: a['Automate_Name'] for a in automates_list}
            except Exception as e:
                logging.warning(f"Impossible de charger les automates pour l'affichage : {e}")
                all_automates = {}

            self.table.setRowCount(0)
            for row_idx, product in enumerate(products):
                self.table.insertRow(row_idx)
                
                # 0. ID + données complètes
                id_item = QTableWidgetItem()
                id_item.setData(Qt.EditRole, product['Product_ID'])
                id_item.setData(Qt.UserRole, product)
                self.table.setItem(row_idx, 0, id_item)
                
                # 1. Nom du Produit
                self.table.setItem(row_idx, 1, self._create_centered_item(product['Product_Name']))
                
                # 2. Famille
                self.table.setItem(row_idx, 2, self._create_centered_item(product.get('Family_Name', '---')))
                
                # 3. Marque
                self.table.setItem(row_idx, 3, self._create_centered_item(product.get('Manuf_Name', '---')))
                
                # 4. Unité Stock
                self.table.setItem(row_idx, 4, self._create_centered_item(product.get('Stock_Unit', '---')))
                
                # 5. Unité Commande
                self.table.setItem(row_idx, 5, self._create_centered_item(product.get('Ordering_Unit', '---')))
                
                # 6. Seuil Min
                min_stock = product.get('Minimum_Stock_Level', 0)
                self.table.setItem(row_idx, 6, self._create_centered_item(min_stock, is_numeric=True))
                
                # 7. Température
                temp = product.get('Storage_Temp_Req', '')
                self.table.setItem(row_idx, 7, self._create_centered_item(temp if temp else 'Ambiante'))
                
                # 8. Automate Préféré ← مصحح هنا
                preferred_id = product.get('Preferred_Automate_ID')
                automate_name = all_automates.get(preferred_id, 'Aucun') if preferred_id else 'Aucun'
                self.table.setItem(row_idx, 8, self._create_centered_item(automate_name))

            self.table.setSortingEnabled(True)
            logging.info(f"{len(products)} produits chargés dans le tableau.")
        except Exception as e:
            logging.error(f"Erreur lors du chargement des produits : {traceback.format_exc()}")
            QMessageBox.critical(self, "Erreur", f"Impossible de charger les produits :\n{e}")

    def open_add_dialog(self):
        try:
            manufacturers = self.data_manager.manufacturers.get_all_manufacturers()
            automates = self.data_manager.automates.get_all_automates()
            families = self.data_manager.families.get_all_families()
            packaging_units = self.data_manager.packaging_units.get_all_units()
            
            dialog = ProductDialog(manufacturers, automates, families, packaging_units, parent=self)
            if dialog.exec():
                product_data = dialog.get_data()
                if not product_data:
                    QMessageBox.warning(self, "Erreur", "Aucune donnée reçue du formulaire.")
                    return
                    
                success = self.data_manager.products.add_product(product_data)
                if success:
                    self.load_products_data()
                else:
                    QMessageBox.warning(self, "Erreur", "Échec de l'ajout en base de données.")
        except Exception as e:
            logging.error(f"Exception ajout produit : {traceback.format_exc()}")
            QMessageBox.critical(self, "Erreur", f"Échec de l'ajout : {e}")

    def open_edit_dialog(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Information", "Veuillez sélectionner un produit à modifier.")
            return

        product_data = self.table.item(row, 0).data(Qt.UserRole)
        if not product_data:
            QMessageBox.warning(self, "Erreur", "Données du produit non disponibles.")
            return
        
        try:
            manufacturers = self.data_manager.manufacturers.get_all_manufacturers()
            automates = self.data_manager.automates.get_all_automates()
            families = self.data_manager.families.get_all_families()
            packaging_units = self.data_manager.packaging_units.get_all_units()

            dialog = ProductDialog(
                manufacturers, 
                automates, 
                families, 
                packaging_units, 
                parent=self, 
                data=product_data
            )
            
            if dialog.exec():
                new_data = dialog.get_data()
                if new_data:
                    success = self.data_manager.products.update_product(product_data['Product_ID'], new_data)
                    if success:
                        self.load_products_data()
                    else:
                        QMessageBox.warning(self, "Erreur", "Échec de la mise à jour en base de données.")
                
        except Exception as e:
            logging.error(f"Erreur édition produit : {traceback.format_exc()}")
            QMessageBox.critical(self, "Erreur", f"Erreur lors de l'édition :\n{e}")

    def delete_product(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Avertissement", "Veuillez sélectionner un produit.")
            return

        product_data = self.table.item(row, 0).data(Qt.UserRole)
        confirm = QMessageBox.question(self, "Confirmation", 
                                       f"Supprimer le produit :\n{product_data['Product_Name']} ?",
                                       QMessageBox.Yes | QMessageBox.No)
        
        if confirm == QMessageBox.Yes:
            try:
                if self.data_manager.products.delete_product(product_data['Product_ID']):
                    self.load_products_data()
                else:
                    QMessageBox.warning(self, "Avertissement", "Impossible de supprimer (stock ou mouvements existants).")
            except Exception as e:
                logging.error(f"Erreur suppression : {traceback.format_exc()}")
                QMessageBox.critical(self, "Erreur", f"Échec de la suppression :\n{e}")