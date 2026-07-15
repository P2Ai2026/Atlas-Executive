"""
PODCAST SIGNAL SCANNER -- daily listening + quantitative through-lines
======================================================================
Same LangGraph shape as before (named boxes wired with arrows, local Ollama
doing the thinking, deterministic routing), but rebuilt around one idea:

    Big change starts in the fringe and works its way to the mainstream.
    Find the signal in the fringe BEFORE it becomes consensus.

What changed vs. the old weekly agent:
    - Runs DAILY. Picks up any episode published in the last LOOKBACK_DAYS
      that it hasn't already processed (a history file remembers).
    - Every episode gets mined for SIGNALS: a curated power/AI-infra term
      watchlist (SMR, linear generators, gas turbines, HVAC, interconnection...)
      plus entities the model spots. Counts are done IN CODE on the raw
      transcript, not by the model -- the numbers are real, not vibes.
    - Signals accumulate in signal_history.json. Each run compares the last
      7 days against the prior 21-day baseline:
          velocity  = this week's mentions vs. the weekly baseline average
          breadth   = how many DIFFERENT shows said it this week
      and classifies each term:
          NEW                first time it's ever appeared
          FRINGE RISING      spiking hard but only 1-2 shows -- the early warning
          EMERGING           rising AND spreading across shows
          MAINSTREAM         everyone's saying it -- you're late, act or skip
    - The synthesis is written for the boss's three questions:
          A) WHERE IS THE CHANGE HAPPENING
          B) WHAT IT MEANS FOR OUR BUSINESS
          C) HOW TO ACT ON IT
    - Output: a PDF brief (as before) PLUS signals_latest.json, which the
      Executive Assistant app reads for its daily Signal Radar tab.

    START -> fetch -> transcribe -> summarize -> analyze -> signals -> synthesize -> report -> END

The "Bible in a Year" feed still rides in its own lane, devotional note only,
never business-framed.

GUARDRAILS (unchanged): local model, token budget + MAX_ITERATIONS cap,
deterministic routing, and HITL -- the agent only OPENS a Mail draft, it
never ever sends. (House rule: AppleScript may save, never send.)

Run it with:
    python podcast_intel_agent.py
"""

import os
import re
import sys
import json
import time
import math
import shutil
import hashlib
import subprocess
from typing import TypedDict, Optional
from datetime import datetime, timedelta, timezone

# --- self-setup: let the agent install a missing library on its own ---------
AUTO_INSTALL = True


def _ensure_package(import_name, pip_name=None):
    """Import a library; if it's missing and AUTO_INSTALL is on, pip-install it once."""
    pip_name = pip_name or import_name
    try:
        __import__(import_name)
        return True
    except ImportError:
        if not AUTO_INSTALL:
            return False
        print(f"[setup]      {pip_name} not found -- installing it once...")
        subprocess.run([sys.executable, "-m", "pip", "install", pip_name], check=False)
        try:
            __import__(import_name)
            return True
        except ImportError:
            return False


for _imp, _pip in [("requests", "requests"),
                   ("feedparser", "feedparser"),
                   ("langgraph", "langgraph")]:
    _ensure_package(_imp, _pip)

import requests
import feedparser
from langgraph.graph import StateGraph, START, END


# =====================================================================
# CONFIG  -- the only block you normally touch
# =====================================================================

# Your watchlist. `feed` is optional: leave it None and the agent resolves the
# RSS feed by name via Apple's lookup (now picks the best NAME MATCH from the
# top 5, not blindly the first result). PIN the exact URL once you trust it.
PODCASTS = [
    {"name": "All-In",                    "feed": None, "bible": False},
    {"name": "Acquired",                  "feed": None, "bible": False},
    {"name": "Invest Like the Best",      "feed": None, "bible": False},
    {"name": "Lex Fridman",               "feed": None, "bible": False},
    {"name": "Dwarkesh Patel",            "feed": None, "bible": False},
    {"name": "MIT Supply Chain",          "feed": None, "bible": False},
    {"name": "MIT Tech Review",           "feed": None, "bible": False},
    {"name": "Infrastructure Technology", "feed": None, "bible": False},
    {"name": "The Investors Podcast",     "feed": None, "bible": False},
    {"name": "Supply Chain Now",          "feed": None, "bible": False},
    {"name": "AI First Business",         "feed": None, "bible": False},
    # -- power & energy lane: the fringe where our early warnings live --
    {"name": "Catalyst with Shayle Kann", "feed": None, "bible": False},
    {"name": "The Interchange",           "feed": None, "bible": False},
    {"name": "Titans of Nuclear",         "feed": None, "bible": False},
    {"name": "Redefining Energy",         "feed": None, "bible": False},
    {"name": "Bible in a Year",           "feed": None, "bible": True},
]

BUSINESS_LENS = ("AI infrastructure and data-center development: chips, power "
                 "(SMRs, linear generators, gas turbines, grid), HVAC/cooling, "
                 "machinery, and construction")

# The curated signal watchlist. canonical name -> list of regex-safe phrases.
# Counting happens IN CODE on the transcript, so these numbers are exact.
# Add terms freely; keep phrases specific enough not to false-positive
# (e.g. "transformer" alone would collide with the neural-net kind).
WATCHLIST = {
    "SMR / small modular reactor": ["smr", "smrs", "small modular reactor", "small modular reactors"],
    "linear generator":            ["linear generator", "linear generators", "mainspring"],
    "gas turbine":                 ["gas turbine", "gas turbines", "combined cycle", "combustion turbine",
                                    "ge vernova", "peaker plant", "natural gas plant"],
    "nuclear power":               ["nuclear"],
    "geothermal":                  ["geothermal", "fervo"],
    "fuel cell":                   ["fuel cell", "fuel cells", "bloom energy"],
    "grid interconnection":        ["interconnection", "grid connection"],
    "behind-the-meter power":      ["behind the meter", "behind-the-meter", "off-grid power", "islanded power"],
    "power purchase agreement":    ["power purchase agreement", "power purchase agreements", "ppa", "ppas"],
    "transformer supply":          ["transformer shortage", "transformer lead time", "transformer lead times",
                                    "step-up transformer", "grid transformer", "transformer backlog"],
    "cooling / HVAC":              ["hvac", "liquid cooling", "liquid-cooled", "direct-to-chip",
                                    "immersion cooling", "chiller", "chillers", "cooling tower"],
    "power constraint":            ["power constraint", "power constrained", "power bottleneck",
                                    "energy bottleneck", "power is the constraint", "power availability"],
    "gigawatt-scale build":        ["gigawatt", "gigawatts", "gw of capacity"],
    "GPU supply":                  ["h100", "h200", "b200", "gb200", "blackwell", "rubin", "gpu shortage",
                                    "gpu supply"],
    "high-bandwidth memory":       ["hbm", "high bandwidth memory", "high-bandwidth memory"],
    "colocation":                  ["colocation", "co-location", "colo capacity"],
    "hyperscaler capex":           ["capex", "capital expenditure", "capital expenditures"],
    "grid / utilities":            ["utilities", "electric utility", "rate case", "grid capacity"],
    "data-center construction":    ["data center construction", "datacenter construction",
                                    "data center buildout", "data center build-out", "greenfield data center"],
    "energy storage":              ["battery storage", "grid storage", "bess", "energy storage"],
}

OLLAMA_MODEL   = "llama3"
LOOKBACK_DAYS  = 2             # daily run; 2-day window so nothing slips through
BASELINE_DAYS  = 21            # trailing baseline the current week is compared to
WINDOW_DAYS    = 7             # "current" window for velocity/breadth math

TRANSCRIPT_MODE   = "auto"     # feed transcript if present, else local Whisper
WHISPER_MODEL     = "base"
MAX_AUDIO_MINUTES = 150

APPROX_CHARS_PER_TOKEN = 4
CHUNK_TOKENS     = 2500
MAX_ITERATIONS   = 5
RUN_TOKEN_BUDGET = 400_000

