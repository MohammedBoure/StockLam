import ast
import importlib
import logging
import os
import py_compile
import sys
import tempfile
import unittest
from pathlib import Path

from dotenv import dotenv_values

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEPENDENCY_GROUPS = [
    ("Qt binding", ["pyside6"]),
    ("MySQL connector", ["mysql-connector-python"]),
    ("environment file loader", ["python-dotenv"]),
    ("Excel export engine", ["pandas", "xlsxwriter"]),
]
CRITICAL_MODULES = [
    "database",
    "database.base.connection",
    "ui.formatting",
]
DB_ENV_REQUIRED_KEYS = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER")
DB_ENV_OPTIONAL_KEYS = ("DB_PASSWORD",)
SAFE_TEST_DB_MARKERS = ("test", "dev", "sandbox", "local")
UNSAFE_DB_MARKERS = ("prod", "production", "real", "live")
DEFAULT_LIVE_DATABASE_NAMES = {"lab_inventory_enterprise_db"}


def missing_dependency_messages(requirement_text, dependency_groups=DEPENDENCY_GROUPS):
    normalized_text = str(requirement_text or "").lower()
    messages = []
    for feature, alternatives in dependency_groups:
        if not any(dependency in normalized_text for dependency in alternatives):
            messages.append(
                f"requirements.txt is missing dependency for {feature}. "
                f"Expected one of: {', '.join(alternatives)}"
            )
    return messages


def import_critical_modules(module_names=CRITICAL_MODULES, importer=importlib.import_module):
    failures = []
    for module_name in module_names:
        try:
            importer(module_name)
        except Exception as exc:
            failures.append(f"Failed to import critical module {module_name}: {exc!r}")
    if failures:
        raise AssertionError("\n".join(failures))


def compile_python_file_to_temp_pyc(source_path):
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / f"{Path(source_path).stem}.pyc"
        py_compile.compile(str(source_path), cfile=str(output_path), doraise=True)
        return output_path.exists()


def _call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def top_level_call_names(source):
    tree = ast.parse(source)
    calls = []

    def visit_statement(statement):
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return
        for node in ast.walk(statement):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(node, ast.Call):
                calls.append(_call_name(node.func))

    for statement in tree.body:
        visit_statement(statement)
    return calls


def main_function_calls(source):
    tree = ast.parse(source)
    for statement in tree.body:
        if isinstance(statement, ast.FunctionDef) and statement.name == "main":
            return [_call_name(node.func) for node in ast.walk(statement) if isinstance(node, ast.Call)]
    raise AssertionError("main.py does not define a main() function.")


def has_main_entrypoint_guard(source):
    tree = ast.parse(source)
    for statement in tree.body:
        if not isinstance(statement, ast.If):
            continue
        condition = ast.unparse(statement.test)
        if "__name__" not in condition or "__main__" not in condition:
            continue
        guarded_calls = [_call_name(node.func) for node in ast.walk(statement) if isinstance(node, ast.Call)]
        if "main" in guarded_calls:
            return True
    return False


def parse_db_env_fixture(path):
    values = dotenv_values(path)
    missing_keys = [key for key in DB_ENV_REQUIRED_KEYS if not str(values.get(key) or "").strip()]
    if missing_keys:
        raise ValueError(f"Missing required DB env settings: {', '.join(missing_keys)}")

    port_value = values.get("DB_PORT")
    try:
        port = int(port_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"DB_PORT must be numeric: {port_value}") from exc

    database = str(values.get("DB_NAME") or "").strip()
    user = str(values.get("DB_USER") or "").strip()
    if not database:
        raise ValueError("DB_NAME must not be empty")
    if not user:
        raise ValueError("DB_USER must not be empty")

    config = {
        "host": str(values.get("DB_HOST") or "").strip(),
        "port": port,
        "user": user,
        "password": values.get("DB_PASSWORD"),
        "database": database,
    }
    return config


