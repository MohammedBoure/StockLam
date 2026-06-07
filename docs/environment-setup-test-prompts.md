# Environment Setup Test Prompts

These prompts are designed to generate automated and semi-automated tests for section `1.1 Environment Setup` in `docs/comprehensive-application-test-plan.md`.

Use them one by one with an AI coding assistant working inside the StockLam repository.

## General Instructions for All Prompts

Apply these constraints to every prompt in this document:

- Work inside the existing StockLam project.
- Do not use the real production database.
- Do not modify `.env`, `config.json`, or local machine settings.
- Prefer `unittest` unless the project already has another active test framework.
- Use temporary files/directories for generated logs and config fixtures.
- Use mocks/fakes for database and GUI startup when possible.
- Do not start a real long-running GUI process in automated tests.
- Use `QT_QPA_PLATFORM=offscreen` for PySide6 tests.
- Keep tests deterministic and suitable for CI/local execution.
- Avoid network access.
- Do not touch unrelated files.
- After changes, run:
  - `venv\Scripts\python.exe -m compileall database ui test`
  - `venv\Scripts\python.exe -m unittest discover`

## Prompt 1: Create a Test File for Environment Setup Checks

```text
You are working inside the StockLam project.

Goal:
Create automated tests for the "1.1 Environment Setup" section from:
docs/comprehensive-application-test-plan.md

Target checklist:
- Install dependencies inside the project virtual environment.
- Start the application from `venv` using `python main.py`.
- Verify `.env` database settings.
- Verify the application does not use production data during testing.
- Verify logs are written and readable.
- Verify screen resolution support: small laptop, standard desktop, wide screen.

Create or update:
test/test_environment_setup.py

Rules:
- Do not use a real MySQL connection.
- Do not launch the full GUI event loop in a blocking way.
- Do not modify `.env` or `config.json`.
- Use `unittest`.
- Use temporary files and monkeypatching/mocking.
- Use `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` before importing PySide6 widgets.
- Tests must pass on Windows PowerShell with:
  venv\Scripts\python.exe -m unittest discover

Implement focused tests that validate:
1. The project virtualenv Python executable exists at `venv\Scripts\python.exe`.
2. `requirements.txt` exists and contains key runtime dependencies used by the app.
3. `main.py` exists and can be imported or syntax-compiled without running the full app.
4. The `.env` parser/config loader can read database settings from a temporary fixture file.
5. A config safety helper or test helper detects production-like database names and rejects them for tests.
6. Log writing can create a temporary log file and read back a known message.
7. Main window or key widgets can be constructed under offscreen mode with fake/mocked data manager.
8. Main window/widget layout can resize to representative sizes: 1366x768, 1920x1080, 1024x600.

If production code is hard to test directly, add tiny helper functions only when necessary and keep them isolated.

Acceptance:
- `venv\Scripts\python.exe -m compileall database ui test` passes.
- `venv\Scripts\python.exe -m unittest discover` passes.
- No real database connection is opened.
- No real GUI window remains open after tests.
```

## Prompt 2: Test Virtual Environment and Dependency Readiness

```text
You are working inside StockLam.

Add tests to `test/test_environment_setup.py` for virtual environment and dependency readiness.

Cover:
- `venv\Scripts\python.exe` exists.
- `requirements.txt` exists.
- `requirements.txt` includes important app dependencies, at minimum:
  - PySide6 or the actual Qt binding used by the project.
  - mysql-connector-python or the actual MySQL connector used by the project.
  - pandas or xlsxwriter if Excel export is supported.
- The active test process is running under a Python executable compatible with the project.
- Import checks for critical modules should be safe and should not open the app:
  - `database`
  - `database.base.connection`
  - `ui.formatting`

Rules:
- Do not install dependencies.
- Do not call pip.
- Do not access the network.
- Do not start `main.py`.
- Use `unittest`.

Expected tests:
- Missing dependency text should produce a clear assertion message.
- Import failures should identify which module failed.
```

## Prompt 3: Test Main Application Startup Safely

```text
You are working inside StockLam.

Add tests that validate startup readiness without launching the real full application.

Target:
Checklist item: "Start the application from `venv` using `python main.py`."

Do not run a blocking GUI.
Instead, implement smoke tests that prove startup is structurally safe:

Cover:
- `main.py` exists.
- `main.py` compiles with `py_compile`.
- Importing startup dependencies does not immediately connect to MySQL unless explicitly invoked.
- If `main.py` exposes a function such as `main()`, inspect it safely without calling the blocking GUI loop.
- If the app startup code uses side effects on import, avoid importing `main.py` directly and use `py_compile` plus source inspection.

Optional:
- Use `subprocess.run` with a very small timeout only for a non-GUI command if the app has a safe flag such as `--help` or `--check`.
- If no safe flag exists, document that automated tests validate compile/import readiness only and manual startup remains in the manual checklist.

Acceptance:
- No real GUI event loop is started.
- No real MySQL connection is opened.
- Test failure clearly explains whether the problem is syntax, import, or missing startup guard.
```

## Prompt 4: Test `.env` Database Settings With Temporary Fixtures

```text
You are working inside StockLam.

Add tests for the checklist item:
"Verify `.env` database settings."

Use temporary fixture files instead of the real `.env`.

Read these files first:
- database/base/config.py
- database/base/connection.py

Cover:
- A valid fixture `.env` containing host, port, database, and user can be parsed by the existing config loader or a small test helper.
- Required fields are present:
  - DB_HOST or actual project key.
  - DB_PORT or actual project key.
  - DB_NAME or actual project key.
  - DB_USER or actual project key.
- Port is numeric.
- Database name is not empty.
- User is not empty.
- Missing required values produce a controlled failure in the test helper.

Rules:
- Do not overwrite the real `.env`.
- Do not print passwords.
- Do not connect to MySQL.
- If the production config loader reads only from the real `.env`, add a test-only helper in the test file to parse fixture text and validate the project's expected keys.

Acceptance:
- Tests verify valid and invalid env fixtures.
- Tests are independent from the developer's local `.env`.
```

