from pathlib import Path
from datetime import datetime
import streamlit as st

BASE = Path(__file__).resolve().parents[1]
AUDIO = BASE / "meeting_audio"
NOTES = BASE / "meeting_notes"
REPORTS = BASE / "meeting_reports"
ARCHIVE = BASE / "archive"
PODCASTS = BASE / "data" / "podcasts"
DOCUMENTS = BASE / "data" / "documents"
INVESTMENTS = BASE / "data" / "investments"

for folder in [AUDIO, NOTES, REPORTS, ARCHIVE, PODCASTS, DOCUMENTS, INVESTMENTS]:
    folder.mkdir(parents=True, exist_ok=True)

def get_counts():
    transcripts = len(list(NOTES.glob("*.txt")))
    reports = len(list(REPORTS.glob("*.pdf")))
    archived = (
        len(list(ARCHIVE.glob("*.m4a")))
        + len(list(ARCHIVE.glob("*.mp3")))
        + len(list(ARCHIVE.glob("*.wav")))
    )
    podcasts = len(list(PODCASTS.glob("*.txt"))) + len(list(PODCASTS.glob("*.md")))
    investment_notes = len(list(INVESTMENTS.glob("*.txt"))) + len(list(INVESTMENTS.glob("*.md")))
    return transcripts, reports, archived, podcasts, investment_notes

def recent_pdfs(limit=10):
    return sorted(REPORTS.glob("*.pdf"), key=lambda f: f.stat().st_mtime, reverse=True)[:limit]

def log_activity(message):
    if "activity_log" not in st.session_state:
        st.session_state.activity_log = []
    timestamp = datetime.now().strftime("%I:%M %p")
    st.session_state.activity_log.insert(0, f"{timestamp} — {message}")
    st.session_state.activity_log = st.session_state.activity_log[:10]
