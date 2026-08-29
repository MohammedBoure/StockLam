# ui/widgets/master_data/dialogs.py

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QGroupBox, QScrollArea,QLabel,QHBoxLayout,
                               QLineEdit, QComboBox, QDialogButtonBox, QDateEdit, QMessageBox, QGridLayout,
                               QTabWidget, QWidget, QCheckBox, QSpinBox, QDoubleSpinBox, QFrame)
from PySide6.QtCore import QDate, Qt, QEvent, QTimer
from PySide6.QtGui import QGuiApplication
import logging
from ui.formatting import format_money

class BaseDialog(QDialog):
    """Fenêtre de dialogue de base unifiée"""
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.layout = QVBoxLayout(self)
        self.form_widget = QWidget()
        self.layout.addWidget(self.form_widget)
        
        # Boutons Enregistrer et Annuler (traduits une seule fois ici)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

        # Traduction centralisée des boutons
        save_btn = self.buttons.button(QDialogButtonBox.Save)
        if save_btn:
            save_btn.setText("Enregistrer")
        cancel_btn = self.buttons.button(QDialogButtonBox.Cancel)
        if cancel_btn:
            cancel_btn.setText("Annuler")

    def make_combo_searchable(self, combo):
        """Rendre un QComboBox filtrable par recherche"""
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.completer().setFilterMode(Qt.MatchContains)
        combo.completer().setCaseSensitivity(Qt.CaseInsensitive)


