import streamlit as st
from agents.meeting_brain import ask_meeting_brain
from ui_pages.common import NOTES, log_activity


def show_meeting_brain():
    st.header("Meeting Brain")
    st.caption("Ask questions across all saved meeting transcripts.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for role, message in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(message)

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Clear Chat"):
            st.session_state.chat_history = []
            st.rerun()
    with col2:
        st.caption(f"Messages: {len(st.session_state.chat_history)}")

    prompt = st.chat_input("Ask Meeting Brain about your meetings...")

    if prompt:
        st.session_state.chat_history.append(("user", prompt))
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Meeting Brain is thinking..."):
                answer = ask_meeting_brain(NOTES, prompt)
                st.markdown(answer)

        st.session_state.chat_history.append(("assistant", answer))
        log_activity("Asked Meeting Brain a question")
