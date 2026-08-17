"""
failure_streamlit_app.py

Interactive Streamlit dashboard for machine failure records, organized
into tabs:

    Overview        - KPIs + the core breakdown/downtime/severity charts
    Deep Dive       - Pareto chart, sunburst drill-down, polar clock view,
                      box plot, animated cumulative-breakdowns race
    Sensor Insights - correlations between pre-failure sensor readings
                      (temperature, vibration, motor current, lubricant
                      quality) and downtime/severity
    Raw Data        - filtered table + CSV download

Accepts either the raw CSV (failure_timestamp column) or the output of
process_failures.py (date / day_of_week / time_of_day columns).

--------------------------------------------------------------------------
SETUP (run once):
    pip install -r requirements.txt

RUN:
    streamlit run failure_streamlit_app.py

This opens a local web app in your browser (usually http://localhost:8501).
Use the sidebar to upload a CSV, or drop failure_records_processed.csv (or
failure_records.csv) in the same folder as this script and it will be
picked up automatically.
--------------------------------------------------------------------------
"""

import os
from datetime import timedelta
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TIME_OF_DAY_ORDER = ["morning", "afternoon", "evening", "night"]
SEVERITY_ORDER = ["Critical", "Major", "Moderate", "Minor"]

# Vivid, high-contrast palette for a dark theme
NEON = ["#00F5D4", "#FF206E", "#FFD23F", "#7B2FF7", "#00B4D8", "#FF9F1C", "#3AFF8C", "#FF4D97"]
SEVERITY_COLORS = {"Critical": "#FF206E", "Major": "#FF9F1C", "Moderate": "#FFD23F", "Minor": "#3AFF8C"}
TOD_COLORS = {"morning": "#FFD23F", "afternoon": "#FF9F1C", "evening": "#7B2FF7", "night": "#00B4D8"}

BG = "#0E1117"
CARD_BG = "#161A25"
FONT_COLOR = "#E6E6E6"

st.set_page_config(page_title="Machine Failure Dashboard", layout="wide", page_icon="⚡")

