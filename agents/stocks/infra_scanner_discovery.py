"""
Distressed-Infrastructure Scanner -- DISCOVERY (two-stream autonomous sourcing)
===============================================================================
The agent finds its own targets through TWO independent nets:

  STREAM A -- FAILING TECH:   companies that disclose "going concern" doubt
              AND are in software / AI / data centers / semiconductors / crypto.

  STREAM B -- SPECULATIVE ENERGY INFRA:   early-stage energy / real-estate
              infrastructure plays like Fermi. Surfaced by distinctive phrases
              ("hyperscale data center", "gigawatts of power", etc.), kept only
              if the SEC classifies them as a REIT / utility / energy filer,
              AND they are pre-revenue / low-revenue (the "shaky" gate that
              drops healthy giants like Equinix and Dominion). Also searches
              S-1 (IPO) filings.

Manual overrides you control:
  - ALWAYS_INCLUDE : tickers to force into every scan (currently empty).
  - EXCLUDE_KEYWORDS : drop a company even if it matched (e.g. aerospace).

Same data source you already trust (SEC EDGAR). No API key.
Test it on its own first:   python3 infra_scanner_discovery.py
"""

import time
import requests
from datetime import datetime, timedelta

from infra_scanner_step1 import HEADERS, get_company_facts, get_cik_map, latest_value

EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

LOOKBACK_DAYS = 120     # only filings from roughly the last 4 months
MAX_COMPANIES = 15      # COST GUARDRAIL: never SCAN more than this per run
MAX_CANDIDATES = 150    # COST GUARDRAIL: per-stream candidates to inspect

# --- MANUAL OVERRIDES (plain text -- edit freely) ---------------------------

ALWAYS_INCLUDE = []     # e.g. ["FRMI"] to force a specific ticker in every scan
EXCLUDE_KEYWORDS = ["aerospace", "aircraft", "defense"]

# ============================================================================
# STREAM A -- FAILING TECH  (precise: required "going concern" phrase)
# ============================================================================
DISTRESS_PHRASES = [
    "substantial doubt about its ability to continue as a going concern",
    "substantial doubt about our ability to continue as a going concern",
]
DISTRESS_FORMS = "10-K,10-Q"

TARGET_SIC_CODES = {
    "7370", "7371", "7372", "7373", "7374", "7375", "7377", "7379",  # software / data / hosting
    "3571", "3572", "3576", "3577",                                   # computers & peripherals
    "3674",                                                           # semiconductors
}
SECTOR_KEYWORDS = [
    "software", "semiconductor", "data center", "artificial intelligence",
    "bitcoin", "crypto", "blockchain", "digital asset",
]

# ============================================================================
# STREAM B -- SPECULATIVE ENERGY INFRA  (fuzzy phrases + "shaky" revenue gate)
# ============================================================================
ENERGY_PHRASES = [
    "hyperscale data center",
    "gigawatts of power",
    "behind-the-meter",
    "data center real estate",
]
ENERGY_FORMS = "10-K,10-Q,S-1"   # include S-1 so newly public infra cos appear

ENERGY_SIC_CODES = {
    "6798",            # Real Estate Investment Trusts
    "6500", "6512",    # real estate / operators of buildings
    "4911", "4931",    # electric services / electric & other combined
    "4924", "4922",    # natural gas distribution / transmission
    "1311",            # crude petroleum & natural gas
}
ENERGY_KEYWORDS = [
    "real estate investment trust", "data center", "energy",
    "power", "electric", "gigawatt", "natural gas",
]

# The "shaky" gate: keep only early-stage / pre-revenue companies. Anything
# with revenue at or above this cutoff is treated as an established giant
# (Equinix, Dominion) and dropped. Raise/lower this number to tune.
REVENUE_CEILING = 100_000_000     # $100 million

# Revenue can be reported under several XBRL tags -- check the common ones so a
# big company can't slip through by labeling its revenue differently.
REVENUE_TAGS = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
]

# ----------------------------------------------------------------------------


