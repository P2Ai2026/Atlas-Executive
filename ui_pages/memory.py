import streamlit as st
from memory.index import ask_memory

EXAMPLES = [
    "What have we learned about NVIDIA?",
    "Summarize our AI infrastructure discussions.",
    "Compare meetings and podcasts about Microsoft.",
]

def show_memory():
    st.markdown("# 🌌 Ask Atlas")
    st.caption("Turn Conversations Into Knowledge")
    st.write("**Private • Local-First • AI Intelligence Platform**")

    st.info("🧠 Atlas searches your meetings, podcasts, and reports locally using Ollama.")

    question = st.text_input(
        "Ask Atlas",
        placeholder="Example: What have we learned about NVIDIA?"
    )

    st.markdown("#### 💡 Try these questions")
    cols = st.columns(3)
    for i, ex in enumerate(EXAMPLES):
        if cols[i].button(ex):
            question = ex

    if st.button("🚀 Ask Atlas", use_container_width=True):
        if not question.strip():
            st.warning("Please enter a question.")
            return

        with st.spinner("Atlas is searching your knowledge base..."):
            answer, sources = ask_memory(question)

        st.markdown("## 📖 Atlas Response")
        st.success(answer)

        st.markdown("## 📚 Knowledge Sources")
        if sources:
            for src in sources:
                st.markdown(f"**📄 {src['file']}**")
                st.caption(f"Source: {src['type']}")
        else:
            st.info("No matching sources found.")
