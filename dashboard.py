import os
import requests
import streamlit as st
from dotenv import load_dotenv

# Page configuration
st.set_page_config(
    page_title="AI DevOps Log Incident Analyzer",
    page_icon="🛠️",
    layout="wide"
)

# Load environment variables
load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")

def analyze_logs(log_content: str, model_name: str = "qwen/qwen3.8-27b") -> str:
    if not API_KEY:
        return "❌ Error: GROQ_API_KEY is not set in `.env`."

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model_name,
        "max_tokens": 750,
        "messages": [
            {
                "role": "user",
                "content": (
                    "You are a Senior DevOps and Site Reliability Engineer (SRE). "
                    "Analyze the provided log content. Provide a clear incident report with:\n"
                    "1. Executive Summary & Severity\n"
                    "2. Root Cause Analysis\n"
                    "3. Step-by-Step Mitigation & Fix Actions\n\n"
                    f"Logs:\n{log_content}"
                )
            }
        ]
    }

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=45
        )
        data = response.json()
        if "error" in data:
            return f"❌ **API Error:** {data['error'].get('message')}"
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        return f"❌ **Network Error:** {e}"

# --- UI Layout ---
st.title("🛠️ AI DevOps Log Incident Analyzer")
st.caption("Automated Incident Triage & Root Cause Localization powered by AI")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    model_choice = st.selectbox(
        "Select Model",
        ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"],
        index=0
    )
    st.markdown("---")
    st.markdown("### 📋 Sample Scenarios")
    if st.button("Load DB Timeout Sample"):
        st.session_state["log_input"] = (
            "2025-02-18 10:00:01 [ERROR] Database connection timed out after 30s\n"
            "2025-02-18 10:00:02 [FATAL] Payment service failed to reach database at 10.0.0.5:5432\n"
            "2025-02-18 10:00:05 [WARN] Circuit breaker tripped for service 'payment-service'"
        )

# Main Grid (2 Columns: Input on Left, AI Output on Right)
col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("📥 Log Ingestion")
    
    # File Uploader
    uploaded_file = st.file_uploader("Upload a log file (.log, .txt)", type=["log", "txt"])
    
    if uploaded_file is not None:
        file_content = uploaded_file.read().decode("utf-8")
        st.session_state["log_input"] = file_content

    # Text Area for manual paste / editing
    default_text = st.session_state.get("log_input", "")
    log_text = st.text_area("Paste or edit raw logs:", value=default_text, height=350)

    analyze_btn = st.button("🚀 Analyze Incident", type="primary", use_container_width=True)

with col2:
    st.subheader("📊 Incident Report")
    
    if analyze_btn:
        if not log_text.strip():
            st.warning("⚠️ Please provide log data first.")
        else:
            with st.spinner("Analyzing log events and determining root cause..."):
                report = analyze_logs(log_text, model_choice)
                st.markdown(report)
    else:
        st.info("👈 Upload a log file or paste logs on the left and click **Analyze Incident**.")