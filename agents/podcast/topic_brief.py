#!/usr/bin/env python3
"""
TOPIC BRIEF -- on-demand meeting prep on any subject.
=====================================================
"I have a meeting about X tomorrow -- what do I need to know?"

Pulls THREE evidence streams and synthesizes one brief:
  1. NEWS      Google News RSS for the topic (same no-auth pattern as
               agents/policy/lutnick_watch.py, generalized to any topic).
  2. PODCASTS  every passage in our transcript cache that mentions the topic,
               attributed to show + episode + date via signal_history.json.
  3. SIGNALS   our measured radar stats for related terms (velocity, breadth).

The synthesis is forced to separate WHAT'S CLAIMED (news) from WHAT THE
MARKET IS SAYING (podcasts/signals) from WHAT WE DON'T KNOW -- a meeting
brief you can defend, not a vibes memo.

Usage:
    python3 topic_brief.py "TITLE" "phrase1" "phrase2" ...
    python3 topic_brief.py "Lutnick meeting" "Lutnick" "sovereign wealth fund" \
        "nuclear" "reindustrialization"

Output: PDF + .md in ~/Desktop/Meeting Briefs/
"""

import os
import re
import sys
import json
import hashlib
from pathlib import Path
from urllib.parse import quote
from datetime import datetime, timedelta, timezone

import requests
import feedparser

# Reuse the podcast agent's Ollama plumbing + config paths
sys.path.insert(0, str(Path(__file__).resolve().parent))
from podcast_intel_agent import (ensure_ollama, llm_call, OUTPUT_DIR,
                                 CACHE_DIR, HISTORY_FILE, SIGNALS_FILE)

BRIEF_DIR = os.environ.get("BRIEF_OUTPUT_DIR") \
            or os.path.expanduser("~/Desktop/Meeting Briefs")
NEWS_LOOKBACK_DAYS = 30
MAX_NEWS = 12
MAX_PASSAGES = 14
PASSAGE_RADIUS = 350          # chars of context either side of a match


# ── 1. NEWS ───────────────────────────────────────────────────────────────────

def fetch_news(phrases):
    """Google News RSS (public, no auth). The FIRST phrase anchors the query
    (usually the person/company the meeting is about); the rest are OR'd
    subtopics — 'Lutnick (nuclear OR "sovereign wealth fund")' beats a bare
    OR across everything, which drowns in generic topic news."""
    anchor = f'"{phrases[0]}"' if " " in phrases[0] else phrases[0]
    if len(phrases) > 1:
        rest = " OR ".join(f'"{p}"' if " " in p else p for p in phrases[1:])
        query = f"{anchor} ({rest})"
    else:
        query = anchor
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
    try:
        parsed = feedparser.parse(url)
    except Exception:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=NEWS_LOOKBACK_DAYS)
    items = []
    for e in parsed.entries[:40]:
        t = getattr(e, "published_parsed", None)
        when = datetime(*t[:6], tzinfo=timezone.utc) if t else None
        if when and when < cutoff:
            continue
        items.append({
            "title": e.get("title", ""),
            "source": (e.get("source") or {}).get("title", "") or "",
            "date": when.strftime("%Y-%m-%d") if when else "",
        })
    items.sort(key=lambda x: x["date"], reverse=True)
    return items[:MAX_NEWS]


# ── 2. PODCAST PASSAGES ───────────────────────────────────────────────────────

def episode_index():
    """Map transcript-cache id -> {podcast, title, date} from signal history."""
    try:
        hist = json.load(open(HISTORY_FILE, encoding="utf-8"))
        return {e["id"]: e for e in hist.get("episodes", [])}
    except Exception:
        return {}


def find_passages(phrases):
    idx = episode_index()
    passages = []
    cache = Path(CACHE_DIR)
    if not cache.exists():
        return passages
    for f in sorted(cache.glob("*.txt"), key=lambda p: -p.stat().st_mtime):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        meta = idx.get(f.stem, {})
        for phrase in phrases:
            for m in re.finditer(re.escape(phrase), text, re.I):
                start = max(0, m.start() - PASSAGE_RADIUS)
                end = min(len(text), m.end() + PASSAGE_RADIUS)
                passages.append({
                    "phrase": phrase,
                    "podcast": meta.get("podcast", "(untracked episode)"),
                    "title": meta.get("title", f.stem[:12]),
                    "date": meta.get("date", ""),
                    "text": re.sub(r"\s+", " ", text[start:end]).strip(),
                })
                if len(passages) >= MAX_PASSAGES:
                    return passages
    return passages


# ── 3. SIGNAL STATS ───────────────────────────────────────────────────────────

def related_signals(phrases):
    try:
        data = json.load(open(SIGNALS_FILE, encoding="utf-8"))
    except Exception:
        return []
    words = {w.lower() for p in phrases for w in p.split()}
    out = []
    for s in data.get("signals", []):
        term_words = set(s["term"].lower().split(" /")[0].split())
        if term_words & words or any(p.lower() in s["term"].lower() for p in phrases):
            out.append(s)
    return out


# ── SYNTHESIS + OUTPUT ────────────────────────────────────────────────────────

