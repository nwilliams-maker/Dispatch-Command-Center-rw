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
# We check the Environment (Railway) FIRST to avoid the Streamlit Secrets crash
ONFLEET_KEY = os.environ.get("ONFLEET_KEY")
GOOGLE_MAPS_KEY = os.environ.get("GOOGLE_MAPS_KEY")

# If Railway didn't have them, ONLY THEN do we try st.secrets (and we catch the error)
if not ONFLEET_KEY or not GOOGLE_MAPS_KEY:
    try:
        ONFLEET_KEY = ONFLEET_KEY or st.secrets.get("ONFLEET_KEY")
        GOOGLE_MAPS_KEY = GOOGLE_MAPS_KEY or st.secrets.get("GOOGLE_MAPS_KEY")
    except Exception:
        # If we get here, it means no secrets file exists AND Railway variables are missing
        pass

# Final check to keep the app from crashing with a traceback
if not ONFLEET_KEY or not GOOGLE_MAPS_KEY:
    st.error("🔑 **API Keys Missing!**")
    st.info("I couldn't find your keys in Railway's 'Variables' tab. Please double-check that you added ONFLEET_KEY and GOOGLE_MAPS_KEY there.")
    st.stop()

PORTAL_BASE_URL = "https://nwilliams-maker.github.io/Dispatch-Command-Center-rw/portal-dcc-rw.html"
GAS_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbyz16LuLJUJfrtUWxhvK8lGJCVSqRcrqPNOwLEICJ47Oa-BrRnBvFSsy4q8XXo-Y2DTAA/exec"
IC_SHEET_URL = "https://docs.google.com/spreadsheets/d/1y6wX0x93iDc3gdK_nZKLD-2QcGkUHkcM75u90ffRO6k/edit#gid=0"
SAVED_ROUTES_GID = "1477617688"
ACCEPTED_ROUTES_GID = "934075207"
DECLINED_ROUTES_GID = "600909788"

# Terraboost Media Brand Palette
TB_PURPLE = "#633094"
TB_GREEN = "#76bc21"
TB_APP_BG = "#f1f5f9"
TB_HOVER_GRAY = "#e2e8f0"

# Status Fills
TB_GREEN_FILL = "#dcfce7" # Ready
TB_BLUE_FILL = "#dbeafe"  # Sent
TB_RED_FILL = "#ffcccc"   # Flagged

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

# --- PINNED TOP-LEFT LOGO ---
# Function to convert the local image into web-safe code
def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception as e:
        return ""

# Make sure "terraboost_logo.png" perfectly matches your saved file name!
logo_base64 = get_base64_image("terraboost_logo.png")

if logo_base64:
    st.markdown(f"""
        <div style="position: fixed; top: 15px; left: 20px; z-index: 999999;">
            <img src="data:image/png;base64,{logo_base64}" style="width: 140px;"> 
        </div>
    """, unsafe_allow_html=True)
else:
    st.sidebar.error("Logo file not found! Check the file name.")

