import os
import json
import logging

# --- PySide6 Imports ---
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QGroupBox, QFormLayout, QDoubleSpinBox, 
    QFileDialog, QColorDialog, QTabWidget, QScrollArea, 
    QFrame, QMessageBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QRectF, QRect
from PySide6.QtGui import QColor, QPixmap, QFont, QPainter, QPen, QBrush

class PdfConfigWidget(QWidget):
    """
    لوحة تحكم شاملة لتخصيص قالب الـ PDF.
    تعرض الإعدادات المخزنة وتسمح بالتحكم الدقيق في موقع الصورة.
    """
    settings_updated = Signal(dict)

    def __init__(self, settings_input="pdf_settings.json"):
        super().__init__()
        
        # 1. إدارة تحميل الإعدادات (دعم القاموس أو المسار)
        if isinstance(settings_input, dict):
            self.settings_path = "pdf_settings.json"
            self.settings = {**self.get_default_settings(), **settings_input}
        else:
            self.settings_path = settings_input
            self.settings = self.load_settings()
            
        # 2. بناء الواجهة الرسومية
        self.init_ui()

    def get_default_settings(self):
        """القيم الافتراضية الشاملة لجميع عناصر القالب"""
        return {
            "theme_color": "#0b666a",
            "doc_title": "Bon de livraison",
            "banner_height_cm": 4.8, 
            "banner_path": "",
            "banner_img_x_cm": 0.0,
            "banner_img_y_cm": 0.0,
            "banner_img_w_cm": 21.0,
            "banner_img_h_cm": 4.8,
            "bank_name": "SOCIETE GENERALE",
            "bank_acc": "00475017000761081",
            "bank_y_offset_cm": 6.6,
            "dest_box_x_cm": 11.5,
            "dest_box_y_cm": 6.0,
            "dest_box_w_cm": 8.0,
            "table_start_y_cm": 9.5,
            "footer_left_label": "Responsable Stock",
            "footer_right_label": "Accusé de réception (Client)"
        }

    def load_settings(self):
        """تحميل الإعدادات من ملف JSON وعرضها في الواجهة"""
        defaults = self.get_default_settings()
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return {**defaults, **data}
            except Exception as e:
                logging.error(f"Error loading PDF settings: {e}")
                return defaults
        return defaults

    # --- الدالة المفقودة التي تسببت في الخطأ ---
    def get_updated_settings(self):
        """إرجاع الإعدادات الحالية ليتم حفظها في ملف config.json الرئيسي"""
        return self.settings

    def save_settings(self):
        """حفظ التعديلات النهائية في ملف الإعدادات المستقل"""
        try:
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self, "Succès", "Le modèle PDF a été mis à jour avec succès.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec de l'enregistrement: {e}")

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(15)

        control_panel = QWidget()
        control_panel.setFixedWidth(450)
        vbox = QVBoxLayout(control_panel)
        
        tabs = QTabWidget()
        tabs.setStyleSheet("QTabBar::tab { height: 35px; width: 100px; }")

        # التبويب الأول: Branding & Image
        tab_branding = QScrollArea()
        branding_content = QWidget()
        branding_vbox = QVBoxLayout(branding_content)

        group_identity = QGroupBox("Identité & Zone Header")
        identity_form = QFormLayout(group_identity)
        self.edit_title = QLineEdit(self.settings.get('doc_title', ''))
        self.btn_color = QPushButton("Changer la couleur du thème")
        self.color_preview = QFrame()
        self.color_preview.setFixedSize(50, 20)
        self.color_preview.setStyleSheet(f"background-color: {self.settings.get('theme_color', '#0b666a')}; border: 1px solid gray;")
        self.sp_banner_total_h = self._create_spin(1.0, 15.0, self.settings.get('banner_height_cm', 4.8))
        identity_form.addRow("Titre Document:", self.edit_title)
        identity_form.addRow("Couleur Thème:", self.btn_color)
        identity_form.addRow("", self.color_preview)
        identity_form.addRow("Hauteur Zone Header (cm):", self.sp_banner_total_h)
        branding_vbox.addWidget(group_identity)

        group_image = QGroupBox("Position & Taille de l'Image (Banner)")
        image_form = QFormLayout(group_image)
        self.btn_banner = QPushButton("Choisir l'image...")
        current_path = self.settings.get('banner_path', "")
        self.lbl_path = QLabel(os.path.basename(current_path) if current_path else "Aucune image")
        self.lbl_path.setStyleSheet("color: #2c3e50; font-weight: bold; font-size: 10px;")
        self.sp_img_x = self._create_spin(-5.0, 21.0, self.settings.get('banner_img_x_cm', 0.0))
        self.sp_img_y = self._create_spin(-5.0, 10.0, self.settings.get('banner_img_y_cm', 0.0))
        self.sp_img_w = self._create_spin(1.0, 30.0, self.settings.get('banner_img_w_cm', 21.0))
        self.sp_img_h = self._create_spin(1.0, 15.0, self.settings.get('banner_img_h_cm', 4.8))
        image_form.addRow(self.btn_banner, self.lbl_path)
        image_form.addRow("Position X (cm):", self.sp_img_x)
        image_form.addRow("Position Y (cm):", self.sp_img_y)
        image_form.addRow("Largeur Image (cm):", self.sp_img_w)
        image_form.addRow("Hauteur Image (cm):", self.sp_img_h)
        branding_vbox.addWidget(group_image)

        tab_branding.setWidget(branding_content)
        tab_branding.setWidgetResizable(True)
        tabs.addTab(tab_branding, "Branding")

        # التبويب الثاني: Positions
        tab_pos = QScrollArea()
        pos_content = QWidget()
        pos_form = QFormLayout(pos_content)
        self.edit_bank = QLineEdit(self.settings.get('bank_name', ''))
        self.edit_rib = QLineEdit(self.settings.get('bank_acc', ''))
        self.sp_bank_y = self._create_spin(0, 25, self.settings.get('bank_y_offset_cm', 6.6))
        self.sp_dest_x = self._create_spin(0, 21, self.settings.get('dest_box_x_cm', 11.5))
        self.sp_dest_y = self._create_spin(0, 29, self.settings.get('dest_box_y_cm', 6.0))
        self.sp_dest_w = self._create_spin(1, 15, self.settings.get('dest_box_w_cm', 8.0))
        pos_form.addRow("Nom Banque:", self.edit_bank)
        pos_form.addRow("N° Compte (RIB):", self.edit_rib)
        pos_form.addRow("Position Banque Y (cm):", self.sp_bank_y)
        pos_form.addRow("Destinataire X (cm):", self.sp_dest_x)
        pos_form.addRow("Destinataire Y (cm):", self.sp_dest_y)
        pos_form.addRow("Largeur Box (cm):", self.sp_dest_w)
        tab_pos.setWidget(pos_content)
        tab_pos.setWidgetResizable(True)
        tabs.addTab(tab_pos, "Positions")

        # التبويب الثالث: Détails
        tab_footer = QScrollArea()
        footer_content = QWidget()
        footer_form = QFormLayout(footer_content)
        self.sp_table_y = self._create_spin(5, 25, self.settings.get('table_start_y_cm', 9.5))
        self.edit_f_left = QLineEdit(self.settings.get('footer_left_label', ''))
        self.edit_f_right = QLineEdit(self.settings.get('footer_right_label', ''))
        footer_form.addRow("Début Tableau Y (cm):", self.sp_table_y)
        footer_form.addRow("Signature Gauche:", self.edit_f_left)
        footer_form.addRow("Signature Droite:", self.edit_f_right)
        tab_footer.setWidget(footer_content)
        tab_footer.setWidgetResizable(True)
        tabs.addTab(tab_footer, "Détails")

        vbox.addWidget(tabs)

        preview_group = QGroupBox("Aperçu en temps réel (Simulation A4)")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_canvas = LivePreviewCanvas(self.settings)
        preview_layout.addWidget(self.preview_canvas)

        main_layout.addWidget(control_panel)
        main_layout.addWidget(preview_group, stretch=1)

        self._connect_signals()
        self.btn_color.clicked.connect(self.pick_color)
        self.btn_banner.clicked.connect(self.pick_banner)
        self.sync_settings() # تفعيل العرض الأولي فوراً

    def _create_spin(self, min_v, max_v, current_v):
        sb = QDoubleSpinBox()
        sb.setRange(min_v, max_v)
        sb.setValue(float(current_v))
        sb.setSingleStep(0.1)
        sb.setSuffix(" cm")
        return sb

    def _connect_signals(self):
        txt_widgets = [self.edit_title, self.edit_bank, self.edit_rib, self.edit_f_left, self.edit_f_right]
        for w in txt_widgets: w.textChanged.connect(self.sync_settings)
        spin_widgets = [
            self.sp_banner_total_h, self.sp_img_x, self.sp_img_y, self.sp_img_w, self.sp_img_h,
            self.sp_bank_y, self.sp_dest_x, self.sp_dest_y, self.sp_dest_w, self.sp_table_y
        ]
        for s in spin_widgets: s.valueChanged.connect(self.sync_settings)

    def pick_banner(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choisir Banner", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self.settings['banner_path'] = path
            self.lbl_path.setText(os.path.basename(path))
            self.sync_settings()

    def pick_color(self):
        curr = self.settings.get('theme_color', "#0b666a")
        c = QColorDialog.getColor(QColor(curr), self)
        if c.isValid():
            self.settings['theme_color'] = c.name()
            self.color_preview.setStyleSheet(f"background-color: {c.name()}; border: 1px solid gray;")
            self.sync_settings()

    def sync_settings(self):
        self.settings.update({
            "doc_title": self.edit_title.text(),
            "banner_height_cm": self.sp_banner_total_h.value(),
            "banner_img_x_cm": self.sp_img_x.value(),
            "banner_img_y_cm": self.sp_img_y.value(),
            "banner_img_w_cm": self.sp_img_w.value(),
            "banner_img_h_cm": self.sp_img_h.value(),
            "bank_name": self.edit_bank.text(),
            "bank_acc": self.edit_rib.text(),
            "bank_y_offset_cm": self.sp_bank_y.value(),
            "dest_box_x_cm": self.sp_dest_x.value(),
            "dest_box_y_cm": self.sp_dest_y.value(),
            "dest_box_w_cm": self.sp_dest_w.value(),
            "table_start_y_cm": self.sp_table_y.value(),
            "footer_left_label": self.edit_f_left.text(),
            "footer_right_label": self.edit_f_right.text()
        })
        self.preview_canvas.settings = self.settings
        self.preview_canvas.update()
        self.settings_updated.emit(self.settings)

class LivePreviewCanvas(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.setMinimumSize(450, 600)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        scale = min(self.width() / 210, self.height() / 297) * 0.95
        p.translate(self.width() / 2, self.height() / 2)
        p.scale(scale, scale)
        p.translate(-105, -148.5)
        p.setBrush(Qt.white)
        p.setPen(QPen(Qt.black, 0.2))
        p.drawRect(0, 0, 210, 297)
        s = self.settings
        color = QColor(s.get('theme_color', "#0b666a"))
        total_h_mm = int(s.get('banner_height_cm', 4.8) * 10)
        p.save()
        p.setClipRect(0, 0, 210, total_h_mm)
        banner_path = s.get('banner_path', "")
        if banner_path and os.path.exists(banner_path):
            img_x = int(s.get('banner_img_x_cm', 0.0) * 10)
            img_y = int(s.get('banner_img_y_cm', 0.0) * 10)
            img_w = int(s.get('banner_img_w_cm', 21.0) * 10)
            img_h = int(s.get('banner_img_h_cm', 4.8) * 10)
            pixmap = QPixmap(banner_path)
            if not pixmap.isNull():
                p.drawPixmap(QRect(img_x, img_y, img_w, img_h), pixmap)
        else:
            p.setPen(QPen(Qt.lightGray, 0.5, Qt.DashLine))
            p.drawRect(0, 0, 210, total_h_mm)
            p.drawText(QRect(0, 0, 210, total_h_mm), Qt.AlignCenter, "Zone Image / Header")
        p.restore()
        p.setPen(color)
        p.setFont(QFont("Arial", 6, QFont.Bold))
        title_y = total_h_mm + 10
        p.drawText(15, title_y, f"{s.get('doc_title', 'Document')} N°: 0001")
        p.setPen(Qt.black)
        p.setFont(QFont("Arial", 3.5))
        bank_y = int(s.get('bank_y_offset_cm', 6.6) * 10)
        p.drawText(15, bank_y, f"Banque : {s.get('bank_name', '')}")
        p.drawText(15, bank_y + 4, f"N° Compte : {s.get('bank_acc', '')}")
        dx, dy, dw = int(s.get('dest_box_x_cm', 11.5) * 10), int(s.get('dest_box_y_cm', 6.0) * 10), int(s.get('dest_box_w_cm', 8.0) * 10)
        p.setBrush(QColor(245, 245, 245))
        p.setPen(QPen(Qt.lightGray, 0.2))
        p.drawRect(dx, dy, dw, 25)
        p.setPen(Qt.black)
        p.drawText(dx + 2, dy + 5, "Destinataire :")
        table_y = int(s.get('table_start_y_cm', 9.5) * 10)
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        p.drawRect(10, table_y, 190, 8)
        p.setPen(Qt.black)
        p.setFont(QFont("Arial", 4, QFont.Bold))
        p.drawText(15, 270, s.get('footer_left_label', ''))
        p.drawText(130, 270, s.get('footer_right_label', ''))