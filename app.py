import os
import requests
from dotenv import load_dotenv

# 1. Load environment variables
load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")

def read_logs(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Log file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def analyze_with_ai(log_content):
    if not API_KEY:
        return "[Config Error]: GROQ_API_KEY is not set. Check your .env file."

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "qwen/qwen3.8-27b",
        "max_tokens": 750,  # <-- Increased from 500 to 750
        "messages": [
            {
                "role": "user",
                "content": f"You are a DevOps engineer. Analyze these logs, identify errors, and give a concise incident report with root cause and immediate fix steps:\n\n{log_content}"
            }
        ]
    }
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        result = response.json()
        
        # Check for API-level errors
        if "error" in result:
            return f"[API Error]: {result['error'].get('message')}"
            
        return result["choices"][0]["message"]["content"]

    except requests.exceptions.RequestException as e:
        return f"[Network Error]: {e}"

if __name__ == "__main__":
    logs = read_logs("sample.log")
    print("=== AI INCIDENT REPORT ===")
    print(analyze_with_ai(logs))