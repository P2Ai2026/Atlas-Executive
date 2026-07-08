import os
import streamlit as st
from app import process_audio
from ui_pages.common import AUDIO, log_activity


def show_meetings():
    st.header("Meeting Organizer")
    st.write("Upload an audio file, then process it with Whisper and Ollama.")

    uploaded_file = st.file_uploader(
        "Drop an audio file here",
        type=["mp3", "wav", "m4a"],
    )

    if uploaded_file is not None:
        save_path = AUDIO / uploaded_file.name
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Uploaded: {uploaded_file.name}")
        log_activity(f"Uploaded {uploaded_file.name}")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Process New Audio"):
            with st.spinner("Processing audio with Whisper and Ollama..."):
                process_audio()
            st.success("Done! Your transcript, AI report, and PDF were created.")
            log_activity("Processed a meeting")

    with col2:
        if st.button("Open Audio Folder"):
            os.system(f'open "{AUDIO}"')
