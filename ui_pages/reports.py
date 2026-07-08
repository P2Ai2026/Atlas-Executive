import streamlit as st
from ui_pages.common import recent_pdfs


def show_reports():
    st.header("Reports")

    pdfs = recent_pdfs(20)
    if not pdfs:
        st.info("No PDF reports found yet.")
        return

    for pdf in pdfs:
        st.subheader(f"📄 {pdf.name}")
        with open(pdf, "rb") as file:
            st.download_button(
                label="Download PDF",
                data=file,
                file_name=pdf.name,
                mime="application/pdf",
            )
        st.divider()
