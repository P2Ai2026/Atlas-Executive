import streamlit as st
from pathlib import Path

from ui_pages.home import show_home
from ui_pages.meetings import show_meetings
from ui_pages.meeting_brain import show_meeting_brain
from ui_pages.reports import show_reports
from ui_pages.dashboard import show_dashboard
from ui_pages.podcasts import show_podcasts
from ui_pages.investments import show_investments
from ui_pages.memory import show_memory
from ui_pages.about import show_about
from memory.index import ask_memory

BASE = Path(__file__).parent
LOGO_PATH = BASE / "assets" / "logos" / "atlas_logo_dark.png"
ICON_PATH = BASE / "assets" / "logos" / "atlas_icon.png"

st.set_page_config(
    page_title="ATLAS AI",
    page_icon=str(ICON_PATH) if ICON_PATH.exists() else "🌌",
    layout="wide",
)
st.markdown("""
<style>
.stApp {
    background:
        radial-gradient(circle at top left, rgba(124, 58, 237, 0.35), transparent 28%),
        radial-gradient(circle at top right, rgba(6, 182, 212, 0.22), transparent 28%),
        linear-gradient(135deg, #050816 0%, #0b1020 45%, #111827 100%);
    color: #f8fafc;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #070b18 0%, #111827 100%);
    border-right: 1px solid rgba(148, 163, 184, 0.2);
}

[data-testid="stSidebar"] * {
    color: #f8fafc;
}

h1, h2, h3 {
    color: #ffffff;
    letter-spacing: -0.04em;
}

p, li, span {
    color: #dbeafe;
}

.block-container {
    padding-top: 2rem;
    max-width: 1250px;
}

.stButton button {
    border-radius: 14px;
    padding: 0.75rem 1.05rem;
    font-weight: 800;
    border: 1px solid rgba(96, 165, 250, 0.65);
    background: linear-gradient(90deg, #2563eb, #7c3aed, #06b6d4);
    color: white;
    box-shadow: 0 0 22px rgba(59, 130, 246, 0.35);
    transition: all 0.2s ease-in-out;
}

.stButton button:hover {
    transform: translateY(-2px);
    box-shadow: 0 0 36px rgba(139, 92, 246, 0.75);
}

[data-testid="stMetric"] {
    background: rgba(15, 23, 42, 0.82);
    padding: 20px;
    border-radius: 20px;
    border: 1px solid rgba(96, 165, 250, 0.35);
    box-shadow:
        0 0 28px rgba(37, 99, 235, 0.14),
        inset 0 1px 0 rgba(255,255,255,0.06);
}

[data-testid="stMetricLabel"] {
    color: #93c5fd;
}

[data-testid="stMetricValue"] {
    color: #ffffff;
}

div[data-testid="stAlert"] {
    border-radius: 18px;
    border: 1px solid rgba(96, 165, 250, 0.28);
    background: rgba(15, 23, 42, 0.65);
}

section.main div[data-testid="stVerticalBlock"] > div {
    border-radius: 14px;
}

input, textarea {
    border-radius: 14px !important;
}

hr {
    border-color: rgba(148, 163, 184, 0.25);
}

.atlas-hero {
    padding: 28px 30px;
    border-radius: 26px;
    border: 1px solid rgba(96, 165, 250, 0.35);
    background:
        radial-gradient(circle at top right, rgba(6,182,212,0.22), transparent 30%),
        linear-gradient(135deg, rgba(30,41,59,0.92), rgba(15,23,42,0.82));
    box-shadow: 0 0 45px rgba(59,130,246,0.18);
    margin-bottom: 24px;
}

.atlas-title {
    font-size: 54px;
    font-weight: 900;
    letter-spacing: -0.06em;
    margin-bottom: 4px;
    background: linear-gradient(90deg, #ffffff, #93c5fd, #c084fc, #67e8f9);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.atlas-tagline {
    font-size: 20px;
    color: #bfdbfe;
    margin-bottom: 6px;
}

.atlas-subtitle {
    font-size: 14px;
    color: #94a3b8;
}
</style>
""", unsafe_allow_html=True)
if "activity_log" not in st.session_state:
    st.session_state.activity_log = []

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if LOGO_PATH.exists():
    st.sidebar.image(str(LOGO_PATH), use_container_width=True)
else:
    st.sidebar.title("ATLAS AI")

st.sidebar.caption("Turn Conversations Into Knowledge")
st.sidebar.markdown("---")
st.sidebar.success("Local Mode")
st.sidebar.success("Ollama Connected")
st.sidebar.success("Whisper Ready")
page = st.sidebar.radio(
    "Navigation",
    [
        "Home",
        "Meeting Organizer",
        "Meeting Brain",
        "Podcast Intelligence",
        "Investment Intelligence",
        "AI Memory",
        "Reports",
        "Dashboard",
        "About",
    ],
)

st.markdown('<div class="atlas-hero">', unsafe_allow_html=True)
if LOGO_PATH.exists():
    st.image(str(LOGO_PATH), width=420)
else:
    st.markdown('<div class="atlas-title">ATLAS AI</div>', unsafe_allow_html=True)
st.markdown("""
    <div class="atlas-tagline">Turn Conversations Into Knowledge</div>
    <div class="atlas-subtitle">Private • Local-First • AI Intelligence Platform</div>
</div>
""", unsafe_allow_html=True)

st.markdown("### 🔍 Ask Atlas")
atlas_query = st.text_input(
    "",
    placeholder="Ask anything about your meetings, podcasts, or research..."
)

if atlas_query:
    with st.spinner("Atlas is searching your knowledge base..."):
        try:
            answer, sources = ask_memory(atlas_query)
            st.success(answer)
            if sources:
                with st.expander("Knowledge Sources"):
                    for src in sources:
                        st.write(f"• {src.get('file','Unknown')} ({src.get('type','Unknown')})")
        except Exception as e:
            st.error(f"Ask Atlas is unavailable: {e}")


if page == "Home":
    show_home()
elif page == "Meeting Organizer":
    show_meetings()
elif page == "Meeting Brain":
    show_meeting_brain()
elif page == "Podcast Intelligence":
    show_podcasts()
elif page == "Investment Intelligence":
    show_investments()
elif page == "AI Memory":
    show_memory()
elif page == "Reports":
    show_reports()
elif page == "Dashboard":
    show_dashboard()
elif page == "About":
    show_about()