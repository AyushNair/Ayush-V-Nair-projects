# ClearPrompt

ClearPrompt is a local-first Python web app for inspecting text before it is pasted into an AI application. Its interface takes inspiration from high-contrast Japanese comic and heist-game design: sharp red-and-black panels, cream paper, halftone texture, condensed headings, and energetic slashes. It uses no borrowed game art or characters.

## Run the desktop app (recommended)

Requirements: Python 3.10 or newer with Tcl/Tk included (the default for most Windows Python installs).

Double-click `run_desktop.bat`. This opens a native Windows app directly; it does not start a web server, use a browser, or need a firewall rule.

## Run the web app (optional)

The browser version is still available if local loopback access works on your computer:

Double-click `run_windows.bat`. It creates the project environment, installs Flask, starts the app, and opens the app in your default browser. Keep the terminal window open while using it.

Or run these commands in PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

Open **http://127.0.0.1:5000**. It runs on your computer and does not call an AI API or send scan content to a third party.

## What works

- Scan pasted text or upload a UTF-8 `.txt` file up to 1 MB.
- Detect email addresses, phone numbers, US SSN patterns, Luhn-valid payment card numbers, common API tokens, AWS access-key formats, and private-key headers.
- Turn individual detectors on or off and save custom keywords in the local policy.
- Apply **Warn**, **Redact**, or **Block**. Redaction returns sanitized text; blocking clears the input field and does not echo the submitted content in the result.
- Save policy settings and audit metadata in SQLite across restarts.
- View recent activity, export the complete audit as CSV, and clear the local audit log.
- Keep submitted content out of both the database and audit log. Audit records contain only UTC time, action, outcome, finding count, and finding types.
- Both the desktop and web interfaces use the same scanner, saved SQLite policy, and audit history.

## Project files

```text
app.py                  Flask app and JSON API
desktop_app.py          Native Windows desktop interface
storage.py              SQLite settings and audit storage
detector.py             Explainable detectors and text redaction
templates/index.html    Actual application interface
static/app.js           UI connected to the Flask API
static/style.css        Persona 5 inspired visual theme
tests/test_app.py       Backend and detector checks
run_windows.bat         Windows setup and launch helper
run_desktop.bat         Native desktop launcher (no local web server)
instance/               Created automatically for the local SQLite database
```

Run the checks with:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
```

## API routes

- `GET /api/health` — app status
- `GET /api/settings` and `PUT /api/settings` — read or save local policy
- `POST /api/scan` — scan submitted text
- `POST /api/scan-file` — scan an uploaded `.txt` file
- `GET /api/audit` — recent metadata-only audit events
- `GET /api/audit/export.csv` — download the audit as CSV
- `DELETE /api/audit` — clear audit history
- `GET /api/stats` — scan and active-detector counts

## Scope

This is a working educational prototype. It scans content submitted to its own page; it does not intercept prompts in ChatGPT or other AI applications. Its detectors use patterns, so they can miss data or flag ordinary text. It has no user accounts, organization-wide management, or production deployment hardening. Avoid using real secrets or personal information in demonstrations.
