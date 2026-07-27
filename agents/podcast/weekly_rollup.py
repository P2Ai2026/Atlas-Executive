#!/usr/bin/env python3
"""
weekly_rollup.py
Lightweight weekly executive summary. Does NOT re-fetch or re-transcribe any
podcasts -- it reads what the daily agent already produced (signals_latest.json
and predictions.json) and writes one higher-altitude PDF for a weekly check-in.
Safe to run any time; never touches podcast feeds or does transcription.

Run:
    python3 weekly_rollup.py
"""
import sys, os, json, re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from podcast_intel_agent import (
    OUTPUT_DIR, SIGNALS_FILE, PREDICTION_CHECK_DAYS,
    llm_call, load_predictions, track_record_summary,
)

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer


def load_latest_signals():
    try:
        with open(SIGNALS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def weekly_synthesis(data, track_record):
    signals = data.get("signals", [])
    opportunities = data.get("opportunities", [])
    today_str = datetime.now().strftime("%B %d, %Y")

    sig_lines_parts = []
    for s in signals[:15]:
        vel = "new" if s["velocity"] is None else f"{s['velocity']}x"
        sig_lines_parts.append(f"- {s['term']}: {s['status']}, {s['breadth']} show(s), velocity {vel}")
    sig_lines = "\n".join(sig_lines_parts)

    opp_lines = "\n\n".join(
        f"## {o['signal']} ({o['status']})\n{o['analysis'][:600]}" for o in opportunities
    ) or "(no opportunity mapping available this week)"

    tr_line = "no resolved predictions yet -- track record is still building"
    if track_record.get("total", 0) > 0:
        counts = ", ".join(f"{v} {k.lower()}" for k, v in track_record["counts"].items())
        tr_line = (f"{track_record['held_up_pct']}% of {track_record['total']} resolved "
                   f"calls held up ({counts}); {track_record['pending']} still pending")

    return llm_call(
        f"Today's real date is {today_str}. You are writing a WEEKLY executive "
        "rollup for an internal strategy meeting -- higher altitude than a daily "
        "brief. Synthesize across the week's signals rather than listing every "
        "single one. Reason ONLY from the material given; do not invent figures. "
        "Format each section header exactly as **SECTION NAME:** on its own line, "
        "followed by bullets starting with '-'.",
        f"THIS WEEK'S MEASURED SIGNALS:\n{sig_lines}\n\n"
        f"THIS WEEK'S OPPORTUNITY MAPPING:\n{opp_lines}\n\n"
        f"TRACK RECORD TO DATE: {tr_line}\n\n"
        "Write a tight weekly executive summary with EXACTLY these sections:\n"
        "**THE WEEK IN ONE PARAGRAPH:** the single most important thread this "
        "week, in plain language for an executive walking into a meeting.\n"
        "**TOP 3 SIGNALS TO WATCH:** the three most important signals, each with "
        "why it matters and its current status.\n"
        "**STRONGEST INVESTABLE EXPOSURE:** the single most credible "
        "company-level exposure from the mapping, with a one-line bull/bear.\n"
        "**TRACK RECORD CHECK:** one line on whether the agent's own past calls "
        "are holding up, based on the data given.\n"
        "**RECOMMENDED TALKING POINTS:** 2-3 bullets specifically framed for "
        "presenting to a boss/team in a meeting.",
    )


def inline_md(text):
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text.replace("&", "&amp;"))


def render_weekly_pdf(synthesis, track_record, path):
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=20, spaceAfter=4)
    sub = ParagraphStyle("sub", parent=styles["Normal"], fontSize=10,
                          textColor=colors.HexColor("#555555"), spaceAfter=14)
    head = ParagraphStyle("head", parent=styles["Heading3"], spaceBefore=12, spaceAfter=4)
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=11, leading=16)
    bull = ParagraphStyle("bull", parent=body, leftIndent=14, spaceAfter=4)

    flow = [Paragraph("Weekly Executive Rollup", h1),
            Paragraph(f"Week ending {datetime.now():%A, %B %d, %Y}", sub)]

    for line in synthesis.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"\*\*(.+?):?\*\*$", line)
        if m:
            flow.append(Paragraph(m.group(1), head))
            continue
        if line.startswith(("-", "*")):
            flow.append(Paragraph(inline_md(line.lstrip("-* ").strip()), bull, bulletText="\u2022"))
        else:
            flow.append(Paragraph(inline_md(line), body))

    if track_record.get("total", 0) > 0:
        flow.append(Spacer(1, 10))
        flow.append(Paragraph("Track Record Snapshot", head))
        counts = ", ".join(f"{v} {k.lower()}" for k, v in track_record["counts"].items())
        flow.append(Paragraph(
            f"{track_record['held_up_pct']}% held up out of {track_record['total']} "
            f"scored ({counts}); {track_record['pending']} pending (checked back "
            f"{PREDICTION_CHECK_DAYS} days after each call).", body))

    doc = SimpleDocTemplate(path, pagesize=letter, topMargin=0.8 * inch,
                            bottomMargin=0.8 * inch, leftMargin=0.8 * inch,
                            rightMargin=0.8 * inch)
    doc.build(flow)


def main():
    print("Running the weekly rollup (reusing today's data -- no fetching/transcribing).\n")
    data = load_latest_signals()
    if not data:
        print("No signals_latest.json found -- run podcast_intel_agent.py at least once first.")
        return
    preds = load_predictions()
    track_record = track_record_summary(preds)

    print("[weekly] synthesizing across this week's signals + opportunities...")
    synthesis = weekly_synthesis(data, track_record)

    stamp = datetime.now().strftime("%Y%m%d")
    out_path = os.path.join(OUTPUT_DIR, f"weekly_rollup_{stamp}.pdf")
    render_weekly_pdf(synthesis, track_record, out_path)
    print(f"\nWeekly rollup saved: {out_path}")

    # Also save the same synthesis as JSON so publish_dashboard.py can render
    # a clean HTML version for the boss-facing site (no PDF re-parsing).
    json_path = os.path.join(OUTPUT_DIR, f"weekly_rollup_{stamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated": datetime.now().isoformat(timespec="seconds"),
            "week_ending": datetime.now().strftime("%Y-%m-%d"),
            "synthesis": synthesis,
            "track_record": track_record,
        }, f, indent=1)

    try:
        import publish_dashboard
        publish_dashboard.publish()
    except Exception as e:
        print(f"[dashboard] skipped publishing this run: {e}")


if __name__ == "__main__":
    main()
