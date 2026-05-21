# ui\main_window.py

import os
import logging
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QStackedWidget, QLabel, QPushButton, QFrame, QButtonGroup, 
                               QTabWidget, QMessageBox) 
from PySide6.QtCore import Qt, QSize, QFile, QTextStream, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
from PySide6.QtGui import QPixmap, QIcon
import qtawesome as qta
import json

from .widgets.master_data.suppliers_tab import SuppliersTab
from .widgets.master_data.products_tab import ProductsTab
from .widgets.dashboard.dashboard_view import DashboardTab
from .widgets.procurement.procurement_tabs import ProcurementTab
from .widgets.supplier.supplier_stats_tab import SupplierStatsTab
from .widgets.supplier.supplier_financial_view import SupplierFinancialView 
from .widgets.inventory.inventory_tabs import InventoryTab
from .widgets.master_data.manufacturers_tab import ManufacturersTab
from .widgets.master_data.locations_tab import LocationsTab
from .widgets.master_data.automates_tab import AutomatesTab
from .widgets.master_data.waste_reasons_tab import WasteReasonsTab
from .widgets.settings.settings_tab import SettingsTab
from .widgets.master_data.product_families_tab import ProductFamiliesTab
from .widgets.master_data.packaging_units_tab import PackagingUnitsTab
from .widgets.user_management_tab import UserManagementTab
from .widgets.master_data.external_partners_tab import ExternalPartnersTab
from .widgets.billing.billing_tab import BillingTab
from .widgets.history import MovementHistoryTab
from database.auto_backup_worker import AutoBackupWorker
from database import active_user_id
from branding import (
    get_app_name,
    get_logo_path,
    get_organization_name,
    get_resource_path as get_brand_resource_path,
    get_settings_app_name,
)

