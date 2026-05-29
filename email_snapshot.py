"""
Pipedrive Month-End Report — Email Delivery
Finds the latest Deal_Details CSV and emails it to Dave.
"""

import os
import glob
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from dotenv import load_dotenv

# ── Environment ───────────────────────────────────────────────────────────────
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

SNAPSHOT_DIR  = os.getenv("SNAPSHOT_OUTPUT_DIR", str(Path(__file__).parent / "output"))
SMTP_HOST     = os.getenv("SMTP_HOST", "send.smtp.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM     = os.getenv("SMTP_FROM", "pipedrivereports@therightclick.com")

RECIPIENTS    = ["david.goldshore@therightclick.com"]
CC_RECIPIENTS = ["grayson.levino@therightclick.com"]


# ── File finder ───────────────────────────────────────────────────────────────
def find_latest_file() -> str | None:
    pattern = os.path.join(SNAPSHOT_DIR, "Deal_Details_*.csv")
    files = sorted(glob.glob(pattern), reverse=True)
    return files[0] if files else None


# ── Email builder ─────────────────────────────────────────────────────────────
def build_email(attachment_path: str, report_date: datetime) -> EmailMessage:
    month_label = report_date.strftime("%B %Y")
    filename    = os.path.basename(attachment_path)

    subject = f"Month-End Pipeline Report — {month_label}"

    body = f"""
    <html><body style="font-family: Arial, sans-serif; font-size: 14px; color: #333;">
      <p>Hi Dave,</p>
      <p>
        Attached is the month-end deal details report for <strong>{month_label}</strong>.
        Drop the file into Claude to review the pipeline, make any categorization calls,
        and build out whatever view you need for the scorecard.
      </p>
      <p>Let me know if anything looks off.</p>
      <br>
      <p style="font-size: 12px; color: #888;">
        Generated automatically from Pipedrive on {report_date.strftime("%B %d, %Y")}.
      </p>
    </body></html>
    """

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = SMTP_FROM
    msg["To"]      = ", ".join(RECIPIENTS)
    if CC_RECIPIENTS:
        msg["Cc"]  = ", ".join(CC_RECIPIENTS)
    msg.set_content("Please view this email in an HTML-capable client.")
    msg.add_alternative(body, subtype="html")

    with open(attachment_path, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="text",
            subtype="csv",
            filename=filename,
        )

    return msg


# ── Sender ────────────────────────────────────────────────────────────────────
def send_email(msg: EmailMessage):
    all_recipients = RECIPIENTS + CC_RECIPIENTS
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM, all_recipients, msg.as_bytes())


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    print("=" * 70)
    print("Pipedrive Month-End Report — Email Delivery")
    print("=" * 70)

    attachment = find_latest_file()
    if not attachment:
        print(f"  ✗ No Deal_Details CSV found in {SNAPSHOT_DIR}")
        print("    Run pipeline_snapshot.py first.")
        return

    print(f"  Attachment : {os.path.basename(attachment)}")
    print(f"  To         : {', '.join(RECIPIENTS)}")
    print(f"  Cc         : {', '.join(CC_RECIPIENTS)}")
    print()

    report_date = datetime.now()
    msg = build_email(attachment, report_date)

    print("Sending...")
    try:
        send_email(msg)
        print("  ✓ Email sent successfully")
    except Exception as e:
        print(f"  ✗ Failed to send: {e}")
        raise

    print("=" * 70)


if __name__ == "__main__":
    main()
