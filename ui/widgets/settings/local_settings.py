"""Per-application-user local settings and stamp storage.

The database remains an optional source for importing PDF templates. Normal
editing and PDF rendering use this local store so one user cannot overwrite
another user's device settings.
"""

import base64
import json
import os
import re
import sys
from copy import deepcopy
from uuid import uuid4


def get_external_path(filename):
    if hasattr(sys, "_MEIPASS"):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, filename)


def _safe_user_key(user):
    if isinstance(user, dict):
        raw = user.get("Username") or user.get("username") or user.get("User_ID")
    else:
        raw = user
    raw = str(raw or "default").strip()
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)
    return safe.strip("._") or "default"


class LocalSettingsStore:
    """Persist general settings, PDF settings, and stamps under one user key."""

    def __init__(self, user=None, root_path=None):
        root = root_path or get_external_path("local_settings")
        self.user_key = _safe_user_key(user)
        self.user_dir = os.path.join(root, self.user_key)
        self.general_path = os.path.join(self.user_dir, "general.json")
        self.pdf_path = os.path.join(self.user_dir, "pdf.json")
        self.stamps_path = os.path.join(self.user_dir, "stamps.json")
        self.banner_path = os.path.join(self.user_dir, "banner.png")
        self.legacy_general_path = get_external_path("config.json")
        self.legacy_pdf_path = get_external_path("pdf_settings.json")

    @staticmethod
    def _read_json(path):
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                value = json.load(handle)
            return value if isinstance(value, (dict, list)) else None
        except (OSError, ValueError, TypeError):
            return None

    def _write_json(self, path, value):
        os.makedirs(self.user_dir, exist_ok=True)
        temporary_path = f"{path}.{os.getpid()}.tmp"
        with open(temporary_path, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
        os.replace(temporary_path, path)

    def load_general(self, defaults=None):
        source = self._read_json(self.general_path)
        if not isinstance(source, dict):
            # One-time compatibility read. The legacy file is never overwritten.
            source = self._read_json(self.legacy_general_path) or {}
            if isinstance(source, dict) and source:
                try:
                    self._write_json(self.general_path, source)
                except OSError:
                    pass
        if not isinstance(source, dict):
            source = {}
        result = deepcopy(defaults or {})
        result.update(source)
        return result

    def save_general(self, settings):
        self._write_json(self.general_path, dict(settings))

    def load_pdf(self, defaults=None):
        source = self._read_json(self.pdf_path)
        if not isinstance(source, dict):
            source = self._read_json(self.legacy_pdf_path) or {}
            if isinstance(source, dict) and source:
                try:
                    self._write_json(self.pdf_path, source)
                except OSError:
                    pass
        if not isinstance(source, dict):
            source = {}
        result = deepcopy(defaults or {})
        result.update(source)
        return result

    def load_merged_pdf_settings(self, defaults=None):
        result = self.load_general()
        result.update(self.load_pdf(defaults))
        return result

    def save_pdf(self, settings, banner_bytes=None, clear_banner=False):
        data = dict(settings)
        if clear_banner:
            try:
                os.remove(self.banner_path)
            except FileNotFoundError:
                pass
            data["banner_path"] = ""
        elif banner_bytes:
            os.makedirs(self.user_dir, exist_ok=True)
            with open(self.banner_path, "wb") as handle:
                handle.write(bytes(banner_bytes))
            data["banner_path"] = self.banner_path
        self._write_json(self.pdf_path, data)

    def load_banner_bytes(self, settings=None):
        data = settings or self.load_pdf()
        candidates = [data.get("banner_path"), self.banner_path, get_external_path("banner_downloaded.png")]
        for path in candidates:
            if path and os.path.exists(path):
                try:
                    with open(path, "rb") as handle:
                        return handle.read()
                except OSError:
                    continue
        return None

    @staticmethod
    def _decode_image(value):
        if not value:
            return b""
        if isinstance(value, (bytes, bytearray, memoryview)):
            return bytes(value)
        try:
            return base64.b64decode(value)
        except (ValueError, TypeError):
            return b""

    def load_stamps(self):
        raw = self._read_json(self.stamps_path)
        if not isinstance(raw, list):
            return []
        stamps = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            stamp = dict(entry)
            stamp["Stamp_ID"] = str(stamp.get("Stamp_ID") or uuid4().hex)
            stamp["Image_Data"] = self._decode_image(stamp.get("Image_Data"))
            stamp["Is_Active"] = bool(stamp.get("Is_Active"))
            stamps.append(stamp)
        return stamps

    def save_stamps(self, stamps):
        payload = []
        for entry in stamps:
            stamp = dict(entry)
            image_bytes = self._decode_image(stamp.pop("Image_Data", b""))
            stamp["Image_Data"] = base64.b64encode(image_bytes).decode("ascii")
            stamp["Stamp_ID"] = str(stamp.get("Stamp_ID") or uuid4().hex)
            stamp["Is_Active"] = bool(stamp.get("Is_Active"))
            payload.append(stamp)
        self._write_json(self.stamps_path, payload)

    def add_stamp(self, name, image_bytes, position_x_cm, position_y_cm, width_cm, height_cm):
        stamps = self.load_stamps()
        stamp_id = uuid4().hex
        stamps.append({
            "Stamp_ID": stamp_id,
            "Stamp_Name": str(name).strip()[:150],
            "Image_Data": bytes(image_bytes),
            "Position_X_CM": float(position_x_cm),
            "Position_Y_CM": float(position_y_cm),
            "Width_CM": float(width_cm),
            "Height_CM": float(height_cm),
            "Is_Active": not stamps,
        })
        self.save_stamps(stamps)
        return stamp_id

    def update_stamp(self, stamp_id, name, position_x_cm, position_y_cm, width_cm, height_cm):
        target = str(stamp_id)
        stamps = self.load_stamps()
        for stamp in stamps:
            if str(stamp.get("Stamp_ID")) == target:
                stamp.update({
                    "Stamp_Name": str(name).strip()[:150],
                    "Position_X_CM": float(position_x_cm),
                    "Position_Y_CM": float(position_y_cm),
                    "Width_CM": float(width_cm),
                    "Height_CM": float(height_cm),
                })
                self.save_stamps(stamps)
                return True
        return False

    def set_active_stamp(self, stamp_id):
        target = str(stamp_id)
        stamps = self.load_stamps()
        found = False
        for stamp in stamps:
            active = str(stamp.get("Stamp_ID")) == target
            stamp["Is_Active"] = active
            found = found or active
        if found:
            self.save_stamps(stamps)
        return found

    def delete_stamp(self, stamp_id):
        target = str(stamp_id)
        stamps = self.load_stamps()
        remaining = [stamp for stamp in stamps if str(stamp.get("Stamp_ID")) != target]
        if len(remaining) == len(stamps):
            return False
        if remaining and not any(stamp.get("Is_Active") for stamp in remaining):
            remaining[0]["Is_Active"] = True
        self.save_stamps(remaining)
        return True

    def import_database_stamps(self, database_stamps):
        imported = []
        for entry in database_stamps or []:
            image_bytes = self._decode_image(entry.get("Image_Data"))
            if not image_bytes:
                continue
            imported.append({
                "Stamp_ID": uuid4().hex,
                "Stamp_Name": str(entry.get("Stamp_Name") or "Cachet")[:150],
                "Image_Data": image_bytes,
                "Position_X_CM": float(entry.get("Position_X_CM") or 13.0),
                "Position_Y_CM": float(entry.get("Position_Y_CM") or 22.0),
                "Width_CM": float(entry.get("Width_CM") or 4.0),
                "Height_CM": float(entry.get("Height_CM") or 4.0),
                "Is_Active": bool(entry.get("Is_Active")),
            })
        if imported and not any(stamp.get("Is_Active") for stamp in imported):
            imported[0]["Is_Active"] = True
        return imported

    def get_active_stamp(self):
        return next((stamp for stamp in self.load_stamps() if stamp.get("Is_Active")), None)


def get_local_settings_store(data_manager=None, current_user=None):
    """Return the store attached to the running session, creating it when needed."""
    if data_manager is not None:
        existing = getattr(data_manager, "local_settings", None)
        if existing is not None:
            return existing
        current_user = current_user or getattr(data_manager, "current_user", None)

    store = LocalSettingsStore(current_user)
    if data_manager is not None:
        try:
            data_manager.local_settings = store
        except Exception:
            pass
    return store
