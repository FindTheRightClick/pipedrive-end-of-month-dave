"""
Email Pipeline Snapshot — Month-End Report
Sends the two latest CSV reports via SMTP (smtp.com relay).
Attaches: Sales_Monthly_YYYY-MM-DD.csv + Deal_Details_YYYY-MM-DD.csv
"""

import os
import glob
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from dotenv import load_dotenv

# ── Environment ──────────────────────────────────────────────────────────────
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# SMTP config — pulled from .env so creds stay out of source code
SMTP_HOST     = os.getenv("SMTP_HOST",     "send.smtp.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER",     "scan_rightclick")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM     = os.getenv("SMTP_FROM",     "pipeline@therightclick.com")

# Output directory (same .env var pipeline_snapshot.py uses)
RIGHTCLICK_PATH = os.path.join(
    "C:\\Users\\GraysonLevino\\RightClick",
    "Professional Services - Documents",
    "Pipedrive Updates",
    "Month End Deal Status"
)
SNAPSHOT_DIR = os.getenv("SNAPSHOT_OUTPUT_DIR", RIGHTCLICK_PATH)

# Recipients
RECIPIENTS    = ["david.goldshore@therightclick.com"]
CC_RECIPIENTS = ["grayson.levino@therightclick.com"]


# ── File helpers ──────────────────────────────────────────────────────────────
def get_latest_pair():
    """
    Find the most recent Sales_Monthly and Deal_Details CSV files.
    Returns (summary_path, details_path) — either may be None if not found.
    """
    summary_files = glob.glob(os.path.join(SNAPSHOT_DIR, "Sales_Monthly_*.csv"))
    details_files = glob.glob(os.path.join(SNAPSHOT_DIR, "Deal_Details_*.csv"))

    summary = max(summary_files, key=os.path.getctime) if summary_files else None
    details = max(details_files, key=os.path.getctime) if details_files else None
    return summary, details


def attach_csv(msg: EmailMessage, filepath: str):
    """Attach a CSV file to an EmailMessage."""
    with open(filepath, "rb") as f:
        data = f.read()
    msg.add_attachment(
        data,
        maintype="text",
        subtype="csv",
        filename=os.path.basename(filepath),
    )


