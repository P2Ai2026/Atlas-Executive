"""
Distressed-Infrastructure Scanner -- STEP 2: ANALYZE
====================================================
Step 1 proved we can PULL the numbers. This step TURNS those numbers into
plain-English distress signals -- still NO AI. We do the judgement in code
(the framework's rule: "routing via code, not LLM discretion"), so every
rating is consistent and you can always see WHY a company was flagged.
The AI arrives in Step 3, only to write the findings up in plain English.

Run it with:   python infra_scanner_step2.py
(It reuses the code you already tested in Step 1 -- that's the import line below.)
"""

import time

# Reuse the fetching machinery we already built and tested in Step 1.
# (This just borrows those functions instead of copy-pasting them.)
from infra_scanner_step1 import get_cik_map, get_company_facts, latest_value, WATCHLIST


def value_only(facts, tag):
    """Like latest_value, but returns just the number (or None)."""
    result = latest_value(facts, tag)
    return result[0] if result else None


def score_company(facts):
    """Inspect the numbers and return (rating, list-of-reasons)."""
    cash        = value_only(facts, "CashAndCashEquivalentsAtCarryingValue")
    net_income  = value_only(facts, "NetIncomeLoss")
    liabilities = value_only(facts, "Liabilities")
    revenue     = value_only(facts, "Revenues")

    flags = []

    # 1. No revenue reported -- pre-revenue or not selling anything yet.
    if not revenue:
        flags.append("No revenue reported (pre-revenue, or files it under another name)")

    # 2. Losing money.
    if net_income is not None and net_income < 0:
        flags.append("Unprofitable (reporting a net loss)")

    # 3. Losing MORE than it earns.
    if net_income is not None and revenue and abs(net_income) > revenue:
        flags.append("Losses are larger than total revenue")

    # 4. Debt is large compared to the cash on hand.
    if liabilities is not None and cash and liabilities > 3 * cash:
        flags.append("Heavy debt load (liabilities more than 3x cash)")

    # 5. Rough cash runway: is cash smaller than its most recent loss?
    if cash is not None and net_income is not None and net_income < 0:
        if cash < abs(net_income):
            flags.append("Thin cash cushion (cash is less than its recent loss)")

    # Rating: the more red flags, the more concern. (Tune these thresholds freely.)
    if len(flags) >= 3:
        rating = "HIGH"
    elif len(flags) >= 1:
        rating = "WATCH"
    else:
        rating = "LOW"

    return rating, flags


def main():
    print("Looking up company IDs from the SEC...\n")
    cik_map = get_cik_map()

    for ticker in WATCHLIST:
        cik = cik_map.get(ticker.upper())
        if not cik:
            print(f"{ticker}: not found -- skipping.\n")
            continue
        facts = get_company_facts(cik)
        if facts is None:
            print(f"{ticker}: no data -- skipping.\n")
            time.sleep(0.2)
            continue

        rating, flags = score_company(facts)
        name = facts.get("entityName", "Unknown")
        print(f"=== {ticker}  ({name})  -->  DISTRESS: {rating} ===")
        if flags:
            for reason in flags:
                print(f"   - {reason}")
        else:
            print("   - No distress signals in the numbers we checked.")
        print()

        time.sleep(0.2)  # stay polite to the SEC's servers


if __name__ == "__main__":
    main()
