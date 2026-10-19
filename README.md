# UPPCL X Complaint Monitoring & Google Sheets Management System

Enterprise-grade automated grievance monitoring, bilingual NLP classification, DISCOM routing, and Google Sheets synchronization system built for the **Uttar Pradesh Power Corporation Limited (UPPCL)** Social Media Cell.

---

## 1. System Overview

This system monitors public consumer complaints on X (formerly Twitter) mentioning the 6 official UPPCL apex authorities, classifies them across official grievance categories (Power Outage, Transformer Damage, Billing, Voltage, Pole/Wire Hazards, etc.), resolves the consumer's district to the corresponding DISCOM (MVVNL, PVVNL, PuVVNL, DVVNL, KESCo), prepares safe response drafts, and synchronizes all records directly into the operational Google Spreadsheet without disrupting existing columns or manual shift rosters.

### Key Highlights
- **6 Apex Monitored Handles**: `@UPPCLLKO`, `@EMofficeUP`, `@AKSharmaOffice`, `@aksharmaBharat`, `@ChairmanUppcl`, `@mduppcl`.
- **Authoritative 5-DISCOM UP Routing**: Maps all 75 districts of Uttar Pradesh across MVVNL, PVVNL, PuVVNL, DVVNL, and KESCo using official master records.
- **Multilingual Grievance NLP**: Recognizes Devanagari Hindi, English, and romanized Hinglish complaints, while accurately filtering out government PR announcements and general appreciation.
- **Strict Duplicate Prevention**: Dual-layer idempotency combining live Google Sheet post IDs with a local ACID SQLite checkpoint database in WAL mode.
- **Two-Phase Guarded Reply Engine**:
  - *Phase 1 (Default)*: Safe Draft Mode (`AUTO_POST_ENABLED = false`). Automatically drafts replies with PII scrubbing and queues for operator review.
  - *Phase 2 (Opt-In)*: Guarded automated posting with daily rate caps, emergency stop, allowlist enforcement, and audit logs.
- **Google Sheets Integrity**: Strictly preserves columns A through S, appending automation metadata in columns T through AF.

---

## 2. Directory Structure

```text
uppcl-x-complaint-system/
├── config/
│   ├── config.yaml               # Authoritative 75-district mapping, keywords & templates
│   └── service_account.json      # Google Cloud Service Account credentials (untracked)
├── google_apps_script/
│   ├── Code.gs                   # Google Apps Script UI menus, approval workflows & kill-switch
│   └── appsscript.json           # Apps Script manifest
├── scripts/
│   ├── deploy_windows_scheduler.ps1 # 5-minute automated scheduler deployment for Windows
│   ├── uppcl-sync.service        # systemd service unit for Linux / VM deployment
│   └── uppcl-sync.timer          # systemd timer for 5-minute periodic triggers
├── tests/
│   ├── test_checkpoint.py        # SQLite persistence and watermark tests
│   ├── test_classifier.py        # NLP classification and shift detection tests
│   ├── test_orchestrator.py      # End-to-end sync and duplicate suppression tests
│   ├── test_reply_engine.py      # PII redaction and safety guardrail tests
│   ├── test_router.py            # 75-district routing and alias resolution tests
│   ├── test_sheets_client.py     # Schema alignment and serialization tests
│   └── test_x_client.py          # X API v2 parsing and mock adapter tests
├── uppcl_x_automation/
│   ├── __init__.py
│   ├── __main__.py
│   ├── checkpoint.py             # SQLite WAL checkpoint & watermark store
│   ├── classifier.py             # Bilingual grievance classifier & PR filter
│   ├── cli.py                    # Command-line interface
│   ├── config.py                 # Configuration loader & validator
│   ├── orchestrator.py           # Master sync pipeline orchestrator
│   ├── reply_engine.py           # Safe drafting & auto-post guardrails
│   ├── router.py                 # 75-district DISCOM routing engine
│   ├── sheets_client.py          # Google Sheets API & offline CSV client
│   └── x_client.py               # Official X API v2 client & mock replay adapter
├── .env.example                  # Environment configuration template
├── .gitignore                    # Credential and artifact exclusions
├── Dockerfile                    # Container definition for Cloud Run / Docker
├── pyproject.toml                # Project packaging metadata
├── requirements.txt              # Pinned Python dependencies
├── ARCHITECTURE.md               # Technical report & approach comparison
└── README.md                     # System documentation & operational guide
```

---

## 3. Quickstart & Installation

### Step 1: Clone or Navigate to Project
```powershell
cd C:\Users\tripa\.gemini\antigravity\scratch\uppcl-x-complaint-system
```

### Step 2: Initialize Virtual Environment & Install Dependencies
Using `uv`:
```powershell
& "C:\Users\tripa\.local\bin\uv.exe" venv --python 3.12 .venv
& "C:\Users\tripa\.local\bin\uv.exe" pip install -r requirements.txt
```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
Edit `.env` with your preferred editor:
- Set `X_BEARER_TOKEN` with your X Developer Portal bearer token.
- Set `GOOGLE_SERVICE_ACCOUNT_FILE=config/service_account.json` (see Google Cloud setup below).
- Keep `DRY_RUN=true` and `AUTO_POST_ENABLED=false` until verification is complete.