# ── Email builder ─────────────────────────────────────────────────────────────
def build_email(summary_file: str | None, details_file: str | None) -> EmailMessage:
    """Construct the EmailMessage with formatted body and CSV attachments."""

    # Derive month label from filename (falls back to today)
    date_source = summary_file or details_file
    if date_source:
        stem = Path(date_source).stem           # e.g. "Sales_Monthly_2026-04-30"
        date_str = stem.rsplit("_", 1)[-1]      # "2026-04-30"
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            date_obj = datetime.now()
    else:
        date_obj = datetime.now()

    month_name     = date_obj.strftime("%B %Y")         # "April 2026"
    formatted_date = date_obj.strftime("%B %d, %Y")     # "April 30, 2026"

    msg = EmailMessage()
    msg["Subject"] = f"Month-End Pipeline Report — {month_name}"
    msg["From"]    = SMTP_FROM
    msg["To"]      = ", ".join(RECIPIENTS)
    if CC_RECIPIENTS:
        msg["Cc"]  = ", ".join(CC_RECIPIENTS)

    # Plain-text fallback
    msg.set_content(
        f"Hi Dave,\n\n"
        f"Attached is the month-end pipeline report for {month_name}.\n\n"
        f"FILES ATTACHED:\n"
        f"  • Sales_Monthly — summary row to copy into the RightClick Tech Monthly Scorecard\n"
        f"  • Deal_Details  — full open deal list for reference\n\n"
        f"HOW TO USE Sales_Monthly:\n"
        f"  1. Open the CSV\n"
        f"  2. Copy row 2 (the data row)\n"
        f"  3. Open the RightClick Tech Monthly Scorecard\n"
        f"  4. Right-click the {month_name} row\n"
        f"  5. Paste Special → Values + Skip Blanks\n\n"
        f"Generated automatically from Pipedrive on {formatted_date}.\n\n"
        f"— Pipeline Snapshot Automation"
    )

    # HTML version
    attachments_note = ""
    if not summary_file:
        attachments_note += "<p style='color:red'>⚠️ Sales_Monthly CSV not found.</p>"
    if not details_file:
        attachments_note += "<p style='color:red'>⚠️ Deal_Details CSV not found.</p>"

    msg.add_alternative(f"""
    <html>
    <body style="font-family: Calibri, Arial, sans-serif; font-size: 11pt; color: #111;">

        <p>Hi Dave,</p>

        <p>Attached is the month-end pipeline report for <strong>{month_name}</strong>.</p>

        {attachments_note}

        <table style="border-collapse:collapse; margin-bottom:12px;">
            <tr>
                <th style="background:#0068E6; color:#fff; padding:6px 12px; text-align:left;">File</th>
                <th style="background:#0068E6; color:#fff; padding:6px 12px; text-align:left;">Purpose</th>
            </tr>
            <tr style="background:#f0f4ff;">
                <td style="padding:6px 12px; border:1px solid #ddd;">Sales_Monthly_{date_obj.strftime('%Y-%m-%d')}.csv</td>
                <td style="padding:6px 12px; border:1px solid #ddd;">Summary row → copy into master scorecard</td>
            </tr>
            <tr>
                <td style="padding:6px 12px; border:1px solid #ddd;">Deal_Details_{date_obj.strftime('%Y-%m-%d')}.csv</td>
                <td style="padding:6px 12px; border:1px solid #ddd;">Full open deal list for reference</td>
            </tr>
        </table>

        <p><strong>How to update the scorecard:</strong></p>
        <ol>
            <li>Open <em>Sales_Monthly_{date_obj.strftime('%Y-%m-%d')}.csv</em></li>
            <li>Copy <strong>row 2</strong> (the data row — row 1 is headers)</li>
            <li>Open the RightClick Tech Monthly Scorecard</li>
            <li>Right-click the <strong>{month_name}</strong> row</li>
            <li>Select <strong>Paste Special</strong> → check <strong>Values</strong> and <strong>Skip blanks</strong></li>
        </ol>

        <p style="font-size:10pt; color:#555;">
            Generated automatically from Pipedrive on {formatted_date}.
        </p>

        <p>Best regards,<br><em>Pipeline Snapshot Automation</em></p>
    </body>
    </html>
    """, subtype="html")

    # Attach whichever files exist
    if summary_file:
        attach_csv(msg, summary_file)
    if details_file:
        attach_csv(msg, details_file)

    return msg


# ── SMTP sender ───────────────────────────────────────────────────────────────
def send_email(msg: EmailMessage):
    """Send via SMTP with STARTTLS."""
    all_recipients = RECIPIENTS + CC_RECIPIENTS
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM, all_recipients, msg.as_bytes())


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("Month-End Pipeline Report — Email")
    print("=" * 60)
    print(f"Timestamp : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Directory : {SNAPSHOT_DIR}")
    print()

    summary_file, details_file = get_latest_pair()

    if summary_file:
        print(f"  Found summary : {os.path.basename(summary_file)}")
    else:
        print("  WARNING: No Sales_Monthly CSV found — email will note missing file")

    if details_file:
        print(f"  Found details : {os.path.basename(details_file)}")
    else:
        print("  WARNING: No Deal_Details CSV found — email will note missing file")

    if not summary_file and not details_file:
        print()
        print("ERROR: No report files found at all. Run pipeline_snapshot.py first.")
        return

    print()
    print("Building email...")
    msg = build_email(summary_file, details_file)

    print(f"Sending via {SMTP_HOST}:{SMTP_PORT}...")
    try:
        send_email(msg)
        print()
        print("=" * 60)
        print(f"✓ Email sent to   : {', '.join(RECIPIENTS)}")
        if CC_RECIPIENTS:
            print(f"  CC              : {', '.join(CC_RECIPIENTS)}")
        print("=" * 60)
    except Exception as e:
        print(f"\nERROR sending email: {e}")
        print()
        print("Troubleshooting:")
        print("  1. Check SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD in .env")
        print("  2. Confirm port 587 is open outbound on the Azure VM (NSG rules)")
        print("  3. Verify smtp.com account is active and sending is enabled")


if __name__ == "__main__":
    main()