EMAIL_TO = "your.email@example.com"   # set this to enable the Mail DRAFT step

# Output location. The Electron app passes PODCAST_OUTPUT_DIR when it spawns
# this script; the Desktop default keeps standalone runs working.
OUTPUT_DIR   = os.environ.get("PODCAST_OUTPUT_DIR") \
               or os.path.expanduser("~/Desktop/Agent 3- Podcast Reviews")
CACHE_DIR    = os.path.join(OUTPUT_DIR, ".transcript_cache")
HISTORY_FILE = os.path.join(OUTPUT_DIR, "signal_history.json")
SIGNALS_FILE = os.path.join(OUTPUT_DIR, "signals_latest.json")
FEEDS_FILE   = os.path.join(OUTPUT_DIR, "feeds_cache.json")   # pinned RSS URLs
PREDICTIONS_FILE = os.path.join(OUTPUT_DIR, "predictions.json")  # track record (NEW)
PREDICTION_CHECK_DAYS = 45   # how long a prediction rides before we score it


# =====================================================================
# SMALL HELPERS
# =====================================================================

def approx_tokens(text: str) -> int:
    return max(1, len(text) // APPROX_CHARS_PER_TOKEN)


def chunk_text(text: str, chunk_tokens: int = CHUNK_TOKENS) -> list:
    size = chunk_tokens * APPROX_CHARS_PER_TOKEN
    words = text.split()
    chunks, buf, count = [], [], 0
    for w in words:
        buf.append(w)
        count += len(w) + 1
        if count >= size:
            chunks.append(" ".join(buf))
            buf, count = [], 0
    if buf:
        chunks.append(" ".join(buf))
    return chunks or [""]


def itunes_lookup(name: str) -> Optional[str]:
    """Resolve podcast NAME -> RSS feed URL. Picks the best name match from the
    top 5 results instead of trusting result #1 (which grabbed clones before)."""
    try:
        r = requests.get(
            "https://itunes.apple.com/search",
            params={"term": name, "media": "podcast", "limit": 5},
            timeout=15,
        )
        results = r.json().get("results", [])
        if not results:
            return None
        want = name.lower()
        def score(res):
            got = (res.get("collectionName") or "").lower()
            if got == want:            return 3
            if want in got:            return 2
            if got and got in want:    return 1
            return 0
        best = max(results, key=score)
        return best.get("feedUrl")
    except Exception as e:
        print(f"            ! feed lookup failed for {name!r}: {e}")
        return None


def _entry_datetime(entry) -> Optional[datetime]:
    t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not t:
        return None
    return datetime(*t[:6], tzinfo=timezone.utc)


def recent_episodes(feed_url: str, lookback_days: int) -> list:
    """Return ALL episodes published within the lookback window (newest first).
    Daily runs can catch two drops from the same show; we want both."""
    parsed = feedparser.parse(feed_url)
    if not parsed.entries:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    out = []
    for entry in parsed.entries[:10]:
        when = _entry_datetime(entry)
        if not when or when < cutoff:
            continue
        audio_url, transcript_url = None, None
        for enc in getattr(entry, "enclosures", []):
            if "audio" in enc.get("type", ""):
                audio_url = enc.get("href")
        for link in getattr(entry, "links", []):
            if "transcript" in (link.get("rel", "") + link.get("type", "")).lower():
                transcript_url = link.get("href")
        if not transcript_url:
            tr = entry.get("podcast_transcript") or entry.get("transcript")
            if isinstance(tr, dict):
                transcript_url = tr.get("url") or tr.get("href")
        out.append({
            "title": entry.get("title", "Untitled"),
            "published": when.strftime("%Y-%m-%d"),
            "audio_url": audio_url,
            "transcript_url": transcript_url,
        })
    out.sort(key=lambda e: e["published"], reverse=True)
    return out


def episode_id(ep) -> str:
    """Stable ID for an episode -- used for the cache AND the history dedupe."""
    return hashlib.md5(
        ((ep.get("audio_url") or "") + (ep.get("title") or "")
         + (ep.get("published") or "")).encode()).hexdigest()


# =====================================================================
# THE LOCAL MODEL  (token budget shared across the run)
# =====================================================================

class Budget:
    def __init__(self, ceiling):
        self.ceiling = ceiling
        self.spent = 0
    def add(self, n):
        self.spent += n
    @property
    def over(self):
        return self.spent >= self.ceiling


BUDGET = Budget(RUN_TOKEN_BUDGET)
_LLM = None

OLLAMA_URL = "http://localhost:11434"


def ensure_ollama(model=OLLAMA_MODEL, wait_seconds=30):
    if _ollama_up():
        print("[ollama]     server already running.")
    else:
        print("[ollama]     not running -- starting it for you...")
        _start_ollama()
        for _ in range(wait_seconds):
            if _ollama_up():
                break
            time.sleep(1)
        if not _ollama_up():
            raise RuntimeError(
                "Couldn't start Ollama automatically. Open the Ollama app once, "
                "then re-run. (Install it from https://ollama.com/download if needed.)")
        print("[ollama]     server is up.")
    _ensure_model(model)
    # A wedged Ollama answers /api/tags but never generates -- demand proof of
    # life with a real (tiny) generation, and restart the app once if it fails.
    if not _ollama_generates(model):
        print("[ollama]     server answers but will not generate -- restarting it...")
        subprocess.run(["osascript", "-e", 'quit app "Ollama"'], check=False)
        time.sleep(3)
        subprocess.run(["pkill", "-f", "llama-server"], check=False)
        time.sleep(2)
        _start_ollama()
        for _ in range(wait_seconds):
            if _ollama_up():
                break
            time.sleep(1)
        if not _ollama_generates(model):
            raise RuntimeError("Ollama will not generate even after a restart -- "
                               "open the Ollama app manually and check it.")
        print("[ollama]     healthy after restart.")


def _ollama_generates(model, timeout=90) -> bool:
    """True only if the model actually produces tokens, not just answers pings."""
    try:
        r = requests.post(f"{OLLAMA_URL}/api/chat", json={
            "model": model, "stream": False,
            "messages": [{"role": "user", "content": "Say OK"}],
        }, timeout=(5, timeout))
        return bool((r.json().get("message") or {}).get("content"))
    except Exception:
        return False


def _ollama_up() -> bool:
    try:
        return requests.get(f"{OLLAMA_URL}/api/tags", timeout=2).status_code == 200
    except Exception:
        return False


def _start_ollama():
    have_cli = shutil.which("ollama") is not None
    have_app = os.path.exists("/Applications/Ollama.app")
    if not have_cli and not have_app:
        raise RuntimeError(
            "Ollama isn't installed. Download it from https://ollama.com/download")
    try:
        if have_app:
            subprocess.Popen(["open", "-a", "Ollama"])
        else:
            subprocess.Popen(["ollama", "serve"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        raise RuntimeError(f"Failed to launch Ollama: {e}")


def _ensure_model(model):
    try:
        data = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5).json()
        have = {m["name"].split(":")[0] for m in data.get("models", [])}
        if model.split(":")[0] in have:
            return
        print(f"[ollama]     model '{model}' not found -- pulling it once...")
        subprocess.run(["ollama", "pull", model], check=False)
    except Exception as e:
        print(f"[ollama]     couldn't verify model ({e}); continuing anyway.")


def _get_llm():
    global _LLM
    if _LLM is None:
        _ensure_package("langchain_ollama", "langchain-ollama")
        from langchain_ollama import ChatOllama
        _LLM = ChatOllama(model=OLLAMA_MODEL, temperature=0.2)
    return _LLM


def llm_call(system: str, user: str) -> str:
    """One model call over plain HTTP with a HARD read timeout and one retry.
    (The old langchain path had no timeout -- a wedged Ollama response blocked
    the whole run forever. A local model that hasn't answered in 10 minutes
    isn't going to.)"""
    if BUDGET.over:
        return "[skipped: run token budget exhausted]"
    BUDGET.add(approx_tokens(system) + approx_tokens(user))
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "options": {"temperature": 0.2},
    }
    last_err = None
    for attempt in (1, 2):
        try:
            r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload,
                              timeout=(10, 600))
            r.raise_for_status()
            out = (r.json().get("message") or {}).get("content", "")
            BUDGET.add(approx_tokens(out))
            return out.strip()
        except Exception as e:
            last_err = e
            print(f"             ! model call failed (attempt {attempt}): {e}")
            time.sleep(5)
    return f"[model error: {last_err}]"


