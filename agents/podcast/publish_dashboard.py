#!/usr/bin/env python3
"""
publish_dashboard.py
=====================================================
Turns the podcast agent's existing JSON output into a clean, quick-to-read
HTML dashboard, and (if the site folder is already a git repo with a
remote) commits + pushes it so the published page updates automatically.

Reads ONLY what podcast_intel_agent.py / weekly_rollup.py already wrote to
disk -- no re-analysis, no new LLM calls, no re-fetching, no network calls
of its own except the git push at the very end. Safe to run as often as
you like; safe to import and call publish() from another script.

Run standalone:
    python3 publish_dashboard.py
"""
import os
import re
import json
import glob
import html
import subprocess
from pathlib import Path
from datetime import datetime

# ── locations ──────────────────────────────────────────────────────────────
OUTPUT_DIR = os.environ.get("PODCAST_OUTPUT_DIR") \
             or os.path.expanduser("~/Desktop/Agent 3- Podcast Reviews")
SIGNALS_FILE = os.path.join(OUTPUT_DIR, "signals_latest.json")
WEEKLY_GLOB = os.path.join(OUTPUT_DIR, "weekly_rollup_*.json")

SITE_DIR = os.environ.get("BRIEFS_SITE_DIR") \
           or os.path.expanduser("~/Desktop/Atlas-Executive")
DOCS_DIR = os.path.join(SITE_DIR, "docs")
REPORTS_DIR = os.path.join(DOCS_DIR, "reports")
MANIFEST_FILE = os.path.join(DOCS_DIR, "manifest.json")

BUSINESS_LENS = "AI infrastructure and data-center development"

STATUS_COLOR = {
    "NEW":              "#7c3aed",
    "FRINGE RISING":    "#dc2626",
    "GOING MAINSTREAM":  "#c026d3",
    "EMERGING":         "#ea580c",
    "RISING":           "#b7791f",
    "MAINSTREAM":       "#16a34a",
    "STEADY":           "#6b7280",
}
RELEVANCE_COLOR = {"HIGH": "#16a34a", "MEDIUM": "#b7791f", "LOW": "#6b7280", "N/A": "#9ca3af"}


# ── text cleanup ──────────────────────────────────────────────────────────
# Strips leaked LLM boilerplate lines like "Here's my response:" / "Here are
# my findings:" that show up verbatim in the raw synthesis/analysis text.
JUNK_LINE = re.compile(
    r"^\s*here'?s?\s+(my|a|the)\s+[a-z0-9 \-']*:?\s*$"
    r"|^\s*here\s+(are|is)\s+(my\s+)?[a-z0-9 \-']*:?\s*$",
    re.I,
)
HEADER_LINE = re.compile(r"^\**([A-Z][A-Z \-/']{2,}):?\**\s*(.*)$")
BULLET_LINE = re.compile(r"^[\*\-•]\s+(.*)$")
NUMBER_LINE = re.compile(r"^(\d+)\.\s+(.*)$")
BOLD = re.compile(r"\*\*(.+?)\*\*")
ITALIC = re.compile(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)")


def esc(t):
    return html.escape(t or "", quote=False)


def inline(t):
    t = esc(t)
    t = BOLD.sub(r"<strong>\1</strong>", t)
    t = ITALIC.sub(r"<em>\1</em>", t)
    return t


def md_to_html(text, heading_tag="h4"):
    """Same shape as the PDF's md_flow(), rendered as HTML instead."""
    if not text:
        return ""
    out = []
    open_list = False

    def close_list():
        nonlocal open_list
        if open_list:
            out.append("</ul>")
            open_list = False

    for raw in text.split("\n"):
        line = raw.strip()
        if not line or JUNK_LINE.match(line):
            continue
        hdr = HEADER_LINE.match(line)
        bullet = BULLET_LINE.match(line)
        number = NUMBER_LINE.match(line)
        if hdr and not bullet:
            close_list()
            label, rest = hdr.group(1), hdr.group(2).strip()
            out.append(f"<{heading_tag}>{inline(label)}</{heading_tag}>")
            if rest:
                out.append(f"<p>{inline(rest)}</p>")
        elif bullet:
            if not open_list:
                out.append("<ul>")
                open_list = True
            out.append(f"<li>{inline(bullet.group(1))}</li>")
        elif number:
            if not open_list:
                out.append("<ol>")
                open_list = True
            out.append(f"<li>{inline(number.group(2))}</li>")
        else:
            close_list()
            out.append(f"<p>{inline(line)}</p>")
    close_list()
    return "\n".join(out)


