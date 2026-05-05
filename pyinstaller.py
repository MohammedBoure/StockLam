# build_exe.py
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import mysql.connector

from branding import BRANDS, DEFAULT_BRAND_KEY, normalize_brand_key


DATA_SEPARATOR = ";" if os.name == "nt" else ":"


def _data_arg(project_dir, source_relative_path, destination_relative_path):
    source_path = (project_dir / source_relative_path).resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Missing build asset: {source_path}")
    return f"--add-data={source_path}{DATA_SEPARATOR}{destination_relative_path}"


def _resolve_brand_key(value):
    brand_key = normalize_brand_key(value)
    if brand_key not in BRANDS:
        valid = ", ".join(sorted(BRANDS))
        raise ValueError(f"Unknown brand '{value}'. Valid values: {valid}, all")
    return brand_key


def _clean_target(project_dir, exe_name):
    build_path = project_dir / "build"
    if build_path.exists():
        shutil.rmtree(build_path)

    spec_path = project_dir / f"{exe_name}.spec"
    if spec_path.exists():
        spec_path.unlink()

    dist_target = project_dir / "dist" / exe_name
    if dist_target.exists():
        shutil.rmtree(dist_target)


def build_lims_production(brand_key=DEFAULT_BRAND_KEY):
    """
    Build one branded executable from the shared source tree.
    """
    project_dir = Path(__file__).resolve().parent
    brand_key = _resolve_brand_key(brand_key)
    brand = BRANDS[brand_key]

    main_script = "main.py"
    exe_name = brand["exe_name"]

    mysql_path = Path(mysql.connector.__file__).resolve().parent
    plugins_src = mysql_path / "plugins"
    locales_src = mysql_path / "locales"

    _clean_target(project_dir, exe_name)

    data_args = [
        _data_arg(project_dir, "ui/styles.qss", "ui"),
        _data_arg(project_dir, brand["logo"], f"brand_assets/{brand_key}"),
        _data_arg(project_dir, f"brand_assets/{brand_key}/brand.json", "."),
        f"--add-data={plugins_src}{DATA_SEPARATOR}mysql/connector/plugins",
        f"--add-data={locales_src}{DATA_SEPARATOR}mysql/connector/locales",
    ]

    if brand.get("banner"):
        data_args.append(_data_arg(project_dir, brand["banner"], f"brand_assets/{brand_key}"))

    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onedir",
        f"--name={exe_name}",
        "--clean",
        f"--paths={project_dir}",
        *data_args,
        "--collect-all=PySide6",
        "--collect-all=mysql.connector",
        "--collect-all=reportlab",
        "--collect-all=pandas",
        "--hidden-import=mysql.connector.plugins.mysql_native_password",
        "--hidden-import=sqlalchemy",
        "--hidden-import=openpyxl",
        f"--icon={(project_dir / brand['logo']).resolve()}",
        main_script,
    ]

    try:
        print(f"Building {exe_name} ({brand_key}) for production...\n")
        subprocess.check_call(command, cwd=project_dir)

        dist_path = project_dir / "dist" / exe_name

        for cfg in (".env", "config.json"):
            cfg_path = project_dir / cfg
            if cfg_path.exists():
                shutil.copy2(cfg_path, dist_path / cfg)
                print(f"Copied external config: {cfg}")

        for folder in ("documents", "exports"):
            (dist_path / folder).mkdir(parents=True, exist_ok=True)

        print("\nSUCCESS!")
        print(f"Application generated in: dist/{exe_name}")

    except subprocess.CalledProcessError as e:
        print("\nPyInstaller failed.")
        print(e)
        raise

    except Exception as e:
        print("\nUnexpected error.")
        print(e)
        raise


def parse_args():
    valid = ", ".join(sorted(BRANDS))
    parser = argparse.ArgumentParser(
        description="Build StockLam or MODERNSTOCK from the shared source tree."
    )
    parser.add_argument(
        "brand",
        nargs="?",
        default=DEFAULT_BRAND_KEY,
        help=f"Brand to build: {valid}, or all. Default: {DEFAULT_BRAND_KEY}",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    requested = args.brand.strip().lower()

    if requested == "all":
        for key in BRANDS:
            build_lims_production(key)
    else:
        build_lims_production(requested)
