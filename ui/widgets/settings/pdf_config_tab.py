import os
import logging
from uuid import uuid4

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QGroupBox, QFormLayout, QDoubleSpinBox, 
    QFileDialog, QColorDialog, QTabWidget, QScrollArea, 
    QFrame, QMessageBox, QSizePolicy, QRadioButton, QButtonGroup,
    QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, Signal, QRectF, QRect, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QColor, QPixmap, QFont, QPainter, QPen, QBrush, QImage

from .pdf_visual_editor import VisualPdfEditorDialog
from .local_settings import LocalSettingsStore
from .pdf_stamp import FOOTER_TITLE_HEIGHT_CM, fit_stamp_size_cm

class PdfConfigWidget(QWidget):
    settings_updated = Signal(dict)

    def __init__(
        self,
        data_manager=None,
        current_user=None,
        can_manage_stamps=None,
        local_store=None,
    ):
        super().__init__()
        self.data_manager = data_manager
        self.current_user = current_user or getattr(data_manager, "current_user", None)
        self.can_manage_stamps = (
            bool(can_manage_stamps)
            if can_manage_stamps is not None
            else bool(getattr(data_manager, "can_manage_stamps", False))
        )
        self.local_store = local_store or LocalSettingsStore(self.current_user)
        self.new_image_bytes = None
        self.clear_banner_on_save = False
        self.banner_pixmap = QPixmap()
        self.stamps = []
        self.current_stamp_id = None
        self.settings = self.load_settings()

        img_bytes = self.local_store.load_banner_bytes(self.settings)
        if img_bytes:
            self.banner_pixmap.loadFromData(img_bytes)

        self.stamps = self.load_stamps()
            
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
            "footer_right_x_cm": 12.0,
            "footer_stamp_gap_cm": 0.3,
            "footer_stamp_area_w_cm": 6.0,
            "footer_stamp_area_h_cm": 3.5
        }

    def load_settings(self):
        defaults = self.get_default_settings()
        return self.local_store.load_pdf(defaults)

    def load_stamps(self):
        return self.local_store.load_stamps()

    def refresh_stamp_list(self, select_id=None, reload=True):
        if not hasattr(self, "list_stamps"):
            return

        if reload:
            self.stamps = self.load_stamps()
        self.list_stamps.blockSignals(True)
        self.list_stamps.clear()

        active_id = next(
            (str(stamp["Stamp_ID"]) for stamp in self.stamps if stamp.get("Is_Active")),
            None,
        )
        row_to_select = None
        for row, stamp in enumerate(self.stamps):
            stamp_id = str(stamp["Stamp_ID"])
            active_marker = " [ACTIF]" if stamp_id == active_id else ""
            item = QListWidgetItem(f"{stamp.get('Stamp_Name') or 'Cachet'}{active_marker}")
            item.setData(Qt.UserRole, stamp_id)
            self.list_stamps.addItem(item)
            if select_id is not None and stamp_id == str(select_id):
                row_to_select = row

        if row_to_select is None and self.stamps:
            row_to_select = next(
                (row for row, stamp in enumerate(self.stamps) if stamp.get("Is_Active")),
                0,
            )
        self.list_stamps.blockSignals(False)

        if row_to_select is None:
            self.on_stamp_selected(-1)
        else:
            self.list_stamps.setCurrentRow(row_to_select)

    def on_stamp_selected(self, row):
        if row < 0 or row >= len(self.stamps):
            self.current_stamp_id = None
            self.stamp_preview.setText("Aucun cachet sélectionné")
            self.stamp_preview.setPixmap(QPixmap())
            self.preview_canvas.active_stamp = None
            self.preview_canvas.active_stamp_pixmap = QPixmap()
            self.preview_canvas.update()
            return

        stamp = self.stamps[row]
        self.current_stamp_id = str(stamp["Stamp_ID"])
        controls = (
            self.edit_stamp_name,
            self.sp_stamp_x,
            self.sp_stamp_y,
            self.sp_stamp_w,
            self.sp_stamp_h,
        )
        for control in controls:
            control.blockSignals(True)
        self.edit_stamp_name.setText(str(stamp.get("Stamp_Name") or "Cachet"))
        self.sp_stamp_x.setValue(float(stamp.get("Position_X_CM") or 0.0))
        self.sp_stamp_y.setValue(float(stamp.get("Position_Y_CM") or 0.0))
        self.sp_stamp_w.setValue(float(stamp.get("Width_CM") or 4.0))
        self.sp_stamp_h.setValue(float(stamp.get("Height_CM") or 4.0))
        for control in controls:
            control.blockSignals(False)

        image = QPixmap()
        image_bytes = stamp.get("Image_Data")
        if image_bytes:
            image.loadFromData(bytes(image_bytes))
        self.lbl_stamp_file.setText("Image PNG enregistrée localement")
        self.stamp_preview.setText("" if not image.isNull() else "Image PNG invalide")
        self.stamp_preview.setPixmap(
            image.scaled(180, 130, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if not image.isNull() else QPixmap()
        )
        self.preview_canvas.active_stamp = stamp
        self.preview_canvas.active_stamp_pixmap = image
        self.preview_canvas.update()

    def update_stamp_preview(self):
        if self.current_stamp_id is None:
            return
        stamp = next(
            (entry for entry in self.stamps if str(entry["Stamp_ID"]) == self.current_stamp_id),
            None,
        )
        if stamp is None:
            return
        stamp.update({
            "Stamp_Name": self.edit_stamp_name.text(),
            "Position_X_CM": self.sp_stamp_x.value(),
            "Position_Y_CM": self.sp_stamp_y.value(),
            "Width_CM": self.sp_stamp_w.value(),
            "Height_CM": self.sp_stamp_h.value(),
        })
        self.preview_canvas.active_stamp = stamp
        self.preview_canvas.update()

    def add_stamp(self):
        if not self.can_manage_stamps:
            QMessageBox.warning(self, "Cachets", "Vous n'avez pas la permission de gérer les cachets.")
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir un cachet PNG",
            "",
            "Images PNG (*.png)",
        )
        if not path:
            return

        try:
            with open(path, "rb") as image_file:
                image_bytes = image_file.read()
            image = QPixmap()
            if not image.loadFromData(image_bytes):
                raise ValueError("Le fichier sélectionné n'est pas une image PNG valide.")

            stamp_id = uuid4().hex
            self.stamps.append({
                "Stamp_ID": stamp_id,
                "Stamp_Name": os.path.splitext(os.path.basename(path))[0][:150],
                "Image_Data": image_bytes,
                "Position_X_CM": 13.0,
                "Position_Y_CM": 22.0,
                "Width_CM": 4.0,
                "Height_CM": 4.0,
                "Is_Active": not self.stamps,
            })
            self.refresh_stamp_list(select_id=stamp_id, reload=False)
        except Exception as exc:
            logging.error(f"Error adding PDF stamp: {exc}")
            QMessageBox.critical(self, "Cachets", f"Échec de l'ajout du cachet :\n{exc}")

    def save_current_stamp(self, show_message=True):
        if self.current_stamp_id is None:
            return False

        stamp_name = self.edit_stamp_name.text().strip()
        if not stamp_name:
            QMessageBox.warning(self, "Cachets", "Donnez un nom au cachet.")
            return False

        stamp = next(
            (entry for entry in self.stamps if str(entry.get("Stamp_ID")) == self.current_stamp_id),
            None,
        )
        if stamp is None:
            QMessageBox.critical(self, "Cachets", "Impossible de trouver le cachet sélectionné.")
            return False
        stamp.update({
            "Stamp_Name": stamp_name,
            "Position_X_CM": self.sp_stamp_x.value(),
            "Position_Y_CM": self.sp_stamp_y.value(),
            "Width_CM": self.sp_stamp_w.value(),
            "Height_CM": self.sp_stamp_h.value(),
        })

        self.refresh_stamp_list(select_id=self.current_stamp_id, reload=False)
        if show_message:
            QMessageBox.information(self, "Cachets", "Les proprietes du cachet ont ete enregistrees.")
        return True

    def activate_stamp(self):
        if self.current_stamp_id is None:
            return
        if not self.save_current_stamp(show_message=False):
            return
        found = False
        for stamp in self.stamps:
            active = str(stamp.get("Stamp_ID")) == self.current_stamp_id
            stamp["Is_Active"] = active
            found = found or active
        if found:
            self.refresh_stamp_list(select_id=self.current_stamp_id, reload=False)

    def delete_stamp(self):
        if not self.can_manage_stamps:
            QMessageBox.warning(self, "Cachets", "Vous n'avez pas la permission de gérer les cachets.")
            return
        if self.current_stamp_id is None:
            return
        reply = QMessageBox.question(
            self,
            "Supprimer le cachet",
            "Supprimer définitivement le cachet sélectionné ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        stamp_id = self.current_stamp_id
        remaining = [
            stamp for stamp in self.stamps
            if str(stamp.get("Stamp_ID")) != stamp_id
        ]
        if len(remaining) == len(self.stamps):
            QMessageBox.warning(self, "Cachets", "Impossible de supprimer le cachet.")
            return
        if remaining and not any(stamp.get("Is_Active") for stamp in remaining):
            remaining[0]["Is_Active"] = True
        self.stamps = remaining
        self.current_stamp_id = None
        self.refresh_stamp_list(reload=False)

    def get_updated_settings(self):
        return self.settings

    def load_settings_into_widgets(self):
        """Apply an in-memory settings snapshot to the already-built editor."""
        text_fields = {
            "edit_bank": "bank_name",
            "edit_rib": "bank_acc",
            "edit_title_bl": "doc_title_bl",
            "edit_dest_bl": "dest_label_bl",
            "edit_qty_bl": "qty_header_bl",
            "edit_tot_bl": "total_label_bl",
            "edit_fl_bl": "footer_left_bl",
            "edit_fr_bl": "footer_right_bl",
            "edit_title_rt": "doc_title_rt",
            "edit_dest_rt": "dest_label_rt",
            "edit_qty_rt": "qty_header_rt",
            "edit_tot_rt": "total_label_rt",
            "edit_fl_rt": "footer_left_rt",
            "edit_fr_rt": "footer_right_rt",
        }
        spin_fields = {
            "sp_banner_total_h": "banner_height_cm",
            "sp_img_x": "banner_img_x_cm",
            "sp_img_y": "banner_img_y_cm",
            "sp_img_w": "banner_img_w_cm",
            "sp_img_h": "banner_img_h_cm",
            "sp_bank_y": "bank_y_offset_cm",
            "sp_dest_x": "dest_box_x_cm",
            "sp_dest_y": "dest_box_y_cm",
            "sp_dest_w": "dest_box_w_cm",
            "sp_table_y": "table_start_y_cm",
            "sp_footer_y": "footer_y_offset_cm",
            "sp_footer_h": "footer_height_cm",
            "sp_footer_left_x": "footer_left_x_cm",
            "sp_footer_right_x": "footer_right_x_cm",
            "sp_footer_stamp_gap": "footer_stamp_gap_cm",
            "sp_footer_stamp_w": "footer_stamp_area_w_cm",
            "sp_footer_stamp_h": "footer_stamp_area_h_cm",
        }

        controls = [getattr(self, name) for name in text_fields]
        controls += [getattr(self, name) for name in spin_fields]
        for control in controls:
            control.blockSignals(True)
        try:
            for widget_name, setting_name in text_fields.items():
                getattr(self, widget_name).setText(str(self.settings.get(setting_name, "")))
            for widget_name, setting_name in spin_fields.items():
                getattr(self, widget_name).setValue(float(self.settings.get(setting_name, 0.0)))
        finally:
            for control in controls:
                control.blockSignals(False)

        self.color_preview.setStyleSheet(
            f"background-color: {self.settings.get('theme_color', '#0b666a')}; border: 1px solid gray;"
        )
        self.preview_canvas.settings = self.settings
        self.preview_canvas.banner_pixmap = self.banner_pixmap
        self.preview_canvas.update()
        self.sync_settings()

    def load_from_database(self):
        """Read DB settings into the dialog without persisting them locally."""
        manager = getattr(self.data_manager, "company_settings", None)
        if manager is None:
            QMessageBox.warning(self, "Configuration PDF", "Le gestionnaire des paramètres de la base de données est indisponible.")
            return False

        try:
            db_settings = manager.get_settings() or {}
            self.settings = {**self.get_default_settings(), **db_settings}

            banner_bytes = manager.get_banner_image()
            self.new_image_bytes = bytes(banner_bytes) if banner_bytes else None
            self.clear_banner_on_save = not bool(self.new_image_bytes)
            self.banner_pixmap = QPixmap()
            if self.new_image_bytes:
                self.banner_pixmap.loadFromData(self.new_image_bytes)
            self.lbl_path.setText(
                "Image chargée depuis la base de données" if not self.banner_pixmap.isNull() else "Aucune image"
            )

            self.stamps = self.local_store.import_database_stamps(
                manager.get_stamps(include_image=True)
            )
            active_id = next(
                (stamp["Stamp_ID"] for stamp in self.stamps if stamp.get("Is_Active")),
                None,
            )
            self.current_stamp_id = None
            self.load_settings_into_widgets()
            self.refresh_stamp_list(select_id=active_id, reload=False)
            return True
        except Exception as exc:
            logging.error(f"Error loading PDF settings from database: {exc}")
            QMessageBox.critical(self, "Configuration PDF", f"Échec du chargement depuis la base :\n{exc}")
            return False

    def save_settings(self):
        """Save this user's PDF settings and stamp library locally only."""
        if self.current_stamp_id is not None and not self.save_current_stamp(show_message=False):
            raise Exception("Échec de l'enregistrement du cachet sélectionné.")
        banner_bytes = self.new_image_bytes
        if banner_bytes is None and not self.clear_banner_on_save:
            banner_bytes = self.local_store.load_banner_bytes(self.settings)
        self.local_store.save_pdf(
            self.settings,
            banner_bytes=banner_bytes,
            clear_banner=self.clear_banner_on_save,
        )
        self.local_store.save_stamps(self.stamps)
        self.new_image_bytes = None
        self.clear_banner_on_save = False

    def save_to_database(self):
        """Save the shared PDF layout and banner to the database on explicit request."""
        manager = getattr(self.data_manager, "company_settings", None)
        if manager is None or not hasattr(manager, "update_settings"):
            raise Exception("Le gestionnaire des paramètres PDF de la base de données est indisponible.")

        self.sync_settings()
        banner_bytes = self.new_image_bytes
        if banner_bytes is None and not self.clear_banner_on_save:
            banner_bytes = self.local_store.load_banner_bytes(self.settings)

        success = manager.update_settings(
            dict(self.settings),
            bytes(banner_bytes) if banner_bytes else None,
            clear_banner=self.clear_banner_on_save,
        )
        if not success:
            raise Exception("Échec de l'enregistrement des paramètres PDF dans la base de données.")

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(15)

        control_panel = QWidget()
        control_panel.setMinimumWidth(500)
        vbox = QVBoxLayout(control_panel)
        
        self.tabs = QTabWidget()
        tabs = self.tabs
        tabs.setStyleSheet("QTabBar::tab { height: 30px; padding: 5px; font-weight: bold; }")
        tabs.tabBar().hide()

        # TAB 1: IDENTITÉ & IMAGE
        tab_branding = QScrollArea()
        branding_content = QWidget()
        branding_form = QFormLayout(branding_content)
        
        self.btn_color = QPushButton("Changer la couleur du thème")
        self.color_preview = QFrame()
        self.color_preview.setFixedSize(50, 20)
        self.color_preview.setStyleSheet(f"background-color: {self.settings.get('theme_color', '#0b666a')}; border: 1px solid gray;")
        
        self.btn_banner = QPushButton("Choisir l'image de l'en-tête...")
        self.lbl_path = QLabel("Image locale chargée" if not self.banner_pixmap.isNull() else "Aucune image")
        self.lbl_path.setStyleSheet("color: #2c3e50; font-weight: bold; font-size: 10px;")
        
        self.sp_banner_total_h = self._create_spin(1.0, 15.0, self.settings.get('banner_height_cm', 4.8))
        self.sp_img_x = self._create_spin(-5.0, 21.0, self.settings.get('banner_img_x_cm', 0.0))
        self.sp_img_y = self._create_spin(-5.0, 10.0, self.settings.get('banner_img_y_cm', 0.0))
        self.sp_img_w = self._create_spin(1.0, 30.0, self.settings.get('banner_img_w_cm', 21.0))
        self.sp_img_h = self._create_spin(1.0, 15.0, self.settings.get('banner_img_h_cm', 4.8))

        branding_form.addRow("Couleur Thème:", self.btn_color)
        branding_form.addRow("Aperçu Couleur:", self.color_preview)
        branding_form.addRow(QLabel(""))
        branding_form.addRow("Image de l'en-tête :", self.btn_banner)
        branding_form.addRow("", self.lbl_path)
        branding_form.addRow("Hauteur de la zone d'en-tête (cm):", self.sp_banner_total_h)
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
        self.sp_footer_stamp_gap = self._create_spin(0, 5, self.settings.get('footer_stamp_gap_cm', 0.3))
        self.sp_footer_stamp_w = self._create_spin(1, 21, self.settings.get('footer_stamp_area_w_cm', 6.0))
        self.sp_footer_stamp_h = self._create_spin(1, 15, self.settings.get('footer_stamp_area_h_cm', 3.5))
        
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
        sig_form.addRow(QLabel("--- Zone du cachet sous « Responsable Stock » ---"))
        sig_form.addRow("Espace sous le titre (cm):", self.sp_footer_stamp_gap)
        sig_form.addRow("Largeur de la zone du cachet (cm):", self.sp_footer_stamp_w)
        sig_form.addRow("Hauteur de la zone du cachet (cm):", self.sp_footer_stamp_h)
        
        tab_sig.setWidget(sig_content)
        tab_sig.setWidgetResizable(True)
        tabs.addTab(tab_sig, "5. Signatures")

        # TAB 6: BIBLIOTHEQUE DES CACHETS PNG
        tab_stamps = QWidget()
        stamps_layout = QVBoxLayout(tab_stamps)
        stamps_group = QGroupBox("Bibliothèque des cachets PNG")
        stamps_group_layout = QVBoxLayout(stamps_group)

        stamps_top = QHBoxLayout()
        self.list_stamps = QListWidget()
        self.list_stamps.setMinimumHeight(135)
        self.list_stamps.setToolTip("Ajoutez plusieurs cachets ; un seul est actif à la fois dans les PDF.")

        self.stamp_preview = QLabel("Aucun cachet sélectionné")
        self.stamp_preview.setAlignment(Qt.AlignCenter)
        self.stamp_preview.setMinimumSize(180, 130)
        self.stamp_preview.setStyleSheet(
            "border: 1px dashed #95a5a6; background: #f8f9f9; padding: 8px;"
        )
        stamps_top.addWidget(self.list_stamps, stretch=1)
        stamps_top.addWidget(self.stamp_preview)
        stamps_group_layout.addLayout(stamps_top)

        stamps_actions = QHBoxLayout()
        self.btn_add_stamp = QPushButton("Ajouter un cachet PNG")
        self.btn_delete_stamp = QPushButton("Supprimer le cachet")
        self.btn_activate_stamp = QPushButton("Définir comme actif")
        self.btn_delete_stamp.setStyleSheet("color: #c0392b;")
        self.btn_activate_stamp.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold;")
        stamps_actions.addWidget(self.btn_add_stamp)
        stamps_actions.addWidget(self.btn_delete_stamp)
        stamps_actions.addWidget(self.btn_activate_stamp)
        stamps_group_layout.addLayout(stamps_actions)

        self.edit_stamp_name = QLineEdit()
        self.lbl_stamp_file = QLabel("Aucun fichier PNG")
        self.lbl_stamp_file.setWordWrap(True)
        self.sp_stamp_x = self._create_spin(0, 21, 13.0)
        self.sp_stamp_y = self._create_spin(0, 29.7, 22.0)
        self.sp_stamp_w = self._create_spin(0.5, 21, 4.0)
        self.sp_stamp_h = self._create_spin(0.5, 29.7, 4.0)
        self.btn_save_stamp = QPushButton("Enregistrer le nom, la position et la taille")
        self.btn_save_stamp.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.btn_add_stamp.setEnabled(self.can_manage_stamps)
        self.btn_delete_stamp.setEnabled(self.can_manage_stamps)
        if not self.can_manage_stamps:
            permission_hint = "Permission requise pour ajouter ou supprimer des cachets."
            self.btn_add_stamp.setToolTip(permission_hint)
            self.btn_delete_stamp.setToolTip(permission_hint)

        stamp_form = QFormLayout()
        stamp_form.addRow("Nom du cachet :", self.edit_stamp_name)
        stamp_form.addRow("Fichier :", self.lbl_stamp_file)
        stamp_form.addRow(QLabel(
            "Le cachet est automatiquement placé sous le premier titre de signature."
        ))
        stamp_form.addRow("Largeur (cm) :", self.sp_stamp_w)
        stamp_form.addRow("Hauteur (cm) :", self.sp_stamp_h)
        stamp_form.addRow("", self.btn_save_stamp)
        stamps_group_layout.addLayout(stamp_form)

        stamps_layout.addWidget(stamps_group)
        stamps_layout.addWidget(QLabel(
            "Les images PNG transparentes ou classiques sont acceptées. "
            "La position et la taille sont propres a chaque cachet et s'appliquent aux PDF de l'entreprise."
        ))
        stamps_layout.addStretch()
        tabs.addTab(tab_stamps, "6. Cachets")

        # TAB 7: ÉDITEUR VISUEL (WYSIWYG)
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
        
        tabs.addTab(tab_wy, "7. Éditeur Visuel (WYSIWYG)")

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
        self.btn_add_stamp.clicked.connect(self.add_stamp)
        self.btn_delete_stamp.clicked.connect(self.delete_stamp)
        self.btn_activate_stamp.clicked.connect(self.activate_stamp)
        self.btn_save_stamp.clicked.connect(self.save_current_stamp)
        self.list_stamps.currentRowChanged.connect(self.on_stamp_selected)
        for stamp_spin in (self.sp_stamp_x, self.sp_stamp_y, self.sp_stamp_w, self.sp_stamp_h):
            stamp_spin.valueChanged.connect(self.update_stamp_preview)
        self.rb_bl.toggled.connect(self.update_preview_mode)
        
        self.sync_settings()
        self.refresh_stamp_list()

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
            self.sp_footer_y, self.sp_footer_h, self.sp_footer_left_x, self.sp_footer_right_x,
            self.sp_footer_stamp_gap, self.sp_footer_stamp_w, self.sp_footer_stamp_h
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
        path, _ = QFileDialog.getOpenFileName(self, "Choisir l'image de l'en-tête", "", "Images (*.png *.jpg *.jpeg)")
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
                self.clear_banner_on_save = False
                
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
            "footer_right_x_cm": self.sp_footer_right_x.value(),
            "footer_stamp_gap_cm": self.sp_footer_stamp_gap.value(),
            "footer_stamp_area_w_cm": self.sp_footer_stamp_w.value(),
            "footer_stamp_area_h_cm": self.sp_footer_stamp_h.value()
        })
        self.preview_canvas.settings = self.settings
        self.preview_canvas.update()
        self.settings_updated.emit(self.settings)

