import streamlit as st


def show_about():
    st.header("About AI Operations Hub")

    st.write(
        "AI Operations Hub is a local AI workspace built to process meetings, "
        "create reports, search transcripts, and chat with saved knowledge."
    )

    st.subheader("Version")
    st.write("v1.0 Clean Foundation")

    st.subheader("Built By")
    st.write("Trip Johnson")

    st.subheader("Current Features")
    st.markdown(
        """
- Drag-and-drop audio upload
- Whisper transcription
- Local AI summaries with Ollama
- PDF report generation
- Meeting Brain chat
- Searchable meeting history
- Dashboard metrics
- Sidebar navigation
- PDF downloads
- Podcast Intelligence placeholder
"""
    )

    st.subheader("Technology")
    st.markdown(
        """
- Python
- Streamlit
- Whisper
- Ollama
- ReportLab
"""
    )

    st.subheader("Roadmap")
    st.markdown(
        """
- Podcast Intelligence
- Universal AI Memory
- Document Intelligence
- Investment Intelligence
- Calendar and email integrations
"""
    )
