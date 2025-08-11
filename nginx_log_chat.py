import re
import json
import subprocess
import pandas as pd
from textblob import TextBlob
from rich.console import Console
from rich.panel import Panel

# ----------- CONFIG -----------
ACCESS_LOG = "/var/log/nginx/access.log"  # Path to your access log
LOG_LIMIT = 500  # Number of latest log lines to parse
MODEL = "llama3"  # Ollama model for AI analysis

# ---------- REGEX ----------
LOG_PATTERN = re.compile(
    r'(?P<ip>\S+) - (?P<user>\S+) \[(?P<date>[^\]]+)\] '
    r'"(?P<method>\S+) (?P<url>\S+) (?P<protocol>\S+)" '
    r'(?P<status>\d{3}) (?P<size>\d+|-) '
    r'"(?P<referrer>[^"]*)" "(?P<agent>[^"]*)"'
)

# ---------- RICH CONSOLE ----------
console = Console()

def box_print(message):
    """Prints message inside a yellow border box."""
    console.print(Panel.fit(str(message), border_style="yellow"))

def parse_nginx_logs(limit=LOG_LIMIT):
    """Reads the access log file and parses each line into a dictionary."""
    entries = []
    try:
        with open(ACCESS_LOG, "r", errors="ignore") as f:
            lines = f.readlines()[-limit:]
            for line in lines:
                m = LOG_PATTERN.search(line)
                if m:
                    entries.append(m.groupdict())
    except FileNotFoundError:
        box_print(f"❌ Log file not found: {ACCESS_LOG}")
    return entries

def correct_spelling(text):
    """Auto-corrects spelling mistakes in user input."""
    return str(TextBlob(text).correct())

def generate_summary(df):
    """Generates a small summary dictionary from the log DataFrame."""
    return {
        "total_requests": len(df),
        "status_counts": df['status'].value_counts().to_dict(),
        "top_ips": df['ip'].value_counts().head(3).to_dict(),
        "top_urls": df['url'].value_counts().head(3).to_dict(),
    }

def detect_anomalies(df):
    """Detects 5xx errors and returns them in a dictionary."""
    anomalies = {}
    error_counts = df[df['status'].str.startswith('5')]['status'].value_counts()
    if not error_counts.empty:
        anomalies['5xx_errors'] = error_counts.to_dict()
    return anomalies

def ask_ai(question, summary, anomalies):
    """Sends the logs summary to the Ollama AI model and gets a short answer."""
    prompt = f"""
You are an AI assistant 🤖 analyzing NGINX logs.
Summary:
{json.dumps(summary, indent=2)}
Anomalies:
{json.dumps(anomalies, indent=2)}

Please answer the question briefly and clearly:
{question}
"""
    try:
        result = subprocess.run(
            ["ollama", "run", MODEL],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=60,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "⚠️ AI request timed out."
    except FileNotFoundError:
        return "⚠️ Ollama is not installed or not found in PATH."

def banner():
    """Displays a welcome banner."""
    box_print("🤖  NGINX Log AI Assistant\n========================================")

# ---------- MAIN PROGRAM ----------
if __name__ == "__main__":
    logs = parse_nginx_logs()
    if not logs:
        box_print("⚠️ No logs parsed. Check your ACCESS_LOG path or permissions.")
        exit(1)

    df = pd.DataFrame(logs)
    df['status'] = df['status'].astype(str)  # Ensure status is string

    banner()

    while True:
        q = console.input("[blue]You 🧑: [/blue]").strip()
        if q.lower() in ["exit", "quit"]:
            box_print("👋 Goodbye!")
            break

        corrected_q = correct_spelling(q)
        if corrected_q != q:
            box_print(f"📝 Corrected input: {corrected_q}")

        summary = generate_summary(df)
        anomalies = detect_anomalies(df)

        # Only show anomalies if user asks
        if "anomaly" in corrected_q.lower():
            if anomalies:
                box_print(f"⚠️ Anomalies Detected:\n{json.dumps(anomalies, indent=2)}")
            else:
                box_print("✅ No major anomalies detected.")

        # Only show full status/IP/URL tables if user asks
        if any(word in corrected_q.lower() for word in ["status", "ip", "url", "table", "top"]):
            from tabulate import tabulate
            status_counts = df['status'].value_counts().reset_index()
            box_print("📊 Status Codes:\n" + tabulate(status_counts, headers=['Status Code', 'Count'], tablefmt='pretty'))

            top_ips = df['ip'].value_counts().head(10).reset_index()
            box_print("🌍 Top IPs:\n" + tabulate(top_ips, headers=['IP', 'Requests'], tablefmt='pretty'))

            top_urls = df['url'].value_counts().head(10).reset_index()
            box_print("🔗 Top URLs:\n" + tabulate(top_urls, headers=['URL', 'Requests'], tablefmt='pretty'))

        # Always give a short AI summary
        answer = ask_ai(corrected_q, summary, anomalies)
        box_print(f"AI 🤖: {answer}")
#yes its new this is my code 
