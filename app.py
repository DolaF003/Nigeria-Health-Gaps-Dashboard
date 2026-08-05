"""
Nigeria's Income-Health Gap - interactive Streamlit dashboard (v2).

Refined after usability testing. Changes from v1:
  1. An always-visible hint explains the interactions; the word "brush" is gone.
  2. The scatter is now clickable too (a dot behaves like a bar).
  3. A "Reset view" button clears any selection.
  4. Plainer labels: "average income per person" instead of "GDP per capita, PPP",
     and help tooltips on the metrics.
  5. The axes are explained, with an option to start the health axis at zero.
  6. Titles and tooltips make the "most recent value" behavior clear.
  7. The regional average is drawn as a dashed benchmark line, not a country.
  8. A layout toggle stacks the charts vertically for small screens.

Run:
    pip install -r requirements.txt
    streamlit run app.py
"""
import os
import pandas as pd
import altair as alt
import streamlit as st

st.set_page_config(page_title="Nigeria's Income-Health Gap", layout="wide")

COLORS = {"Nigeria": "#C0392B", "Peer country": "#5B8AA6", "Region average": "#95A5A6"}
ROLE_SCALE = alt.Scale(domain=list(COLORS), range=list(COLORS.values()))
REGION = "Sub-Saharan Africa"
BENCH = "#6E7D89"

OUTCOMES = {
    "Life expectancy (years)":          ("life_exp", False),
    "Under-5 mortality (per 1,000)":    ("u5_mort",  True),
    "Infant mortality (per 1,000)":     ("inf_mort", True),
    "Maternal mortality (per 100,000)": ("mat_mort", True),
}
INDICATORS = {
    "NY.GDP.PCAP.PP.KD": "gdp_pc_ppp", "SP.DYN.LE00.IN": "life_exp",
    "SH.DYN.MORT": "u5_mort", "SP.DYN.IMRT.IN": "inf_mort",
    "SH.STA.MMRT": "mat_mort", "SH.XPD.CHEX.GD.ZS": "hexp_gdp",
    "SH.XPD.CHEX.PC.CD": "hexp_pc", "SI.POV.DDAY": "pov_intl", "SI.POV.GINI": "gini",
}
NAMES = {"NGA": "Nigeria", "GHA": "Ghana", "SEN": "Senegal", "KEN": "Kenya",
         "ETH": "Ethiopia", "ZAF": "South Africa", "SSF": REGION}
COUNTRY_NAMES = ["Nigeria", "Ghana", "Senegal", "Kenya", "Ethiopia", "South Africa"]


def role(c):
    if c == "Nigeria":
        return "Nigeria"
    if c == REGION:
        return "Region average"
    return "Peer country"


@st.cache_data(show_spinner="Loading World Bank data...")
def load_data():
    if os.path.exists("nigeria_peers_wide.csv"):
        panel = pd.read_csv("nigeria_peers_wide.csv")
    else:
        import wbgapi as wb
        panel = wb.data.DataFrame(list(INDICATORS), list(NAMES), time=range(2000, 2024),
                                  columns="series", skipBlanks=False, labels=False)
        panel = panel.rename(columns=INDICATORS).reset_index()
        panel = panel.rename(columns={"economy": "country_code", "time": "year"})
        panel["year"] = panel["year"].astype(str).str.replace("YR", "", regex=False).astype(int)
        panel["country"] = panel["country_code"].map(NAMES)
    if "role" not in panel.columns:
        panel["role"] = panel["country"].map(role)
    return panel


def asof(panel, col, year):
    d = panel[panel["year"] <= year].dropna(subset=[col])
    g = d.sort_values("year").groupby("country").last()
    return g[[col, "year"]].rename(columns={"year": col + "_yr"})


def snapshot(panel, outcome, year, keep):
    inc = asof(panel, "gdp_pc_ppp", year)
    out = asof(panel, outcome, year).rename(columns={outcome: "outcome", outcome + "_yr": "out_yr"})
    snap = inc.join(out, how="inner").reset_index()
    snap["role"] = snap["country"].map(role)
    return snap[snap["country"].isin(keep)]


