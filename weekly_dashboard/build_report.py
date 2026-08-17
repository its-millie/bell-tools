"""
build_report.py

Finds the newest CSV in data_drop/, loads and cleans it, and builds a
PDF where every chart compares THIS MONTH vs LAST MONTH side by side
(using the SAME chart functions the live Streamlit app can also use).

Run this on its own first to check the PDF comes out right:
    python build_report.py

"This month" / "last month" are calendar months based on the most
recent date in the data — e.g. if the latest record is Aug 12, 2026,
"this month" is Aug 1-12 (so far) and "last month" is all of July.
That means the two bars won't always represent an equal number of
days; a quiet start to a new month can look artificially low next to
a full previous month. Worth keeping in mind when reading the report,
especially early in a month.
"""

import os

import pandas as pd
from fpdf import FPDF

import config
from data_utils import find_latest_dropped_file, load_data
from charts import (
    breakdowns_per_machine_mom_chart,
    downtime_per_machine_mom_chart,
    severity_breakdown_mom_chart,
    weekday_downtime_mom_chart,
)


def build_report() -> str:
    # 1. Find and load the latest data
    latest_file = find_latest_dropped_file(config.DATA_DROP_FOLDER)
    df = load_data(latest_file)

    # 2. Split into "this month" vs "last month" (calendar months, based
    # on the most recent date in the data)
    now = df["failure_timestamp"].max()
    this_month_start = now.replace(day=1)
    last_month_end = this_month_start - pd.Timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    this_month_df = df[df["failure_timestamp"] >= this_month_start]
    last_month_df = df[(df["failure_timestamp"] >= last_month_start) & (df["failure_timestamp"] < this_month_start)]

    this_label = this_month_start.strftime("%b %Y")
    last_label = last_month_start.strftime("%b %Y")

    # 3. Build the 4 comparison charts
    figures = [
        breakdowns_per_machine_mom_chart(this_month_df, last_month_df, this_label, last_label),
        downtime_per_machine_mom_chart(this_month_df, last_month_df, this_label, last_label),
        severity_breakdown_mom_chart(this_month_df, last_month_df, this_label, last_label),
        weekday_downtime_mom_chart(this_month_df, last_month_df, this_label, last_label),
    ]

    # 4. Export each chart to a PNG (requires the `kaleido` package)
    tmp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp_chart_images")
    os.makedirs(tmp_dir, exist_ok=True)
    image_paths = []
    for i, fig in enumerate(figures):
        img_path = os.path.join(tmp_dir, f"chart_{i}.png")
        fig.write_image(img_path, width=1000, height=600, scale=2)
        image_paths.append(img_path)

    # 5. KPI summary: this month's totals, with the change vs last month
    def pct_change(this_val, last_val):
        if last_val == 0:
            return "n/a" if this_val == 0 else "new"
        return f"{100 * (this_val - last_val) / last_val:+.0f}%"

    this_breakdowns = len(this_month_df)
    last_breakdowns = len(last_month_df)
    this_downtime = this_month_df["downtime_hours"].sum()
    last_downtime = last_month_df["downtime_hours"].sum()

    # 6. Assemble the PDF
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "Monthly Machine Failure Report", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"{this_label} vs {last_label}", ln=True)
    pdf.ln(6)

    pdf.set_font("Helvetica", "", 13)
    kpi_lines = [
        f"Total Breakdowns: {this_breakdowns:,} ({pct_change(this_breakdowns, last_breakdowns)} vs {last_label})",
        f"Total Downtime: {this_downtime:,.1f} hrs ({pct_change(this_downtime, last_downtime)} vs {last_label})",
    ]
    for line in kpi_lines:
        pdf.cell(0, 9, line, ln=True)

    # One chart per page
    for img_path in image_paths:
        pdf.add_page()
        pdf.image(img_path, x=10, y=10, w=277)  # fits A4 landscape width

    pdf.output(config.REPORT_OUTPUT_PATH)

    # Clean up temp images
    for img_path in image_paths:
        os.remove(img_path)
    os.rmdir(tmp_dir)

    return config.REPORT_OUTPUT_PATH


if __name__ == "__main__":
    path = build_report()
    print(f"Report saved to: {path}")