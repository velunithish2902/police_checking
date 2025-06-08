import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
import base64
import datetime

# -----------------------------------------------------
# ✅ Set Page Configuration
# -----------------------------------------------------
st.set_page_config(page_title="Traffic Stop Log", layout="wide")

# -----------------------------------------------------
# 🔌 Database Connection
# -----------------------------------------------------
def get_engine():
    return create_engine("postgresql+psycopg2://postgres:292929@localhost:5432/simple_n")


def run_query(query):
    try:
        engine = get_engine()
        return pd.read_sql(query, engine)
    except Exception as e:
        st.error(f"Query failed: {e}")
        return pd.DataFrame()

def show_chart(df, x, y, title, color=None, barmode=None, labels=None, text=None):
    fig = px.bar(df, x=x, y=y, color=color, barmode=barmode, title=title, labels=labels, text=text)
    if text:
        fig.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
    st.plotly_chart(fig)

def show_box_plot(df, x, y, title, labels=None):
    fig = px.box(df, x=x, y=y, title=title, labels=labels)
    st.plotly_chart(fig)

# -----------------------------------------------------
# 🏠 App Title
# -----------------------------------------------------
st.title("🚨 Traffic Stop Insights Dashboard")

# Arrest Rate by Age Group
st.subheader("👮 Arrest Rate by Age Group")
query = """
WITH age_groups AS (
    SELECT
        CASE
            WHEN driver_age < 18 THEN 'Under 18'
            WHEN driver_age BETWEEN 18 AND 25 THEN '18-25'
            WHEN driver_age BETWEEN 26 AND 35 THEN '26-35'
            WHEN driver_age BETWEEN 36 AND 45 THEN '36-45'
            WHEN driver_age BETWEEN 46 AND 60 THEN '46-60'
            ELSE '60+'
        END AS age_group,
        is_arrested
    FROM traffic_stops1
    WHERE driver_age IS NOT NULL
),
arrest_stats AS (
    SELECT
        age_group,
        COUNT(*) AS total_stops,
        SUM(CASE WHEN is_arrested THEN 1 ELSE 0 END) AS arrests,
        ROUND(100.0 * SUM(CASE WHEN is_arrested THEN 1 ELSE 0 END)::numeric / COUNT(*), 2) AS arrest_rate
    FROM age_groups
    GROUP BY age_group
)
SELECT * FROM arrest_stats ORDER BY arrest_rate DESC;
"""
df = run_query(query)
st.dataframe(df)
show_chart(df, x="age_group", y="arrest_rate", title="Arrest Rate by Age Group", color="arrest_rate", labels={"arrest_rate": "Arrest Rate (%)"}, text="arrest_rate")

# Gender Distribution by Country
st.subheader("🌍 Gender Distribution by Country")
query = """
SELECT country_name, driver_gender, COUNT(*) AS stop_count
FROM traffic_stops1
GROUP BY country_name, driver_gender
ORDER BY country_name, stop_count DESC;
"""
df = run_query(query)
st.dataframe(df)
show_chart(df, x="country_name", y="stop_count", color="driver_gender", title="Gender Distribution by Country", barmode="group", labels={"stop_count": "Number of Stops"})

# Search Rate by Race & Gender
st.subheader("🔍 Search Rate by Race & Gender")
query = """
WITH base AS (
    SELECT driver_race, driver_gender,
        COUNT(*) AS total_stops,
        SUM(CASE WHEN search_conducted THEN 1 ELSE 0 END) AS total_searches
    FROM traffic_stops1
    GROUP BY driver_race, driver_gender
)
SELECT *, ROUND(100.0 * total_searches::numeric / total_stops, 2) AS search_rate
FROM base
ORDER BY search_rate DESC;
"""
df = run_query(query)
st.dataframe(df)
show_chart(df, x="driver_race", y="search_rate", color="driver_gender", barmode="group", title="Search Rate by Race and Gender", labels={"search_rate": "Search Rate (%)"})

# Traffic Stops by Hour
st.subheader("⏰ Traffic Stops by Hour")
query = """
SELECT EXTRACT(HOUR FROM stop_time) AS hour, COUNT(*) AS total_stops
FROM traffic_stops1
WHERE stop_time IS NOT NULL
GROUP BY hour
ORDER BY hour;
"""
df = run_query(query)
st.dataframe(df)
show_chart(df, x="hour", y="total_stops", title="Traffic Stops by Hour", labels={"total_stops": "Number of Stops"})

