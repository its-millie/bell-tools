"""
config.py

All the settings you'll want to change later live here, in one place.
Nothing in this file is secret except the app password, which is read
from an environment variable instead (see send_email.py) — never put
a real password in this file.
"""

import os

# --- Dummy addresses for the prototype. Swap these for the real ones later. ---
FROM_EMAIL = "dashboard.bot@example.com"
TO_EMAIL = "test.manager@example.com"

# --- SMTP server settings (adjust to whichever provider you end up using) ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465

# --- Folder where the new weekly CSV gets dropped ---
DATA_DROP_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_drop")

# --- Where the generated report gets saved before emailing ---
REPORT_OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weekly_report.pdf")

# --- Repo the manager needs access to, and the command to run the app ---
REPO_URL = "https://github.com/Bell-Integration-AI-Automation/bell-mcp-lab"
REPO_CLONE_COMMAND = "git clone https://github.com/Bell-Integration-AI-Automation/bell-mcp-lab.git"
APP_FOLDER = "bell-mcp-lab/weekly_dashboard"  # adjust if the repo layout changes
RUN_COMMAND = "streamlit run failure_streamlit_app.py"
