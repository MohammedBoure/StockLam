import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path

from dotenv import dotenv_values

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_db_env_fixture(path):
    values = dotenv_values(path)
    port_value = values.get("DB_PORT") or "3306"
    try:
        port = int(port_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"DB_PORT must be numeric: {port_value}") from exc

    config = {
        "host": values.get("DB_HOST") or "localhost",
        "port": port,
        "user": values.get("DB_USER"),
        "password": values.get("DB_PASSWORD"),
        "database": values.get("DB_NAME"),
    }
    missing = [key for key in ("user", "password", "database") if not config.get(key)]
    if missing:
        raise ValueError(f"Missing DB settings: {', '.join(missing)}")
    return config


def is_safe_test_database_name(name):
    text = str(name or "").strip().lower()
    if not text:
        return False

    unsafe_tokens = {"prod", "production", "real", "live"}
    if any(token in text for token in unsafe_tokens):
        return False

    safe_tokens = {"test", "dev", "sandbox", "local"}
    return any(token in text for token in safe_tokens)


class FakeInventoryCounts:
    def get_sessions(self, status=None, limit=100):
        return [
            {
                "Session_ID": 1,
                "Session_Name": "Environment smoke session",
                "Status": "Counting",
                "Started_At": "2026-06-07 10:00:00",
                "Created_By": 1,
            }
        ]

    def get_session_lines(self, session_id, status=None, search=None):
        return []

    def get_session_summary(self, session_id):
        return {
            "OK": 0,
            "SHORT": 0,
            "EXCESS": 0,
            "NOT_COUNTED": 0,
            "UNKNOWN": 0,
            "Estimated_Variance_Value": 0,
        }


class FakeDataManager:
    def __init__(self):
        self.inventory_counts = FakeInventoryCounts()


class EnvironmentSetupTests(unittest.TestCase):
    def test_virtualenv_and_requirements_are_ready(self):
        venv_python = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
        requirements = PROJECT_ROOT / "requirements.txt"

        self.assertTrue(
            venv_python.exists(),
            "Expected project virtual environment Python at venv\\Scripts\\python.exe.",
        )
        self.assertTrue(requirements.exists(), "requirements.txt must exist.")
        self.assertGreaterEqual(sys.version_info[:2], (3, 10))

        requirement_text = requirements.read_text(encoding="utf-8").lower()
        expected_dependencies = [
            "pyside6",
            "mysql-connector-python",
            "python-dotenv",
            "pandas",
            "xlsxwriter",
        ]
        for dependency in expected_dependencies:
            self.assertIn(dependency, requirement_text, f"Missing dependency: {dependency}")

    def test_critical_modules_import_without_opening_database(self):
        import database  # noqa: F401
        import database.base.connection  # noqa: F401
        import ui.formatting  # noqa: F401

    def test_main_py_syntax_compiles_without_running_application(self):
        main_path = PROJECT_ROOT / "main.py"
        self.assertTrue(main_path.exists(), "main.py must exist.")

        source = main_path.read_text(encoding="utf-8")
        compile(source, str(main_path), "exec")

        self.assertIn("def main(", source)
        self.assertIn("if __name__ == \"__main__\"", source)

    def test_env_fixture_parser_validates_database_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "DB_HOST=127.0.0.1",
                        "DB_PORT=3306",
                        "DB_USER=tester",
                        "DB_PASSWORD=secret",
                        "DB_NAME=stocklam_test",
                    ]
                ),
                encoding="utf-8",
            )

            config = parse_db_env_fixture(env_path)

            self.assertEqual(config["host"], "127.0.0.1")
            self.assertEqual(config["port"], 3306)
            self.assertEqual(config["user"], "tester")
            self.assertEqual(config["password"], "secret")
            self.assertEqual(config["database"], "stocklam_test")

            env_path.write_text(
                "\n".join(
                    [
                        "DB_HOST=127.0.0.1",
                        "DB_PORT=not-a-number",
                        "DB_USER=tester",
                        "DB_PASSWORD=secret",
                        "DB_NAME=stocklam_test",
                    ]
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "DB_PORT"):
                parse_db_env_fixture(env_path)

            env_path.write_text("DB_HOST=127.0.0.1\nDB_PORT=3306\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Missing DB settings"):
                parse_db_env_fixture(env_path)

    def test_database_name_guard_rejects_production_like_names(self):
        safe_names = [
            "stocklam_test",
            "lab_inventory_enterprise_db_test",
            "stocklam_dev",
            "inventory_sandbox",
            "local_stocklam",
        ]
        unsafe_names = [
            "",
            "Lab_Inventory_Enterprise_DB",
            "production_stocklam",
            "stocklam_prod",
            "real_inventory",
            "live_stocklam",
        ]

        for name in safe_names:
            self.assertTrue(is_safe_test_database_name(name), f"{name} should be safe for tests.")
        for name in unsafe_names:
            self.assertFalse(is_safe_test_database_name(name), f"{name} should be rejected.")

    def test_log_file_can_be_written_and_read_from_temporary_path(self):
        logger = logging.getLogger("stocklam.environment-test")
        logger.setLevel(logging.INFO)
        logger.propagate = False

        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "environment.log"
            handler = logging.FileHandler(log_path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(levelname)s:%(message)s"))
            logger.addHandler(handler)
            try:
                logger.info("startup message")
                logger.error("database error message")
            finally:
                logger.removeHandler(handler)
                handler.close()

            content = log_path.read_text(encoding="utf-8")

        self.assertIn("INFO:startup message", content)
        self.assertIn("ERROR:database error message", content)

    def test_inventory_widget_resizes_under_offscreen_qt(self):
        from PySide6.QtWidgets import QApplication

        from ui.widgets.inventory.inventory_count_tab import InventoryCountTab

        app = QApplication.instance() or QApplication([])
        widget = InventoryCountTab(FakeDataManager(), {"Permissions": []})
        try:
            for width, height in [(1024, 600), (1366, 768), (1920, 1080)]:
                widget.resize(width, height)
                app.processEvents()

                self.assertGreater(widget.width(), 0)
                self.assertGreater(widget.height(), 0)
                self.assertGreater(widget.sessions_table.width(), 0)
                self.assertGreater(widget.lines_table.width(), 0)
                self.assertIsNotNone(widget.btn_refresh)
                self.assertGreater(widget.btn_refresh.sizeHint().width(), 0)
        finally:
            widget.deleteLater()
            app.processEvents()


if __name__ == "__main__":
    unittest.main()
