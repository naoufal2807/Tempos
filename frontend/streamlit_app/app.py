import os, requests, streamlit as st

API = os.getenv("API_URL", "http://localhost:8000/api/v1")

st.set_page_config(page_title="Tempos UI", layout="centered")
st.title("Tempos — Talk to your tasks")

with st.form("parse"):
    text = st.text_area("Enter tasks in natural language:")
    if st.form_submit_button("Parse & Save"):
        r = requests.post(f"{API}/tasks/parse", json={"text": text})
        st.write(r.json())

st.subheader("Ask a question")
q = st.text_input("e.g., What tasks do I have this week?")
if st.button("Ask"):
    r = requests.post(f"{API}/query", json={"question": q})
    st.write(r.json())

st.subheader("All tasks")
if st.button("Refresh tasks"):
    r = requests.get(f"{API}/tasks")
    st.write(r.json())