st.markdown(
    f"""
    <style>
    .stApp {{ background-color: {BG}; color: {FONT_COLOR} !important; }}
    [data-testid="stMetric"] {{
        background-color: {CARD_BG};
        border: 1px solid #2A2F3E;
        border-radius: 10px;
        padding: 12px 8px;
    }}
    [data-testid="stMetricLabel"] {{ color: #B8BEC9 !important; }}
    [data-testid="stMetricValue"] {{ color: #FFFFFF !important; font-weight: 700; }}
    [data-testid="stMetricValue"] div {{ color: #FFFFFF !important; }}
    h1, h2, h3, h4, p, span, label, .stMarkdown, .stCaption {{ color: {FONT_COLOR} !important; }}
    [data-testid="stCaptionContainer"] {{ color: #B8BEC9 !important; }}
    button[data-baseweb="tab"] {{ color: #B8BEC9 !important; }}
    button[data-baseweb="tab"][aria-selected="true"] {{ color: #FF206E !important; }}
    section[data-testid="stSidebar"] {{ background-color: {CARD_BG}; }}
    section[data-testid="stSidebar"] * {{ color: {FONT_COLOR} !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def style_fig(fig, title_extra: str = "") -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=dict(color=FONT_COLOR, size=13),
        title=dict(font=dict(color="#FFFFFF", size=16)),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=FONT_COLOR, size=12),
            title=dict(font=dict(color="#FFFFFF", size=13)),
        ),
        coloraxis_colorbar=dict(
            tickfont=dict(color=FONT_COLOR),
            title=dict(font=dict(color=FONT_COLOR)),
        ),
        margin=dict(t=60, l=10, r=10, b=10),
    )
    fig.update_xaxes(title_font=dict(color=FONT_COLOR), tickfont=dict(color=FONT_COLOR))
    fig.update_yaxes(title_font=dict(color=FONT_COLOR), tickfont=dict(color=FONT_COLOR))
    return fig


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

def classify_time_of_day(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    else:
        return "night"


@st.cache_data
def load_data(file) -> pd.DataFrame:
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


def find_default_file() -> Optional[str]:
    script_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
    data_drop_dir = os.path.join(script_dir, "data_drop")

    # Check data_drop/ first (this is where the weekly automation drops
    # new files), then fall back to the old locations for compatibility.
    search_dirs = [data_drop_dir, script_dir, os.getcwd()]
    for directory in search_dirs:
        for name in ("failure_records_processed.csv", "failure_records.csv"):
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                return candidate
    return None


# --------------------------------------------------------------------------
# Sidebar: data source + filters
# --------------------------------------------------------------------------

st.sidebar.header("Data")
uploaded = st.sidebar.file_uploader("Upload CSV", type="csv")

default_path = find_default_file()
source = uploaded if uploaded is not None else default_path

if source is None:
    st.title("⚡ Machine Failure Dashboard")
    st.warning(
        "No data found. Upload a CSV in the sidebar, or place "
        "'failure_records_processed.csv' (or 'failure_records.csv') "
        "in the data_drop folder next to this script."
    )
    st.stop()

try:
    df_full = load_data(source)
except Exception as e:
    st.error(f"Could not load data: {e}")
    st.stop()

if uploaded is None:
    st.sidebar.caption(f"Using local file: {os.path.basename(default_path)}")

st.sidebar.header("Filters")

machines = sorted(df_full["machine_id"].dropna().unique().tolist())
sel_machines = st.sidebar.multiselect("Machine", machines, default=machines)

severities = [s for s in SEVERITY_ORDER if s in df_full["failure_severity"].unique()]
sel_severities = st.sidebar.multiselect("Severity", severities, default=severities)

categories = sorted(df_full["root_cause_category"].dropna().unique().tolist())
sel_categories = st.sidebar.multiselect("Root cause category", categories, default=categories)

min_date = df_full["failure_timestamp"].min().date()
max_date = df_full["failure_timestamp"].max().date()
date_range = st.sidebar.date_input("Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)

df = df_full[
    df_full["machine_id"].isin(sel_machines)
    & df_full["failure_severity"].isin(sel_severities)
    & df_full["root_cause_category"].isin(sel_categories)
]
if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
    df = df[(df["failure_timestamp"].dt.date >= start) & (df["failure_timestamp"].dt.date <= end)]

st.title("⚡ Machine Failure Dashboard")
st.caption(f"{len(df)} of {len(df_full)} records shown after filters")

if df.empty:
    st.warning("No records match the current filters.")
    st.stop()

now = df["failure_timestamp"].max()
past_month_start = now - timedelta(days=30)
this_week_start = now - timedelta(days=7)
past_month = df[df["failure_timestamp"] >= past_month_start]
this_week = df[df["failure_timestamp"] >= this_week_start]


# --------------------------------------------------------------------------
# KPI row
# --------------------------------------------------------------------------

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Breakdowns", f"{len(df):,}")
k2.metric("Total Downtime (hrs)", f"{df['downtime_hours'].sum():,.1f}")
k3.metric("Avg Downtime / Breakdown", f"{df['downtime_hours'].mean():.1f} hrs")
top_machine = df["machine_id"].value_counts().idxmax()
k4.metric("Most Problematic Machine", top_machine)
top_cause = df["root_cause_category"].value_counts().idxmax()
k5.metric("Top Root Cause", top_cause.replace("_", " ").title())

st.write("")

tab_overview, tab_deep, tab_sensor, tab_raw = st.tabs(
    ["📊 Overview", "🔍 Deep Dive", "📡 Sensor Insights", "📋 Raw Data"]
)


# --------------------------------------------------------------------------
# Tab 1: Overview
# --------------------------------------------------------------------------

with tab_overview:
    col1, col2 = st.columns(2)

    with col1:
        s1 = past_month["machine_id"].value_counts().sort_index().reset_index()
        s1.columns = ["machine_id", "count"]
        fig = px.bar(
            s1, x="machine_id", y="count", color="machine_id",
            title=f"Breakdowns per Machine (past 30 days, since {past_month_start.date()})",
            labels={"machine_id": "Machine ID", "count": "Number of breakdowns"},
            color_discrete_sequence=NEON,
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(style_fig(fig), width="stretch")

    with col2:
        s2 = past_month.groupby("machine_id")["downtime_hours"].sum().sort_index().reset_index()
        fig = px.bar(
            s2, x="machine_id", y="downtime_hours", color="machine_id",
            title=f"Downtime Hours per Machine (past 30 days, since {past_month_start.date()})",
            labels={"machine_id": "Machine ID", "downtime_hours": "Downtime hours"},
            color_discrete_sequence=NEON,
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(style_fig(fig), width="stretch")

    col3, col4 = st.columns(2)

    with col3:
        s6 = past_month["failure_severity"].value_counts()
        order = [s for s in SEVERITY_ORDER if s in df["failure_severity"].unique()]
        s6 = s6.reindex(order, fill_value=0).reset_index()
        s6.columns = ["failure_severity", "count"]
        fig = px.bar(
            s6, x="failure_severity", y="count", color="failure_severity",
            title=f"Breakdowns per Severity (past 30 days, since {past_month_start.date()})",
            labels={"failure_severity": "Severity", "count": "Number of breakdowns"},
            color_discrete_map=SEVERITY_COLORS,
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(style_fig(fig), width="stretch")

    with col4:
        pivot = (
            df.groupby(["machine_id", "day_of_week"]).size()
            .unstack(fill_value=0)
            .reindex(columns=DAY_ORDER, fill_value=0)
            .reindex(sorted(df["machine_id"].unique()))
        )
        fig = px.imshow(
            pivot, x=pivot.columns, y=pivot.index, aspect="auto",
            color_continuous_scale="Plasma",
            title="Breakdown Heatmap: Machine vs Day of Week",
            labels={"x": "Day of week", "y": "Machine ID", "color": "Breakdowns"},
        )
        st.plotly_chart(style_fig(fig), width="stretch")


# --------------------------------------------------------------------------
# Tab 2: Deep Dive
# --------------------------------------------------------------------------

with tab_deep:
    col1, col2 = st.columns(2)

    # Pareto chart: category counts (bars) + cumulative % (line, secondary axis)
    with col1:
        s4 = df["root_cause_category"].value_counts().reset_index()
        s4.columns = ["root_cause_category", "count"]
        s4["cumulative_pct"] = 100 * s4["count"].cumsum() / s4["count"].sum()
        top_category = s4.iloc[0]["root_cause_category"]

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(x=s4["root_cause_category"], y=s4["count"], name="Breakdowns",
                   marker_color=NEON[0]),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(x=s4["root_cause_category"], y=s4["cumulative_pct"], name="Cumulative %",
                       mode="lines+markers", line=dict(color=NEON[1], width=3)),
            secondary_y=True,
        )
        fig.update_yaxes(title_text="Number of breakdowns", secondary_y=False)
        fig.update_yaxes(title_text="Cumulative %", range=[0, 105], secondary_y=True)
        fig.update_yaxes(title_font=dict(color=FONT_COLOR), tickfont=dict(color=FONT_COLOR), secondary_y=True)
        fig.update_layout(title="Pareto: Root Cause Categories (all-time, filtered)")
        st.plotly_chart(style_fig(fig), width="stretch")

    # Sunburst drill-down: category -> subcategory
    with col2:
        if df["root_cause_subcategory"].notna().any():
            fig = px.sunburst(
                df, path=["root_cause_category", "root_cause_subcategory"],
                title="Root Cause Drill-Down (click to zoom)",
                color="root_cause_category", color_discrete_sequence=NEON,
            )
            st.plotly_chart(style_fig(fig), width="stretch")
        else:
            st.info("No subcategory data available for the current filters.")

    col3, col4 = st.columns(2)

    # Polar "clock" view: day of week x time of day
    with col3:
        pivot_dow = (
            df.groupby(["day_of_week", "time_of_day"]).size()
            .unstack(fill_value=0)
            .reindex(DAY_ORDER)
            .reindex(columns=TIME_OF_DAY_ORDER, fill_value=0)
            .reset_index()
        )
        melted = pivot_dow.melt(id_vars="day_of_week", var_name="time_of_day", value_name="count")
        fig = px.bar_polar(
            melted, r="count", theta="day_of_week", color="time_of_day",
            category_orders={"day_of_week": DAY_ORDER, "time_of_day": TIME_OF_DAY_ORDER},
            color_discrete_map=TOD_COLORS,
            title="Breakdown Clock: Day of Week × Time of Day",
        )
        st.plotly_chart(style_fig(fig), width="stretch")

    # Box plot: downtime distribution by severity
    with col4:
        order = [s for s in SEVERITY_ORDER if s in df["failure_severity"].unique()]
        fig = px.box(
            df, x="failure_severity", y="downtime_hours", color="failure_severity",
            category_orders={"failure_severity": order},
            color_discrete_map=SEVERITY_COLORS,
            title="Downtime Hours Distribution by Severity",
            labels={"failure_severity": "Severity", "downtime_hours": "Downtime hours"},
            points="all",
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(style_fig(fig), width="stretch")

    # Weekly downtime line with range slider
    weekly = (
        df.set_index("failure_timestamp")
        .resample("W-MON")["downtime_hours"]
        .sum()
        .sort_index()
        .reset_index()
    )
    fig = go.Figure(go.Scatter(
        x=weekly["failure_timestamp"], y=weekly["downtime_hours"],
        mode="lines+markers", fill="tozeroy",
        line=dict(color=NEON[2], width=2), marker=dict(size=5, color=NEON[1]),
    ))
    fig.update_layout(
        title="Total Weekly Downtime Hours Over Time (drag the slider below to zoom)",
        xaxis=dict(rangeslider=dict(visible=True)),
        yaxis_title="Total downtime hours",
    )
    st.plotly_chart(style_fig(fig), width="stretch")

    # Animated race: cumulative breakdowns per machine over time
    st.subheader("Cumulative Breakdown Race")
    weekly_counts = df.groupby([pd.Grouper(key="failure_timestamp", freq="W-MON"), "machine_id"]).size().unstack(fill_value=0)
    if not weekly_counts.empty:
        full_weeks = pd.date_range(weekly_counts.index.min(), weekly_counts.index.max(), freq="W-MON")
        weekly_counts = weekly_counts.reindex(full_weeks, fill_value=0)
        cumulative = weekly_counts.cumsum()
        race = cumulative.reset_index().melt(id_vars="index", var_name="machine_id", value_name="cumulative_count")
        race = race.rename(columns={"index": "week"})
        race["week_label"] = race["week"].dt.strftime("%Y-%m-%d")
        race = race.sort_values("week")
        fig = px.bar(
            race, x="machine_id", y="cumulative_count", color="machine_id",
            animation_frame="week_label", range_y=[0, race["cumulative_count"].max() + 1],
            color_discrete_sequence=NEON,
            title="Cumulative Breakdowns per Machine Over Time (press ▶ play)",
            labels={"machine_id": "Machine ID", "cumulative_count": "Cumulative breakdowns"},
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(style_fig(fig), width="stretch")


# --------------------------------------------------------------------------
# Tab 3: Sensor Insights
# --------------------------------------------------------------------------

with tab_sensor:
    sensor_cols = ["max_temperature_c_72h", "max_vibration_x_72h", "max_motor_current_a_72h", "min_lubricant_quality_72h"]
    available_sensors = [c for c in sensor_cols if c in df.columns and df[c].notna().any()]

    if not available_sensors:
        st.info(
            "No pre-failure sensor columns (temperature, vibration, motor current, "
            "lubricant quality) found in this file. This tab needs the raw "
            "failure_records.csv, not the process_failures.py output."
        )
    else:
        order = [s for s in SEVERITY_ORDER if s in df["failure_severity"].unique()]

        col1, col2 = st.columns(2)

        if "max_temperature_c_72h" in available_sensors:
            with col1:
                fig = px.scatter(
                    df, x="max_temperature_c_72h", y="downtime_hours",
                    color="failure_severity", size="downtime_hours",
                    category_orders={"failure_severity": order},
                    color_discrete_map=SEVERITY_COLORS,
                    hover_data=["machine_id", "root_cause_category"],
                    title="Pre-Failure Max Temperature vs Downtime",
                    labels={"max_temperature_c_72h": "Max temperature, 72h before (°C)", "downtime_hours": "Downtime hours"},
                )
                st.plotly_chart(style_fig(fig), width="stretch")

        if "max_vibration_x_72h" in available_sensors:
            with col2:
                fig = px.scatter(
                    df, x="max_vibration_x_72h", y="downtime_hours",
                    color="root_cause_category", size="downtime_hours",
                    color_discrete_sequence=NEON,
                    hover_data=["machine_id", "failure_severity"],
                    title="Pre-Failure Max Vibration vs Downtime",
                    labels={"max_vibration_x_72h": "Max vibration, 72h before", "downtime_hours": "Downtime hours"},
                )
                st.plotly_chart(style_fig(fig), width="stretch")

        col3, col4 = st.columns(2)

        if "max_motor_current_a_72h" in available_sensors and "min_lubricant_quality_72h" in available_sensors:
            with col3:
                fig = px.scatter(
                    df, x="max_motor_current_a_72h", y="min_lubricant_quality_72h",
                    color="failure_severity", size="downtime_hours",
                    category_orders={"failure_severity": order},
                    color_discrete_map=SEVERITY_COLORS,
                    hover_data=["machine_id", "root_cause_category"],
                    title="Motor Current vs Lubricant Quality",
                    labels={"max_motor_current_a_72h": "Max motor current, 72h before (A)", "min_lubricant_quality_72h": "Min lubricant quality, 72h before"},
                )
                st.plotly_chart(style_fig(fig), width="stretch")

        with col4:
            numeric_cols = ["downtime_hours"] + available_sensors
            corr = df[numeric_cols].corr()
            fig = px.imshow(
                corr, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
                title="Correlation: Downtime vs Sensor Readings",
                labels={"color": "Correlation"},
            )
            st.plotly_chart(style_fig(fig), width="stretch")


# --------------------------------------------------------------------------
# Tab 4: Raw Data
# --------------------------------------------------------------------------

with tab_raw:
    st.dataframe(df, width="stretch")
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download filtered data as CSV", data=csv_bytes, file_name="failure_records_filtered.csv", mime="text/csv")