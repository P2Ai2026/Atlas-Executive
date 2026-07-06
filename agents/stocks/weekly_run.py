#!/usr/bin/env python3
"""
WEEKLY RUNNER -- runs the Distressed-Infrastructure Scanner on a schedule.
==========================================================================
What it does, with NO Mail and NO sound:
  1. Makes sure Ollama is running (the AI step needs it).
  2. Runs your existing LangGraph agent from infra_scanner_step9.
  3. Saves the finished PDF into:  ~/Desktop/Distress Reports/
  4. OPENS that folder in Finder so the report is right in front of you.
     (Also fires a silent banner -- a bonus if your settings allow it.)

Run it by hand to test:   python3 weekly_run.py
"""

import os
import sys
import time
import shutil
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime

HOME = Path.home()
PROJECT = Path(__file__).resolve().parent          # where step1-9 live
# The Electron app passes DISTRESS_OUTPUT_DIR when it spawns this script;
# the Desktop default keeps standalone runs working.
REPORTS = Path(os.environ.get("DISTRESS_OUTPUT_DIR")
               or HOME / "Desktop" / "Distress Reports")
OLLAMA_URL = "http://127.0.0.1:11434/api/tags"


def notify(title, message):
    """Silent macOS banner (no sound). A bonus signal if settings allow it."""
    subprocess.run([
        "osascript", "-e",
        f'display notification "{message}" with title "{title}"'
    ])


def reveal(folder):
    """Open a folder in Finder -- the reliable, can't-miss signal."""
    subprocess.run(["open", str(folder)])


def ollama_up():
    try:
        urllib.request.urlopen(OLLAMA_URL, timeout=3)
        return True
    except Exception:
        return False


def ensure_ollama(max_wait=60):
    """If Ollama isn't running, launch the app and wait for it."""
    if ollama_up():
        return True
    subprocess.run(["open", "-a", "Ollama"])
    waited = 0
    while waited < max_wait:
        if ollama_up():
            return True
        time.sleep(3)
        waited += 3
    return False


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)

    if not ensure_ollama():
        notify("Distress Scanner - FAILED",
               "Could not reach Ollama, so no report was generated.")
        reveal(REPORTS)
        sys.exit(1)

    try:
        from infra_scanner_step9 import build_agent
        agent = build_agent()
        final = agent.invoke({"companies": [], "pdf_path": ""})
        pdf = final.get("pdf_path", "")
    except Exception as e:
        notify("Distress Scanner - FAILED", f"Run errored: {str(e)[:110]}")
        sys.exit(1)

    src = Path(pdf)
    if not src.is_absolute():
        src = PROJECT / pdf
    if src.exists():
        dest = REPORTS / f"distress_report_{datetime.now():%Y-%m-%d}.pdf"
        shutil.move(str(src), str(dest))
        notify("Distress Scanner - Report ready",
               f"Saved as {dest.name}")
        reveal(REPORTS)                    # <-- the dependable signal
        print(f"Done. Report at: {dest}")
    else:
        notify("Distress Scanner - Done, no file found",
               "The run finished but no PDF was produced. Check the logs.")
        reveal(REPORTS)
        print("Run finished but PDF path was empty or missing.")


if __name__ == "__main__":
    main()
