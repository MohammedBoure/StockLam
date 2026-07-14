"""Shared PDF rendering helpers for the configurable company stamp."""

import io
import logging

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


def draw_active_stamp(canvas, company_settings, page_width, page_height):
    """Draw the active PNG stamp without making PDF export fail when it is invalid."""
    if not company_settings or not hasattr(company_settings, "get_active_stamp"):
        return False

    try:
        stamp = company_settings.get_active_stamp()
        image_bytes = stamp.get("Image_Data") if stamp else None
        if not image_bytes:
            return False

        from reportlab.lib.units import cm
        from reportlab.lib.utils import ImageReader

        x, y, width, height = stamp_rect(stamp, page_width, page_height)
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