def summarize_long(text: str, what: str) -> str:
    """Map-reduce with the hard MAX_ITERATIONS escape hatch (unchanged)."""
    chunks = chunk_text(text)
    notes = []
    for i, ch in enumerate(chunks, 1):
        notes.append(llm_call(
            "You are a precise note-taker. Summarize faithfully, no fluff.",
            f"Part {i}/{len(chunks)} of {what}. Summarize the key points:\n\n{ch}",
        ))
    BATCH = 4
    iterations = 0
    while len(notes) > 1 and iterations < MAX_ITERATIONS:
        iterations += 1
        folded = []
        for i in range(0, len(notes), BATCH):
            group = "\n\n".join(notes[i:i + BATCH])
            folded.append(llm_call(
                "You merge notes into one tighter set. Keep every distinct point.",
                f"Combine these notes from {what} into one coherent summary:\n\n{group}",
            ))
        notes = folded
    if len(notes) > 1:
        print(f"             ! reduce hit MAX_ITERATIONS={MAX_ITERATIONS}; forcing final merge")
        notes = [llm_call(
            "You merge notes into one tighter set. Keep every distinct point.",
            f"Combine these notes from {what}:\n\n" + "\n\n".join(notes),
        )]
    return notes[0]


# =====================================================================
# SIGNAL ENGINE  -- the new core. Counting in code; the model only nominates.
# =====================================================================

def load_history() -> dict:
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"episodes": []}


def save_history(history: dict):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=1)


def count_phrases(transcript: str, phrases: list) -> int:
    """Exact, case-insensitive, word-boundary counts. Code counts, not the model."""
    text = transcript.lower()
    total = 0
    for p in phrases:
        total += len(re.findall(r"\b" + re.escape(p.lower()) + r"\b", text))
    return total


def extract_entities(summary: str) -> list:
    """The model NOMINATES entities worth tracking; the counting still happens
    in code against the raw transcript. Bad nominations count to zero and drop out."""
    out = llm_call(
        "You extract trackable market entities from podcast notes. "
        "Output ONLY a plain list, one entity per line, no numbering, no commentary. "
        "Entities = specific companies, technologies, products, or projects relevant to "
        "AI infrastructure, energy/power, semiconductors, data centers, industrial "
        "supply chains, or major tech/finance players. "
        "EXCLUDE consumer/lifestyle topics (restaurants, hotels, travel, yachts, sports), "
        "generic nouns, podcast segment names, and people's first names alone.",
        f"List up to 12 specific companies/technologies/products mentioned here:\n\n{summary[:6000]}",
    )
    entities = []
    for line in out.split("\n"):
        name = re.sub(r"^[\s\-\*\d\.\)]+", "", line).strip().strip(".")
        if 2 < len(name) <= 40 and not name.startswith("["):
            entities.append(name)
    return entities[:12]


def mine_episode_terms(ep) -> dict:
    """One dict of {term: exact_count} per episode: watchlist + nominated entities."""
    transcript = ep.get("transcript") or ""
    if not transcript or transcript.startswith("["):
        return {}
    terms = {}
    for canon, phrases in WATCHLIST.items():
        n = count_phrases(transcript, phrases)
        if n:
            terms[canon] = n
    for ent in ep.get("entities", []):
        key = ent.lower()
        if key in (c.lower() for c in WATCHLIST):
            continue
        n = count_phrases(transcript, [ent])
        if n >= 2:                      # one stray mention isn't a signal
            terms[key] = max(terms.get(key, 0), n)
    return terms


def gate_terms(history: dict):
    """Relevance gate over every term ever mined. Watchlist terms auto-keep;
    model-nominated terms get ONE keep/drop verdict, cached in the history file,
    applied retroactively — so junk ('restaurants', 'yachts') vanishes from the
    radar without touching the underlying counts."""
    verdicts = history.setdefault("term_verdicts", {})
    for canon in WATCHLIST:
        verdicts[canon] = "keep"
    all_terms = set()
    for e in history["episodes"]:
        all_terms.update(e.get("terms", {}))
    pending = sorted(t for t in all_terms if t not in verdicts)
    if not pending:
        return
    out = llm_call(
        "You are a strict market-signal curator for an AI-/data-center-infrastructure "
        "business. For EACH term, answer whether it is worth tracking as a market signal. "
        "keep = specific company, technology, product, or industry topic relevant to AI, "
        "energy/power, chips, data centers, industrial supply chains, or capital markets. "
        "drop = consumer/lifestyle topic, generic noun, podcast segment name, or vague phrase. "
        "Output one line per term, EXACTLY in the format: term | keep  OR  term | drop. "
        "No commentary.",
        "Terms:\n" + "\n".join(pending),
    )
    parsed = {}
    for line in out.split("\n"):
        m = re.match(r"^\s*(.+?)\s*\|\s*(keep|drop)\s*$", line.strip(), re.I)
        if m:
            parsed[m.group(1).strip().lower()] = m.group(2).lower()
    for t in pending:
        # default keep: better a stray term on the radar than a lost real signal
        verdicts[t] = parsed.get(t.lower(), "keep")
    dropped = [t for t in pending if verdicts[t] == "drop"]
    if dropped:
        print(f"             gate dropped: {', '.join(dropped[:8])}"
              + (" …" if len(dropped) > 8 else ""))


def update_history(history: dict, episodes: list):
    """Append newly processed episodes; dedupe on episode id."""
    known = {e["id"] for e in history["episodes"]}
    for ep in episodes:
        eid = episode_id(ep)
        if eid in known:
            continue
        history["episodes"].append({
            "id": eid,
            "date": ep.get("published") or datetime.now().strftime("%Y-%m-%d"),
            "podcast": ep.get("podcast", ""),
            "title": ep.get("title", ""),
            "relevance": ep.get("relevance", "N/A"),
            "terms": ep.get("term_counts", {}),
        })
    # keep 6 months of history; plenty for baselines, file stays small
    cutoff = (datetime.now() - timedelta(days=183)).strftime("%Y-%m-%d")
    history["episodes"] = [e for e in history["episodes"] if e["date"] >= cutoff]