# Avg Stop Duration by Violation
st.subheader("⌛ Avg Stop Duration by Violation")
query = """
SELECT violation,
       ROUND(AVG(
           CASE
               WHEN stop_duration ~ '^[0-9]+$' THEN CAST(stop_duration AS numeric)
               WHEN stop_duration ~ '^[0-9]+:[0-9]{2}:[0-9]{2}$' THEN EXTRACT(EPOCH FROM stop_duration::interval) / 60
               ELSE NULL
           END
       ), 2) AS avg_duration
FROM traffic_stops1
WHERE stop_duration IS NOT NULL
GROUP BY violation
ORDER BY avg_duration DESC;
"""
df = run_query(query)
st.dataframe(df)
show_box_plot(df, x="violation", y="avg_duration", title="Avg Stop Duration by Violation", labels={"avg_duration": "Duration (min)"})

# Arrest Rate: Day vs Night
st.subheader("🌙 Arrest Rate: Day vs Night")
query = """
WITH time_class AS (
    SELECT *,
        CASE WHEN EXTRACT(HOUR FROM stop_time) < 6 OR EXTRACT(HOUR FROM stop_time) >= 18 THEN 'Night' ELSE 'Day' END AS time_of_day
    FROM traffic_stops1
    WHERE stop_time IS NOT NULL AND is_arrested IS NOT NULL
)
SELECT time_of_day,
       COUNT(*) AS total_stops,
       SUM(CASE WHEN is_arrested THEN 1 ELSE 0 END) AS arrests,
       ROUND(100.0 * SUM(CASE WHEN is_arrested THEN 1 ELSE 0 END)::numeric / COUNT(*), 2) AS arrest_rate
FROM time_class
GROUP BY time_of_day;
"""
df = run_query(query)
st.dataframe(df)
fig = px.pie(df, names="time_of_day", values="arrest_rate", title="Arrest Rate: Day vs Night", color_discrete_sequence=px.colors.sequential.RdBu)
fig.update_traces(textinfo='label+percent', pull=[0.05, 0.05])
st.plotly_chart(fig)

# -----------------------------------------------------
# 📝 Add New Police Log & Predict Outcome
# -----------------------------------------------------
st.title("🚔 Add New Police Log & Predict Outcome and Violation")
selected_date = st.date_input("Select Stop Date", datetime.date.today())
stop_date = selected_date.strftime("%Y-%m-%d")
stop_time = st.text_input("Stop Time (HH:MM:SS)")
county_name = st.text_input("County Name")
driver_gender = st.selectbox("Driver Gender", ["Male", "Female"])
driver_age = st.number_input("Driver Age", min_value=16, max_value=100)
driver_race = st.text_input("Driver Race")
was_search_conducted = st.selectbox("Was a Search Conducted?", ["No", "Yes"])
search_type = st.text_input("Search Type")
drug_related = st.selectbox("Was it Drug Related?", ["No", "Yes"])
stop_duration = st.selectbox("Stop Duration", ["0-15 Min", "16-30 Min", "30+ Min"])
vehicle_number = st.text_input("Vehicle Number")

# Background Style
st.markdown("""
    <style>
    .stApp {
        background-image: url("https://i.pinimg.com/originals/89/33/79/8933793edc44ee2962c58dd81eab0859.jpg");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }
    </style>
""", unsafe_allow_html=True)

# Advanced Insights Header
st.markdown("""
    <style>
        .title-container {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .title-icon {
            font-size: 30px;
        }
        .title-text {
            font-size: 28px;
            font-weight: 600;
        }
    </style>
    <div class="title-container">
        <div class="title-icon">🧩</div>
        <div class="title-text">Advanced Insights</div>
    </div>
""", unsafe_allow_html=True)

# Optional query section
query_option = st.selectbox("Select a Query to Run", ["Top 5 Most Frequent Search Types"])
if st.button("Run Query"):
    if query_option == "Top 5 Most Frequent Search Types":
        df = run_query("SELECT search_type, COUNT(*) AS frequency FROM traffic_stops1 GROUP BY search_type ORDER BY frequency DESC LIMIT 5;")
        st.dataframe(df)

# Outcome Summary
if st.button("Predict Stop Outcome & Violation"):
    try:
        summary = (
            f"🚗 A {int(driver_age)}-year-old {driver_gender.lower()} driver was stopped"
            f" for Speeding at {stop_time}. "
            f"{'A search was conducted' if was_search_conducted == 'Yes' else 'No search was conducted'}, "
            f"and he received a citation. "
            f"The stop lasted {stop_duration.lower()} "
            f"and was {'drug-related' if drug_related == 'Yes' else 'not drug-related'}."
        )
        st.markdown("### 📰 Officer Report Summary")
        st.markdown(summary)
    except Exception as e:
        st.error(f"Error generating summary: {e}")

# Footer
st.title("🚦 Safe Drive Save Life")
