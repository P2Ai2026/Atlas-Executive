"""
Distressed-Infrastructure Scanner -- STEP 7: UNIFIED REPORT
===========================================================
The capstone. This runs the WHOLE pipeline for each company --
  financial distress  (Steps 1-3)  +  permit picture  (Steps 5-6)
-- and writes it all into ONE report file, sorted worst-first.

Same human-in-the-loop rule as before: it writes a DRAFT FILE and sends
nothing anywhere. You review; you decide what leaves the building.

Before running: make sure the Ollama app is OPEN.
Run it with:   python infra_scanner_step7.py
(This is the longest one yet -- full financials AND permits for every
company. Give it several minutes.)
"""

import time
from datetime import datetime

from infra_scanner_step1 import get_cik_map, get_company_facts, WATCHLIST
from infra_scanner_step2 import score_company
from infra_scanner_step3 import collect_numbers, write_interpretation
from infra_scanner_step4 import numbers_table, RANK
from infra_scanner_step6 import (
    find_infra_filings, fetch_filing_text, extract_excerpts,
    summarize_permits, INFRA_TERMS,
)


def permit_read(ticker, cik):
    """Run the permit pipeline for one company. Returns (summary, source_label)."""
    matched = find_infra_filings(cik)
    if not matched:
        return "No infrastructure-permit language found in recent filings.", None
    (accession, document), info = max(matched.items(), key=lambda kv: kv[1]["date"])
    text = fetch_filing_text(cik, accession, document)
    if not text:
        return "A permit-related filing was found but could not be read.", None
    excerpts = extract_excerpts(text, INFRA_TERMS)
    if not excerpts:
        return "A permit-related filing was found but had no readable passages.", None
    summary = summarize_permits(ticker, sorted(info["terms"]), excerpts)
    source = f"{info['form']} filed {info['date']} (matched: {', '.join(sorted(info['terms']))})"
    return summary, source


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
        name = facts.get("entityName", "Unknown")
        numbers = collect_numbers(facts)

        print(f"  {ticker} ({rating}) -- financial read...")
        fin_note = write_interpretation(ticker, name, rating, flags, numbers)

        print(f"  {ticker} -- permit read...")
        perm_note, perm_source = permit_read(ticker, cik)

        companies.append({
            "ticker": ticker, "name": name, "rating": rating, "flags": flags,
            "facts": facts, "fin_note": fin_note,
            "perm_note": perm_note, "perm_source": perm_source,
        })
        time.sleep(0.3)

    companies.sort(key=lambda c: RANK.get(c["rating"], 3))

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    highs = sum(1 for c in companies if c["rating"] == "HIGH")
    watches = sum(1 for c in companies if c["rating"] == "WATCH")
    lows = sum(1 for c in companies if c["rating"] == "LOW")

    out = []
    out.append("# Distressed Infrastructure Scan")
    out.append(f"_Generated {stamp}  -  Source: SEC EDGAR filings  -  Local model: Llama 3_\n")
    out.append(f"**Summary:** {len(companies)} companies scanned -- "
               f"{highs} HIGH, {watches} WATCH, {lows} LOW.\n")
    out.append("**[DRAFT - FOR HUMAN REVIEW]** Figures and permit language pulled "
               "automatically from SEC filings; verify before sharing or acting. "
               "Covers public companies only, and reads what companies disclose -- "
               "not official agency permit records. Nothing here was sent anywhere.\n")
    out.append("---\n")

    for c in companies:
        out.append(f"## {c['ticker']} - {c['name']}  ({c['rating']})\n")
        out.append(f"**Financial read:** {c['fin_note']}\n")
        out.append("**Distress signals:**")
        out.extend(f"- {f}" for f in c["flags"]) if c["flags"] else out.append("- none")
        out.append("")
        out.append(f"**Permit read:** {c['perm_note']}")
        if c["perm_source"]:
            out.append(f"\n_Permit source: {c['perm_source']}_")
        out.append("\n**Reported figures:**\n")
        out.append("| Item | Value (USD) | As of |")
        out.append("|---|---|---|")
        out.append(numbers_table(c["facts"]))
        out.append("\n---\n")

    return "\n".join(out)


def main():
    print("Building the unified report -- financials AND permits for every company.")
    print("This is the long one. Give it several minutes.\n")
    report = build_report()

    filename = f"distress_report_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    with open(filename, "w") as f:
        f.write(report)

    print("\n" + "=" * 60)
    print(f"DONE. Report saved to:  {filename}")
    print("Open it with:  open " + filename)
    print("Review it, then decide what to share. Nothing was sent anywhere.")
    print("=" * 60)


if __name__ == "__main__":
    main()
