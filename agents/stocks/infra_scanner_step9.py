"""
Distressed-Infrastructure Scanner -- STEP 9: THE LANGGRAPH AGENT
===============================================================
Everything already worked as eight scripts run in order. This step does NOT
add new abilities or change any result -- it REORGANIZES the pipeline into a
formal LangGraph "state machine": named boxes wired with arrows.

    START -> source -> analyze -> interpret -> permits -> report -> END

Each box (node) just calls the functions you already built and tested. The
"state" is a bag of data that flows through, getting richer at each box.

Why bother: (1) it matches your framework's wording to the letter
("state charts, routing via code, not LLM discretion"), and (2) it makes the
agent easy to GROW -- a discovery feature later becomes a new box + arrow,
not a rewrite. (max_iterations comes in then, once there's an actual loop.)

Before running: make sure the Ollama app is OPEN.
Run it with:   python infra_scanner_step9.py
"""

import time
from typing import TypedDict
from datetime import datetime

from langgraph.graph import StateGraph, START, END

# Reuse every building block -- nothing here is reinvented.
from infra_scanner_step1 import get_cik_map, get_company_facts, WATCHLIST
from infra_scanner_step2 import score_company
from infra_scanner_step3 import collect_numbers, write_interpretation
from infra_scanner_step4 import RANK
from infra_scanner_step7 import permit_read
from infra_scanner_step8 import render_pdf, figures_for, open_email_draft, EMAIL_TO
from infra_scanner_discovery import discover_companies  # autonomous sourcing


# ---- The "state" that flows through the graph ----
class ScanState(TypedDict):
    companies: list   # list of per-company dicts, enriched at each step
    pdf_path: str     # filled in at the end


# ---- Each node = one stage of the pipeline ----

def source_node(state):
    print("[source]    discovering distressed companies from SEC filings...")
    companies = discover_companies()
    print(f"[source]    found {len(companies)} companies to scan.")
    return {"companies": companies}


def analyze_node(state):
    print("[analyze]   scoring distress (in code, not by the AI)...")
    for c in state["companies"]:
        c["rating"], c["flags"] = score_company(c["facts"])
    return {"companies": state["companies"]}


def interpret_node(state):
    print("[interpret] AI writing the financial reads...")
    for c in state["companies"]:
        numbers = collect_numbers(c["facts"])
        c["fin_note"] = write_interpretation(
            c["ticker"], c["name"], c["rating"], c["flags"], numbers)
    return {"companies": state["companies"]}


def permits_node(state):
    print("[permits]   searching + summarizing permits...")
    for c in state["companies"]:
        c["perm_note"], c["perm_source"] = permit_read(c["ticker"], c["cik"])
    return {"companies": state["companies"]}


def report_node(state):
    print("[report]    building the PDF...")
    companies = sorted(state["companies"], key=lambda c: RANK.get(c["rating"], 3))
    for c in companies:
        c["figures"] = figures_for(c["facts"])
    stats = (sum(c["rating"] == "HIGH" for c in companies),
             sum(c["rating"] == "WATCH" for c in companies),
             sum(c["rating"] == "LOW" for c in companies))
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    pdf_name = f"distress_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    render_pdf(companies, stamp, stats, pdf_name)
    return {"companies": companies, "pdf_path": pdf_name}


# ---- Wire the boxes together ----
def build_agent():
    g = StateGraph(ScanState)
    g.add_node("source", source_node)
    g.add_node("analyze", analyze_node)
    g.add_node("interpret", interpret_node)
    g.add_node("permits", permits_node)
    g.add_node("report", report_node)

    g.add_edge(START, "source")
    g.add_edge("source", "analyze")
    g.add_edge("analyze", "interpret")
    g.add_edge("interpret", "permits")
    g.add_edge("permits", "report")
    g.add_edge("report", END)
    return g.compile()


def main():
    print("Running the agent graph -- give it several minutes.\n")
    agent = build_agent()
    final = agent.invoke({"companies": [], "pdf_path": ""})

    pdf = final["pdf_path"]
    print(f"\nPDF saved: {pdf}")

    if EMAIL_TO != "your.email@example.com":
        print("Opening an email draft for you to review and send...")
        open_email_draft(pdf, EMAIL_TO)
        print("A draft should be open in Mail with the PDF attached. Review it, then hit Send.")
    else:
        print("(Set EMAIL_TO in infra_scanner_step8.py to enable the email draft.)")


if __name__ == "__main__":
    main()
