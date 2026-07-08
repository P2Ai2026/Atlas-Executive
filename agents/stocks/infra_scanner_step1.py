"""
Distressed-Infrastructure Scanner -- STEP 1: SOURCING
=====================================================
Goal of this step: prove we can pull REAL, current financial numbers for a
watchlist of companies straight from the SEC. No AI yet -- this is the
"does the plumbing work" test, the data-layer version of your hello-world.

Data source: SEC EDGAR public API. Free, no API key, no signup.
Docs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces

Run it with:   python infra_scanner_step1.py
(First do:     pip install requests )
"""

import time
import requests

# --- SETTINGS --------------------------------------------------------------

# The SEC REQUIRES a User-Agent header that says who you are (a name + email).
# If you leave this generic, your requests can get blocked with a "403" error.
# >>> Put YOUR real email between the quotes below. <<<
HEADERS = {"User-Agent": "Internship Project maximilian.dabbous@gmail.com"}

# The companies to scan. Add or remove tickers freely.
#   FRMI = Fermi America  (Texas AI data-center infrastructure -- the example)
#   the rest are public bitcoin-mining / AI-hosting companies
WATCHLIST = ["FRMI", "MARA", "RIOT", "CIFR", "WULF", "CORZ"]

# The financial line-items we care about for spotting trouble.
# (These are "XBRL tags" -- the SEC's standard names for each number.)
WANTED_FACTS = {
    "CashAndCashEquivalentsAtCarryingValue": "Cash",
    "NetIncomeLoss": "Net income (loss)",
    "Liabilities": "Total liabilities",
    "Revenues": "Revenue",
}

# --- HELPERS ---------------------------------------------------------------

def get_cik_map():
    """Download the SEC's master ticker -> CIK table (their internal company ID)."""
    url = "https://www.sec.gov/files/company_tickers.json"
    data = requests.get(url, headers=HEADERS).json()
    # Build a simple dictionary: {"AAPL": "0000320193", ...}
    # The SEC needs the ID padded to 10 digits with leading zeros.
    return {
        row["ticker"].upper(): str(row["cik_str"]).zfill(10)
        for row in data.values()
    }


def get_company_facts(cik):
    """Fetch every financial fact a company has ever filed (one big JSON)."""
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        return None
    return resp.json()


def latest_value(facts, tag):
    """Pull the most recent reported value for one XBRL tag, with its date."""
    try:
        usd_entries = facts["facts"]["us-gaap"][tag]["units"]["USD"]
    except KeyError:
        return None  # this company doesn't report this particular line-item
    # Each entry has an "end" date; sort and take the newest one.
    newest = sorted(usd_entries, key=lambda e: e.get("end", ""))[-1]
    return newest.get("val"), newest.get("end")


# --- MAIN ------------------------------------------------------------------

def main():
    print("Looking up company IDs from the SEC...\n")
    cik_map = get_cik_map()

    for ticker in WATCHLIST:
        cik = cik_map.get(ticker.upper())
        if not cik:
            print(f"{ticker}: not found in the SEC ticker list -- skipping.\n")
            continue

        facts = get_company_facts(cik)
        if facts is None:
            print(f"{ticker}: no financial data available yet -- skipping.\n")
            time.sleep(0.2)
            continue

        print(f"=== {ticker}  ({facts.get('entityName', 'Unknown')}) ===")
        for tag, label in WANTED_FACTS.items():
            result = latest_value(facts, tag)
            if result:
                value, period = result
                print(f"  {label:<20} {value:>18,.0f}   (as of {period})")
            else:
                print(f"  {label:<20} {'not reported':>18}")
        print()

        # Be polite to the SEC's servers (their limit is 10 requests per second).
        time.sleep(0.2)


if __name__ == "__main__":
    main()
