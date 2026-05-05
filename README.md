# Pipedrive Month-End Report — Automation

Pulls deal data from Pipedrive at the end of each month, generates two CSV reports, and emails them to Dave and Grayson automatically via Task Scheduler.

---

## What it does

On the last day of each month at 9 PM, this automation:

1. Hits the Pipedrive API and pulls all open, won, and lost deals
2. Writes two CSVs to the configured output directory:
   - `Sales_Monthly_YYYY-MM-DD.csv` — summary row Dave pastes into the RightClick Tech Monthly Scorecard
   - `Deal_Details_YYYY-MM-DD.csv` — full open deal list for reference
3. Emails both files to Dave (To) and Grayson (CC) via smtp.com

---

## Files

| File | Purpose |
|---|---|
| `pipeline_snapshot.py` | Pulls Pipedrive data, writes the two CSVs |
| `email_snapshot.py` | Finds the CSVs, sends the email via SMTP |
| `run_snapshot.bat` | Manual test — runs snapshot only, no email |
| `run_month_end.bat` | Full automation — snapshot + email |
| `.env` | Config and credentials (not committed to git) |

---

## Setup

### 1. Prerequisites

Confirm Python is installed:
```powershell
python --version
```

Install the two required packages:
```powershell
pip install httpx python-dotenv
```

### 2. Configure .env

Create a `.env` file in the same folder as the scripts. Use this as your template:

**Two things you must fill in before running:**
- `PIPEDRIVE_API_TOKEN` — found in Pipedrive under Settings → Personal Preferences → API
- `SNAPSHOT_OUTPUT_DIR` — the folder on this machine where CSVs should be saved (will be created automatically if it doesn't exist)

### 3. Confirm port 587 is open

Make sure the Azure VM's Network Security Group (NSG) allows outbound traffic on port 587. Without this the email step will fail silently.

---

## Test before scheduling

Run snapshot only first to confirm the Pipedrive connection and CSV output are working:
```powershell
.\run_snapshot.bat
```

Check the output folder — two CSVs should appear. Then test the full flow:
```powershell
.\run_month_end.bat
```

Confirm the email lands in Dave's and Grayson's inboxes with both CSVs attached.

---

## Task Scheduler setup

Once manual testing passes, schedule the full automation:

| Setting | Value |
|---|---|
| Task name | `Pipedrive Month-End Report` |
| Trigger | Monthly — last day of every month — 9:00 PM |
| Action | Start a program: `run_month_end.bat` |
| Start in | The folder where these files live |
| Run whether user is logged on or not | ✅ |
| Run with highest privileges | ✅ |
| If task fails, restart every | 10 minutes, up to 3 times |
| Run task as soon as possible after a missed start | ✅ |

After creating the task, right-click → **Run** to verify it executes cleanly end-to-end.

---

## How Dave uses the report

1. Open `Sales_Monthly_YYYY-MM-DD.csv`
2. Copy **row 2** (the data row — row 1 is headers)
3. Open the RightClick Tech Monthly Scorecard
4. Right-click the row for that month
5. Paste Special → **Values** + **Skip Blanks**

The scorecard formulas handle the rest.

---

## Owner

Built and maintained by Grayson Levino — AI Strategy & Enablement, RightClick.  
Questions? grayson.levino@therightclick.com
