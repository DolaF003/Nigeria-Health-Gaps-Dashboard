"""
Nigeria's Income-Health Gap - interactive Streamlit dashboard.

Interactions (assignment requirements):
  1. UI interaction        - sidebar selectbox, year slider, country multiselect, log-scale toggle
  2. Within-visualization  - drag a brush on the scatter; click a bar
  3. Tooltips              - hover any mark for the underlying values
  4. Coordinated views     - brushing the scatter filters the ranked bar;
                             clicking a bar highlights that country in the scatter and the time series

Run:
    pip install -r requirements.txt
    streamlit run app.py
"""
import os
import pandas as pd
import altair as alt
import streamlit as st

st.set_page_config(page_title="Nigeria's Income-Health Gap", layout="wide")

# ---------------------------------------------------------------- palette + fields
COLORS = {"Nigeria": "#C0392B", "Peer country": "#5B8AA6", "Region average": "#95A5A6"}
ROLE_SCALE = alt.Scale(domain=list(COLORS), range=list(COLORS.values()))

OUTCOMES = {
    "Life expectancy (years)":          ("life_exp", "higher is better", False),
    "Under-5 mortality (per 1,000)":    ("u5_mort",  "lower is better",  True),
    "Infant mortality (per 1,000)":     ("inf_mort", "lower is better",  True),
    "Maternal mortality (per 100,000)": ("mat_mort", "lower is better",  True),
}

INDICATORS = {
    "NY.GDP.PCAP.PP.KD": "gdp_pc_ppp", "SP.DYN.LE00.IN": "life_exp",
    "SH.DYN.MORT": "u5_mort", "SP.DYN.IMRT.IN": "inf_mort",
    "SH.STA.MMRT": "mat_mort", "SH.XPD.CHEX.GD.ZS": "hexp_gdp",
    "SH.XPD.CHEX.PC.CD": "hexp_pc", "SI.POV.DDAY": "pov_intl", "SI.POV.GINI": "gini",
}
NAMES = {"NGA": "Nigeria", "GHA": "Ghana", "SEN": "Senegal", "KEN": "Kenya",
         "ETH": "Ethiopia", "ZAF": "South Africa", "SSF": "Sub-Saharan Africa"}


def role(country):
    if country == "Nigeria":
        return "Nigeria"
    if country == "Sub-Saharan Africa":
        return "Region average"
    return "Peer country"


@st.cache_data(show_spinner="Loading World Bank data...")
def load_data():
    """Load the tidy panel. Prefer a local CSV; otherwise pull live from the World Bank."""
    if os.path.exists("nigeria_peers_wide.csv"):
        panel = pd.read_csv("nigeria_peers_wide.csv")
    else:
        import wbgapi as wb
        econ = list(NAMES)
        panel = wb.data.DataFrame(list(INDICATORS), econ, time=range(2000, 2024),
                                  columns="series", skipBlanks=False, labels=False)
        panel = panel.rename(columns=INDICATORS).reset_index()
        panel = panel.rename(columns={"economy": "country_code", "time": "year"})
        panel["year"] = panel["year"].astype(str).str.replace("YR", "", regex=False).astype(int)
        panel["country"] = panel["country_code"].map(NAMES)
    if "role" not in panel.columns:
        panel["role"] = panel["country"].map(role)
    return panel


def asof(panel, col, year):
    """Most recent non-missing value of col at or before `year`, per country."""
    d = panel[panel["year"] <= year].dropna(subset=[col])
    g = d.sort_values("year").groupby("country").last()
    return g[[col, "year"]].rename(columns={"year": col + "_yr"})


def snapshot(panel, outcome, year):
    """Cross-section: each country's income and chosen outcome, as of `year`."""
    inc = asof(panel, "gdp_pc_ppp", year)
    out = asof(panel, outcome, year).rename(columns={outcome: "outcome", outcome + "_yr": "out_yr"})
    snap = inc.join(out, how="inner").reset_index()
    snap["role"] = snap["country"].map(role)
    return snap


# ================================================================ load + sidebar
panel = load_data()

st.title("Nigeria's Income-Health Gap")
st.caption("An interactive look at whether Nigeria's health matches its income, "
           "against six African peers. World Bank data, 2000 to 2023.")

with st.sidebar:
    st.header("Controls")
    out_label = st.selectbox("Health outcome", list(OUTCOMES), index=0)
    outcome, direction, lower_better = OUTCOMES[out_label]
    year = st.slider("Snapshot year", 2000, 2023, 2022, help=(
        "The scatter and bar show each country's most recent value at or before this year."))
    all_countries = [c for c in NAMES.values()]
    picked = st.multiselect("Countries", all_countries, default=all_countries)
    log_x = st.checkbox("Log scale for income", value=True)
    st.markdown("---")
    st.markdown("**How to use**")
    st.markdown(
        "- Drag a box on the scatter to filter the ranked bar.\n"
        "- Click a bar to highlight that country in the scatter and the time series.\n"
        "- Hover any mark for its values.")

