"""Inkling UI. Run from the repo root: python -m streamlit run app/streamlit_app.py"""

import streamlit as st

from agent.stub import respond

st.set_page_config(page_title="Inkling")
st.title("Inkling")
st.caption("Not a medical device. Patterns and education only, never a diagnosis.")

mode = st.radio("Mode", ["education", "summary"], horizontal=True)
question = st.text_input("Ask a question", "Why do I feel so tired this week?")

if question:
    r = respond(question, mode=mode)
    if r.fallback_used:
        st.warning("Live service unavailable, showing a cached answer.")
    if r.safety == "red_flag":
        st.error(r.escalation.reason)
    elif r.safety == "caution":
        st.warning("Worth asking a clinician about.")
    st.write(r.text)
    st.info(r.uncertainty_note)
    for chip in r.data_chips:
        st.markdown(f"**{chip.label}:** {chip.value} &nbsp; `data: {chip.source}`")
    for ev in r.evidence_chips:
        st.markdown(f"[{ev.source_org}: {ev.title}]({ev.url})  \n> {ev.snippet}")
