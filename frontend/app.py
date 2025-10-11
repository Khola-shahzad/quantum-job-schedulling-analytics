"""
Streamlit Dashboard - dark quantum theme
"""
import streamlit as st
import pandas as pd
import requests
import plotly.express as px

BACKEND_URL = "http://backend:5000"

st.set_page_config(page_title="Quantum Job Scheduling", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: radial-gradient(circle at top left, #0a0f29, #000000 80%); color: #e0e0e0;}
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0a0f29 0%, #000000 100%); }
h1, h2, h3, h4 { color:#00ffff !important; text-shadow:0 0 10px #00ffff;}
div.stButton>button { background: linear-gradient(90deg,#6a00ff,#00ffff); color:white; border-radius:10px;}
[data-testid="stMetricValue"] { color:#00ffff !important; text-shadow:0 0 8px #00ffff; }
thead th { color:#00ffff !important; background:#111 !important; }
tbody tr { background:#090c20 !important; }
</style>
""", unsafe_allow_html=True)

st.title("⚛️ Quantum Job Scheduling Analytics")
st.sidebar.header("Simulation Controls")
algorithm = st.sidebar.selectbox("Select algorithm", ["FIFO", "RoundRobin", "Priority"])
num_jobs = st.sidebar.slider("Number of jobs", 1000, 10000, 5000, step=1000)
if st.sidebar.button("Run Simulation"):
    with st.spinner("Running..."):
        try:
            r = requests.post(f"{BACKEND_URL}/run-simulation", json={"algorithm": algorithm, "num_jobs": num_jobs}, timeout=600)
            if r.status_code == 200:
                st.success("Simulation finished")
            else:
                st.error(f"Backend error: {r.text}")
        except Exception as e:
            st.error(f"Error connecting to backend: {e}")

st.markdown("---")
try:
    r2 = requests.get(f"{BACKEND_URL}/get-results", timeout=10)
    if r2.status_code == 200:
        payload = r2.json()
        metrics = payload["metrics"]
        jobs = pd.DataFrame(payload["jobs"])

        col1, col2, col3 = st.columns(3)
        col1.metric("Avg Waiting Time (s)", metrics.get("avg_waiting_time"))
        col2.metric("Avg Turnaround (s)", metrics.get("avg_turnaround_time"))
        col3.metric("Throughput (jobs/s)", metrics.get("throughput"))

        st.markdown("### Waiting Time Distribution")
        fig = px.histogram(jobs, x="waiting_time", nbins=40)
        fig.update_layout(plot_bgcolor="#0a0f29", paper_bgcolor="#0a0f29", font_color="#e0e0e0")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Job Logs (top 100)")
        st.dataframe(jobs)
    else:
        st.info("No results yet. Run a simulation.")
except Exception as e:
    st.error(f"Could not load results: {e}")
