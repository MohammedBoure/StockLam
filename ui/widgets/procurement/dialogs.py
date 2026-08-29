from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
                               QLineEdit, QComboBox, QDialogButtonBox, QDateEdit, 
                               QTableWidget, QTableWidgetItem, QWidget, QLabel, 
                               QSpinBox, QPushButton, QHeaderView, QTextEdit, QFrame, 
                               QMessageBox, QCompleter, QGridLayout) 
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QBrush, QColor

from ui.widgets.master_data.dialogs import BaseDialog
from ui.formatting import format_money

class StockAlertDialog(QDialog):
    def __init__(self, parent=None, alerts_data=None):
        super().__init__(parent)
        self.setWindowTitle("Alertes de Stock")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)
        self.resize(500, 700)
        self.alerts_data = alerts_data or []
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        lbl_info = QLabel("Double-cliquez pour ajouter au formulaire de commande")
        lbl_info.setStyleSheet("color: #7f8c8d; font-style: italic; font-size: 12px;")
        lbl_info.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_info)
        
        self.alerts_table = QTableWidget()
        acols = ["Produit", "Marque", "Qté", "Seuil"]
        self.alerts_table.setColumnCount(len(acols))
        self.alerts_table.setHorizontalHeaderLabels(acols)
        
        aheader = self.alerts_table.horizontalHeader()
        aheader.setSectionResizeMode(0, QHeaderView.Stretch)      
        aheader.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        aheader.setSectionResizeMode(2, QHeaderView.ResizeToContents)       
        aheader.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        self.alerts_table.setAlternatingRowColors(True)
        self.alerts_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.alerts_table.setSelectionMode(QTableWidget.SingleSelection)
        self.alerts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.alerts_table.verticalHeader().setVisible(False)
        self.alerts_table.setWordWrap(True)
        
        self.alerts_table.cellDoubleClicked.connect(self.on_alert_double_clicked)
        
        layout.addWidget(self.alerts_table)
        
        self.load_stock_alerts()
        
        btn_close = QPushButton("Fermer")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)

    def load_stock_alerts(self):
        self.alerts_table.setRowCount(len(self.alerts_data))
        for row_idx, a in enumerate(self.alerts_data):
            p_item = QTableWidgetItem(a.get('Product', ''))
            p_item.setData(Qt.UserRole, a) 
            m_item = QTableWidgetItem(a.get('Brand', '-'))
            q_item = QTableWidgetItem(str(a.get('RawValue', '0')))
            q_item.setTextAlignment(Qt.AlignCenter)
            q_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            q_item.setForeground(QBrush(QColor("#c0392b"))) 
            
            min_val = "-"
            details = a.get('Details', '')
            if "Min:" in details:
                min_val = details.split("Min:")[1].replace(")", "").strip()
            
            s_item = QTableWidgetItem(min_val)
            s_item.setTextAlignment(Qt.AlignCenter)
            
            self.alerts_table.setItem(row_idx, 0, p_item)
            self.alerts_table.setItem(row_idx, 1, m_item)
            self.alerts_table.setItem(row_idx, 2, q_item)
            self.alerts_table.setItem(row_idx, 3, s_item)

    def on_alert_double_clicked(self, row, column):
        p_item = self.alerts_table.item(row, 0)
        if p_item:
            alert_data = p_item.data(Qt.UserRole)
            if hasattr(self.parent(), 'handle_alert_selection'):
                self.parent().handle_alert_selection(alert_data)
                self.accept()