def build_brief(title, phrases):
    news = fetch_news(phrases)
    passages = find_passages(phrases)
    signals = related_signals(phrases)

    news_block = "\n".join(f"- [{n['date']}] {n['title']} ({n['source']})"
                           for n in news) or "(no recent news found)"
    pas_block = "\n\n".join(
        f'[{p["date"]}] {p["podcast"]} — "{p["title"]}" (matched: {p["phrase"]})\n…{p["text"]}…'
        for p in passages) or "(no podcast mentions in our transcript archive)"
    sig_block = "\n".join(
        f"- {s['term']}: {s['current']} mentions this week, "
        f"{s['breadth']} show(s), status {s['status']}"
        for s in signals) or "(no matching radar signals in the current window)"

    synthesis = llm_call(
        "You are preparing an executive for a high-stakes meeting. He runs an "
        "AI-/data-center-infrastructure business (power, chips, cooling, construction). "
        "Be precise about EVIDENCE: news headlines are claims, not confirmations; "
        "podcast passages are market chatter; radar stats are our own measurements. "
        "Never invent facts not present in the evidence below.",
        f"MEETING TOPIC: {title}\nTracked phrases: {', '.join(phrases)}\n\n"
        f"RECENT NEWS HEADLINES (last {NEWS_LOOKBACK_DAYS} days):\n{news_block}\n\n"
        f"PODCAST EVIDENCE (our transcript archive):\n{pas_block}\n\n"
        f"OUR RADAR SIGNALS:\n{sig_block}\n\n"
        "Write the brief with EXACTLY these sections:\n"
        "WHAT'S BEING SAID: 3-5 bullets from the news, each ending with the headline date.\n"
        "WHAT THE MARKET IS SAYING: 2-4 bullets from podcast evidence + radar stats. "
        "If coverage is thin, SAY SO — thin chatter on a big story is itself a signal.\n"
        "WHAT IT MEANS FOR US: 2-4 bullets tying this to power, chips, cooling, or construction.\n"
        "QUESTIONS TO ASK IN THE MEETING: 3-5 pointed questions.\n"
        "WHAT WE DON'T KNOW: 2-3 bullets of open unknowns or unverified claims.",
    )
    return synthesis, news, passages, signals


def write_outputs(title, phrases, synthesis, news, passages, signals):
    os.makedirs(BRIEF_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40]
    stamp = datetime.now().strftime("%Y%m%d")
    md_path = os.path.join(BRIEF_DIR, f"brief_{slug}_{stamp}.md")
    pdf_path = os.path.join(BRIEF_DIR, f"brief_{slug}_{stamp}.pdf")

    md = [f"# Meeting Brief — {title}",
          f"*{datetime.now():%A, %B %d, %Y} · phrases: {', '.join(phrases)}*", "",
          synthesis, "", "---", "## Appendix — evidence", "", "### News"]
    md += [f"- [{n['date']}] {n['title']} ({n['source']})" for n in news] or ["(none)"]
    md += ["", "### Podcast passages"]
    md += [f"- **[{p['date']}] {p['podcast']}** — …{p['text'][:250]}…" for p in passages] or ["(none)"]
    md += ["", "### Radar signals"]
    md += [f"- {s['term']}: {s['current']} mentions, {s['breadth']} shows, {s['status']}"
           for s in signals] or ["(none)"]
    open(md_path, "w", encoding="utf-8").write("\n".join(md))

    # simple clean PDF
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=base["Heading1"], fontSize=17,
                        textColor=colors.HexColor("#16324f"))
    sub = ParagraphStyle("sub", parent=base["Normal"], fontSize=9,
                         textColor=colors.HexColor("#6b7280"))
    body = ParagraphStyle("body", parent=base["Normal"], fontSize=9.5, leading=14)
    head = ParagraphStyle("head", parent=body, fontName="Helvetica-Bold", fontSize=10.5,
                          textColor=colors.HexColor("#16324f"), spaceBefore=8, spaceAfter=3)

    def esc(t):
        return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    flow = [Paragraph(f"Meeting Brief — {esc(title)}", h1),
            Paragraph(f"{datetime.now():%A, %B %d, %Y} · phrases: {esc(', '.join(phrases))}", sub),
            Spacer(1, 10)]
    for raw in synthesis.split("\n"):
        line = raw.strip()
        if not line:
            continue
        hdr = re.match(r"^\**([A-Z][A-Z '&/\-]{2,}:)\**\s*(.*)$", line)
        if hdr:
            flow.append(Paragraph(esc(hdr.group(1)), head))
            if hdr.group(2):
                flow.append(Paragraph(esc(hdr.group(2)), body))
        else:
            flow.append(Paragraph(esc(re.sub(r"^[\*\-•]\s*", "• ", line)), body))
    flow += [Spacer(1, 12), HRFlowable(width="100%", thickness=0.5,
                                       color=colors.HexColor("#d7dee6")),
             Paragraph(f"<font size=8 color='#9ca3af'>Evidence: {len(news)} news items · "
                       f"{len(passages)} podcast passages · {len(signals)} radar signals. "
                       f"Full appendix in the .md file.</font>", body)]
    SimpleDocTemplate(pdf_path, pagesize=letter, topMargin=0.7*inch,
                      bottomMargin=0.7*inch, leftMargin=0.8*inch,
                      rightMargin=0.8*inch).build(flow)
    return md_path, pdf_path


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    title, phrases = sys.argv[1], sys.argv[2:]
    print(f"Topic brief: {title}  ({', '.join(phrases)})")
    ensure_ollama()
    synthesis, news, passages, signals = build_brief(title, phrases)
    md, pdf = write_outputs(title, phrases, synthesis, news, passages, signals)
    print(f"\nBrief written:\n  {pdf}\n  {md}")
    print(f"Evidence: {len(news)} news · {len(passages)} podcast passages · {len(signals)} signals")


if __name__ == "__main__":
    main()