def is_safe_test_database_name(name):
    text = str(name or "").strip().lower()
    if not text:
        return False

    normalized = text.replace("-", "_").replace(" ", "_")
    if normalized in DEFAULT_LIVE_DATABASE_NAMES:
        return False

    if any(token in text for token in UNSAFE_DB_MARKERS):
        return False

    return any(token in text for token in SAFE_TEST_DB_MARKERS)


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
    def test_project_virtualenv_python_exists(self):
        venv_python = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"

        self.assertTrue(
            venv_python.exists(),
            "Expected project virtual environment Python at venv\\Scripts\\python.exe.",
        )

    def test_requirements_file_declares_runtime_dependencies(self):
        requirements = PROJECT_ROOT / "requirements.txt"

        self.assertTrue(requirements.exists(), "requirements.txt must exist.")

        requirement_text = requirements.read_text(encoding="utf-8")
        missing_messages = missing_dependency_messages(requirement_text)

        self.assertEqual(missing_messages, [], "\n".join(missing_messages))

    def test_missing_dependency_messages_are_clear(self):
        messages = missing_dependency_messages(
            "PySide6\nmysql-connector-python\npython-dotenv\n",
            dependency_groups=DEPENDENCY_GROUPS,
        )

        self.assertEqual(len(messages), 1)
        self.assertIn("Excel export engine", messages[0])
        self.assertIn("pandas, xlsxwriter", messages[0])

    def test_active_python_process_is_project_compatible(self):
        self.assertGreaterEqual(
            sys.version_info[:2],
            (3, 10),
            f"Active Python is too old: {sys.version_info.major}.{sys.version_info.minor}",
        )
        self.assertTrue(sys.executable, "Active test process must expose sys.executable.")

    def test_critical_modules_import_without_opening_database(self):
        import_critical_modules()

    def test_import_failure_message_identifies_module_name(self):
        def fake_importer(module_name):
            if module_name == "database.base.connection":
                raise RuntimeError("blocked import")
            return object()

        with self.assertRaisesRegex(AssertionError, "database\\.base\\.connection"):
            import_critical_modules(importer=fake_importer)

    def test_main_py_syntax_compiles_without_running_application(self):
        main_path = PROJECT_ROOT / "main.py"
        self.assertTrue(main_path.exists(), "main.py must exist.")

        source = main_path.read_text(encoding="utf-8")
        compile(source, str(main_path), "exec")

        self.assertIn("def main(", source)
        self.assertIn("if __name__ == \"__main__\"", source)

    def test_main_py_compiles_with_py_compile_without_gui_or_database(self):
        main_path = PROJECT_ROOT / "main.py"
        self.assertTrue(main_path.exists(), "main.py must exist before startup readiness can be tested.")

        try:
            compiled = compile_python_file_to_temp_pyc(main_path)
        except py_compile.PyCompileError as exc:
            self.fail(f"main.py failed py_compile syntax check: {exc}")

        self.assertTrue(compiled, "main.py did not produce a temporary bytecode file during py_compile.")

    def test_main_py_has_startup_guard_and_exposes_main_function(self):
        main_path = PROJECT_ROOT / "main.py"
        source = main_path.read_text(encoding="utf-8")
        calls_inside_main = main_function_calls(source)

        self.assertIn(
            "QApplication",
            calls_inside_main,
            "main.py main() should contain GUI startup logic, but tests must not execute it.",
        )
        self.assertIn(
            "connect_to_database_with_retry",
            calls_inside_main,
            "main.py main() should contain database startup logic, but tests must not execute it.",
        )
        self.assertTrue(
            has_main_entrypoint_guard(source),
            'main.py must call main() only behind an `if __name__ == "__main__"` guard.',
        )

    def test_main_py_does_not_connect_to_database_or_open_gui_on_import(self):
        main_path = PROJECT_ROOT / "main.py"
        source = main_path.read_text(encoding="utf-8")
        calls = top_level_call_names(source)
        prohibited_top_level_calls = {
            "Database",
            "LabDataManager",
            "connect_to_database_with_retry",
            "QApplication",
            "MainWindow",
            "LoginDialog",
        }
        found = sorted(prohibited_top_level_calls.intersection(calls))

        self.assertEqual(
            found,
            [],
            (
                "main.py should not open MySQL or start GUI at import time. "
                f"Unexpected top-level startup calls: {', '.join(found)}"
            ),
        )

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

    def test_env_fixture_parser_does_not_depend_on_real_dotenv_file(self):
        real_env_path = PROJECT_ROOT / ".env"
        before = real_env_path.read_text(encoding="utf-8") if real_env_path.exists() else None

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture_path = Path(temp_dir) / ".env"
            fixture_path.write_text(
                "\n".join(
                    [
                        "DB_HOST=example.test",
                        "DB_PORT=4406",
                        "DB_USER=fixture_user",
                        "DB_PASSWORD=fixture_secret",
                        "DB_NAME=fixture_db_test",
                    ]
                ),
                encoding="utf-8",
            )

            config = parse_db_env_fixture(fixture_path)

        after = real_env_path.read_text(encoding="utf-8") if real_env_path.exists() else None

        self.assertEqual(config["host"], "example.test")
        self.assertEqual(config["port"], 4406)
        self.assertEqual(config["user"], "fixture_user")
        self.assertEqual(config["database"], "fixture_db_test")
        self.assertEqual(after, before, "Parsing a fixture .env must not modify the real project .env.")

    def test_env_fixture_parser_reports_missing_required_keys(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture_path = Path(temp_dir) / ".env"
            fixture_path.write_text(
                "\n".join(
                    [
                        "DB_HOST=127.0.0.1",
                        "DB_PORT=3306",
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "DB_NAME.*DB_USER"):
                parse_db_env_fixture(fixture_path)

    def test_env_fixture_parser_requires_numeric_port(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture_path = Path(temp_dir) / ".env"
            fixture_path.write_text(
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

            with self.assertRaisesRegex(ValueError, "DB_PORT must be numeric"):
                parse_db_env_fixture(fixture_path)

    def test_env_fixture_parser_rejects_empty_database_and_user(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture_path = Path(temp_dir) / ".env"
            fixture_path.write_text(
                "\n".join(
                    [
                        "DB_HOST=127.0.0.1",
                        "DB_PORT=3306",
                        "DB_USER=",
                        "DB_PASSWORD=secret",
                        "DB_NAME=",
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "DB_NAME.*DB_USER"):
                parse_db_env_fixture(fixture_path)

    def test_database_connection_uses_expected_env_keys_without_instantiating_database(self):
        connection_path = PROJECT_ROOT / "database" / "base" / "connection.py"
        source = connection_path.read_text(encoding="utf-8")

        for key in DB_ENV_REQUIRED_KEYS + DB_ENV_OPTIONAL_KEYS:
            with self.subTest(key=key):
                self.assertIn(
                    key,
                    source,
                    f"database/base/connection.py should read expected .env key {key}.",
                )

    def test_database_name_guard_accepts_expected_safe_names(self):
        safe_names = [
            "stocklam_test",
            "lab_inventory_enterprise_db_test",
            "stocklam_dev",
            "inventory_sandbox",
            "local_stocklam",
        ]

        for name in safe_names:
            self.assertTrue(is_safe_test_database_name(name), f"{name} should be safe for tests.")

    def test_database_name_guard_rejects_production_like_names(self):
        unsafe_names = [
            "",
            "Lab_Inventory_Enterprise_DB",
            "Lab Inventory Enterprise DB",
            "production_stocklam",
            "stocklam_prod",
            "real_inventory",
            "live_stocklam",
            "stocklam",
            "modernlam",
        ]

        for name in unsafe_names:
            self.assertFalse(is_safe_test_database_name(name), f"{name} should be rejected.")

    def test_default_live_database_name_is_safe_only_when_marked_for_tests(self):
        self.assertFalse(is_safe_test_database_name("Lab_Inventory_Enterprise_DB"))
        self.assertFalse(is_safe_test_database_name("lab inventory enterprise db"))
        self.assertTrue(is_safe_test_database_name("Lab_Inventory_Enterprise_DB_test"))

    def test_future_integration_tests_can_call_database_name_guard(self):
        candidate_database = "production_stocklam"

        self.assertFalse(
            is_safe_test_database_name(candidate_database),
            "Integration tests must reject production-like database names before opening a connection.",
        )

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
