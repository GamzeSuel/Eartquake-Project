import threading
import queue
import time
import numpy as np
import streamlit as st
import pandas as pd
from obspy import UTCDateTime, Trace
from obspy.clients.seedlink.easyseedlink import EasySeedLinkClient
from obspy.signal.trigger import classic_sta_lta

st.set_page_config(page_title="EEW Prototype", layout="wide")

# -----------------------------
# 1. Data Queue
# -----------------------------
data_queue = queue.Queue()

# -----------------------------
# 2. SeedLink Listener
# -----------------------------
class SLListener(EasySeedLinkClient):
    def on_data(self, trace):
        data_queue.put(trace)

# =============================
# 🔹 GERÇEK TCP SEEDLINK AYARI
# =============================
# Örnek SeedLink (GFZ Geofon)
# Not: HTTP linkler çalışmaz
client = SLListener("geofon.gfz.de/waveform/status/index.php")
client.select_stream("KO", "FAKI", "HHZ")

# =============================
# 🔹 TEST İÇİN SIMÜLASYON
# =============================
def simulate_trace(station="TEST1"):
    data = np.random.randn(1000)
    trace = Trace(data=data)
    trace.stats.station = station
    trace.stats.starttime = UTCDateTime.now()
    data_queue.put(trace)

# -----------------------------
# 3. STA/LTA P Picker
# -----------------------------
def detect_p(trace, sta=1, lta=20, threshold_on=3.5):
    df = trace.stats.sampling_rate if hasattr(trace.stats, "sampling_rate") else 100
    nsta = int(sta * df)
    nlta = int(lta * df)
    cft = classic_sta_lta(trace.data, nsta, nlta)
    triggers = np.where(cft > threshold_on)[0]
    if len(triggers) > 0:
        pick_time = trace.stats.starttime + triggers[0] / df
        return pick_time
    return None

# -----------------------------
# 4. Multi-istasyon association
# -----------------------------
picks = {}  # {station: pick_time}
MIN_STATIONS = 3
TIME_WINDOW = 5  # saniye

def register_pick(station, pick_time):
    picks[station] = pick_time

def check_event():
    now = UTCDateTime()
    valid_stations = []
    for station, t in picks.items():
        if now - t < TIME_WINDOW:
            valid_stations.append((station, t))
    if len(valid_stations) >= MIN_STATIONS:
        return valid_stations
    return None

# -----------------------------
# 5. Hypocenter tahmini
# -----------------------------
stations_coord = {
    "KRSI": (39.92, 32.85),
    "ISTN": (41.01, 28.97),
    "ANKR": (39.93, 32.86),
}

def estimate_epicenter(pick_data):
    lats = [stations_coord[s][0] for s, t in pick_data if s in stations_coord]
    lons = [stations_coord[s][1] for s, t in pick_data if s in stations_coord]
    if len(lats) == 0:
        return (0, 0)
    return (np.mean(lats), np.mean(lons))

# -----------------------------
# 6. Streamlit Layout
# -----------------------------
st.title("🌍 EEW Prototype Dashboard")
alert_placeholder = st.empty()
status_placeholder = st.empty()

# -----------------------------
# 7. Thread ile veri işleme
# -----------------------------
def eew_loop():
    global picks
    while True:
        try:
            trace = data_queue.get(timeout=1)
        except queue.Empty:
            continue
        station = trace.stats.station
        pick_time = detect_p(trace)
        if pick_time:
            register_pick(station, pick_time)
            event = check_event()
            if event:
                epicenter = estimate_epicenter(event)
                alert_placeholder.markdown(f"⚠️ **Deprem Algılandı!**")
                alert_placeholder.markdown(f"- Episantr (approx): {epicenter}")
                alert_placeholder.markdown(f"- İlgili istasyonlar: {[s for s,t in event]}")
                picks = {}

threading.Thread(target=eew_loop, daemon=True).start()

# -----------------------------
# 8. UI Güncelleme
# -----------------------------
def get_station_status():
    data = []
    now = UTCDateTime()
    for station, t in picks.items():
        age = now - t
        data.append([station, str(t), f"{age:.1f}s"])
    return pd.DataFrame(data, columns=["Station", "Pick Time", "Age (s)"])

def ui_update_loop():
    while True:
        status_placeholder.dataframe(get_station_status())
        time.sleep(1)

threading.Thread(target=ui_update_loop, daemon=True).start()

# -----------------------------
# 9. Test Simülasyon Döngüsü
# -----------------------------
def simulation_loop():
    stations = ["TEST1", "TEST2", "TEST3", "TEST4"]
    while True:
        for s in stations:
            simulate_trace(s)
            time.sleep(1)

threading.Thread(target=simulation_loop, daemon=True).start()