"""Validated design-system tokens — see DASHBOARD_REDESIGN_SPEC.md Part 4.

Every color below was run through the dataviz skill's palette validator (light mode,
2026-09-29). Plotly cannot read CSS custom properties, so chart colors are the light-mode
hex values directly; the CSS injected by style.py handles the light/dark swap for HTML
chrome (headings, KPI cards, chips). This is a known, accepted scope limit — see the
Method page's design-system note.
"""

# --- Identity / series colors (max 3 hues on any scatter/bubble/density chart) ---
SERIES_1 = "#2a78d6"   # primary: GMV, the main single-series line, selected state
SERIES_2 = "#eb6834"   # the one supporting series (e.g. share-of-value vs share-of-customers)
SERIES_3 = "#1baf7a"   # third identity slot only — ships with direct labels (2.74:1 contrast)

# --- Sequential (magnitude) — one hue, light -> dark. Never diverging on a magnitude measure. ---
SEQUENTIAL_SCALE = [[0.0, "#cde2fb"], [1.0, "#0d366b"]]
SEQUENTIAL_SCALE_PX = "Blues"  # plotly express named-scale equivalent for continuous color args

# --- Ordinal (3-step, ordered categories e.g. 7d/14d/30d windows) ---
ORDINAL_RAMP = ["#86b6ef", "#2a78d6", "#104281"]

# --- Reference / status tokens ---
REFERENCE_RULE = "#898781"       # pooled-average lines, the 30-min threshold rule
STATUS_GOOD = "#0ca30c"          # Delivered
STATUS_WARNING = "#fab219"       # Refunded
STATUS_CRITICAL = "#d03b3b"      # Cancelled
NEUTRAL_SUPPRESSED = "#e1e0d9"   # cells below minimum sample size (light mode)

STATUS_COLOR_MAP = {
    "Delivered": STATUS_GOOD,
    "Cancelled": STATUS_CRITICAL,
    "Refunded": STATUS_WARNING,
}
STATUS_ORDER = ["Delivered", "Cancelled", "Refunded"]

# --- Ink / surface tokens (mirrors the CSS vars in style.py) ---
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
SURFACE = "#fcfcfb"

FONT_FAMILY = "system-ui, -apple-system, 'Segoe UI', sans-serif"

CHART_MARGIN = dict(l=56, r=24, t=8, b=48)


def base_layout(height: int, **overrides) -> dict:
    """Shared Plotly layout: design-system font, margins, surface, no title (HTML carries it)."""
    layout = dict(
        template="plotly_white",
        height=height,
        font=dict(family=FONT_FAMILY, color=INK_PRIMARY, size=12),
        margin=CHART_MARGIN,
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        title=None,
    )
    layout.update(overrides)
    return layout


def gridline_axis(**overrides) -> dict:
    """Solid hairline gridline, one shade off surface — never dashed."""
    axis = dict(gridcolor=GRIDLINE, gridwidth=1, zeroline=False, showline=False)
    axis.update(overrides)
    return axis