def compute_signals(history: dict) -> list:
    """The quantitative through-line: current 7-day window vs. prior 21-day
    baseline. Velocity = how fast a term is accelerating. Breadth = how many
    different shows said it. Fringe = high velocity + low breadth."""
    today = datetime.now()
    cur_start  = (today - timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%d")
    base_start = (today - timedelta(days=WINDOW_DAYS + BASELINE_DAYS)).strftime("%Y-%m-%d")

    verdicts = history.get("term_verdicts", {})
    cur, base = {}, {}   # term -> {"count": n, "shows": set}
    for e in history["episodes"]:
        bucket = cur if e["date"] >= cur_start else (base if e["date"] >= base_start else None)
        if bucket is None:
            continue
        for term, n in e.get("terms", {}).items():
            if verdicts.get(term) == "drop":
                continue
            slot = bucket.setdefault(term, {"count": 0, "shows": set()})
            slot["count"] += n
            slot["shows"].add(e["podcast"])

    baseline_weeks = BASELINE_DAYS / 7.0
    signals = []
    for term, c in cur.items():
        b = base.get(term, {"count": 0, "shows": set()})
        base_weekly = b["count"] / baseline_weeks
        velocity = c["count"] / max(base_weekly, 0.5)
        breadth = len(c["shows"])
        if b["count"] == 0 and c["count"] >= 8:
            status = "FRINGE RISING"        # never seen before, suddenly loud
        elif b["count"] == 0:
            status = "NEW"
        elif velocity >= 3 and breadth <= 2:
            status = "FRINGE RISING"        # spiking hard, still only 1-2 shows
        elif velocity >= 1.5 and breadth >= 4:
            status = "GOING MAINSTREAM"     # the fringe->mainstream move, live
        elif velocity >= 1.5 and breadth >= 3:
            status = "EMERGING"
        elif breadth >= 4:
            status = "MAINSTREAM"
        elif velocity >= 1.5:
            status = "RISING"
        else:
            status = "STEADY"
        score = velocity * math.log(1 + c["count"]) * (1 + 0.3 * breadth)
        signals.append({
            "term": term,
            "current": c["count"],
            "baseline_weekly": round(base_weekly, 1),
            # velocity vs. a zero baseline is an artifact, not a measurement —
            # report null for brand-new terms and let the status badge speak
            "velocity": None if b["count"] == 0 else round(velocity, 1),
            "breadth": breadth,
            "shows": sorted(c["shows"]),
            "status": status,
            "score": round(score, 2),
        })
    signals.sort(key=lambda s: s["score"], reverse=True)
    return signals


def signals_table_text(signals: list, top: int = 15) -> str:
    """Plain-text stats table fed to the synthesis prompt, so the model reasons
    FROM the numbers instead of inventing its own."""
    lines = ["TERM | THIS WEEK | BASELINE/WK | VELOCITY | # SHOWS | STATUS"]
    for s in signals[:top]:
        vel = "new (no baseline yet)" if s["velocity"] is None else f"{s['velocity']}x"
        lines.append(f"{s['term']} | {s['current']} | {s['baseline_weekly']} | "
                     f"{vel} | {s['breadth']} ({', '.join(s['shows'])}) | {s['status']}")
    return "\n".join(lines)


# =====================================================================
# THE STATE that flows through the graph
# =====================================================================

class PodState(TypedDict):
    episodes: list          # business podcasts, enriched at each node
    bible: Optional[dict]   # the devotional episode, separate lane
    signals: list           # computed cross-run signal stats
    opportunities: list     # signal -> exposure/bull/bear mapping
    track_record: dict      # scoreboard across all resolved predictions (NEW)
    newly_resolved: list    # predictions scored just this run (NEW)
    synthesis: str          # the A/B/C brief
    red_team: str           # contrarian stress-test of the brief
    pdf_path: str


# =====================================================================
# NODES
# =====================================================================

def load_feed_cache() -> dict:
    try:
        with open(FEEDS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def effective_lookback(history) -> int:
    """Catch-up logic: if the scanner missed days (laptop closed, app not
    running), widen the window back to the last processed episode so nothing
    is lost forever. Capped at 7 days to keep a catch-up run bounded."""
    try:
        newest = max(e["date"] for e in history["episodes"])
        gap = (datetime.now() - datetime.strptime(newest, "%Y-%m-%d")).days + 1
        return min(7, max(LOOKBACK_DAYS, gap))
    except ValueError:
        return 7   # empty history -- first run pulls a full week


def fetch_node(state):
    history = load_history()
    seen = {e["id"] for e in history["episodes"]}
    lookback = effective_lookback(history)
    print(f"[fetch]      finding new episodes (window: last {lookback} days)...")
    # Pin resolved RSS URLs: look each show up ONCE, then reuse the cached URL
    # every day after — faster, and immune to the lookup grabbing a clone feed.
    # To force a re-lookup (e.g. a show moves hosts), delete its line from
    # feeds_cache.json in the output folder.
    feed_cache = load_feed_cache()
    cache_dirty = False
    episodes, bible = [], None
    for pod in PODCASTS:
        feed = pod["feed"] or feed_cache.get(pod["name"])
        if not feed:
            feed = itunes_lookup(pod["name"])
            if feed:
                feed_cache[pod["name"]] = feed
                cache_dirty = True
        if not feed:
            print(f"             - {pod['name']}: no feed found, skipping")
            continue
        eps = recent_episodes(feed, lookback)
        fresh = [e for e in eps if episode_id(e) not in seen]
        if not fresh:
            print(f"             - {pod['name']}: nothing new")
            continue
        for ep in fresh:
            ep["podcast"] = pod["name"]
            ep["is_bible"] = pod["bible"]
            print(f"             + {pod['name']}: {ep['title'][:60]}")
            if pod["bible"]:
                bible = ep
            else:
                episodes.append(ep)
        time.sleep(0.2)
    if cache_dirty:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(FEEDS_FILE, "w", encoding="utf-8") as f:
            json.dump(feed_cache, f, indent=1)
    return {"episodes": episodes, "bible": bible}


def transcribe_node(state):
    print("[transcribe] getting the words...")
    every = state["episodes"] + ([state["bible"]] if state["bible"] else [])
    for ep in every:
        ep["transcript"] = get_transcript(ep)
        ok = ep["transcript"] and not ep["transcript"].startswith("[")
        print(f"             {'ok ' if ok else '-- '}{ep['podcast']}")
    return {"episodes": state["episodes"], "bible": state["bible"]}


def summarize_node(state):
    print("[summarize]  AI writing per-episode summaries...")
    for ep in state["episodes"]:
        if not ep.get("transcript") or ep["transcript"].startswith("["):
            ep["summary"] = "[no transcript available]"
            continue
        ep["summary"] = summarize_long(ep["transcript"], f"the {ep['podcast']} episode")

    b = state["bible"]
    if b and b.get("transcript") and not b["transcript"].startswith("["):
        b["message"] = llm_call(
            "You write a short, warm devotional note. Plain, reverent, 4-6 sentences.",
            f"From this 'Bible in a Year' episode ({b['title']}), give this week's "
            f"main spiritual message and one line to sit with:\n\n{b['transcript'][:8000]}",
        )
    elif b:
        b["message"] = "[no transcript available]"
    return {"episodes": state["episodes"], "bible": state["bible"]}


def analyze_node(state):
    print("[analyze]    scoring each through our business lens...")
    for ep in state["episodes"]:
        if ep["summary"].startswith("["):
            ep["analysis"] = ep["summary"]
            ep["relevance"] = "N/A"
            continue
        out = llm_call(
            "You are a sharp business analyst. Be concrete and skeptical. "
            "No hype; name the so-what and the holes.",
            f"Our business: {BUSINESS_LENS}.\n\n"
            f"Episode summary ({ep['podcast']} -- {ep['title']}):\n{ep['summary']}\n\n"
            "Respond in three short labelled parts:\n"
            "RELEVANCE: one of HIGH / MEDIUM / LOW for our business, plus 1 line why.\n"
            "SIGNAL: 2-4 bullets of what actually matters to us here.\n"
            "CRITIQUE: 1-2 bullets -- what's overstated, missing, or worth doubting.",
        )
        ep["analysis"] = out
        m = re.search(r"RELEVANCE:\s*(HIGH|MEDIUM|LOW)", out, re.I)
        ep["relevance"] = m.group(1).upper() if m else "MEDIUM"
    return {"episodes": state["episodes"], "bible": state["bible"]}


def signals_node(state):
    """Mine terms from today's episodes, fold into history, recompute stats.
    Runs even when there are NO new episodes -- the rolling window still moves,
    so the daily radar stays honest."""
    print("[signals]    mining terms + computing velocity/breadth...")
    for ep in state["episodes"]:
        if ep.get("summary") and not ep["summary"].startswith("["):
            ep["entities"] = extract_entities(ep["summary"])
        else:
            ep["entities"] = []
        ep["term_counts"] = mine_episode_terms(ep)
        if ep["term_counts"]:
            top3 = sorted(ep["term_counts"].items(), key=lambda kv: -kv[1])[:3]
            print(f"             {ep['podcast']}: " +
                  ", ".join(f"{t}({n})" for t, n in top3))

    history = load_history()
    update_history(history, state["episodes"])
    gate_terms(history)
    save_history(history)
    signals = compute_signals(history)
    return {"signals": signals}


# =====================================================================
# OPPORTUNITY MAPPING -- signal -> investable exposure (NEW)
# =====================================================================
# IMPORTANT: this node maps signals to companies with a bull case, bear
# case, and a falsifiable trigger. It does NOT output "buy" / "sell"
# directives -- that's a deliberate choice, not a limitation. A brief that
# shows its reasoning and where it could be wrong is more useful to an
# executive (and more honest) than a black-box recommendation would be.

OPPORTUNITY_STATUSES = ("FRINGE RISING", "NEW", "GOING MAINSTREAM", "EMERGING")
MAX_OPPORTUNITIES = 5


def opportunity_node(state):
    print("[opportunity] mapping top signals to investable exposure...")
    signals = state.get("signals", [])
    top = [s for s in signals if s["status"] in OPPORTUNITY_STATUSES][:MAX_OPPORTUNITIES]
    if not top:
        return {"opportunities": []}

    opportunities = []
    for s in top:
        vel_text = "new (no baseline)" if s["velocity"] is None else f"{s['velocity']}x"
        out = llm_call(
            "You are a skeptical equity research analyst working for an internal "
            "strategy team. You do NOT give buy/sell directives or personalized "
            "investment advice -- you map a market signal to PUBLIC companies with "
            "real exposure, then lay out the bull case, the bear case, and a "
            "concrete falsifiable trigger. Do NOT invent specific factual claims "
            "about a company (which cloud vendor it uses, which specific product "
            "depends on which) unless you are highly confident it is accurate. "
            "Tag every company in EXPOSURE as [CONFIRMED] only if the connection "
            "is a well-known, verifiable fact, or [LIKELY] if you are inferring a "
            "plausible but unverified connection. If you are not confident a "
            "company has real, direct exposure at all, say so explicitly instead "
            "of guessing or padding the list.",
            f"Signal: {s['term']} -- status: {s['status']}, velocity: {vel_text}, "
            f"mentioned on {s['breadth']} show(s) this week ({', '.join(s['shows'])}).\n\n"
            "Respond in exactly these four labelled parts:\n"
            "EXPOSURE: 2-4 public companies/tickers with real, direct exposure to "
            "this signal, each tagged [CONFIRMED] or [LIKELY] per the rule above "
            "(write 'no clear public exposure' if none fit).\n"
            "BULL CASE: why this signal, if it keeps accelerating, benefits them.\n"
            "BEAR CASE: why this could stall out, reverse, or already be priced in.\n"
            "CONFIRM/KILL TRIGGER: one concrete, checkable thing -- a filing, an "
            "earnings line, a capacity announcement -- that would validate or "
            "invalidate this within 30-60 days.",
        )
        opportunities.append({
            "signal": s["term"],
            "status": s["status"],
            "velocity": s["velocity"],
            "breadth": s["breadth"],
            "analysis": out,
        })
    return {"opportunities": opportunities}


# =====================================================================
# RED TEAM -- contrarian stress-test of the finished brief (NEW)
# =====================================================================
# Runs AFTER synthesis. Its only job is to argue with the brief: which
# claims are thin, overconfident, or contradicted elsewhere. This is what
# "critique" means at the brief level (episode-level critique already
# happens in analyze_node) -- a second, adversarial pass over the
# conclusions rather than the raw material.

def stress_test(synthesis: str, opportunities: list) -> str:
    if not synthesis or synthesis.startswith("["):
        return "[skipped: no synthesis to stress-test]"
    opp_text = "\n\n".join(
        f"{o['signal']} ({o['status']}):\n{o['analysis']}" for o in opportunities
    ) or "(no opportunity mapping today)"
    return llm_call(
        "You are a skeptical devil's advocate reviewing an internal strategy brief "
        "before it goes to executives. Your only job is to find the weakest claims "
        "and say plainly why they might be wrong. Be specific -- name the claim, "
        "then the reason to doubt it. Do not soften with praise.",
        "Stress-test this brief. For each major claim, flag if it is "
        "overconfident, based on thin data (e.g. only 1-2 shows, brand-new "
        "signal with no baseline), or contradicted by anything else here. "
        "End with one line: is today's overall signal-to-noise HIGH, MEDIUM, "
        "or LOW confidence, and why.\n\n"
        f"SYNTHESIS:\n{synthesis}\n\nOPPORTUNITY MAPPING:\n{opp_text}",
    )


# =====================================================================
# PREDICTION TRACKING -- does the agent's own call-out hold up? (NEW)
# =====================================================================
# Every time opportunity_node flags a signal, that call gets logged with a
# check-back date. On a later run, once that date has passed, we look at
# what actually happened to the SAME signal in our own measured data
# (velocity/breadth) and score it: did the trend keep accelerating,
# broaden, or fade? Self-contained and quantitative -- no extra model
# call, no guessing. Over months this becomes a real track record.

def load_predictions() -> dict:
    try:
        with open(PREDICTIONS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"predictions": []}


def save_predictions(preds: dict):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(PREDICTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(preds, f, indent=1)


def record_new_predictions(preds: dict, opportunities: list):
    open_terms = {p["signal"] for p in preds["predictions"] if not p["resolved"]}
    today = datetime.now().strftime("%Y-%m-%d")
    check_after = (datetime.now() + timedelta(days=PREDICTION_CHECK_DAYS)).strftime("%Y-%m-%d")
    for o in opportunities:
        if o["signal"] in open_terms:
            continue
        preds["predictions"].append({
            "id": hashlib.md5(f"{o['signal']}-{today}".encode()).hexdigest()[:10],
            "date_created": today,
            "signal": o["signal"],
            "status_at_creation": o["status"],
            "velocity_at_creation": o["velocity"],
            "breadth_at_creation": o["breadth"],
            "analysis": o["analysis"],
            "check_after": check_after,
            "resolved": False,
            "verdict": None,
            "resolved_date": None,
            "resolution_note": None,
        })


def review_predictions(preds: dict, current_signals: list) -> list:
    today = datetime.now().strftime("%Y-%m-%d")
    by_term = {s["term"]: s for s in current_signals}
    newly_resolved = []
    for p in preds["predictions"]:
        if p["resolved"] or p["check_after"] > today:
            continue
        now = by_term.get(p["signal"])
        if now is None:
            verdict = "FADED"
            note = f"'{p['signal']}' dropped off the radar entirely -- no mentions in the current window."
        elif now["status"] in ("MAINSTREAM", "GOING MAINSTREAM"):
            verdict = "CONFIRMED"
            note = (f"'{p['signal']}' went mainstream: now mentioned on {now['breadth']} "
                    f"show(s), status {now['status']}.")
        else:
            old_v = p["velocity_at_creation"] or 0
            new_v = now["velocity"] or 0
            old_b = p["breadth_at_creation"] or 0
            new_b = now["breadth"]
            if new_v >= old_v and new_b >= old_b:
                verdict = "CONTINUED"
                note = (f"'{p['signal']}' kept accelerating: velocity {old_v}x -> {new_v}x, "
                        f"breadth {old_b} -> {new_b} shows.")
            elif new_b > old_b:
                verdict = "BROADENING"
                note = (f"'{p['signal']}' spread to more shows ({old_b} -> {new_b}) but "
                        f"velocity cooled ({old_v}x -> {new_v}x).")
            else:
                verdict = "STALLED"
                note = (f"'{p['signal']}' cooled off: velocity {old_v}x -> {new_v}x, "
                        f"breadth {old_b} -> {new_b} shows.")
        p["resolved"] = True
        p["verdict"] = verdict
        p["resolved_date"] = today
        p["resolution_note"] = note
        newly_resolved.append(p)
    return newly_resolved


def track_record_summary(preds: dict) -> dict:
    resolved = [p for p in preds["predictions"] if p["resolved"]]
    if not resolved:
        return {"total": 0}
    counts = {}
    for p in resolved:
        counts[p["verdict"]] = counts.get(p["verdict"], 0) + 1
    held_up = counts.get("CONFIRMED", 0) + counts.get("CONTINUED", 0) + counts.get("BROADENING", 0)
    return {
        "total": len(resolved),
        "counts": counts,
        "held_up_pct": round(100 * held_up / len(resolved)),
        "pending": len([p for p in preds["predictions"] if not p["resolved"]]),
    }


def predictions_node(state):
    print("[predictions] scoring past calls + logging today's...")
    signals = state.get("signals", [])
    opportunities = state.get("opportunities", [])
    preds = load_predictions()
    newly_resolved = review_predictions(preds, signals)
    if newly_resolved:
        for p in newly_resolved:
            print(f"             {p['verdict']:<10} {p['signal']} -- {p['resolution_note']}")
    record_new_predictions(preds, opportunities)
    save_predictions(preds)
    return {
        "track_record": track_record_summary(preds),
        "newly_resolved": newly_resolved,
    }


def synthesize_node(state):
    print("[synthesize] the A/B/C brief: where / what it means / how to act...")
    signals = state.get("signals", [])
    opportunities = state.get("opportunities", [])
    stats = signals_table_text(signals)
    usable = [e for e in state["episodes"] if not e.get("analysis", "[").startswith("[")]

    if not usable and not signals:
        return {"synthesis": "No new episodes and no active signals today.", "red_team": ""}

    episode_digest = "\n\n".join(
        f"## {e['podcast']} -- {e['title']} (relevance: {e['relevance']})\n{e['analysis']}"
        for e in usable
    ) or "(no new episodes today -- reason from the signal table alone)"
    if approx_tokens(episode_digest) > CHUNK_TOKENS * 2:
        episode_digest = summarize_long(episode_digest, "today's slate of episodes")

    opp_digest = "\n\n".join(
        f"## {o['signal']} ({o['status']})\n{o['analysis']}" for o in opportunities
    ) or "(no opportunity mapping today)"

    synthesis = llm_call(
        "You are a strategy analyst for an AI-/data-center-infrastructure company. "
        "Your job is early warning: change starts at the fringe and moves mainstream. "
        "Reason FROM the measured signal table and the opportunity mapping provided -- "
        "cite their numbers (mentions, velocity, show counts) and company names. Do not "
        "invent statistics or exposures that are not in the material given to you. You "
        "are producing analysis, not personalized investment advice -- never write "
        "'buy' or 'sell'; write what the signal implies and let the reader decide.",
        f"Our business: {BUSINESS_LENS}.\n\n"
        f"MEASURED SIGNALS (7-day window vs prior 3-week baseline):\n{stats}\n\n"
        f"OPPORTUNITY MAPPING (signal -> exposure/bull/bear/trigger):\n{opp_digest}\n\n"
        f"TODAY'S EPISODES:\n{episode_digest}\n\n"
        "Write a tight daily brief with EXACTLY these five sections:\n"
        "WHERE THE CHANGE IS HAPPENING: 2-4 bullets. Lead with FRINGE RISING and NEW "
        "signals -- the things only 1-2 shows are saying but saying loudly. Cite the numbers.\n"
        "WHAT IT MEANS FOR OUR BUSINESS: 2-4 bullets tying those signals to chips, power, "
        "HVAC, machinery, or data-center construction. Be concrete about which line of "
        "business is exposed or advantaged.\n"
        "INVESTABLE EXPOSURE: 1-2 sentences only, pointing to the detailed mapping "
        "below -- do NOT repeat company names, tickers, or bull/bear cases here, "
        "they are already covered in full further down this report. Just note "
        "how many signals had exposure mapped and name the single most notable one.\n"
        "HOW TO ACT: 2-4 specific, near-term moves (a call to make, a vendor to evaluate, "
        "a market to price, a hire to consider). No platitudes.\n"
        "WATCH NEXT: 1-3 signals to check tomorrow, with the threshold that would confirm them.",
    )

    print("[redteam]    stress-testing the brief...")
    red_team = stress_test(synthesis, opportunities)
    return {"synthesis": synthesis, "red_team": red_team}


def report_node(state):
    print("[report]     writing signals_latest.json + PDF...")
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "N/A": 3}
    eps = sorted(state["episodes"], key=lambda e: order.get(e.get("relevance"), 3))
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1) JSON for the Executive Assistant app -- written EVERY run
    payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "window_days": WINDOW_DAYS,
        "baseline_days": BASELINE_DAYS,
        "new_episodes": [
            {"podcast": e["podcast"], "title": e["title"],
             "published": e["published"], "relevance": e.get("relevance", "N/A")}
            for e in eps
        ],
        "signals": [{k: v for k, v in s.items() if k != "score"}
                    for s in state.get("signals", [])[:25]],
        "opportunities": state.get("opportunities", []),
        "track_record": state.get("track_record", {}),
        "synthesis": state.get("synthesis", ""),
        "red_team": state.get("red_team", ""),
    }
    with open(SIGNALS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1)

    # 2) PDF -- only when there's something new to read
    if not eps:
        print("             no new episodes -- JSON updated, skipping PDF.")
        return {"episodes": eps, "pdf_path": ""}

    pdf_name = f"podcast_brief_{datetime.now().strftime('%Y%m%d')}.pdf"
    pdf_path = os.path.join(OUTPUT_DIR, pdf_name)
    render_pdf(state.get("synthesis", ""), eps, state["bible"],
               state.get("signals", []), state.get("opportunities", []),
               state.get("red_team", ""), state.get("track_record", {}),
               state.get("newly_resolved", []), pdf_path)
    return {"episodes": eps, "pdf_path": pdf_path}


