"""
Pipedrive Month-End Report
Generates a single CSV with all deals for Dave to review in Claude.
Structure:
  Section 1 — Open deals (all)
  Section 2 — Won deals this month
  Section 3 — Lost deals this month
"""

import os
import csv
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import httpx

# ── Environment ───────────────────────────────────────────────────────────────
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

PIPEDRIVE_API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")
BASE_URL = "https://rightclick.pipedrive.com/v1"
OUTPUT_DIR = os.getenv("SNAPSHOT_OUTPUT_DIR", str(Path(__file__).parent / "output"))

# ── Stage mappings ────────────────────────────────────────────────────────────
STAGE_NAMES = {
    1: "Qualified",
    3: "Demo",
    4: "Proposal",
    5: "Negotiations",
}

LABEL_MAP: dict = {}

DEAL_COLUMNS = [
    "Deal ID", "Title", "Organization", "Owner",
    "Stage", "Label", "Value", "Currency",
    "Expected Close Date", "Add Time", "Update Time",
]


# ── API helpers ───────────────────────────────────────────────────────────────
def api_get(endpoint: str, params: dict = {}) -> dict:
    params["api_token"] = PIPEDRIVE_API_TOKEN
    try:
        response = httpx.get(f"{BASE_URL}{endpoint}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"  API Error [{endpoint}]: {e}")
        return {"error": str(e)}


def load_label_mapping():
    global LABEL_MAP
    data = api_get("/dealFields")
    if "error" in data:
        print(f"  Warning: could not load label mapping — {data['error']}")
        return
    for field in data.get("data", []):
        if field.get("key") == "label":
            for opt in field.get("options", []):
                LABEL_MAP[opt["id"]] = opt["label"]
            break
    print(f"  Loaded {len(LABEL_MAP)} label options")


def format_label(label_value) -> str:
    if not label_value:
        return ""
    if isinstance(label_value, str) and "," in label_value:
        parts = []
        for part in label_value.split(","):
            try:
                parts.append(LABEL_MAP.get(int(part.strip()), f"Unknown({part.strip()})"))
            except ValueError:
                parts.append(part.strip())
        return " + ".join(parts)
    try:
        lid = int(label_value) if isinstance(label_value, str) else label_value
        return LABEL_MAP.get(lid, f"Unknown({label_value})")
    except (ValueError, TypeError):
        return str(label_value)


# ── Deal fetching ─────────────────────────────────────────────────────────────
def get_all_deals(status: str) -> list:
    all_deals = []
    start = 0
    limit = 500
    while True:
        data = api_get("/deals", {"status": status, "start": start, "limit": limit})
        if "error" in data:
            print(f"  Error fetching {status} deals: {data['error']}")
            break
        deals = data.get("data") or []
        if not deals:
            break
        all_deals.extend(deals)
        pagination = data.get("additional_data", {}).get("pagination", {})
        if not pagination.get("more_items_in_collection"):
            break
        start = pagination.get("next_start", start + limit)
    return all_deals


# ── Row builder ───────────────────────────────────────────────────────────────
def deal_row(deal: dict) -> list:
    stage_id = deal.get("stage_id")
    return [
        deal.get("id"),
        deal.get("title"),
        deal.get("org_name", ""),
        deal.get("owner_name", ""),
        STAGE_NAMES.get(stage_id, f"Stage {stage_id}") if stage_id else "",
        format_label(deal.get("label")),
        deal.get("value", 0),
        deal.get("currency", "USD"),
        deal.get("expected_close_date", ""),
        deal.get("add_time", ""),
        deal.get("update_time", ""),
    ]


def filter_by_month(deals: list, time_field: str, year: int, month: int) -> list:
    result = []
    for deal in deals:
        ts = deal.get(time_field, "")
        if not ts:
            continue
        try:
            dt = datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")
            if dt.year == year and dt.month == month:
                result.append(deal)
        except (ValueError, TypeError):
            pass
    return result


# ── CSV writer ────────────────────────────────────────────────────────────────
def write_details_csv(
    open_deals: list,
    won_deals: list,
    lost_deals: list,
    report_date: datetime,
    output_dir: str,
) -> str:
    os.makedirs(output_dir, exist_ok=True)
    timestamp = report_date.strftime("%Y-%m-%d")
    filepath = os.path.join(output_dir, f"Deal_Details_{timestamp}.csv")
    month_label = report_date.strftime("%B %Y")

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # ── Section 1: Open deals ─────────────────────────────────────────────
        writer.writerow([f"--- OPEN DEALS ---"] + [""] * (len(DEAL_COLUMNS) - 1))
        writer.writerow(DEAL_COLUMNS)
        for deal in open_deals:
            writer.writerow(deal_row(deal))

        # ── Section 2: Won this month ─────────────────────────────────────────
        writer.writerow([])
        writer.writerow([f"--- WON IN {month_label.upper()} ---"] + [""] * (len(DEAL_COLUMNS) - 1))
        writer.writerow(DEAL_COLUMNS)
        for deal in won_deals:
            writer.writerow(deal_row(deal))

        # ── Section 3: Lost this month ────────────────────────────────────────
        writer.writerow([])
        writer.writerow([f"--- LOST IN {month_label.upper()} ---"] + [""] * (len(DEAL_COLUMNS) - 1))
        writer.writerow(DEAL_COLUMNS)
        for deal in lost_deals:
            writer.writerow(deal_row(deal))

    return filepath


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    print("=" * 70)
    print("Pipedrive Month-End Report — Deal Details")
    print("=" * 70)
    report_date = datetime.now()
    cy, cm = report_date.year, report_date.month
    print(f"Report Date : {report_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Output Dir  : {OUTPUT_DIR}")
    print()

    print("Loading label mapping from Pipedrive...")
    load_label_mapping()
    print()

    print("Fetching deals...")
    open_deals = get_all_deals("open")
    all_won    = get_all_deals("won")
    all_lost   = get_all_deals("lost")

    won_this_month  = filter_by_month(all_won,  "won_time",  cy, cm)
    lost_this_month = filter_by_month(all_lost, "lost_time", cy, cm)

    print(f"  Open          : {len(open_deals)}")
    print(f"  Won this month: {len(won_this_month)}")
    print(f"  Lost this month: {len(lost_this_month)}")
    print()

    print("Writing CSV...")
    details_file = write_details_csv(
        open_deals, won_this_month, lost_this_month, report_date, OUTPUT_DIR
    )
    print(f"  ✓ {os.path.basename(details_file)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
