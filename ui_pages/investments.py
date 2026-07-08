import re
from collections import Counter
import streamlit as st
from ui_pages.common import INVESTMENTS, PODCASTS, NOTES, log_activity

COMPANY_KEYWORDS=["NVIDIA","NVDA","Microsoft","MSFT","Apple","Tesla","Amazon","Google","Alphabet","Meta","OpenAI","Anthropic","AMD","Broadcom","Palantir","Oracle","Netflix","Salesforce"]
THEME_KEYWORDS=["AI","artificial intelligence","semiconductors","chips","data centers","cloud","energy","robotics","automation","growth","competition","regulation"]
RISK_KEYWORDS=["risk","competition","regulation","valuation","debt","recession","rates","export controls"]

def read_text_files(folder):
    items=[]
    for p in ["*.txt","*.md"]:
        for f in folder.glob(p):
            try:
                items.append((f.name,f.read_text(encoding="utf-8",errors="ignore")))
            except:
                pass
    return items

def combined_sources():
    s=[]
    for folder,label in [(INVESTMENTS,"Investment"),(PODCASTS,"Podcast"),(NOTES,"Meeting")]:
        s += [(f"{label}: {n}",t) for n,t in read_text_files(folder)]
    return s

def count_mentions(text,words):
    c=Counter(); low=text.lower()
    for w in words:
        n=low.count(w.lower())
        if n:c[w]=n
    return c

def show_investments():
    st.markdown("# 🌌 Atlas AI • Investment Intelligence")
    st.caption("Research, not financial advice")
    st.info("Analyze companies, themes and risks across your local knowledge base.")

    up=st.file_uploader("Upload research",type=["txt","md"])
    if up:
        path=INVESTMENTS/up.name
        path.write_bytes(up.getbuffer())
        st.success(f"Saved {up.name}")
        log_activity(f"Uploaded {up.name}")

    src=combined_sources()
    text="\n\n".join(t for _,t in src)
    if not text.strip():
        st.info("Upload research or analyze meetings/podcasts first.")
        return

    comps=count_mentions(text,COMPANY_KEYWORDS).most_common(8)
    themes=count_mentions(text,THEME_KEYWORDS).most_common(8)
    risks=count_mentions(text,RISK_KEYWORDS).most_common(8)

    a,b,c=st.columns(3)
    a.metric("Sources",len(src))
    b.metric("Companies",len(comps))
    c.metric("Themes",len(themes))

    l,m,r=st.columns(3)
    with l:
        st.subheader("🏢 Company Spotlight")
        [st.write(f"• {x} ({n})") for x,n in comps] or st.caption("No data")
    with m:
        st.subheader("🔥 Emerging Themes")
        [st.write(f"• {x} ({n})") for x,n in themes] or st.caption("No data")
    with r:
        st.subheader("⚠️ Risks")
        [st.write(f"• {x} ({n})") for x,n in risks] or st.caption("No data")

    st.divider()
    q=st.text_input("Ask Atlas Research")
    if st.button("🚀 Ask Atlas",use_container_width=True):
        if not q.strip():
            st.warning("Enter a question.")
            return
        import subprocess
        prompt=f"You are Atlas AI Research. Use only this context. Do not give financial advice.\nQuestion:{q}\nContext:\n{text[:12000]}"
        with st.spinner("Atlas is analyzing..."):
            res=subprocess.run(["ollama","run","llama3.2"],input=prompt,text=True,capture_output=True)
        st.markdown("## 📖 Atlas Research Response")
        st.write(res.stdout.strip())
        log_activity("Asked Atlas Research")
