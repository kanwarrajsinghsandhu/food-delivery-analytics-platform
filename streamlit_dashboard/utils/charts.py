"""Figure factories — every chart on the analytical pages is built here so the design
system (spec Part 4) is enforced in one place rather than re-implemented per page.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.theme import (
    SERIES_1,
    SERIES_2,
    SEQUENTIAL_SCALE,
    ORDINAL_RAMP,
    REFERENCE_RULE,
    STATUS_COLOR_MAP,
    STATUS_ORDER,
    NEUTRAL_SUPPRESSED,
    base_layout,
    gridline_axis,
)


# ---------------------------------------------------------------------------
# V1.1 + V1.2 — GMV hero with order-volume companion panel
# ---------------------------------------------------------------------------
def gmv_hero_figure(monthly_df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.73, 0.27], vertical_spacing=0.06,
    )
    fig.add_trace(
        go.Scatter(
            x=monthly_df["MONTH"], y=monthly_df["GMV_CAD"],
            mode="lines", name="GMV (CAD)",
            line=dict(color=SERIES_1, width=2),
            fill="tozeroy", fillcolor="rgba(42,120,214,0.12)",
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Bar(
            x=monthly_df["MONTH"], y=monthly_df["ORDERS"],
            name="Orders", marker=dict(color=SERIES_1),
        ),
        row=2, col=1,
    )
    fig.update_layout(**base_layout(410), showlegend=False)
    fig.update_yaxes(title_text="GMV (CAD)", tickprefix="$", rangemode="tozero", row=1, col=1, **gridline_axis())
    fig.update_yaxes(title_text="Orders", rangemode="tozero", row=2, col=1, **gridline_axis())
    fig.update_xaxes(row=2, col=1, **gridline_axis())
    fig.update_xaxes(row=1, col=1, showgrid=False)
    return fig


# ---------------------------------------------------------------------------
# V1.3 — Monthly active customers
# ---------------------------------------------------------------------------
def mau_line_figure(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=df["MONTH"], y=df["MONTHLY_ACTIVE_USERS"],
            mode="lines+markers", line=dict(color=SERIES_1, width=2),
            marker=dict(size=4),
        )
    )
    fig.update_layout(**base_layout(280))
    fig.update_yaxes(title_text="Customers", rangemode="tozero", **gridline_axis())
    fig.update_xaxes(**gridline_axis())
    return fig


# ---------------------------------------------------------------------------
# V1.4 — Monthly retention rate (fixed 60-100% axis)
# ---------------------------------------------------------------------------
def retention_line_figure(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=df["MONTH"], y=df["MONTHLY_RETENTION_RATE"] * 100,
            mode="lines+markers", line=dict(color=SERIES_1, width=2),
            marker=dict(size=4),
        )
    )
    fig.update_layout(**base_layout(280))
    fig.update_yaxes(title_text="Retention %", range=[60, 100], dtick=5, **gridline_axis())
    fig.update_xaxes(**gridline_axis())
    return fig


# ---------------------------------------------------------------------------
# V1.5 — Delivery time distribution with the 30-min proxy threshold drawn on it
# ---------------------------------------------------------------------------
def delivery_distribution_figure(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=df["DELIVERY_TIME_MIN"], y=df["ORDERS"],
            marker=dict(color=SERIES_1),
        )
    )
    fig.add_vline(
        x=30, line=dict(color=REFERENCE_RULE, width=1.5),
        annotation_text="30-min proxy threshold", annotation_position="top",
        annotation=dict(font=dict(size=11, color=REFERENCE_RULE)),
    )
    fig.update_layout(**base_layout(300))
    fig.update_xaxes(title_text="Delivery time (minutes)", dtick=10, **gridline_axis())
    fig.update_yaxes(title_text="Delivered orders", rangemode="tozero", **gridline_axis())
    return fig


# ---------------------------------------------------------------------------
# V1.6 — Order outcome mix over time (100% stacked, fixed status colors)
# ---------------------------------------------------------------------------
def outcome_mix_figure(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for status in STATUS_ORDER:
        col = f"{status.upper()}_SHARE"
        if col in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["MONTH"], y=df[col] * 100,
                    mode="lines", name=status, stackgroup="one",
                    line=dict(width=0.5, color=STATUS_COLOR_MAP[status]),
                    fillcolor=STATUS_COLOR_MAP[status],
                )
            )
    fig.update_layout(**base_layout(280), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
    fig.update_yaxes(title_text="% of orders", range=[0, 100], **gridline_axis())
    fig.update_xaxes(**gridline_axis())
    return fig


# ---------------------------------------------------------------------------
# V1.7 — Top cuisine tags by GMV (single hue, sorted desc)
# ---------------------------------------------------------------------------
def cuisine_bar_figure(df: pd.DataFrame) -> go.Figure:
    d = df.sort_values("GMV_CAD")
    fig = go.Figure(
        go.Bar(
            x=d["GMV_CAD"], y=d["CUISINE_TAG"], orientation="h",
            marker=dict(color=SERIES_1),
            text=d["GMV_CAD"].map(lambda v: f"${v/1e6:.1f}M"),
            textposition="outside",
        )
    )
    fig.update_layout(**base_layout(280))
    fig.update_xaxes(title_text="GMV (CAD)", tickprefix="$", rangemode="tozero", **gridline_axis())
    fig.update_yaxes(title_text=None, **gridline_axis())
    return fig


# ---------------------------------------------------------------------------
# V2.1 — Value concentration by segment (paired tornado bars)
# ---------------------------------------------------------------------------
def concentration_hero_figure(df: pd.DataFrame) -> go.Figure:
    d = df.sort_values("VALUE_SHARE")
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=d["SEGMENT_LABEL"], x=-d["CUSTOMER_SHARE"] * 100, orientation="h",
            name="Share of customers", marker=dict(color=SERIES_1),
            text=(d["CUSTOMER_SHARE"] * 100).map(lambda v: f"{v:.1f}%"),
            textposition="outside",
        )
    )
    fig.add_trace(
        go.Bar(
            y=d["SEGMENT_LABEL"], x=d["VALUE_SHARE"] * 100, orientation="h",
            name="Share of value", marker=dict(color=SERIES_2),
            text=(d["VALUE_SHARE"] * 100).map(lambda v: f"{v:.1f}%"),
            textposition="outside",
        )
    )
    max_val = max(d["CUSTOMER_SHARE"].max(), d["VALUE_SHARE"].max()) * 100 * 1.35
    fig.update_layout(
        **base_layout(380),
        barmode="overlay",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(
        title_text="% of customers  <—   —>  % of value",
        range=[-max_val, max_val],
        tickvals=[-max_val * 0.8, -max_val * 0.4, 0, max_val * 0.4, max_val * 0.8],
        ticktext=[f"{max_val*0.8:.0f}%", f"{max_val*0.4:.0f}%", "0", f"{max_val*0.4:.0f}%", f"{max_val*0.8:.0f}%"],
        **gridline_axis(),
    )
    fig.update_yaxes(title_text=None)
    return fig


# ---------------------------------------------------------------------------
# V2.2 — Recency x Frequency density (SQL-binned cells, single-hue sequential)
# ---------------------------------------------------------------------------
def rf_density_figure(df: pd.DataFrame) -> go.Figure:
    pivot = df.pivot(index="FREQ_BIN_LABEL", columns="RECENCY_BIN_LABEL", values="CUSTOMERS").fillna(0)
    pivot = pivot.reindex(sorted(pivot.index, key=lambda s: float(s.split("-")[0])))
    pivot = pivot[sorted(pivot.columns, key=lambda s: float(s.split("-")[0]))]
    fig = go.Figure(
        go.Heatmap(
            z=pivot.values, x=pivot.columns, y=pivot.index,
            colorscale=SEQUENTIAL_SCALE,
            colorbar=dict(title="Customers"),
        )
    )
    fig.update_layout(**base_layout(320))
    fig.update_xaxes(title_text="Recency (days since last order)")
    fig.update_yaxes(title_text="Frequency (lifetime orders)")
    return fig


# ---------------------------------------------------------------------------
# V2.3 — Value by customer decile (ordinal ramp interpolated to 10 steps)
# ---------------------------------------------------------------------------
def value_decile_figure(df: pd.DataFrame) -> go.Figure:
    d = df.sort_values("DECILE")
    n = len(d)
    # 3-step ramp interpolated across n steps, darkest at decile 1 (highest value)
    import plotly.colors as pc
    colors = pc.sample_colorscale(
        [[0, ORDINAL_RAMP[2]], [0.5, ORDINAL_RAMP[1]], [1, ORDINAL_RAMP[0]]],
        [i / max(n - 1, 1) for i in range(n)],
    )
    fig = go.Figure(
        go.Bar(
            x=d["DECILE"], y=d["VALUE_SHARE"] * 100,
            marker=dict(color=colors),
            text=(d["VALUE_SHARE"] * 100).map(lambda v: f"{v:.1f}%"),
            textposition="outside",
        )
    )
    fig.update_layout(**base_layout(320))
    fig.update_xaxes(title_text="Value decile (1 = highest value)", dtick=1, **gridline_axis())
    fig.update_yaxes(title_text="% of total value", rangemode="tozero", **gridline_axis())
    return fig


# ---------------------------------------------------------------------------
# V3.1 — Cohort retention heatmap with sample-size suppression
# ---------------------------------------------------------------------------
def cohort_heatmap_figure(pivot_pct: pd.DataFrame, suppressed_mask: pd.DataFrame) -> go.Figure:
    z = pivot_pct.values.copy()
    z_display = np.where(suppressed_mask.values, np.nan, z)
    text = np.where(
        suppressed_mask.values, "",
        np.vectorize(lambda v: "" if pd.isna(v) else f"{v:.0f}%")(z),
    )
    fig = go.Figure(
        go.Heatmap(
            z=z_display, x=pivot_pct.columns, y=pivot_pct.index,
            colorscale=SEQUENTIAL_SCALE, zmin=0, zmax=100,
            text=text, texttemplate="%{text}", textfont={"size": 10},
            colorbar=dict(title="Retention %"),
            hoverongaps=False,
        )
    )
    # overlay suppressed cells as flat neutral squares
    z_supp = np.where(suppressed_mask.values, 1, np.nan)
    fig.add_trace(
        go.Heatmap(
            z=z_supp, x=pivot_pct.columns, y=pivot_pct.index,
            colorscale=[[0, NEUTRAL_SUPPRESSED], [1, NEUTRAL_SUPPRESSED]],
            showscale=False, hoverinfo="skip",
        )
    )
    fig.update_layout(**base_layout(520))
    fig.update_xaxes(title_text="Months since acquisition", dtick=1)
    fig.update_yaxes(title_text="Acquisition cohort", autorange="reversed")
    return fig


# ---------------------------------------------------------------------------
# V3.2 — Selected cohort curve vs platform-weighted benchmark
# ---------------------------------------------------------------------------
def cohort_curve_figure(selected_df: pd.DataFrame, benchmark_df: pd.DataFrame, cohort_label: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=benchmark_df["PERIOD_NUMBER"], y=benchmark_df["RETENTION_RATE"] * 100,
            mode="lines", name="Platform weighted",
            line=dict(color=REFERENCE_RULE, width=1.5),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=selected_df["PERIOD_NUMBER"], y=selected_df["RETENTION_RATE"] * 100,
            mode="lines+markers", name=cohort_label,
            line=dict(color=SERIES_1, width=2), marker=dict(size=5),
        )
    )
    fig.update_layout(**base_layout(320), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
    fig.update_xaxes(title_text="Months since acquisition", **gridline_axis())
    fig.update_yaxes(title_text="Retention %", range=[0, 100], **gridline_axis())
    return fig


# ---------------------------------------------------------------------------
# V3.3 — Activation windows (nested cumulative shares, ordinal ramp)
# ---------------------------------------------------------------------------
def activation_windows_figure(df: pd.DataFrame) -> go.Figure:
    colors = ORDINAL_RAMP + [REFERENCE_RULE]
    fig = go.Figure(
        go.Bar(
            x=df["WINDOW"], y=df["PCT"] * 100,
            marker=dict(color=colors[: len(df)]),
            text=df["PCT"].map(lambda v: f"{v*100:.1f}%"),
            textposition="outside",
        )
    )
    fig.update_layout(**base_layout(320))
    fig.update_xaxes(title_text=None, **gridline_axis())
    fig.update_yaxes(title_text="% of first-time customers", range=[0, 100], **gridline_axis())
    return fig


# ---------------------------------------------------------------------------
# V3.4 — First-order experience diagnostic panel (fixed 0-100%, pooled reference line)
# ---------------------------------------------------------------------------
def diagnostic_panel_figure(df: pd.DataFrame, bucket_col: str, rate_col: str, pooled_rate: float) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            y=df[bucket_col], x=df[rate_col] * 100, orientation="h",
            marker=dict(color=SERIES_1),
            text=df[rate_col].map(lambda v: f"{v*100:.1f}%"),
            textposition="outside",
        )
    )
    fig.add_vline(
        x=pooled_rate * 100, line=dict(color=REFERENCE_RULE, width=1.5),
        annotation_text="platform rate", annotation_position="top",
        annotation=dict(font=dict(size=10, color=REFERENCE_RULE)),
    )
    fig.update_layout(**base_layout(300))
    fig.update_xaxes(title_text="30-day reorder rate", range=[0, 100], **gridline_axis())
    fig.update_yaxes(title_text=None)
    return fig
