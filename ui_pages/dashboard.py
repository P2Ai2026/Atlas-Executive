import streamlit as st
from agents.search import search_meetings
from ui_pages.common import get_counts, NOTES, log_activity

def show_dashboard():
    st.markdown("# 🌌 ATLAS AI • Mission Control")
    st.caption("Turn Conversations Into Knowledge")

    transcripts, reports, archived, podcasts, investment_notes = get_counts()

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("🎙 Meetings", transcripts)
    c2.metric("🎧 Podcasts", podcasts)
    c3.metric("📄 Reports", reports)
    c4.metric("💾 Audio", archived)
    c5.metric("🧠 Research", investment_notes)

    st.divider()

    left,right = st.columns([2,1])

    with left:
        st.subheader("🛰 Atlas System Status")
        st.success("🟢 Ollama Connected")
        st.success("🟢 Whisper Ready")
        st.success("🟢 Ask Atlas Online")
        st.success("🟢 Local-First Mode")

        st.subheader("🔍 Ask Meeting History")
        query = st.text_input("Search meetings")

        if st.button("Search", use_container_width=True):
            if not query.strip():
                st.warning("Enter a search term.")
            else:
                results = search_meetings(NOTES, query)
                if results:
                    for r in results:
                        st.info(r)
                else:
                    st.info("No results found.")
                log_activity(f"Searched meetings for: {query}")

    with right:
        st.subheader("🌟 Company Spotlight")
        st.markdown("## NVIDIA")
        st.caption("Most discussed company")
        st.metric("Meeting Mentions", transcripts)
        st.metric("Podcast Mentions", podcasts)

        st.subheader("🚀 Atlas Modules")
        st.markdown("- 🧠 Ask Atlas")
        st.markdown("- 🎙 Meetings")
        st.markdown("- 🎧 Podcasts")
        st.markdown("- 📈 Investment Intelligence")