def region_value(panel, outcome, year):
    d = panel[(panel["country"] == REGION) & (panel["year"] <= year)].dropna(subset=[outcome])
    if len(d):
        r = d.sort_values("year").iloc[-1]
        return float(r[outcome]), int(r["year"])
    return None, None


# ================================================================ sidebar
panel = load_data()
if "reset_nonce" not in st.session_state:
    st.session_state.reset_nonce = 0

st.title("Nigeria's Income-Health Gap")
st.caption("Does Nigeria's health match its income? Compared with five African peers, "
           "with the Sub-Saharan Africa average as a benchmark. World Bank data, 2000 to 2023.")

with st.sidebar:
    st.header("Controls")
    out_label = st.selectbox("Health outcome", list(OUTCOMES), index=0)
    outcome, lower_better = OUTCOMES[out_label]
    year = st.slider("Show values up to", 2000, 2023, 2022, help=(
        "Each country shows its most recent value at or before this year. Some fields "
        "come from periodic surveys, so a value may be from an earlier year, shown in the tooltip."))
    picked = st.multiselect("Countries", COUNTRY_NAMES, default=COUNTRY_NAMES)
    st.markdown("---")
    log_x = st.checkbox("Log scale for income", value=True,
                        help="Spaces the income axis by multiples so South Africa does not flatten the rest.")
    zero_y = st.checkbox("Start the health axis at zero", value=False,
                         help="Off by default so small differences are visible. Turn on to compare absolute size.")
    show_region = st.checkbox("Show Sub-Saharan Africa benchmark", value=True,
                              help="Draws the regional average as a dashed reference line, not a country.")
    stack = st.checkbox("Stack charts vertically (better on phones)", value=False)
    st.markdown("---")
    if st.button("Reset view", help="Clear any selection and show all countries."):
        st.session_state.reset_nonce += 1
    st.caption("Tip: you can also double-click a chart to clear a selection.")

if not picked:
    st.warning("Select at least one country in the sidebar.")
    st.stop()

snap = snapshot(panel, outcome, year, picked)
reg_val, reg_yr = region_value(panel, outcome, year)
ts = panel.dropna(subset=[outcome]).copy()
keep_ts = picked + ([REGION] if show_region else [])
ts = ts[ts["country"].isin(keep_ts)][["country", "role", "year", outcome]].rename(columns={outcome: "value"})

# ================================================================ KPIs
c1, c2, c3 = st.columns(3)
nga = snap[snap["country"] == "Nigeria"]
peers = snap[snap["role"] == "Peer country"]
if len(nga):
    nga_val = float(nga["outcome"].iloc[0])
    c1.metric(f"Nigeria - {out_label}", f"{nga_val:,.1f}")
    if len(peers):
        peer_med = float(peers["outcome"].median())
        gap = nga_val - peer_med
        c2.metric("Peer median", f"{peer_med:,.1f}",
                  help="The middle value among the selected peer countries (Nigeria excluded).")
        c3.metric("Nigeria vs peer median", f"{gap:+,.1f}", delta=f"{gap:+,.1f}",
                  delta_color="inverse" if lower_better else "normal",
                  help="How far Nigeria sits from the peer middle for this outcome.")
else:
    c1.info("Nigeria has no value for this outcome at or before the selected year.")

# ================================================================ interaction hint
st.info("Drag a box across the scatter to filter the ranked list. Click a dot or a bar to "
        "trace that country over time. Hover any mark for its exact values.")

# ================================================================ charts
sel = alt.selection_point(name="pick", fields=["country"], on="click", empty=True)
brush = alt.selection_interval(name="brush", encodings=["x", "y"])

x_scale = alt.Scale(type="log") if log_x else alt.Scale(zero=False)
y_scale = alt.Scale(zero=True) if zero_y else alt.Scale(zero=False)
income_title = "Average income per person (PPP $" + (", log scale" if log_x else "") + ")"
tips = [
    alt.Tooltip("country:N", title="Country"),
    alt.Tooltip("gdp_pc_ppp:Q", title="Average income (PPP $)", format="$,.0f"),
    alt.Tooltip("outcome:Q", title=out_label, format=".1f"),
    alt.Tooltip("out_yr:Q", title="Data year (most recent)", format="d"),
]

