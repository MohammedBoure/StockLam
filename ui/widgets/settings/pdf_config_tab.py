import os
import json
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QGroupBox, QFormLayout, QDoubleSpinBox, 
    QFileDialog, QColorDialog, QTabWidget, QScrollArea, 
    QFrame, QMessageBox, QSizePolicy, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt, Signal, QRectF, QRect
from PySide6.QtGui import QColor, QPixmap, QFont, QPainter, QPen, QBrush

from .pdf_visual_editor import VisualPdfEditorDialog

class PdfConfigWidget(QWidget):
    settings_updated = Signal(dict)

    def __init__(self, data_manager=None):
        super().__init__()
        self.data_manager = data_manager
        self.new_image_bytes = None
        self.banner_pixmap = QPixmap()
        self.settings = self.load_settings()
        
        if self.data_manager and hasattr(self.data_manager, 'company_settings'):
            img_bytes = self.data_manager.company_settings.get_banner_image()
            if img_bytes:
                self.banner_pixmap.loadFromData(img_bytes)
            
        self.init_ui()

    def get_default_settings(self):
        return {
            "theme_color": "#0b666a",
            
            # Textes BL
            "doc_title_bl": "BON DE LIVRAISON",
            "dest_label_bl": "Destinataire :",
            "qty_header_bl": "Qté",
            "total_label_bl": "MONTANT TOTAL À PAYER",
            "footer_left_bl": "Responsable Stock",
            "footer_right_bl": "Accusé de réception (Client)",
            
            # Textes Retour
            "doc_title_rt": "BON DE RETOUR",
            "dest_label_rt": "Retourné à (Sous-traitant) :",
            "qty_header_rt": "Qté Rtr.",
            "total_label_rt": "VALEUR TOTALE DU RETOUR",
            "footer_left_rt": "Signature Magasin / Expéditeur",
            "footer_right_rt": "Accusé de Réception (Fournisseur)",

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
            
            "footer_y_offset_cm": 1.5,
            "footer_height_cm": 2.5,
            "footer_left_x_cm": 1.0,
            "footer_right_x_cm": 12.0
        }

    def load_settings(self):
        defaults = self.get_default_settings()
        if self.data_manager and hasattr(self.data_manager, 'company_settings'):
            try:
                db_settings = self.data_manager.company_settings.get_settings()
                if db_settings:
                    return {**defaults, **db_settings}
            except Exception as e:
                logging.error(f"Error loading PDF settings from DB: {e}")
        return defaults

    def get_updated_settings(self):
        return self.settings

    def save_settings(self):
        if self.data_manager and hasattr(self.data_manager, 'company_settings'):
            success = self.data_manager.company_settings.update_settings(self.settings, self.new_image_bytes)
            if success:
                self.new_image_bytes = None
            else:
                raise Exception("Échec de l'enregistrement dans la base de données.")
        else:
            raise Exception("Manager de base de données non disponible.")

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(15)

        control_panel = QWidget()
        control_panel.setFixedWidth(500)
        vbox = QVBoxLayout(control_panel)
        
        tabs = QTabWidget()
        tabs.setStyleSheet("QTabBar::tab { height: 30px; padding: 5px; font-weight: bold; }")

        # TAB 1: IDENTITÉ & IMAGE
        tab_branding = QScrollArea()
        branding_content = QWidget()
        branding_form = QFormLayout(branding_content)
        
        self.btn_color = QPushButton("Changer la couleur du thème")
        self.color_preview = QFrame()
        self.color_preview.setFixedSize(50, 20)
        self.color_preview.setStyleSheet(f"background-color: {self.settings.get('theme_color', '#0b666a')}; border: 1px solid gray;")
        
        self.btn_banner = QPushButton("Choisir l'image Banner...")
        self.lbl_path = QLabel("Image chargée depuis la BDD" if not self.banner_pixmap.isNull() else "Aucune image")
        self.lbl_path.setStyleSheet("color: #2c3e50; font-weight: bold; font-size: 10px;")
        
        self.sp_banner_total_h = self._create_spin(1.0, 15.0, self.settings.get('banner_height_cm', 4.8))
        self.sp_img_x = self._create_spin(-5.0, 21.0, self.settings.get('banner_img_x_cm', 0.0))
        self.sp_img_y = self._create_spin(-5.0, 10.0, self.settings.get('banner_img_y_cm', 0.0))
        self.sp_img_w = self._create_spin(1.0, 30.0, self.settings.get('banner_img_w_cm', 21.0))
        self.sp_img_h = self._create_spin(1.0, 15.0, self.settings.get('banner_img_h_cm', 4.8))

        branding_form.addRow("Couleur Thème:", self.btn_color)
        branding_form.addRow("Aperçu Couleur:", self.color_preview)
        branding_form.addRow(QLabel(""))
        branding_form.addRow("Image Banner:", self.btn_banner)
        branding_form.addRow("", self.lbl_path)
        branding_form.addRow("Hauteur Zone Header (cm):", self.sp_banner_total_h)
        branding_form.addRow("Position Image X (cm):", self.sp_img_x)
        branding_form.addRow("Position Image Y (cm):", self.sp_img_y)
        branding_form.addRow("Largeur Image (cm):", self.sp_img_w)
        branding_form.addRow("Hauteur Image (cm):", self.sp_img_h)

        tab_branding.setWidget(branding_content)
        tab_branding.setWidgetResizable(True)
        tabs.addTab(tab_branding, "1. Identité")

        # TAB 2: TEXTES BL
        tab_bl = QScrollArea()
        bl_content = QWidget()
        bl_form = QFormLayout(bl_content)
        
        self.edit_title_bl = QLineEdit(self.settings.get('doc_title_bl', ''))
        self.edit_dest_bl = QLineEdit(self.settings.get('dest_label_bl', ''))
        self.edit_qty_bl = QLineEdit(self.settings.get('qty_header_bl', ''))
        self.edit_tot_bl = QLineEdit(self.settings.get('total_label_bl', ''))
        
        bl_form.addRow("Titre Document:", self.edit_title_bl)
        bl_form.addRow("Label Destinataire:", self.edit_dest_bl)
        bl_form.addRow("En-tête Quantité:", self.edit_qty_bl)
        bl_form.addRow("Label Total:", self.edit_tot_bl)
        
        tab_bl.setWidget(bl_content)
        tab_bl.setWidgetResizable(True)
        tabs.addTab(tab_bl, "2. Textes B.L.")

        # TAB 3: TEXTES RETOUR
        tab_rt = QScrollArea()
        rt_content = QWidget()
        rt_form = QFormLayout(rt_content)
        
        self.edit_title_rt = QLineEdit(self.settings.get('doc_title_rt', ''))
        self.edit_dest_rt = QLineEdit(self.settings.get('dest_label_rt', ''))
        self.edit_qty_rt = QLineEdit(self.settings.get('qty_header_rt', ''))
        self.edit_tot_rt = QLineEdit(self.settings.get('total_label_rt', ''))
        
        rt_form.addRow("Titre Document:", self.edit_title_rt)
        rt_form.addRow("Label Retourné à:", self.edit_dest_rt)
        rt_form.addRow("En-tête Quantité:", self.edit_qty_rt)
        rt_form.addRow("Label Total:", self.edit_tot_rt)
        
        tab_rt.setWidget(rt_content)
        tab_rt.setWidgetResizable(True)
        tabs.addTab(tab_rt, "3. Textes Retour")

        # TAB 4: POSITIONS
        tab_pos = QScrollArea()
        pos_content = QWidget()
        pos_form = QFormLayout(pos_content)
        
        self.edit_bank = QLineEdit(self.settings.get('bank_name', ''))
        self.edit_rib = QLineEdit(self.settings.get('bank_acc', ''))
        self.sp_bank_y = self._create_spin(0, 25, self.settings.get('bank_y_offset_cm', 6.6))
        
        self.sp_dest_x = self._create_spin(0, 21, self.settings.get('dest_box_x_cm', 11.5))
        self.sp_dest_y = self._create_spin(0, 29, self.settings.get('dest_box_y_cm', 6.0))
        self.sp_dest_w = self._create_spin(1, 15, self.settings.get('dest_box_w_cm', 8.0))
        self.sp_table_y = self._create_spin(5, 25, self.settings.get('table_start_y_cm', 9.5))
        self.sp_footer_y = self._create_spin(0, 10, self.settings.get('footer_y_offset_cm', 1.5))
        self.sp_footer_h = self._create_spin(1, 15, self.settings.get('footer_height_cm', 2.5))
        self.sp_footer_left_x = self._create_spin(0, 21, self.settings.get('footer_left_x_cm', 1.0))
        self.sp_footer_right_x = self._create_spin(0, 21, self.settings.get('footer_right_x_cm', 12.0))
        
        pos_form.addRow("Nom Banque:", self.edit_bank)
        pos_form.addRow("N° Compte (RIB):", self.edit_rib)
        pos_form.addRow("Position Banque Y (cm):", self.sp_bank_y)
        pos_form.addRow(QLabel(""))
        pos_form.addRow("Boîte Destinataire X (cm):", self.sp_dest_x)
        pos_form.addRow("Boîte Destinataire Y (cm):", self.sp_dest_y)
        pos_form.addRow("Largeur Boîte (cm):", self.sp_dest_w)
        pos_form.addRow(QLabel(""))
        pos_form.addRow("Début Tableau Y (cm):", self.sp_table_y)
        
        tab_pos.setWidget(pos_content)
        tab_pos.setWidgetResizable(True)
        tabs.addTab(tab_pos, "4. Mise en page")

        # TAB 5: SIGNATURES
        tab_sig = QScrollArea()
        sig_content = QWidget()
        sig_form = QFormLayout(sig_content)
        
        self.edit_fl_bl = QLineEdit(self.settings.get('footer_left_bl', ''))
        self.edit_fr_bl = QLineEdit(self.settings.get('footer_right_bl', ''))
        self.edit_fl_rt = QLineEdit(self.settings.get('footer_left_rt', ''))
        self.edit_fr_rt = QLineEdit(self.settings.get('footer_right_rt', ''))
        
        sig_form.addRow(QLabel("--- Textes B.L. ---"))
        sig_form.addRow("Signature Gauche:", self.edit_fl_bl)
        sig_form.addRow("Signature Droite:", self.edit_fr_bl)
        sig_form.addRow(QLabel("--- Textes Retour ---"))
        sig_form.addRow("Signature Gauche:", self.edit_fl_rt)
        sig_form.addRow("Signature Droite:", self.edit_fr_rt)
        sig_form.addRow(QLabel("--- Positionnement ---"))
        sig_form.addRow("Signature Gauche X (cm):", self.sp_footer_left_x)
        sig_form.addRow("Signature Droite X (cm):", self.sp_footer_right_x)
        sig_form.addRow("Signatures Y Offset (cm):", self.sp_footer_y)
        sig_form.addRow("Hauteur de la Signature (cm):", self.sp_footer_h)
        
        tab_sig.setWidget(sig_content)
        tab_sig.setWidgetResizable(True)
        tabs.addTab(tab_sig, "5. Signatures")

        # TAB 6: ÉDITEUR VISUEL (WYSIWYG)
        tab_wy = QWidget()
        wy_layout = QVBoxLayout(tab_wy)
        wy_lbl = QLabel("<h3>Éditeur Visuel Interactif (WYSIWYG)</h3><p>Vous manquez d'espace ? Cliquez sur le bouton ci-dessous pour ouvrir l'éditeur de PDF dans une nouvelle fenêtre plein écran où vous pourrez ajuster tous vos éléments à la souris avec précision.</p>")
        wy_lbl.setWordWrap(True)
        wy_lbl.setAlignment(Qt.AlignCenter)
        
        self.btn_open_visual = QPushButton("🚀 Ouvrir l'Éditeur Visuel Plein Écran")
        self.btn_open_visual.setStyleSheet("background-color: #9b59b6; color: white; font-weight: bold; padding: 15px; font-size: 16px; border-radius: 5px;")
        self.btn_open_visual.setCursor(Qt.PointingHandCursor)
        self.btn_open_visual.clicked.connect(self.open_visual_editor_dialog)
        
        wy_layout.addStretch()
        wy_layout.addWidget(wy_lbl)
        wy_layout.addWidget(self.btn_open_visual)
        wy_layout.addStretch()
        
        tabs.addTab(tab_wy, "6. Éditeur Visuel (WYSIWYG)")

        vbox.addWidget(tabs)

        # Aperçu en temps réel
        preview_group = QGroupBox("Aperçu en temps réel (Simulation A4)")
        preview_layout = QVBoxLayout(preview_group)
        
        # Toggle BL / Retour
        toggle_layout = QHBoxLayout()
        self.rb_bl = QRadioButton("Aperçu: Bon de Livraison")
        self.rb_rt = QRadioButton("Aperçu: Bon de Retour")
        self.rb_bl.setChecked(True)
        toggle_group = QButtonGroup(self)
        toggle_group.addButton(self.rb_bl)
        toggle_group.addButton(self.rb_rt)
        toggle_layout.addWidget(self.rb_bl)
        toggle_layout.addWidget(self.rb_rt)
        toggle_layout.addStretch()
        
        preview_layout.addLayout(toggle_layout)
        
        self.preview_canvas = LivePreviewCanvas(self.settings)
        self.preview_canvas.banner_pixmap = self.banner_pixmap
        preview_layout.addWidget(self.preview_canvas)

        main_layout.addWidget(control_panel)
        main_layout.addWidget(preview_group, stretch=1)

        self._connect_signals()
        self.btn_color.clicked.connect(self.pick_color)
        self.btn_banner.clicked.connect(self.pick_banner)
        self.rb_bl.toggled.connect(self.update_preview_mode)
        
        self.sync_settings() 

    def _create_spin(self, min_v, max_v, current_v):
        sb = QDoubleSpinBox()
        sb.setRange(min_v, max_v)
        sb.setValue(float(current_v))
        sb.setSingleStep(0.1)
        sb.setSuffix(" cm")
        return sb

    def _connect_signals(self):
        txt_widgets = [
            self.edit_bank, self.edit_rib, self.edit_title_bl, self.edit_title_rt,
            self.edit_dest_bl, self.edit_dest_rt, self.edit_qty_bl, self.edit_qty_rt,
            self.edit_tot_bl, self.edit_tot_rt, self.edit_fl_bl, self.edit_fr_bl,
            self.edit_fl_rt, self.edit_fr_rt
        ]
        for w in txt_widgets: w.textChanged.connect(self.sync_settings)

        spin_widgets = [
            self.sp_banner_total_h, self.sp_img_x, self.sp_img_y, self.sp_img_w, self.sp_img_h,
            self.sp_bank_y, self.sp_dest_x, self.sp_dest_y, self.sp_dest_w, self.sp_table_y,
            self.sp_footer_y, self.sp_footer_h, self.sp_footer_left_x, self.sp_footer_right_x
        ]
        for s in spin_widgets: s.valueChanged.connect(self.sync_settings)

    def open_visual_editor_dialog(self):
        dialog = VisualPdfEditorDialog(self.settings, self)
        dialog.settings_changed.connect(self.on_visual_editor_changed)
        dialog.exec_()
        
    def on_visual_editor_changed(self, new_settings):
        # Update spinboxes from visual editor WITHOUT triggering a loop
        self.settings.update(new_settings)
        
        # Block signals temporarily
        self.sp_dest_x.blockSignals(True)
        self.sp_dest_y.blockSignals(True)
        self.sp_footer_left_x.blockSignals(True)
        self.sp_footer_right_x.blockSignals(True)
        
        self.sp_dest_x.setValue(self.settings.get('dest_box_x_cm', 11.5))
        self.sp_dest_y.setValue(self.settings.get('dest_box_y_cm', 6.0))
        self.sp_footer_left_x.setValue(self.settings.get('footer_left_x_cm', 1.0))
        self.sp_footer_right_x.setValue(self.settings.get('footer_right_x_cm', 12.0))
        
        self.sp_dest_x.blockSignals(False)
        self.sp_dest_y.blockSignals(False)
        self.sp_footer_left_x.blockSignals(False)
        self.sp_footer_right_x.blockSignals(False)
        
        # Update the live preview canvas
        self.preview_canvas.settings = self.settings
        self.preview_canvas.update()
        self.settings_updated.emit(self.settings)

    def pick_banner(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choisir Banner", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self.lbl_path.setText(os.path.basename(path))
            try:
                img = QImage(path)
                if img.width() > 1500:
                    img = img.scaledToWidth(1500, Qt.SmoothTransformation)
                ba = QByteArray()
                buffer = QBuffer(ba)
                buffer.open(QIODevice.WriteOnly)
                img.save(buffer, "JPEG", 85)
                self.new_image_bytes = ba.data()
                
                self.banner_pixmap.loadFromData(self.new_image_bytes)
                self.preview_canvas.banner_pixmap = self.banner_pixmap
            except Exception as e:
                logging.error(f"Error reading and compressing image: {e}")
            self.sync_settings()

    def pick_color(self):
        curr = self.settings.get('theme_color', "#0b666a")
        c = QColorDialog.getColor(QColor(curr), self)
        if c.isValid():
            self.settings['theme_color'] = c.name()
            self.color_preview.setStyleSheet(f"background-color: {c.name()}; border: 1px solid gray;")
            self.sync_settings()

    def update_preview_mode(self):
        is_retour = self.rb_rt.isChecked()
        self.preview_canvas.is_retour = is_retour
        self.preview_canvas.update()

    def sync_settings(self):
        self.settings.update({
            "doc_title_bl": self.edit_title_bl.text(),
            "dest_label_bl": self.edit_dest_bl.text(),
            "qty_header_bl": self.edit_qty_bl.text(),
            "total_label_bl": self.edit_tot_bl.text(),
            "footer_left_bl": self.edit_fl_bl.text(),
            "footer_right_bl": self.edit_fr_bl.text(),
            
            "doc_title_rt": self.edit_title_rt.text(),
            "dest_label_rt": self.edit_dest_rt.text(),
            "qty_header_rt": self.edit_qty_rt.text(),
            "total_label_rt": self.edit_tot_rt.text(),
            "footer_left_rt": self.edit_fl_rt.text(),
            "footer_right_rt": self.edit_fr_rt.text(),
            
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
            "footer_y_offset_cm": self.sp_footer_y.value(),
            "footer_height_cm": self.sp_footer_h.value(),
            "footer_left_x_cm": self.sp_footer_left_x.value(),
            "footer_right_x_cm": self.sp_footer_right_x.value()
        })
        self.preview_canvas.settings = self.settings
        self.preview_canvas.update()
        self.settings_updated.emit(self.settings)

class LivePreviewCanvas(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.is_retour = False
        self.setMinimumSize(450, 600)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        scale = min(self.width() / 210, self.height() / 297) * 0.95
        p.translate(self.width() / 2, self.height() / 2)
        p.scale(scale, scale)
        p.translate(-105, -148.5)
        
        # Draw paper
        p.setBrush(Qt.white)
        p.setPen(QPen(Qt.black, 0.2))
        p.drawRect(0, 0, 210, 297)
        
        s = self.settings
        color = QColor(s.get('theme_color', "#0b666a"))
        total_h_mm = int(s.get('banner_height_cm', 4.8) * 10)
        
        # Banner image
        p.save()
        p.setClipRect(0, 0, 210, total_h_mm)
        pixmap = getattr(self, 'banner_pixmap', QPixmap())
        if not pixmap.isNull():
            img_x = int(s.get('banner_img_x_cm', 0.0) * 10)
            img_y = int(s.get('banner_img_y_cm', 0.0) * 10)
            img_w = int(s.get('banner_img_w_cm', 21.0) * 10)
            img_h = int(s.get('banner_img_h_cm', 4.8) * 10)
            p.drawPixmap(QRect(img_x, img_y, img_w, img_h), pixmap)
        else:
            p.setPen(QPen(Qt.lightGray, 0.5, Qt.DashLine))
            p.drawRect(0, 0, 210, total_h_mm)
            p.drawText(QRect(0, 0, 210, total_h_mm), Qt.AlignCenter, "Zone Image / Header")
        p.restore()
        
        # Get dynamic texts
        title = s.get('doc_title_rt', 'BON DE RETOUR') if self.is_retour else s.get('doc_title_bl', 'BON DE LIVRAISON')
        dest_label = s.get('dest_label_rt', 'Retourné à (Sous-traitant) :') if self.is_retour else s.get('dest_label_bl', 'Destinataire :')
        f_left = s.get('footer_left_rt', 'Signature Magasin / Expéditeur') if self.is_retour else s.get('footer_left_bl', 'Responsable Stock')
        f_right = s.get('footer_right_rt', 'Accusé de Réception (Fournisseur)') if self.is_retour else s.get('footer_right_bl', 'Accusé de réception (Client)')
        
        # Title
        p.setPen(color)
        p.setFont(QFont("Arial", 6, QFont.Bold))
        title_y = total_h_mm + 10
        p.drawText(15, title_y, f"{title} N°: 2026/001")
        
        # Bank
        p.setPen(Qt.black)
        p.setFont(QFont("Arial", 3.5))
        bank_y = int(s.get('bank_y_offset_cm', 6.6) * 10)
        p.drawText(15, bank_y, f"Banque : {s.get('bank_name', '')}")
        p.drawText(15, bank_y + 4, f"N° Compte : {s.get('bank_acc', '')}")
        
        # Destinataire Box
        dx, dy, dw = int(s.get('dest_box_x_cm', 11.5) * 10), int(s.get('dest_box_y_cm', 6.0) * 10), int(s.get('dest_box_w_cm', 8.0) * 10)
        p.setBrush(QColor(245, 245, 245))
        p.setPen(QPen(Qt.lightGray, 0.2))
        p.drawRect(dx, dy, dw, 25)
        p.setPen(Qt.black)
        p.drawText(dx + 2, dy + 5, dest_label)
        p.drawText(dx + 2, dy + 10, "Nom du Partenaire")
        p.drawText(dx + 2, dy + 14, "NIF : 123456789")
        
        # Table
        table_y = int(s.get('table_start_y_cm', 9.5) * 10)
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        p.drawRect(10, table_y, 190, 8)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(Qt.lightGray, 0.5))
        p.drawRect(10, table_y + 8, 190, 50) # fake table body
        
        # Footer
        table_end_y = table_y + 58
        f_offset_y = int(s.get('footer_y_offset_cm', 1.5) * 10)
        signature_y = table_end_y + f_offset_y
        
        f_left_x = int(s.get('footer_left_x_cm', 1.0) * 10)
        f_right_x = int(s.get('footer_right_x_cm', 12.0) * 10)
        f_height = int(s.get('footer_height_cm', 2.5) * 10)
        
        p.setPen(Qt.black)
        p.drawText(f_left_x, signature_y, f_left)
        p.drawText(f_right_x, signature_y, f_right)
        
        # Visualize signature height box
        p.setPen(QPen(Qt.gray, 0.2, Qt.DashLine))
        p.drawRect(f_left_x, signature_y, 60, f_height)
        p.drawRect(f_right_x, signature_y, 60, f_height)