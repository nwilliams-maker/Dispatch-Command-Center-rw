import streamlit as st
import requests
import base64
import math
import pandas as pd
import time
import hashlib
import json
from datetime import datetime, timedelta
from streamlit_folium import st_folium
import folium
import threading
import os

# --- CONFIG & CREDENTIALS ---
ONFLEET_KEY = os.environ.get("ONFLEET_KEY")
GOOGLE_MAPS_KEY = os.environ.get("GOOGLE_MAPS_KEY")

if not ONFLEET_KEY or not GOOGLE_MAPS_KEY:
    try:
        ONFLEET_KEY = ONFLEET_KEY or st.secrets.get("ONFLEET_KEY")
        GOOGLE_MAPS_KEY = GOOGLE_MAPS_KEY or st.secrets.get("GOOGLE_MAPS_KEY")
    except Exception: pass

if not ONFLEET_KEY or not GOOGLE_MAPS_KEY:
    st.error("🔑 API Keys Missing!")
    st.stop()

PORTAL_BASE_URL = "https://nwilliams-maker.github.io/Dispatch-Command-Center-rw/portal-dcc-rw.html"
GAS_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbyz16LuLJUJfrtUWxhvK8lGJCVSqRcrqPNOwLEICJ47Oa-BrRnBvFSsy4q8XXo-Y2DTAA/exec"
IC_SHEET_URL = "https://docs.google.com/spreadsheets/d/1y6wX0x93iDc3gdK_nZKLD-2QcGkUHkcM75u90ffRO6k/edit#gid=0"
SAVED_ROUTES_GID = "1477617688"
ACCEPTED_ROUTES_GID = "934075207"
DECLINED_ROUTES_GID = "600909788"
FINALIZED_ROUTES_GID = "2137441498"

TB_PURPLE = "#633094"
TB_GREEN = "#76bc21"
TB_APP_BG = "#f1f5f9"
TB_GREEN_FILL = "#dcfce7" 
TB_BLUE_FILL = "#dbeafe"  
TB_RED_FILL = "#ffcccc"   

POD_CONFIGS = {
    "Blue": {"states": {"AL", "AR", "FL", "IL", "IA", "LA", "MI", "MN", "MS", "MO", "NC", "SC", "WI"}},
    "Green": {"states": {"CO", "DC", "GA", "IN", "KY", "MD", "NJ", "OH", "UT"}},
    "Orange": {"states": {"AK", "AZ", "CA", "HI", "ID", "NV", "OR", "WA"}},
    "Purple": {"states": {"KS", "MT", "NE", "NM", "ND", "OK", "SD", "TN", "TX", "WY"}},
    "Red": {"states": {"CT", "DE", "ME", "MA", "NH", "NY", "PA", "RI", "VT", "VA", "WV"}}
}

STATE_MAP = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR", "CALIFORNIA": "CA",
    "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE", "FLORIDA": "FL", "GEORGIA": "GA",
    "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA",
    "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS",
    "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD", "TENNESSEE": "TN",
    "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY", "DISTRICT OF COLUMBIA": "DC"
}

headers = {"Authorization": f"Basic {base64.b64encode(f'{ONFLEET_KEY}:'.encode()).decode()}"}
st.set_page_config(page_title="Dispatch Command Center", layout="wide")

