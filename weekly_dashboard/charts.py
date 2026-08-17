"""
charts.py

All chart-building logic for the machine failure dashboard, factored
OUT of Streamlit. Every function here takes a dataframe (plus small
extra args) and returns a Plotly figure object — nothing here calls
st.anything(). That's what makes these functions reusable:

    - failure_streamlit_app.py calls these and then does
      st.plotly_chart(fig) to display them live.
    - build_report.py calls the exact same functions and then does
      fig.write_image(...) to save them as PNGs for the emailed PDF.

If you ever need to tweak how a chart looks, change it ONCE here and
both the live dashboard and the weekly report update together.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data_utils import DAY_ORDER, TIME_OF_DAY_ORDER, SEVERITY_ORDER

NEON = ["#00F5D4", "#FF206E", "#FFD23F", "#7B2FF7", "#00B4D8", "#FF9F1C", "#3AFF8C", "#FF4D97"]
SEVERITY_COLORS = {"Critical": "#FF206E", "Major": "#FF9F1C", "Moderate": "#FFD23F", "Minor": "#3AFF8C"}
TOD_COLORS = {"morning": "#FFD23F", "afternoon": "#FF9F1C", "evening": "#7B2FF7", "night": "#00B4D8"}

BG = "#0E1117"
FONT_COLOR = "#E6E6E6"


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
# Overview tab charts
# --------------------------------------------------------------------------

def breakdowns_per_machine_chart(period_df: pd.DataFrame, since_label: str) -> go.Figure:
    s = period_df["machine_id"].value_counts().sort_index().reset_index()
    s.columns = ["machine_id", "count"]
    fig = px.bar(
        s, x="machine_id", y="count", color="machine_id",
        title=f"Breakdowns per Machine (since {since_label})",
        labels={"machine_id": "Machine ID", "count": "Number of breakdowns"},
        color_discrete_sequence=NEON,
    )
    fig.update_layout(showlegend=False)
    return style_fig(fig)


def downtime_per_machine_chart(period_df: pd.DataFrame, since_label: str) -> go.Figure:
    s = period_df.groupby("machine_id")["downtime_hours"].sum().sort_index().reset_index()
    fig = px.bar(
        s, x="machine_id", y="downtime_hours", color="machine_id",
        title=f"Downtime Hours per Machine (since {since_label})",
        labels={"machine_id": "Machine ID", "downtime_hours": "Downtime hours"},
        color_discrete_sequence=NEON,
    )
    fig.update_layout(showlegend=False)
    return style_fig(fig)


def severity_breakdown_chart(period_df: pd.DataFrame, since_label: str) -> go.Figure:
    s = period_df["failure_severity"].value_counts()
    order = [sev for sev in SEVERITY_ORDER if sev in period_df["failure_severity"].unique()]
    s = s.reindex(order, fill_value=0).reset_index()
    s.columns = ["failure_severity", "count"]
    fig = px.bar(
        s, x="failure_severity", y="count", color="failure_severity",
        title=f"Breakdowns per Severity (since {since_label})",
        labels={"failure_severity": "Severity", "count": "Number of breakdowns"},
        color_discrete_map=SEVERITY_COLORS,
    )
    fig.update_layout(showlegend=False)
    return style_fig(fig)


def heatmap_machine_day_chart(df: pd.DataFrame) -> go.Figure:
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
    return style_fig(fig)


# --------------------------------------------------------------------------
# Deep Dive tab charts
# --------------------------------------------------------------------------

def pareto_chart(df: pd.DataFrame) -> go.Figure:
    s = df["root_cause_category"].value_counts().reset_index()
    s.columns = ["root_cause_category", "count"]
    s["cumulative_pct"] = 100 * s["count"].cumsum() / s["count"].sum()

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=s["root_cause_category"], y=s["count"], name="Breakdowns", marker_color=NEON[0]),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=s["root_cause_category"], y=s["cumulative_pct"], name="Cumulative %",
                   mode="lines+markers", line=dict(color=NEON[1], width=3)),
        secondary_y=True,
    )
    fig.update_yaxes(title_text="Number of breakdowns", secondary_y=False)
    fig.update_yaxes(title_text="Cumulative %", range=[0, 105], secondary_y=True)
    fig.update_yaxes(title_font=dict(color=FONT_COLOR), tickfont=dict(color=FONT_COLOR), secondary_y=True)
    fig.update_layout(title="Pareto: Root Cause Categories")
    return style_fig(fig)


def boxplot_downtime_by_severity_chart(df: pd.DataFrame) -> go.Figure:
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
    return style_fig(fig)


def weekly_downtime_line_chart(df: pd.DataFrame) -> go.Figure:
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
        title="Total Weekly Downtime Hours Over Time",
        yaxis_title="Total downtime hours",
    )
    return style_fig(fig)


def sunburst_chart(df: pd.DataFrame):
    if not df["root_cause_subcategory"].notna().any():
        return None
    fig = px.sunburst(
        df, path=["root_cause_category", "root_cause_subcategory"],
        title="Root Cause Drill-Down",
        color="root_cause_category", color_discrete_sequence=NEON,
    )
    return style_fig(fig)


def polar_clock_chart(df: pd.DataFrame) -> go.Figure:
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
    return style_fig(fig)


# --------------------------------------------------------------------------
# Sensor Insights tab charts
# --------------------------------------------------------------------------

def temp_vs_downtime_chart(df: pd.DataFrame):
    if "max_temperature_c_72h" not in df.columns or not df["max_temperature_c_72h"].notna().any():
        return None
    order = [s for s in SEVERITY_ORDER if s in df["failure_severity"].unique()]
    fig = px.scatter(
        df, x="max_temperature_c_72h", y="downtime_hours",
        color="failure_severity", size="downtime_hours",
        category_orders={"failure_severity": order},
        color_discrete_map=SEVERITY_COLORS,
        hover_data=["machine_id", "root_cause_category"],
        title="Pre-Failure Max Temperature vs Downtime",
        labels={"max_temperature_c_72h": "Max temperature, 72h before (°C)", "downtime_hours": "Downtime hours"},
    )
    return style_fig(fig)


def vibration_vs_downtime_chart(df: pd.DataFrame):
    if "max_vibration_x_72h" not in df.columns or not df["max_vibration_x_72h"].notna().any():
        return None
    fig = px.scatter(
        df, x="max_vibration_x_72h", y="downtime_hours",
        color="root_cause_category", size="downtime_hours",
        color_discrete_sequence=NEON,
        hover_data=["machine_id", "failure_severity"],
        title="Pre-Failure Max Vibration vs Downtime",
        labels={"max_vibration_x_72h": "Max vibration, 72h before", "downtime_hours": "Downtime hours"},
    )
    return style_fig(fig)


def motor_current_vs_lubricant_chart(df: pd.DataFrame):
    needed = ["max_motor_current_a_72h", "min_lubricant_quality_72h"]
    if not all(c in df.columns and df[c].notna().any() for c in needed):
        return None
    order = [s for s in SEVERITY_ORDER if s in df["failure_severity"].unique()]
    fig = px.scatter(
        df, x="max_motor_current_a_72h", y="min_lubricant_quality_72h",
        color="failure_severity", size="downtime_hours",
        category_orders={"failure_severity": order},
        color_discrete_map=SEVERITY_COLORS,
        hover_data=["machine_id", "root_cause_category"],
        title="Motor Current vs Lubricant Quality",
        labels={"max_motor_current_a_72h": "Max motor current, 72h before (A)", "min_lubricant_quality_72h": "Min lubricant quality, 72h before"},
    )
    return style_fig(fig)

def correlation_heatmap_chart(df: pd.DataFrame, available_sensors: list) -> go.Figure:
    numeric_cols = ["downtime_hours"] + available_sensors
    corr = df[numeric_cols].corr()
    fig = px.imshow(
        corr, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
        title="Correlation: Downtime vs Sensor Readings",
        labels={"color": "Correlation"},
    )
    return style_fig(fig)


# --------------------------------------------------------------------------
# Month-over-month comparison charts (used by build_report.py)
# --------------------------------------------------------------------------

MOM_COLORS = [NEON[0], NEON[1]]  # [this month, last month]


def _mom_count_data(this_df: pd.DataFrame, last_df: pd.DataFrame, group_col: str,
                     this_label: str, last_label: str, all_categories=None) -> pd.DataFrame:
    """Builds a long-format dataframe of counts per category per period, zero-filled."""
    if all_categories is None:
        all_categories = sorted(set(this_df[group_col].dropna().unique()) | set(last_df[group_col].dropna().unique()))

    this_counts = this_df[group_col].value_counts().reindex(all_categories, fill_value=0)
    last_counts = last_df[group_col].value_counts().reindex(all_categories, fill_value=0)

    return pd.concat([
        pd.DataFrame({group_col: all_categories, "count": this_counts.values, "period": this_label}),
        pd.DataFrame({group_col: all_categories, "count": last_counts.values, "period": last_label}),
    ])


def _mom_sum_data(this_df: pd.DataFrame, last_df: pd.DataFrame, group_col: str, value_col: str,
                   this_label: str, last_label: str, all_categories=None) -> pd.DataFrame:
    """Builds a long-format dataframe of summed value_col per category per period, zero-filled."""
    if all_categories is None:
        all_categories = sorted(set(this_df[group_col].dropna().unique()) | set(last_df[group_col].dropna().unique()))

    this_sums = this_df.groupby(group_col)[value_col].sum().reindex(all_categories, fill_value=0)
    last_sums = last_df.groupby(group_col)[value_col].sum().reindex(all_categories, fill_value=0)

    return pd.concat([
        pd.DataFrame({group_col: all_categories, value_col: this_sums.values, "period": this_label}),
        pd.DataFrame({group_col: all_categories, value_col: last_sums.values, "period": last_label}),
    ])


def breakdowns_per_machine_mom_chart(this_df: pd.DataFrame, last_df: pd.DataFrame,
                                      this_label: str, last_label: str) -> go.Figure:
    data = _mom_count_data(this_df, last_df, "machine_id", this_label, last_label)
    fig = px.bar(
        data, x="machine_id", y="count", color="period", barmode="group",
        title=f"Breakdowns per Machine: {this_label} vs {last_label}",
        labels={"machine_id": "Machine ID", "count": "Number of breakdowns", "period": ""},
        color_discrete_sequence=MOM_COLORS,
    )
    return style_fig(fig)


def downtime_per_machine_mom_chart(this_df: pd.DataFrame, last_df: pd.DataFrame,
                                    this_label: str, last_label: str) -> go.Figure:
    data = _mom_sum_data(this_df, last_df, "machine_id", "downtime_hours", this_label, last_label)
    fig = px.bar(
        data, x="machine_id", y="downtime_hours", color="period", barmode="group",
        title=f"Downtime Hours per Machine: {this_label} vs {last_label}",
        labels={"machine_id": "Machine ID", "downtime_hours": "Downtime hours", "period": ""},
        color_discrete_sequence=MOM_COLORS,
    )
    return style_fig(fig)


def severity_breakdown_mom_chart(this_df: pd.DataFrame, last_df: pd.DataFrame,
                                  this_label: str, last_label: str) -> go.Figure:
    all_severities = [s for s in SEVERITY_ORDER if s in set(this_df["failure_severity"]) | set(last_df["failure_severity"])]
    data = _mom_count_data(this_df, last_df, "failure_severity", this_label, last_label, all_categories=all_severities)
    fig = px.bar(
        data, x="failure_severity", y="count", color="period", barmode="group",
        category_orders={"failure_severity": all_severities},
        title=f"Breakdowns per Severity: {this_label} vs {last_label}",
        labels={"failure_severity": "Severity", "count": "Number of breakdowns", "period": ""},
        color_discrete_sequence=MOM_COLORS,
    )
    return style_fig(fig)


def weekday_downtime_mom_chart(this_df: pd.DataFrame, last_df: pd.DataFrame,
                                this_label: str, last_label: str) -> go.Figure:
    """Total downtime per day-of-week, this month vs last month."""
    data = _mom_sum_data(this_df, last_df, "day_of_week", "downtime_hours", this_label, last_label, all_categories=DAY_ORDER)
    fig = px.bar(
        data, x="day_of_week", y="downtime_hours", color="period", barmode="group",
        category_orders={"day_of_week": DAY_ORDER},
        title=f"Downtime by Day of Week: {this_label} vs {last_label}",
        labels={"day_of_week": "Day of week", "downtime_hours": "Downtime hours", "period": ""},
        color_discrete_sequence=MOM_COLORS,
    )
    return style_fig(fig)