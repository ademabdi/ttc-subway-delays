"""TTC subway delay dashboard.

Run from the project root (after `dbt build`):
    streamlit run dashboard/app.py

Reads the dbt marts in ttc.duckdb. Each query opens a READ-ONLY connection and
closes it straight away, so the database isn't locked while the app is open.
(If a query happens to run at the same moment as `dbt build`, just refresh.)
"""
from pathlib import Path

import altair as alt
import duckdb
import streamlit as st

DB = Path(__file__).resolve().parent.parent / "ttc.duckdb"

# TTC line colours (Line 1 yellow darkened slightly so it shows on white;
# checked for colour-blind separation). Colour always follows the line.
LINE_NAMES = {"YU": "Line 1 Yonge-University", "BD": "Line 2 Bloor-Danforth", "SHP": "Line 4 Sheppard"}
LINE_COLOURS = alt.Scale(domain=list(LINE_NAMES.values()), range=["#d9a400", "#00923f", "#a21a68"])
BLUE = "#2a78d6"   # single-series charts
GRID = "#e6e5e1"


@st.cache_data(ttl=600)
def query(sql: str, params: tuple = ()):
    con = duckdb.connect(str(DB), read_only=True)
    try:
        return con.execute(sql, list(params)).df()
    finally:
        con.close()


def line_label(df, col="line"):
    df["line_name"] = df[col].map(LINE_NAMES)
    return df


def style(chart, height):
    return (chart.properties(height=height)
            .configure_axis(gridColor=GRID, domainColor=GRID, tickColor=GRID,
                            labelColor="#52514e", titleColor="#52514e", labelFontSize=12)
            .configure_view(strokeWidth=0)
            .configure_legend(orient="top", title=None, labelColor="#52514e", labelFontSize=12))


st.set_page_config(page_title="TTC Subway Delays", layout="wide")

if not DB.exists():
    st.error(f"Database not found at {DB}. Run `python db.py` and `dbt build --profiles-dir .` first.")
    st.stop()

# ---------------------------------------------------------------- header + filter
period = query("select min(delay_date) first, max(delay_date) last from fct_subway_delays").iloc[0]
st.title("TTC Subway Delays")
st.caption(f"{period['first']:%b %d, %Y} – {period['last']:%b %d, %Y} · Source: Toronto Open Data, "
           "TTC Subway Delay Data + TTC Subway Ridership 2023–2024")

chosen = st.multiselect("Lines", options=list(LINE_NAMES), default=list(LINE_NAMES),
                        format_func=LINE_NAMES.get)
if not chosen:
    st.info("Pick at least one line.")
    st.stop()
lines = tuple(chosen)
in_lines = f"({','.join('?' * len(lines))})"

# ---------------------------------------------------------------- headline numbers
k = query(f"""
    select count(*) as incidents,
           count(*) filter (where min_delay > 0) as delays,
           coalesce(sum(min_delay), 0) as total_minutes,
           avg(case when station_name is not null then 1.0 else 0 end) as mapped
    from fct_subway_delays where line in {in_lines}""", lines).iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Incidents logged", f"{k.incidents:,.0f}")
c2.metric("Incidents that delayed service", f"{k.delays:,.0f}",
          help="Min Delay > 0. The rest are logged incidents that didn't stop trains.")
c3.metric("Minutes of delay", f"{k.total_minutes:,.0f}")
c4.metric("Matched to a station", f"{k.mapped:.0%}",
          help="Share of incidents mapped to one of the 70 stations (see seeds/station_mapping.csv).")
other = query("select count(*) as n from fct_subway_delays "
              "where line is null or line not in ('YU', 'BD', 'SHP')").iloc[0]["n"]
st.caption(f"Counts cover Lines 1, 2 and 4. {other:,} records logged against several lines, "
           "a bus route, or no line are left out.")

# ---------------------------------------------------------------- 1. raw vs per-rider
st.subheader("Which stations are worst? It depends how you count")
st.markdown("**Left:** total weekday minutes of delay. **Right:** the same minutes relative to how many "
            "people use the station. Busy hubs drop out and small stations rise to the top.")

rates = line_label(query(f"""
    select station_name, line, weekday_station_usage, minutes_lost, delay_incidents,
           minutes_lost_per_100k_users
    from mart_station_delay_rates where line in {in_lines}""", lines))
rates["station"] = rates["station_name"] + " (" + rates["line"] + ")"
TOP = 15
tip = [alt.Tooltip("station:N", title="Station"),
       alt.Tooltip("line_name:N", title="Line"),
       alt.Tooltip("minutes_lost:Q", title="Weekday minutes lost", format=",.0f"),
       alt.Tooltip("delay_incidents:Q", title="Delays (>0 min)", format=",.0f"),
       alt.Tooltip("weekday_station_usage:Q", title="Weekday station users", format=",.0f"),
       alt.Tooltip("minutes_lost_per_100k_users:Q", title="Minutes / day / 100k users", format=".1f")]


