"""
Distressed-Infrastructure Scanner -- STEP 8: PDF REPORT + EMAIL DRAFT
====================================================================
Same pipeline as Step 7 (financials + permits), but now it:
  1. writes a clean, styled PDF (no more raw-markdown "weird font"), and
  2. opens a ready-to-send email to YOU with that PDF attached.

About the email: it opens a DRAFT in your Mac's Mail app and you click Send.
On purpose -- not a silent auto-send. Two reasons: it keeps YOU as the
approval gate (the safety property we told your boss about), and it means
your email password never has to be stored in this file. The PDF is also
saved to your folder no matter what, so even if the draft hiccups you can
attach it by hand.

>>> SET YOUR EMAIL in EMAIL_TO below before running. <<<

Before running: make sure the Ollama app is OPEN.
Run it with:   python infra_scanner_step8.py
"""

import os
import time
import subprocess
from datetime import datetime
from fpdf import FPDF

from infra_scanner_step1 import get_cik_map, get_company_facts, latest_value, WATCHLIST
from infra_scanner_step2 import score_company
from infra_scanner_step3 import collect_numbers, write_interpretation
from infra_scanner_step4 import RANK, REPORT_FACTS
from infra_scanner_step7 import permit_read

# >>> maximilian.dabbous@gmail.com <<<
EMAIL_TO = "maximilian.dabbous@gmail.com"


# ---------- PDF rendering (tested) ----------

def safe(text):
    """Swap fancy quotes/dashes so the PDF's basic font can render them."""
    if text is None:
        return ""
    for a, b in {"\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
                 "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u2022": "-"}.items():
        text = text.replace(a, b)
    return text.encode("latin-1", "replace").decode("latin-1")


RATING_COLOR = {"HIGH": (190, 30, 30), "WATCH": (200, 120, 0), "LOW": (40, 130, 40)}


def render_pdf(companies, stamp, stats, out_path):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    L = pdf.l_margin

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "Distressed Infrastructure Scan", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9); pdf.set_text_color(110, 110, 110)
    pdf.cell(0, 5, safe(f"Generated {stamp}  -  Source: SEC EDGAR filings  -  Local model: Llama 3"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    h, w, lo = stats
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, safe(f"Summary: {h+w+lo} companies scanned  -  {h} HIGH, {w} WATCH, {lo} LOW"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 8); pdf.set_text_color(120, 120, 120); pdf.set_x(L)
    pdf.multi_cell(pdf.epw, 4, safe("[DRAFT - FOR HUMAN REVIEW] Pulled automatically from SEC filings; "
                                    "verify before sharing. Public companies only; reflects disclosures, "
                                    "not official agency permit records."))
    pdf.set_text_color(0, 0, 0); pdf.ln(3)

    for c in companies:
        pdf.set_draw_color(210, 210, 210)
        pdf.line(L, pdf.get_y(), L + pdf.epw, pdf.get_y()); pdf.ln(2)

        pdf.set_x(L); pdf.set_font("Helvetica", "B", 13); pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 8, safe(f"{c['ticker']} - {c['name']}"), new_x="LMARGIN", new_y="NEXT")
        r, g, b = RATING_COLOR.get(c["rating"], (0, 0, 0))
        pdf.set_font("Helvetica", "B", 11); pdf.set_text_color(r, g, b)
        pdf.cell(0, 6, safe(f"Distress: {c['rating']}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0); pdf.ln(1)

        pdf.set_font("Helvetica", "B", 10); pdf.set_x(L)
        pdf.cell(0, 6, "Financial read", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10); pdf.set_x(L); pdf.multi_cell(pdf.epw, 5, safe(c["fin_note"])); pdf.ln(1)

        pdf.set_font("Helvetica", "B", 10); pdf.set_x(L)
        pdf.cell(0, 6, "Distress signals", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for f in (c["flags"] or ["none"]):
            pdf.set_x(L); pdf.multi_cell(pdf.epw, 5, safe(f"  -  {f}"))
        pdf.ln(1)

        pdf.set_font("Helvetica", "B", 10); pdf.set_x(L)
        pdf.cell(0, 6, "Permit read", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10); pdf.set_x(L); pdf.multi_cell(pdf.epw, 5, safe(c["perm_note"]))
        if c.get("perm_source"):
            pdf.set_font("Helvetica", "I", 8); pdf.set_text_color(120, 120, 120); pdf.set_x(L)
            pdf.multi_cell(pdf.epw, 4, safe(f"Permit source: {c['perm_source']}")); pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

        pdf.set_x(L); pdf.set_font("Helvetica", "B", 9); pdf.set_fill_color(235, 235, 235)
        pdf.cell(70, 6, "Item", border=1, fill=True)
        pdf.cell(55, 6, "Value (USD)", border=1, fill=True, align="R")
        pdf.cell(40, 6, "As of", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for item, val, date in c["figures"]:
            pdf.set_x(L)
            pdf.cell(70, 6, safe(item), border=1)
            pdf.cell(55, 6, safe(val), border=1, align="R")
            pdf.cell(40, 6, safe(date), border=1, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    pdf.output(out_path)


# ---------- data gathering ----------

def figures_for(facts):
    rows = []
    for tag, label in REPORT_FACTS.items():
        res = latest_value(facts, tag)
        if res:
            val, date = res
            rows.append((label, f"{val:,.0f}", date))
        else:
            rows.append((label, "not reported", "-"))
    return rows


def gather():
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
            "fin_note": fin_note, "perm_note": perm_note, "perm_source": perm_source,
            "figures": figures_for(facts),
        })
        time.sleep(0.3)
    companies.sort(key=lambda c: RANK.get(c["rating"], 3))
    return companies


# ---------- email draft ----------

def open_email_draft(pdf_path, to_addr):
    """Open a ready-to-send draft in the Mac Mail app with the PDF attached."""
    abspath = os.path.abspath(pdf_path)
    script = f'''
tell application "Mail"
    set newMessage to make new outgoing message with properties {{subject:"Distressed Infrastructure Scan", content:"Latest distress + permit scan attached. Draft for review.\\n\\n", visible:true}}
    tell newMessage
        make new to recipient at end of to recipients with properties {{address:"{to_addr}"}}
    end tell
    delay 1
    tell content of newMessage
        make new attachment with properties {{file name:(POSIX file "{abspath}")}} at after the last paragraph
    end tell
    activate
end tell
'''
    subprocess.run(["osascript", "-e", script], check=False)


def main():
    if EMAIL_TO == "your.email@example.com":
        print("NOTE: set EMAIL_TO near the top of this file to your real email first.\n")

    print("Building the report -- financials AND permits for every company.")
    print("This is the long one. Give it several minutes.\n")
    companies = gather()

    stats = (sum(c["rating"] == "HIGH" for c in companies),
             sum(c["rating"] == "WATCH" for c in companies),
             sum(c["rating"] == "LOW" for c in companies))
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    pdf_name = f"distress_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    render_pdf(companies, stamp, stats, pdf_name)
    print(f"\nPDF saved: {pdf_name}")

    if EMAIL_TO != "your.email@example.com":
        print("Opening an email draft for you to review and send...")
        open_email_draft(pdf_name, EMAIL_TO)
        print("A draft should now be open in Mail with the PDF attached. Review it, then hit Send.")
    else:
        print("(No email sent -- set EMAIL_TO to enable the draft. You can open the PDF directly.)")


if __name__ == "__main__":
    main()
