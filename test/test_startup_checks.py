import importlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
STARTUP_COMPILE_COMMAND = [
    str(VENV_PYTHON),
    "-m",
    "compileall",
    "database",
    "ui",
    "test",
]
STARTUP_TEST_COMMAND = [str(VENV_PYTHON), "-m", "unittest", "discover"]


class FakeDatabaseConnectionDialog:
    instances = []

    def __init__(self, parent=None):
        self.parent = parent
        self.shown = False
        self.accepted = False
        self.attempts = []
        self.lines = []
        self.success_marked = False
        self.statuses = []
        FakeDatabaseConnectionDialog.instances.append(self)

    def show(self):
        self.shown = True

    def set_attempt(self, attempt):
        self.attempts.append(attempt)

    def append_line(self, text, level=logging.INFO):
        self.lines.append((text, level))

    def set_status(self, text):
        self.statuses.append(text)

    def mark_success(self):
        self.success_marked = True

    def accept(self):
        self.accepted = True


class FakeApp:
    def __init__(self):
        self.process_events_count = 0

    def processEvents(self):
        self.process_events_count += 1


class FakeDatabase:
    reset_calls = 0
    created = 0

    @classmethod
    def reset_connection_state(cls):
        cls.reset_calls += 1

    def __init__(self):
        FakeDatabase.created += 1


class FakeLabDataManager:
    created_with = []

    def __init__(self, db):
        self.db = db
        self.users = object()
        FakeLabDataManager.created_with.append(db)


class FakeAutoBackupWorker:
    instances = []

    def __init__(self, data_manager):
        self.data_manager = data_manager
        self.started = False
        self.stopped = False
        FakeAutoBackupWorker.instances.append(self)

    def start(self):
        self.started = True

    def isRunning(self):
        return self.started

    def stop(self):
        self.stopped = True
        self.started = False


def import_main_safely():
    """Import main.py without creating app.log or reading real CLI brand args."""
    original_main = sys.modules.pop("main", None)
    old_excepthook = sys.excepthook
    try:
        with patch.object(sys, "argv", ["main.py"]), \
             patch("logging.handlers.RotatingFileHandler", lambda *args, **kwargs: logging.NullHandler()):
            module = importlib.import_module("main")
        return module
    finally:
        sys.excepthook = old_excepthook
        if original_main is not None:
            sys.modules["main"] = original_main


def count_test_cases(suite):
    total = 0
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            total += count_test_cases(item)
        else:
            total += 1
    return total


class StartupChecksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        self.app.processEvents()

    def test_compileall_command_is_structurally_runnable_from_venv(self):
        self.assertTrue(
            VENV_PYTHON.exists(),
            f"Startup compile check cannot run because venv Python is missing: {VENV_PYTHON}",
        )
        for relative_dir in ("database", "ui", "test"):
            path = PROJECT_ROOT / relative_dir
            self.assertTrue(path.is_dir(), f"Startup compile check missing required directory: {path}")

        self.assertEqual(STARTUP_COMPILE_COMMAND[1:], ["-m", "compileall", "database", "ui", "test"])

    def test_compileall_subprocess_returns_zero(self):
        if not VENV_PYTHON.exists():
            self.skipTest(f"venv Python executable not found: {VENV_PYTHON}")

        result = subprocess.run(
            STARTUP_COMPILE_COMMAND,
            cwd=PROJECT_ROOT,
            timeout=120,
            capture_output=True,
            text=True,
            shell=False,
        )

        self.assertEqual(
            result.returncode,
            0,
            "Startup compileall failed.\n"
            f"Command: {' '.join(STARTUP_COMPILE_COMMAND)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}",
        )

    def test_unittest_discover_command_is_documented_without_recursive_run(self):
        self.assertEqual(STARTUP_TEST_COMMAND[1:], ["-m", "unittest", "discover"])
        test_dir = PROJECT_ROOT / "test"
        self.assertTrue(test_dir.is_dir(), "Startup test discover check requires the test directory.")
        self.assertTrue(
            any(test_dir.glob("test_*.py")),
            "Startup test discover check found no test_*.py files.",
        )

        suite = unittest.defaultTestLoader.discover(
            start_dir=str(test_dir),
            pattern="test_*.py",
            top_level_dir=str(PROJECT_ROOT),
        )

        self.assertGreater(
            count_test_cases(suite),
            0,
            "unittest discover found no tests; the startup suite command would not validate anything.",
        )

    def test_nested_unittest_discover_is_guarded_by_environment_variable(self):
        if os.environ.get("STOCKLAM_RUN_NESTED_TEST_DISCOVER") != "1":
            self.skipTest(
                "Nested unittest discover is intentionally skipped by default. "
                "Set STOCKLAM_RUN_NESTED_TEST_DISCOVER=1 to run the finite subprocess smoke."
            )
        if not VENV_PYTHON.exists():
            self.skipTest(f"venv Python executable not found: {VENV_PYTHON}")

        env = os.environ.copy()
        env["STOCKLAM_RUN_NESTED_TEST_DISCOVER"] = "0"
        result = subprocess.run(
            STARTUP_TEST_COMMAND,
            cwd=PROJECT_ROOT,
            timeout=180,
            capture_output=True,
            text=True,
            shell=False,
            env=env,
        )

        self.assertEqual(
            result.returncode,
            0,
            "Nested unittest discover smoke failed.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}",
        )

    def test_valid_database_startup_path_is_simulated_without_real_connection(self):
        main_module = import_main_safely()
        FakeDatabase.reset_calls = 0
        FakeDatabase.created = 0
        FakeLabDataManager.created_with = []
        FakeDatabaseConnectionDialog.instances = []

        fake_config = {
            "host": "127.0.0.1",
            "port": 3306,
            "user": "tester",
            "password": "secret",
            "database": "stocklam_test",
        }
        with patch.object(main_module, "DatabaseConnectionDialog", FakeDatabaseConnectionDialog), \
             patch.object(main_module, "Database", FakeDatabase), \
             patch.object(main_module, "LabDataManager", FakeLabDataManager), \
             patch.object(main_module, "_get_runtime_db_config", return_value=("temp.env", fake_config)), \
             patch.object(main_module, "_probe_tcp_connection", return_value=4), \
             patch.object(main_module.time, "sleep", lambda seconds: None):
            data_manager, error = main_module.connect_to_database_with_retry(FakeApp())

        dialog = FakeDatabaseConnectionDialog.instances[0]
        self.assertIsInstance(data_manager, FakeLabDataManager)
        self.assertIsNone(error)
        self.assertTrue(dialog.shown)
        self.assertTrue(dialog.success_marked)
        self.assertTrue(dialog.accepted)
        self.assertEqual(FakeDatabase.created, 1)
        self.assertEqual(len(FakeLabDataManager.created_with), 1)
        self.assertTrue(
            any("Connexion MySQL et initialisation application OK." in line for line, _ in dialog.lines),
            "Valid startup simulation did not log the expected success message.",
        )

    def test_database_unavailable_startup_path_returns_controlled_error(self):
        main_module = import_main_safely()
        FakeDatabase.reset_calls = 0
        FakeDatabaseConnectionDialog.instances = []
        critical_messages = []

        with patch.object(main_module, "DatabaseConnectionDialog", FakeDatabaseConnectionDialog), \
             patch.object(main_module, "DB_CONNECTION_ATTEMPTS", 1), \
             patch.object(main_module, "_get_runtime_db_config", side_effect=RuntimeError("database offline")), \
             patch.object(main_module.Database, "reset_connection_state", side_effect=FakeDatabase.reset_connection_state), \
             patch.object(main_module.QMessageBox, "critical", lambda *args: critical_messages.append(args)):
            data_manager, error = main_module.connect_to_database_with_retry(FakeApp())

        dialog = FakeDatabaseConnectionDialog.instances[0]
        self.assertIsNone(data_manager)
        self.assertIsInstance(error, str)
        self.assertIn("Impossible de se connecter", error)
        self.assertIn("RuntimeError: database offline", error)
        self.assertTrue(dialog.accepted)
        self.assertTrue(critical_messages, "Database-unavailable startup should report a controlled critical message.")

    def test_connection_error_formatter_includes_database_error_details(self):
        main_module = import_main_safely()

        class FakeDbError(Exception):
            errno = 2003
            sqlstate = "HY000"
            msg = "cannot connect"

        formatted = main_module._format_connection_error(FakeDbError("network unavailable"))

        self.assertIn("FakeDbError: network unavailable", formatted)
        self.assertIn("errno: 2003", formatted)
        self.assertIn("sqlstate: HY000", formatted)
        self.assertIn("msg: cannot connect", formatted)

    def test_main_window_valid_startup_starts_auto_backup_worker(self):
        from ui import main_window as main_window_module

        FakeAutoBackupWorker.instances = []
        switches = []

        def fake_switch_page(window, page_id):
            switches.append(page_id)

        fake_data_manager = type("FakeDataManager", (), {"db": object()})()
        current_user = {
            "User_ID": 7,
            "Full_Name": "Test User",
            "Permissions": ["nav_settings"],
        }

        with patch.object(main_window_module, "AutoBackupWorker", FakeAutoBackupWorker), \
             patch.object(main_window_module.MainWindow, "switch_page", fake_switch_page), \
             patch.object(QApplication, "exec", side_effect=AssertionError("startup smoke must not call app.exec()")):
            window = main_window_module.MainWindow(fake_data_manager, current_user, connection_error=None)

        self.assertEqual(switches, [4])
        self.assertIsNotNone(getattr(window, "content_area", None), "MainWindow should create a content area.")
        self.assertGreaterEqual(
            window.content_area.count(),
            10,
            "MainWindow startup should initialize page placeholders in the content area.",
        )
        self.assertIsNotNone(getattr(window, "sidebar_container", None), "MainWindow should create the sidebar.")
        self.assertTrue(
            any(button.isVisibleTo(window) or not button.isHidden() for button in window.nav_group.buttons()),
            "Fake valid user should have enough permissions to avoid a blank sidebar.",
        )
        window.resize(1400, 800)
        self.app.processEvents()
        self.assertGreaterEqual(window.width(), 1366)
        self.assertGreaterEqual(window.height(), 768)
        self.assertIsInstance(window.auto_backup_thread, FakeAutoBackupWorker)
        self.assertTrue(window.auto_backup_thread.started)
        self.assertIs(window.auto_backup_thread.data_manager, fake_data_manager)

        with patch.object(main_window_module.QMessageBox, "question", return_value=QMessageBox.Yes):
            window.close()

        self.assertTrue(window.auto_backup_thread.stopped)
        window.deleteLater()

    def test_main_window_database_unavailable_opens_settings_without_backup(self):
        from ui import main_window as main_window_module

        FakeAutoBackupWorker.instances = []
        switches = []

        def fake_switch_page(window, page_id):
            switches.append(page_id)

        with patch.object(main_window_module, "AutoBackupWorker", FakeAutoBackupWorker), \
             patch.object(main_window_module.MainWindow, "switch_page", fake_switch_page):
            window = main_window_module.MainWindow(
                data_manager=None,
                current_user=None,
                connection_error="database unavailable",
            )

        self.assertEqual(switches, [4])
        self.assertEqual(window.connection_error, "database unavailable")
        self.assertIsNone(window.auto_backup_thread)
        self.assertEqual(FakeAutoBackupWorker.instances, [])
        window.deleteLater()

    def test_auto_backup_worker_logs_skip_without_database_connection(self):
        from database.auto_backup_worker import AutoBackupWorker

        worker = AutoBackupWorker(data_manager=None)

        with self.assertLogs(level="INFO") as logs:
            worker.run()

        self.assertTrue(
            any("Auto-backup worker skipped: no database connection is available." in line for line in logs.output),
            "Auto-backup worker should log a clear skipped message when no database connection exists.",
        )

    def test_auto_backup_worker_one_cycle_uses_temp_config_and_fake_database(self):
        from database.auto_backup_worker import AutoBackupWorker

        class FakeBackupDb:
            def __init__(self):
                self.calls = []

            def create_multi_backup(self, backup_paths, password, is_auto=False):
                self.calls.append((backup_paths, password, is_auto))
                return True, "backup ok"

        class OneCycleWorker(AutoBackupWorker):
            def _sleep_check(self, seconds):
                self.sleep_seconds = seconds
                self.running = False

        fake_db = FakeBackupDb()
        fake_data_manager = type("FakeDataManager", (), {"db": fake_db})()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "config.json"
            backup_path = temp_path / "backups"
            backup_path.mkdir()
            config_path.write_text(
                json.dumps(
                    {
                        "auto_backup_enabled": True,
                        "auto_backup_interval": 0,
                        "auto_backup_password": "secret",
                        "backup_paths": [str(backup_path)],
                    }
                ),
                encoding="utf-8",
            )

            worker = OneCycleWorker(fake_data_manager)
            worker.config_file = str(config_path)
            with self.assertLogs(level="INFO") as logs:
                worker.run()

        self.assertEqual(fake_db.calls, [([str(backup_path)], "secret", True)])
        self.assertEqual(worker.sleep_seconds, 0)
        self.assertTrue(any("Auto-backup worker started" in line for line in logs.output))
        self.assertTrue(any("Auto-backup success" in line for line in logs.output))


if __name__ == "__main__":
    unittest.main()
