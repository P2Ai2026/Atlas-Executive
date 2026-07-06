"""
Distressed-Infrastructure Scanner -- STEP 6: PERMIT SUMMARY  (v2: targeted terms)
=================================================================================
WHAT CHANGED FROM v1:
v1 searched for the bare word "permit" -- which is everywhere in filings for
the WRONG reasons ("early adoption was permitted", "Permitted Acquisitions" in
loan agreements, etc.). That noise produced junk summaries. Garbage in, garbage
out. v2 instead hunts the specific phrases an infrastructure investor cares
about, so we only catch REAL permitting language:

    air permit, interconnection, environmental permit, construction permit, TCEQ

For each company we search those phrases, fetch the most recent filing that
matched, pull the passages around those exact terms, and have Llama 3 summarize
-- grounded only in the real text. If a company has no such language, we say so
plainly (which is itself a useful answer).

Before running: make sure the Ollama app is OPEN.
Run it with:   python infra_scanner_step6.py
"""

import re
import html
import time
import requests

from infra_scanner_step1 import get_cik_map, HEADERS, WATCHLIST
from infra_scanner_step3 import llm
from infra_scanner_step5 import search_filings

# The infrastructure-permit language we actually care about.
INFRA_TERMS = ["air permit", "interconnection", "environmental permit",
               "construction permit", "TCEQ"]


def find_infra_filings(cik):
    """Search each infra-permit phrase; collect this company's matching filings."""
    matched = {}
    for term in INFRA_TERMS:
        data, status = search_filings(cik, f'"{term}"')
        if not data:
            continue
        for h in data.get("hits", {}).get("hits", []):
            src = h.get("_source", {})
            if cik not in src.get("ciks", []):
                continue
            parts = h.get("_id", "").split(":")
            accession = parts[0]
            document = parts[1] if len(parts) > 1 else None
            form = src.get("root_forms", src.get("file_type", "?"))
            if isinstance(form, list):
                form = ",".join(form)
            entry = matched.setdefault(
                (accession, document),
                {"date": src.get("file_date", ""), "form": form, "terms": set()},
            )
            entry["terms"].add(term)
        time.sleep(0.2)
    return matched


def clean_html(raw):
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def fetch_filing_text(cik, accession, document):
    if not document:
        return None
    url = (f"https://www.sec.gov/Archives/edgar/data/"
           f"{int(cik)}/{accession.replace('-', '')}/{document}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        return clean_html(resp.text) if resp.status_code == 200 else None
    except Exception:
        return None


def extract_excerpts(text, terms, window=300, max_snippets=6):
    """Pull passages around each infra term that actually appears in the text."""
    lower = text.lower()
    found = []
    for term in terms:
        t, start = term.lower(), 0
        while True:
            idx = lower.find(t, start)
            if idx == -1:
                break
            a, b = max(0, idx - window), min(len(text), idx + len(t) + window)
            found.append((idx, text[a:b].strip()))
            start = b
    found.sort()
    return [s for _, s in found][:max_snippets]


def summarize_permits(ticker, terms_found, excerpts):
    blob = "\n---\n".join(excerpts)[:3500]
    prompt = f"""You are a research assistant for an infrastructure investor. Below are excerpts from {ticker}'s most recent SEC filing that mentions infrastructure-permit language ({', '.join(terms_found)}). Using ONLY these excerpts, summarize in 3-4 sentences what infrastructure permits or grid/environmental approvals this company holds, has applied for, or still needs. Be specific where the text is specific. If the language is vague or generic, say so plainly. Do NOT invent anything not in the text.

Excerpts:
{blob}

Permit summary:"""
    return llm.invoke(prompt).content.strip()


def main():
    cik_map = get_cik_map()

    for ticker in WATCHLIST:
        cik = cik_map.get(ticker.upper())
        if not cik:
            print(f"{ticker}: not found -- skipping.\n")
            continue

        print(f"=== {ticker} ===")
        matched = find_infra_filings(cik)
        if not matched:
            print("   No infrastructure-permit language found in recent filings.\n")
            continue

        # Most recent matching filing.
        (accession, document), info = max(matched.items(), key=lambda kv: kv[1]["date"])
        print(f"   Reading {info['form']} filed {info['date']}  "
              f"(matched: {', '.join(sorted(info['terms']))})...")

        text = fetch_filing_text(cik, accession, document)
        if not text:
            print("   Could not read the filing document.\n")
            continue

        excerpts = extract_excerpts(text, INFRA_TERMS)
        if not excerpts:
            print("   Matched in search but no readable passages in this document.\n")
            continue

        print("   (asking Llama 3 to summarize -- a few seconds...)\n")
        summary = summarize_permits(ticker, sorted(info["terms"]), excerpts)
        print("   " + summary.replace("\n", "\n   "))
        print()


if __name__ == "__main__":
    main()
