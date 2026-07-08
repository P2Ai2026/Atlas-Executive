import streamlit as st
from pathlib import Path
import whisper
import subprocess
from datetime import datetime

BASE = Path(__file__).resolve().parents[1]
PODCAST_AUDIO = BASE / "podcast_audio"
PODCAST_TRANSCRIPTS = BASE / "podcast_transcripts"
PODCAST_REPORTS = BASE / "podcast_reports"

def get_latest_audio():
    files = list(PODCAST_AUDIO.glob("*.mp3")) + list(PODCAST_AUDIO.glob("*.wav")) + list(PODCAST_AUDIO.glob("*.m4a"))
    return max(files, key=lambda f: f.stat().st_mtime) if files else None

def get_latest_transcript():
    files = list(PODCAST_TRANSCRIPTS.glob("*.txt"))
    return max(files, key=lambda f: f.stat().st_mtime) if files else None

def transcribe_podcast(audio_path):
    model = whisper.load_model("base")
    return model.transcribe(str(audio_path))["text"]

def analyze_podcast(transcript):
    prompt = f"""
You are Atlas AI.

Analyze this transcript for research purposes only.

Return:
1. Executive Summary
2. Companies Mentioned
3. People Mentioned
4. Technologies Mentioned
5. Industries Discussed
6. Bullish Arguments
7. Bearish Arguments
8. Risks
9. Topics Worth Researching
10. Action Items

Transcript:
{transcript}
"""
    result = subprocess.run(
        ["ollama","run","llama3.2"],
        input=prompt,
        text=True,
        capture_output=True
    )
    return result.stdout.strip()

def extract_section(text, heading):
    lines=text.splitlines()
    collect=False
    out=[]
    for line in lines:
        if heading.lower() in line.lower():
            collect=True
            continue
        if collect:
            if line.strip()[:2].isdigit() or (line.strip()[:1].isdigit() and "." in line):
                break
            out.append(line)
    return "\n".join(out).strip()

def show_podcasts():
    st.markdown("# 🌌 Atlas AI • Podcast Intelligence")
    st.caption("Turn Conversations Into Knowledge")
    st.info("🎧 Upload a podcast and Atlas will transcribe and analyze it locally using Whisper + Ollama.")

    uploaded=st.file_uploader("Upload podcast",type=["mp3","wav","m4a"])
    if uploaded:
        path=PODCAST_AUDIO/uploaded.name
        path.write_bytes(uploaded.getbuffer())
        st.success(f"Saved {uploaded.name}")

    latest=get_latest_audio()
    st.divider()
    st.subheader("🎙 Step 1 • Transcription")
    if latest:
        st.write(f"Current file: `{latest.name}`")
        if st.button("Transcribe with Whisper",use_container_width=True):
            with st.spinner("Transcribing..."):
                txt=transcribe_podcast(latest)
                out=PODCAST_TRANSCRIPTS/f"{latest.stem}_transcript.txt"
                out.write_text(txt,encoding="utf-8")
            st.success(f"Transcript saved: {out.name}")
            st.text_area("Preview",txt[:3000],height=220)

    transcript=get_latest_transcript()
    st.divider()
    st.subheader("🧠 Step 2 • Ask Atlas")
    if transcript:
        st.write(f"Transcript: `{transcript.name}`")
        if st.button("Analyze with Atlas",use_container_width=True):
            with st.spinner("Analyzing..."):
                analysis=analyze_podcast(transcript.read_text(encoding="utf-8",errors="ignore"))
                report=PODCAST_REPORTS/f"{transcript.stem}_{datetime.now():%Y-%m-%d}.md"
                report.write_text(analysis,encoding="utf-8")
            st.success(f"Research saved: {report.name}")
            a,b=st.columns(2)
            with a:
                st.markdown("### 🏢 Companies")
                st.write(extract_section(analysis,"Companies Mentioned") or "_None_")
                st.markdown("### 👥 People")
                st.write(extract_section(analysis,"People Mentioned") or "_None_")
            with b:
                st.markdown("### ⚙️ Technologies")
                st.write(extract_section(analysis,"Technologies Mentioned") or "_None_")
                st.markdown("### 🔍 Research Ideas")
                st.write(extract_section(analysis,"Topics Worth Researching") or "_None_")
            with st.expander("📄 Full Atlas Analysis"):
                st.markdown(analysis)
