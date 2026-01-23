# database/managers/printer_manager.py

import os
import json
import logging
import io
import win32print
import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont, ImageOps
import sys

def get_external_path(filename):
    """ Récupère le chemin absolu du fichier, compatible avec PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(os.path.dirname(sys.executable), filename)
    return os.path.join(os.path.abspath("."), filename)

CONFIG_FILE = get_external_path("config.json")

class PrinterManager:
    """
    Gère la conception et l'impression des étiquettes de codes-barres pour le laboratoire.
    Structure de l'étiquette : Code-barres (haut) -> Nom du produit -> Lot & Expiration.
    """
    def __init__(self, db_instance=None):
        self.db = db_instance
        self.config = {
            "selected_printer": "",
            "label_width": 50,
            "label_height": 30,
            "gap": 2,
            "font_size_name": 18,
            "font_size_info": 16,
            "font_size_barcode": 14
        }
        self.reload_settings()

    def reload_settings(self):
        """ Recharge les paramètres depuis le fichier de configuration JSON """
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key in self.config.keys():
                        if key in data:
                            self.config[key] = data[key]
            except Exception as e:
                logging.error(f"PrinterManager : Erreur lors du chargement des paramètres : {e}")

    def get_available_printers(self):
        """ Retourne la liste des imprimantes installées sur le système """
        try:
            printers = win32print.EnumPrinters(2)
            return [p[2] for p in printers] if printers else []
        except Exception as e:
            logging.error(f"Erreur lors de la récupération des imprimantes : {e}")
            return []

    # ----------------------------------------------------------------
    # 1. CONCEPTION DE L'ÉTIQUETTE
    # ----------------------------------------------------------------
    def _create_label_image(self, product_name, barcode_data, lot_number, expiry_date):
        """ 
        تصميم 40x20 ملم مع تصغير تلقائي لاسم المنتج ليناسب العرض.
        """
        w_px = 320 # 40mm
        h_px = 160 # 20mm
        
        img = Image.new('L', (w_px, h_px), 255) 
        draw = ImageDraw.Draw(img)

        # 1. إعدادات الخطوط الأساسية
        max_font_size = 22  # الحجم الأقصى المفضل
        min_font_size = 10  # الحجم الأدنى الذي لا نريد النزول عنه
        font_path = "arialbd.ttf"
        
        try:
            f_side = ImageFont.truetype("arial.ttf", 12)
        except:
            f_side = ImageFont.load_default()

        # --- 1. الشريط الجانبي (مضغوط أقصى اليمين) ---
        sidebar_w = 40 
        sidebar_img = Image.new('L', (h_px, sidebar_w), 255)
        side_draw = ImageDraw.Draw(sidebar_img)
        side_draw.text((10, 2),  f"LOT: {lot_number}", font=f_side, fill=0)
        side_draw.text((10, 20), f"EXP: {str(expiry_date)[:10]}", font=f_side, fill=0)
        rotated_sidebar = sidebar_img.rotate(90, expand=True)
        img.paste(rotated_sidebar, (w_px - sidebar_w, 0))

        # --- 2. منطقة الباركود والاسم ---
        main_area_w = w_px - sidebar_w - 10 # ترك هامش بسيط 10 بكسل
        display_name = product_name.upper() # أزلنا التحديد بـ 25 حرف لنجعله يتكيف
        bc_text = str(barcode_data)

        # --- منطق التصغير التلقائي لاسم المنتج ---
        current_size = max_font_size
        try:
            f_prod = ImageFont.truetype(font_path, current_size)
            # حلقة لتقليل الخط حتى يناسب المساحة المتاحة
            while current_size > min_font_size:
                bbox = draw.textbbox((0, 0), display_name, font=f_prod)
                text_width = bbox[2] - bbox[0]
                if text_width <= main_area_w:
                    break
                current_size -= 1
                f_prod = ImageFont.truetype(font_path, current_size)
            
            # بالنسبة لرقم الباركود، نستخدم الحجم الأصلي أو حجم الاسم أيهما أصغر
            f_bc_digits = ImageFont.truetype(font_path, min(20, current_size))
        except:
            f_prod = f_bc_digits = ImageFont.load_default()

        try:
            # إنشاء الباركود
            bc_class = barcode.get_barcode_class('code128') 
            writer = ImageWriter()
            opts = {"module_width": 0.7, "module_height": 20.0, "quiet_zone": 1.0, "write_text": False}
            
            fp = io.BytesIO()
            bc_obj = bc_class(bc_text, writer=writer)
            bc_obj.write(fp, options=opts)
            fp.seek(0)
            bc_img = Image.open(fp).convert("L")
            
            # مط الباركود عرضياً
            target_w = int(main_area_w * 0.98)
            target_h = 75 
            bc_img = bc_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            
            # حسابات التمركز
            bbox_bc = draw.textbbox((0, 0), bc_text, font=f_bc_digits)
            w_bc_text = bbox_bc[2] - bbox_bc[0]
            
            bbox_prod = draw.textbbox((0, 0), display_name, font=f_prod)
            w_prod_text = bbox_prod[2] - bbox_prod[0]

            # التوزيع العمودي
            start_y = 15 
            img.paste(bc_img, ((main_area_w - target_w) // 2 + 2, start_y))
            
            current_y = start_y + target_h + 2
            # رسم رقم الباركود
            draw.text(((main_area_w - w_bc_text) // 2 + 2, current_y), bc_text, font=f_bc_digits, fill=0)
            
            # رسم اسم المنتج (الذي أصبح حجمه مناسباً الآن)
            current_y += 24 # إزاحة ثابتة للأسفل
            draw.text(((main_area_w - w_prod_text) // 2 + 2, current_y), display_name, font=f_prod, fill=0)

        except Exception as e:
            logging.error(f"Error in label design: {e}")

        return img.convert('1')
    # ----------------------------------------------------------------
    # 2. CONVERSION DE L'IMAGE EN COMMANDES TSPL
    # ----------------------------------------------------------------
    def _image_to_tspl(self, pil_img, copies=1):
        """ Convertit l'image PIL en langage de programmation TSPL """
        w_mm = self.config['label_width']
        h_mm = self.config['label_height']
        gap = self.config['gap']
        
        W, H = pil_img.size
        Wb = (W + 7) // 8 
        
        data = pil_img.tobytes()
        
        cmds = [
            f"SIZE {w_mm} mm, {h_mm} mm",
            f"GAP {gap} mm, 0 mm",
            "DIRECTION 1",
            "CLS",
            f"BITMAP 0,0,{Wb},{H},0,"
        ]
        
        header = "\r\n".join(cmds).encode("ascii")
        footer = f"\r\nPRINT {copies}\r\n".encode("ascii")
        
        return header + data + footer

    # ----------------------------------------------------------------
    # 3. EXÉCUTION DE L'IMPRESSION
    # ----------------------------------------------------------------
    def print_label(self, product_name, barcode_data, lot_number, expiry_date, copies=1):
        """ Envoie le travail d'impression à l'imprimante sélectionnée """
        self.reload_settings()
        
        printer_name = self.config.get('selected_printer')
        if not printer_name:
            return False, "Aucune imprimante sélectionnée dans les paramètres."

        try:
            img = self._create_label_image(product_name, barcode_data, lot_number, expiry_date)
            if not img:
                return False, "Échec de la création du design de l'étiquette."

            raw_data = self._image_to_tspl(img, copies)

            hprinter = win32print.OpenPrinter(printer_name)
            try:
                job_info = ("Travail Etiquette LIMS", None, "RAW")
                win32print.StartDocPrinter(hprinter, 1, job_info)
                win32print.StartPagePrinter(hprinter)
                win32print.WritePrinter(hprinter, raw_data)
                win32print.EndPagePrinter(hprinter)
                win32print.EndDocPrinter(hprinter)
            finally:
                win32print.ClosePrinter(hprinter)
            
            logging.info(f"Étiquette imprimée pour {product_name} sur {printer_name}")
            return True, "Commande d'impression envoyée avec succès."

        except Exception as e:
            logging.error(f"Exception lors de l'impression : {e}")
            return False, f"Erreur d'impression : {e}"