class LivePreviewCanvas(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.is_retour = False
        self.active_stamp = None
        self.active_stamp_pixmap = QPixmap()
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
            p.drawText(QRect(0, 0, 210, total_h_mm), Qt.AlignCenter, "Zone image / en-tête")
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
        stamp_gap = float(s.get('footer_stamp_gap_cm', 0.3)) * 10
        stamp_area_w = float(s.get('footer_stamp_area_w_cm', 6.0)) * 10
        stamp_area_h = float(s.get('footer_stamp_area_h_cm', 3.5)) * 10
        f_height = max(f_height, int(FOOTER_TITLE_HEIGHT_CM * 10 + stamp_gap + stamp_area_h))

        p.setPen(Qt.black)
        p.drawText(f_left_x, signature_y, f_left)
        p.drawText(f_right_x, signature_y, f_right)
        
        # Visualize signature height box
        p.setPen(QPen(Qt.gray, 0.2, Qt.DashLine))
        p.drawRect(f_left_x, signature_y, 60, f_height)
        p.drawRect(f_right_x, signature_y, 60, f_height)

        # The selected stamp is anchored under the first signature title.
        stamp = getattr(self, "active_stamp", None)
        stamp_pixmap = getattr(self, "active_stamp_pixmap", QPixmap())
        area_x = f_left_x
        area_y = signature_y + FOOTER_TITLE_HEIGHT_CM * 10 + stamp_gap
        p.setPen(QPen(QColor("#95a5a6"), 0.4, Qt.DashLine))
        p.drawRect(area_x, area_y, stamp_area_w, stamp_area_h)
        if stamp and not stamp_pixmap.isNull():
            stamp_w_cm, stamp_h_cm = fit_stamp_size_cm(
                stamp,
                float(s.get('footer_stamp_area_w_cm', 6.0)),
                float(s.get('footer_stamp_area_h_cm', 3.5)),
            )
            stamp_w = int(stamp_w_cm * 10)
            stamp_h = int(stamp_h_cm * 10)
            stamp_x = int(area_x + (stamp_area_w - stamp_w) / 2)
            stamp_y = int(area_y)
            p.drawPixmap(QRect(stamp_x, stamp_y, stamp_w, stamp_h), stamp_pixmap)
            p.setPen(QPen(QColor("#e67e22"), 0.6, Qt.DashLine))
            p.drawRect(stamp_x, stamp_y, stamp_w, stamp_h)
