import streamlit as st
import requests
import uuid
import time
from requests.exceptions import ConnectionError, Timeout

# --- CONFIG ---
BASE_URL = "http://localhost:8000"

st.set_page_config(
    page_title="Nexus AI", 
    page_icon="🔮", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS STYLING ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stButton>button {border-radius: 8px; font-weight: 600;}
    .stChatMessage {border-radius: 15px; padding: 1rem; margin-bottom: 0.5rem;}
    [data-testid="stSidebar"] h1 {
        background: -webkit-linear-gradient(45deg, #FE6B8B 30%, #FF8E53 90%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
    }
</style>
""", unsafe_allow_html=True)

# --- STATE INIT ---
if "token" not in st.session_state: st.session_state.token = None
if "user" not in st.session_state: st.session_state.user = None
if "current_session_id" not in st.session_state: st.session_state.current_session_id = str(uuid.uuid4())
if "messages" not in st.session_state: st.session_state.messages = []

# --- HELPERS ---
def get_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}

def load_session_messages(session_id):
    try:
        # Increased timeout to 10s for history fetching
        resp = requests.get(f"{BASE_URL}/history/{session_id}", headers=get_headers(), timeout=10)
        if resp.status_code == 200:
            st.session_state.messages = []
            for h in resp.json():
                st.session_state.messages.append({"role": "user", "type": "text", "content": h["prompt"]})
                rtype = "image" if "http" in h["response"] or "data:image" in h["response"] else "text"
                st.session_state.messages.append({"role": "assistant", "type": rtype, "content": h["response"]})
            st.session_state.current_session_id = session_id
            st.rerun()
    except Exception as e:
        st.error(f"Could not load history: {e}")

def create_new_chat():
    st.session_state.current_session_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.rerun()

# --- PAGES ---
def login_page():
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.title("🔮 Nexus AI")
        st.markdown("##### The Multi-Model Intelligence Hub")
        
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
        
        with tab1:
            with st.form("login"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("Access System", use_container_width=True):
                    try:
                        r = requests.post(f"{BASE_URL}/token", data={"username": u, "password": p}, timeout=5)
                        if r.status_code == 200:
                            st.session_state.token = r.json()["access_token"]
                            st.session_state.user = u
                            st.success("Verified. Redirecting...")
                            time.sleep(0.5)
                            # RERUN MUST BE OUTSIDE OR HANDLED CAREFULLY
                            st.rerun() 
                        else:
                            st.error("Invalid Credentials")
                    except ConnectionError:
                        st.error("❌ Cannot connect to Backend. Is 'main.py' running?")
                    except Timeout:
                        st.error("❌ Server took too long to respond.")
                    except Exception as e:
                        # This catches weird errors, but we ignore the Rerun exception if it slips through
                        if "script" not in str(e).lower(): 
                            st.error(f"Error: {e}")

        with tab2:
            with st.form("reg"):
                u = st.text_input("New Username")
                p = st.text_input("New Password", type="password")
                if st.form_submit_button("Initialize Account", use_container_width=True):
                    try:
                        r = requests.post(f"{BASE_URL}/register", json={"username": u, "password": p}, timeout=5)
                        if r.status_code == 200: st.success("Identity Created. Proceed to Login.")
                        else: st.error(r.text)
                    except Exception as e: st.error(f"Error: {e}")

def chat_page():
    with st.sidebar:
        st.title("🔮 Nexus")
        st.caption(f"User: **{st.session_state.user}**")
        if st.button("➕ Start New Session", use_container_width=True): create_new_chat()
        
        st.divider()
        st.subheader("🗂️ Archives")
        try:
            # Timeout added here too
            sessions = requests.get(f"{BASE_URL}/sessions", headers=get_headers(), timeout=5).json()
            if not sessions: st.info("No archives.")
            for s in sessions:
                title = s['title'][:25] + "..." if len(s['title']) > 25 else s['title']
                if s['id'] == st.session_state.current_session_id: st.markdown(f"**👉 {title}**")
                else: 
                    if st.button(f"🗨️ {title}", key=s['id']): load_session_messages(s['id'])
        except: st.warning("Archives offline")
        
        st.divider()
        if st.button("🔌 Disconnect", use_container_width=True):
            st.session_state.token = None
            st.rerun()

    if not st.session_state.messages:
        st.title("System Ready.")
        st.markdown(f"Welcome back, **{st.session_state.user}**.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🐍 Python Code", use_container_width=True):
                st.session_state.messages.append({"role": "user", "type": "text", "content": "Write a Python script for a calculator."})
                st.rerun()
        with col2:
            if st.button("🎨 Cyberpunk City", use_container_width=True):
                st.session_state.messages.append({"role": "user", "type": "text", "content": "Generate a cyberpunk city with neon lights."})
                st.rerun()

    for msg in st.session_state.messages:
        avatar = "👤" if msg["role"] == "user" else "🔮"
        with st.chat_message(msg["role"], avatar=avatar):
            if msg["type"] == "text": st.markdown(msg["content"])
            else: st.image(msg["content"], width=500)

    if prompt := st.chat_input("Input command..."):
        st.session_state.messages.append({"role": "user", "type": "text", "content": prompt})
        with st.chat_message("user", avatar="👤"): st.markdown(prompt)

        with st.chat_message("assistant", avatar="🔮"):
            with st.spinner("Processing..."):
                try:
                    # INCREASED TIMEOUT TO 60 SECONDS FOR IMAGES
                    r = requests.post(
                        f"{BASE_URL}/chat", 
                        json={"prompt": prompt, "session_id": st.session_state.current_session_id}, 
                        headers=get_headers(),
                        timeout=60 
                    )
                    if r.status_code == 200:
                        out = r.json()["output"]
                        if "image_url" in out:
                            st.image(out["image_url"], width=500)
                            st.session_state.messages.append({"role": "assistant", "type": "image", "content": out["image_url"]})
                        else:
                            st.markdown(out["text"])
                            st.session_state.messages.append({"role": "assistant", "type": "text", "content": out["text"]})
                    elif r.status_code == 401:
                        st.session_state.token = None
                        st.rerun()
                    else: st.error(f"Error: {r.text}")
                except Timeout:
                    st.error("The model took too long to respond. Try again.")
                except Exception as e: 
                    st.error(f"Error: {e}")

if st.session_state.token: chat_page()
else: login_page()