def quick_take(synthesis):
    """First real bullet/line of the synthesis -- used as the one-line
    'quick take' banner at the top of a report."""
    for raw in (synthesis or "").split("\n"):
        line = raw.strip()
        if not line or JUNK_LINE.match(line) or HEADER_LINE.match(line):
            continue
        line = BULLET_LINE.match(line).group(1) if BULLET_LINE.match(line) else line
        return inline(line)
    return ""


# ── data loading ───────────────────────────────────────────────────────────

def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_manifest():
    return load_json(MANIFEST_FILE) or {"entries": []}


def save_manifest(manifest):
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)


# ── page renderers ─────────────────────────────────────────────────────────

PAGE_CSS = """
:root{
  --ink:#16324f; --mute:#6b7280; --rule:#e2e8f0; --bg:#f7f9fc;
  --card:#ffffff; --gold:#b08d57;
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--bg); color:#1f2937;
  font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
}
.wrap{max-width:820px;margin:0 auto;padding:28px 20px 80px}
a{color:#2563eb;text-decoration:none}
a:hover{text-decoration:underline}
.top-nav{font-size:14px;margin-bottom:18px}
.masthead{margin-bottom:22px}
.masthead h1{font-size:26px;margin:0 0 4px;color:var(--ink);letter-spacing:-.02em}
.masthead .meta{color:var(--mute);font-size:14px}
.quick-take{
  background:linear-gradient(135deg,#eef4ff,#f5eefc);
  border:1px solid #dbe4f3; border-radius:14px; padding:16px 18px;
  margin:18px 0 26px; font-size:17px; font-weight:600; color:var(--ink);
}
.quick-take .label{
  display:block; font-size:11px; font-weight:800; letter-spacing:.08em;
  color:#7c3aed; text-transform:uppercase; margin-bottom:6px;
}
.card{
  background:var(--card); border:1px solid var(--rule); border-radius:14px;
  padding:18px 20px; margin-bottom:16px;
}
.band{
  font-weight:800; font-size:13px; letter-spacing:.03em; text-transform:uppercase;
  color:#fff; background:var(--ink); border-radius:8px; padding:8px 12px;
  margin:0 0 14px; display:inline-block;
}
.band.gold{background:var(--gold)} .band.red{background:#7c2d12}
h4{margin:14px 0 4px;font-size:13.5px;color:var(--ink);letter-spacing:.02em}
h4:first-child{margin-top:0}
p{margin:4px 0 8px}
ul,ol{margin:4px 0 10px;padding-left:22px}
li{margin:3px 0}
table.sig{width:100%;border-collapse:collapse;font-size:13.5px;margin-bottom:4px}
table.sig th,table.sig td{padding:7px 8px;border-bottom:1px solid var(--rule);text-align:left}
table.sig th{color:var(--mute);font-weight:700;font-size:11.5px;text-transform:uppercase;letter-spacing:.03em}
.status-pill{display:inline-block;padding:2px 9px;border-radius:999px;color:#fff;font-weight:700;font-size:11.5px;white-space:nowrap}
.rel-pill{display:inline-block;padding:2px 9px;border-radius:999px;color:#fff;font-weight:700;font-size:11px}
details{border:1px solid var(--rule);border-radius:12px;margin-bottom:10px;overflow:hidden}
details summary{
  cursor:pointer; padding:12px 16px; font-weight:700; color:var(--ink);
  list-style:none; display:flex; justify-content:space-between; gap:10px;
  align-items:center; background:#fafbfd;
}
details summary::-webkit-details-marker{display:none}
details summary .arrow{color:var(--mute);font-weight:400;font-size:13px}
details[open] summary{border-bottom:1px solid var(--rule)}
details .inner{padding:14px 16px}
.tag{font-size:11.5px;font-weight:700;padding:2px 8px;border-radius:6px}
.tag.verified{background:#dcfce7;color:#166534}
.tag.inferred{background:#fef3c7;color:#92400e}
.episode-title{font-style:italic;color:var(--mute);font-size:13.5px}
.note-card{
  background:#fbf8f2; border:1px dashed #d9c9a8; border-radius:14px;
  padding:16px 20px; margin-top:26px;
}
.note-card summary{background:transparent}
.index-list{list-style:none;margin:0;padding:0}
.index-item{
  display:block; background:var(--card); border:1px solid var(--rule);
  border-radius:14px; padding:16px 18px; margin-bottom:12px;
}
.index-item .idate{font-weight:800;color:var(--ink);font-size:15px}
.index-item .itype{
  font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:.05em;
  color:#7c3aed; margin-left:8px;
}
.index-item .itake{margin-top:6px;color:#374151;font-size:14.5px}
footer{color:var(--mute);font-size:12px;margin-top:30px;text-align:center}
"""