## Prompt 5: Add Test Database Safety Checks

```text
You are working inside StockLam.

Add tests for the checklist item:
"Verify the application does not use production data during testing."

Goal:
Prevent automated tests from accidentally targeting production-like database names.

Implement a small helper if needed in `test/test_environment_setup.py`:
`is_safe_test_database_name(name: str) -> bool`

Suggested safe rules:
- Accept names containing `test`, `dev`, `sandbox`, or `local`.
- Reject empty names.
- Reject names containing `prod`, `production`, `real`, or obvious live deployment names.
- Reject names equal to the default live-looking database if the project uses one, unless it includes `test`.

Tests:
- `stocklam_test` is safe.
- `lab_inventory_enterprise_db_test` is safe.
- `Lab_Inventory_Enterprise_DB` is unsafe unless explicitly configured as test.
- `production_stocklam` is unsafe.
- Empty database name is unsafe.

Rules:
- Do not modify real configuration.
- Do not connect to MySQL.
- Keep this as a guardrail test/helper, not as a migration.

Acceptance:
- The helper is covered by unit tests.
- A future test suite can call the helper before any integration test that might touch a database.
```

## Prompt 6: Test Log Writing and Readability

```text
You are working inside StockLam.

Add tests for the checklist item:
"Verify logs are written and readable."

Use temporary directories/files only.

Cover:
- A logger can write a known startup-like message to a temporary file.
- The file exists after logging.
- The file content can be read back.
- The known message appears in the file.
- Error-level messages can also be written and read.
- Log handlers are cleaned up at the end of the test so they do not affect other tests.

Rules:
- Do not write into the real application log path.
- Do not depend on existing log files.
- Do not leave open file handlers.
- Use `tempfile.TemporaryDirectory`.

Acceptance:
- Tests pass repeatedly.
- Tests do not pollute project logs.
```

## Prompt 7: Test Screen Resolution Support With Offscreen Qt

```text
You are working inside StockLam.

Add UI tests for the checklist item:
"Verify screen resolution support: small laptop, standard desktop, wide screen."

Use PySide6 in offscreen mode:
`os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")`

Target:
- Prefer testing a real key widget if it can be constructed safely with fake dependencies.
- If full MainWindow construction requires a real database, test representative top-level widgets/pages with fake data managers.
- Candidate widgets:
  - ui.main_window.MainWindow if it can be safely mocked.
  - ui.widgets.inventory.inventory_count_tab.InventoryCountTab.
  - Other dashboard/main content widgets that can be constructed without DB.

Cover sizes:
- 1024x600 small screen.
- 1366x768 laptop.
- 1920x1080 desktop.

Assertions:
- Widget can resize to each size without exception.
- Important controls remain visible.
- No required table or navigation area has zero width/height.
- Text-heavy buttons have non-zero size hints.
- For Inventaire page, sessions table, lines table, and action panel remain present.

Rules:
- Do not show a real blocking GUI.
- Use `QApplication.instance() or QApplication([])`.
- Call `widget.resize(width, height)` and `QApplication.processEvents()`.
- Destroy widgets with `deleteLater()`.

Acceptance:
- Tests run under `unittest discover`.
- Tests do not require a real monitor or database.
```

## Prompt 8: Update the Checklist Automatically Only When Tests Pass

```text
You are working inside StockLam.

Goal:
Create a safe helper script or documentation workflow that updates the checkboxes in:
docs/comprehensive-application-test-plan.md

Specifically for section:
1.1 Environment Setup

Important:
Do not automatically mark `[x]` unless the related automated test has passed and the user explicitly asks to update the checklist.

Create either:
- A documentation note explaining how to update the checklist manually, or
- A small script under `tools/` that can update only the selected checklist rows after confirmation.

Rules:
- Do not change checkbox states by default.
- Do not mark tests complete just because code exists.
- Preserve the Markdown table structure.
- Keep this optional and safe.

Acceptance:
- The workflow makes it clear that `[x]` means tested and verified.
- No checklist item is marked complete without explicit instruction.
```

## Prompt 9: Full Implementation Prompt for Section 1.1

```text
You are working inside StockLam.

Implement the best possible automated tests for section `1.1 Environment Setup` from:
docs/comprehensive-application-test-plan.md

Create:
test/test_environment_setup.py

Read first:
- docs/comprehensive-application-test-plan.md
- requirements.txt
- main.py
- database/base/config.py
- database/base/connection.py
- ui/main_window.py
- ui/widgets/inventory/inventory_count_tab.py

Test coverage target:
- Environment prerequisites.
- Requirements file presence and key dependencies.
- Safe startup compile/smoke checks.
- `.env` database settings validation using temporary fixture text.
- Protection against production database names in tests.
- Temporary log writing/readability.
- Offscreen Qt layout resize smoke checks for key widgets.

Hard constraints:
- Do not use a real MySQL database.
- Do not modify `.env`.
- Do not modify `config.json`.
- Do not start a blocking GUI.
- Do not install packages.
- Do not access network.
- Do not touch unrelated files.

After implementation run:
- `venv\Scripts\python.exe -m compileall database ui test`
- `venv\Scripts\python.exe -m unittest discover`

Final response must include:
- Tests added.
- What checklist rows they cover.
- Commands run.
- Any checklist rows that still require manual verification.
```

