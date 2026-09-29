"""Reader for the two death counts. Uses the committed extracts."""

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DATA = Path(__file__).resolve().parents[1] / "app" / "data"
NAVY, TEAL, SLATE = "#1e3a5f", "#0f766e", "#64748b"

st.set_page_config(page_title="Denver's two traffic-death counts", layout="wide")
st.markdown(
    """
    <style>
      .block-container {padding-top: 1.4rem;}
      h1, h2, h3 {color: #0f172a;}
    </style>
    """,
    unsafe_allow_html=True,
)

yearly = pd.read_csv(DATA / "yearly.csv")
deaths = pd.read_csv(DATA / "chart_deaths.csv")
ped = pd.read_csv(DATA / "chart_ped.csv")
claims = pd.read_csv(DATA / "claims.csv")
points = pd.read_csv(DATA / "ped_points.csv")
meta = pd.read_json(DATA / "meta.json", typ="series")
y2025 = yearly.set_index("year").loc[2025]

st.title("Denver's two traffic-death counts")
st.caption(
    f"Open crash file retrieved {meta['retrieved']}. "
    "Navy is a published city or Gazette figure. Teal is the open file. "
    "The two are not added together. 2026 is year to date."
)

city_2025 = int(
    deaths[(deaths["year"] == 2025) & (deaths["series"] == "City reported")]["deaths"].iloc[0]
)
c1, c2, c3, c4 = st.columns(4)
c1.metric("City page, 2025", city_2025)
c2.metric("Open file, 2025", int(y2025["file_deaths"]))
c3.metric("Walking deaths in the file", int(y2025["file_ped_deaths"]))
c4.metric("Walking crashes in the file", int(y2025["file_ped_crashes"]))

left, right = st.columns(2)
with left:
    st.subheader("Two counts")
    chart = deaths[deaths["year"].between(2024, 2026)].copy()
    chart["year"] = chart["year"].astype(str)
    fig = px.bar(
        chart,
        x="year",
        y="deaths",
        color="series",
        barmode="group",
        color_discrete_map={"City reported": NAVY, "Open crash file": TEAL},
    )
    fig.update_layout(
        legend_title_text="",
        plot_bgcolor="white",
        paper_bgcolor="white",
        font_color="#0f172a",
        legend=dict(orientation="h", y=1.12),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("2024 uses the Gazette figure of 80. 2025 and 2026 use the city page. The Gazette said 93 for 2025.")

with right:
    st.subheader("People walking")
    file_deaths = ped[ped["series"] == "Pedestrian deaths in the file"].sort_values("year")
    reported_deaths = ped[ped["series"] == "Pedestrian deaths reported by DOTI"].sort_values("year")
    fig2 = go.Figure()
    fig2.add_trace(
        go.Scatter(
            x=file_deaths["year"].astype(str),
            y=file_deaths["value"],
            mode="lines+markers",
            name="Deaths in the open file",
            line={"color": SLATE, "width": 3},
            marker={"size": 9, "color": SLATE},
        )
    )
    fig2.add_trace(
        go.Bar(
            x=reported_deaths["year"].astype(str),
            y=reported_deaths["value"],
            name="Deaths reported by DOTI",
            marker_color=NAVY,
        )
    )
    years = [str(year) for year in range(2021, 2027)]
    fig2.update_layout(
        barmode="group",
        plot_bgcolor="white",
        paper_bgcolor="white",
        font_color="#0f172a",
        legend=dict(orientation="h", y=1.14),
        yaxis_title="Deaths",
        xaxis={
            "type": "category",
            "categoryorder": "array",
            "categoryarray": years,
            "tickmode": "array",
            "tickvals": years,
        },
    )
    st.plotly_chart(fig2, use_container_width=True)
    st.caption("DOTI's pedestrian deaths, via the Denver Gazette, beside the pedestrian deaths the file still records.")

st.subheader("2025 pedestrian crashes")
mapped = points.dropna(subset=["geo_lat", "geo_lon"])
fig3 = px.scatter_map(
    mapped,
    lat="geo_lat",
    lon="geo_lon",
    color="on_hin",
    color_discrete_map={"on network": TEAL, "off network": SLATE},
    hover_data=["neighborhood_id", "LIGHT_CONDITION"],
    zoom=11,
    height=560,
)
fig3.update_layout(map_style="carto-positron", margin={"l": 0, "r": 0, "t": 0, "b": 0})
st.plotly_chart(fig3, use_container_width=True)
share = float(meta["hin_share_2025_ped"])
st.caption(
    f"{share:.0%} of 2025 pedestrian crashes with coordinates fall within "
    f"{int(meta['hin_buffer_m'])} meters of the High Injury Network. "
    "A crash near the network is not a death. The buffer is a choice."
)

st.subheader("Claims")
for _, row in claims.iterrows():
    st.markdown(f"**{row['statement']}**")
    st.write(row["evidence"])
    st.caption(row["caveat"])