# --- UI STYLING ---
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
.stApp {{ background-color: {TB_APP_BG} !important; color: #000000 !important; font-family: 'Inter', sans-serif !important; }}
.main .block-container {{ max-width: 1100px !important; padding-top: 2rem; }}

/* GLOBAL TABS CONTAINER - Clean & Floating with Bottom Line */
.stTabs [data-baseweb="tab-list"] {{ 
    justify-content: center; 
    gap: 12px; 
    background: transparent !important; /* Removes the gray box background */
    padding: 15px 15px 20px 15px !important; /* Adds extra padding on the bottom so pills don't touch the line */
    border-bottom: 2px solid #cbd5e1 !important; /* 🌟 THIS IS THE HORIZONTAL LINE 🌟 */
    margin-bottom: 15px !important; /* Pushes the dashboard content down slightly for breathing room */
}}

/* CENTERED PURPLE HEADERS */
h1, h2, h3, h4, h5, h6 {{ 
    font-weight: 800 !important; 
    text-align: center !important; 
    width: 100%;
}}

/* MODERN CONDENSED REFRESH BUTTON - FAR RIGHT */
div.refresh-btn-container {{
    display: flex;
    justify-content: flex-end;
    width: 100%;
}}

div.refresh-btn-container > div > button {{
    height: 32px !important; /* Slightly taller for breathing room */
    padding: 0 16px !important;
    font-size: 13px !important;
    border-radius: 20px !important;
    border: 1.2px solid #633094 !important;
    background-color: transparent !important;
    color: #633094 !important;
    font-weight: 700 !important;
    transition: all 0.2s ease-in-out !important;
    
    /* THE FIX: Forces icon and text onto one line perfectly centered */
    white-space: nowrap !important; 
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
}}

/* Ensures Streamlit's internal text wrapper doesn't force a line break */
div.refresh-btn-container > div > button div,
div.refresh-btn-container > div > button p {{
    white-space: nowrap !important;
    margin: 0 !important;
    padding: 0 !important;
}}
div.refresh-btn-container > div > button:hover {{
    background-color: #633094 !important;
    color: white !important;
    box-shadow: 0 2px 8px rgba(99, 48, 148, 0.3) !important;
}}

/* GLOBAL TABS STYLING */
.stTabs [data-baseweb="tab-list"] {{ justify-content: center; gap: 8px; background: rgba(255,255,255,0.6); padding: 10px; border-radius: 15px; }}

/* PERMANENT POD TAB OUTLINES & DARK TEXT */
.stTabs [data-baseweb="tab"] {{
    border-top: 1px solid #cbd5e1 !important;
    border-left: 1px solid #cbd5e1 !important;
    border-right: 1px solid #cbd5e1 !important;
    margin: 0 4px !important;
    transition: all 0.2s ease !important;
    font-weight: 800 !important;
    border-radius: 10px 10px 0 0 !important;
    padding: 10px 20px !important;
}}

/* GLOBAL TABS CONTAINER - Clean & Floating */
.stTabs [data-baseweb="tab-list"] {{ 
    justify-content: center; 
    gap: 12px; 
    background: transparent !important; /* Removes the gray box background */
    padding: 15px; 
}}

/* KILL THE DEFAULT UNDERLINE (The "Cutoff" source) */
.stTabs [data-baseweb="tab-highlight"] {{
    background-color: transparent !important;
}}

/* PERMANENT FLOATING PILLS - No flat bottoms */
.stTabs [data-baseweb="tab"] {{
    border-radius: 30px !important; /* Full rounded pill */
    margin: 0 5px !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    font-weight: 800 !important;
    padding: 8px 25px !important;
    border: 2px solid transparent !important; /* Invisible border until set below */
}}

/* Global Tab */
.stTabs [data-baseweb="tab"]:nth-of-type(1) {{ border: 2px solid #633094 !important; color: #3b1d58 !important; background: white !important; }}

/* Blue Pod */
.stTabs [data-baseweb="tab"]:nth-of-type(2) {{ border: 2px solid #3b82f6 !important; background-color: #f0f7ff !important; color: #1e3a8a !important; }}

/* Green Pod */
.stTabs [data-baseweb="tab"]:nth-of-type(3) {{ border: 2px solid #22c55e !important; background-color: #f0fdf4 !important; color: #064e3b !important; }}

/* Orange Pod */
.stTabs [data-baseweb="tab"]:nth-of-type(4) {{ border: 2px solid #f97316 !important; background-color: #fffaf5 !important; color: #7c2d12 !important; }}

/* Purple Pod */
.stTabs [data-baseweb="tab"]:nth-of-type(5) {{ border: 2px solid #a855f7 !important; background-color: #faf5ff !important; color: #4c1d95 !important; }}

/* Red Pod */
.stTabs [data-baseweb="tab"]:nth-of-type(6) {{ border: 2px solid #ef4444 !important; background-color: #fef2f2 !important; color: #7f1d1d !important; }}

/* ACTIVE STATE - The "Full Glow" (No flat bottom border) */
.stTabs [aria-selected="true"] {{ 
    background-color: #ffffff !important;
    transform: translateY(-4px) !important; /* Removed the scale(1.05) so it matches cards perfectly */
    box-shadow: 0 10px 20px rgba(99, 48, 148, 0.25) !important; 
}}

/* PRIMARY & SECONDARY BUTTONS */
button[kind="primary"] {{
    background-color: #76bc21 !important;
    color: white !important;
    height: 3.5rem !important;
    font-size: 1.2rem !important;
    font-weight: 800 !important;
    border: none !important;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
    transition: all 0.2s ease !important;
}}

button[kind="secondary"] {{
    background-color: #ffffff !important;
    color: {TB_PURPLE} !important;
    border: 2px solid {TB_PURPLE} !important;
    height: 42px !important;
    font-size: 0.9rem !important;
    font-weight: 800 !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
    transition: all 0.2s ease !important;
}}

/* EXPANDER & LAYOUT TIGHTENING (Pure CSS Fusion) */
/* 1. Target the Expander on the Left side of the gap */
div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(2) button) > div[data-testid="stColumn"]:nth-child(1) div[data-testid="stExpander"] {{
    border-top-right-radius: 0px !important;
    border-bottom-right-radius: 0px !important;
}}

/* 2. Target the Button on the Right side of the gap */
div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(1) div[data-testid="stExpander"]) > div[data-testid="stColumn"]:nth-child(2) button {{
    margin-left: -1rem !important;
    width: calc(100% + 1rem) !important;
    border-top-left-radius: 0px !important;
    border-bottom-left-radius: 0px !important;
}}

/* Main Expander Container */
div[data-testid="stExpander"] {{ 
    border: 1px solid #cbd5e1 !important; 
    border-radius: 10px !important; 
    box-shadow: 0 2px 4px rgba(0,0,0,0.02) !important;
    margin-bottom: 8px !important;
    background-color: #ffffff !important;
    overflow: hidden !important;
}}

/* Header text color */
div[data-testid="stExpander"] details summary p {{ 
    color: #000000 !important; 
    font-weight: 800 !important; 
    font-size: 0.85rem !important;
}}

/* 🚀 FIX: STOP THE DARK HOVER & BLACK CLICK FILL */
div[data-testid="stExpander"] details summary {{
    background-color: #ffffff !important; /* Force base color */
    transition: background-color 0.2s ease !important;
}}

div[data-testid="stExpander"] details summary:hover {{
    background-color: #fcfaff !important; /* Very light purple on hover */
}}

/* This targets the exact moment you click it */
div[data-testid="stExpander"] details summary:active {{
    background-color: #ffffff !important; 
}}

/* This removes the "Black/Gray Box" focus state that stays after clicking */
div[data-testid="stExpander"] details summary:focus, 
div[data-testid="stExpander"] details summary:focus-visible {{
    background-color: #ffffff !important;
    outline: none !important;
    box-shadow: none !important;
}}

/* Ensure the text stays visible during the click */
div[data-testid="stExpander"] details summary:hover p,
div[data-testid="stExpander"] details summary:active p,
div[data-testid="stExpander"] details summary:focus p {{
    color: #633094 !important;
}}

label, div[data-testid="stWidgetLabel"] p {{ color: #000000 !important; font-weight: 600 !important; }}

/* MAP & FOLIUM */
iframe[title="streamlit_folium.st_folium"] {{
    border-radius: 15px !important;
    box-shadow: 0 4px 6px rgba(0,0,0,0.05) !important;
}}
.stFolium {{ background: transparent !important; }}

/* =========================================
   UNIFIED HOVER & CLICK EFFECTS
   ========================================= */

/* 1. BUTTONS: Lift + Purple Glow */
button[kind="primary"]:hover,
button[kind="secondary"]:hover,
div.refresh-btn-container > div > button:hover {{
    transform: translateY(-4px) !important;
    box-shadow: 0 12px 28px rgba(99, 48, 148, 0.35) !important;
    border-color: #633094 !important;
    z-index: 10;
}}

/* 2. CARDS, TABS & EXPANDERS: Lift + Neutral Drop Shadow (No Purple) */
div[data-testid="stExpander"]:hover,
.pod-card-pill:hover,
.dashboard-supercard:hover,
.stTabs [data-baseweb="tab"]:hover {{
    transform: translateY(-4px) !important;
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.08) !important; 
    z-index: 10;
}}

/* 3. STRICT CLICK ANIMATION (Kills the "Push In" effect) */
/* Forces all elements to just drop back to baseline smoothly when clicked */
button[kind="primary"]:active,
button[kind="secondary"]:active,
div.refresh-btn-container > div > button:active,
div[data-testid="stExpander"] details summary:active,
.pod-card-pill:active,
.dashboard-supercard:active,
.stTabs [data-baseweb="tab"]:active {{
    transform: translateY(0px) scale(1) !important; 
    box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
}}

/* Smooth transitions for everything */
div[data-testid="stExpander"],
div[data-testid="stExpander"] details summary,
.pod-card-pill,
.dashboard-supercard,
button[kind="primary"],
button[kind="secondary"],
div.refresh-btn-container > div > button,
.stTabs [data-baseweb="tab"] {{
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
}}

/* =========================================
   SUB-TAB PILL STYLING (Column-Targeting Method)
   ========================================= */

/* --- LEFT COLUMN: Dispatch Tabs --- */
/* 1. Ready (Green) */
div[data-testid="stColumn"]:nth-child(1) div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(1) {{
    background-color: #dcfce7 !important;
    border: 2px solid #166534 !important;
}}
div[data-testid="stColumn"]:nth-child(1) div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(1) p {{
    color: #166534 !important; 
}}

/* 2. Flagged (Red) */
div[data-testid="stColumn"]:nth-child(1) div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(2) {{
    background-color: #fee2e2 !important;
    border: 2px solid #991b1b !important;
}}
div[data-testid="stColumn"]:nth-child(1) div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(2) p {{
    color: #991b1b !important; 
}}


/* --- RIGHT COLUMN: Awaiting Tabs --- */
/* Force the gap so they break apart into individual pills */
div[data-testid="stColumn"]:nth-child(2) div[data-testid="stTabs"] [data-baseweb="tab-list"] {{
    gap: 12px !important;
}}

/* 1. Sent (Purple/Blue) - THE MISSING FIX */
div[data-testid="stColumn"]:nth-child(2) div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(1) {{
    background-color: #f3e8ff !important;
    border: 2px solid #633094 !important;
    border-radius: 30px !important;
}}
div[data-testid="stColumn"]:nth-child(2) div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(1) p {{
    color: #633094 !important; 
}}

/* 2. Accepted (Green) */
div[data-testid="stColumn"]:nth-child(2) div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(2) {{
    background-color: #dcfce7 !important;
    border: 2px solid #166534 !important;
    border-radius: 30px !important;
}}
div[data-testid="stColumn"]:nth-child(2) div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(2) p {{
    color: #166534 !important; 
}}

/* 3. Declined (Red) */
div[data-testid="stColumn"]:nth-child(2) div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(3) {{
    background-color: #fee2e2 !important;
    border: 2px solid #991b1b !important;
    border-radius: 30px !important;
}}
div[data-testid="stColumn"]:nth-child(2) div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(3) p {{
    color: #991b1b !important; 
}}


/* ALIGN COLUMNS AT THE TOP (Fixes the giant gap on the left) */
div[data-testid="stHorizontalBlock"] {{ align-items: flex-start !important; }}

/* TIGHTEN GAPS BETWEEN CARDS */
div[data-testid="stVerticalBlock"] {{ gap: 0.2rem !important; }}
div[data-testid="stExpander"] {{ margin-top: 0px !important; margin-bottom: 2px !important; }}

/* MINI REVOKE BUTTON (Single Line, Right Aligned) */
div.mini-btn button {{
    height: 30px !important;
    min-height: 30px !important;
    padding: 0 8px !important;
    font-size: 11px !important;
    white-space: nowrap !important; /* CRITICAL: Stops "Revoke" from dropping to a second line */
    float: right !important;
    margin-top: 4px !important;
    border-radius: 4px !important;
}}

</style>
""", unsafe_allow_html=True)

def background_sheet_move(cluster_hash, payload_json):
    try:
        # This runs safely in a separate invisible thread
        requests.post(GAS_WEB_APP_URL, json={
            "action": "archiveRoute",  # 🌟 FIX: Tell the Sheet to Archive instead of Delete
            "cluster_hash": cluster_hash,
            "payload": payload_json
        })
    except:
        pass
def finalize_route_handler(cluster_hash):
    # This fires the command to your Google Sheet to change status to 'finalized'
    try:
        res = requests.post(GAS_WEB_APP_URL, json={
            "action": "finalizeRoute", 
            "cluster_hash": cluster_hash
        }).json()
        if res.get("success"):
            st.toast("🏁 Route Finalized!")
        else:
            st.error("Failed to update database.")
    except Exception as e:
        st.error(f"Finalization Error: {e}")
        
def move_to_dispatch(cluster_hash, ic_name, pod_name, action_label="Revoked", check_onfleet=False):
    # 1. 🚀 DATABASE ARCHIVE
    # Tell Google Sheets to move the row to Archive so the portal link dies.
    try:
        requests.post(GAS_WEB_APP_URL, json={
            "action": "archiveRoute", 
            "cluster_hash": cluster_hash
        }, timeout=5)
    except Exception as e:
        st.error(f"Archive Failed: {e}")

    clusters = st.session_state.get(f"clusters_{pod_name}", [])
    for c in clusters:
        task_ids = [str(t['id']).strip() for t in c['data']]
        old_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
        
        if old_hash == cluster_hash:
            valid_tasks = []
            
            # 2. 📡 RELEASE TASKS
            if check_onfleet:
                for t in c['data']:
                    try:
                        res = requests.get(f"https://onfleet.com/api/v2/tasks/{t['id']}", headers=headers, timeout=5).json()
                        if res.get('state') != 3:  
                            valid_tasks.append(t)
                    except:
                        valid_tasks.append(t)
            else:
                valid_tasks = c['data']
            
            if not valid_tasks:
                clusters.remove(c)
                st.toast("✅ Route cleared (Tasks completed or assigned elsewhere).")
                st.rerun()
                return
            
            # Update the cluster object
            c['data'] = valid_tasks
            c['stops'] = len(set(x['full'] for x in valid_tasks))
            
            new_task_ids = [str(t['id']).strip() for t in c['data']]
            new_hash = hashlib.md5("".join(sorted(new_task_ids)).encode()).hexdigest()
            
            # 3. 🧠 THE TOTAL MEMORY WIPE
            # We clear EVERYTHING associated with the old hash's assigned state.
            ui_keys_to_kill = [
                f"sync_{old_hash}", f"tx_{old_hash}_preview", f"last_data_{old_hash}", 
                f"tx_ver_{old_hash}", f"pay_val_{old_hash}", f"rate_val_{old_hash}", 
                f"sel_{old_hash}", f"last_sel_{old_hash}", f"dd_{old_hash}",
                f"is_ghost_{old_hash}", f"route_ts_{old_hash}",
                # 🌟 FIX: Kill the checklist states so they don't persist
                f"g_s1_{old_hash}_0", f"g_s1_{old_hash}_1", f"g_s1_{old_hash}_2",
                f"g_s2_{old_hash}_0", f"g_s2_{old_hash}_1", f"g_s2_{old_hash}_2",
                f"g_s3_{old_hash}_0", f"g_s3_{old_hash}_1", f"g_s3_{old_hash}_2"
            ]
            for k in ui_keys_to_kill:
                st.session_state.pop(k, None)
            
            # 4. 🔄 REDIRECT TO DISPATCH
            st.session_state[f"reverted_{new_hash}"] = True
            st.session_state[f"route_state_{new_hash}"] = "ready"
            
            # Log the event
            hist = st.session_state.get(f"history_{old_hash}", [])
            hist.append(f"{ic_name} ({datetime.now().strftime('%m/%d')} - {action_label})")
            st.session_state[f"history_{new_hash}"] = hist
            
            # Clean up tracking keys if hash changed
            if old_hash != new_hash:
                for key in [f"history_{old_hash}", f"reverted_{old_hash}", f"route_state_{old_hash}"]:
                    st.session_state.pop(key, None)
            
            st.toast(f"✅ Route {action_label}. Tasks back in Dispatch.")
            st.rerun() # 🌟 FINAL PUNCH: Force UI to update immediately
            return

def instant_revoke_handler(cluster_hash, ic_name, payload_json, pod_name):
    # This specifically handles the SENT tab
    threading.Thread(target=background_sheet_move, args=(cluster_hash, payload_json)).start()
    # Sent tab doesn't need OnFleet scrub!
    move_to_dispatch(cluster_hash, ic_name, pod_name, action_label="Revoked", check_onfleet=False)
    
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
        sheets_to_fetch = [
            (DECLINED_ROUTES_GID, "declined"),
            (ACCEPTED_ROUTES_GID, "accepted"),
            (SAVED_ROUTES_GID, "sent")
        ]
        
        sent_dict = {}
        # Prepare ghost lists for each pod
        ghost_routes = {"Blue": [], "Green": [], "Orange": [], "Purple": [], "Red": [], "UNKNOWN": []}
        
        for gid, status_label in sheets_to_fetch:
            try:
                df = pd.read_csv(base_url + gid)
                df.columns = [str(c).strip().lower() for c in df.columns]
                
                if 'json payload' in df.columns:
                    for _, row in df.iterrows():
                        try:
                            p = json.loads(row['json payload'])
                            tids = str(p.get('taskIds', '')).replace('|', ',').split(',')
                            c_name = str(row.get('contractor', 'Unknown Contractor'))
                            
                            raw_ts = row.get('date created', '')
                            ts_display = ""
                            if pd.notna(raw_ts) and str(raw_ts).strip():
                                try:
                                    ts_display = pd.to_datetime(raw_ts).strftime('%m/%d %I:%M %p')
                                except:
                                    ts_display = str(raw_ts)
                            
                            # 1. Live Task Matching
                            for tid in tids:
                                tid = tid.strip()
                                if tid:
                                    sent_dict[tid] = {
                                        "name": c_name, 
                                        "status": status_label,
                                        "time": ts_display,
                                        "wo": p.get('wo', c_name) # Falls back to name if missing
                                    }
                            
                            # 2. GHOST ROUTES (Only for Accepted routes that vanish from the pool)
                            if status_label == 'accepted':
                                locs_str = str(p.get('locs', ''))
                                state_guess, city_guess = "UNKNOWN", "Unknown"
                                stops_list = [s.strip() for s in locs_str.split('|') if s.strip()]
                                
                                # Extract city/state from the first real stop
                                if len(stops_list) > 1:
                                    addr_parts = stops_list[1].split(',')
                                    if len(addr_parts) >= 2:
                                        state_guess = addr_parts[-1].strip().upper()
                                        city_guess = addr_parts[-2].strip()
                                
                                norm_state = STATE_MAP.get(state_guess, state_guess)
                                pod_name = "UNKNOWN"
                                for p_name, p_config in POD_CONFIGS.items():
                                    if norm_state in p_config['states']:
                                        pod_name = p_name
                                        break
                                
                                if pod_name != "UNKNOWN":
                                    # 🌟 FIX: Calculate the hash so the checklist can finalize this route
                                    clean_tids = [str(t).strip() for t in tids if str(t).strip()]
                                    ghost_hash = hashlib.md5("".join(sorted(clean_tids)).encode()).hexdigest()

                                    ghost_routes[pod_name].append({
                                        "contractor_name": c_name,
                                        "route_ts": ts_display,
                                        "city": city_guess,
                                        "state": norm_state,
                                        "stops": p.get('lCnt', 0),
                                        "tasks": p.get('tCnt', len(tids)),
                                        "pay": p.get('comp', 0),
                                        "wo": p.get('wo', c_name),
                                        "hash": ghost_hash # Pass the hash to the UI
                                    })
                                    
                        except: continue
            except: continue
        return sent_dict, ghost_routes
    except Exception as e:
        st.error(f"Failed to fetch portal records: {e}")
        return {}, {}

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

@st.cache_data(ttl=600)
def load_ic_database(sheet_url):
    try:
        export_url = f"{sheet_url.split('/edit')[0]}/export?format=csv&gid=0"
        return pd.read_csv(export_url)
    except: return None

# --- CORE LOGIC ---
def process_pod(pod_name, master_bar=None, pod_idx=0, total_pods=1):
    config = POD_CONFIGS[pod_name]
    
    # Logic to handle if we are doing a single pod or a global pull
    pod_weight = 1.0 / total_pods
    start_pct = pod_idx * pod_weight
    
    # Use the master bar if provided, otherwise create a local one
    prog_bar = master_bar if master_bar else st.progress(0)
    
    def update_prog(rel_val, msg):
        # Maps a 0.0-1.0 internal progress to the global start/end points
        global_val = min(start_pct + (rel_val * pod_weight), 0.99)
        prog_bar.progress(global_val, text=f"[{pod_name}] {msg}")

    try:
        update_prog(0.0, "📥 Extracting tasks...")
        APPROVED_TEAMS = [
            "a - escalation", "b - boosted campaigns", "b - local campaigns", 
            "c - priority nationals", "cvs kiosk removal", "n - national campaigns"
        ]

        teams_res = requests.get("https://onfleet.com/api/v2/teams", headers=headers).json()
        target_team_ids = [t['id'] for t in teams_res if any(appr in str(t.get('name', '')).lower() for appr in APPROVED_TEAMS)]
        esc_team_ids = [t['id'] for t in teams_res if 'escalation' in str(t.get('name', '')).lower()]

        all_tasks_raw = []
        url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time()*1000)-(80*24*3600*1000)}"
        
        while url:
            response = requests.get(url, headers=headers)
            res_json = response.json()
            
            # Check for API errors immediately
            if response.status_code != 200:
                st.error(f"Onfleet API Error: {res_json}")
                break
                
            tasks_page = res_json.get('tasks', [])
            all_tasks_raw.extend(tasks_page)
            
            url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time()*1000)-(80*24*3600*1000)}&lastId={res_json['lastId']}" if res_json.get('lastId') else None
            update_prog(min(len(all_tasks_raw)/500 * 0.4, 0.4), "📡 Fetching task pages...")

        unique_tasks_dict = {t['id']: t for t in all_tasks_raw}
        all_tasks = list(unique_tasks_dict.values())
        
        # 🌟 UNIVERSAL WHITELIST: Only these three trigger the plug and 25-mile radius
        DIGITAL_WHITELIST = ["digital service", "digital ins/remove", "digital offline", "site survey"]

        # PERFORMANCE FIX: Fetch Google Sheets data once before the loop
        fresh_sent_db, _ = fetch_sent_records_from_sheet()
        st.session_state.sent_db = fresh_sent_db

        pool = []
        for t in all_tasks:
            container = t.get('container', {})
            c_type = str(container.get('type', '')).upper()
            
            if c_type == 'TEAM' and container.get('team') not in target_team_ids: 
                continue

            addr = t.get('destination', {}).get('address', {})
            stt = normalize_state(addr.get('state', ''))
            is_esc = (c_type == 'TEAM' and container.get('team') in esc_team_ids)
            
            # 1. BASE TASK TYPE EXTRACTION
            tt_val = str(t.get('taskType', '')).strip() or str(t.get('taskDetails', '')).strip()

            # --- 🌟 1. DEFINE CORE TRIGGER KEYWORDS ---
            DIGITAL_WHITELIST = ["service", "ins/remove", "offline"]
            
            # --- 🔍 2. DEEP SCAN ---
            official_fields = (t.get('customFields') or []) + (t.get('metadata') or [])
            is_digital_task = False 
            found_official_type = False
            
            # Step A: Baseline check against Native Onfleet Type
            native_tt = tt_val.lower()
            if any(trigger in native_tt for trigger in DIGITAL_WHITELIST):
                is_digital_task = True

            # Step B: Priority Scan of Official Fields (Metadata/Custom Fields)
            for f in official_fields:
                f_name = str(f.get('name', '')).strip().lower()
                f_key = str(f.get('key', '')).strip().lower()
                f_val = str(f.get('value', '')).strip()
                f_val_lower = f_val.lower()
                
                # Check for Task Type in Official Fields
                if f_name in ['task type', 'tasktype'] or f_key in ['tasktype', 'task_type']:
                    tt_val = f_val # This becomes the display name (e.g., "Digital Service")
                    found_official_type = True
                    
                    # 🔌 TRIGGER: Check if this official value contains our keywords
                    if any(trigger in f_val_lower for trigger in DIGITAL_WHITELIST):
                        is_digital_task = True
                
                # Check for Escalation (Official Field Priority)
                if ('escalation' in f_name or 'escalation' in f_key):
                    if f_val_lower in ['1', '1.0', 'true', 'yes'] or 'escalation' in f_val_lower:
                        is_esc = True
                
                # Fallback for generic 'type' metadata if Task Type hasn't been found
                elif (f_name == 'type' or f_key == 'type') and not found_official_type:
                    tt_val = f_val
                    if any(trigger in f_val_lower for trigger in DIGITAL_WHITELIST):
                        is_digital_task = True

            # --- 3. ASSIGN STATUS ---
            t_status = 'ready'
            t_wo = 'none'
            if t['id'] in fresh_sent_db:
                t_status = fresh_sent_db[t['id']].get('status', 'ready').lower()
                t_wo = fresh_sent_db[t['id']].get('wo', 'none')
            
            if stt in config['states']:
                pool.append({
                    "id": t['id'], 
                    "city": addr.get('city', 'Unknown'), 
                    "state": stt,
                    "full": f"{addr.get('number','')} {addr.get('street','')}, {addr.get('city','')}, {stt}",
                    "lat": t['destination']['location'][1], 
                    "lon": t['destination']['location'][0],
                    "escalated": is_esc, 
                    "task_type": tt_val,
                    "is_digital": is_digital_task, # 🔌 Flagged for Service, Ins/Rem, or Offline
                    "db_status": t_status, 
                    "wo": t_wo,
                })
                
        clusters = []
        total_pool = len(pool)
        ic_df = st.session_state.get('ic_df', pd.DataFrame())
        v_ics_base = ic_df[~ic_df.astype(str).apply(lambda x: x.str.contains('Field Agent', case=False, na=False).any(), axis=1)].dropna(subset=['Lat', 'Lng']).copy() if not ic_df.empty else pd.DataFrame()

        while pool:
            # Routing progress calculation
            rel_prog = 0.4 + (0.6 * (1 - (len(pool) / total_pool if total_pool > 0 else 1)))
            update_prog(rel_prog, f"🗺️ Routing {len(pool)} remaining tasks...")
            
            anc = pool.pop(0)
            
            # --- NEW: Strict Digital Separation & Dynamic Radius ---
            anc_tt = str(anc.get('task_type', '')).lower()
            anc_is_digital = anc.get('is_digital', False)
            anc_status = anc.get('db_status', 'ready')
            anc_wo = anc.get('wo', 'none')
            
            # Set radius strictly based on the whitelist result
            route_radius = 25 if anc_is_digital else 50
            
            candidates = []; rem = []
            for t in pool:
                t_tt = str(t.get('task_type', '')).lower()
                t_is_digital = t.get('is_digital', False)
                t_status = t.get('db_status', 'ready')
                t_wo = t.get('wo', 'none')
                
                # Rule 1: Digital and Standard never mix
                if anc_is_digital == t_is_digital:
                    
                    # Rule 2: Sent and Accepted are FROZEN
                    if anc_status in ['sent', 'accepted']:
                        # Bypasses distance! ONLY groups if the Work Order matches perfectly.
                        if t_status == anc_status and t_wo == anc_wo:
                            candidates.append((0, t)) 
                        else:
                            rem.append(t)
                            
                    # Rule 3: Ready and Declined are LIQUID (They can mix!)
                    elif anc_status in ['ready', 'declined']:
                        if t_status in ['ready', 'declined']:
                            d = haversine(anc['lat'], anc['lon'], t['lat'], t['lon'])
                            if d <= route_radius: 
                                candidates.append((d, t))
                            else: 
                                rem.append(t)
                        else:
                            rem.append(t)
                else:
                    rem.append(t)
            
            candidates.sort(key=lambda x: x[0])
            
            # --- PRESERVED: 20 STOP LIMIT LOGIC ---
            group = [anc]
            unique_stops = {anc['full']}
            spillover = []
            
            for _, t in candidates:
                # Only add the task if we're under 20 stops OR the task is at an address we already have
                if len(unique_stops) < 20 or t['full'] in unique_stops:
                    group.append(t)
                    unique_stops.add(t['full'])
                else:
                    spillover.append(t)
            
            # 🌟 BRIDGE: Put spillover back and fix the 'd' column error
            rem.extend(spillover)
            
            # --- 📡 1. IC SEARCH & DISTANCE CHECK ---
            has_ic = False
            ic_dist = 0
            closest_ic_loc = f"{anc['lat']},{anc['lon']}" 
            
            if not v_ics_base.empty:
                dists = v_ics_base.apply(lambda x: haversine(anc['lat'], anc['lon'], x['Lat'], x['Lng']), axis=1)
                valid_ics = v_ics_base[dists <= 100].copy()
                
                if not valid_ics.empty:
                    # 🛠️ THE FIX: Add the 'd' column here to prevent the KeyError
                    valid_ics['d'] = dists[valid_ics.index]
                    best_ic = valid_ics.sort_values('d').iloc[0]
                    has_ic = True
                    ic_dist = best_ic['d']
                    closest_ic_loc = best_ic['Location']

            def check_viability(grp):
                seen = set(); u_locs = []
                for x in grp:
                    if x['full'] not in seen: seen.add(x['full']); u_locs.append(x['full'])
                if not u_locs: return 0, 0
                _, hrs, _ = get_gmaps(closest_ic_loc, u_locs[:25])
                pay = round(max(len(u_locs) * 18.0, hrs * 25.0), 2)
                return round(pay / len(u_locs), 2), len(u_locs)
            
            gate_avg, _ = check_viability(group)
            
            # --- 🚦 2. UPDATED FLAGGING LOGIC ---
            if anc_status in ['sent', 'accepted']:
                status = anc_status.capitalize()
            else:
                status = "Ready" # Default status
                
                # Flag Criteria A: High Rate (> $23/stop)
                if gate_avg > 23.00:
                    if len(group) > 1:
                        removed = group.pop()
                        new_avg, _ = check_viability(group)
                        if new_avg <= 23.00:
                            rem.append(removed)
                        else:
                            group.append(removed)
                            status = "Flagged"
                    else:
                        status = "Flagged"
                
                # Flag Criteria B: Long Distance (> 60 miles) or No Contractor
                if not has_ic or ic_dist > 60:
                    status = "Flagged"

            # --- 📊 3. COUNTERS & SAVE TO SESSION ---
            g_data = group

            # 🌟 CLEANUP: No need to loop again; the anchor already knows!
            route_is_digital = anc_is_digital
            
            clusters.append({
                "data": g_data, 
                "center": [anc['lat'], anc['lon']], 
                "stops": len(set(x['full'] for x in g_data)), 
                "city": anc['city'], "state": anc['state'],
                "status": status,
                "has_ic": has_ic,
                "esc_count": sum(1 for x in g_data if x.get('escalated')),
                "is_digital": route_is_digital, # 🔌 Driven by the anchor's verified flag
                "inst_count": sum(1 for x in g_data if "install" in str(x.get('task_type', '')).lower()),
                "remov_count": sum(1 for x in g_data if "remov" in str(x.get('task_type', '')).lower()),
                "wo": anc_wo
            })
            pool = rem

        st.session_state[f"clusters_{pod_name}"] = clusters
        if not master_bar: 
            prog_bar.empty()

    except Exception as e:
        st.error(f"Error initializing {pod_name}: {str(e)}")

# --- DISPATCH RENDERING ---
def render_dispatch(i, cluster, pod_name, is_sent=False, is_declined=False):
    task_ids = [str(t['id']).strip() for t in cluster['data']]
    cluster_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
    sync_key = f"sync_{cluster_hash}"
    real_id = st.session_state.get(sync_key)
    link_id = real_id if real_id else "LINK_PENDING"

    # --- 1. STATE KEYS & INITIALIZATION ---
    pay_key = f"pay_val_{cluster_hash}"
    rate_key = f"rate_val_{cluster_hash}"
    sel_key = f"sel_{cluster_hash}"
    last_sel_key = f"last_sel_{cluster_hash}" # Tracks the "previous" selection

    st.write("### Route Stops")

    # --- NEW: HISTORY LOG ---
    hist = st.session_state.get(f"history_{cluster_hash}", [])
    if hist:
        st.markdown(f"<p style='color: #94a3b8; font-size: 13px; margin-top: -10px; margin-bottom: 15px; font-weight: 600;'>↩️ Previously sent to: {', '.join(hist)}</p>", unsafe_allow_html=True)

    # --- 2. STOP METRICS & PILLS ---
    stop_metrics = {}
    
    # Unified Master Loop: One pass for accuracy
    for t in cluster['data']:
        addr = t['full']
        
        # 1. Initialize stop if seen for the first time
        if addr not in stop_metrics:
            stop_metrics[addr] = {
                't_count': 0, 'n_ad': 0, 'c_ad': 0, 'd_ad': 0, 
                'inst': 0, 'remov': 0, 'digi': 0, 'oth': 0, 'esc': False
            }
        
        # 2. Basic Metrics
        stop_metrics[addr]['t_count'] += 1
        if t.get('escalated'): 
            stop_metrics[addr]['esc'] = True
            
        # 3. Task Type Text Cleaning (Omit "Escalation" if others exist)
        raw_tt = str(t.get('task_type', '')).strip()
        parts = [p.strip().lower() for p in raw_tt.split(',') if p.strip()]
        
        if "escalation" in parts:
            if len(parts) > 1:
                parts.remove("escalation") 
            else:
                parts = ["new ad"] 
        
        tt = ", ".join(parts)

        # 4. Classification (Independent Ifs for accurate workload)
        found_category = False
        if any(x in tt for x in ["service", "offline", "skykit", "ins/re"]): 
            stop_metrics[addr]['digi'] += 1
            found_category = True
        if "install" in tt: 
            stop_metrics[addr]['inst'] += 1
            found_category = True
        if "removal" in tt: 
            stop_metrics[addr]['remov'] += 1
            found_category = True
        if any(x in tt for x in ["continuity", "photo retake", "swap"]): 
            stop_metrics[addr]['c_ad'] += 1
            found_category = True
        if any(x in tt for x in ["default", "pull down"]): 
            stop_metrics[addr]['d_ad'] += 1
            found_category = True
        
        # Fallback Logic
        if any(x in tt for x in ["new ad", "art change", "top"]) or not tt:
            stop_metrics[addr]['n_ad'] += 1
        elif not found_category:
            stop_metrics[addr]['oth'] += 1
            
    # --- UI RENDERING ---
    for addr, metrics in stop_metrics.items():
        pill_parts = []
        if metrics['n_ad'] > 0: pill_parts.append(f"🆕 {metrics['n_ad']} New Ad")
        if metrics['c_ad'] > 0: pill_parts.append(f"🔄 {metrics['c_ad']} Continuity")
        if metrics['d_ad'] > 0: pill_parts.append(f"⚪ {metrics['d_ad']} Default")
        if metrics['inst'] > 0: pill_parts.append(f"🛠️ {metrics['inst']} Kiosk Install")
        if metrics['remov'] > 0: pill_parts.append(f"🛑 {metrics['remov']} Kiosk Removal")
        if metrics['digi'] > 0: pill_parts.append(f"🔌 {metrics['digi']} Digital Service")
        if metrics['oth'] > 0: pill_parts.append(f"📦 {metrics['oth']} Other")
        
        pill_str = " | ".join(pill_parts)
        display_addr = f"⭐ {addr}" if metrics['esc'] else addr
        
        # 🌟 UI FIX: Use <b> for address and colored badges for task counts
        st.markdown(
            f"<b>{display_addr}</b> &nbsp;"
            f"<span style='color: #633094; background-color: #f3e8ff; padding: 2px 6px; border-radius: 10px; font-weight: 800; font-size: 11px;'>"
            f"{metrics['t_count']} Tasks</span>&nbsp; "
            f"<span style='font-size: 13px; color: #475569;'>— {pill_str}</span>", 
            unsafe_allow_html=True
        )
        
    st.divider()

    # --- 3. CONTRACTOR FILTERING (100 MILES) ---
    ic_df = st.session_state.get('ic_df', pd.DataFrame())
    v_ics = ic_df[~ic_df.astype(str).apply(lambda x: x.str.contains('Field Agent', case=False, na=False).any(), axis=1)].dropna(subset=['Lat', 'Lng']).copy()
    if not v_ics.empty:
        v_ics['d'] = v_ics.apply(lambda x: haversine(cluster['center'][0], cluster['center'][1], x['Lat'], x['Lng']), axis=1)
        v_ics = v_ics[v_ics['d'] <= 100].sort_values('d')

    if v_ics.empty:
        st.error("⚠️ No contractors found within 100 miles. Manual recruiting or assignment required.")
        return

    # --- NEW: Inject the 🔌 for Digital Certified Contractors ---
    ic_opts = {}
    for _, r in v_ics.iterrows():
        # Safely extract the column value (defaults to blank if missing to prevent crashes)
        cert_val = str(r.get('Digital Certified', '')).strip().upper()
        # Checks for various ways 'YES' might be formatted in the sheet
        cert_icon = " 🔌" if cert_val in ['YES', 'Y', 'TRUE', '1', '1.0'] else ""
        
        label = f"{r['Name']}{cert_icon} ({round(r['d'], 1)} mi)"
        ic_opts[label] = r
    
    # --- 3. DYNAMIC PRICING SYNC LOGIC ---
    def sync_on_total():
        # 🌟 FIX: Use safely with .get() to survive memory wipes
        val = st.session_state.get(pay_key)
        if val is not None:
            st.session_state[rate_key] = round(val / cluster['stops'], 2) if cluster['stops'] > 0 else 0

    def sync_on_rate():
        # 🌟 FIX: Use safely with .get() to survive memory wipes
        val = st.session_state.get(rate_key)
        if val is not None:
            st.session_state[pay_key] = round(val * cluster['stops'], 2)

    def update_for_new_contractor():
        # 🌟 FIX: Use .get() safely so it doesn't crash if the Memory Wipe deleted the key!
        selected_label = st.session_state.get(sel_key)
        
        # Only run the math if the label actually exists
        if selected_label and selected_label != st.session_state.get(last_sel_key):
            ic_new = ic_opts[selected_label]
            _, h, _ = get_gmaps(ic_new['Location'], list(stop_metrics.keys())[:25])
            new_pay = float(round(max(cluster['stops'] * 18.0, h * 25.0), 2))
            st.session_state[pay_key] = new_pay
            st.session_state[rate_key] = round(new_pay / cluster['stops'], 2) if cluster['stops'] > 0 else 0
            st.session_state[last_sel_key] = selected_label

    # Initial Setup (First time card is seen)
    if pay_key not in st.session_state:
        # 🌟 FIX: Look for the previously sent contractor first!
        prev_name = cluster.get('contractor_name', 'Unknown')
        default_label = list(ic_opts.keys())[0] # Fallback to closest if previous is missing
        
        if prev_name != 'Unknown':
            for label, row in ic_opts.items():
                if row['Name'] == prev_name:
                    default_label = label
                    break
                    
        ic_init = ic_opts[default_label]
        _, h, _ = get_gmaps(ic_init['Location'], list(stop_metrics.keys())[:25])
        initial_pay = float(round(max(cluster['stops'] * 18.0, h * 25.0), 2))
        st.session_state[pay_key] = initial_pay
        st.session_state[rate_key] = round(initial_pay / cluster['stops'], 2) if cluster['stops'] > 0 else 0
        st.session_state[sel_key] = default_label
        st.session_state[last_sel_key] = default_label

    # --- 5. THE UI ROW ---
    col_a, col_b, col_c, col_d = st.columns([1.5, 1, 1, 1])
    
    with col_a:
        # The callback is attached here to force the background math to run
        st.selectbox("Contractor", list(ic_opts.keys()), key=sel_key, on_change=update_for_new_contractor)
    
    # Get current state values
    ic = ic_opts[st.session_state[sel_key]]
    mi, hrs, t_str = get_gmaps(ic['Location'], list(stop_metrics.keys())[:25])
    
    # LOCK CHECK
    curr_rate = st.session_state[rate_key]
    needs_unlock = (curr_rate >= 25.0) or (ic['d'] > 60) or (cluster['status'] == 'Flagged')
    is_unlocked = True 
    
    if needs_unlock:
        reasons = []
        if curr_rate >= 25.0: reasons.append(f"High Rate (${curr_rate})")
        if ic['d'] > 60: reasons.append(f"Distance ({round(ic['d'],1)}mi)")
        if cluster['status'] == 'Flagged': reasons.append("Flagged Route")
        st.markdown(f"""<div style="background-color:#fef2f2; border:1px solid #ef4444; padding:10px; border-radius:8px; margin-bottom:15px;"><span style="color:#b91c1c; font-weight:800;">🔒 ACTION REQUIRED:</span> <span style="color:#7f1d1d;">{" & ".join(reasons)}</span></div>""", unsafe_allow_html=True)
        is_unlocked = st.checkbox("Authorize Premium Rate / Distance", key=f"lock_{cluster_hash}")

    with col_b:
        st.number_input("Total Comp ($)", min_value=0.0, step=5.0, key=pay_key, on_change=sync_on_total, disabled=not is_unlocked)
    with col_c:
        st.number_input("Rate/Stop ($)", min_value=0.0, step=1.0, key=rate_key, on_change=sync_on_rate, disabled=not is_unlocked)
    with col_d:
        st.date_input("Deadline", datetime.now().date()+timedelta(14), key=f"dd_{cluster_hash}", disabled=not is_unlocked)

    # --- 6. UPDATED FINANCIALS & PREVIEW ---
    # Fetch final values from session state to ensure they match the UI dynamically
    final_pay = st.session_state[pay_key]
    final_rate = st.session_state[rate_key]

    m1, m2 = st.columns(2)
    with m1: 
        status_color = TB_GREEN if 18.0 <= final_rate <= 23.0 else "#ef4444"
        st.markdown(f"<div style='background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:15px; margin-bottom:10px;'><p style='font-size:11px; font-weight:800; text-transform:uppercase;'>Financials</p><p style='margin:0; font-size:24px; font-weight:800; color:{status_color};'>Total: ${final_pay:,.2f}</p><p style='margin:0; font-size:13px; color:#000000;'>Breakdown: ${final_rate}/stop</p></div>", unsafe_allow_html=True)
    with m2: 
        st.markdown(f"<div style='background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:15px; margin-bottom:10px;'><p style='font-size:11px; font-weight:800; text-transform:uppercase;'>Logistics</p><p style='margin:0; font-size:24px; font-weight:800; color:#000000;'>{t_str}</p><p style='margin:0; font-size:13px; color:#000000;'>Round Trip: {mi} mi</p></div>", unsafe_allow_html=True)

    # --- BUILD STOP PREVIEW & METRICS ---
    stops_text = ""
    
    # 🌟 FIX: Use unique locations instead of raw tasks, and inject the star!
    for i, (addr, metrics) in enumerate(list(stop_metrics.items())[:2], start=1):
        esc_star = "⭐ " if metrics['esc'] else ""
        stops_text += f"📍 Stop {i}: {esc_star}{addr}\n"
        
    if len(stop_metrics) > 2:
        stops_text += f"   ... and {len(stop_metrics) - 2} more stops.\n"

    # Calculate total kiosk installs and digital tasks across the whole route
    total_installs = sum(metrics['inst'] for metrics in stop_metrics.values())
    total_digital = sum(metrics['digi'] for metrics in stop_metrics.values()) # 🌟 FIX: Calculate Digital Total
    
    install_warning = "⚠️ Please Note: This route contains kiosk install(s) which will require heavy lifting of up to 50lbs.\n\n" if total_installs > 0 else ""

    
    
    # --- 🌟 FIX: PRE-CALCULATE DATA FOR EMAIL & BUTTON ---
    total_digital = sum(1 for t in cluster['data'] if t.get('is_digital'))
    install_warning = "⚠️ NOTE: This route contains Kiosk Installs. Please ensure you have adequate vehicle space.\n\n" if any("install" in str(t.get('task_type','')).lower() for t in cluster['data']) else ""

    # Build the Location Pills (The icons for each address)
    loc_pills = {}
    for t in cluster['data']:
        addr = t.get('full', 'Unknown')
        if addr not in loc_pills: loc_pills[addr] = ""
        if t.get('escalated') and "⭐" not in loc_pills[addr]: loc_pills[addr] += "⭐"
        if t.get('is_digital') and "🔌" not in loc_pills[addr]: loc_pills[addr] += "🔌"
        if "install" in str(t.get('task_type','')).lower() and "🛠️" not in loc_pills[addr]: loc_pills[addr] += "🛠️"
        if "removal" in str(t.get('task_type','')).lower() and "🗑️" not in loc_pills[addr]: loc_pills[addr] += "🗑️"

    # --- 🌟 FIX 1: USE THE CORRECT LINK ID ---
    real_id = st.session_state.get(sync_key)
    link_id = real_id if real_id else "LINK_PENDING"

    # --- DYNAMIC EMAIL PREVIEW ---
    due = st.session_state.get(f"dd_{cluster_hash}", datetime.now().date()+timedelta(14))
    
    # Smart Work Order Logic
    prev_ic_name = cluster.get('contractor_name', 'Unknown')
    if ic['Name'] == prev_ic_name and cluster.get('wo', 'none') != 'none':
        wo_val = cluster['wo']
    else:
        wo_val = f"{ic['Name']} - {datetime.now().strftime('%m%d%Y')}"
    
    # 🌟 FIX 2: Inject link_id directly into the template
    sig_preview = (
        f"Hello {ic['Name']},\n\n"
        f"We have a new route available for you to review.\n\n"
        f" Work Order: {wo_val}\n"
        f"📅 Due Date: {due.strftime('%A, %b %d, %Y')}\n"
        f" Total Stops: {cluster['stops']}\n"
        f" Estimated Compensation: ${final_pay:.2f}\n"
        f" 🔌 Digital Tasks: {total_digital}\n\n" 
        f"{install_warning}"
        f"To view the complete route details—including total stops, estimated mileage, and time—please click the secure link below to access your Route Summary.\n\n"
        f"⚠️ ACTION REQUIRED:\n"
        f"You must confirm by selecting 'Accept' or 'Decline' directly through the portal link.\n\n"
        f"Route Summary Link:\n"
        f"{PORTAL_BASE_URL}?route={link_id}&v2=true"
    )
    
    # Versioning logic
    last_data_key = f"last_data_{cluster_hash}"
    version_key = f"tx_ver_{cluster_hash}"
    current_data_fingerprint = f"{ic['Name']}_{final_pay}_{due}_{wo_val}"
    
    if version_key not in st.session_state:
        st.session_state[version_key] = 1

    if st.session_state.get(last_data_key) != current_data_fingerprint:
        st.session_state[version_key] += 1
        st.session_state[last_data_key] = current_data_fingerprint
        # Initialize the new version with the preview
        st.session_state[f"tx_{cluster_hash}_{st.session_state[version_key]}"] = sig_preview
    
    active_tx_key = f"tx_{cluster_hash}_{st.session_state[version_key]}"

    # 🌟 FIX 3: ENSURE THE BOX IS NEVER BLANK
    # If the user edited the text, but then we generated a real ID, swap the placeholder
    if active_tx_key not in st.session_state:
        st.session_state[active_tx_key] = sig_preview
    elif real_id and "LINK_PENDING" in st.session_state[active_tx_key]:
        st.session_state[active_tx_key] = st.session_state[active_tx_key].replace("LINK_PENDING", real_id)
    
    email_body_content = st.text_area("Email Content Preview", height=180, key=active_tx_key, disabled=not is_unlocked)

    # --- 7. BUTTON LAYOUT ---
    btn_label = "🚀 GENERATE LINK & OPEN GMAIL"

    with st.container():
        if st.button(btn_label, type="primary", key=f"gbtn_{cluster_hash}", disabled=not is_unlocked, use_container_width=True):
            with st.spinner("Syncing latest data & generating link..."):
                home = ic['Location']
                
                # Pre-calculate the payload
                payload = {
                    "cluster_hash": cluster_hash,
                    "icn": ic['Name'], "ice": ic['Email'], "wo": wo_val, 
                    "due": str(due), "comp": final_pay, "lCnt": cluster['stops'], "mi": mi, "time": t_str, "phone": str(ic['Phone']),
                    "locs": " | ".join([home] + list(stop_metrics.keys()) + [home]),
                    "taskIds": ",".join(task_ids),
                    "tCnt": len(task_ids),
                    "jobOnly": " | ".join([f"{addr} {pills}" for addr, pills in loc_pills.items()])
                }

                # 🌟 1. HIT THE SERVER ONCE
                try:
                    res = requests.post(GAS_WEB_APP_URL, json={"action": "saveRoute", "payload": payload}, timeout=10).json()
                except Exception as e:
                    st.error(f"Connection Error: {e}")
                    st.stop()
                
                if res.get("success"):
                    final_route_id = res.get("routeId")
                    
                    # 🌟 1. PREPARE THE EMAIL (Inject the real ID for Gmail)
                    # We use email_body_content to preserve any manual edits you made
                    final_sig = email_body_content.replace("LINK_PENDING", final_route_id)
                    subject_line = f"Route Request | {wo_val}"
                    gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={ic['Email']}&su={requests.utils.quote(subject_line)}&body={requests.utils.quote(final_sig)}"
                    
                    # 🌟 2. OPEN GMAIL
                    st.components.v1.html(f"<script>window.open('{gmail_url}', '_blank');</script>", height=0)
                    
                    # 🌟 3. UPDATE SESSION STATE (Moving the card to 'Sent')
                    st.session_state[sync_key] = final_route_id
                    st.session_state[f"sent_ts_{cluster_hash}"] = datetime.now().strftime('%m/%d %I:%M %p')
                    st.session_state[f"contractor_{cluster_hash}"] = ic['Name']
                    st.session_state[f"route_state_{cluster_hash}"] = "email_sent"
                    st.session_state[f"reverted_{cluster_hash}"] = False
                    
                    # 🚀 FIX: Removed the line that causes the StreamlitAPIException crash.
                    # Your 'Fix 3' at the top will handle the text area refresh on rerun!
                    
                    # 🌟 4. THE VISUAL TIMER
                    timer_placeholder = st.empty()
                    for seconds in range(3, 0, -1):
                        timer_placeholder.success(f"✅ Link Live! Moving to 'Sent' in {seconds}s...")
                        time.sleep(1)
                    timer_placeholder.empty()
                    
                    # 🌟 5. FINALLY RERUN
                    st.rerun()
            
def run_pod_tab(pod_name):
    # Grab the contractor database from session state
    ic_df = st.session_state.get('ic_df', pd.DataFrame())
    
    # ... rest of your header code ...
    # Grab the matching "Midnight" text color for the current pod
    text_color = {
        "Blue": "#1e3a8a",
        "Green": "#064e3b",
        "Orange": "#7c2d12",
        "Purple": "#4c1d95",
        "Red": "#7f1d1d"
    }.get(pod_name, "#633094") # Defaults to TB Purple if not found
    
    # Inject the dynamic color into the centered header
    st.markdown(f"<h2 style='color: {text_color}; text-align:center;'>{pod_name} Pod Dashboard</h2>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # Check if data exists for this pod
    if f"clusters_{pod_name}" not in st.session_state:
        if st.button(f"🚀 Initialize {pod_name} Data", key=f"init_{pod_name}"):
            process_pod(pod_name)
            st.rerun()
        return
        
    # Load cluster data
    cls = st.session_state[f"clusters_{pod_name}"]

    if not cls:
        st.info(f"No tasks pending in the {pod_name} region.")
        if st.button("🔄 Check Again", key=f"empty_ref_{pod_name}"):
            process_pod(pod_name); st.rerun()
        return

    # --- KEEPING THE CLEAN AUTO-SYNC LOGIC ---
    sent_db, ghost_db = fetch_sent_records_from_sheet()
    pod_ghosts = ghost_db.get(pod_name, [])

    # Added 'finalized' to the list
    ready, review, sent, accepted, declined, finalized = [], [], [], [], [], []

    for c in cls:
        task_ids = [str(t['id']).strip() for t in c['data']]
        cluster_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
        
        sheet_match = sent_db.get(next((tid for tid in task_ids if tid in sent_db), None))
        route_state = st.session_state.get(f"route_state_{cluster_hash}")
        local_ts = st.session_state.get(f"sent_ts_{cluster_hash}", "")
        local_contractor = st.session_state.get(f"contractor_{cluster_hash}", "Unknown")
        
        # Check if the dispatcher manually revoked this route
        is_reverted = st.session_state.get(f"reverted_{cluster_hash}", False)
        
        if sheet_match and not is_reverted:
            c['contractor_name'] = sheet_match.get('name', 'Unknown')
            c['route_ts'] = sheet_match.get('time', '') or local_ts
            c['wo'] = sheet_match.get('wo', c['contractor_name'])
        else:
            c['contractor_name'] = local_contractor
            c['route_ts'] = local_ts
        
        # --- NEW PRIORITY: LIVE DATABASE OVERRIDES LOCAL STATE ---
        if sheet_match and not is_reverted:
            raw_status = str(sheet_match.get('status', '')).lower()
            if raw_status == 'declined':
                declined.append(c)
            elif raw_status == 'accepted':
                accepted.append(c)
            elif raw_status == 'finalized': # NEW: Catch finalized status
                finalized.append(c)
            else:
                sent.append(c)
        elif route_state == "email_sent" and not is_reverted:
            sent.append(c)
        elif route_state == "link_generated" and not is_reverted:
            orig = st.session_state.get(f"orig_status_{cluster_hash}")
            if orig == "declined":
                declined.append(c)
            else:
                ready.append(c)
        else:
            # Falls back into standard Dispatching
            if c.get('status') == 'Ready': 
                ready.append(c)
            else: 
                review.append(c)

    total_tasks = sum(len(c['data']) for c in cls)
    total_stops = sum(c['stops'] for c in cls)
    total_routes = len(cls)

    # 🌟 NEW: Add ghosts to the Tracking Math
    total_accepted = len(accepted) + len(pod_ghosts)
    total_dispatched = len(sent) + total_accepted + len(declined)

    # We swap the widths so the wider 'Routes' card fits on the left
    c1, c2, c3 = st.columns([1.5, 1, 1.5])

    # Dashboard Supercards (Now with Hover Glow!)
    c1, c2, c3 = st.columns([1.5, 1, 1.5])

    with c1:
        st.markdown(f"""
            <div class='dashboard-supercard' style='background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:10px; box-shadow:0 2px 4px rgba(0,0,0,0.05); margin-bottom:20px; height: 110px;'>
                <p style='margin:0 0 5px 0; font-size:11px; font-weight:800; color:#000000; text-transform:uppercase; text-align:center;'>Total Routes: {total_routes}</p>
                <div style='display:flex; justify-content:space-between; gap:8px;'>
                    <div style='background:{TB_GREEN_FILL}; flex:1; padding:8px; border-radius:8px; text-align:center;'>
                        <p style='margin:0; font-size:9px; font-weight:800; color:#000000;'>READY</p>
                        <p style='margin:0; font-size:20px; font-weight:800; color:#000000;'>{len(ready)}</p>
                    </div>
                    <div style='background:{TB_BLUE_FILL}; flex:1; padding:8px; border-radius:8px; text-align:center;'>
                        <p style='margin:0; font-size:9px; font-weight:800; color:#000000;'>SENT (PENDING)</p>
                        <p style='margin:0; font-size:20px; font-weight:800; color:#000000;'>{len(sent)}</p>
                    </div>
                    <div style='background:{TB_RED_FILL}; flex:1; padding:8px; border-radius:8px; text-align:center;'>
                        <p style='margin:0; font-size:9px; font-weight:800; color:#000000;'>FLAGGED</p>
                        <p style='margin:0; font-size:20px; font-weight:800; color:#000000;'>{len(review)}</p>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
            <div class='dashboard-supercard' style='background:#f8fafc; border:1px solid #cbd5e1; border-radius:12px; padding:15px; box-shadow:0 2px 4px rgba(0,0,0,0.05); margin-bottom:20px; height: 110px;'>
                <div style='display:flex; justify-content:space-around; text-align:center; height:100%; align-items:center;'>
                    <div>
                        <p style='margin:0; font-size:11px; font-weight:800; color:#000000; text-transform:uppercase;'>Total Tasks</p>
                        <p style='margin:0; font-size:26px; font-weight:800; color:#000000;'>{total_tasks}</p>
                    </div>
                    <div style='border-left: 2px solid #cbd5e1; height: 40px;'></div>
                    <div>
                        <p style='margin:0; font-size:11px; font-weight:800; color:#000000; text-transform:uppercase;'>Total Stops</p>
                        <p style='margin:0; font-size:26px; font-weight:800; color:#000000;'>{total_stops}</p>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
            <div class='dashboard-supercard' style='background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:10px; box-shadow:0 2px 4px rgba(0,0,0,0.05); height: 110px;'>
                <p style='margin:0 0 5px 0; font-size:11px; font-weight:800; color:#000000; text-transform:uppercase; text-align:center;'>Dispatched Tracking: {total_dispatched}</p>
                <div style='display:flex; justify-content:space-between; gap:8px;'>
                    <div style='background:{TB_GREEN_FILL}; flex:1; padding:8px; border-radius:8px; text-align:center;'>
                        <p style='margin:0; font-size:9px; font-weight:800; color:#000000;'>ACCEPTED</p>
                        <p style='margin:0; font-size:20px; font-weight:800; color:#000000;'>{total_accepted}</p>
                    </div>
                    <div style='background:{TB_RED_FILL}; flex:1; padding:8px; border-radius:8px; text-align:center;'>
                        <p style='margin:0; font-size:9px; font-weight:800; color:#000000;'>DECLINED</p>
                        <p style='margin:0; font-size:20px; font-weight:800; color:#000000;'>{len(declined)}</p>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
    # --- ACTION BUTTON ---
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("⚙️ Re-Optimize Routes", use_container_width=True, key=f"reopt_{pod_name}"):
        st.session_state.pop(f"clusters_{pod_name}", None) # Wipes current clusters
        process_pod(pod_name) # Re-runs Onfleet pull and clustering
        st.rerun()

    # --- MAP RENDERING (STAYS RIGHT BELOW) ---
    
    # We use the first cluster as the center point
    m = folium.Map(location=cls[0]['center'], zoom_start=6, tiles="cartodbpositron")
    
    # Draw markers
    for c in ready: folium.CircleMarker(c['center'], radius=8, color=TB_GREEN, fill=True, opacity=0.8).add_to(m)
    for c in sent: folium.CircleMarker(c['center'], radius=8, color="#3b82f6", fill=True, opacity=0.8).add_to(m)
    for c in review: folium.CircleMarker(c['center'], radius=8, color="#ef4444", fill=True, opacity=0.8).add_to(m)
    
    # FIX: Remove width=1100 and use container width for responsiveness
    st_folium(m, height=400, use_container_width=True, key=f"map_{pod_name}")
    
    # --- ICON KEY (LEGEND) ---
    # (Pushed to the far left so Streamlit doesn't turn it into a code block)
    st.markdown("""
<div style="display: flex; justify-content: center; flex-wrap: wrap; gap: 20px; background: #ffffff; padding: 12px; border-radius: 12px; border: 1px solid #cbd5e1; margin-top: -10px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
    <div style="font-size: 11px; font-weight: 800; color: #64748b; text-transform: uppercase; align-self: center; margin-right: 10px;">Route Key:</div>
    <div style="font-size: 13px; cursor: help;" title="Route is within distance limits (<60mi) and standard rate (<$25/stop).">🟢 Ready</div>
    <div style="font-size: 13px; cursor: help;" title="Route is frozen and requires manual authorization before sending.">🔒 Action Required</div>
    <div style="font-size: 13px; cursor: help;" title="The calculated price per stop is $25.00 or higher.">💰 High Rate</div>
    <div style="font-size: 13px; cursor: help;" title="The closest contractor is more than 60 miles away.">📡 Long Distance</div>
    <div style="font-size: 13px; cursor: help;" title="Route was flagged for review (e.g., low density).">🔴 Flagged</div>
    <div style="font-size: 13px; cursor: help;" title="Priority: Contains escalated tasks.">⭐ Escalated</div>
    <div style="font-size: 13px; cursor: help;" title="Digital Service: Contains digital service requests.">🔌Digital Service</div>
    <div style="font-size: 13px; cursor: help;" title="Route request has been sent to the contractor.">✉️ Sent</div>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")

    # Create two equal-width columns for side-by-side layout
    # [4, 5.5] ratio makes the left card narrower and the right side wider
    col_left, col_right = st.columns([4.5, 5.5])

    with col_left:
        # ==========================================
        # SECTION 1: DISPATCH (LEFT SIDE - CENTERED)
        # ==========================================
        st.markdown(f"<div style='font-size: 1.5rem; font-weight: 800; color: {TB_PURPLE}; margin-bottom: 5px; text-align: center;'>🚀 Dispatch</div>", unsafe_allow_html=True)
        t_ready, t_flagged = st.tabs(["📥 Ready", "⚠️ Flagged"])

        with t_ready:
            if not ready: st.info("No tasks ready for dispatch.")
            for i, c in enumerate(ready):
                # --- PRE-CALCULATE BADGES ---
                badges = ""
                if not ic_df.empty:
                    v_ics = ic_df[~ic_df.astype(str).apply(lambda x: x.str.contains('Field Agent', case=False, na=False).any(), axis=1)].dropna(subset=['Lat', 'Lng']).copy()
                    if not v_ics.empty:
                        v_ics['d'] = v_ics.apply(lambda x: haversine(c['center'][0], c['center'][1], x['Lat'], x['Lng']), axis=1)
                        closest_ic = v_ics.sort_values('d').iloc[0]
                        _, hrs, _ = get_gmaps(closest_ic['Location'], [t['full'] for t in c['data'][:25]])
                        est_pay = max(c['stops'] * 18.0, hrs * 25.0)
                        est_rate = est_pay / c['stops'] if c['stops'] > 0 else 0
                        
                        if est_rate >= 25.0: badges += " 💰"
                        if closest_ic['d'] > 60: badges += " 📡"
                        if est_rate >= 25.0 or closest_ic['d'] > 60: badges = " 🔒" + badges

                esc_pill = f"  [ ⭐ {c.get('esc_count', 0)} ]" if c.get('esc_count', 0) > 0 else ""
                digi_pill = " 🔌" if c.get('is_digital') else ""  
                inst_pill = f"  [ 🛠️ {c.get('inst_count', 0)} Installs ]" if c.get('inst_count', 0) > 0 else "" # 🌟 FIX
                with st.expander(f"{badges} 🟢 {c['city']}, {c['state']} | {c['stops']} Stops{digi_pill}{inst_pill}{esc_pill}"):
                    render_dispatch(i, c, pod_name)
                    
        with t_flagged:
            if not review: st.info("No flagged tasks requiring review.")
            for i, c in enumerate(review):
                esc_pill = f"  [ ⭐ {c.get('esc_count', 0)} ]" if c.get('esc_count', 0) > 0 else ""
                digi_pill = " 🔌" if c.get('is_digital') else ""  
                inst_pill = f"  [ 🛠️ {c.get('inst_count', 0)} Installs ]" if c.get('inst_count', 0) > 0 else "" # 🌟 FIX
                with st.expander(f"🔒 🔴 {c['city']}, {c['state']} | {c['stops']} Stops{digi_pill}{inst_pill}{esc_pill}"):
                    render_dispatch(i+1000, c, pod_name)

    with col_right:
        # ==========================================
        # SECTION 2: AWAITING CONFIRMATION (RIGHT SIDE - CENTERED)
        # ==========================================
        st.markdown(f"<div style='font-size: 1.5rem; font-weight: 800; color: {TB_GREEN}; margin-bottom: 5px; text-align: center;'>⏳ Awaiting Confirmation</div>", unsafe_allow_html=True)
        t_sent, t_acc, t_dec, t_fin = st.tabs(["✉️ Sent (Pending)", "✅ Accepted", "❌ Declined", "🏁 Finalized"])
        
        with t_sent:
            if not sent: st.info("No pending routes sent.")
            for i, c in enumerate(sent):
                ic_name = c.get('contractor_name', 'Unknown')
                esc_pill = f"  [ ⭐ {c.get('esc_count', 0)} ]" if c.get('esc_count', 0) > 0 else ""
                digi_pill = " 🔌" if c.get('is_digital') else ""  
                inst_pill = f"  [ 🛠️ {c.get('inst_count', 0)} Installs ]" if c.get('inst_count', 0) > 0 else ""
                
                # Re-calculate hash for the quick-revoke button
                task_ids = [str(t['id']).strip() for t in c['data']]
                cluster_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
                
                # Clean native columns, perfectly centered
                exp_col, btn_col = st.columns([8.2, 1.8], vertical_alignment="center")
                
                with exp_col:
                    ts_suffix = f" | {c.get('route_ts', '')}" if c.get('route_ts') else ""
                    digi_pill = " 🔌" if c.get('is_digital') else ""
                    inst_pill = f"  [ 🛠️ {c.get('inst_count', 0)} Installs ]" if c.get('inst_count', 0) > 0 else ""
                    with st.expander(f"✉️ {ic_name} | {c['city']}, {c['state']}{digi_pill}{inst_pill}{esc_pill}{ts_suffix}"):
                        render_dispatch(i+500, c, pod_name, is_sent=True)
                        
                with btn_col:
                    # Pure Streamlit Button (No HTML wrapping!)
                    st.button(
                        "↩️ Revoke", 
                        key=f"instant_rev_{cluster_hash}", 
                        on_click=instant_revoke_handler,
                        args=(cluster_hash, ic_name, c, pod_name),
                        use_container_width=True
                    )
        with t_acc:
            if not accepted and not pod_ghosts: st.info("Waiting for portal acceptances...")
            
            for i, c in enumerate(accepted):
                ic_name = c.get('contractor_name', 'Unknown')
                wo_display = c.get('wo', ic_name)
                ts_suffix = f" | {c.get('route_ts', '')}" if c.get('route_ts') else ""
                
                task_ids = [str(t['id']).strip() for t in c['data']]
                cluster_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
                
                exp_col, btn_col = st.columns([8.2, 1.8], vertical_alignment="center")
                
                with exp_col:
                    digi_pill = " 🔌" if c.get('is_digital') else "" # 🌟 FIX: Added the plug
                    with st.expander(f"✅ {wo_display} | {c['city']}, {c['state']}{digi_pill}{ts_suffix}"):
                        st.success("Route accepted. Tasks are assigning in Onfleet.")
                        
                        # --- SEQUENTIAL CHECKLIST ---
                        st.divider()
                        st.markdown("<p style='font-weight:800; color:#16a34a;'>📋 Operational Readiness</p>", unsafe_allow_html=True)
                        
                        # Step 1: Onfleet Optimization
                        step1 = st.checkbox("1. **Onfleet**: Optimized route?", key=f"s1_{cluster_hash}")
                        
                        # Step 2: Backend Plan (Disabled until Step 1 is done)
                        step2 = st.checkbox("2. **Plan**: Fields & Backend Dispatch?", key=f"s2_{cluster_hash}", disabled=not step1)
                        
                        # Step 3: Packing List (Disabled until Step 2 is done)
                        # Automatic trigger: if step3 is clicked, fire the database update
                        if st.checkbox("3. **Pack**: Packing list uploaded?", key=f"s3_{cluster_hash}", disabled=not step2):
                            finalize_route_handler(cluster_hash)
                            st.rerun()

                        render_dispatch(i+2000, c, pod_name, is_sent=True)
                        
                with btn_col:
                    # Keep the manual revoke option for emergencies 
                    with st.popover("↩️ Revoke", use_container_width=True):
                        st.error(f"Revoke from {ic_name}?")
                        if st.button("🚨 Yes, Revoke", key=f"rev_acc_{cluster_hash}", type="primary"):
                            move_to_dispatch(cluster_hash, ic_name, pod_name, action_label="Revoked", check_onfleet=True)
                            st.rerun()

            # --- 2. GHOST ROUTES ---
            for i, g in enumerate(pod_ghosts):
                wo_display = g.get('wo', g.get('contractor_name', 'Unknown'))
                ts_suffix = f" | {g.get('route_ts', '')}"
                ghost_hash = g.get('hash', f"ghost_{i}") # Grab the hash we created
                
                with st.expander(f"✅ {wo_display} | {g.get('city', 'Unknown')}, {g.get('state', 'Unknown')}{ts_suffix}"):
                    st.success("Route accepted and tasks successfully assigned in OnFleet.")
                    st.markdown(f"""
                        <div style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px; padding:12px; margin-top:5px;">
                            <p style="margin:0; font-size:12px; color:#64748b; font-weight:800; text-transform:uppercase;">Historical Route Data</p>
                            <div style="display:flex; justify-content:space-between; margin-top:8px;">
                                <div><span style="font-size:11px; color:#475569;">Original Tasks:</span><br><b style="color:#000000; font-size:16px;">{g.get('tasks', 0)}</b></div>
                                <div><span style="font-size:11px; color:#475569;">Stops:</span><br><b style="color:#000000; font-size:16px;">{g.get('stops', 0)}</b></div>
                                <div><span style="font-size:11px; color:#475569;">Compensation:</span><br><b style="color:#22c55e; font-size:16px;">${g.get('pay', 0)}</b></div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # 🌟 FIX: Inject Operational Readiness Checklist for Ghost Routes
                    st.divider()
                    st.markdown("<p style='font-weight:800; color:#16a34a;'>📋 Operational Readiness</p>", unsafe_allow_html=True)
                    
                    # Added '_{i}' to the end of each key to guarantee they are 100% unique!
                    s1 = st.checkbox("1. **Onfleet**: Optimized route?", key=f"g_s1_{ghost_hash}_{i}")
                    s2 = st.checkbox("2. **Plan**: Fields & Backend Dispatch?", key=f"g_s2_{ghost_hash}_{i}", disabled=not s1)
                    
                    if st.checkbox("3. **Pack**: Packing list uploaded?", key=f"g_s3_{ghost_hash}_{i}", disabled=not s2):
                        finalize_route_handler(ghost_hash)
                        st.rerun()
                    
        with t_dec:
            if not declined: st.info("No declined routes.")
            for i, c in enumerate(declined):
                ic_name = c.get('contractor_name', 'Unknown')
                ts_label = f" | {c.get('route_ts', '')}" if c.get('route_ts') else ""
                esc_pill = f"  [ ⭐ {c.get('esc_count', 0)} ]" if c.get('esc_count', 0) > 0 else ""
                digi_pill = " 🔌" if c.get('is_digital') else ""  
                inst_pill = f"  [ 🛠️ {c.get('inst_count', 0)} Installs ]" if c.get('inst_count', 0) > 0 else ""
                
                # Re-calculate hash for the quick-action button
                task_ids = [str(t['id']).strip() for t in c['data']]
                cluster_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
                
                # Use the exact same [5, 1] layout as the Sent tab
                # Gives the button enough room to stay on one line, and vertically centers them
                exp_col, btn_col = st.columns([8.2, 1.8], vertical_alignment="center")
                
                with exp_col:
                    digi_pill = " 🔌" if c.get('is_digital') else "" # 🌟 FIX: Added the plug
                    with st.expander(f"❌ {ic_name} | {c['city']}, {c['state']}{digi_pill}{esc_pill}{ts_suffix}"):
                        st.error("Route declined. Select a new contractor below to generate a fresh link.")
                        render_dispatch(i+3000, c, pod_name, is_declined=True)
                        
                with btn_col:
                    clicked = st.button("↩️ Re-Route", key=f"quick_reroute_{cluster_hash}", help="Pull this declined route back to Dispatch", use_container_width=True)
                    
                    if clicked:
                        move_to_dispatch(cluster_hash, ic_name, pod_name, action_label="Declined", check_onfleet=False)
                        st.rerun()
        with t_fin:
            if not finalized: st.info("No finalized routes.")
            for i, c in enumerate(finalized):
                ic_name = c.get('contractor_name', 'Unknown')
                ts_suffix = f" | {c.get('route_ts', '')}" if c.get('route_ts') else ""
                
                task_ids = [str(t['id']).strip() for t in c['data']]
                cluster_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
                
                exp_col, btn_col = st.columns([8.2, 1.8], vertical_alignment="center")
                
                with exp_col:
                    digi_pill = " 🔌" if c.get('is_digital') else "" # 🌟 FIX: Added the plug
                    with st.expander(f"🏁 {ic_name} | {c['city']}, {c['state']}{digi_pill}{ts_suffix}"):
                        st.info("Route is archived in Finalized.")
                        render_dispatch(i+4000, c, pod_name, is_sent=True)
                
                with btn_col:
                    # Allows moving work back to Dispatch if a mistake was made
                    if st.button("↩️ Re-Route", key=f"fin_rr_{cluster_hash}", use_container_width=True):
                        move_to_dispatch(cluster_hash, ic_name, pod_name, action_label="Finalized", check_onfleet=False)
                        st.rerun()
                        
# --- START ---
if "ic_df" not in st.session_state:
    try:
        url = f"{IC_SHEET_URL.split('/edit')[0]}/export?format=csv&gid=0"
        st.session_state.ic_df = pd.read_csv(url)
    except: st.error("Database connection failed.")

# --- HEADER ROW (Title & Refresh Button) ---
# [1, 8, 2] ratio gives the refresh button enough room to stay flat
col_left_space, col_main_title, col_ref = st.columns([1, 8, 2])

with col_main_title:
    st.markdown("<h1 style='color: #633094;'>Terraboost Media: Dispatch Command Center</h1>", unsafe_allow_html=True)

with col_ref:
    st.markdown("<div class='refresh-btn-container' style='margin-top: 26px;'>", unsafe_allow_html=True)
    if st.button("🔄 Refresh", key="top_ref_btn"):
        st.cache_data.clear()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# Define the tabs for the entire app
tabs = st.tabs(["Global", "Blue Pod", "Green Pod", "Orange Pod", "Purple Pod", "Red Pod"])

# --- TAB 0: GLOBAL CONTROL ---
with tabs[0]:
    st.markdown("<h2 style='color: #633094; text-align:center;'>🌍 Global Command Overview</h2>", unsafe_allow_html=True)
    
    # --- 1. INITIALIZE BUTTON ---
    c_btn = st.columns([1,2,1])[1]
    if c_btn.button("🚀 Initialize All Pods", key="global_init_btn", use_container_width=True):
        st.session_state.sent_db, st.session_state.ghost_db = fetch_sent_records_from_sheet()
        st.session_state.trigger_pull = True

    st.markdown("---")
    
    # NEW: Placeholder to anchor the progress bar ABOVE the cards
    loading_placeholder = st.empty()

    # --- 2. PILL CARDS LOOP ---
    cols = st.columns(len(POD_CONFIGS))
    pod_keys = list(POD_CONFIGS.keys())
    global_map = folium.Map(location=[39.8283, -98.5795], zoom_start=4, tiles="cartodbpositron")
    
    current_sent_db, ghost_db = fetch_sent_records_from_sheet()

    for i, pod in enumerate(pod_keys):
        # Python Colors Mapping
        colors = {
            "Blue":   {"border": "#3b82f6", "bg": "#f0f7ff", "text": "#1e3a8a"},
            "Green":  {"border": "#22c55e", "bg": "#f0fdf4", "text": "#064e3b"},
            "Orange": {"border": "#f97316", "bg": "#fffaf5", "text": "#7c2d12"},
            "Purple": {"border": "#a855f7", "bg": "#faf5ff", "text": "#4c1d95"},
            "Red":    {"border": "#ef4444", "bg": "#fef2f2", "text": "#7f1d1d"}
        }.get(pod)
        
        with cols[i]:
            is_loading = st.session_state.get("current_loading_pod") == pod
            has_data = f"clusters_{pod}" in st.session_state
            
            # --- CONSTRUCT INNER CONTENT ---
            if is_loading:
                card_content = f"<p class='loading-pulse' style='color:{colors['border']}; margin-top:25px;'>📡 SYNCING...</p>"
            elif has_data:
                pod_cls = st.session_state[f"clusters_{pod}"]
                total_routes = len(pod_cls)
                total_tasks = sum(len(c['data']) for c in pod_cls)
                total_stops = sum(c['stops'] for c in pod_cls)
                
                # --- EXACT SYNC LOGIC FROM POD TABS ---
                sent, accepted, declined = [], [], []
                for c in pod_cls:
                    task_ids = [str(t['id']).strip() for t in c['data']]
                    cluster_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
                    
                    sheet_match = current_sent_db.get(next((tid for tid in task_ids if tid in current_sent_db), None))
                    route_state = st.session_state.get(f"route_state_{cluster_hash}")
                    is_reverted = st.session_state.get(f"reverted_{cluster_hash}", False)
                    
                    # --- NEW PRIORITY: LIVE DATABASE OVERRIDES LOCAL STATE ---
                    if sheet_match and not is_reverted:
                        raw_status = sheet_match.get('status')
                        if raw_status == 'declined':
                            declined.append(c)
                        elif raw_status == 'accepted':
                            accepted.append(c)
                        else:
                            sent.append(c)
                    elif route_state == "email_sent" and not is_reverted:
                        sent.append(c)
                    elif route_state == "link_generated" and not is_reverted:
                        orig = st.session_state.get(f"orig_status_{cluster_hash}")
                        if orig == "declined":
                            declined.append(c)
                
                # Combine Live data with Ghost History
                pod_ghosts = ghost_db.get(pod, [])
                total_accepted = len(accepted) + len(pod_ghosts)
                true_sent_count = len(sent) + total_accepted + len(declined)
                visual_total_routes = len(pod_cls) + len(pod_ghosts)
                
                # Metrics HTML (Flushed Left to prevent markdown code blocks)
                card_content = f"""
<p style='margin: 10px 0 0 0; font-size: 26px; font-weight: 800; color: {colors['text']};'>{true_sent_count} / {visual_total_routes}</p>
<p style='margin: -5px 0 0 0; font-size: 11px; font-weight: 700; color: {colors['text']}; opacity: 0.6; text-transform: uppercase;'>Routes Sent</p>
<p style='margin: 2px 0 8px 0; font-size: 9px; font-weight: 700; color: {colors['text']}; opacity: 0.5;'>{total_accepted} ACCEPTED | {len(declined)} DECLINED</p>
<div style='display: flex; justify-content: space-around; border-top: 1px solid rgba(0,0,0,0.08); padding-top: 10px;'>
<div><p style='margin:0; font-size:9px; color: {colors['text']}; opacity: 0.8; font-weight: 800;'>TASKS</p><b style='color: {colors['text']};'>{total_tasks}</b></div>
<div style='border-left: 1px solid rgba(0,0,0,0.08); height: 20px;'></div>
<div><p style='margin:0; font-size:9px; color: {colors['text']}; opacity: 0.8; font-weight: 800;'>STOPS</p><b style='color: {colors['text']};'>{total_stops}</b></div>
</div>
"""
                for c in pod_cls: folium.CircleMarker(c['center'], radius=5, color=colors['border'], fill=True, fill_opacity=0.7).add_to(global_map)
            else:
                card_content = f"<p style='color: {colors['text']}; opacity: 0.3; font-weight: 800; margin-top: 30px;'>OFFLINE</p>"

            # --- RENDER THE PILL (Entire string Flushed Left) ---
            st.markdown(f"""
<div class="pod-card-pill" style="border: 2px solid {colors['border']}; border-radius: 30px; padding: 20px 10px; background-color: {colors['bg']}; text-align: center; height: 190px; box-shadow: 0 4px 10px rgba(0,0,0,0.03); display: flex; flex-direction: column; justify-content: center;">
<div style="margin: 0; color: {colors['text']}; font-weight: 800; font-size: 1.2rem;">{pod} Pod</div>
{card_content}
</div>
""", unsafe_allow_html=True)
            
    # --- 3. THE LOADING ZONE (Progress Bar ABOVE cards via placeholder) ---
    if st.session_state.get("trigger_pull"):
        st.session_state.sent_db, st.session_state.ghost_db = fetch_sent_records_from_sheet()
        # THE FIX: Tell the progress bar to render inside the placeholder we made up top
        p_bar = loading_placeholder.progress(0, text="🎬 Initializing Operational Data...")
        for idx, p in enumerate(pod_keys):
            st.session_state.current_loading_pod = p 
            process_pod(p, master_bar=p_bar, pod_idx=idx, total_pods=len(pod_keys))
        st.session_state.current_loading_pod = None
        st.session_state.trigger_pull = False
        st.rerun()

    # --- 4. MASTER MAP ---
    st.markdown("<br> 🗺️ Master Route Map", unsafe_allow_html=True)
    st_folium(global_map, height=500, use_container_width=True, key="global_master_map")

# --- INDIVIDUAL POD TABS ---
for i, pod in enumerate(["Blue", "Green", "Orange", "Purple", "Red"], 1):
    with tabs[i]: run_pod_tab(pod)