def page_shell(title, body_html, nav_html=""):
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>{PAGE_CSS}</style>
</head><body><div class="wrap">
{nav_html}
{body_html}
<footer>Generated automatically from the podcast intelligence agent &middot; not investment advice</footer>
</div></body></html>"""


def status_pill(status):
    color = STATUS_COLOR.get(status, "#6b7280")
    return f'<span class="status-pill" style="background:{color}">{esc(status)}</span>'


def rel_pill(rel):
    color = RELEVANCE_COLOR.get(rel, "#9ca3af")
    return f'<span class="rel-pill" style="background:{color}">{esc(rel)}</span>'


def signal_table_html(signals):
    if not signals:
        return ""
    rows = []
    for s in signals[:15]:
        vel = "&mdash;" if s.get("velocity") is None else f"{s['velocity']}x"
        rows.append(
            f"<tr><td><strong>{esc(s['term'])}</strong></td>"
            f"<td>{s['current']}</td><td>{s['baseline_weekly']}</td>"
            f"<td>{vel}</td><td>{s['breadth']}</td>"
            f"<td>{status_pill(s['status'])}</td></tr>"
        )
    return (
        '<table class="sig"><tr><th>Signal</th><th>7-day</th><th>Base/wk</th>'
        '<th>Velocity</th><th># shows</th><th>Status</th></tr>'
        + "".join(rows) + "</table>"
    )


def opportunities_html(opportunities):
    if not opportunities:
        return ""
    cards = []
    for o in opportunities:
        tag = ('<span class="tag verified">&#10003; data-verified</span>' if o.get("data_grounded")
               else '<span class="tag inferred">model-inferred</span>')
        cards.append(f"""
<details>
  <summary><span>{esc(o['signal'])} &middot; {status_pill(o['status'])} &nbsp; {tag}</span>
  <span class="arrow">tap to expand</span></summary>
  <div class="inner">{md_to_html(o.get('analysis',''))}</div>
</details>""")
    return f"""
<div class="card">
  <span class="band gold">Investable Exposure &mdash; not advice</span>
  <p style="color:#6b7280;font-size:13.5px;margin-top:0">Mapped exposure with bull/bear case and a
  falsifiable trigger, straight from the agent's own data &mdash; this is analysis to inform your
  own judgment, not a recommendation.</p>
  {''.join(cards)}
</div>"""


def episodes_html(episodes):
    if not episodes:
        return ""
    cards = []
    for e in episodes:
        body = e.get("analysis", "")
        body_html = (
            md_to_html(body, heading_tag="h4")
            if body else
            '<p style="color:#9ca3af">Full episode breakdown wasn\'t saved for this run '
            '&mdash; it will show up starting with the next scan.</p>'
        )
        cards.append(f"""
<details>
  <summary><span>{esc(e['podcast'])} &nbsp;{rel_pill(e.get('relevance','N/A'))}
  <span class="episode-title">&mdash; {esc(e.get('title',''))}</span></span>
  <span class="arrow">{esc(e.get('published',''))}</span></summary>
  <div class="inner">{body_html}</div>