# =====================================================================
# TRANSCRIPT ACQUISITION (unchanged)
# =====================================================================

def get_transcript(ep) -> str:
    key = episode_id(ep)
    path = os.path.join(CACHE_DIR, key + ".txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    text = _get_transcript_raw(ep)
    if text and not text.startswith("["):
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return text


def _get_transcript_raw(ep) -> str:
    if TRANSCRIPT_MODE in ("feed", "auto") and ep.get("transcript_url"):
        text = _fetch_transcript_url(ep["transcript_url"])
        if text:
            return text
        if TRANSCRIPT_MODE == "feed":
            return "[no transcript in feed]"
    if TRANSCRIPT_MODE == "feed":
        return "[no transcript in feed]"
    if not ep.get("audio_url"):
        return "[no audio to transcribe]"
    return _whisper_transcribe(ep["audio_url"])


def _fetch_transcript_url(url: str) -> str:
    try:
        r = requests.get(url, timeout=30)
        body = r.text
        if "vtt" in url.lower() or body.lstrip().startswith("WEBVTT"):
            return _strip_vtt(body)
        if url.lower().endswith(".srt"):
            return _strip_vtt(body)
        if url.lower().endswith(".json"):
            data = json.loads(body)
            segs = data if isinstance(data, list) else data.get("segments", [])
            return " ".join(s.get("body") or s.get("text", "") for s in segs)
        return re.sub(r"<[^>]+>", " ", body)
    except Exception:
        return ""


def _strip_vtt(body: str) -> str:
    lines = []
    for ln in body.splitlines():
        ln = ln.strip()
        if not ln or ln == "WEBVTT" or "-->" in ln or ln.isdigit():
            continue
        lines.append(re.sub(r"<[^>]+>", "", ln))
    return " ".join(lines)


_WHISPER = None

def _get_whisper():
    """Load the Whisper model ONCE per run, preferring the local cache so no
    network call happens at all. (Constructing it per episode re-checked
    HuggingFace each time — one hung socket froze a whole scan for hours.)"""
    global _WHISPER
    if _WHISPER is None:
        from faster_whisper import WhisperModel
        try:
            _WHISPER = WhisperModel(WHISPER_MODEL, compute_type="int8",
                                    local_files_only=True)
        except Exception:
            # first ever run: model not downloaded yet -- allow one network fetch
            _WHISPER = WhisperModel(WHISPER_MODEL, compute_type="int8")
    return _WHISPER


class _StallGuard:
    """Hard wall-clock ceiling on a block of work, via SIGALRM. Whatever
    stalls inside — a socket, a decoder, a library bug — the run moves on."""
    def __init__(self, seconds):
        self.seconds = seconds
    def __enter__(self):
        import signal
        signal.signal(signal.SIGALRM,
                      lambda *_: (_ for _ in ()).throw(TimeoutError("stall guard tripped")))
        signal.alarm(self.seconds)
    def __exit__(self, *args):
        import signal
        signal.alarm(0)


def _whisper_transcribe(audio_url: str) -> str:
    if not _ensure_package("faster_whisper", "faster-whisper"):
        return "[whisper unavailable: set AUTO_INSTALL=True or pip install faster-whisper]"
    try:
        with _StallGuard(60 * 60):   # no single episode may take over an hour
            tmp = "/tmp/_episode_audio"
            with requests.get(audio_url, stream=True, timeout=(15, 120)) as r:
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 16):
                        f.write(chunk)
            model = _get_whisper()
            segments, info = model.transcribe(tmp)
            if info.duration and info.duration / 60 > MAX_AUDIO_MINUTES:
                return "[episode too long for this run]"
            return " ".join(seg.text for seg in segments)
    except TimeoutError:
        return "[transcription timed out after 60 minutes -- skipped]"
    except Exception as e:
        return f"[transcription failed: {e}]"