class PurchaseOrderDialog(BaseDialog):
    def __init__(self, suppliers_list, products_list, parent=None, data=None, read_only=False):
        self.read_only = read_only
        self.suppliers = suppliers_list
        self.products = products_list
        self.data = data
        
        self.po_id = self.data.get('PO_ID') if self.data else None
        self.batches_data = [] 

        # Récupération du gestionnaire et des derniers prix enregistrés dans le stock
        self.manager = getattr(parent, 'manager', None) or getattr(parent, 'data_manager', None)
        self.latest_prices_map = {}
        if self.manager and hasattr(self.manager, 'po') and hasattr(self.manager.po, 'get_products_latest_stock_prices'):
            try:
                self.latest_prices_map = self.manager.po.get_products_latest_stock_prices()
            except Exception as e:
                import logging
                logging.error(f"Error loading latest stock prices in PurchaseOrderDialog: {e}")

        if self.read_only:
            title = f"Détails de la Commande #{self.po_id or '---'} (Lecture seule)"
        elif self.po_id:
            title = f"Modifier la Commande #{self.po_id}"
        else:
            title = "Nouvelle Commande d'Achat"

        super().__init__(title, parent)
        
        # التأكد من ظهور النافذة بحجم الشاشة بالكامل
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.setWindowState(Qt.WindowMaximized)
        self.showMaximized() 
        self.setMinimumSize(1200, 800)
        
        self.init_ui()
        
        if self.data:
            self.populate_form()
            # En mode modification, on suppose que l'en-tête est valide, donc on le verrouille
            self.validate_header(initial_load=True)
        else:
            # En mode création, on verrouille la partie détails au début
            self.toggle_inputs_state(False)
            
        if self.read_only:
            self.set_read_only_mode()

        self.editing_row = -1

    def init_ui(self):
        # استخدام التخطيط الرئيسي للنموذج الموجود في BaseDialog
        h_layout = QHBoxLayout(self.form_widget)
        h_layout.setSpacing(15)
        h_layout.setContentsMargins(10, 10, 10, 10)
        
        # --- الجانب الأيسر (النموذج الأصلي) ---
        left_widget = QWidget()
        main_layout = QVBoxLayout(left_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.addWidget(left_widget) # 100% since no right group anymore

        # === 1. Informations Générales (En-tête) ===
        top_section = QGroupBox("Informations Générales")
        top_section.setStyleSheet("""
            QGroupBox { font-weight: bold; font-size: 13px; border: 1px solid #dcdcdc; border-radius: 8px; margin-top: 10px; padding-top: 5px; }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 5px; }
        """)
        top_grid = QGridLayout(top_section)
        top_grid.setContentsMargins(15, 10, 15, 10)
        top_grid.setHorizontalSpacing(20)
        top_grid.setVerticalSpacing(8)

        # السطر الأول: Fournisseur + Notes
        top_grid.addWidget(QLabel("Fournisseur * :"), 0, 0)
        self.supplier_combo = QComboBox()
        self.supplier_combo.setMinimumHeight(38)
        for s in self.suppliers:
            self.supplier_combo.addItem(s['Supplier_Name'], s['Supplier_ID'])
        top_grid.addWidget(self.supplier_combo, 0, 1)

        top_grid.addWidget(QLabel("Notes :"), 0, 2)
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Notes générales...")
        self.notes_input.setMinimumHeight(38)
        top_grid.addWidget(self.notes_input, 0, 3)

        # السطر الثاني: التواريخ
        top_grid.addWidget(QLabel("Date Commande :"), 1, 0)
        self.order_date = QDateEdit(QDate.currentDate())
        self.order_date.setCalendarPopup(True)
        self.order_date.setMinimumHeight(38)
        top_grid.addWidget(self.order_date, 1, 1)

        top_grid.addWidget(QLabel("Livraison Prévue :"), 1, 2)
        self.delivery_date = QDateEdit(QDate.currentDate().addDays(7))
        self.delivery_date.setCalendarPopup(True)
        self.delivery_date.setMinimumHeight(38)
        top_grid.addWidget(self.delivery_date, 1, 3)

        # السطر الثالث: أزرار التحكم في الرأس (Validation / Unlock)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 10, 0, 0)
        
        self.btn_validate_header = QPushButton("Valider & Verrouiller")
        self.btn_validate_header.setCursor(Qt.PointingHandCursor)
        self.btn_validate_header.setMinimumHeight(38)
        self.btn_validate_header.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; border-radius: 4px; padding: 0 15px;")
        self.btn_validate_header.clicked.connect(self.validate_header)
        
        self.btn_unlock_header = QPushButton("✏️ Modifier l'en-tête")
        self.btn_unlock_header.setCursor(Qt.PointingHandCursor)
        self.btn_unlock_header.setMinimumHeight(38)
        self.btn_unlock_header.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; border-radius: 4px; padding: 0 15px;")
        self.btn_unlock_header.setVisible(False)
        self.btn_unlock_header.clicked.connect(self.unlock_header)

        btn_layout.addWidget(self.btn_validate_header)
        btn_layout.addWidget(self.btn_unlock_header)
        btn_layout.addStretch() # لدفع الأزرار لليسار
        
        top_grid.addLayout(btn_layout, 2, 0, 1, 4)

        main_layout.addWidget(top_section, stretch=0)

        # === 2. Section Ajout / Modification (Groupée) ===
        self.add_group = QGroupBox("Ajout d'un Article")
        self.add_group.setStyleSheet("""
            QGroupBox { font-weight: bold; font-size: 13px; border: 1px solid #dcdcdc; border-radius: 8px; margin-top: 5px; padding-top: 5px; }
        """)
        add_layout = QVBoxLayout(self.add_group)
        
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Produit :"))
        self.product_search = QLineEdit()
        self.product_search.setPlaceholderText("🔍 Rechercher un produit...")
        self.product_search.setMinimumHeight(38)
        row1.addWidget(self.product_search, stretch=4)

        row1.addWidget(QLabel("Unité :"))
        self.unit_combo = QComboBox()
        self.unit_combo.setMinimumHeight(38)
        self.unit_combo.setFixedWidth(120)
        self.unit_combo.setEnabled(False)
        row1.addWidget(self.unit_combo)

        row1.addWidget(QLabel("Qté :"))
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 99999)
        self.qty_spin.setMinimumHeight(38)
        self.qty_spin.setFixedWidth(100)
        row1.addWidget(self.qty_spin)

        row1.addWidget(QLabel("Note :"))
        self.item_note_input = QLineEdit()
        self.item_note_input.setMinimumHeight(38)
        row1.addWidget(self.item_note_input, stretch=2)

        # أزرار الإضافة والتحكم
        self.btn_show_alerts = QPushButton("⚠️ Alertes")
        self.btn_show_alerts.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; border-radius: 4px;")
        self.btn_show_alerts.setMinimumHeight(38)
        self.btn_show_alerts.setFixedWidth(100)
        row1.addWidget(self.btn_show_alerts)
        
        self.add_or_save_btn = QPushButton("➕ Ajouter")
        self.btn_edit_line = QPushButton("✏️ Modifier")
        self.btn_delete_line = QPushButton("🗑️ Supprimer")
        
        for btn in [self.add_or_save_btn, self.btn_edit_line, self.btn_delete_line]:
            btn.setMinimumHeight(38)
            btn.setFixedWidth(120)
            row1.addWidget(btn)

        add_layout.addLayout(row1)
        main_layout.addWidget(self.add_group, stretch=0)

        # === 3. Tableau des Articles (Groupé) ===
        self.table_group = QGroupBox("Liste des Articles Commandés")
        self.table_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #dcdcdc; border-radius: 8px; }")
        table_layout = QVBoxLayout(self.table_group)

        self.lines_table = QTableWidget()
        cols = ["Désignation", "Marque", "Unité", "Qté", "P.U Estimé (TTC)", "Total Estimé (TTC)", "Observation"]
        self.lines_table.setColumnCount(len(cols))
        self.lines_table.setHorizontalHeaderLabels(cols)

        header = self.lines_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)      
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Fixed)       
        header.setSectionResizeMode(3, QHeaderView.Fixed)       
        header.setSectionResizeMode(4, QHeaderView.Fixed)       
        header.setSectionResizeMode(5, QHeaderView.Fixed)       
        header.setSectionResizeMode(6, QHeaderView.Stretch)     
        
        self.lines_table.setColumnWidth(2, 100)
        self.lines_table.setColumnWidth(3, 80)
        self.lines_table.setColumnWidth(4, 130)
        self.lines_table.setColumnWidth(5, 140)

        self.lines_table.setAlternatingRowColors(True)
        self.lines_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.lines_table.setSelectionMode(QTableWidget.SingleSelection)
        
        table_layout.addWidget(self.lines_table)

        self.lbl_estimated_total = QLabel("💰 Montant Total Estimé (TTC) : ---")
        self.lbl_estimated_total.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 13px;
                color: #7f8c8d;
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 8px 15px;
            }
        """)
        self.lbl_estimated_total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        table_layout.addWidget(self.lbl_estimated_total)
        
        main_layout.addWidget(self.table_group, stretch=10) 

        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.product_search.setCompleter(self.completer)
        self.update_search_data(self.products)
        self.completer.activated.connect(self.on_completer_activated)
        
        self.btn_show_alerts.clicked.connect(self.open_alerts_dialog)
        self.add_or_save_btn.clicked.connect(self.handle_add_or_save)
        self.btn_edit_line.clicked.connect(self.edit_selected_line)
        self.btn_delete_line.clicked.connect(self.delete_selected_line)
        self.lines_table.selectionModel().selectionChanged.connect(self.update_action_buttons_state)
        
        self.update_action_buttons_state()
        
        # Modifier les boutons du bas: enlever Enregistrer/Annuler, garder seulement Fermer
        if hasattr(self, 'buttons'):
            self.buttons.clear()
            self.btn_close = QPushButton("Fermer")
            self.btn_close.clicked.connect(self.accept)
            self.buttons.addButton(self.btn_close, QDialogButtonBox.AcceptRole)

    def open_alerts_dialog(self):
        try:
            if hasattr(self.parent(), 'manager') and hasattr(self.parent().manager, 'stats'):
                all_alerts = self.parent().manager.stats.get_active_alerts()
                stock_alerts = [a for a in all_alerts if a.get('Type') == "Rupture de Stock"]
                dialog = StockAlertDialog(self, stock_alerts)
                dialog.exec()
        except Exception as e:
            import logging
            logging.error(f"Error opening alerts dialog: {e}")

    def handle_alert_selection(self, alert_data):
        """When an alert is double clicked in the dialog, pre-fill the product search box"""
        # التأكد من أن الإدخال مسموح به حالياً
        if not self.add_group.isEnabled():
            QMessageBox.information(self, "Attention", "Veuillez d'abord valider l'en-tête de la commande.")
            return
            
        product_name = alert_data.get('Product', '')
        brand_name = alert_data.get('Brand', '---')
        
        # صيغة العرض في مربع البحث هي: "Nom du produit (Marque)"
        display_name = f"{product_name} ({brand_name})"
        
        # تعبئة مربع البحث
        self.product_search.setText(display_name)
        self.on_completer_activated(display_name)
        
        # التركيز على حقل الكمية المطلوبة لتسريع العمل
        self.qty_spin.setFocus()
        self.qty_spin.selectAll()

    def load_stock_alerts(self):
        """Fetches and displays products with low stock"""
        self.alerts_table.setRowCount(0)
        try:
            # الوصول لمدير الإحصائيات عبر الـ parent 
            if hasattr(self.parent(), 'manager') and hasattr(self.parent().manager, 'stats'):
                all_alerts = self.parent().manager.stats.get_active_alerts()
                
                # تصفية تنبيهات انخفاض المخزون فقط
                stock_alerts = [a for a in all_alerts if a.get('Type') == "Rupture de Stock"]
                
                self.alerts_table.setRowCount(len(stock_alerts))
                for row_idx, a in enumerate(stock_alerts):
                    p_item = QTableWidgetItem(a.get('Product', ''))
                    p_item.setData(Qt.UserRole, a) # حفظ بيانات التنبيه كاملة في العنصر
                    
                    m_item = QTableWidgetItem(a.get('Brand', '-'))
                    q_item = QTableWidgetItem(str(a.get('RawValue', '0')))
                    q_item.setTextAlignment(Qt.AlignCenter)
                    q_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                    q_item.setForeground(QBrush(QColor("#c0392b"))) # Red color for low stock
                    
                    # استخراج الحد الأدنى من سلسلة Details: "Stock actuel: 0.0 (Min: 24)"
                    min_val = "-"
                    details = a.get('Details', '')
                    if "Min:" in details:
                        min_val = details.split("Min:")[1].replace(")", "").strip()
                    
                    s_item = QTableWidgetItem(min_val)
                    s_item.setTextAlignment(Qt.AlignCenter)
                    
                    self.alerts_table.setItem(row_idx, 0, p_item)
                    self.alerts_table.setItem(row_idx, 1, m_item)
                    self.alerts_table.setItem(row_idx, 2, q_item)
                    self.alerts_table.setItem(row_idx, 3, s_item)
                    
        except Exception as e:
            import logging
            logging.error(f"Error loading stock alerts in PO dialog: {e}")

    def on_alert_double_clicked(self, row, column):
        """When an alert is double clicked, pre-fill the product search box"""
        # التأكد من أن الإدخال مسموح به حالياً
        if not self.add_group.isEnabled():
            QMessageBox.information(self, "Attention", "Veuillez d'abord valider l'en-tête de la commande.")
            return
            
        p_item = self.alerts_table.item(row, 0)
        if p_item:
            alert_data = p_item.data(Qt.UserRole)
            product_name = alert_data.get('Product', '')
            brand_name = alert_data.get('Brand', '---')
            
            # صيغة العرض في مربع البحث هي: "Nom du produit (Marque)"
            display_name = f"{product_name} ({brand_name})"
            
            # تعبئة مربع البحث
            self.product_search.setText(display_name)
            
            # محاكاة الضغط لإظهار البيانات في الخانات الأخرى
            self.on_completer_activated(display_name)
            
            # التركيز على حقل الكمية المطلوبة لتسريع العمل
            self.order_qty_spin.setFocus()
            self.order_qty_spin.selectAll()

    def toggle_inputs_state(self, enabled):
        """Active ou désactive la zone de saisie des produits"""
        self.add_group.setEnabled(enabled)
        self.table_group.setEnabled(enabled)

    def validate_header(self, initial_load=False):
        """Valide les informations de l'en-tête et déverrouille la saisie des produits"""
        if not self.supplier_combo.currentData():
            if not initial_load:
                QMessageBox.warning(self, "Attention", "Veuillez sélectionner un fournisseur.")
            return

        header_data = {
            'Supplier_ID': self.supplier_combo.currentData(),
            'Order_Date': self.order_date.date().toString("yyyy-MM-dd"),
            'Expected_Delivery_Date': self.delivery_date.date().toString("yyyy-MM-dd"),
            'Notes': self.notes_input.text(),
        }
        
        if hasattr(self.parent(), 'manager') and not initial_load:
            po_manager = self.parent().manager.po
            if not self.po_id:
                try:
                    user_id = self.parent().manager.users.get_current_user()['User_ID']
                except:
                    user_id = 1
                header_data['Created_By'] = user_id
                
                new_id = po_manager.create_po_header(header_data)
                if not new_id:
                    QMessageBox.critical(self, "Erreur", "Impossible de créer la commande.")
                    return
                self.po_id = new_id
                self.setWindowTitle(f"Modifier la Commande #{self.po_id}")
            else:
                success = po_manager.update_po_header(self.po_id, header_data)
                if not success:
                    QMessageBox.critical(self, "Erreur", "Impossible de mettre à jour l'en-tête.")
                    return

        # Verrouiller l'en-tête
        self.supplier_combo.setEnabled(False)
        self.notes_input.setReadOnly(True)
        self.order_date.setReadOnly(True)
        self.delivery_date.setReadOnly(True)
        
        # Changer les boutons
        self.btn_validate_header.setVisible(False)
        self.btn_unlock_header.setVisible(True)
        
        # Déverrouiller la partie détails
        self.toggle_inputs_state(True)

    def unlock_header(self):
        """Déverrouille l'en-tête pour modification et verrouille la saisie des produits"""
        # Déverrouiller l'en-tête
        self.supplier_combo.setEnabled(True)
        self.notes_input.setReadOnly(False)
        self.order_date.setReadOnly(False)
        self.delivery_date.setReadOnly(False)
        
        # Changer les boutons
        self.btn_validate_header.setVisible(True)
        self.btn_unlock_header.setVisible(False)
        
        # Verrouiller la partie détails pour forcer la revalidation
        self.toggle_inputs_state(False)

    def update_search_data(self, products_list):
        self.product_data_map = {}
        suggestions = []
        for p in products_list:
            brand = p.get('Manuf_Name') or "---"
            display_name = f"{p['Product_Name']} ({brand})"
            self.product_data_map[display_name] = p
            suggestions.append(display_name)
        
        from PySide6.QtCore import QStringListModel
        self.completer.setModel(QStringListModel(suggestions))

    def handle_enter_pressed(self):
        text = self.product_search.text().strip()
        if not text:
            return
        if text in self.product_data_map:
            self.on_completer_activated(text)
        elif self.completer.completionCount() > 0:
            self.on_completer_activated(self.completer.currentCompletion())

    def on_completer_activated(self, text):
        product_data = self.product_data_map.get(text)
        if product_data:
            self.unit_combo.clear()
            # تجميع الوحدات المتاحة مع ضمان وجودها
            raw_units = [product_data.get('Ordering_Unit'), product_data.get('Stock_Unit'), product_data.get('Usage_Unit')]
            units = sorted(list(set([u for u in raw_units if u]))) # استخدام sorted لتوحيد الترتيب
            
            if not units:
                units = ['U']
                
            self.unit_combo.addItems(units)
            self.unit_combo.setCurrentIndex(0)
            self.unit_combo.setEnabled(True)
            self.qty_spin.setValue(1)
            self.item_note_input.clear()
            self.add_or_save_btn.setText("➕ Ajouter")
            self.editing_row = -1

    def handle_add_or_save(self):
        product_text = self.product_search.text().strip()
        if not product_text:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner un produit.")
            return

        product_data = self.product_data_map.get(product_text)
        if not product_data:
            QMessageBox.warning(self, "Attention", "Produit non reconnu.")
            return

        if not self.unit_combo.isEnabled() or self.unit_combo.count() == 0:
            QMessageBox.warning(self, "Attention", "Aucune unité disponible.")
            return

        qty = self.qty_spin.value()
        
        # [FIX] قراءة الوحدة الحالية والتأكد من أنها نص صالح
        unit = self.unit_combo.currentText().strip()
        note = self.item_note_input.text().strip()

        if self.editing_row == -1:
            self.add_line(product_data, qty, unit, note)
        else:
            self.update_line(self.editing_row, qty, unit, note)

        self.reset_input_fields()

    def reset_input_fields(self):
        self.product_search.clear()
        self.unit_combo.clear()
        self.unit_combo.setEnabled(False)
        self.qty_spin.setValue(1)
        self.item_note_input.clear()
        self.add_or_save_btn.setText("➕ Ajouter")
        self.editing_row = -1

    def reload_details_from_db(self):
        if not self.po_id or not hasattr(self.parent(), 'manager'):
            return
        
        full_data = self.parent().manager.po.get_full_order_details(self.po_id)
        if full_data:
            self.data = full_data
            self.lines_table.setRowCount(0)
            self.populate_form(details_only=True)

    def add_line(self, product_data, qty=1, unit='', item_note=""):
        # التحقق من التكرار
        for r in range(self.lines_table.rowCount()):
            if self.lines_table.item(r, 0) and self.lines_table.item(r, 0).data(Qt.UserRole) == product_data['Product_ID']:
                QMessageBox.information(self, "Information", "Cet article est déjà ajouté.")
                return

        final_unit_text = "U" 
        if unit and str(unit).strip():
            final_unit_text = str(unit).strip()
        elif product_data:
            final_unit_text = product_data.get('Ordering_Unit', 'U')

        if hasattr(self.parent(), 'manager') and self.po_id:
            po_manager = self.parent().manager.po
            item_data = {
                'Product_ID': product_data['Product_ID'],
                'Qty_Ordered': qty,
                'Ordering_Unit': final_unit_text,
                'Item_Note': item_note
            }
            if not po_manager.add_po_line(self.po_id, item_data):
                QMessageBox.critical(self, "Erreur", "Erreur lors de l'ajout de l'article.")
                return
            self.reload_details_from_db()
        else:
            self._add_line_to_ui(product_data, qty, final_unit_text, item_note)
            
    def recalculate_dialog_totals(self):
        total_rows = self.lines_table.rowCount()
        known_count = 0
        total_amount = 0.0
        
        for r in range(total_rows):
            p_item = self.lines_table.item(r, 0)
            if not p_item:
                continue
            has_price = bool(p_item.data(Qt.UserRole + 2))
            line_total = float(p_item.data(Qt.UserRole + 3) or 0.0)
            if has_price:
                known_count += 1
                total_amount += line_total
                
        if total_rows == 0 or known_count == 0:
            self.lbl_estimated_total.setText("💰 Montant Total Estimé (TTC) : ---")
            self.lbl_estimated_total.setStyleSheet("""
                QLabel {
                    font-weight: bold; font-size: 13px; color: #7f8c8d;
                    background-color: #f8f9fa; border: 1px solid #e0e0e0;
                    border-radius: 6px; padding: 8px 15px;
                }
            """)
            self.lbl_estimated_total.setToolTip("Aucun prix d'achat enregistré dans le stock pour les articles actuels.")
        elif known_count < total_rows:
            self.lbl_estimated_total.setText(f"💰 Montant Total Estimé (TTC) : > {format_money(total_amount, 'DA')}")
            self.lbl_estimated_total.setStyleSheet("""
                QLabel {
                    font-weight: bold; font-size: 13px; color: #d35400;
                    background-color: #fef5e7; border: 1px solid #f39c12;
                    border-radius: 6px; padding: 8px 15px;
                }
            """)
            self.lbl_estimated_total.setToolTip(f"Estimation partielle ({known_count}/{total_rows} articles ont un prix en stock). Le montant final sera supérieur.")
        else:
            self.lbl_estimated_total.setText(f"💰 Montant Total Estimé (TTC) : {format_money(total_amount, 'DA')}")
            self.lbl_estimated_total.setStyleSheet("""
                QLabel {
                    font-weight: bold; font-size: 13px; color: #27ae60;
                    background-color: #eafaf1; border: 1px solid #2ecc71;
                    border-radius: 6px; padding: 8px 15px;
                }
            """)
            self.lbl_estimated_total.setToolTip("Montant estimé calculé d'après les derniers prix d'achat enregistrés dans le stock (TVA et remises incluses).")

    def _add_line_to_ui(self, product_data, qty, final_unit_text, item_note, detail_id=None):
        row = self.lines_table.rowCount()
        self.lines_table.insertRow(row)

        product_id = product_data['Product_ID']
        name_item = QTableWidgetItem(product_data['Product_Name'])
        name_item.setData(Qt.UserRole, product_id)
        if detail_id:
            name_item.setData(Qt.UserRole + 1, detail_id) # Store Detail_ID
            
        self.lines_table.setItem(row, 0, name_item)

        brand_text = product_data.get('Manuf_Name') or "---"
        self.lines_table.setItem(row, 1, QTableWidgetItem(brand_text))
        
        self.lines_table.setItem(row, 2, QTableWidgetItem(final_unit_text))

        qty_item = QTableWidgetItem(str(qty))
        qty_item.setTextAlignment(Qt.AlignCenter)
        qty_item.setFlags(qty_item.flags() & ~Qt.ItemIsEditable)
        self.lines_table.setItem(row, 3, qty_item)

        price_info = self.latest_prices_map.get(product_id)
        has_price = False
        line_total_ttc = 0.0
        
        if price_info and price_info.get('Unit_Price_TTC', 0) > 0:
            base_pu_ttc = price_info['Unit_Price_TTC']
            from database.purchase_order_manager import PurchaseOrderManager
            factor = PurchaseOrderManager.calculate_unit_conversion_factor(
                line_unit=final_unit_text,
                ordering_unit=product_data.get('Ordering_Unit'),
                stock_unit=product_data.get('Stock_Unit'),
                stock_qty_per_order_unit=product_data.get('Stock_Qty_Per_Order_Unit'),
                usage_unit=product_data.get('Usage_Unit'),
                usage_qty_per_stock_unit=product_data.get('Usage_Qty_Per_Stock_Unit')
            )
            effective_pu_ttc = base_pu_ttc * factor
            line_total_ttc = float(qty) * effective_pu_ttc
            has_price = True
            
            pu_item = QTableWidgetItem(format_money(effective_pu_ttc, 'DA'))
            total_item = QTableWidgetItem(format_money(line_total_ttc, 'DA'))
            pu_item.setForeground(QColor("#27ae60"))
            total_item.setForeground(QColor("#27ae60"))
        else:
            pu_item = QTableWidgetItem("---")
            total_item = QTableWidgetItem("---")
            pu_item.setForeground(QColor("#7f8c8d"))
            total_item.setForeground(QColor("#7f8c8d"))

        pu_item.setTextAlignment(Qt.AlignCenter)
        total_item.setTextAlignment(Qt.AlignCenter)
        pu_item.setFlags(pu_item.flags() & ~Qt.ItemIsEditable)
        total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)

        name_item.setData(Qt.UserRole + 2, has_price)
        name_item.setData(Qt.UserRole + 3, line_total_ttc)

        self.lines_table.setItem(row, 4, pu_item)
        self.lines_table.setItem(row, 5, total_item)
        self.lines_table.setItem(row, 6, QTableWidgetItem(item_note))

        self.lines_table.scrollToBottom()
        self.update_action_buttons_state()
        self.recalculate_dialog_totals()

    def edit_selected_line(self):
        row = self.lines_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Information", "Veuillez sélectionner un article.")
            return
        self.edit_line(row)

    def delete_selected_line(self):
        row = self.lines_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Information", "Veuillez sélectionner un article.")
            return

        reply = QMessageBox.question(self, "Confirmation", "Supprimer cet article ?")
        if reply == QMessageBox.Yes:
            product_item = self.lines_table.item(row, 0)
            detail_id = product_item.data(Qt.UserRole + 1) if product_item else None
            
            if hasattr(self.parent(), 'manager') and detail_id:
                if not self.parent().manager.po.delete_po_line(detail_id):
                    QMessageBox.critical(self, "Erreur", "Erreur lors de la suppression.")
                    return
                self.reload_details_from_db()
            else:
                self.lines_table.removeRow(row)
                
            self.update_action_buttons_state()
            self.recalculate_dialog_totals()
            if self.editing_row == row:
                self.reset_input_fields()

    def edit_line(self, row):
        product_item = self.lines_table.item(row, 0)
        if not product_item:
            return

        product_id = product_item.data(Qt.UserRole)
        product_data = next((p for p in self.products if p['Product_ID'] == product_id), None)
        if not product_data:
            return

        brand = product_data.get('Manuf_Name') or "---"
        self.product_search.setText(f"{product_data['Product_Name']} ({brand})")

        self.unit_combo.clear()
        raw_units = [product_data.get('Ordering_Unit'), product_data.get('Stock_Unit'), product_data.get('Usage_Unit')]
        units = sorted(list(set([u for u in raw_units if u])))
        if not units: units = ['U']
        self.unit_combo.addItems(units)
        
        # استرجاع الوحدة الحالية من الجدول
        current_unit = self.lines_table.item(row, 2).text()
        if current_unit:
            if self.unit_combo.findText(current_unit) == -1:
                self.unit_combo.addItem(current_unit)
            self.unit_combo.setCurrentText(current_unit)
            
        self.unit_combo.setEnabled(True)

        self.qty_spin.setValue(int(self.lines_table.item(row, 3).text() or 1))
        self.item_note_input.setText(self.lines_table.item(row, 6).text() or "")

        self.add_or_save_btn.setText("💾 Enregistrer")
        self.editing_row = row

    def update_line(self, row, qty, unit, note):
        product_item = self.lines_table.item(row, 0)
        detail_id = product_item.data(Qt.UserRole + 1) if product_item else None
        
        if hasattr(self.parent(), 'manager') and detail_id:
            po_manager = self.parent().manager.po
            item_data = {
                'Qty_Ordered': qty,
                'Ordering_Unit': unit,
                'Item_Note': note
            }
            if not po_manager.update_po_line(detail_id, item_data):
                QMessageBox.critical(self, "Erreur", "Erreur lors de la mise à jour.")
                return
            self.reload_details_from_db()
        else:
            product_id = product_item.data(Qt.UserRole)
            product_data = next((p for p in self.products if p['Product_ID'] == product_id), {})

            self.lines_table.item(row, 2).setText(str(unit).strip())
            self.lines_table.item(row, 3).setText(str(qty))
            
            price_info = self.latest_prices_map.get(product_id)
            has_price = False
            line_total_ttc = 0.0
            
            if price_info and price_info.get('Unit_Price_TTC', 0) > 0:
                base_pu_ttc = price_info['Unit_Price_TTC']
                from database.purchase_order_manager import PurchaseOrderManager
                factor = PurchaseOrderManager.calculate_unit_conversion_factor(
                    line_unit=unit,
                    ordering_unit=product_data.get('Ordering_Unit'),
                    stock_unit=product_data.get('Stock_Unit'),
                    stock_qty_per_order_unit=product_data.get('Stock_Qty_Per_Order_Unit'),
                    usage_unit=product_data.get('Usage_Unit'),
                    usage_qty_per_stock_unit=product_data.get('Usage_Qty_Per_Stock_Unit')
                )
                effective_pu_ttc = base_pu_ttc * factor
                line_total_ttc = float(qty) * effective_pu_ttc
                has_price = True
                
                self.lines_table.item(row, 4).setText(format_money(effective_pu_ttc, 'DA'))
                self.lines_table.item(row, 5).setText(format_money(line_total_ttc, 'DA'))
                self.lines_table.item(row, 4).setForeground(QColor("#27ae60"))
                self.lines_table.item(row, 5).setForeground(QColor("#27ae60"))
            else:
                self.lines_table.item(row, 4).setText("---")
                self.lines_table.item(row, 5).setText("---")
                self.lines_table.item(row, 4).setForeground(QColor("#7f8c8d"))
                self.lines_table.item(row, 5).setForeground(QColor("#7f8c8d"))
                
            product_item.setData(Qt.UserRole + 2, has_price)
            product_item.setData(Qt.UserRole + 3, line_total_ttc)
            self.lines_table.item(row, 6).setText(note)
            self.recalculate_dialog_totals()

    def update_action_buttons_state(self):
        has_selection = self.lines_table.currentRow() >= 0
        self.btn_edit_line.setEnabled(has_selection)
        self.btn_delete_line.setEnabled(has_selection)

    def set_read_only_mode(self):
        self.supplier_combo.setEnabled(False)
        self.order_date.setReadOnly(True)
        self.delivery_date.setReadOnly(True)
        self.notes_input.setReadOnly(True)
        
        # Masquer les boutons de validation/modification en lecture seule
        self.btn_validate_header.setVisible(False)
        self.btn_unlock_header.setVisible(False)
        
        self.product_search.setEnabled(False)
        self.unit_combo.setEnabled(False)
        self.qty_spin.setEnabled(False)
        self.item_note_input.setEnabled(False)
        self.add_or_save_btn.setEnabled(False)
        self.btn_edit_line.setEnabled(False)
        self.btn_delete_line.setEnabled(False)
        self.lines_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        save_btn = self.buttons.button(QDialogButtonBox.Save)
        if save_btn: save_btn.setVisible(False)
        cancel_btn = self.buttons.button(QDialogButtonBox.Cancel)
        if cancel_btn: cancel_btn.setText("Fermer")

    def populate_form(self, details_only=False):
        if not self.data: return
        
        if not details_only:
            idx = self.supplier_combo.findData(self.data.get('Supplier_ID'))
            if idx >= 0: self.supplier_combo.setCurrentIndex(idx)
            
            if self.data.get('Order_Date'):
                self.order_date.setDate(QDate.fromString(str(self.data['Order_Date']), "yyyy-MM-dd"))
            if self.data.get('Expected_Delivery_Date'):
                self.delivery_date.setDate(QDate.fromString(str(self.data['Expected_Delivery_Date']), "yyyy-MM-dd"))
            
            self.notes_input.setText(self.data.get('Notes', ''))
        
        for item in self.data.get('Details', []):
            prod_id = item.get('Product_ID')
            full_prod = next((p for p in self.products if p['Product_ID'] == prod_id), None)
            if full_prod:
                self._add_line_to_ui(
                    full_prod,
                    item.get('Qty_Ordered', 1),
                    item.get('Ordering_Unit', full_prod.get('Ordering_Unit', 'U')),
                    item.get('Item_Note', ""),
                    item.get('ID')  # Pass detail_id
                )
        self.recalculate_dialog_totals()

    def accept(self):
        super().accept()