class MainWindow(QMainWindow):
    def __init__(self, data_manager, current_user, connection_error=None): 
        super().__init__()
        self.data_manager = data_manager
        self.current_user = current_user 
        self.connection_error = connection_error

        if self.current_user:
            # نستخدم get للبحث عن User_ID أو id لتجنب أخطاء المفاتيح
            u_id = self.current_user.get('User_ID') or self.current_user.get('id')
            if u_id:
                active_user_id.set(u_id)
        # ---------------------
        
        # --- تحسين: تخزين الصفحات التي تم تحميلها فقط ---
        self.loaded_pages = {} 

        # --- حالة الشريط الجانبي ---
        self.is_sidebar_expanded = True
        self.sidebar_full_width = 260
        self.sidebar_compact_width = 70
        self.button_texts = {} 

        full_name = self.current_user.get('Full_Name', 'Utilisateur') if self.current_user else 'Invité'
        self.setWindowTitle(f"{get_app_name()} | {full_name}")

        logo_path = get_logo_path()
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
        else:
            self.setWindowIcon(qta.icon('fa5s.heartbeat', color='#007572'))
        self.setMinimumSize(QSize(1366, 768))

        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QHBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self._setup_show_sidebar_button()
        self._setup_sidebar()

        self.content_area = QStackedWidget()
        self.main_layout.addWidget(self.content_area)
        
        # تهيئة الـ StackedWidget بعناصر فارغة
        self._init_placeholders()
        self.load_stylesheet()
        
        self.apply_permissions()

        if connection_error:
            self.switch_page(4) 
        else:
            # خريطة الصفحات مرتبطة بصلاحياتها
            mapping = {
                0: "nav_dashboard",
                1: "nav_data",
                2: "nav_procurement",
                3: "nav_inventory",
                8: "nav_finance",
                6: "nav_services",
                7: "nav_history",
                5: "tab_users",
                4: "nav_settings"
            }

            first_permitted_page = None
            
            # المرور على الصفحات بالترتيب والتحقق من الصلاحية برمجياً
            for page_id in sorted(mapping.keys()):
                perm_key = mapping[page_id]
                if self.has_permission(perm_key):
                    first_permitted_page = page_id
                    break
            
            # فتح أول صفحة يملك المستخدم صلاحيتها
            if first_permitted_page is not None:
                self.switch_page(first_permitted_page)
                if self.nav_group.button(first_permitted_page):
                    self.nav_group.button(first_permitted_page).setChecked(True)
            else:
                logging.warning("User has no permitted pages to display.")
        self.auto_backup_thread = None
        if self.data_manager and not self.connection_error:
            self.auto_backup_thread = AutoBackupWorker(self.data_manager)
            self.auto_backup_thread.start()

                


    def open_product_history(self, search_text):
        """تستقبل طلب البحث من صفحة المخزون وتفتح السجل"""
        # 1. الانتقال لصفحة السجل (رقم 7)
        self.switch_page(7)
        
        # 2. تحديث الزر الجانبي ليظهر كمحدد
        if self.nav_group.button(7):
            self.nav_group.button(7).setChecked(True)

        # 3. الوصول للكائن الخاص بصفحة السجل
        history_widget = self.loaded_pages.get(7)
        
        if history_widget:
            # 4. وضع النص في مربع البحث (نفترض أن اسمه search_input)
            if hasattr(history_widget, 'search_input'):
                history_widget.search_input.setText(search_text)
                
                # 5. تشغيل عملية البحث/الفلترة
                # نحاول استدعاء دوال التحديث المعتادة
                if hasattr(history_widget, 'filter_data'):
                    history_widget.filter_data()
                elif hasattr(history_widget, 'load_data'):
                    history_widget.load_data()
                elif hasattr(history_widget, 'on_search_changed'): # احتمال آخر
                     history_widget.on_search_changed(search_text)

    def load_stylesheet(self):
        try:
            style_path = get_brand_resource_path("ui/styles.qss")
            style_file = QFile(style_path)
            if style_file.open(QFile.ReadOnly | QFile.Text):
                stream = QTextStream(style_file)
                self.setStyleSheet(stream.readAll())
                style_file.close()
        except Exception as e:
            logging.error(f"Error loading stylesheet: {e}")

    def _setup_show_sidebar_button(self):
        self.show_sidebar_container = QFrame()
        self.show_sidebar_container.setObjectName("show_sidebar_container") 
        self.show_sidebar_container.setFixedWidth(0)
        layout = QVBoxLayout(self.show_sidebar_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        self.btn_show_sidebar = QPushButton()
        self.btn_show_sidebar.setObjectName("btn_show_sidebar")
        self.btn_show_sidebar.setIcon(qta.icon("fa5s.chevron-right", color="#2c3e50"))
        self.btn_show_sidebar.setCursor(Qt.PointingHandCursor)
        self.btn_show_sidebar.clicked.connect(self.toggle_sidebar_visibility)
        layout.addWidget(self.btn_show_sidebar)
        layout.addStretch()
        self.main_layout.addWidget(self.show_sidebar_container)

    def update_header_layout(self, compact):
        if self.header_container.layout():
            old_layout = self.header_container.layout()
            old_layout.removeWidget(self.btn_toggle)
            old_layout.removeWidget(self.logo_label)
            old_layout.removeWidget(self.text_container)
            self.btn_toggle.setParent(self.header_container)
            self.logo_label.setParent(self.header_container)
            self.text_container.setParent(self.header_container)
            QWidget().setLayout(old_layout)

        if compact:
            layout = QVBoxLayout(self.header_container)
            layout.setContentsMargins(5, 10, 5, 5)
            layout.setSpacing(5) 
            self.header_container.setFixedHeight(90)
            layout.addWidget(self.btn_toggle, alignment=Qt.AlignHCenter)
            layout.addWidget(self.logo_label, alignment=Qt.AlignHCenter)
            self.text_container.hide()
            self.btn_toggle.show()
            self.logo_label.show()
        else:
            layout = QHBoxLayout(self.header_container)
            layout.setContentsMargins(15, 15, 15, 15)
            layout.setSpacing(10)
            self.header_container.setFixedHeight(80)
            layout.addWidget(self.logo_label)
            layout.addWidget(self.text_container)
            layout.addStretch()
            layout.addWidget(self.btn_toggle)
            self.text_container.show()
            self.btn_toggle.show()
            self.logo_label.show()

    def _setup_sidebar(self):
        self.sidebar_container = QFrame()
        self.sidebar_container.setObjectName("sidebar_container")
        self.sidebar_container.setProperty("state", "expanded")
        self.sidebar_container.setFixedWidth(self.sidebar_full_width)
        
        sidebar_layout = QVBoxLayout(self.sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(6)

        self.header_container = QWidget()
        self.header_container.setObjectName("header_container")
        self.header_container.setFixedHeight(80) 

        self.logo_label = QLabel()
        logo_path = get_logo_path()
        if os.path.exists(logo_path):
            self.logo_pixmap = QPixmap(logo_path)
        else:
            self.logo_pixmap = qta.icon('fa5s.heartbeat', color='#007572').pixmap(QSize(64, 64))
        self.logo_label.setPixmap(self.logo_pixmap.scaled(35, 35, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.logo_label.setFixedSize(35, 35)

        self.text_container = QWidget()
        text_layout = QVBoxLayout(self.text_container)
        text_layout.setContentsMargins(0, 2, 0, 2)
        text_layout.setSpacing(0)
        lbl_title = QLabel(get_app_name())
        lbl_title.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 16px; font-weight: 800; color: #2c3e50;")
        lbl_sub = QLabel("gestion de stock")
        lbl_sub.setStyleSheet("font-size: 10px; font-weight: 600; color: #007572; letter-spacing: 1px;")
        text_layout.addWidget(lbl_title)
        text_layout.addWidget(lbl_sub)
        
        self.btn_toggle = QPushButton()
        self.btn_toggle.setIcon(qta.icon("fa5s.bars", color="#546e7a"))
        self.btn_toggle.setFixedSize(35, 35)
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.setFlat(True)
        self.btn_toggle.clicked.connect(self.toggle_sidebar_compact)

        self.update_header_layout(compact=False)
        sidebar_layout.addWidget(self.header_container)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #f0f2f5; margin: 0px 10px;")
        line.setFixedHeight(1)
        sidebar_layout.addWidget(line)
        sidebar_layout.addSpacing(10)

        self.nav_group = QButtonGroup(self)
        self.nav_group.idClicked.connect(self.switch_page)

        buttons_info = [
            (0, "Tableau de Bord", "fa5s.chart-pie"),
            (1, "Données de Base", "fa5s.layer-group"),
            (2, "Achats & Entrées", "fa5s.shopping-cart"), 
            (3, "Stock & Magasin",  "fa5s.boxes"),
            (8, "États Fournisseurs", "fa5s.file-invoice-dollar"), 
            (6, "Sous-Traitants",   "fa5s.file-invoice-dollar"), 
            (7, "Traçabilité",      "fa5s.history"),
            (5, "Utilisateurs",    "fa5s.users"),
            (4, "Paramètres",      "fa5s.sliders-h")
        ]

        for btn_id, text, icon_name in buttons_info:
            icon = qta.icon(icon_name, color="#546e7a", color_active="#007572")
            btn = QPushButton(text)
            btn.setIcon(icon)
            btn.setIconSize(QSize(20, 20))
            btn.setCheckable(True)
            btn.setProperty("class", "nav_button")
            btn.setCursor(Qt.PointingHandCursor)
            self.button_texts[btn] = text
            self.nav_group.addButton(btn, btn_id)
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        self.btn_logout = QPushButton("Déconnexion")
        self.btn_logout.setIcon(qta.icon("fa5s.power-off", color="#e74c3c"))
        self.btn_logout.setProperty("class", "logout_button")
        self.btn_logout.setCursor(Qt.PointingHandCursor)
        self.btn_logout.clicked.connect(self.logout)
        self.button_texts[self.btn_logout] = "Déconnexion"
        sidebar_layout.addWidget(self.btn_logout)

        self.btn_hide_sidebar = QPushButton()
        self.btn_hide_sidebar.setIcon(qta.icon("fa5s.chevron-left", color="#b0bec5"))
        self.btn_hide_sidebar.setProperty("class", "hide_button")
        self.btn_hide_sidebar.setCursor(Qt.PointingHandCursor)
        self.btn_hide_sidebar.clicked.connect(self.toggle_sidebar_visibility)
        sidebar_layout.addWidget(self.btn_hide_sidebar)

        self.main_layout.addWidget(self.sidebar_container)

    def toggle_sidebar_compact(self):
        if self.sidebar_container.width() == 0: return
        target_width = self.sidebar_compact_width if self.is_sidebar_expanded else self.sidebar_full_width
        self.anim = QPropertyAnimation(self.sidebar_container, b"minimumWidth")
        self.anim.setDuration(250)
        self.anim.setStartValue(self.sidebar_container.width())
        self.anim.setEndValue(target_width)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.anim.start()
        self.anim_max = QPropertyAnimation(self.sidebar_container, b"maximumWidth")
        self.anim_max.setDuration(250)
        self.anim_max.setStartValue(self.sidebar_container.width())
        self.anim_max.setEndValue(target_width)
        self.anim_max.start()

        if self.is_sidebar_expanded:
            self.sidebar_container.setProperty("state", "compact")
            self.update_header_layout(compact=True)
            for btn in self.nav_group.buttons() + [self.btn_logout]:
                btn.setText("")
                btn.setToolTip(self.button_texts[btn])
        else:
            self.sidebar_container.setProperty("state", "expanded")
            self.update_header_layout(compact=False)
            for btn in self.nav_group.buttons() + [self.btn_logout]:
                btn.setText(self.button_texts[btn])
                btn.setToolTip("")

        self.is_sidebar_expanded = not self.is_sidebar_expanded
        self.sidebar_container.style().unpolish(self.sidebar_container)
        self.sidebar_container.style().polish(self.sidebar_container)

    def toggle_sidebar_visibility(self):
        current_width = self.sidebar_container.width()
        if current_width > 0:
            start_val = current_width
            end_val = 0
            self.show_sidebar_container.setFixedWidth(30)
        else:
            start_val = 0
            end_val = self.sidebar_full_width if self.is_sidebar_expanded else self.sidebar_compact_width
            self.show_sidebar_container.setFixedWidth(0)

        self.anim_vis = QPropertyAnimation(self.sidebar_container, b"maximumWidth")
        self.anim_vis.setDuration(300)
        self.anim_vis.setStartValue(start_val)
        self.anim_vis.setEndValue(end_val)
        self.anim_vis.setEasingCurve(QEasingCurve.InOutSine)
        
        self.anim_vis_min = QPropertyAnimation(self.sidebar_container, b"minimumWidth")
        self.anim_vis_min.setDuration(300)
        self.anim_vis_min.setStartValue(start_val)
        self.anim_vis_min.setEndValue(end_val)

        group = QParallelAnimationGroup(self)
        group.addAnimation(self.anim_vis)
        group.addAnimation(self.anim_vis_min)
        group.start()

    def closeEvent(self, event):
        """تأكيد الخروج وإيقاف المهام الخلفية قبل إغلاق التطبيق."""
        # إظهار رسالة تأكيد باللغة الفرنسية (لتطابق باقي النظام)
        reply = QMessageBox.question(
            self, 
            "Confirmation de sortie",  
            "Voulez-vous vraiment quitter l'application ?",  
            QMessageBox.Yes | QMessageBox.No,  
            QMessageBox.No  
        )
        
        # إذا وافق المستخدم على الخروج
        if reply == QMessageBox.Yes:
            # إيقاف خيط النسخ الاحتياطي التلقائي إن وجد
            if self.auto_backup_thread and self.auto_backup_thread.isRunning():
                logging.info("Stopping auto-backup thread...")
                self.auto_backup_thread.stop()
            
            # قبول حدث الإغلاق (يتم إغلاق البرنامج)
            event.accept()
        else:
            # تجاهل حدث الإغلاق (يبقى البرنامج مفتوحاً)
            event.ignore()

    def apply_permissions(self):
        """التحكم في ظهور أزرار القائمة الجانبية بناءً على الصلاحيات"""
        if not self.current_user: return
        
        # ربط المعرف (ID) الخاص بالزر بمفتاح الصلاحية (Permission Key)
        mapping = {
            0: "nav_dashboard",
            1: "nav_data",
            2: "nav_procurement",
            3: "nav_inventory",
            8: "nav_finance",
            6: "nav_services",
            7: "nav_history",  # واجهة السجل المستقلة
            5: "tab_users",
            4: "nav_settings"
        }
        for btn_id, perm in mapping.items():
            btn = self.nav_group.button(btn_id)
            if btn:
                btn.setVisible(self.has_permission(perm))

    def logout(self):
        """تسجيل الخروج مع طلب التأكيد"""
        ans = QMessageBox.question(
            self, 
            "Confirmation",  
            "Voulez-vous vraiment vous déconnecter ?",  
            QMessageBox.Yes | QMessageBox.No,  
            QMessageBox.No  
        )
        
        if ans == QMessageBox.Yes:
            self.want_logout = True 
            
            from PySide6.QtCore import QSettings
            settings = QSettings(get_organization_name(), get_settings_app_name())
            
            self.close()

    def _init_placeholders(self):
        for i in range(9):
            self.content_area.addWidget(QWidget())

    def has_permission(self, perm_key):
        """التحقق مما إذا كان المستخدم يملك الصلاحية المحددة في ملف JSON"""
        if not self.current_user:
            return False
            
        perms = self.current_user.get('Permissions', {})
        
        # تحويل النص إلى كائن برمجي في حال كان String
        if isinstance(perms, str):
            try:
                perms = json.loads(perms)
            except json.JSONDecodeError:
                perms = []

        # إذا كانت الصلاحيات محفوظة على شكل مصفوفة (كما في users_view.py)
        if isinstance(perms, list):
            return perm_key in perms
        # إذا كانت محفوظة على شكل قاموس {key: True}
        elif isinstance(perms, dict):
            return perms.get(perm_key, False)
            
        return False

    def _load_page(self, page_id):
        """تحميل الواجهات وإضافة التبويبات بناءً على الصلاحيات المخصصة"""
        if page_id in self.loaded_pages:
            return self.loaded_pages[page_id]

        widget = None
        
        # --- 0. Dashboard ---
        if page_id == 0:
            widget = DashboardTab(self.data_manager)
            if self.has_permission("tab_dash_overview"):
                widget.tabs.addTab(widget.page_overview, "📌 Vue d'ensemble")
            if self.has_permission("tab_dash_reception"):
                widget.tabs.addTab(widget.page_family_reception, "📅 Entrées par Famille")
            if self.has_permission("tab_dash_consumption"):
                widget.tabs.addTab(widget.page_consumption, "📋 Consommation")
            if self.has_permission("tab_dash_valuation"):
                widget.tabs.addTab(widget.page_valuation, "💰 Valorisation")
            if self.has_permission("tab_dash_waste"):
                widget.tabs.addTab(widget.page_waste, "🗑️ Pertes")
            if self.has_permission("tab_dash_alerts"):
                widget.tabs.addTab(widget.page_alerts, "⚠️ Alertes")

        # --- 1. Master Data (Données de Base) ---
        elif page_id == 1:
            from .widgets.master_data.master_data_tabs import MasterDataTabs
            widget = MasterDataTabs(self.data_manager)
            
            if self.has_permission("tab_data_products"):
                widget.tabs.addTab(widget.tab_products, "Produits")
            if hasattr(self.data_manager, 'families') and self.has_permission("tab_data_families"): 
                widget.tabs.addTab(widget.tab_families, "Familles")
            if hasattr(self.data_manager, 'packaging_units') and self.has_permission("tab_data_units"): 
                widget.tabs.addTab(widget.tab_units, "Unités (Pkg)")
            if hasattr(self.data_manager, 'suppliers') and self.has_permission("tab_data_suppliers"): 
                widget.tabs.addTab(widget.tab_suppliers, "Fournisseurs")
            if hasattr(self.data_manager, 'manufacturers') and self.has_permission("tab_data_manufacturers"): 
                widget.tabs.addTab(widget.tab_manufacturers, "Fabricants")
            if hasattr(self.data_manager, 'partners') and self.has_permission("tab_data_partners"): 
                widget.tabs.addTab(widget.tab_partners, "Partenaires")
            if hasattr(self.data_manager, 'automates') and self.has_permission("tab_data_automates"):
                widget.tabs.addTab(widget.tab_automates, "Automates")
            if hasattr(self.data_manager, 'locations') and self.has_permission("tab_data_locations"): 
                widget.tabs.addTab(widget.tab_locations, "Emplacements")
            if hasattr(self.data_manager, 'waste_reasons') and self.has_permission("tab_data_waste_reasons"): 
                widget.tabs.addTab(widget.tab_waste, "Motifs Rebut")

        # --- 2. Procurement (Achats) ---
        elif page_id == 2:
            widget = ProcurementTab(self.data_manager)
            if self.has_permission("tab_proc_po"):
                widget.tabs.addTab(widget.po_tab, "📦 Bons de Commandes")
            if self.has_permission("tab_proc_reception"):
                widget.tabs.addTab(widget.history_tab, "📜 Bons de Réceptions")
            if self.has_permission("tab_proc_credit"):
                widget.tabs.addTab(widget.credit_tab, "↩️ Avoirs / Retours")
            if self.has_permission("tab_proc_reclamation"):
                widget.tabs.addTab(widget.reclamation_tab, "⚠️ Réclamations")
                
        elif page_id == 3:
            widget = InventoryTab(self.data_manager)
            if hasattr(widget, 'batches_tab'):
                widget.batches_tab.request_product_history.connect(self.open_product_history)
            if self.has_permission("tab_inv_list"): 
                widget.tabs.addTab(widget.batches_tab, "📦 1. Stock Actuel")
            if self.has_permission("tab_inv_dispatch"): 
                widget.tabs.addTab(widget.dispatch_tab, "🚚 2. Transfert & Consommation")

        # --- 4. Settings (Paramètres) ---
        elif page_id == 4:
            widget = SettingsTab(self.data_manager)
            if self.connection_error and hasattr(widget, 'set_connection_error'):
                widget.set_connection_error(self.connection_error)
            if self.connection_error:
                widget.tabs.addTab(widget.tab_db, "Base de données")
                widget.tabs.setCurrentWidget(widget.tab_db)
            if self.has_permission("tab_config"):
                widget.tabs.addTab(widget.tab_general, "🏢 Général / Gestion des données")
            if self.has_permission("tab_set_db"):
                widget.tabs.addTab(widget.tab_db, "🗄️ Base de données")
            if self.has_permission("tab_set_printer"):
                widget.tabs.addTab(widget.tab_printer, "🖨️ Imprimante")
            if self.has_permission("tab_set_system"):
                widget.tabs.addTab(widget.tab_system, "⚙️ Système")
            if self.has_permission("tab_system_logs"):
                widget.tabs.addTab(widget.tab_system_logs, "📝 Logs Système")
            if self.has_permission("tab_set_pdf"):
                widget.tabs.addTab(widget.tab_pdf_config, "🎨 Configuration PDF")

        # --- 5. Users ---
        elif page_id == 5:
            widget = UserManagementTab(self.data_manager)

        # --- 6. Services / Sous-Traitants ---
        elif page_id == 6:
            try:
                widget = BillingTab(self.data_manager)
            except:
                widget = QLabel("Module Facturation non chargé")

        # --- 8. Supplier Financials ---
        elif page_id == 8: 
            from .widgets.supplier.supplier_financial_view import SupplierFinancialView
            widget = SupplierFinancialView(self.data_manager)
            
            if self.has_permission("tab_fin_situation"):
                widget.tabs.addTab(widget.tab_situation, "📜 Grand Livre (Situation)")
            if self.has_permission("tab_fin_journal"):
                widget.tabs.addTab(widget.tab_journal, "💰 Journal des Paiements")
            if self.has_permission("tab_fin_dashboard"):
                widget.tabs.addTab(widget.tab_dashboard, "📊 Tableau de Bord")
                widget.tab_dashboard.refresh_stats()

        elif page_id == 7:
            from .widgets.history import MovementHistoryTab
            widget = MovementHistoryTab(self.data_manager)
            if hasattr(widget, 'load_data'):
                widget.load_data()

        if widget:
            old_widget = self.content_area.widget(page_id)
            self.content_area.removeWidget(old_widget)
            self.content_area.insertWidget(page_id, widget)
            self.loaded_pages[page_id] = widget
            return widget
        return None

    def switch_page(self, page_id):
        if self.connection_error and page_id != 4:
            QMessageBox.warning(self, "Erreur Connexion", "Veuillez configurer la base de données.")
            self.switch_page(4)
            return

        # خريطة لربط رقم الصفحة بمفتاح الصلاحية المطلوب
        mapping = {
            0: "nav_dashboard",
            1: "nav_data",
            2: "nav_procurement",
            3: "nav_inventory",
            8: "nav_finance",
            6: "nav_services",
            7: "nav_history",
            5: "tab_users",
            4: "nav_settings"
        }
        
        required_perm = None if self.connection_error and page_id == 4 else mapping.get(page_id)
        # التحقق: إذا كانت الصفحة تتطلب صلاحية والمستخدم لا يملكها، امنع الدخول
        if required_perm and not self.has_permission(required_perm):
            logging.warning(f"Unauthorized access attempt to page {page_id}")
            return

        self._load_page(page_id)
        self.content_area.setCurrentIndex(page_id)
