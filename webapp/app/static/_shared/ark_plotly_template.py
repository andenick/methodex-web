"""Arcanum Site Kit — ark_plotly_template.py (v1.2)

Shared Plotly theming for SERVER / Streamlit stacks (no DOM/CSS-var access).
Mirrors ark-plotly.js: transparent backgrounds, accent-led colorway, light/dark
variants, and the standard trimmed-modebar config. For Streamlit, pass
`dark=st.session_state.get("ark_theme","dark")=="dark"` so charts follow the toggle.

Usage (Streamlit):
    import plotly.express as px
    from ark_plotly_template import apply, ARK_CONFIG
    fig = px.bar(df, x="state", y="n")
    apply(fig, dark=DARK, accent="#0891b2")
    st.plotly_chart(fig, config=ARK_CONFIG, use_container_width=True)
"""
from __future__ import annotations

_COLORWAY = ["#6b7280", "#0d9488", "#b8860b", "#7c4dff", "#dc2626", "#15803d", "#0891b2"]
_FONT = "system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif"

ARK_CONFIG = {
    "responsive": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}


def ark_layout(dark: bool = True, accent: str = "#1565c0") -> dict:
    fg = "#e7edf3" if dark else "#14181d"
    dim = "#9aa7b4" if dark else "#5a6673"
    line = "#2a313b" if dark else "#dde3ea"
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=_FONT, size=13, color=fg),
        colorway=[accent] + _COLORWAY,
        margin=dict(l=60, r=20, t=16, b=44),
        xaxis=dict(gridcolor=line, zerolinecolor=line, linecolor=line, tickfont=dict(color=dim)),
        yaxis=dict(gridcolor=line, zerolinecolor=line, linecolor=line, tickfont=dict(color=dim)),
        # DNA Universal Graph Contract: legend ALWAYS below the plot (mirrors ark-plotly.js)
        legend=dict(orientation="h", x=0, xanchor="left", y=-0.18, yanchor="top", font=dict(color=fg)),
        # tooltip colors from tokens (fixes the white-on-white hover box)
        hoverlabel=dict(bgcolor=("#161b22" if dark else "#ffffff"), bordercolor=line, font=dict(family=_FONT, color=fg)),
    )


def _dedupe_yaxis_titles(fig):
    """Broken-/dual-axis y-title de-dup (F-9B-05). When a figure stacks subplots
    (yaxis + yaxis2 ... on separate domains) and two y-axes carry the SAME title
    string, Plotly renders them overlapping in the left margin as garbled doubled
    text. Keep the shared title on the first axis and blank the duplicates so one
    legible label remains; distinct per-panel titles are left untouched."""
    seen: set[str] = set()
    for key in sorted(k for k in fig.layout if k == "yaxis" or (k.startswith("yaxis") and k[5:].isdigit())):
        ax = fig.layout[key]
        txt = (getattr(ax.title, "text", None) or "").strip()
        if not txt:
            continue
        if txt in seen:
            ax.title.text = ""
        else:
            seen.add(txt)
    return fig


def apply(fig, dark: bool = True, accent: str = "#1565c0"):
    """Apply the Arcanum theme to a Plotly figure in place; returns it."""
    fig.update_layout(**ark_layout(dark, accent))
    _dedupe_yaxis_titles(fig)
    return fig
