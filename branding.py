import json
import os
import sys
from functools import lru_cache


APP_VERSION = "1.10.0"
DEFAULT_BRAND_KEY = "stocklam"
BRAND_ENV_VAR = "STOCKLAM_BRAND"
_BRAND_OVERRIDE = None

BRANDS = {
    "stocklam": {
        "app_name": "StockLam",
        "exe_name": "StockLam",
        "organization_name": "StockLam",
        "settings_app_name": "StockManager",
        "lock_file_name": "stocklam_stockmanager.lock",
        "logo": os.path.join("brand_assets", "stocklam", "logo.png"),
    },
    "modernstock": {
        "app_name": "MODERNSTOCK",
        "exe_name": "MODERNSTOCK",
        "organization_name": "ModernLam",
        "settings_app_name": "StockManager",
        "lock_file_name": "modernlam_stockmanager.lock",
        "logo": os.path.join("brand_assets", "modernstock", "logo.png"),
        "banner": os.path.join("brand_assets", "modernstock", "logo2.png"),
    },
}

BRAND_ALIASES = {
    "stocklam": "stocklam",
    "stock": "stocklam",
    "modernstock": "modernstock",
    "modern_stock": "modernstock",
    "modernlam": "modernstock",
    "modern_lam": "modernstock",
}


def normalize_brand_key(value):
    if not value:
        return None
    key = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return BRAND_ALIASES.get(key)


def configure_brand(value):
    global _BRAND_OVERRIDE

    brand_key = normalize_brand_key(value)
    if brand_key not in BRANDS:
        valid = ", ".join(sorted(BRANDS))
        raise ValueError(f"Unknown brand '{value}'. Valid values: {valid}")

    _BRAND_OVERRIDE = brand_key
    get_brand_key.cache_clear()
    return brand_key


def configure_brand_from_argv(argv):
    cleaned_argv = [argv[0]]
    index = 1

    while index < len(argv):
        arg = argv[index]
        brand_value = None

        if arg in ("--brand", "-b"):
            if index + 1 >= len(argv):
                raise ValueError("--brand requires a value")
            brand_value = argv[index + 1]
            index += 2
        elif arg.startswith("--brand="):
            brand_value = arg.split("=", 1)[1]
            index += 1
        elif index == 1 and normalize_brand_key(arg):
            brand_value = arg
            index += 1
        else:
            cleaned_argv.append(arg)
            index += 1

        if brand_value is not None:
            configure_brand(brand_value)

    argv[:] = cleaned_argv


def get_resource_base_path():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.abspath(os.path.dirname(__file__))


def get_resource_path(relative_path):
    return os.path.join(get_resource_base_path(), relative_path)


def _read_packaged_brand_key():
    brand_file = get_resource_path("brand.json")
    if not os.path.exists(brand_file):
        return None

    try:
        with open(brand_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    return normalize_brand_key(data.get("brand"))


@lru_cache(maxsize=1)
def get_brand_key():
    if getattr(sys, "frozen", False):
        packaged_brand = _read_packaged_brand_key()
        if packaged_brand:
            return packaged_brand

    if _BRAND_OVERRIDE:
        return _BRAND_OVERRIDE

    env_brand = normalize_brand_key(os.environ.get(BRAND_ENV_VAR))
    if env_brand:
        return env_brand

    packaged_brand = _read_packaged_brand_key()
    if packaged_brand:
        return packaged_brand

    return DEFAULT_BRAND_KEY


def get_branding():
    return BRANDS[get_brand_key()]


def get_app_name():
    return get_branding()["app_name"]


def get_login_window_title():
    return f"{get_app_name()}-{APP_VERSION}"


def get_exe_name(brand_key=None):
    key = normalize_brand_key(brand_key) if brand_key else get_brand_key()
    return BRANDS[key]["exe_name"]


def get_organization_name():
    return get_branding()["organization_name"]


def get_settings_app_name():
    return get_branding()["settings_app_name"]


def get_lock_file_name():
    return get_branding()["lock_file_name"]


def _existing_brand_asset(asset_key):
    relative_path = get_branding().get(asset_key)
    if not relative_path:
        return None

    path = get_resource_path(relative_path)
    return path if os.path.exists(path) else None


def get_logo_path():
    return _existing_brand_asset("logo") or get_resource_path(os.path.join("ui", "logo.png"))


def get_banner_path():
    return _existing_brand_asset("banner") or get_logo_path()