</details>""")
    return f"""
<div class="card">
  <span class="band">Per-Episode Breakdown</span>
  {''.join(cards)}
</div>"""


def bible_html(bible):
    if not bible or not bible.get("message"):
        return ""
    return f"""
<details class="note-card">
  <summary><span>Personal note &mdash; Bible in a Year</span><span class="arrow">tap to expand</span></summary>
  <div class="inner">
    <p class="episode-title">{esc(bible.get('title',''))}</p>
    {md_to_html(bible.get('message',''))}
  </div>
</details>"""


def track_record_html(tr):
    if not tr or not tr.get("total"):
        return ""
    counts = ", ".join(f"{v} {k.lower()}" for k, v in tr.get("counts", {}).items())
    return f"""
<div class="card">
  <span class="band gold">Track Record &mdash; do this agent's own calls hold up?</span>
  <p><strong>{tr['held_up_pct']}%</strong> of resolved calls held up out of
  <strong>{tr['total']}</strong> scored to date ({counts}).
  {tr.get('pending',0)} calls still pending.</p>
</div>"""


def render_daily(data):
    date_str = data.get("generated", "")[:10]
    try:
        pretty_date = datetime.fromisoformat(data["generated"]).strftime("%A, %B %d, %Y")
    except Exception:
        pretty_date = date_str

    qt = quick_take(data.get("synthesis", ""))
    body = [
        '<div class="top-nav"><a href="../index.html">&larr; All briefs</a></div>',
        '<div class="masthead">',
        '<h1>Daily Podcast Signal Brief</h1>',
        f'<div class="meta">{esc(pretty_date)} &middot; lens: {esc(BUSINESS_LENS)}</div>',
        '</div>',
    ]
    if qt:
        body.append(f'<div class="quick-take"><span class="label">Quick take</span>{qt}</div>')

    body.append(track_record_html(data.get("track_record")))

    sig_html = signal_table_html(data.get("signals", []))
    if sig_html:
        body.append(f'<div class="card"><span class="band">Signal Radar &mdash; 7-day vs 3-week baseline</span>{sig_html}</div>')

    syn_html = md_to_html(data.get("synthesis", ""))
    if syn_html:
        body.append(f'<div class="card"><span class="band">Where the Change Is Happening / What It Means / How to Act</span>{syn_html}</div>')

    body.append(opportunities_html(data.get("opportunities", [])))

    rt = data.get("red_team", "")
    if rt and not rt.startswith("["):
        body.append(f'<div class="card"><span class="band red">Confidence Check (Red Team)</span>{md_to_html(rt)}</div>')

    body.append(episodes_html(data.get("new_episodes", [])))
    body.append(bible_html(data.get("bible")))

    return page_shell(f"Daily Brief — {pretty_date}", "\n".join(b for b in body if b))


def render_weekly(data):
    date_str = data.get("week_ending", data.get("generated", ""))[:10]
    try:
        pretty_date = datetime.fromisoformat(date_str).strftime("%A, %B %d, %Y")
    except Exception:
        pretty_date = date_str

    qt = quick_take(data.get("synthesis", ""))
    body = [
        '<div class="top-nav"><a href="../index.html">&larr; All briefs</a></div>',
        '<div class="masthead">',
        '<h1>Weekly Executive Rollup</h1>',
        f'<div class="meta">Week ending {esc(pretty_date)}</div>',
        '</div>',
    ]
    if qt:
        body.append(f'<div class="quick-take"><span class="label">The week in one line</span>{qt}</div>')

    body.append(track_record_html(data.get("track_record")))

    syn_html = md_to_html(data.get("synthesis", ""))
    if syn_html:
        body.append(f'<div class="card"><span class="band">Weekly Summary</span>{syn_html}</div>')

    return page_shell(f"Weekly Rollup — {pretty_date}", "\n".join(b for b in body if b))


def render_index(manifest):
    entries = sorted(manifest.get("entries", []), key=lambda e: e["date"], reverse=True)
    items = []
    for e in entries:
        kind = "Weekly Rollup" if e["type"] == "weekly" else "Daily Brief"
        items.append(f"""