# =====================================================================
# PDF + EMAIL (HITL -- draft only, NEVER send)
# =====================================================================

def render_pdf(synthesis, episodes, bible, signals, opportunities, red_team,
               track_record, newly_resolved, path):
    _ensure_package("reportlab")
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    HRFlowable, Table, TableStyle, KeepTogether)
    from reportlab.lib import colors

    INK   = colors.HexColor("#16324f")
    RULE  = colors.HexColor("#d7dee6")
    MUTE  = colors.HexColor("#6b7280")
    GOLD  = colors.HexColor("#b08d57")
    BADGE = {"HIGH":  colors.HexColor("#2e7d32"),
             "MEDIUM":colors.HexColor("#b7791f"),
             "LOW":   colors.HexColor("#6b7280"),
             "N/A":   colors.HexColor("#9ca3af")}
    SIG   = {"NEW":              colors.HexColor("#7c3aed"),
             "FRINGE RISING":    colors.HexColor("#dc2626"),
             "GOING MAINSTREAM": colors.HexColor("#c026d3"),
             "EMERGING":         colors.HexColor("#ea580c"),
             "RISING":           colors.HexColor("#b7791f"),
             "MAINSTREAM":       colors.HexColor("#2e7d32"),
             "STEADY":           colors.HexColor("#6b7280")}

    base = getSampleStyleSheet()
    h1   = ParagraphStyle("h1", parent=base["Heading1"], fontSize=19,
                          textColor=INK, spaceAfter=2)
    band = ParagraphStyle("band", parent=base["Heading2"], fontSize=12,
                          textColor=colors.white, leading=15)
    sub  = ParagraphStyle("sub", parent=base["Normal"], fontSize=9,
                          textColor=MUTE, spaceAfter=2)
    body = ParagraphStyle("body", parent=base["Normal"], fontSize=9.5, leading=14,
                          spaceAfter=3)
    head = ParagraphStyle("head", parent=body, fontName="Helvetica-Bold",
                          fontSize=10, textColor=INK, spaceBefore=6, spaceAfter=2)
    bull = ParagraphStyle("bull", parent=body, leftIndent=15, bulletIndent=3,
                          spaceAfter=2)
    name = ParagraphStyle("name", parent=base["Normal"], fontName="Helvetica-Bold",
                          fontSize=12.5, textColor=INK)
    badge_st = ParagraphStyle("badge", parent=base["Normal"], fontSize=8.5,
                              textColor=colors.white, fontName="Helvetica-Bold",
                              alignment=TA_RIGHT)
    cell = ParagraphStyle("cell", parent=body, fontSize=8.5, leading=11)
    cellb = ParagraphStyle("cellb", parent=cell, fontName="Helvetica-Bold")

    usable = letter[0] - 1.4 * inch

    JUNK = re.compile(r"^\s*(here (are|is)( my)?.*responses?:?|here is a short.*:?"
                      r"|by focusing on these.*)\s*$", re.I)

    def inline(t):
        t = (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"(?<!\*)\*(?!\s)(.+?)\*(?!\*)", r"<i>\1</i>", t)
        return t

    def md_flow(text):
        out = []
        for raw in (text or "").split("\n"):
            line = raw.strip()
            if not line or JUNK.match(line):
                continue
            hdr = re.match(r"^\**([A-Z][A-Z \-/']{2,}:)\**\s*(.*)$", line)
            bullet = re.match(r"^[\*\-•]\s+(.*)$", line)
            number = re.match(r"^(\d+)\.\s+(.*)$", line)
            if hdr and not bullet:
                label, rest = hdr.group(1), hdr.group(2).strip()
                out.append(Paragraph(inline(label), head))
                if rest:
                    out.append(Paragraph(inline(rest), body))
            elif bullet:
                out.append(Paragraph(inline(bullet.group(1)), bull, bulletText="•"))
            elif number:
                out.append(Paragraph(inline(number.group(2)), bull,
                                     bulletText=f"{number.group(1)}."))
            else:
                out.append(Paragraph(inline(line), body))
        return out

    def episode_card(e):
        rel = e.get("relevance", "N/A")
        header = Table(
            [[Paragraph(e["podcast"], name),
              Paragraph(rel, badge_st)]],
            colWidths=[usable - 78, 54])
        header.setStyle(TableStyle([
            ("BACKGROUND", (1, 0), (1, 0), BADGE.get(rel, BADGE["N/A"])),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (1, 0), (1, 0), 6), ("RIGHTPADDING", (1, 0), (1, 0), 6),
            ("TOPPADDING", (1, 0), (1, 0), 3), ("BOTTOMPADDING", (1, 0), (1, 0), 3),
            ("LEFTPADDING", (0, 0), (0, 0), 0),
        ]))
        inner = [header,
                 Paragraph(f"{e.get('published','')} &nbsp;·&nbsp; "
                           f"<i>{e.get('title','')}</i>", sub),
                 HRFlowable(width="100%", thickness=0.5, color=RULE,
                            spaceBefore=4, spaceAfter=4)]
        inner += md_flow(e.get("analysis", ""))
        card = Table([[inner]], colWidths=[usable])
        card.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.75, RULE),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))
        return KeepTogether([card, Spacer(1, 10)])

    def section_band(text, color):
        t = Table([[Paragraph(text, band)]], colWidths=[usable])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), color),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    def signal_table(sigs):
        rows = [[Paragraph("<b>SIGNAL</b>", cell), Paragraph("<b>7-DAY</b>", cell),
                 Paragraph("<b>BASE/WK</b>", cell), Paragraph("<b>VELOCITY</b>", cell),
                 Paragraph("<b># SHOWS</b>", cell), Paragraph("<b>STATUS</b>", cell)]]
        for s in sigs[:15]:
            color = SIG.get(s["status"], MUTE)
            rows.append([
                Paragraph(inline(s["term"]), cellb),
                Paragraph(str(s["current"]), cell),
                Paragraph(str(s["baseline_weekly"]), cell),
                Paragraph("—" if s["velocity"] is None else f"{s['velocity']}x", cell),
                Paragraph(str(s["breadth"]), cell),
                Paragraph(f"<font color='{('#' + color.hexval()[2:]) if hasattr(color,'hexval') else '#000000'}'>"
                          f"<b>{s['status']}</b></font>", cell),
            ])
        t = Table(rows, colWidths=[usable*0.34, usable*0.10, usable*0.12,
                                   usable*0.12, usable*0.12, usable*0.20])
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, RULE),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f6")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return t

    doc = SimpleDocTemplate(path, pagesize=letter, topMargin=0.7*inch,
                            bottomMargin=0.7*inch,
                            leftMargin=0.7*inch, rightMargin=0.7*inch)
    flow = [Paragraph("Daily Podcast Signal Brief", h1),
            Paragraph(f"{datetime.now():%A, %B %d, %Y}  ·  lens: {BUSINESS_LENS}", sub),
            Spacer(1, 8)]

    if track_record.get("total", 0) > 0:
        c = track_record["counts"]
        parts = ", ".join(f"{v} {k.lower()}" for k, v in c.items())
        flow += [section_band("Track Record -- does this agent's own calls hold up?", GOLD),
                 Spacer(1, 6),
                 Paragraph(f"<b>{track_record['held_up_pct']}%</b> of resolved calls held up "
                           f"(kept accelerating or went mainstream) out of "
                           f"<b>{track_record['total']}</b> scored to date "
                           f"({parts}). {track_record['pending']} calls still pending "
                           f"(checked back {PREDICTION_CHECK_DAYS} days after the call).", body)]
        if newly_resolved:
            flow.append(Spacer(1, 4))
            flow.append(Paragraph("<b>Scored today:</b>", head))
            for p in newly_resolved:
                good = p['verdict'] in ('CONFIRMED', 'CONTINUED', 'BROADENING')
                flow.append(Paragraph(
                    f"<font color='{'#2e7d32' if good else '#dc2626'}'>"
                    f"<b>{p['verdict']}</b></font> -- {inline(p['resolution_note'])}",
                    bull, bulletText="•"))
        flow.append(Spacer(1, 14))

    if signals:
        flow += [section_band("Signal Radar — 7-day window vs 3-week baseline", INK),
                 Spacer(1, 6), signal_table(signals), Spacer(1, 14)]

    flow += [section_band("Where the Change Is Happening / What It Means / How to Act", INK),
             Spacer(1, 6)]
    flow += md_flow(synthesis)

    if opportunities:
        flow += [Spacer(1, 14),
                 section_band("Investable Exposure — signal → companies (not advice)", GOLD),
                 Spacer(1, 6),
                 Paragraph("<i>Mapped exposure with bull/bear case and a falsifiable "
                           "trigger. This is analysis to inform your own judgment, "
                           "not a buy/sell recommendation.</i>", sub),
                 Spacer(1, 4)]
        for o in opportunities:
            card = Table(
                [[Paragraph(f"<b>{o['signal']}</b> &nbsp;·&nbsp; {o['status']}", name)]],
                colWidths=[usable])
            card.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0)]))
            flow.append(card)
            flow += md_flow(o["analysis"])
            flow.append(Spacer(1, 8))

    if red_team and not red_team.startswith("["):
        flow += [Spacer(1, 10),
                 section_band("Red Team — stress-testing today's brief", colors.HexColor("#7c2d12")),
                 Spacer(1, 6)]
        flow += md_flow(red_team)

    flow += [Spacer(1, 14), section_band("Per-Episode Breakdown", INK), Spacer(1, 10)]
    for e in episodes:
        flow.append(episode_card(e))

    if bible and bible.get("message"):
        flow += [Spacer(1, 6), section_band("Bible in a Year — This Week", GOLD),
                 Spacer(1, 6),
                 Paragraph(f"<i>{bible.get('title','')}</i>", sub)]
        flow += md_flow(bible["message"])

    flow += [Spacer(1, 16),
             HRFlowable(width="100%", thickness=0.5, color=RULE),
             Paragraph(f"<font size=8 color='#9ca3af'>tokens used this run: "
                       f"~{BUDGET.spent:,} of {RUN_TOKEN_BUDGET:,} budget</font>", body)]
    doc.build(flow)


