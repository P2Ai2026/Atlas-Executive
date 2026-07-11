#!/usr/bin/env python3
"""
lutnick_watch.py
Daily policy tracker: searches Google News for coverage of Commerce
Secretary Lutnick discussing the fund / reindustrialization / nuclear
energy, and asks a local Ollama model to summarize what's new. Keeps a
"seen" list so nothing gets reported twice. Outputs a PDF brief.

Run:
    python3 lutnick_watch.py
"""
import os, json, re, subprocess, time
from urllib.parse import quote
import feedparser
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------
# Google News RSS search -- public, no auth, no bot-blocking (unlike
# commerce.gov, which returned a 403 Forbidden to a direct scrape).
# NOTE: kept to specific phrases (not the bare word "fund") to avoid
# pulling in unrelated stories that happen to mention "fund" in passing.
SEARCH_QUERY = 'Lutnick ("sovereign wealth fund" OR nuclear OR reindustrial OR "industrial base" OR "economic security fund")'
FEED_URL = f"https://news.google.com/rss/search?q={quote(SEARCH_QUERY)}&hl=en-US&gl=US&ceid=US:en"

# 30 days: this topic doesn't get covered daily like a podcast does, so a
# short window mostly finds nothing. The "seen" list (below) is what
# actually prevents duplicate reporting, not this window.
LOOKBACK_DAYS = 30
OUTPUT_DIR = str(Path.home() / "Desktop" / "Policy Watch")
SEEN_FILE = os.path.join(OUTPUT_DIR, "lutnick_seen.json")
OLLAMA_MODEL = "llama3"
OLLAMA_URL = "http://localhost:11434/api/generate"

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
}


def ensure_ollama():
    try:
        requests.get("http://localhost:11434", timeout=3)
    except Exception:
        print("[ollama]     not running -- starting it...")
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)


def llm_call(system: str, user: str) -> str:
    try:
        r = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": f"{system}\n\n{user}",
            "stream": False,
        }, timeout=180)
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except Exception as e:
        return f"[llm error: {e}]"


def load_seen() -> set:
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(seen: set):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, indent=1)


EXCLUDE_KEYWORDS = ["iran", "gaza", "houthi", "missile strike"]  # unrelated "nuclear" topic


def is_relevant(title: str, summary: str) -> bool:
    text = f"{title} {summary}".lower()
    if any(k in text for k in EXCLUDE_KEYWORDS):
        return False
    return True


def pdf_safe(text: str) -> str:
    if not text:
        return text
    return text.encode("latin-1", "ignore").decode("latin-1").strip(" -")


def fetch_new_items(seen: set) -> list:
    print("[fetch]      searching Google News for Lutnick coverage...")
    try:
        resp = requests.get(FEED_URL, headers=REQUEST_HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"             could not reach the feed: {e}")
        return []

    feed = feedparser.parse(resp.content)
    if feed.bozo and not feed.entries:
        print(f"             feed did not parse cleanly: {feed.bozo_exception}")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    new_items = []
    for entry in feed.entries:
        link = entry.get("link", "")
        if not link or link in seen:
            continue
        title = entry.get("title", "")
        summary = entry.get("summary", "") or entry.get("description", "")
        source = entry.get("source", {}).get("title", "") if entry.get("source") else ""
        if not is_relevant(title, summary):
            continue
        published = entry.get("published_parsed")
        if published:
            pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
            if pub_dt < cutoff:
                continue
        new_items.append({"title": title, "link": link, "summary": summary, "source": source})
    return new_items


def synthesize(items: list) -> str:
    digest = "\n\n".join(
        f"## {it['title']} ({it['source']})\n{it['summary']}\nSource: {it['link']}"
        for it in items
    )
    return llm_call(
        "You are a policy analyst briefing an executive on U.S. Commerce Secretary "
        "Howard Lutnick's public statements. Reason ONLY from the material given -- "
        "do not add outside claims or invent numbers not present in the text. Note "
        "if a claim comes from a single source vs. multiple corroborating sources.",
        f"Here is recent news coverage mentioning Lutnick:\n\n{digest}\n\n"
        "Write a short brief with exactly these sections:\n"
        "WHAT'S NEW: 2-4 bullets on what Lutnick said or announced, per these articles.\n"
        "RELEVANCE TO THE FUND / NUCLEAR / REINDUSTRIALIZATION: 2-3 bullets connecting "
        "this to the ongoing sovereign-wealth-fund debate, reindustrialization push, "
        "and nuclear energy deals specifically.\n"
        "WATCH NEXT: 1-2 things worth checking for in the coming weeks based on this.",
    )


def inline_md(text: str) -> str:
    text = text.replace("&", "&amp;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return text


def render_pdf(brief_text: str, items: list, path: str):
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=18, spaceAfter=4)
    sub = ParagraphStyle("sub", parent=styles["Normal"], fontSize=10,
                          textColor=colors.HexColor("#555555"), spaceAfter=10)
    head = ParagraphStyle("head", parent=styles["Heading3"], spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10.5, leading=15)
    bull = ParagraphStyle("bull", parent=body, leftIndent=14, spaceAfter=4)
    src = ParagraphStyle("src", parent=styles["Normal"], fontSize=8.5, leading=12,
                          textColor=colors.HexColor("#555555"))

    flow = [Paragraph("Lutnick Policy Watch", h1),
            Paragraph(f"{datetime.now():%A, %B %d, %Y}", sub)]

    for line in brief_text.splitlines():
        line = line.strip()
        if not line:
            continue
        header_match = re.match(r"\*\*(.+?):?\*\*$", line)
        if header_match:
            flow.append(Paragraph(header_match.group(1), head))
            continue
        if line.startswith("*") or line.startswith("-"):
            text = line.lstrip("*- ").strip()
            flow.append(Paragraph(inline_md(text), bull, bulletText="\u2022"))
            continue
        flow.append(Paragraph(inline_md(line), body))

    flow.append(Spacer(1, 14))
    flow.append(Paragraph("Sources", head))
    for it in items:
        safe_title = pdf_safe(it["title"]).replace("&", "&amp;")
        safe_source = pdf_safe(it["source"])
        suffix = f" -- {safe_source}" if safe_source else ""
        flow.append(Paragraph(
            f'<link href="{it["link"]}" color="#1a73e8">{safe_title}</link>{suffix}',
            src))

    doc = SimpleDocTemplate(path, pagesize=letter, topMargin=0.7 * inch,
                            bottomMargin=0.7 * inch, leftMargin=0.7 * inch,
                            rightMargin=0.7 * inch)
    doc.build(flow)


def main():
    print("Running the Lutnick policy watch.\n")
    ensure_ollama()
    seen = load_seen()
    items = fetch_new_items(seen)

    if not items:
        print("[report]     nothing new on Lutnick / the fund / nuclear today.")
        return

    print(f"[report]     {len(items)} new relevant item(s) found:")
    for it in items:
        print(f"             - {it['title']}")

    brief = synthesize(items)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"lutnick_brief_{datetime.now():%Y%m%d}.pdf")
    render_pdf(brief, items, out_path)

    seen.update(it["link"] for it in items)
    save_seen(seen)
    print(f"\nBrief saved: {out_path}")


if __name__ == "__main__":
    main()