---

## 4. Google Sheets API Authorization

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g., `uppcl-complaint-monitor`).
3. Enable the **Google Sheets API** and **Google Drive API**:
   - Navigation Menu -> **APIs & Services** -> **Library** -> Search for `Google Sheets API` -> Click **Enable**.
4. Create a Service Account:
   - **APIs & Services** -> **Credentials** -> **Create Credentials** -> **Service Account**.
   - Name it `uppcl-sheets-sync`.
   - Click **Done**.
5. Generate a JSON Key:
   - Click the newly created service account -> **Keys** tab -> **Add Key** -> **Create new key** -> **JSON**.
   - Save this key as `config/service_account.json` in this project directory.
6. Share the Spreadsheet with the Service Account:
   - Copy the service account email (e.g., `uppcl-sheets-sync@project-id.iam.gserviceaccount.com`).
   - Open the target Google Sheet: [Twitter Complaint List](https://docs.google.com/spreadsheets/d/12smJ_xw3sRWPcCzDsh_hC44ac2NlpO9I_wDnXF-wFXU/edit).
   - Click **Share** (top right) -> Paste the service account email -> Grant **Editor** access -> Click **Send**.

---

## 5. X Developer Portal Authorization

1. Visit the [X Developer Portal](https://developer.x.com).
2. Create an App under your Project.
3. In the **Keys and Tokens** section:
   - Copy the **Bearer Token** into `X_BEARER_TOKEN` in `.env`.
4. If enabling automated replies (Phase 2):
   - Under **User authentication settings**, set permissions to **Read and Write**.
   - Generate **OAuth 1.0a / OAuth 2.0 User Access Tokens** and populate `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, and `X_ACCESS_TOKEN_SECRET` in `.env`.

---

## 6. CLI Usage & Operations

All commands can be executed via the virtual environment:

### A. Run a Dry-Run Sync (Safe Simulation)
```powershell
& "C:\Users\tripa\.local\bin\uv.exe" run python -m uppcl_x_automation.cli sync --dry-run
```
*Queries posts, performs NLP classification, runs 75-district routing, prepares drafts, checks duplicates against the live Google Sheet, and reports results without writing changes.*

### B. Run a Live Sync Cycle
```powershell
& "C:\Users\tripa\.local\bin\uv.exe" run python -m uppcl_x_automation.cli sync
```

### C. Run as Continuous Background Polling Daemon
```powershell
& "C:\Users\tripa\.local\bin\uv.exe" run python -m uppcl_x_automation.cli sync --daemon
```

### D. Check Database Status and Metrics
```powershell
& "C:\Users\tripa\.local\bin\uv.exe" run python -m uppcl_x_automation.cli status
```

### E. Test Classification and Routing on Sample Text
```powershell
& "C:\Users\tripa\.local\bin\uv.exe" run python -m uppcl_x_automation.cli test-routing --text "@UPPCLLKO बनारस अस्सी घाट के पास 63 KVA ट्रांसफार्मर फुंक गया है, तुरंत बदलें"
```

---

## 7. Running the Automated Test Suite

To verify all 39 unit and integration tests:
```powershell
& "C:\Users\tripa\.local\bin\uv.exe" run python -m pytest -v
```

---

## 8. Continuous Scheduler Deployment

### On Windows (Windows Task Scheduler):
Run the provided PowerShell deployment script as Administrator:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy_windows_scheduler.ps1 -IntervalMinutes 5
```
*This registers a background scheduled task named `UPPCL_X_Complaint_Monitor` that wakes up every 5 minutes.*

To uninstall:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy_windows_scheduler.ps1 -Uninstall
```

### On Linux / Virtual Machine (`systemd`):
```bash
sudo cp scripts/uppcl-sync.service /etc/systemd/system/
sudo cp scripts/uppcl-sync.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now uppcl-sync.timer
```

---

## 9. Google Apps Script Integration (Custom Sheets Menu)

1. Open your target Google Sheet.
2. In the top menu, go to **Extensions** -> **Apps Script**.
3. Replace any default code with the contents of `google_apps_script/Code.gs`.
4. Click **Save** (disk icon), then click **Run** on `onOpen`.
5. Return to your spreadsheet; a new menu **UPPCL Automation** will appear with:
   - **Setup Supporting Tabs**: Generates `Settings`, `Processing Log`, and `Dashboard` tabs.
   - **Review Pending Drafts**: Highlights ambiguous records needing operator review.
   - **Approve Selected Rows**: Approves highlighted drafts.
   - **Emergency Stop: ENGAGE / RELEASE**: Global kill-switch for automated posting.

---

## 10. Emergency Stop & Disaster Recovery

- **Immediate Stop via Environment**:
  In `.env`, set:
  ```env
  EMERGENCY_STOP=true
  ```
- **Immediate Stop via Google Sheet**:
  Go to the `Settings` tab in the Google Sheet and change `EMERGENCY_STOP` to `TRUE`, or use the **UPPCL Automation** menu.
- **Database Backup**:
  The SQLite database file is located at `data/uppcl_monitor.db`. It runs in WAL mode and can be backed up at any time by copying the file.
