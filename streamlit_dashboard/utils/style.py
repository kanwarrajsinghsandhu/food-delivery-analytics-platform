"""Injected CSS — the design-system spacing/typography scale (spec Part 4.3).

Streamlit's own layout primitives can't hit an 8px spacing scale or normalize KPI-card
heights, so this one CSS block does it. Call inject_style() once per page, right after
st.set_page_config().
"""

import streamlit as st

_CSS = """
<style>
:root{
  --sp-1:8px; --sp-2:16px; --sp-3:24px; --sp-4:32px; --sp-5:48px;
  --ink-1:#0b0b0b; --ink-2:#52514e; --ink-3:#898781;
  --rule:#e1e0d9; --surface:#fcfcfb;
}
@media (prefers-color-scheme: dark){
  :root{ --ink-1:#ffffff; --ink-2:#c3c2b7; --ink-3:#898781; --rule:#2c2c2a; --surface:#1a1a19; }
}

.block-container{
  padding-top: var(--sp-3);
  padding-bottom: var(--sp-5);
  max-width: 1560px;
  padding-left: var(--sp-4);
  padding-right: var(--sp-4);
}

div[data-testid="stHorizontalBlock"]{ gap: var(--sp-3); }

div[data-testid="stMetric"]{
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: 8px;
  padding: var(--sp-2);
  min-height: 104px;
}
div[data-testid="stMetricValue"]{
  font-size: 34px; font-weight: 600; font-variant-numeric: proportional-nums;
}
div[data-testid="stMetricLabel"]{
  font-size: 12px; font-weight: 500; color: var(--ink-3); letter-spacing: .02em;
}

.section-rule{ border-top: 1px solid var(--rule); margin: var(--sp-5) 0 var(--sp-4); }

.page-title{ font-size: 30px; font-weight: 650; color: var(--ink-1); margin: 0 0 4px; }
.page-subtitle{ font-size: 15px; font-weight: 400; color: var(--ink-2); margin: 0 0 var(--sp-1); }

.chips{
  font-size: 13px; font-weight: 500; color: var(--ink-3);
  font-variant-numeric: tabular-nums;
  margin: var(--sp-1) 0 var(--sp-4);
}

.section-h2{ font-size: 20px; font-weight: 600; color: var(--ink-1); margin: 0 0 var(--sp-2); }
.viz-h{ font-size: 15px; font-weight: 600; color: var(--ink-1); margin: 0 0 4px; }
.viz-sub{ font-size: 13px; color: var(--ink-2); margin: 0 0 var(--sp-2); line-height: 1.4; }
.viz-note{ font-size: 12px; color: var(--ink-3); margin: var(--sp-1) 0 0; font-style: italic; }
.viz-note.null-result{ font-style: normal; font-weight: 500; color: var(--ink-2); }

.disabled-filter-note{
  font-size: 12px; color: var(--ink-3); font-style: italic; margin-top: -4px;
}
</style>
"""


def inject_style() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="page-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-subtitle">{subtitle}</div>', unsafe_allow_html=True)


def context_chips(text: str) -> None:
    st.markdown(f'<div class="chips">{text}</div>', unsafe_allow_html=True)


def section_heading(text: str) -> None:
    st.markdown('<div class="section-rule"></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-h2">{text}</div>', unsafe_allow_html=True)


def viz_heading(heading: str, subheading: str) -> None:
    st.markdown(f'<div class="viz-h">{heading}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="viz-sub">{subheading}</div>', unsafe_allow_html=True)


def viz_note(text: str, null_result: bool = False) -> None:
    cls = "viz-note null-result" if null_result else "viz-note"
    st.markdown(f'<div class="{cls}">{text}</div>', unsafe_allow_html=True)