def open_email_draft(pdf_path, to_addr):
    """Mac: open a pre-filled Mail DRAFT with the PDF attached. Draft only --
    the user reviews and hits Send themselves. AppleScript never sends."""
    subject = f"Daily Podcast Signal Brief — {datetime.now():%b %d}"
    body = "Today's podcast signal brief is attached. (Auto-drafted; review before sending.)"
    apath = os.path.abspath(pdf_path)
    script = f'''
    set theAttachment to POSIX file "{apath}"
    tell application "Mail"
        set newMessage to make new outgoing message with properties {{subject:"{subject}", content:"{body}" & return, visible:true}}
        tell newMessage
            make new to recipient at end of to recipients with properties {{address:"{to_addr}"}}
            make new attachment with properties {{file name:theAttachment}} at after last paragraph
        end tell
        activate
    end tell
    '''
    subprocess.run(["osascript", "-e", script], check=False)


# =====================================================================
# WIRE THE BOXES + RUN
# =====================================================================

def build_agent():
    g = StateGraph(PodState)
    g.add_node("fetch", fetch_node)
    g.add_node("transcribe", transcribe_node)
    g.add_node("summarize", summarize_node)
    g.add_node("analyze", analyze_node)
    g.add_node("signals", signals_node)
    g.add_node("opportunity", opportunity_node)
    g.add_node("predictions", predictions_node)
    g.add_node("synthesize", synthesize_node)
    g.add_node("report", report_node)

    g.add_edge(START, "fetch")
    g.add_edge("fetch", "transcribe")
    g.add_edge("transcribe", "summarize")
    g.add_edge("summarize", "analyze")
    g.add_edge("analyze", "signals")
    g.add_edge("signals", "opportunity")
    g.add_edge("opportunity", "predictions")
    g.add_edge("predictions", "synthesize")
    g.add_edge("synthesize", "report")
    g.add_edge("report", END)
    return g.compile()


