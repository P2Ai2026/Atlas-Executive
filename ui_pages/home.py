import streamlit as st
from ui_pages.common import get_counts, recent_pdfs

def show_home():
    transcripts, reports, archived, podcasts, investment_notes = get_counts()

    st.markdown("""
<style>
.atlas-command {
    width: 100%;
    padding: 18px 22px;
    border-radius: 18px;
    border: 1px solid rgba(96,165,250,.45);
    background: rgba(15,23,42,.78);
    box-shadow: 0 0 30px rgba(59,130,246,.18);
    color: #cbd5e1;
    margin-bottom: 22px;
}
.atlas-hero-card {
    padding: 34px;
    border-radius: 26px;
    border: 1px solid rgba(96,165,250,.35);
    background:
        radial-gradient(circle at 85% 20%, rgba(59,130,246,.35), transparent 30%),
        radial-gradient(circle at 65% 20%, rgba(139,92,246,.25), transparent 25%),
        linear-gradient(135deg, rgba(15,23,42,.95), rgba(2,6,23,.9));
    box-shadow: 0 0 50px rgba(59,130,246,.16);
    margin-bottom: 22px;
}
.atlas-logo-text {
    font-size: 58px;
    font-weight: 900;
    letter-spacing: -0.06em;
    background: linear-gradient(90deg,#ffffff,#60a5fa,#c084fc);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.atlas-gradient {
    background: linear-gradient(90deg,#38bdf8,#8b5cf6,#d946ef);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.atlas-card {
    padding: 22px;
    border-radius: 22px;
    border: 1px solid rgba(148,163,184,.22);
    background: rgba(15,23,42,.72);
    box-shadow: inset 0 1px 0 rgba(255,255,255,.04), 0 0 28px rgba(15,23,42,.35);
    min-height: 150px;
}
.atlas-card h3 {
    margin-top: 0;
}
.atlas-pill {
    display: inline-block;
    padding: 7px 12px;
    margin: 4px 6px 4px 0;
    border-radius: 999px;
    border: 1px solid rgba(96,165,250,.35);
    background: rgba(30,41,59,.75);
    color: #dbeafe;
    font-size: 13px;
}
.atlas-small {
    color: #94a3b8;
    font-size: 14px;
}
.atlas-status {
    color: #22c55e;
    font-weight: 800;
}
</style>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="atlas-command">
    Ask Atlas anything...
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="atlas-hero-card">
    <div class="atlas-logo-text">ATLAS AI</div>
    <h2 class="atlas-gradient">Turn Conversations Into Knowledge</h2>
    <p class="atlas-small">Private • Local-First • AI Intelligence Platform</p>
</div>
""", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Meetings Processed", transcripts)
    c2.metric("Podcasts Analyzed", podcasts)
    c3.metric("Reports Generated", reports)
    c4.metric("Atlas Queries", len(st.session_state.get("chat_history", [])))

    st.divider()

    left, right = st.columns([1.25, 1])

    with left:
        st.markdown("""
<div class="atlas-card">
<h3>Recent Activity</h3>
<p><span class="atlas-pill">Podcast</span> Podcast analysis ready</p>
<p><span class="atlas-pill">Meeting</span> Meeting Intelligence online</p>
<p><span class="atlas-pill">Memory</span> Ask Atlas connected</p>
<p><span class="atlas-pill">Research</span> Investment Intelligence active</p>
</div>
""", unsafe_allow_html=True)

        st.markdown("### Atlas Modules")
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.info("Meeting Intelligence\n\nOrganize and analyze meetings.")
        with m2:
            st.info("Podcast Intelligence\n\nExtract insights from podcasts.")
        with m3:
            st.info("Research Intelligence\n\nTrack themes and companies.")
        with m4:
            st.info("Ask Atlas\n\nSearch your local memory.")

    with right:
        st.markdown(f"""
<div class="atlas-card">
<h3>Company Spotlight</h3>
<h2>NVIDIA</h2>
<p class="atlas-small">Most discussed company placeholder</p>
<p><b>{podcasts}</b> podcast sources</p>
<p><b>{transcripts}</b> meeting sources</p>
<span class="atlas-pill">AI Infrastructure</span>
<span class="atlas-pill">Data Centers</span>
<span class="atlas-pill">Chips</span>
</div>
""", unsafe_allow_html=True)

        st.markdown("""
<div class="atlas-card" style="margin-top:18px;">
<h3>System Health</h3>
<p><span class="atlas-status">●</span> Ollama Online</p>
<p><span class="atlas-status">●</span> Whisper Ready</p>
<p><span class="atlas-status">●</span> Local Storage Healthy</p>
<p><span class="atlas-status">●</span> Ask Atlas Ready</p>
</div>
""", unsafe_allow_html=True)

    st.divider()

    st.subheader("Latest Reports")
    pdfs = recent_pdfs(5)
    if pdfs:
        for pdf in pdfs:
            st.write(pdf.name)
    else:
        st.caption("No reports generated yet.")
