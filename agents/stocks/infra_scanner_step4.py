"""
Distressed-Infrastructure Scanner -- STEP 4: REPORT  (+ the human gate)
=======================================================================
This runs the WHOLE pipeline (source -> analyze -> interpret) and bundles
the results into one clean report file, sorted worst-first.

The Human-in-the-Loop rule, straight from your framework:
  This agent WRITES A DRAFT FILE and sends nothing, nowhere. It cannot
  email anyone or touch any database. You read the file, you decide what
  (if anything) leaves the building. The machine prepares; the human approves.

Before running: make sure the Ollama app is OPEN.
Run it with:   python infra_scanner_step4.py
(It runs the full pipeline, so give it a couple of minutes.)
"""

import time
from datetime import datetime

# Reuse everything from the earlier steps.
from infra_scanner_step1 import get_cik_map, get_company_facts, latest_value, WATCHLIST
from infra_scanner_step2 import score_company
from infra_scanner_step3 import collect_numbers, write_interpretation

# The numbers we show in the report (with the date each was reported).
REPORT_FACTS = {
    "CashAndCashEquivalentsAtCarryingValue": "Cash",
    "NetIncomeLoss": "Net income (loss)",
    "Liabilities": "Total liabilities",
    "Revenues": "Revenue",
}

RANK = {"HIGH": 0, "WATCH": 1, "LOW": 2}


def numbers_table(facts):
    """Build a little table of the headline figures, each with its 'as of' date."""
    rows = []
    for tag, label in REPORT_FACTS.items():
        result = latest_value(facts, tag)
        if result:
            value, date = result
            rows.append(f"| {label} | {value:,.0f} | {date} |")
        else:
            rows.append(f"| {label} | not reported | - |")
    return "\n".join(rows)


def build_report():
    cik_map = get_cik_map()
    companies = []

    for ticker in WATCHLIST:
        cik = cik_map.get(ticker.upper())
        if not cik:
            continue
        facts = get_company_facts(cik)
        if facts is None:
            continue

        rating, flags = score_company(facts)
        numbers = collect_numbers(facts)
        name = facts.get("entityName", "Unknown")

        print(f"  analyzing {ticker} ({rating}) -- asking Llama 3...")
        note = write_interpretation(ticker, name, rating, flags, numbers)
        companies.append((ticker, name, rating, flags, facts, note))
        time.sleep(0.2)

    # Sort worst-first.
    companies.sort(key=lambda c: RANK.get(c[2], 3))

    # Assemble the report text.
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    highs = sum(1 for c in companies if c[2] == "HIGH")
    watches = sum(1 for c in companies if c[2] == "WATCH")
    lows = sum(1 for c in companies if c[2] == "LOW")

    out = []
    out.append("# Distressed Infrastructure Scan")
    out.append(f"_Generated {stamp}  -  Source: SEC EDGAR filings  -  Local model: Llama 3_\n")
    out.append(f"**Summary:** {len(companies)} companies scanned -- "
               f"{highs} HIGH, {watches} WATCH, {lows} LOW.\n")
    out.append("**[DRAFT - FOR HUMAN REVIEW]** Figures pulled automatically from SEC "
               "filings; verify before sharing or acting. Nothing here was sent anywhere.\n")
    out.append("---\n")

    for ticker, name, rating, flags, facts, note in companies:
        out.append(f"## {ticker} - {name}  ({rating})\n")
        out.append(f"**Read:** {note}\n")
        out.append("**Distress signals:**")
        if flags:
            out.extend(f"- {f}" for f in flags)
        else:
            out.append("- none")
        out.append("\n**Reported figures:**\n")
        out.append("| Item | Value (USD) | As of |")
        out.append("|---|---|---|")
        out.append(numbers_table(facts))
        out.append("\n---\n")

    return "\n".join(out)


def main():
    print("Building report -- running the full pipeline. Give it a couple of minutes.\n")
    report = build_report()

    filename = f"distress_report_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    with open(filename, "w") as f:
        f.write(report)

    print("\n" + "=" * 60)
    print(f"DONE. Report saved to:  {filename}")
    print("Open it, review it, and only THEN decide what to share.")
    print("The agent sent nothing anywhere -- that's your approval gate.")
    print("=" * 60)


if __name__ == "__main__":
    main()