if not picked:
    st.warning("Select at least one country in the sidebar.")
    st.stop()

snap = snapshot(panel, outcome, year)
snap = snap[snap["country"].isin(picked)]
ts = panel.dropna(subset=[outcome]).copy()
ts = ts[ts["country"].isin(picked)][["country", "role", "year", outcome]].rename(columns={outcome: "value"})

# ================================================================ KPI row
c1, c2, c3 = st.columns(3)
nga = snap[snap["country"] == "Nigeria"]
peers = snap[snap["role"] == "Peer country"]
if len(nga):
    nga_val = float(nga["outcome"].iloc[0])
    c1.metric(f"Nigeria - {out_label}", f"{nga_val:,.1f}")
    if len(peers):
        peer_med = float(peers["outcome"].median())
        gap = nga_val - peer_med
        c2.metric("Peer median", f"{peer_med:,.1f}")
        # for "lower is better" outcomes, Nigeria being higher is bad -> inverse coloring
        c3.metric("Nigeria vs peer median", f"{gap:+,.1f}",
                  delta=f"{gap:+,.1f}", delta_color="inverse" if lower_better else "normal")
else:
    c1.info("Nigeria has no value at or before this year for this outcome.")

# ================================================================ coordinated charts
brush = alt.selection_interval(name="brush", encodings=["x", "y"])
click = alt.selection_point(name="pick", fields=["country"], on="click", toggle=True, empty=True)

x_scale = alt.Scale(type="log") if log_x else alt.Scale(zero=False)
tips = [
    alt.Tooltip("country:N", title="Country"),
    alt.Tooltip("gdp_pc_ppp:Q", title="Income (PPP $)", format="$,.0f"),
    alt.Tooltip("outcome:Q", title=out_label, format=".1f"),
    alt.Tooltip("out_yr:Q", title="Outcome year", format="d"),
]

scatter = (
    alt.Chart(snap).mark_circle(opacity=0.9).encode(
        x=alt.X("gdp_pc_ppp:Q", scale=x_scale,
                axis=alt.Axis(title="GDP per capita, PPP $" + (" (log scale)" if log_x else ""), format="$,d")),
        y=alt.Y("outcome:Q", scale=alt.Scale(zero=False), axis=alt.Axis(title=out_label)),
        color=alt.condition(brush, alt.Color("role:N", scale=ROLE_SCALE,
                            legend=alt.Legend(title=None, orient="top-left")), alt.value("#D9D9D9")),
        opacity=alt.condition(click, alt.value(1.0), alt.value(0.25)),
        size=alt.value(240),
        tooltip=tips,
    )
    .add_params(brush)
    .properties(height=380, title=f"Income vs {out_label}  -  as of {year}")
)

bar = (
    alt.Chart(snap).transform_filter(brush).mark_bar().encode(
        y=alt.Y("country:N", sort="-x", axis=alt.Axis(title=None)),
        x=alt.X("outcome:Q", axis=alt.Axis(title=out_label)),
        color=alt.Color("role:N", scale=ROLE_SCALE, legend=None),
        opacity=alt.condition(click, alt.value(1.0), alt.value(0.4)),
        tooltip=tips,
    )
    .add_params(click)
    .properties(height=380, title="Ranked (brush the scatter to filter, click a bar to highlight)")
)

lines = (
    alt.Chart(ts).mark_line().encode(
        x=alt.X("year:Q", axis=alt.Axis(title=None, format="d", values=list(range(2000, 2024, 4)))),
        y=alt.Y("value:Q", scale=alt.Scale(zero=False), axis=alt.Axis(title=out_label)),
        color=alt.Color("role:N", scale=ROLE_SCALE, legend=alt.Legend(title=None, orient="top-left")),
        detail="country:N",
        opacity=alt.condition(click, alt.value(1.0), alt.value(0.15)),
        size=alt.condition(click, alt.value(3.5), alt.value(1.5)),
        tooltip=[alt.Tooltip("country:N", title="Country"), alt.Tooltip("year:Q", format="d"),
                 alt.Tooltip("value:Q", title=out_label, format=".1f")],
    )
    .properties(height=300, title=f"{out_label} over time  -  click a bar above to highlight one country")
)

top = alt.hconcat(scatter, bar).resolve_scale(color="shared")
dashboard = alt.vconcat(top, lines).configure_view(strokeOpacity=0).configure_axis(
    labelFontSize=12, titleFontSize=12, grid=True, gridColor="#ECECEC").configure_title(
    fontSize=15, anchor="start")

st.altair_chart(dashboard, use_container_width=True)

with st.expander("What this shows"):
    st.markdown(
        "The scatter places each country by income and the chosen health outcome, as of the "
        "selected year. Drag a box over any region to filter the ranked bar to just those "
        "countries. Click a bar to trace that country through time in the bottom chart. "
        "Across the group, income and health come apart: Nigeria sits near the top on income "
        "yet at the worst end on most health outcomes.")
    st.caption("Source: World Bank World Development Indicators (data.worldbank.org). "
               "Charts built with Altair.")
