"""
Pipedrive Month-End Report - CSV Version
Generates two CSV files matching RightClick Tech Monthly Scorecard structure:
  1. Sales_Monthly_YYYY-MM-DD.csv   — summary row Dave copies into the scorecard
  2. Deal_Details_YYYY-MM-DD.csv    — full open deal list for reference
"""

import os
import csv
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import httpx

# ── Environment ──────────────────────────────────────────────────────────────
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

# Label map is populated at runtime from the Pipedrive API
LABEL_MAP: dict = {}


# ── API helpers ───────────────────────────────────────────────────────────────
def api_get(endpoint: str, params: dict = {}) -> dict:
    """Make a GET request to the Pipedrive API."""
    params["api_token"] = PIPEDRIVE_API_TOKEN
    try:
        response = httpx.get(f"{BASE_URL}{endpoint}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"  API Error [{endpoint}]: {e}")
        return {"error": str(e)}


def load_label_mapping():
    """Populate LABEL_MAP from Pipedrive deal fields."""
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
    """Convert raw label value (int, str, or comma-separated IDs) to human-readable string."""
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
def get_all_deals(status: str = "open") -> list:
    """Fetch all deals for a given status, handling Pipedrive pagination."""
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


# ── Categorisation ────────────────────────────────────────────────────────────
def categorize_deal(deal) -> str:
    """Return 'MSP', 'ProServe', or 'Other' based on deal label."""
    label = format_label(deal.get("label"))
    if "MSP" in label:
        return "MSP"
    if "ProServe" in label or "AI" in label:
        return "ProServe"
    return "Other"


# ── Summary generation ────────────────────────────────────────────────────────
def _empty_bucket() -> dict:
    return {
        "new_deals": 0,
        "qualified_deals": 0, "qualified_value": 0,
        "demo_deals": 0,      "demo_value": 0,
        "proposal_deals": 0,  "proposal_value": 0,
        "negotiation_deals": 0, "negotiation_value": 0,
        "deals_won": 0,       "revenue_won": 0,
        "deals_lost": 0,      "revenue_lost": 0,
    }


def generate_summary_data(report_date: datetime):
    """Pull deals from Pipedrive and produce the summary dict + open deal list."""
    print("Fetching open deals...")
    open_deals = get_all_deals("open")
    print("Fetching won deals...")
    won_deals = get_all_deals("won")
    print("Fetching lost deals...")
    lost_deals = get_all_deals("lost")

    summary = {"MSP": _empty_bucket(), "ProServe": _empty_bucket()}
    cy, cm = report_date.year, report_date.month

    # Open deals — pipeline snapshot + new-deal count
    for deal in open_deals:
        cat = categorize_deal(deal)
        if cat not in summary:
            continue
        value = deal.get("value", 0) or 0
        stage = deal.get("stage_id")

        # New deals created this calendar month
        add_time_str = deal.get("add_time", "")
        if add_time_str:
            try:
                add_dt = datetime.strptime(add_time_str, "%Y-%m-%d %H:%M:%S")
                if add_dt.year == cy and add_dt.month == cm:
                    summary[cat]["new_deals"] += 1
            except (ValueError, TypeError):
                pass

        if stage == 1:
            summary[cat]["qualified_deals"] += 1
            summary[cat]["qualified_value"] += value
        elif stage == 3:
            summary[cat]["demo_deals"] += 1
            summary[cat]["demo_value"] += value
        elif stage == 4:
            summary[cat]["proposal_deals"] += 1
            summary[cat]["proposal_value"] += value
        elif stage == 5:
            summary[cat]["negotiation_deals"] += 1
            summary[cat]["negotiation_value"] += value

    # Won deals — filter to current month
    for deal in won_deals:
        cat = categorize_deal(deal)
        if cat not in summary:
            continue
        won_time_str = deal.get("won_time", "")
        if won_time_str:
            try:
                won_dt = datetime.strptime(won_time_str[:19], "%Y-%m-%d %H:%M:%S")
                if won_dt.year == cy and won_dt.month == cm:
                    summary[cat]["deals_won"] += 1
                    summary[cat]["revenue_won"] += deal.get("value", 0) or 0
            except (ValueError, TypeError):
                pass

    # Lost deals — filter to current month
    for deal in lost_deals:
        cat = categorize_deal(deal)
        if cat not in summary:
            continue
        lost_time_str = deal.get("lost_time", "")
        if lost_time_str:
            try:
                lost_dt = datetime.strptime(lost_time_str[:19], "%Y-%m-%d %H:%M:%S")
                if lost_dt.year == cy and lost_dt.month == cm:
                    summary[cat]["deals_lost"] += 1
                    summary[cat]["revenue_lost"] += deal.get("value", 0) or 0
            except (ValueError, TypeError):
                pass

    return summary, open_deals


# ── CSV writers ───────────────────────────────────────────────────────────────
def write_summary_csv(summary: dict, report_date: datetime, output_dir: str) -> str:
    """
    Write Sales_Monthly_YYYY-MM-DD.csv.
    One data row — column order matches Dave's master scorecard (Sheet 1).
    Formula-only columns (N/O/P/S/V/W/X and ProServe equivalents) are left blank.
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = report_date.strftime("%Y-%m-%d")
    filepath = os.path.join(output_dir, f"Sales_Monthly_{timestamp}.csv")

    msp = summary["MSP"]
    ps  = summary["ProServe"]

    headers = [
        # Col A
        "Month",
        # MSP — cols E-U (formula cols left blank)
        "MSP New Deals Created",
        "MSP Qualified Deals", "MSP Qualified Value ($)",
        "MSP Demo Deals",      "MSP Demo Value ($)",
        "MSP Proposal Deals",  "MSP Proposal Value ($)",
        "MSP Negotiation Deals","MSP Negotiation Value ($)",
        "",                     # N — formula
        "",                     # O — formula
        "",                     # P — formula
        "MSP Won Deals",       "MSP Won Revenue ($)",
        "",                     # S — formula
        "MSP Lost Deals",      "MSP Lost Revenue ($)",
        "",                     # V — formula
        "",                     # W — formula
        "",                     # X — formula
        # ProServe — cols Y-AP
        "PS New Deals Created",
        "PS Qualified Deals",  "PS Qualified Value ($)",
        "PS Demo Deals",       "PS Demo Value ($)",
        "PS Proposal Deals",   "PS Proposal Value ($)",
        "PS Negotiation Deals","PS Negotiation Value ($)",
        "",                     # AH — formula
        "",                     # AI — formula
        "",                     # AJ — formula
        "PS Won Deals",        "PS Won Revenue ($)",
        "",                     # AM — formula
        "PS Lost Deals",       "PS Lost Revenue ($)",
        "",                     # AP — formula
    ]

    row = [
        report_date.strftime("%Y-%m-%d"),
        msp["new_deals"],
        msp["qualified_deals"],   msp["qualified_value"],
        msp["demo_deals"],         msp["demo_value"],
        msp["proposal_deals"],     msp["proposal_value"],
        msp["negotiation_deals"],  msp["negotiation_value"],
        "", "", "",
        msp["deals_won"],          msp["revenue_won"],
        "",
        msp["deals_lost"],         msp["revenue_lost"],
        "", "", "",
        ps["new_deals"],
        ps["qualified_deals"],     ps["qualified_value"],
        ps["demo_deals"],          ps["demo_value"],
        ps["proposal_deals"],      ps["proposal_value"],
        ps["negotiation_deals"],   ps["negotiation_value"],
        "", "", "",
        ps["deals_won"],           ps["revenue_won"],
        "",
        ps["deals_lost"],          ps["revenue_lost"],
        "",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerow(row)

    return filepath


def write_details_csv(open_deals: list, report_date: datetime, output_dir: str) -> str:
    """Write Deal_Details_YYYY-MM-DD.csv with one row per open deal."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = report_date.strftime("%Y-%m-%d")
    filepath = os.path.join(output_dir, f"Deal_Details_{timestamp}.csv")

    headers = [
        "Deal ID", "Title", "Organization", "Owner",
        "Stage", "Label", "Category",
        "Value", "Currency",
        "Expected Close Date", "Add Time", "Update Time",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for deal in open_deals:
            stage_id = deal.get("stage_id")
            label_decoded = format_label(deal.get("label"))
            writer.writerow([
                deal.get("id"),
                deal.get("title"),
                deal.get("org_name", ""),
                deal.get("owner_name", ""),
                STAGE_NAMES.get(stage_id, f"Stage {stage_id}"),
                label_decoded,
                categorize_deal(deal),
                deal.get("value", 0),
                deal.get("currency", "USD"),
                deal.get("expected_close_date", ""),
                deal.get("add_time", ""),
                deal.get("update_time", ""),
            ])

    return filepath


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    print("=" * 70)
    print("Pipedrive Month-End Report — CSV")
    print("=" * 70)
    report_date = datetime.now()
    print(f"Report Date : {report_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Output Dir  : {OUTPUT_DIR}")
    print()

    print("Loading label mapping from Pipedrive...")
    load_label_mapping()
    print()

    print("Pulling deal data...")
    summary, open_deals = generate_summary_data(report_date)
    print(f"  Open deals fetched: {len(open_deals)}")
    print()

    print("Writing CSVs...")
    summary_file = write_summary_csv(summary, report_date, OUTPUT_DIR)
    details_file = write_details_csv(open_deals, report_date, OUTPUT_DIR)
    print(f"  ✓ Summary : {os.path.basename(summary_file)}")
    print(f"  ✓ Details : {os.path.basename(details_file)}")
    print()

    # Console summary
    print("=" * 70)
    print("MANAGED SERVICES")
    msp = summary["MSP"]
    print(f"  New Deals  : {msp['new_deals']}")
    print(f"  Pipeline   : Qualified {msp['qualified_deals']} (${msp['qualified_value']:,.0f})"
          f"  Demo {msp['demo_deals']} (${msp['demo_value']:,.0f})"
          f"  Proposal {msp['proposal_deals']} (${msp['proposal_value']:,.0f})"
          f"  Negotiations {msp['negotiation_deals']} (${msp['negotiation_value']:,.0f})")
    print(f"  Won        : {msp['deals_won']} deals  ${msp['revenue_won']:,.0f}")
    print(f"  Lost       : {msp['deals_lost']} deals  ${msp['revenue_lost']:,.0f}")

    print("\nPROFESSIONAL SERVICES")
    ps = summary["ProServe"]
    print(f"  New Deals  : {ps['new_deals']}")
    print(f"  Pipeline   : Qualified {ps['qualified_deals']} (${ps['qualified_value']:,.0f})"
          f"  Demo {ps['demo_deals']} (${ps['demo_value']:,.0f})"
          f"  Proposal {ps['proposal_deals']} (${ps['proposal_value']:,.0f})"
          f"  Negotiations {ps['negotiation_deals']} (${ps['negotiation_value']:,.0f})")
    print(f"  Won        : {ps['deals_won']} deals  ${ps['revenue_won']:,.0f}")
    print(f"  Lost       : {ps['deals_lost']} deals  ${ps['revenue_lost']:,.0f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