<a class="index-item" href="reports/{esc(e['filename'])}">
  <span class="idate">{esc(e['pretty_date'])}</span><span class="itype">{esc(kind)}</span>
  <div class="itake">{e.get('quick_take','')}</div>
</a>""")
    body = f"""
<div class="masthead">
  <h1>Podcast Signal Briefs</h1>
  <div class="meta">Auto-updated every couple of days &middot; lens: {esc(BUSINESS_LENS)}</div>
</div>
<div class="index-list">
{''.join(items) if items else '<p style="color:#6b7280">No briefs published yet.</p>'}
</div>"""
    return page_shell("Podcast Signal Briefs", body)


# ── publish ────────────────────────────────────────────────────────────────

def publish():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    manifest = load_manifest()
    known = {e["filename"] for e in manifest["entries"]}

    daily = load_json(SIGNALS_FILE)
    if daily and daily.get("generated"):
        date_str = daily["generated"][:10]
        filename = f"{date_str}.html"
        with open(os.path.join(REPORTS_DIR, filename), "w", encoding="utf-8") as f:
            f.write(render_daily(daily))
        if filename not in known:
            try:
                pretty = datetime.fromisoformat(daily["generated"]).strftime("%b %d, %Y")
            except Exception:
                pretty = date_str
            manifest["entries"].append({
                "type": "daily", "date": date_str, "pretty_date": pretty,
                "filename": filename, "quick_take": quick_take(daily.get("synthesis", "")),
            })
            known.add(filename)
        else:
            for e in manifest["entries"]:
                if e["filename"] == filename:
                    e["quick_take"] = quick_take(daily.get("synthesis", ""))

    for path in sorted(glob.glob(WEEKLY_GLOB)):
        weekly = load_json(path)
        if not weekly:
            continue
        date_str = (weekly.get("week_ending") or weekly.get("generated") or "")[:10]
        if not date_str:
            continue
        filename = f"weekly-{date_str}.html"
        with open(os.path.join(REPORTS_DIR, filename), "w", encoding="utf-8") as f:
            f.write(render_weekly(weekly))
        if filename not in known:
            try:
                pretty = datetime.fromisoformat(date_str).strftime("%b %d, %Y")
            except Exception:
                pretty = date_str
            manifest["entries"].append({
                "type": "weekly", "date": date_str, "pretty_date": pretty,
                "filename": filename, "quick_take": quick_take(weekly.get("synthesis", "")),
            })

    save_manifest(manifest)
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_index(manifest))

    print(f"[publish_dashboard] wrote {len(manifest['entries'])} report page(s) to {DOCS_DIR}")
    _git_publish()


def _git_publish():
    """Best-effort commit + push. Silently no-ops until the one-time GitHub
    setup (see SETUP.md) has been done -- never raises, never blocks the
    caller (the daily scan / weekly rollup must still succeed either way)."""
    try:
        if not os.path.isdir(os.path.join(SITE_DIR, ".git")):
            print("[publish_dashboard] site folder isn't a git repo yet -- "
                  "see SETUP.md to publish it. Local HTML is up to date.")
            return
        run = lambda *a: subprocess.run(a, cwd=SITE_DIR, capture_output=True, text=True)
        run("git", "add", "-A")
        diff = run("git", "diff", "--cached", "--quiet")
        if diff.returncode == 0:
            print("[publish_dashboard] no changes to publish.")
            return
        msg = f"Update briefs {datetime.now():%Y-%m-%d %H:%M}"
        run("git", "commit", "-m", msg)
        push = run("git", "push")
        if push.returncode == 0:
            print("[publish_dashboard] pushed update to GitHub Pages.")
        else:
            print(f"[publish_dashboard] git push failed (will retry next run): {push.stderr.strip()[:300]}")
    except Exception as e:
        print(f"[publish_dashboard] publish step skipped due to error: {e}")


if __name__ == "__main__":
    publish()
