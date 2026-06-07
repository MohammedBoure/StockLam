# Startup Checks Test Prompts

These prompts are designed to generate automated and semi-automated checks for section `1.2 Startup Checks` in `docs/tests/comprehensive-application-test-plan.md`.

## General Instructions for All Prompts

Apply these constraints to every prompt in this document:

- Work inside the existing StockLam project.
- Do not use the real production database.
- Do not modify `.env`, `config.json`, or local machine settings.
- Prefer `unittest` unless the project already has another active test framework.
- Use temporary files/directories for generated logs, configs, and runtime artifacts.
- Use mocks/fakes for database access and GUI startup when possible.
- Do not start a blocking GUI event loop in automated tests.
- Use `QT_QPA_PLATFORM=offscreen` for PySide6 tests.
- Keep tests deterministic and suitable for CI/local execution.
- Avoid network access.
- Do not install dependencies.
- Do not call `pip`.
- Do not touch unrelated files.
- After changes, run:
  - `venv\Scripts\python.exe -m compileall database ui test`
  - `venv\Scripts\python.exe -m unittest discover`

## Prompt 1: Add Startup Checks Test Module

You are working inside StockLam.

Goal:
Create automated tests for section `1.2 Startup Checks` from:
`docs/tests/comprehensive-application-test-plan.md`

Target checklist:
- Run `venv\Scripts\python.exe -m compileall database ui test`.
- Run `venv\Scripts\python.exe -m unittest discover`.
- Start application with valid database connection.
- Start application with database unavailable.
- Verify auto-backup worker startup.

Create or update:
`test/test_startup_checks.py`

Rules:
- Do not use a real MySQL database.
- Do not launch the full GUI event loop.
- Do not modify `.env` or `config.json`.
- Use `unittest`.
- Use `subprocess.run` only for safe, finite commands with timeouts.
- Use mocks/fakes for database manager, connection failures, and backup worker startup.
- Use `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` before importing PySide6 widgets.

Implement focused tests that validate:
1. The compile command is structurally runnable from the project virtual environment.
2. A safe compileall subprocess returns exit code `0`.
3. The test suite command is documented and runnable outside the tests.
4. A valid-database startup path can be simulated with fake database objects and offscreen widgets.
5. A database-unavailable startup path reports a controlled error without crashing.
6. The auto-backup worker starts only when a usable data manager/database exists.
7. The auto-backup worker logs a clear skipped message when no database connection exists.

Important:
- Do not create a test that recursively runs `unittest discover` during normal `unittest discover`.
- If a full nested test-suite smoke is needed, guard it behind an environment variable such as `STOCKLAM_RUN_NESTED_TEST_DISCOVER=1` and skip it by default.

Acceptance:
- `venv\Scripts\python.exe -m compileall database ui test` passes.
- `venv\Scripts\python.exe -m unittest discover` passes.
- No real database connection is opened.
- No blocking GUI process remains open.
- Failures clearly explain whether the problem is compile, startup, database handling, or auto-backup handling.

## Prompt 2: Test Compileall Command

You are working inside StockLam.

Add tests for the checklist item:
`Run venv\Scripts\python.exe -m compileall database ui test`

Target:
`test/test_startup_checks.py`

Cover:
- `venv\Scripts\python.exe` exists.
- The directories `database`, `ui`, and `test` exist.
- The command can be executed safely with:
  `subprocess.run([venv_python, "-m", "compileall", "database", "ui", "test"], timeout=120, capture_output=True, text=True)`
- The command returns exit code `0`.
- On failure, the assertion message includes stdout/stderr so syntax/import issues are easy to diagnose.

Rules:
- Do not use shell=True.
- Do not write outside the workspace.
- Do not hide stderr.
- Do not skip this test unless the virtual environment Python executable is missing; if skipped, the skip reason must be clear.

Acceptance:
- The test proves the compile command succeeds in the current project state.
- A compile failure identifies the failing file or compile output.

## Prompt 3: Test Unittest Discover Command Safely

You are working inside StockLam.

Add checks for the checklist item:
`Run venv\Scripts\python.exe -m unittest discover`

Important:
Running `unittest discover` from inside a test that is itself discovered can create recursion or double execution. Avoid that by default.

Implement one of these safe approaches:

Preferred approach:
- Add a metadata/documentation test that verifies:
  - `test` directory exists.
  - At least one `test_*.py` file exists.
  - `unittest` can discover test cases programmatically using `unittest.TestLoader().discover("test")`.
  - Discovered suite has a non-zero number of test cases.

Optional guarded approach:
- Add a skipped-by-default subprocess test.
- It only runs when `STOCKLAM_RUN_NESTED_TEST_DISCOVER=1`.
- It executes:
  `subprocess.run([venv_python, "-m", "unittest", "discover"], timeout=180, capture_output=True, text=True)`
- It asserts return code `0`.

Rules:
- Do not recursively run the full suite by default.
- Do not use shell=True.
- Do not require network or MySQL.
- Ensure failure messages show discovered count or subprocess output.

Acceptance:
- Normal `venv\Scripts\python.exe -m unittest discover` does not recurse indefinitely.
- The test confirms that unittest discovery is structurally healthy.
- Optional full-suite subprocess smoke is available only when explicitly enabled.

## Prompt 4: Simulate Startup With Valid Database Connection

You are working inside StockLam.

Add tests for the checklist item:
`Start application with valid database connection.`

Goal:
Verify the main UI startup path can be constructed with fake valid dependencies, without opening a real database connection or blocking GUI loop.

Read first:
- `main.py`
- `ui/main_window.py`
- `database/__init__.py`
- `ui/login_dialog.py`

Target:
`test/test_startup_checks.py`

Use:
- `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")`
- `QApplication.instance() or QApplication([])`
- Fake data manager with the attributes/methods that `MainWindow` and startup code require.
- Monkeypatch `database.auto_backup_worker.AutoBackupWorker` or `ui.main_window.AutoBackupWorker` with a fake worker that records whether `start()` was called.

Cover:
- Main startup dependencies can be imported safely without connecting to MySQL.
- `MainWindow(fake_data_manager, current_user=fake_user)` can be constructed, resized, and closed under offscreen mode.
- The fake user has enough navigation permissions to avoid a blank window.
- The window has a content area or sidebar after construction.
- No blocking `app.exec()` is called.
- The fake auto-backup worker is started only as part of main window construction if that is the existing behavior.

Rules:
- Do not call `main.main()` if it starts the real app loop or real DB.
- Do not instantiate the real `LabDataManager` unless fully mocked to avoid DB access.
- Do not show a real window.
- Clean up widgets with `close()` and `deleteLater()`.

Acceptance:
- The test proves a valid startup path can build the main window with fake valid dependencies.
- The test does not open MySQL.
- The test does not leave Qt windows or threads running.

## Prompt 5: Simulate Startup With Database Unavailable

You are working inside StockLam.

Add tests for the checklist item:
`Start application with database unavailable.`

Goal:
Verify database connection failure is handled in a controlled way and does not crash the startup path.

Read first:
- `main.py`
- `database/base/connection.py`
- `ui/main_window.py`

Target:
`test/test_startup_checks.py`

Cover:
- Monkeypatch the database connection initializer or data manager creation to raise a controlled exception.
- If `main.py` has a helper for initialization, call that helper with mocks.
- If startup logic is tightly coupled to `main()`, test the smaller import/constructor paths and document that full DB-unavailable startup remains a manual checklist item.
- Construct `MainWindow` with `connection_error=True` or the project equivalent if supported.
- Verify the UI does not attempt to open normal pages that require database access.
- Verify Settings or the intended fallback page remains accessible if that is the current behavior.
- Verify a clear error message is logged or returned.

Rules:
- Do not use a real MySQL server.
- Do not modify `.env`.
- Do not display real modal dialogs; monkeypatch `QMessageBox`.
- Do not call blocking `app.exec()`.

Acceptance:
- The database-unavailable path returns/records a clear error instead of raising an unhandled exception.
- No real DB connection is attempted.
- The test explains any remaining manual verification needed for the exact visible login/main-window behavior.

## Prompt 6: Test Auto-Backup Worker Startup

You are working inside StockLam.

Add tests for the checklist item:
`Verify auto-backup worker startup.`

Read first:
- `database/auto_backup_worker.py`
- `ui/main_window.py`
- `ui/widgets/settings/settings_tab.py`
- `database/base/backup_manager.py`

