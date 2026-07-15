"""Shared PDF rendering helpers for the configurable company stamp."""

import io
import logging

FOOTER_TITLE_HEIGHT_CM = 0.5

def stamp_rect(stamp, page_width, page_height):
    """Return a ReportLab rectangle from the UI's top-left centimetre values."""
    from reportlab.lib.units import cm

    x_cm = float(stamp.get("Position_X_CM", 0.0))
    y_cm = float(stamp.get("Position_Y_CM", 0.0))
    width_cm = float(stamp.get("Width_CM", 0.0))
    height_cm = float(stamp.get("Height_CM", 0.0))

    x = x_cm * cm
    y = page_height - ((y_cm + height_cm) * cm)
    return x, y, width_cm * cm, height_cm * cm


def get_active_stamp(stamp_provider):
    """Return the selected stamp from either the local store or a DB provider."""
    if not stamp_provider or not hasattr(stamp_provider, "get_active_stamp"):
        return None
    try:
        return stamp_provider.get_active_stamp()
    except Exception as exc:
        logging.warning("Unable to read the active PDF stamp: %s", exc)
        return None


def fit_stamp_size_cm(stamp, max_width_cm, max_height_cm):
    """Fit a stamp inside the configured signature area without distortion."""
    width_cm = max(float(stamp.get("Width_CM", 0.0)), 0.1)
    height_cm = max(float(stamp.get("Height_CM", 0.0)), 0.1)
    scale = min(1.0, float(max_width_cm) / width_cm, float(max_height_cm) / height_cm)
    return width_cm * scale, height_cm * scale


def draw_stamp_image(canvas, stamp, x, y, width, height):
    """Draw one stamp at an explicit ReportLab position."""
    image_bytes = stamp.get("Image_Data") if stamp else None
    if not image_bytes:
        return False

    try:
        from reportlab.lib.utils import ImageReader

        image = ImageReader(io.BytesIO(image_bytes))
        canvas.drawImage(
            image,
            x,
            y,
            width=width,
            height=height,
            mask="auto",
            preserveAspectRatio=False,
        )
        return True
    except Exception as exc:
        logging.warning("Unable to draw the active PDF stamp: %s", exc)
        return False


def draw_active_stamp(canvas, stamp_provider, page_width, page_height):
    """Draw the active PNG stamp using its legacy absolute page position."""
    stamp = get_active_stamp(stamp_provider)
    if not stamp:
        return False

    try:
        x, y, width, height = stamp_rect(stamp, page_width, page_height)
        return draw_stamp_image(canvas, stamp, x, y, width, height)
    except Exception as exc:
        logging.warning("Unable to draw the active PDF stamp: %s", exc)
        return False

try:
    from reportlab.platypus import Flowable
    from reportlab.lib.units import cm
    
    class SignatureFooter(Flowable):
        def __init__(self, t_left, t_right, x_l, x_r, h, stamp, stamp_gap, stamp_area_w, stamp_area_h):
            Flowable.__init__(self)
            self.t_left = t_left
            self.t_right = t_right
            self.x_l = x_l * cm
            self.x_r = x_r * cm
            self.h = max(h, FOOTER_TITLE_HEIGHT_CM + stamp_gap + stamp_area_h) * cm
            self.stamp = stamp
            self.stamp_gap = float(stamp_gap) * cm
            self.stamp_area_w = float(stamp_area_w) * cm
            self.stamp_area_h = float(stamp_area_h) * cm
        
        def wrap(self, availW, availH):
            return availW, self.h
            
        def draw(self):
            self.canv.saveState()
            self.canv.setFont("Helvetica-Bold", 10)
            self.canv.drawString(self.x_l, self.h - 15, self.t_left)
            self.canv.drawString(self.x_r, self.h - 15, self.t_right)
            if self.stamp:
                stamp_w_cm, stamp_h_cm = fit_stamp_size_cm(
                    self.stamp,
                    self.stamp_area_w / cm,
                    self.stamp_area_h / cm,
                )
                stamp_w = stamp_w_cm * cm
                stamp_h = stamp_h_cm * cm
                stamp_x = self.x_l + max(0, (self.stamp_area_w - stamp_w) / 2)
                stamp_top = self.h - 15 - FOOTER_TITLE_HEIGHT_CM * cm - self.stamp_gap
                stamp_y = max(0, stamp_top - stamp_h)
                draw_stamp_image(
                    self.canv,
                    self.stamp,
                    stamp_x,
                    stamp_y,
                    stamp_w,
                    stamp_h,
                )
            self.canv.restoreState()
except ImportError:
    pass
