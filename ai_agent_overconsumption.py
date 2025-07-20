import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest
import sqlite3
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_NAME = "ai_agent"
CREDENTIALS_FILE = "C:\\Users\\Njain\\Downloads\\streamlit-energy-app-466417-c797ef8c435f.json"  # <-- Replace with your actual JSON key filename

# Google Sheets authentication
def connect_to_gsheet():
    scope = [
        "https://docs.google.com//spreadsheets//d//1k2iTyFIb9bANTKpt5fv0ABT5QZrGf3KBrENkX3GiP-Q//edit?gid=0#gid=0",
        "https://console.cloud.google.com//marketplace//product//google//drive.googleapis.com?q=search&referrer=search&inv=1&invt=Ab3MNQ&project=streamlit-energy-app-466417"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    return sheet
# ------------------------- LOAD DATA ------------------------- #
@st.cache_data
def load_data():
    df = pd.read_csv("C:\\Users\\Njain\\Desktop\\data.csv", parse_dates=["Date"])  # Replace with your CSV filename
    return df

df = load_data()

# ---------------------- STREAMLIT SIDEBAR -------------------- #
st.sidebar.title("Overconsumption Settings")
threshold_multiplier = st.sidebar.slider("Threshold Multiplier", 0.5, 3.0, 1.5)

st.title("🏠 AI Agent: Home Energy Overconsumption Detector")

# ---------------------- RAW DATA PREVIEW --------------------- #
if st.checkbox("Show Raw Data"):
    st.write(df.head())

# --------------------- OVERUSE DETECTION --------------------- #
avg = df["Energy_Consumption_kWh"].mean()
std = df["Energy_Consumption_kWh"].std()
threshold = avg + threshold_multiplier * std
df["Overconsumption"] = df["Energy_Consumption_kWh"] > threshold

model = IsolationForest(contamination=0.1, random_state=42)
df["Anomaly"] = model.fit_predict(df[["Energy_Consumption_kWh", "Peak_Hours_Usage_kWh"]])
df["AI_Overconsumption"] = df["Anomaly"] == -1
df["Final_Overuse"] = df["Overconsumption"] | df["AI_Overconsumption"]

# --------------------- ENERGY SAVING TIPS --------------------- #
def generate_energy_tip(row):
    if row["Has_AC"] == 1 and row["Avg_Temperature_C"] > 28:
        return "❄ Set AC to 24°C and use fans to reduce load."
    elif row["Peak_Hours_Usage_kWh"] > 0.6 * row["Energy_Consumption_kWh"]:
        return "🔌 Shift appliance use to non-peak hours."
    elif row["Household_Size"] > 5:
        return "👨‍👩‍👧‍👦 Use energy-efficient appliances for large families."
    else:
        return "✅ Your usage is efficient. Keep it up!"

df["Energy_Tip"] = df.apply(generate_energy_tip, axis=1)

# ------------------ ALERTS TABLE + EXPORT --------------------- #
st.subheader("⚠ Detected Overconsumption")
over_df = df[df["Final_Overuse"]]
st.write(f"🔍 Households with Overuse: {over_df['Household_ID'].nunique()}")
st.dataframe(over_df[["Household_ID", "Date", "Energy_Consumption_kWh", "Peak_Hours_Usage_kWh", "Energy_Tip"]].head())

# Export as CSV
st.download_button(
    label="📥 Download Alerts as CSV",
    data=over_df.to_csv(index=False),
    file_name='overconsumption_alerts.csv',
    mime='text/csv'
)

# ------------------ SAVE TO SQLITE DB ------------------------ #
def save_to_sqlite(df, db_file="alerts.db"):
    conn = sqlite3.connect(db_file)
    df.to_sql("alerts", conn, if_exists="replace", index=False)
    conn.close()

if st.button("💾 Save Alerts to Local DB (SQLite)"):
    try:
        save_to_sqlite(over_df)
        st.success("✅ Saved to local database (alerts.db)!")
    except Exception as e:
        st.error(f"❌ Error saving to SQLite: {e}")

# ------------------ SAVE TO GOOGLE SHEET --------------------- #

    if st.button("📤 Save Alerts to Google Sheet"):
        try:
            sheet = connect_to_gsheet()
            for _, row in over_df.iterrows():
                sheet.append_row([
                str(row["Household_ID"]),
                str(row["Date"].date()),
                round(row["Energy_Consumption_kWh"], 2),
                round(row["Peak_Hours_Usage_kWh"], 2)
            ])
            st.success("✅ Alerts saved to Google Sheets successfully.")
        except Exception as e:
            st.error(f"❌ Save failed: {e}")


# ------------------- HOUSEHOLD PLOT -------------------------- #
st.subheader("📈 Energy Trend for Household")
selected_id = st.selectbox("Select Household ID", df["Household_ID"].unique())
house_data = df[df["Household_ID"] == selected_id]

plt.figure(figsize=(10, 4))
plt.plot(house_data["Date"], house_data["Energy_Consumption_kWh"], label="Energy (kWh)")
plt.axhline(y=threshold, color='r', linestyle='--', label="Overuse Threshold")
plt.legend()
plt.title(f"Energy Use for Household {selected_id}")
plt.xlabel("Date")
plt.ylabel("kWh")
st.pyplot(plt)

# ------------------- LIVE ENERGY TIP -------------------------- #
st.subheader("💡 Energy Tip for Selected Household")
latest_row = house_data.iloc[-1]
tip = generate_energy_tip(latest_row)

if latest_row["Final_Overuse"]:
    st.error("⚠ Overconsumption Detected!")
else:
    st.success("✅ Usage is under control.")

st.info(tip)