LOCK_FILE = os.path.join(OUTPUT_DIR, ".scan_lock")

def acquire_lock() -> bool:
    """One scan at a time, across ALL launchers (launchd, the app, manual).
    A lock older than 3h is treated as a crashed run and stolen."""
    try:
        if os.path.exists(LOCK_FILE):
            age = time.time() - os.path.getmtime(LOCK_FILE)
            if age < 3 * 3600:
                return False
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
        return True
    except Exception:
        return True   # never let lock bookkeeping block a scan


def release_lock():
    try:
        os.remove(LOCK_FILE)
    except Exception:
        pass


def main():
    if not acquire_lock():
        print("Another scan is already running (lock held) -- exiting.")
        return
    print("Running the podcast signal scanner (daily mode).\n")
    try:
        _run()
    finally:
        release_lock()


def _run():
    ensure_ollama()
    agent = build_agent()
    final = agent.invoke({"episodes": [], "bible": None, "signals": [],
                          "opportunities": [], "track_record": {}, "newly_resolved": [],
                          "synthesis": "", "red_team": "", "pdf_path": ""})

    print(f"\nSignals JSON: {SIGNALS_FILE}")
    if final.get("pdf_path"):
        print(f"PDF saved:    {final['pdf_path']}")
    print(f"Tokens used this run: ~{BUDGET.spent:,} of {RUN_TOKEN_BUDGET:,}")

    if final.get("pdf_path") and EMAIL_TO != "your.email@example.com":
        print("Opening a Mail DRAFT for you to review (nothing is sent)...")
        open_email_draft(final["pdf_path"], EMAIL_TO)


if __name__ == "__main__":
    main()