def ranked_bars(df, measure, title):
    top = df.nlargest(TOP, measure)
    return (alt.Chart(top).mark_bar(cornerRadiusEnd=4, height={"band": 0.7})
            .encode(y=alt.Y("station:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220)),
                    x=alt.X(f"{measure}:Q", title=title),
                    color=alt.Color("line_name:N", scale=LINE_COLOURS),
                    tooltip=tip))


left, right = st.columns(2)
with left:
    st.altair_chart(style(ranked_bars(rates, "minutes_lost", "Total weekday minutes lost"), 430),
                    use_container_width=True)
with right:
    st.altair_chart(style(ranked_bars(rates, "minutes_lost_per_100k_users",
                                      "Minutes lost per day, per 100k station users"), 430),
                    use_container_width=True)
st.caption("Weekdays only (ridership is a typical weekday). Ridership is Sep 2023–Aug 2024 and counts "
           "entries + exits. A delay at a small station also delays everyone riding through it, so "
           "per-user rates favour big stations — read both views together. See docs/decisions.md #14–17.")
with st.expander("Table: all stations"):
    st.dataframe(rates[["station_name", "line_name", "weekday_station_usage", "delay_incidents",
                        "minutes_lost", "minutes_lost_per_100k_users"]]
                 .sort_values("minutes_lost_per_100k_users", ascending=False),
                 hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- 2. when
st.subheader("When do delays happen?")
by_hour = query(f"""
    select hour(delay_ts) as hour,
           case when day_of_week in ('Saturday','Sunday') then 'Weekend' else 'Weekday' end as day_type,
           count(*) filter (where min_delay > 0)
             / count(distinct delay_date) as delays_per_day
    from fct_subway_delays where line in {in_lines}
    group by all""", lines)
by_month = line_label(query(f"""
    select date_trunc('month', delay_date) as month, line, sum(min_delay) as minutes_lost
    from fct_subway_delays where line in {in_lines}
    group by all order by 1""", lines))

h, m = st.columns(2)
with h:
    day_type = st.radio("Days", ["Weekday", "Weekend"], horizontal=True)
    chart = (alt.Chart(by_hour[by_hour.day_type == day_type])
             .mark_bar(color=BLUE, cornerRadiusEnd=4, width={"band": 0.75})
             .encode(x=alt.X("hour:O", title="Hour of day", axis=alt.Axis(labelAngle=0)),
                     y=alt.Y("delays_per_day:Q", title="Delays per day (avg)"),
                     tooltip=[alt.Tooltip("hour:O", title="Hour"),
                              alt.Tooltip("delays_per_day:Q", title="Delays per day", format=".2f")]))
    st.altair_chart(style(chart, 320), use_container_width=True)
with m:
    st.markdown("**Minutes of delay per month, by line**")
    hover = alt.selection_point(fields=["month"], nearest=True, on="pointerover", empty=False)
    base = alt.Chart(by_month).encode(
        x=alt.X("month:T", title=None),
        y=alt.Y("minutes_lost:Q", title="Minutes lost"),
        color=alt.Color("line_name:N", scale=LINE_COLOURS))
    lines_layer = base.mark_line(strokeWidth=2)
    points = base.mark_point(size=60, filled=True).encode(
        opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("month:T", title="Month", format="%b %Y"),
                 alt.Tooltip("line_name:N", title="Line"),
                 alt.Tooltip("minutes_lost:Q", title="Minutes lost", format=",.0f")]).add_params(hover)
    rule = alt.Chart(by_month).mark_rule(color="#a3a29c").encode(x="month:T").transform_filter(hover)
    st.altair_chart(style(alt.layer(lines_layer, points, rule), 360), use_container_width=True)

st.markdown("**Delays by day and hour**")
heat = query(f"""
    select day_of_week,
           hour(delay_ts) as time_hour,
           count(*)       as delays
    from fct_subway_delays
    where min_delay != 0
      and line in {in_lines}
    group by all""", lines)
days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
chart = (alt.Chart(heat).mark_rect()
         .encode(x=alt.X("time_hour:O", title="Hour of day", axis=alt.Axis(labelAngle=0)),
                 y=alt.Y("day_of_week:N", sort=days, title=None),
                 color=alt.Color("delays:Q", scale=alt.Scale(scheme="blues"), title="Delays"),
                 tooltip=[alt.Tooltip("day_of_week:N", title="Day"),
                          alt.Tooltip("time_hour:O", title="Hour"),
                          alt.Tooltip("delays:Q", title="Delays", format=",")]))
st.altair_chart(style(chart, 340), use_container_width=True)
st.caption("Blank cells around 2–5am are when the subway is closed, not reliable hours.")

# ---------------------------------------------------------------- 3. why
st.subheader("What causes the most lost time?")
codes = query(f"""
    select delay_code,
           coalesce(delay_description, '(not in TTC code list)') as description,
           count(*) filter (where min_delay > 0) as delays,
           sum(min_delay) as minutes_lost
    from fct_subway_delays where line in {in_lines}
    group by all order by minutes_lost desc limit 12""", lines)
codes["label"] = codes["delay_code"] + " · " + codes["description"].str.slice(0, 45)
chart = (alt.Chart(codes).mark_bar(color=BLUE, cornerRadiusEnd=4, height={"band": 0.7})
         .encode(y=alt.Y("label:N", sort="-x", title=None, axis=alt.Axis(labelLimit=380)),
                 x=alt.X("minutes_lost:Q", title="Minutes of delay"),
                 tooltip=[alt.Tooltip("delay_code:N", title="Code"),
                          alt.Tooltip("description:N", title="Description"),
                          alt.Tooltip("delays:Q", title="Delays (>0 min)", format=",.0f"),
                          alt.Tooltip("minutes_lost:Q", title="Minutes lost", format=",.0f")]))
st.altair_chart(style(chart, 380), use_container_width=True)

st.caption("Built with DuckDB, dbt and Streamlit. Data quality notes: docs/data_profile.md · "
           "Decisions: docs/decisions.md")