# ---------------------------------------------------------
# Location Type Input Dialog
# ---------------------------------------------------------
class LocationTypeInputDialog(BaseDialog):
    def __init__(self, parent=None, data=None):
        super().__init__("Type d'Emplacement", parent)
        self.resize(350, 150)
        self.data = data
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self.form_widget)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ex : Étage, Armoire, Tiroir...")
        
        layout.addRow("Nom du Type * :", self.name_input)

        if self.data:
            self.name_input.setText(self.data.get('Type_Name', ''))

    def get_data(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Erreur", "Le nom du type est obligatoire.")
            return None
        return {"Type_Name": name}



class ProductDialog(BaseDialog):
    def __init__(self, manufacturers, automates, families, packaging_units, parent=None, data=None):
        super().__init__("Données du Produit (Product Master)", parent)
        
        self.manufacturers = manufacturers
        self.automates = automates
        self.families = families
        self.packaging_units = packaging_units
        self.data = data

        self.adjust_dialog_size()
        self.init_ui()
        self._apply_auto_select_to_all_inputs()

    def adjust_dialog_size(self):
        screen_geo = QGuiApplication.primaryScreen().availableGeometry()
        width = min(1100, int(screen_geo.width() * 0.7))
        height = min(950, int(screen_geo.height() * 0.85))
        self.setMinimumSize(900, 700)
        self.resize(width, height)

    def init_ui(self):
        # استخدام تخطيط BaseDialog الموجود
        outer_layout = QVBoxLayout(self.form_widget)
        outer_layout.setContentsMargins(5, 5, 5, 5)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        container = QWidget()
        main_grid = QGridLayout(container)
        main_grid.setSpacing(25)
        main_grid.setContentsMargins(25, 25, 25, 25)

        # ---------------------------------------------------------
        # Groupe 1 : Informations de Base
        # ---------------------------------------------------------
        basic_group = QGroupBox("Informations de Base")
        basic_layout = QFormLayout(basic_group)
        basic_layout.setSpacing(15)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Nom du produit (obligatoire)")
        
        self.family_combo = QComboBox()
        self.manuf_combo = QComboBox()
        
        # --- إضافة Checkbox لـ Is_Billable ---
        self.is_billable_cb = QCheckBox("Ce produit est facturable ?")
        self.is_billable_cb.setToolTip("Cochez si ce produit est facturé au patient/client.")
        
        basic_layout.addRow("Nom du Produit * :", self.name_input)
        basic_layout.addRow("Famille * :", self.family_combo)
        basic_layout.addRow("Marque * :", self.manuf_combo)
        basic_layout.addRow("Facturation :", self.is_billable_cb) # الحقل الجديد

        # ---------------------------------------------------------
        # Groupe 2 : Gestion des Unités & Conversion
        # ---------------------------------------------------------
        units_group = QGroupBox("Gestion des Unités & Conversion")
        units_layout = QFormLayout(units_group)
        units_layout.setSpacing(15)

        self.order_unit_combo = QComboBox()
        self.stock_unit_combo = QComboBox()
        
        self.stock_qty_spin = QSpinBox()
        self.stock_qty_spin.setRange(1, 100000)
        
        self.usage_unit_combo = QComboBox()
        
        # --- تعديل: استخدام QSpinBox (Int) بدلاً من QDoubleSpinBox ---
        self.usage_qty_spin = QSpinBox() 
        self.usage_qty_spin.setRange(1, 100000) # منع الصفر
        self.usage_qty_spin.setSuffix(" (Tests/Unités)")

        units_layout.addRow("Unité de Commande :", self.order_unit_combo)
        units_layout.addRow("Unité de Stockage :", self.stock_unit_combo)
        units_layout.addRow("→ Qté Stock / Commande :", self.stock_qty_spin)
        units_layout.addRow("Unité d'Usage :", self.usage_unit_combo)
        units_layout.addRow("→ Qté Usage / Stockage :", self.usage_qty_spin)

        # ---------------------------------------------------------
        # Groupe 3 : Stockage & Alertes
        # ---------------------------------------------------------
        storage_group = QGroupBox("Stockage & Alertes")
        storage_layout = QFormLayout(storage_group)
        storage_layout.setSpacing(15)

        self.min_stock_spin = QSpinBox()
        self.min_stock_spin.setRange(0, 10000)
        
        self.alert_days_spin = QSpinBox()
        self.alert_days_spin.setRange(1, 3650)
        
        # --- تعديل: استخدام ComboBox لدرجة الحرارة ---
        self.temp_req_combo = QComboBox()
        self.temp_req_combo.addItems(["Sec", "Frigo", "Congélateur"])
        
        self.auto_combo = QComboBox()
        
        # --- إضافة Checkbox لـ Show_In_Alerts ---
        self.show_alerts_cb = QCheckBox("Afficher dans les alertes")
        self.show_alerts_cb.setToolTip("Cochez pour afficher les alertes de péremption et de rupture pour ce produit.")

        storage_layout.addRow("Stock Minimum :", self.min_stock_spin)
        storage_layout.addRow("Alerte Expiration (Jours) :", self.alert_days_spin)
        storage_layout.addRow("Conditions Température :", self.temp_req_combo)
        storage_layout.addRow("Automate Préféré :", self.auto_combo)
        storage_layout.addRow("Alertes :", self.show_alerts_cb)

        # إضافة المجموعات للشبكة الرئيسية
        main_grid.addWidget(basic_group, 0, 0)
        main_grid.addWidget(units_group, 1, 0)
        main_grid.addWidget(storage_group, 0, 1, 2, 1)

        # Uniformisation de la hauteur des champs
        for widget in container.findChildren(QWidget):
            if isinstance(widget, (QLineEdit, QSpinBox)):
                widget.setMinimumHeight(40)
                # محاذاة النص والـ SpinBox
                if isinstance(widget, QLineEdit):
                    widget.setAlignment(Qt.AlignLeading | Qt.AlignVCenter)
                
                widget.setStyleSheet("""
                    QLineEdit, QSpinBox {
                        padding-top: 0px;
                        padding-bottom: 0px;
                        margin: 0px;
                    }
                """)
            
            elif isinstance(widget, QComboBox):
                widget.setMinimumHeight(40)
                if widget.isEditable():
                    widget.lineEdit().setAlignment(Qt.AlignLeading | Qt.AlignVCenter)
                    widget.lineEdit().setStyleSheet("padding-top: 0px; padding-bottom: 0px;")

        self._initialize_combos_data()
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

        if self.data:
            self.populate_data()

    def _apply_auto_select_to_all_inputs(self):
        for widget in self.findChildren(QWidget):
            target = None
            if isinstance(widget, QLineEdit):
                target = widget
            elif isinstance(widget, (QSpinBox, QComboBox)):
                if hasattr(widget, 'lineEdit') and widget.lineEdit():
                    target = widget.lineEdit()
            if target:
                target.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.FocusIn:
            QTimer.singleShot(0, obj.selectAll)
        return super().eventFilter(obj, event)

    def _initialize_combos_data(self):
        self._setup_filterable_combo(self.family_combo, self.families, 'Family_Name', 'Family_ID')
        self._setup_filterable_combo(self.manuf_combo, self.manufacturers, 'Manuf_Name', 'Manuf_ID')
        self._setup_filterable_combo(self.auto_combo, self.automates, 'Automate_Name', 'Automate_ID')

        unit_names = [u.get('Unit_Name') for u in self.packaging_units] or ["Carton", "Boîte", "Kit", "Test", "Flacon"]
        for combo in [self.order_unit_combo, self.stock_unit_combo, self.usage_unit_combo]:
            combo.addItems(unit_names)
            combo.setEditable(True)

    def _setup_filterable_combo(self, combo, items_list, name_key, id_key):
        combo.clear()
        combo.addItem("", None)
        for item in items_list:
            combo.addItem(item.get(name_key), item.get(id_key))
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.lineEdit().textEdited.connect(lambda text: self._filter_combo(combo, items_list, name_key, id_key, text))

    def _filter_combo(self, combo, items_list, name_key, id_key, text):
        combo.blockSignals(True)
        current_text = combo.lineEdit().text()
        combo.clear()
        combo.addItem("", None)
        text_lower = text.lower()
        for item in items_list:
            if text_lower in item.get(name_key, '').lower():
                combo.addItem(item.get(name_key), item.get(id_key))
        combo.lineEdit().setText(current_text)
        combo.blockSignals(False)

    def populate_data(self):
        """تعبئة البيانات عند التعديل"""
        d = self.data
        self.name_input.setText(d.get('Product_Name', ''))
        
        # تعبئة القوائم المنسدلة المرتبطة بـ ID
        for combo, key in [(self.family_combo, 'Family_ID'), (self.manuf_combo, 'Manuf_ID'), (self.auto_combo, 'Preferred_Automate_ID')]:
            idx = combo.findData(d.get(key))
            if idx >= 0:
                combo.setCurrentIndex(idx)

        # تعيين حالة Checkbox (Is_Billable)
        self.is_billable_cb.setChecked(bool(d.get('Is_Billable', False)))

        # تعيين الوحدات
        self.order_unit_combo.setCurrentText(str(d.get('Ordering_Unit', '')))
        self.stock_unit_combo.setCurrentText(str(d.get('Stock_Unit', '')))
        self.stock_qty_spin.setValue(int(d.get('Stock_Qty_Per_Order_Unit', 1)))
        
        self.usage_unit_combo.setCurrentText(str(d.get('Usage_Unit', '')))
        
        # --- تعديل: تعيين القيمة كعدد صحيح ---
        # حتى لو كانت القيمة في الداتابيس decimal، نحولها لـ float ثم int للعرض في SpinBox
        try:
            val = int(float(d.get('Usage_Qty_Per_Stock_Unit', 1)))
            self.usage_qty_spin.setValue(val)
        except (ValueError, TypeError):
            self.usage_qty_spin.setValue(1)
        
        self.min_stock_spin.setValue(int(d.get('Minimum_Stock_Level', 5)))
        self.alert_days_spin.setValue(int(d.get('Alert_Before_Expiry_Days', 30)))
        
        self.show_alerts_cb.setChecked(bool(d.get('Show_In_Alerts', False)))
        
        # --- تعديل: اختيار النص المطابق لدرجة الحرارة ---
        temp_val = str(d.get('Storage_Temp_Req', 'Sec'))
        idx = self.temp_req_combo.findText(temp_val, Qt.MatchContains)
        if idx >= 0:
            self.temp_req_combo.setCurrentIndex(idx)
        else:
            self.temp_req_combo.setCurrentIndex(0) # الافتراضي Sec

    def get_data(self):
        """استرجاع البيانات من الواجهة لإرسالها للداتابيس"""
        product_name = self.name_input.text().strip()
        if not product_name:
            QMessageBox.warning(self, "Erreur", "Le nom du produit est obligatoire.")
            return None
            
        return {
            "Product_Name": product_name,
            "Family_ID": self.family_combo.currentData(),
            "Manuf_ID": self.manuf_combo.currentData(),
            "Is_Billable": self.is_billable_cb.isChecked(),  # الحقل الجديد
            "Show_In_Alerts": self.show_alerts_cb.isChecked(),
            
            "Ordering_Unit": self.order_unit_combo.currentText().strip(),
            "Stock_Unit": self.stock_unit_combo.currentText().strip(),
            "Stock_Qty_Per_Order_Unit": self.stock_qty_spin.value(),
            
            "Usage_Unit": self.usage_unit_combo.currentText().strip(),
            "Usage_Qty_Per_Stock_Unit": self.usage_qty_spin.value(), # يعود كـ int
            
            "Minimum_Stock_Level": self.min_stock_spin.value(),
            "Alert_Before_Expiry_Days": self.alert_days_spin.value(),
            
            "Storage_Temp_Req": self.temp_req_combo.currentText(), # يعود كنص (Sec, Frigo...)
            "Preferred_Automate_ID": self.auto_combo.currentData()
        }
# ---------------------------------------------------------
# 2. Manufacturer Dialog
# ---------------------------------------------------------
class ManufacturerDialog(BaseDialog):
    def __init__(self, parent=None, data=None):
        super().__init__("Données de la Marque", parent)
        self.data = data
        self.init_ui()

    def init_ui(self):
        outer_layout = QVBoxLayout(self.form_widget)
        outer_layout.setContentsMargins(5, 5, 5, 5)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        container = QWidget()
        main_grid = QGridLayout(container)
        main_grid.setSpacing(20)
        main_grid.setContentsMargins(20, 20, 20, 20)

        # Informations de Base
        basic_group = QGroupBox("Informations de Base")
        basic_layout = QFormLayout(basic_group)
        basic_layout.setSpacing(12)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Nom de la marque (obligatoire)")
        self.country_input = QLineEdit()
        self.website_input = QLineEdit()
        
        basic_layout.addRow("Nom de la Marque * :", self.name_input)
        basic_layout.addRow("Pays d'Origine :", self.country_input)
        basic_layout.addRow("Site Web :", self.website_input)

        main_grid.addWidget(basic_group, 0, 0, 1, 2)

        # Uniformisation de la hauteur
        for widget in container.findChildren(QWidget):
            if isinstance(widget, (QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox)):
                widget.setMinimumHeight(38)

        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

        if self.data:
            self.name_input.setText(self.data.get('Manuf_Name', ''))
            self.country_input.setText(self.data.get('Country_of_Origin', ''))
            self.website_input.setText(self.data.get('Website', ''))

    def get_data(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Erreur", "Le nom de la marque est obligatoire.")
            return None
        return {
            "Manuf_Name": name,
            "Country_of_Origin": self.country_input.text().strip() or None,
            "Website": self.website_input.text().strip() or None
        }


# ---------------------------------------------------------
# 3. Supplier Dialog
# ---------------------------------------------------------
class SupplierDialog(BaseDialog):
    """
    Dialog pour Ajouter/Modifier un fournisseur.
    Affiche TOUTES les informations sur une seule page bien organisée, sans onglets.
    """
    def __init__(self, parent=None, data=None):
        self.data = data
        title = "Modifier le Fournisseur" if self.data else "Nouveau Fournisseur"
        super().__init__(title, parent)
        
        # حجم مناسب لاستيعاب كافة الحقول براحة
        self.resize(1000, 600) 
        self.init_ui()
        
        if self.data:
            self.populate_form()

    def init_ui(self):
        main_layout = QVBoxLayout(self.form_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # ---------------------------------------------------------
        # ZONE 1: Général & Fiscalité (المنطقة العلوية)
        # ---------------------------------------------------------
        row1_layout = QHBoxLayout()
        
        # --- Groupe: Général ---
        grp_gen = self._create_group("Informations Générales", "#2c3e50")
        grid_gen = QGridLayout(grp_gen)
        
        self.inp_name = QLineEdit()
        self.inp_contact = QLineEdit()
        
        grid_gen.addWidget(QLabel("Nom Fournisseur * :"), 0, 0)
        grid_gen.addWidget(self.inp_name, 0, 1)
        grid_gen.addWidget(QLabel("Responsable :"), 1, 0)
        grid_gen.addWidget(self.inp_contact, 1, 1)
        
        row1_layout.addWidget(grp_gen, stretch=1)

        # --- Groupe: Fiscalité ---
        grp_fisc = self._create_group("Fiscalité", "#8e44ad")
        grid_fisc = QGridLayout(grp_fisc)
        
        self.inp_tax_id = QLineEdit()
        self.inp_rc = QLineEdit()
        
        grid_fisc.addWidget(QLabel("NIF (Matricule) :"), 0, 0)
        grid_fisc.addWidget(self.inp_tax_id, 0, 1)
        grid_fisc.addWidget(QLabel("Reg. Commerce :"), 1, 0)
        grid_fisc.addWidget(self.inp_rc, 1, 1)
        
        row1_layout.addWidget(grp_fisc, stretch=1)
        main_layout.addLayout(row1_layout)

        # ---------------------------------------------------------
        # ZONE 2: Contact & Adresse (المنطقة الوسطى)
        # ---------------------------------------------------------
        row2_layout = QHBoxLayout()

        # --- Groupe: Contact ---
        grp_contact = self._create_group("Coordonnées", "#2980b9")
        grid_contact = QGridLayout(grp_contact)
        
        self.inp_phone = QLineEdit()
        self.inp_email = QLineEdit()
        self.inp_website = QLineEdit()

        grid_contact.addWidget(QLabel("Téléphone :"), 0, 0)
        grid_contact.addWidget(self.inp_phone, 0, 1)
        grid_contact.addWidget(QLabel("Email :"), 1, 0)
        grid_contact.addWidget(self.inp_email, 1, 1)
        grid_contact.addWidget(QLabel("Site Web :"), 2, 0)
        grid_contact.addWidget(self.inp_website, 2, 1)

        row2_layout.addWidget(grp_contact, stretch=1)

        # --- Groupe: Adresse ---
        grp_address = self._create_group("Localisation", "#27ae60")
        grid_addr = QGridLayout(grp_address)
        
        self.inp_addr1 = QLineEdit()
        self.inp_addr2 = QLineEdit()
        self.inp_city = QLineEdit()
        self.inp_postal = QLineEdit()

        grid_addr.addWidget(QLabel("Adresse (Ligne 1) :"), 0, 0)
        grid_addr.addWidget(self.inp_addr1, 0, 1, 1, 3)
        grid_addr.addWidget(QLabel("Adresse (Ligne 2) :"), 1, 0)
        grid_addr.addWidget(self.inp_addr2, 1, 1, 1, 3)
        grid_addr.addWidget(QLabel("Ville :"), 2, 0)
        grid_addr.addWidget(self.inp_city, 2, 1)
        grid_addr.addWidget(QLabel("Code Postal :"), 2, 2)
        grid_addr.addWidget(self.inp_postal, 2, 3)

        row2_layout.addWidget(grp_address, stretch=1)
        main_layout.addLayout(row2_layout)

        # ---------------------------------------------------------
        # ZONE 3: Banque (المنطقة السفلية)
        # ---------------------------------------------------------
        grp_bank = self._create_group("Informations Bancaires", "#c0392b")
        hbox_bank = QHBoxLayout(grp_bank)
        
        self.inp_bank_name = QLineEdit()
        self.inp_iban = QLineEdit()
        
        hbox_bank.addWidget(QLabel("Nom Banque :"))
        hbox_bank.addWidget(self.inp_bank_name, 1)
        hbox_bank.addWidget(QLabel("RIB / IBAN :"))
        hbox_bank.addWidget(self.inp_iban, 2)
        
        main_layout.addWidget(grp_bank)
        
        # دفع جميع العناصر للأعلى لتجنب التمدد العشوائي
        main_layout.addStretch()

    def _create_group(self, title, color):
        """دالة مساعدة لإنشاء QGroupBox بتنسيق موحد"""
        gb = QGroupBox(title)
        gb.setStyleSheet(f"""
            QGroupBox {{ 
                font-weight: bold; border: 1px solid #bdc3c7; 
                border-radius: 6px; margin-top: 10px; padding-top: 12px; 
            }}
            QGroupBox::title {{ 
                subcontrol-origin: margin; left: 10px; padding: 0 5px; color: {color}; 
            }}
        """)
        return gb

    def populate_form(self):
        """تعبئة الحقول بالبيانات في حالة التعديل"""
        d = self.data
        if not d: return

        self.inp_name.setText(d.get('Supplier_Name') or "")
        self.inp_contact.setText(d.get('Contact_Person') or "")
        self.inp_phone.setText(d.get('Phone') or "")
        self.inp_email.setText(d.get('Email') or "")
        self.inp_website.setText(d.get('Website') or "")
        
        self.inp_addr1.setText(d.get('Address_Line1') or "")
        self.inp_addr2.setText(d.get('Address_Line2') or "")
        self.inp_city.setText(d.get('City') or "")
        self.inp_postal.setText(str(d.get('Postal_Code') or ""))
        
        self.inp_tax_id.setText(str(d.get('Tax_ID_Number') or ""))
        self.inp_rc.setText(str(d.get('Commercial_Reg_No') or ""))
        
        self.inp_bank_name.setText(d.get('Bank_Name') or "")
        self.inp_iban.setText(d.get('Bank_Account_IBAN') or "")

    def get_data(self):
        """تجهيز البيانات للإرسال إلى قاعدة البيانات"""
        name = self.inp_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Erreur", "Le nom du fournisseur est obligatoire.")
            return None

        # تحويل النصوص الفارغة إلى None
        def val(txt): return txt.strip() if txt.strip() else None

        return {
            "Supplier_Name": name,
            "Contact_Person": val(self.inp_contact.text()),
            "Phone": val(self.inp_phone.text()),
            "Email": val(self.inp_email.text()),
            "Website": val(self.inp_website.text()),
            
            "Address_Line1": val(self.inp_addr1.text()),
            "Address_Line2": val(self.inp_addr2.text()),
            "City": val(self.inp_city.text()),
            "Postal_Code": val(self.inp_postal.text()),
            
            "Tax_ID_Number": val(self.inp_tax_id.text()),
            "Commercial_Reg_No": val(self.inp_rc.text()),
            
            "Bank_Name": val(self.inp_bank_name.text()),
            "Bank_Account_IBAN": val(self.inp_iban.text())
        }

# ---------------------------------------------------------
# 4. Automate Dialog
# ---------------------------------------------------------
class AutomateDialog(BaseDialog):
    def __init__(self, locations_list, parent=None, data=None):
        super().__init__("Données de l'Automate", parent)
        self.locations_list = locations_list
        self.data = data
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self.form_widget)
        
        self.name_input = QLineEdit()
        self.model_input = QLineEdit()
        self.serial_input = QLineEdit()
        self.purchase_date = QDateEdit()
        self.purchase_date.setDisplayFormat("yyyy-MM-dd")
        self.purchase_date.setCalendarPopup(True)
        self.purchase_date.setDate(QDate.currentDate())
        
        self.location_combo = QComboBox()
        self.make_combo_searchable(self.location_combo)
        
        self.location_combo.addItem("--- Sans Emplacement ---", None)
        for loc in self.locations_list:
            self.location_combo.addItem(loc.get('Location_Name', 'Inconnu'), loc.get('Location_ID'))

        layout.addRow("Nom de l'Automate * :", self.name_input)
        layout.addRow("Modèle :", self.model_input)
        layout.addRow("Numéro de Série :", self.serial_input)
        layout.addRow("Date d'Achat :", self.purchase_date)
        layout.addRow("Emplacement Actuel (recherche) :", self.location_combo)

        if self.data:
            self.name_input.setText(self.data.get('Automate_Name', ''))
            self.model_input.setText(self.data.get('Model_Number', ''))
            self.serial_input.setText(self.data.get('Serial_Number', ''))
            
            d = self.data.get('Date_of_Purchase')
            if d:
                try:
                    date_obj = QDate.fromString(str(d)[:10], "yyyy-MM-dd")
                    self.purchase_date.setDate(date_obj)
                except:
                    pass

            loc_id = self.data.get('Location_ID')
            if loc_id:
                idx = self.location_combo.findData(loc_id)
                if idx >= 0:
                    self.location_combo.setCurrentIndex(idx)

    def get_data(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Erreur", "Le nom de l'automate est obligatoire.")
            return None
        return {
            "Automate_Name": name,
            "Model_Number": self.model_input.text().strip() or None,
            "Serial_Number": self.serial_input.text().strip() or None,
            "Date_of_Purchase": self.purchase_date.date().toString("yyyy-MM-dd"),
            "Location_ID": self.location_combo.currentData()
        }


# ---------------------------------------------------------
# 5. Location Dialog
# ---------------------------------------------------------
class LocationDialog(BaseDialog):
    def __init__(self, location_types, parent=None, data=None, parent_name=None):
        title = "Nouvel Emplacement"
        if data:
            title = "Modifier l'Emplacement"
        elif parent_name:
            title = f"Ajouter sous : {parent_name}"
            
        super().__init__(title, parent)
        self.resize(450, 250)
        self.data = data
        self.location_types = location_types
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self.form_widget)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ex : Labo Chimie, Étagère A...")
        
        self.type_combo = QComboBox()
        self.type_combo.addItem("--- Sélectionner Type ---", None)
        for t in self.location_types:
            self.type_combo.addItem(t['Type_Name'], t['Type_ID'])
            
        # الحل: ربط النص الفرنسي بالقيمة الإنجليزية التي تقبلها قاعدة البيانات
        self.zone_combo = QComboBox()
        self.zone_combo.addItem("Température Ambiante", "Room Temp")
        self.zone_combo.addItem("Réfrigéré (2-8°C)", "Refrigerated 2-8")
        self.zone_combo.addItem("Congelé (-20°C)", "Frozen -20")
        self.zone_combo.addItem("Congélation Profonde (-80°C)", "Deep Freeze -80")
        
        layout.addRow("Nom de l'Emplacement * :", self.name_input)
        layout.addRow("Type d'Emplacement * :", self.type_combo)
        layout.addRow("Condition de Température :", self.zone_combo)

        if self.data:
            self.name_input.setText(self.data.get('Location_Name', ''))
            
            # البحث عن القيمة الإنجليزية المخزنة وتحديد النص الفرنسي المقابل لها
            current_zone = self.data.get('Temperature_Zone', 'Room Temp')
            idx_zone = self.zone_combo.findData(current_zone)
            if idx_zone >= 0:
                self.zone_combo.setCurrentIndex(idx_zone)
            
            current_type_id = self.data.get('Type_ID')
            if current_type_id:
                idx_type = self.type_combo.findData(current_type_id)
                if idx_type >= 0:
                    self.type_combo.setCurrentIndex(idx_type)

    def get_data(self):
        name = self.name_input.text().strip()
        type_id = self.type_combo.currentData()
        # سحب القيمة الإنجليزية (Data) وليس النص الفرنسي (Text)
        zone_db_value = self.zone_combo.currentData()
        
        if not name:
            QMessageBox.warning(self, "Erreur", "Le nom de l'emplacement est obligatoire.")
            return None
        
        if not type_id:
            QMessageBox.warning(self, "Erreur", "Le type d'emplacement est obligatoire.")
            return None

        return {
            "Location_Name": name,
            "Type_ID": type_id,
            "Temperature_Zone": zone_db_value # القيمة التي ستذهب لقاعدة البيانات
        }


# ---------------------------------------------------------
# 6. Waste Reason Dialog
# ---------------------------------------------------------
class WasteReasonDialog(BaseDialog):
    def __init__(self, parent=None, data=None):
        super().__init__("Raison de Mise au Rebut", parent)
        self.data = data
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self.form_widget)
        self.reason_input = QLineEdit()
        self.is_active_chk = QCheckBox("Actif")
        self.is_active_chk.setChecked(True)

        layout.addRow("Raison * :", self.reason_input)
        layout.addRow("", self.is_active_chk)

        if self.data:
            self.reason_input.setText(self.data.get('Reason_Name', ''))
            self.is_active_chk.setChecked(bool(self.data.get('Is_Active', True)))

    def get_data(self):
        reason = self.reason_input.text().strip()
        if not reason:
            QMessageBox.warning(self, "Erreur", "La raison est obligatoire.")
            return None
        return {
            "Reason_Name": reason,
            "Is_Active": self.is_active_chk.isChecked()
        }


# ---------------------------------------------------------
# 7. Product Family Dialog
# ---------------------------------------------------------
class ProductFamilyDialog(BaseDialog):
    def __init__(self, parent=None, data=None):
        super().__init__("Famille de Produit", parent)
        self.data = data
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self.form_widget)
        self.name_input = QLineEdit()
        self.desc_input = QLineEdit()
        
        layout.addRow("Nom de la Famille * :", self.name_input)
        layout.addRow("Description :", self.desc_input)

        if self.data:
            self.name_input.setText(self.data.get('Family_Name', ''))
            self.desc_input.setText(self.data.get('Description', ''))

    def get_data(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Erreur", "Le nom de la famille est obligatoire.")
            return None
        return {
            "Family_Name": name,
            "Description": self.desc_input.text().strip() or None
        }


# ---------------------------------------------------------
# 8. Packaging Unit Dialog
# ---------------------------------------------------------
class PackagingUnitDialog(BaseDialog):
    def __init__(self, parent=None, data=None):
        super().__init__("Unité de Conditionnement", parent)
        self.data = data
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self.form_widget)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ex : Carton, Boîte, Kit...")
        self.desc_input = QLineEdit()
        
        layout.addRow("Nom de l'Unité * :", self.name_input)
        layout.addRow("Description :", self.desc_input)

        if self.data:
            self.name_input.setText(self.data.get('Unit_Name', ''))
            self.desc_input.setText(self.data.get('Description', ''))

    def get_data(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Erreur", "Le nom de l'unité est obligatoire.")
            return None
        return {
            "Unit_Name": name,
            "Description": self.desc_input.text().strip() or None
        }
    
class PartnerDialog(BaseDialog):
    """
    Dialog pour Ajouter/Modifier un partenaire.
    Affiche TOUTES les informations disponibles.
    """
    def __init__(self, parent=None, data=None):
        self.data = data # البيانات القادمة من الجدول (Dictionary)
        
        title = "Modifier le Partenaire" if self.data else "Nouveau Partenaire"
        super().__init__(title, parent)
        
        self.resize(1100, 650) # حجم كبير لاستيعاب كل البيانات
        self.init_ui()
        
        # تعبئة البيانات إذا كنا في وضع التعديل
        if self.data:
            self.populate_form()

    def init_ui(self):
        main_layout = QVBoxLayout(self.form_widget)
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        self.tab_info = QWidget()
        info_layout = QVBoxLayout(self.tab_info)
        info_layout.setSpacing(15)
        info_layout.setContentsMargins(15, 15, 15, 15)
        
        # This variable points to info_layout so the rest of the code works as is
        main_layout = info_layout

        # ---------------------------------------------------------
        # ZONE 1: Identité & Fiscalité (أعلى)
        # ---------------------------------------------------------
        row1_layout = QHBoxLayout()
        
        # --- Groupe: Identité ---
        grp_identity = self._create_group("Identité & Classification", "#2c3e50")
        grid_id = QGridLayout(grp_identity)
        
        self.inp_name = QLineEdit()
        self.cb_type = QComboBox()
        self.cb_type.addItems(["Laboratoire", "Médecin", "Hôpital", "Pharmacie", "Salle de Soins", "Clinique", "Autre"])
        self.cb_type.setItemData(0, "Laboratory")
        self.cb_type.setItemData(1, "Doctor")
        self.cb_type.setItemData(2, "Hospital")
        self.cb_type.setItemData(3, "Pharmacy")
        self.cb_type.setItemData(4, "CareRoom")
        self.cb_type.setItemData(5, "Clinic")
        self.cb_type.setItemData(6, "Other")
        
        self.inp_agrement = QLineEdit()
        self.inp_agrement.setPlaceholderText("Numéro d'agrément officiel")

        grid_id.addWidget(QLabel("Nom Partenaire * :"), 0, 0)
        grid_id.addWidget(self.inp_name, 0, 1, 1, 3)
        grid_id.addWidget(QLabel("Type :"), 1, 0)
        grid_id.addWidget(self.cb_type, 1, 1)
        grid_id.addWidget(QLabel("N° Agrément :"), 1, 2)
        grid_id.addWidget(self.inp_agrement, 1, 3)
        
        row1_layout.addWidget(grp_identity, stretch=3)

        # --- Groupe: Fiscalité ---
        grp_fiscal = self._create_group("Fiscalité", "#8e44ad")
        grid_fiscal = QGridLayout(grp_fiscal)
        
        self.inp_tax_id = QLineEdit() # NIF
        self.inp_rc = QLineEdit()     # RC
        
        grid_fiscal.addWidget(QLabel("NIF (Matricule) :"), 0, 0)
        grid_fiscal.addWidget(self.inp_tax_id, 0, 1)
        grid_fiscal.addWidget(QLabel("Reg. Commerce :"), 1, 0)
        grid_fiscal.addWidget(self.inp_rc, 1, 1)
        
        row1_layout.addWidget(grp_fiscal, stretch=2)
        main_layout.addLayout(row1_layout)

        # ---------------------------------------------------------
        # ZONE 2: Contact & Adresse (وسط)
        # ---------------------------------------------------------
        row2_layout = QHBoxLayout()

        # --- Groupe: Contact ---
        grp_contact = self._create_group("Coordonnées", "#2980b9")
        grid_contact = QGridLayout(grp_contact)
        
        self.inp_contact_person = QLineEdit()
        self.inp_phone = QLineEdit()
        self.inp_email = QLineEdit()
        self.inp_website = QLineEdit()

        grid_contact.addWidget(QLabel("Responsable :"), 0, 0)
        grid_contact.addWidget(self.inp_contact_person, 0, 1)
        grid_contact.addWidget(QLabel("Téléphone :"), 1, 0)
        grid_contact.addWidget(self.inp_phone, 1, 1)
        grid_contact.addWidget(QLabel("Email :"), 2, 0)
        grid_contact.addWidget(self.inp_email, 2, 1)
        grid_contact.addWidget(QLabel("Site Web :"), 3, 0)
        grid_contact.addWidget(self.inp_website, 3, 1)

        row2_layout.addWidget(grp_contact, stretch=1)

        # --- Groupe: Adresse ---
        grp_address = self._create_group("Localisation", "#27ae60")
        grid_addr = QGridLayout(grp_address)
        
        self.inp_address1 = QLineEdit()
        self.inp_address2 = QLineEdit()
        self.inp_city = QLineEdit()
        self.inp_postal_code = QLineEdit()

        grid_addr.addWidget(QLabel("Adresse (Ligne 1) :"), 0, 0)
        grid_addr.addWidget(self.inp_address1, 0, 1, 1, 3)
        grid_addr.addWidget(QLabel("Adresse (Ligne 2) :"), 1, 0)
        grid_addr.addWidget(self.inp_address2, 1, 1, 1, 3)
        grid_addr.addWidget(QLabel("Ville :"), 2, 0)
        grid_addr.addWidget(self.inp_city, 2, 1)
        grid_addr.addWidget(QLabel("Code Postal :"), 2, 2)
        grid_addr.addWidget(self.inp_postal_code, 2, 3)

        row2_layout.addWidget(grp_address, stretch=2)
        main_layout.addLayout(row2_layout)

        # ---------------------------------------------------------
        # ZONE 3: Banque (أسفل)
        # ---------------------------------------------------------
        grp_bank = self._create_group("Informations Bancaires", "#c0392b")
        hbox_bank = QHBoxLayout(grp_bank)
        
        self.inp_bank_name = QLineEdit()
        self.inp_iban = QLineEdit()
        
        hbox_bank.addWidget(QLabel("Nom Banque :"))
        hbox_bank.addWidget(self.inp_bank_name, 1)
        hbox_bank.addWidget(QLabel("RIB / IBAN :"))
        hbox_bank.addWidget(self.inp_iban, 2)
        
        main_layout.addWidget(grp_bank)
        main_layout.addStretch()
        
        self.tabs.addTab(self.tab_info, "Informations Générales")
        
        if self.data:
            self.tab_bl = QWidget()
            self.tab_br = QWidget()
            self.tabs.addTab(self.tab_bl, "Bons de Livraison (Sortie)")
            self.tabs.addTab(self.tab_br, "Bons de Retour")
            self.init_transfers_tabs()

    def init_transfers_tabs(self):
        from PySide6.QtWidgets import QTableWidget, QHeaderView, QTableWidgetItem
        from PySide6.QtCore import Qt
        
        # BL
        bl_layout = QVBoxLayout(self.tab_bl)
        self.table_bl = QTableWidget(0, 3)
        self.table_bl.setHorizontalHeaderLabels(["Date & Heure", "Total (DA)", "Statut"])
        self.table_bl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_bl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_bl.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_bl.setAlternatingRowColors(True)
        bl_layout.addWidget(self.table_bl)
        
        # BR
        br_layout = QVBoxLayout(self.tab_br)
        self.table_br = QTableWidget(0, 3)
        self.table_br.setHorizontalHeaderLabels(["Date & Heure", "Total (DA)", "Statut"])
        self.table_br.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_br.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_br.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_br.setAlternatingRowColors(True)
        br_layout.addWidget(self.table_br)
        
        try:
            manager = self.parent().manager
            with manager.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT Transaction_Date, Total_Amount, Status, Transfer_Type FROM External_Transfer_Log WHERE Partner_ID = %s ORDER BY Transaction_Date DESC", (self.data['Partner_ID'],))
                transfers = cursor.fetchall()
            
            for t in transfers:
                raw_dt = t.get('Transaction_Date')
                date_str = raw_dt.strftime("%Y-%m-%d %H:%M") if hasattr(raw_dt, 'strftime') else str(raw_dt or "")[:16]
                amt_val = float(t.get('Total_Amount') or 0)
                row_data = [
                    date_str,
                    format_money(amt_val, 'DA'),
                    str(t.get('Status', ''))
                ]
                ttype = t.get('Transfer_Type') or 'Outbound'
                target_table = self.table_br if ttype == 'Return' else self.table_bl
                
                r = target_table.rowCount()
                target_table.insertRow(r)
                for c, val in enumerate(row_data):
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignCenter if c != 1 else (Qt.AlignRight | Qt.AlignVCenter))
                    if ttype == 'Return':
                        item.setForeground(Qt.magenta)
                    target_table.setItem(r, c, item)
        except Exception as e:
            import logging
            logging.error(f"Error loading transfers in dialog: {e}")

    def _create_group(self, title, color):
        gb = QGroupBox(title)
        gb.setStyleSheet(f"""
            QGroupBox {{ 
                font-weight: bold; border: 1px solid #bdc3c7; 
                border-radius: 6px; margin-top: 10px; padding-top: 12px; 
            }}
            QGroupBox::title {{ 
                subcontrol-origin: margin; left: 10px; padding: 0 5px; color: {color}; 
            }}
        """)
        return gb

    def populate_form(self):
        """
        تعبئة جميع الحقول. 
        يتم استخدام .get() مع قيمة افتراضية "" لتجنب الأخطاء إذا كانت القيمة None.
        """
        d = self.data
        if not d: return

        # 1. Identité
        self.inp_name.setText(d.get('Partner_Name') or "")
        
        # البحث عن النوع في القائمة المنسدلة
        type_code = d.get('Partner_Type', 'Laboratory')
        idx = self.cb_type.findData(type_code)
        if idx >= 0: 
            self.cb_type.setCurrentIndex(idx)
        else:
            self.cb_type.setCurrentIndex(0)

        self.inp_agrement.setText(str(d.get('Agrement_Number') or ""))

        # 2. Fiscalité
        self.inp_tax_id.setText(str(d.get('Tax_ID_Number') or ""))
        self.inp_rc.setText(str(d.get('Commercial_Reg_No') or ""))

        # 3. Contact
        self.inp_contact_person.setText(d.get('Contact_Person') or "")
        self.inp_phone.setText(d.get('Phone') or "")
        self.inp_email.setText(d.get('Email') or "")
        self.inp_website.setText(d.get('Website') or "")

        # 4. Adresse
        self.inp_address1.setText(d.get('Address_Line1') or "")
        self.inp_address2.setText(d.get('Address_Line2') or "")
        self.inp_city.setText(d.get('City') or "")
        self.inp_postal_code.setText(str(d.get('Postal_Code') or ""))

        # 5. Banque
        self.inp_bank_name.setText(d.get('Bank_Name') or "")
        self.inp_iban.setText(d.get('Bank_Account_IBAN') or "")

    def get_data(self):
        """تجهيز البيانات للإرسال إلى قاعدة البيانات"""
        name = self.inp_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Erreur", "Le nom du partenaire est obligatoire.")
            return None

        # دالة مساعدة لتحويل النصوص الفارغة إلى None (اختياري، حسب تصميم الـ DB)
        def val(txt): return txt.strip() if txt.strip() else None

        return {
            'Partner_Name': name,
            'Partner_Type': self.cb_type.currentData(),
            'Agrement_Number': val(self.inp_agrement.text()),
            
            'Tax_ID_Number': val(self.inp_tax_id.text()),
            'Commercial_Reg_No': val(self.inp_rc.text()),
            
            'Contact_Person': val(self.inp_contact_person.text()),
            'Phone': val(self.inp_phone.text()),
            'Email': val(self.inp_email.text()),
            'Website': val(self.inp_website.text()),
            
            'Address_Line1': val(self.inp_address1.text()),
            'Address_Line2': val(self.inp_address2.text()),
            'City': val(self.inp_city.text()),
            'Postal_Code': val(self.inp_postal_code.text()),
            
            'Bank_Name': val(self.inp_bank_name.text()),
            'Bank_Account_IBAN': val(self.inp_iban.text())
        }