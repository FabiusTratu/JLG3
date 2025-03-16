import streamlit as st
import random
import threading
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import requests

# ============ FASTAPI BACKEND ============

app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

challenges = [
    {"text": "Mach 10 Liegestütze", "reward": 20},
    {"text": "Springe 3x hoch", "reward": 10},
    {"text": "Singe laut im Park", "reward": 15},
]
targets = ["🏞️ Spielplatz", "🛒 Supermarkt", "🚏 Bushaltestelle"]
players = {}

@app.post("/register/{username}")
def register_player(username: str):
    if username in players:
        raise HTTPException(status_code=400, detail="Spieler existiert bereits!")

    players[username] = {
        "coins": 100, "freeze_until": 0, 
        "target": random.choice(targets), "current_challenge": None
    }
    
    return {"message": "Registrierung erfolgreich!", "coins": 100, "target": players[username]["target"]}

@app.post("/spend_money/{username}/{amount}")
def spend_money(username: str, amount: int):
    if username not in players:
        raise HTTPException(status_code=400, detail="Spieler nicht gefunden!")
    if players[username]["coins"] < amount:
        raise HTTPException(status_code=400, detail="Nicht genug Coins!")
    players[username]["coins"] -= amount
    return {"new_coins": players[username]["coins"]}

@app.get("/get_coins/{username}")
def get_coins(username: str):
    if username not in players:
        raise HTTPException(status_code=400, detail="Spieler nicht gefunden!")
    return {"coins": players[username]["coins"]}

@app.post("/reached_target/{username}")
def reached_target(username: str):
    if username not in players:
        raise HTTPException(status_code=400, detail="Spieler nicht gefunden!")
    players[username]["target"] = random.choice(targets)
    return {"new_target": players[username]["target"]}

@app.post("/draw_challenge/{username}")
def draw_challenge(username: str):
    if username not in players:
        raise HTTPException(status_code=400, detail="Spieler nicht gefunden!")
    if time.time() < players[username]["freeze_until"]:
        raise HTTPException(status_code=400, detail="Du bist noch eingefroren!")
    challenge = random.choice(challenges)
    players[username]["current_challenge"] = challenge
    return challenge

@app.post("/accept_challenge/{username}")
def accept_challenge(username: str):
    if username not in players or not players[username]["current_challenge"]:
        raise HTTPException(status_code=400, detail="Keine aktive Challenge!")
    reward = players[username]["current_challenge"]["reward"]
    players[username]["coins"] += reward
    players[username]["current_challenge"] = None
    return {"new_coins": players[username]["coins"]}

@app.post("/reject_challenge/{username}")
def reject_challenge(username: str):
    if username not in players:
        raise HTTPException(status_code=400, detail="Spieler nicht gefunden!")
    players[username]["freeze_until"] = time.time() + 900  # 15 Minuten
    players[username]["current_challenge"] = None
    return {"message": "Eingefroren für 15 Minuten!"}

@app.post("/caught/{username}")
def caught_player(username: str):
    if username not in players:
        raise HTTPException(status_code=400, detail="Spieler nicht gefunden!")
    players[username]["target"] = random.choice(targets)
    return {"new_target": players[username]["target"]}

def start_fastapi():
    uvicorn.run(app, host="127.0.0.1", port=8000)

threading.Thread(target=start_fastapi, daemon=True).start()

# ============ STREAMLIT FRONTEND ============

st.title("🏃 Outdoor-Fangspiel")

API_BASE_URL = "http://127.0.0.1:8000"

if "game_started" not in st.session_state:
    st.session_state["game_started"] = False

if not st.session_state["game_started"]:
    username = st.text_input("Gib deinen Namen ein:")
    
    if username and st.button("🚀 Spiel starten"):
        response = requests.post(f"{API_BASE_URL}/register/{username}")
        if response.status_code == 200:
            data = response.json()
            st.session_state.update({
                "username": username,
                "coins": data["coins"],
                "target": data["target"],
                "current_challenge": None,
                "game_started": True
            })
        else:
            st.error(response.json()["detail"])
else:
    st.write(f"👤 **Spieler:** {st.session_state['username']}")
    st.write(f"💰 **Kontostand:** {st.session_state['coins']} Coins")
    
    st.markdown(f"## 🎯 **Dein Ziel:**")
    st.markdown(f"<h2 style='color: red;'>{st.session_state['target']}</h2>", unsafe_allow_html=True)
    
    if st.button("✅ Ziel erreicht!"):
        response = requests.post(f"{API_BASE_URL}/reached_target/{st.session_state['username']}")
        if response.status_code == 200:
            st.session_state["target"] = response.json()["new_target"]
            st.success(f"Neues Ziel: {st.session_state['target']}")
    
    if st.button("😱 Ich wurde gefangen!"):
        response = requests.post(f"{API_BASE_URL}/caught/{st.session_state['username']}")
        if response.status_code == 200:
            st.session_state["target"] = response.json()["new_target"]
            st.success(f"Neues Ziel: {st.session_state['target']}")
    
    if st.button("🎲 Challenge ziehen"):
        response = requests.post(f"{API_BASE_URL}/draw_challenge/{st.session_state['username']}")
        if response.status_code == 200:
            st.session_state["current_challenge"] = response.json()
        else:
            st.error(response.json()["detail"])

    if st.session_state.get("current_challenge"):
        st.write(f"📜 **Challenge:** {st.session_state['current_challenge']['text']}")
        st.write(f"🏆 **Belohnung:** {st.session_state['current_challenge']['reward']} Coins")
        
        if st.button("✔ Challenge annehmen"):
            response = requests.post(f"{API_BASE_URL}/accept_challenge/{st.session_state['username']}")
            st.session_state["coins"] = response.json()["new_coins"]
        if st.button("❌ Challenge ablehnen"):
            requests.post(f"{API_BASE_URL}/reject_challenge/{st.session_state['username']}")
            st.warning("Eingefroren für 15 Minuten!")
    
    amount = st.number_input("💸 Betrag eingeben:", min_value=1, step=1)
    if st.button("💰 Geld ausgeben"):
        requests.post(f"{API_BASE_URL}/spend_money/{st.session_state['username']}/{amount}")
        