def _search_filings(phrase, forms, start, end):
    params = {
        "q": f'"{phrase}"', "forms": forms, "dateRange": "custom",
        "startdt": start, "enddt": end, "from": 0, "size": 100,
    }
    try:
        resp = requests.get(EFTS_URL, params=params, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return []
        return resp.json().get("hits", {}).get("hits", [])
    except Exception:
        return []


def _get_submission_meta(cik):
    try:
        resp = requests.get(SUBMISSIONS_URL.format(cik=cik), headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None


def _excluded(blob):
    return any(bad in blob for bad in EXCLUDE_KEYWORDS)


def _in_target_sector(meta):
    """STREAM A keep-test: software / AI / data-center / chip / crypto."""
    sic = str(meta.get("sic", "") or "")
    blob = (meta.get("sicDescription") or "").lower() + " " + (meta.get("name") or "").lower()
    if _excluded(blob):
        return False
    if sic in TARGET_SIC_CODES:
        return True
    return any(kw in blob for kw in SECTOR_KEYWORDS)


def _in_energy_realestate(meta):
    """STREAM B keep-test: REIT / utility / energy real-estate filer."""
    sic = str(meta.get("sic", "") or "")
    blob = (meta.get("sicDescription") or "").lower() + " " + (meta.get("name") or "").lower()
    if _excluded(blob):
        return False
    if sic in ENERGY_SIC_CODES:
        return True
    return any(kw in blob for kw in ENERGY_KEYWORDS)


def _latest_revenue(facts):
    """Largest recent revenue across the common revenue tags (None if none)."""
    best = None
    for tag in REVENUE_TAGS:
        r = latest_value(facts, tag)
        if r and r[0] is not None:
            if best is None or r[0] > best:
                best = r[0]
    return best


def _looks_speculative(facts):
    """STREAM B financial gate: keep pre-revenue / small-revenue (shaky) only."""
    revenue = _latest_revenue(facts)
    if revenue is None:
        return True                        # pre-revenue -> speculative (keep)
    return revenue < REVENUE_CEILING       # small revenue -> keep; giants drop


def _build_company(ticker, cik):
    facts = get_company_facts(cik)
    time.sleep(0.2)
    if facts is None:
        return None
    return {"ticker": ticker, "cik": cik,
            "name": facts.get("entityName", "Unknown"), "facts": facts}


def _pinned_companies():
    if not ALWAYS_INCLUDE:
        return []
    cik_map = get_cik_map()
    out = []
    for ticker in ALWAYS_INCLUDE:
        cik = cik_map.get(ticker.upper())
        if not cik:
            print(f"  (pinned '{ticker}' not in SEC ticker list -- skipping)")
            continue
        company = _build_company(ticker.upper(), cik)
        if company:
            out.append(company)
    return out


def _run_stream(phrases, forms, keep_fn, start, end, have_ciks, slots, financial_gate=None):
    """Surface candidates with `phrases`, keep those passing `keep_fn`
    (and `financial_gate`, if given)."""
    if slots <= 0:
        return []
    candidate_ciks = []
    for phrase in phrases:
        for hit in _search_filings(phrase, forms, start, end):
            for raw in hit.get("_source", {}).get("ciks", []):
                cik = str(raw).zfill(10)
                if cik not in candidate_ciks:
                    candidate_ciks.append(cik)
        time.sleep(0.2)

    out = []
    for cik in candidate_ciks[:MAX_CANDIDATES]:
        if len(out) >= slots:
            break
        if cik in have_ciks:
            continue
        meta = _get_submission_meta(cik)
        time.sleep(0.2)
        if meta is None:
            continue
        tickers = meta.get("tickers") or []
        if not tickers:
            continue
        if not keep_fn(meta):
            continue
        company = _build_company(tickers[0], cik)
        if company is None:
            continue
        if financial_gate and not financial_gate(company["facts"]):
            continue                       # drops healthy giants in Stream B
        out.append(company)
        have_ciks.add(cik)
    return out


def discover_companies(max_companies=MAX_COMPANIES):
    """Find targets via pins + Stream A (failing tech) + Stream B (shaky energy)."""
    companies = _pinned_companies()
    have_ciks = {c["cik"] for c in companies}

    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    print("  ...stream A: failing tech (going concern)")
    companies += _run_stream(DISTRESS_PHRASES, DISTRESS_FORMS, _in_target_sector,
                             start, end, have_ciks, max_companies - len(companies))

    print("  ...stream B: speculative energy / real-estate infrastructure")
    companies += _run_stream(ENERGY_PHRASES, ENERGY_FORMS, _in_energy_realestate,
                             start, end, have_ciks, max_companies - len(companies),
                             financial_gate=_looks_speculative)

    return companies


if __name__ == "__main__":
    print("Discovering targets across BOTH streams...\n")
    found = discover_companies()
    print(f"\nKept {len(found)} company(ies):\n")
    for c in found:
        rev = _latest_revenue(c["facts"])
        rev_str = "pre-revenue" if rev is None else f"rev ~${rev:,.0f}"
        print(f"  {c['ticker']:<6} {c['name']:<40} {rev_str}")
    if not found:
        print("  (none this run -- widen LOOKBACK_DAYS or the phrase lists)")
