"""
data_utils.py

Shared data-loading logic for the machine failure dashboard.
Used by BOTH failure_streamlit_app.py (the live app) and
build_report.py (the weekly emailed PDF) so there is exactly one
place that knows how to read and clean the data.
"""

import os
from typing import Optional

import pandas as pd

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TIME_OF_DAY_ORDER = ["morning", "afternoon", "evening", "night"]
SEVERITY_ORDER = ["Critical", "Major", "Moderate", "Minor"]


def classify_time_of_day(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    else:
        return "night"


def load_data(file) -> pd.DataFrame:
    """
    Accepts either the raw CSV (failure_timestamp column) or the output
    of process_failures.py (date / day_of_week / time_of_day columns).
    `file` can be a path (str) or a file-like object (e.g. Streamlit's
    uploaded file).
    """
    df = pd.read_csv(file)

    has_timestamp = "failure_timestamp" in df.columns
    has_date = "date" in df.columns

    if not has_timestamp and not has_date:
        raise ValueError(
            "Expected either a 'failure_timestamp' column (raw file) or a "
            "'date' column (output of process_failures.py), but found "
            f"columns: {list(df.columns)}"
        )

    if has_timestamp:
        df["failure_timestamp"] = pd.to_datetime(df["failure_timestamp"])
    else:
        df["failure_timestamp"] = pd.to_datetime(df["date"], format="%d-%m-%Y")

    if "date" not in df.columns:
        df["date"] = df["failure_timestamp"].dt.strftime("%d-%m-%Y")
    if "day_of_week" not in df.columns:
        df["day_of_week"] = df["failure_timestamp"].dt.strftime("%A")
    if "time_of_day" not in df.columns:
        df["time_of_day"] = df["failure_timestamp"].dt.hour.apply(classify_time_of_day)

    required = ["machine_id", "downtime_hours", "failure_severity", "root_cause_category"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required column(s): {missing}")

    if "root_cause_subcategory" not in df.columns:
        df["root_cause_subcategory"] = None

    return df


def find_default_file(search_dir: Optional[str] = None) -> Optional[str]:
    """Looks for the standard filenames in search_dir (defaults to cwd)."""
    search_dir = search_dir or os.getcwd()
    for name in ("failure_records_processed.csv", "failure_records.csv"):
        candidate = os.path.join(search_dir, name)
        if os.path.isfile(candidate):
            return candidate
    return None


def find_latest_dropped_file(drop_folder: str, pattern: str = "*.csv") -> str:
    """
    Used by build_report.py: finds the most recently modified CSV in the
    weekly data_drop/ folder. Raises if the folder is empty.
    """
    import glob

    files = glob.glob(os.path.join(drop_folder, pattern))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {drop_folder}")
    return max(files, key=os.path.getmtime)
