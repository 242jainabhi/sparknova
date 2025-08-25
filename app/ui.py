import os
import streamlit as st
import requests

BACKEND = os.getenv("BACKEND_URL","http://localhost:8000")

st.set_page_config(page_title="Teams Q&A", page_icon="💬", layout="centered")
st.title("💬 Teams Q&A (RAG)")

# Load channels
try:
    r = requests.get(f"{BACKEND}/channels", timeout=10)
    r.raise_for_status()
    chans = r.json().get("channels", [])
except Exception as e:
    st.error(f"Failed to load channels from backend: {e}")
    st.stop()

labels = [c["channel_label"] for c in chans]
label = st.selectbox("Select channel", labels) if labels else st.text_input("Channel label")

query = st.text_input("Your question", placeholder="Describe the issue or question...")
top_k = st.slider("Results to retrieve", 1, 10, 5)

if st.button("Search"):
    if not query.strip():
        st.warning("Please enter a question.")
    else:
        with st.spinner("Searching..."):
            try:
                res = requests.post(f"{BACKEND}/query", json={
                    "query": query,
                    "channel_label": label,
                    "top_k": top_k
                }, timeout=60)
                res.raise_for_status()
                data = res.json()
                st.subheader("Answer")
                st.write(data.get("answer","(no answer)"))
                st.subheader("Matches")
                for i, m in enumerate(data.get("matches", []), start=1):
                    st.markdown(f"**Match {i}** — {m.get('channel_label','')} (score={m.get('score',0):.3f})")
                    st.code(m.get("snippet",""))
            except Exception as e:
                st.error(f"Query failed: {e}")