Target:
`test/test_startup_checks.py`

Cover:
- `AutoBackupWorker` constructed with a data manager that has no usable `db` logs/skips safely.
- The worker does not call backup when there is no database connection.
- When auto-backup is disabled in fake settings/config, backup is not executed.
- When auto-backup is enabled and fake backup paths exist, the worker calls `create_multi_backup(paths, password, is_auto=True)` exactly once in a controlled single-iteration test.
- Success from `create_multi_backup` writes or triggers a success log message.
- Failure from `create_multi_backup` writes or triggers a warning log message.
- Exceptions from backup do not crash the test and are logged as critical errors.

Implementation guidance:
- Avoid running the real infinite thread loop.
- If `AutoBackupWorker.run()` loops forever, add a tiny test seam only if necessary, such as an internal `_run_once()` helper, while preserving production behavior.
- Prefer monkeypatching sleep/wait behavior and using fake settings.
- Use `assertLogs` to verify messages.

Rules:
- Do not write real backup files.
- Do not use real backup paths except temporary directories.
- Do not start a long-running `QThread`.
- Do not leave threads running after tests.

Acceptance:
- Auto-backup startup behavior is verified without creating real backups.
- Enabled/disabled/no-db/success/failure paths are covered.
- Logs are clear enough to support the checklist evidence.

## Prompt 7: Optional Manual Verification Notes for Real Startup

You are working inside StockLam.

Create or update a small manual verification section in the test documentation for checklist rows that cannot be safely automated without a real test database:
- Start application with valid database connection.
- Start application with database unavailable.
- Verify auto-backup worker startup in the real application.

Target:
Either update `docs/tests/comprehensive-application-test-plan.md` notes, or create:
`docs/tests/startup-manual-verification.md`

Document:
1. Preconditions:
   - Use a dedicated test database only.
   - Confirm database name contains `test`, `dev`, `sandbox`, or `local`.
   - Never use production data.
2. Valid database startup:
   - Start from venv with `python main.py`.
   - Confirm login/main window opens.
   - Capture log evidence.
3. Database unavailable:
   - Temporarily point to a safe invalid test host or stop only the test DB service.
   - Confirm clear error message and no crash.
   - Restore original test-only settings afterward.
4. Auto-backup:
   - Use a temporary backup directory.
   - Enable auto-backup in settings.
   - Confirm worker log says it started.
   - Confirm it only creates backups in the temporary directory.

Rules:
- Do not instruct users to change production settings.
- Do not include real passwords.
- Do not mark checkboxes `[x]` automatically.
- Make it clear that evidence should be recorded before checklist completion.

Acceptance:
- Manual steps are clear, safe, and repeatable.
- The checklist remains honest: `[x]` means actually verified.

## Prompt 8: Full Implementation Prompt for Section 1.2

You are working inside StockLam.

Goal:
Implement the best possible automated tests and documentation support for section `1.2 Startup Checks` from:
`docs/tests/comprehensive-application-test-plan.md`

Create or update:
- `test/test_startup_checks.py`
- Optional: `docs/tests/startup-manual-verification.md`

Checklist rows:
- Run `venv\Scripts\python.exe -m compileall database ui test`.
- Run `venv\Scripts\python.exe -m unittest discover`.
- Start application with valid database connection.
- Start application with database unavailable.
- Verify auto-backup worker startup.

Hard constraints:
- Do not use a real MySQL database.
- Do not modify `.env`.
- Do not modify `config.json`.
- Do not start a blocking GUI.
- Do not install packages.
- Do not access the network.
- Do not touch unrelated files.

Implementation expectations:
- Add `unittest` tests for compileall command execution.
- Add safe unittest discovery checks without recursive default execution.
- Add offscreen Qt startup smoke tests using fake data manager/current user.
- Add database-unavailable smoke tests with monkeypatched connection failure.
- Add auto-backup worker tests using fake DB/settings and no real backup files.
- Use clear skip reasons for anything that must remain manual.

After implementation run:
- `venv\Scripts\python.exe -m compileall database ui test`
- `venv\Scripts\python.exe -m unittest discover`

Final response must include:
- Tests added.
- Checklist rows covered automatically.
- Checklist rows still requiring manual verification.
- Commands run.
- Any risks or limitations.
