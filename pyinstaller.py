# build_exe.py
import os
import sys
import subprocess
import shutil
import mysql.connector


def build_lims_production():
    """
    Final Build Script for LIMS Manager.
    Uses the current venv Python explicitly to avoid launcher / PATH issues.
    """
    project_dir = os.path.abspath(os.path.dirname(__file__))
    main_script = "main.py"
    exe_name = "MODERNSTOCK"

    # Detect MySQL connector paths (pure Python)
    mysql_path = os.path.dirname(mysql.connector.__file__)
    plugins_src = os.path.join(mysql_path, "plugins")
    locales_src = os.path.join(mysql_path, "locales")

    # 1. Clean Workspace
    for folder in ("dist", "build"):
        folder_path = os.path.join(project_dir, folder)
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)

    # 2. PyInstaller command (CRITICAL FIX: use current venv python)
    command = [
        sys.executable, "-m", "PyInstaller",

        "--noconsole",
        "--onedir",
        f"--name={exe_name}",
        "--clean",

        # UI assets
        "--add-data=ui/logo.png;ui",
        "--add-data=ui/logo2.png;ui",
        "--add-data=ui/styles.qss;ui",

        # MySQL pure-python resources
        f"--add-data={plugins_src};mysql/connector/plugins",
        f"--add-data={locales_src};mysql/connector/locales",

        # Mandatory collections
        "--collect-all=PySide6",
        "--collect-all=mysql.connector",
        "--collect-all=reportlab",
        "--collect-all=pandas",

        # Hidden imports
        "--hidden-import=mysql.connector.plugins.mysql_native_password",
        "--hidden-import=sqlalchemy",
        "--hidden-import=openpyxl",

        "--icon=ui/logo.png",
        main_script
    ]

    try:
        print(f"🏗️ Building {exe_name} for production...\n")
        subprocess.check_call(command)

        # 3. Post-build: copy external config files
        dist_path = os.path.join(project_dir, "dist", exe_name)

        for cfg in (".env", "config.json"):
            if os.path.exists(cfg):
                shutil.copy(cfg, dist_path)
                print(f"✅ Copied external config: {cfg}")

        # 4. Create runtime folders
        for folder in ("documents", "exports"):
            os.makedirs(os.path.join(dist_path, folder), exist_ok=True)

        print("\n🚀 SUCCESS!")
        print(f"📦 Application generated in: dist/{exe_name}")

    except subprocess.CalledProcessError as e:
        print("\n❌ PyInstaller failed.")
        print(e)

    except Exception as e:
        print("\n❌ Unexpected error.")
        print(e)


if __name__ == "__main__":
    build_lims_production()
