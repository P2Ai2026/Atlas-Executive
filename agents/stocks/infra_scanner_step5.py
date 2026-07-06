"""
Distressed-Infrastructure Scanner -- STEP 5: PERMIT SEARCH  (v2: with retries)
==============================================================================
New data source: the SEC's FULL-TEXT search (efts.sec.gov). The API we used
before returns NUMBERS; this one searches the actual WORDS inside filings, so
we can find where a company discusses permits.

WHAT CHANGED FROM v1:
The SEC's full-text server sometimes bounces a request when calls come in
quick succession (it briefly says "slow down"). v1 gave up on the first
bounce -- that's why some companies showed "search failed." Now the script
WAITS A MOMENT AND RETRIES (up to 3 times), which clears it almost every time.
If something still fails, it now prints the real error code so we can see why.

Run it with:   python infra_scanner_step5.py
(Reuses your email + watchlist from Step 1.)
"""

import time
from datetime import datetime, timedelta
import requests

from infra_scanner_step1 import get_cik_map, HEADERS, WATCHLIST

SEARCH_TERM = '"permit"'        # broad on purpose for now; we target specifics next
FORMS = "10-K,10-Q,8-K"         # the filings where permit talk usually lives
LOOKBACK_DAYS = 730             # roughly the last two years

# Same identifying header as before, plus a hint that we want JSON back.
SEARCH_HEADERS = {**HEADERS, "Accept": "application/json"}


def search_filings(cik, term, attempts=3):
    """Ask the SEC full-text search for this company's filings mentioning `term`.
    Retries with a short back-off if the server bounces us.
    Returns (data, status) -- data is None if every attempt failed."""
    url = "https://efts.sec.gov/LATEST/search-index"
    params = {
        "q": term,
        "ciks": cik,                                   # restrict to this company
        "forms": FORMS,
        "startdt": (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d"),
        "enddt": datetime.now().strftime("%Y-%m-%d"),
    }

    last_status = None
    for i in range(attempts):
        try:
            resp = requests.get(url, headers=SEARCH_HEADERS, params=params, timeout=20)
            last_status = resp.status_code
            if resp.status_code == 200:
                return resp.json(), 200
        except Exception as e:
            last_status = f"error: {e}"
        time.sleep(1.5 * (i + 1))   # wait longer each retry: 1.5s, 3s, 4.5s

    return None, last_status


def filing_link(cik, accession):
    """Build a clickable URL to the filing so you can verify the permit text yourself."""
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"


def main():
    cik_map = get_cik_map()

    for ticker in WATCHLIST:
        cik = cik_map.get(ticker.upper())
        if not cik:
            print(f"{ticker}: not found -- skipping.\n")
            continue

        data, status = search_filings(cik, SEARCH_TERM)
        if not data:
            print(f"{ticker}: search failed (HTTP {status}) -- skipping.\n")
            time.sleep(0.5)
            continue

        hits = data.get("hits", {}).get("hits", [])
        total = data.get("hits", {}).get("total", {}).get("value", 0)
        print(f"=== {ticker} ===  {total} filing(s) mention {SEARCH_TERM} (last ~2 yrs)")

        seen = set()
        shown = 0
        for h in hits:
            src = h.get("_source", {})
            if cik not in src.get("ciks", []):       # safety: this company only
                continue
            accession = h.get("_id", "").split(":")[0]
            if accession in seen:                    # skip duplicate filings
                continue
            seen.add(accession)

            form = src.get("root_forms", src.get("file_type", "?"))
            if isinstance(form, list):
                form = ",".join(form)
            date = src.get("file_date", "?")
            print(f"   - {form:6} filed {date}")
            print(f"     {filing_link(cik, accession)}")

            shown += 1
            if shown >= 5:
                break

        if shown == 0:
            print("   - (no permit mentions found for this company in the window)")
        print()

        time.sleep(0.5)   # polite gap between companies


if __name__ == "__main__":
    main()
