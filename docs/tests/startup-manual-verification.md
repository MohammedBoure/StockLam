# Startup Manual Verification

This note covers startup checklist rows that should not be fully automated unless a dedicated test database is available. Record evidence before marking any related checklist row as `[x]` in `comprehensive-application-test-plan.md`.

## Preconditions

- Use a dedicated test database only.
- Confirm the database name clearly contains `test`, `dev`, `sandbox`, or `local`.
- Never use production data, production credentials, or production backup paths.
- Do not write real passwords in this document, screenshots, tickets, or logs.
- Save evidence for each completed row: timestamp, tester, commit hash, database name, screenshots if useful, and relevant `app.log` lines.
- Restore all test-only settings after each manual run.

## Valid Database Startup

1. Confirm `.env` points to the dedicated test database.
2. Confirm the database name contains `test`, `dev`, `sandbox`, or `local`.
3. Start the application from the project virtual environment:

   ```powershell
   venv\Scripts\python.exe main.py
   ```

4. Confirm the database connection dialog reports success.
5. Confirm the login dialog or main window opens normally.
6. Log in with a test user only.
7. Confirm the sidebar and first permitted page render without a blank window.
8. Save evidence from `app.log`, including the database target and successful initialization message.
9. Mark the checklist row `[x]` only after the visible startup and log evidence are confirmed.

## Database Unavailable Startup

1. Work only with test-only settings.
2. Temporarily point `.env` to a safe invalid test host, or stop only the test database service.
3. Start the application from the project virtual environment:

   ```powershell
   venv\Scripts\python.exe main.py
   ```

4. Confirm the application shows a clear database connection error.
5. Confirm the application does not crash.
6. Confirm Settings or the intended database configuration fallback remains accessible.
7. Save evidence from `app.log`, including the controlled connection error.
8. Restore the original test-only `.env` or restart the test database service.
9. Restart once with the valid test database to confirm recovery.
10. Mark the checklist row `[x]` only after the failure behavior and recovery are both verified.

## Auto-Backup Worker Startup

1. Use a temporary backup directory created only for this test.
2. Confirm the application is connected to a dedicated test database.
3. In Settings, enable auto-backup using the temporary directory.
4. Use a short test interval only if it is safe for the local environment.
5. Start or restart the application from the project virtual environment:

   ```powershell
   venv\Scripts\python.exe main.py
   ```

6. Confirm `app.log` records that the auto-backup worker started.
7. Confirm backup files are created only inside the temporary directory.
8. Confirm no production backup directory is touched.
9. Disable auto-backup or restore the previous test-only setting after evidence is collected.
10. Remove the temporary backup directory when it is no longer needed.
11. Mark the checklist row `[x]` only after logs and file evidence confirm the worker used the temporary directory.

## Evidence Template

Use this template in the checklist notes, a ticket, or a release record:

```text
Checklist row:
Tester:
Date/time:
Commit hash:
Database name:
Environment:
Result:
Evidence files/log lines:
Notes:
```