scatter = alt.Chart(snap).mark_circle(size=300, opacity=0.9).encode(
    x=alt.X("gdp_pc_ppp:Q", scale=x_scale, axis=alt.Axis(title=income_title, format="$,d")),
    y=alt.Y("outcome:Q", scale=y_scale, axis=alt.Axis(title=out_label)),
    color=alt.condition(brush, alt.Color("role:N", scale=ROLE_SCALE,
                        legend=alt.Legend(title=None, orient="top-left")), alt.value("#D9D9D9")),
    opacity=alt.condition(sel, alt.value(1.0), alt.value(0.3)),
    tooltip=tips,
).add_params(brush, sel).properties(height=360, title=f"Income vs {out_label}  -  latest value by {year}")

bar = alt.Chart(snap).transform_filter(brush).mark_bar().encode(
    y=alt.Y("country:N", sort="-x", axis=alt.Axis(title=None)),
    x=alt.X("outcome:Q", axis=alt.Axis(title=out_label)),
    color=alt.Color("role:N", scale=ROLE_SCALE, legend=None),
    opacity=alt.condition(sel, alt.value(1.0), alt.value(0.45)),
    tooltip=tips,
).add_params(sel).properties(height=360, title="Ranked countries  -  drag the scatter to filter, click to trace")

# regional-average benchmark as dashed reference lines (not a country)
if show_region and reg_val is not None:
    rdf = pd.DataFrame({"v": [reg_val]})
    rule_s = alt.Chart(rdf).mark_rule(color=BENCH, strokeDash=[6, 4], size=1.5).encode(y="v:Q")
    lbl_s = alt.Chart(pd.DataFrame({"v": [reg_val], "t": ["Sub-Saharan Africa avg."]})).mark_text(
        align="left", dx=6, dy=-6, color=BENCH, fontSize=11).encode(y="v:Q", text="t:N")
    scatter = scatter + rule_s + lbl_s
    rule_b = alt.Chart(rdf).mark_rule(color=BENCH, strokeDash=[6, 4], size=1.5).encode(x="v:Q")
    bar = bar + rule_b

lines = alt.Chart(ts).mark_line().encode(
    x=alt.X("year:Q", axis=alt.Axis(title=None, format="d", values=list(range(2000, 2024, 4)))),
    y=alt.Y("value:Q", scale=y_scale, axis=alt.Axis(title=out_label)),
    color=alt.Color("role:N", scale=ROLE_SCALE, legend=alt.Legend(title=None, orient="top-left")),
    detail="country:N",
    strokeDash=alt.condition("datum.role == 'Region average'", alt.value([6, 4]), alt.value([1, 0])),
    opacity=alt.condition(sel, alt.value(1.0), alt.value(0.2)),
    size=alt.condition(sel, alt.value(3), alt.value(1.5)),
    tooltip=[alt.Tooltip("country:N", title="Country"), alt.Tooltip("year:Q", format="d"),
             alt.Tooltip("value:Q", title=out_label, format=".1f")],
).properties(height=300, title=f"{out_label} over time  -  click a country above to trace it")

top = alt.vconcat(scatter, bar) if stack else alt.hconcat(scatter, bar)
dashboard = (alt.vconcat(top, lines).resolve_scale(color="shared")
             .properties(usermeta={"reset": st.session_state.reset_nonce})
             .configure_view(strokeOpacity=0)
             .configure_axis(labelFontSize=12, titleFontSize=12, grid=True, gridColor="#ECECEC")
             .configure_title(fontSize=15, anchor="start"))

st.altair_chart(dashboard, use_container_width=True)

note = "The income axis is spaced by multiples (log scale). " if log_x else ""
note += ("The health axis starts at zero." if zero_y else "The health axis is zoomed to the data range, not starting at zero.")
st.caption(note)

with st.expander("What this shows"):
    st.markdown(
        "Each country appears at its income and chosen health outcome, using its most recent "
        "value at or before the selected year. The dashed line is the Sub-Saharan Africa average, "
        "a benchmark rather than a country. Drag a box on the scatter to filter the ranked list, "
        "and click a dot or a bar to trace that country in the time series. Across the group, "
        "income and health come apart: Nigeria sits near the top on income yet at the worst end "
        "on most health outcomes.")
    st.caption("Source: World Bank World Development Indicators (data.worldbank.org). Built with Altair.")