# --- UI STYLING ---
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
.stApp {{ background-color: {TB_APP_BG} !important; color: #000000 !important; font-family: 'Inter', sans-serif !important; }}
.stTabs [data-baseweb="tab-list"] {{ justify-content: center; gap: 8px; background: transparent !important; padding-bottom: 20px; border-bottom: 2px solid #cbd5e1 !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ background-color: transparent !important; }}
.stTabs [data-baseweb="tab"] {{ border-radius: 30px !important; margin: 0 4px !important; font-weight: 800 !important; padding: 8px 20px !important; transition: all 0.3s ease !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(1) {{ border: 2px solid {TB_PURPLE} !important; color: {TB_PURPLE} !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(2) {{ border: 2px solid #3b82f6 !important; color: #1e3a8a !important; background-color: #f0f7ff !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(3) {{ border: 2px solid #22c55e !important; color: #064e3b !important; background-color: #f0fdf4 !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(4) {{ border: 2px solid #f97316 !important; color: #7c2d12 !important; background-color: #fffaf5 !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(5) {{ border: 2px solid #a855f7 !important; color: #4c1d95 !important; background-color: #faf5ff !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(6) {{ border: 2px solid #ef4444 !important; color: #7f1d1d !important; background-color: #fef2f2 !important; }}
.stTabs [aria-selected="true"] {{ transform: translateY(-4px) !important; box-shadow: 0 10px 20px rgba(0,0,0,0.1) !important; background-color: white !important; }}
div[data-testid="stExpander"] {{ border: 1px solid #cbd5e1 !important; border-radius: 10px !important; background-color: #ffffff !important; margin-bottom: 8px !important; }}
div[data-testid="stExpander"] details summary p {{ color: #000000 !important; font-weight: 800 !important; font-size: 0.85rem !important; }}
button[kind="secondary"] {{ background-color: white !important; color: {TB_PURPLE} !important; border: 2px solid {TB_PURPLE} !important; border-radius: 20px !important; }}
button[kind="primary"] {{ background-color: {TB_GREEN} !important; color: white !important; border-radius: 10px !important; }}
</style>
""", unsafe_allow_html=True)

# --- UTILITIES ---
def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def normalize_state(st_str):
    if not st_str: return "UNKNOWN"
    clean = str(st_str).strip().upper()
    return STATE_MAP.get(clean, clean)

@st.cache_data(ttl=15, show_spinner=False)
def fetch_sent_records_from_sheet():
    try:
        base_url = f"{IC_SHEET_URL.split('/edit')[0]}/export?format=csv&gid="
        sheets = [(DECLINED_ROUTES_GID, "declined"), (ACCEPTED_ROUTES_GID, "accepted"), (SAVED_ROUTES_GID, "sent"), (FINALIZED_ROUTES_GID, "finalized")]
        sent_dict, ghost_routes = {}, {p: [] for p in list(POD_CONFIGS.keys()) + ["UNKNOWN"]}
        for gid, status_label in sheets:
            try:
                df = pd.read_csv(base_url + gid)
                df.columns = [str(c).strip().lower() for c in df.columns]
                if 'json payload' in df.columns:
                    for _, row in df.iterrows():
                        try:
                            p = json.loads(row['json payload'])
                            tids = str(p.get('taskIds', '')).replace('|', ',').split(',')
                            c_name, raw_ts = str(row.get('contractor', 'Unknown')), row.get('date created', '')
                            ts_display = pd.to_datetime(raw_ts).strftime('%m/%d %I:%M %p') if pd.notna(raw_ts) else ""
                            for tid in tids:
                                tid = tid.strip()
                                if tid: sent_dict[tid] = {"name": c_name, "status": status_label, "time": ts_display, "wo": p.get('wo', c_name)}
                        except: continue
            except: continue
        return sent_dict, ghost_routes
    except: return {}, {}

@st.cache_data(show_spinner=False)
def get_gmaps(home, waypoints):
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={home}&destination={home}&waypoints=optimize:true|{'|'.join(waypoints)}&key={GOOGLE_MAPS_KEY}"
    try:
        res = requests.get(url).json()
        if res['status'] == 'OK':
            mi = sum(l['distance']['value'] for l in res['routes'][0]['legs']) * 0.000621371
            hrs = sum(l['duration']['value'] for l in res['routes'][0]['legs']) / 3600
            return round(mi, 1), hrs, f"{int(hrs)}h {int((hrs * 60) % 60)}m"
    except: pass
    return 0, 0, "0h 0m"

def finalize_route_handler(cluster_hash):
    try:
        res = requests.post(GAS_WEB_APP_URL, json={"action": "finalizeRoute", "cluster_hash": cluster_hash}).json()
        if res.get("success"): st.toast("🏁 Route Finalized!")
    except: st.error("Database update failed.")

def move_to_dispatch(cluster_hash, ic_name, pod_name, action_label="Revoked", check_onfleet=False):
    if action_label == "Declined":
        try: requests.post(GAS_WEB_APP_URL, json={"action": "archiveRoute", "cluster_hash": cluster_hash})
        except: pass
    st.session_state[f"reverted_{cluster_hash}"] = True
    st.toast("✅ Route pulled back to Dispatch!")

def instant_revoke_handler(cluster_hash, ic_name, payload_json, pod_name):
    threading.Thread(target=lambda: requests.post(GAS_WEB_APP_URL, json={"action": "revokeRoute", "cluster_hash": cluster_hash, "payload": payload_json})).start()
    move_to_dispatch(cluster_hash, ic_name, pod_name)

# --- CORE ENGINE ---
def process_pod(pod_name, master_bar=None, pod_idx=0, total_pods=1):
    config = POD_CONFIGS[pod_name]
    try:
        fresh_db, _ = fetch_sent_records_from_sheet()
        st.session_state.sent_db = fresh_db
        all_tasks_raw = []
        url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time()*1000)-(80*24*3600*1000)}"
        while url:
            res = requests.get(url, headers=headers).json()
            all_tasks_raw.extend(res.get('tasks', []))
            url = f"https://onfleet.com/api/v2/tasks/all?state=0&lastId={res['lastId']}" if res.get('lastId') else None
        
        pool = []
        for t in all_tasks_raw:
            addr = t.get('destination', {}).get('address', {})
            stt = normalize_state(addr.get('state', ''))
            if stt not in config['states']: continue
            
            # --- DEEP SEARCH TASK EXTRACTION ---
            tt_val = str(t.get('taskType', '')).strip().lower()
            if not tt_val: tt_val = str(t.get('taskDetails', '')).strip().lower()
            for m in (t.get('metadata') or []):
                m_name, m_val = str(m.get('name', '')).lower(), str(m.get('value', '')).lower()
                if "task type" in m_name or any(x in m_val for x in ["digital", "ins", "offline", "kiosk", "removal"]):
                    tt_val += f" {m_val}"
            raw_notes = str(t.get('notes', '')).lower()
            if any(x in raw_notes for x in ["digital", "skykit", "ins", "offline"]): tt_val += f" {raw_notes}"

            db_entry = fresh_db.get(t['id'], {})
            raw_status = db_entry.get('status', 'ready').lower()
            t_status = 'ready' if raw_status == 'declined' else raw_status

            pool.append({
                "id": t['id'], "city": addr.get('city', 'Unknown'), "state": stt,
                "full": f"{addr.get('number','')} {addr.get('street','')}, {addr.get('city','')}, {stt}",
                "lat": t['destination']['location'][1], "lon": t['destination']['location'][0],
                "task_type": tt_val.strip(), "db_status": t_status, "wo": db_entry.get('wo', 'none')
            })

        clusters = []
        while pool:
            anc = pool.pop(0)
            anc_is_dig = any(x in anc['task_type'] for x in ["digital", "ins", "offline", "service"])
            rad = 25 if anc_is_dig else 50
            group, rem = [anc], []
            for t in pool:
                t_is_dig = any(x in t['task_type'] for x in ["digital", "ins", "offline", "service"])
                if anc_is_dig == t_is_dig and haversine(anc['lat'], anc['lon'], t['lat'], t['lon']) <= rad:
                    if anc['db_status'] in ['sent', 'accepted'] and t['wo'] != anc['wo']: rem.append(t)
                    else: group.append(t)
                else: rem.append(t)
            pool = rem
            status = anc['db_status'].capitalize() if anc['db_status'] in ['sent', 'accepted'] else "Ready"
            clusters.append({
                "data": group, "center": [anc['lat'], anc['lon']], "stops": len(set(x['full'] for x in group)),
                "city": anc['city'], "state": anc['state'], "status": status, "is_digital": anc_is_dig,
                "esc_count": sum(1 for x in group if 'escalat' in x['task_type'])
            })
        st.session_state[f"clusters_{pod_name}"] = clusters
    except Exception as e: st.error(f"Error initializing {pod_name}: {e}")

def render_dispatch(i, cluster, pod_name, is_sent=False, is_declined=False):
    task_ids = [str(t['id']).strip() for t in cluster['data']]
    c_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
    stop_metrics = {}
    for t in cluster['data']:
        addr = t['full']
        if addr not in stop_metrics: stop_metrics[addr] = {'t_count': 0, 'digi': 0, 'inst': 0, 'remov': 0, 'c_ad': 0, 'd_ad': 0, 'n_ad': 0, 'oth': 0}
        stop_metrics[addr]['t_count'] += 1
        tt = t['task_type']
        if any(x in tt for x in ["digital", "ins", "offline", "service", "skykit"]): stop_metrics[addr]['digi'] += 1
        elif any(x in tt for x in ["install", "setup", "assembly"]): stop_metrics[addr]['inst'] += 1
        elif "removal" in tt: stop_metrics[addr]['remov'] += 1
        elif any(x in tt for x in ["continuity", "photo", "swap"]): stop_metrics[addr]['c_ad'] += 1
        else: stop_metrics[addr]['n_ad'] += 1

    st.write("### Route Stops")
    loc_pills = {}
    for addr, m in stop_metrics.items():
        pills = []
        if m['digi'] > 0: pills.append(f"🔌 {m['digi']} Digital")
        if m['inst'] > 0: pills.append(f"🛠️ {m['inst']} Kiosk Install")
        if m['remov'] > 0: pills.append(f"🛑 {m['remov']} Kiosk Removal")
        if m['c_ad'] > 0: pills.append(f"🔄 {m['c_ad']} Continuity")
        if m['n_ad'] > 0: pills.append(f"🆕 {m['n_ad']} New Ad")
        pill_str = " | ".join(pills)
        loc_pills[addr] = f"({m['t_count']} Tasks) {pill_str}"
        st.markdown(f"**{addr}** <span style='font-size:12px; color:#64748b;'>— {pill_str}</span>", unsafe_allow_html=True)
    
    st.divider()
    ic_df = st.session_state.get('ic_df', pd.DataFrame())
    if not ic_df.empty:
        v_ics = ic_df.dropna(subset=['Lat', 'Lng']).copy()
        v_ics['d'] = v_ics.apply(lambda x: haversine(cluster['center'][0], cluster['center'][1], x['Lat'], x['Lng']), axis=1)
        v_ics = v_ics[v_ics['d'] <= 100].sort_values('d')
        ic_opts = {f"{r['Name']} ({round(r['d'],1)} mi)": r for _, r in v_ics.iterrows()}
        if ic_opts:
            sel_ic = st.selectbox("Assign Contractor", list(ic_opts.keys()), key=f"sel_{c_hash}")
            if st.button("🚀 Send to Portal", key=f"btn_{c_hash}", use_container_width=True):
                ic = ic_opts[sel_ic]
                payload = {
                    "icn": ic['Name'], "ice": ic['Email'], "wo": f"WO-{c_hash[:6]}",
                    "due": str(datetime.now().date()+timedelta(14)), "comp": 0, "lCnt": cluster['stops'],
                    "locs": " | ".join(list(stop_metrics.keys())), "taskIds": ",".join(task_ids), "tCnt": len(task_ids),
                    "jobOnly": " | ".join([f"{a} {p}" for a, p in loc_pills.items()])
                }
                requests.post(GAS_WEB_APP_URL, json={"action": "saveRoute", "payload": payload})
                st.session_state[f"route_state_{c_hash}"] = "email_sent"
                st.rerun()

def run_pod_tab(pod_name):
    if f"clusters_{pod_name}" not in st.session_state:
        if st.button(f"🚀 Initialize {pod_name} Data", use_container_width=True): 
            process_pod(pod_name); st.rerun()
        return

    cls = st.session_state[f"clusters_{pod_name}"]
    fresh_db, ghost_db = fetch_sent_records_from_sheet()
    pod_ghosts = ghost_db.get(pod_name, [])
    
    ready, review, sent, accepted, declined, finalized = [], [], [], [], [], []
    for c in cls:
        ids = [str(t['id']).strip() for t in c['data']]
        c_hash = hashlib.md5("".join(sorted(ids)).encode()).hexdigest()
        h_icons = ""
        tt_all = " ".join([t['task_type'] for t in c['data']])
        if any(x in tt_all for x in ["digital", "ins", "offline", "service", "skykit"]): h_icons += " 🔌"
        if "install" in tt_all: h_icons += " 🛠️"
        if "removal" in tt_all: h_icons += " 🛑"
        if any(x in tt_all for x in ["continuity", "photo", "swap"]): h_icons += " 🔄"
        if any(x in tt_all for x in ["new ad", "art change"]): h_icons += " 🆕"
        if c.get('esc_count', 0) > 0: h_icons += " ⭐"
        c['h_icons'] = h_icons

        match = fresh_db.get(next((tid for tid in ids if tid in fresh_db), None))
        is_rev = st.session_state.get(f"reverted_{c_hash}", False)
        if match and not is_rev:
            c['contractor_name'], c['route_ts'], stat = match['name'], match['time'], match['status'].lower()
            if stat == 'declined': declined.append(c)
            elif stat == 'accepted': accepted.append(c)
            elif stat == 'finalized': finalized.append(c)
            else: sent.append(c)
        else: ready.append(c)

    col_l, col_r = st.columns([4, 6])
    with col_l:
        st.markdown('<div style="margin-top:-35px;"></div><h3 style="text-align:center;">🚀 Dispatch</h3>', unsafe_allow_html=True)
        tr, tf = st.tabs(["Ready", "Flagged"])
        with tr:
            for i, c in enumerate(ready):
                with st.expander(f"🟢 {c['city']}, {c['state']}{c['h_icons']} | {c['stops']} Stops"): render_dispatch(i, c, pod_name)

    with col_r:
        st.markdown('<h3 style="text-align:center;">⏳ Awaiting Confirmation</h3>', unsafe_allow_html=True)
        ts, ta, td, tfi = st.tabs(["Sent", "Accepted", "Declined", "Finalized"])
        with ts:
            for i, c in enumerate(sent):
                exp, btn = st.columns([8, 2], vertical_alignment="center")
                with exp: 
                    with st.expander(f"✉️ {c['contractor_name']} | {c['city']}{c['h_icons']}"): render_dispatch(i+500, c, pod_name, is_sent=True)
                with btn:
                    ids = [str(t['id']).strip() for t in c['data']]
                    h = hashlib.md5("".join(sorted(ids)).encode()).hexdigest()
                    st.button("↩️ Revoke", key=f"rev_{h}", on_click=instant_revoke_handler, args=(h, c['contractor_name'], c, pod_name))
        with ta:
            for i, c in enumerate(accepted):
                ids = [str(t['id']).strip() for t in c['data']]
                h = hashlib.md5("".join(sorted(ids)).encode()).hexdigest()
                with st.expander(f"✅ {c['contractor_name']} | {c['city']}{c['h_icons']}"):
                    s1 = st.checkbox("1. Onfleet Optimized?", key=f"s1_{h}")
                    s2 = st.checkbox("2. Backend Fields Done?", key=f"s2_{h}", disabled=not s1)
                    if st.checkbox("3. Packing List Uploaded?", key=f"s3_{h}", disabled=not s2):
                        finalize_route_handler(h); st.rerun()
                    render_dispatch(i+2000, c, pod_name, is_sent=True)
        with td:
            for i, c in enumerate(declined):
                ids = [str(t['id']).strip() for t in c['data']]
                h = hashlib.md5("".join(sorted(ids)).encode()).hexdigest()
                with st.expander(f"❌ {c['contractor_name']} | {c['city']}{c['h_icons']}"):
                    if st.button("↩️ Re-Route", key=f"rr_{h}"): move_to_dispatch(h, "", pod_name, "Declined"); st.rerun()
        with tfi:
            for i, c in enumerate(finalized):
                with st.expander(f"🏁 {c['contractor_name']} | {c['city']}{c['h_icons']}"): st.success("Route Archived.")

# --- MAIN ---
st.markdown("<h1 style='text-align:center;'>Dispatch Command Center</h1>", unsafe_allow_html=True)
tabs = st.tabs(["Global", "Blue Pod", "Green Pod", "Orange Pod", "Purple Pod", "Red Pod"])

with tabs[0]:
    db, ghosts = fetch_sent_records_from_sheet()
    cols = st.columns(5)
    for i, pod in enumerate(POD_CONFIGS.keys()):
        with cols[i]:
            has_data = f"clusters_{pod}" in st.session_state
            if has_data:
                pod_cls = st.session_state[f"clusters_{pod}"]
                sent, accepted, declined, finalized = [], [], [], []
                for c in pod_cls:
                    ids = [str(t['id']).strip() for t in c['data']]
                    m = db.get(next((tid for tid in ids if tid in db), None))
                    if m:
                        s = m['status'].lower()
                        if s == 'declined': declined.append(c)
                        elif s == 'accepted': accepted.append(c)
                        elif s == 'finalized': finalized.append(c)
                        else: sent.append(c)
                st.metric(pod, f"{len(accepted)} Accepted", f"{len(sent)} Sent")
            else: st.write(f"{pod}: Offline")

for i, pod in enumerate(POD_CONFIGS.keys(), 1):
    with tabs[i]: run_pod_tab(pod)
