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
