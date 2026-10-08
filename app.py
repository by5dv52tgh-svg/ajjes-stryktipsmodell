import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Ajjes Spelmotor & AI-Analys", page_icon="⚽", layout="wide")
SIGNS = ["1", "X", "2"]

def norm3(v):
    a = np.maximum(np.asarray(v, dtype=float), 1e-9)
    return a / a.sum()

st.title("⚽ Ajjes Spelmotor & AI-Analys")
st.caption("Operativt verktyg för rent spelvärde, budgetkontroll och avancerad AI-generering.")

# Standardlista för veckans matcher som användaren snabbt kan skriva över
default_teams = [
    ("Manchester United", "Tottenham"), ("Chelsea", "Bournemouth"), ("Aston Villa", "Wolves"),
    ("Sunderland", "Leeds"), ("Ipswich", "Fulham"), ("Blackburn", "QPR"),
    ("Bolton", "Wrexham"), ("Derby", "Norwich"), ("Middlesbrough", "Millwall"),
    ("Preston", "Watford"), ("Sheffield Utd", "Luton"), ("Portsmouth", "Sheffield Wed"),
    ("Coventry", "Hull")
]

with st.sidebar:
    st.header("1. Konfiguration")
    budget = st.selectbox("Systembudget (kr / rader)", [16, 32, 64, 128, 256, 486, 512, 1024, 2048], index=4)
st.subheader("1. Fyll i Matcher, Odds & Streck")
matches_data = []

# Skapar 13 enkla och rena rader på skärmen
for i in range(13):
    col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 2, 1, 1, 1, 1, 1])
    def_h, def_a = default_teams[i]
    
    with col1: h = st.text_input(f"Hemmalag {i+1}", def_h, key=f"h_{i}")
    with col2: a = st.text_input(f"Bortalag {i+1}", def_a, key=f"a_{i}")
    with col3: o1 = st.number_input("Odds 1", min_value=1.0, max_value=50.0, value=2.1, step=0.05, key=f"o1_{i}")
    with col4: ox = st.number_input("Odds X", min_value=1.0, max_value=50.0, value=3.3, step=0.05, key=f"ox_{i}")
    with col5: o2 = st.number_input("Odds 2", min_value=1.0, max_value=50.0, value=3.1, step=0.05, key=f"o2_{i}")
    with col6: s1 = st.number_input("Streck 1 (%)", min_value=0, max_value=100, value=45, key=f"s1_{i}")
    with col7: s2 = st.number_input("Streck 2 (%)", min_value=0, max_value=100, value=25, key=f"s2_{i}")
    sx = max(0, 100 - s1 - s2)
    
    matches_data.append({"match": i+1, "home": h, "away": a, "o1": o1, "ox": ox, "o2": o2, "s1": s1, "sx": sx, "s2": s2})

st.markdown("---")
st.subheader("2. Matematisk Analysöversikt (Rent Spelvärde)")

val_table = []
ai_payload = []

for m in matches_data:
    raw_mp = [1/m["o1"], 1/m["ox"], 1/m["o2"]]
    mp = norm3(raw_mp) # Sannolikhet utifrån odds
    cp = norm3([m["s1"], m["sx"], m["s2"]]) # Sannolikhet utifrån streck
    
    v1 = mp[0] - cp[0]
    vX = mp[1] - cp[1]
    v2 = mp[2] - cp[2]
    
    val_table.append({
        "Match": f"{m['match']}. {m['home']} - {m['away']}",
        "Sannolikhet (1/X/2)": f"{round(mp[0]*100)}% / {round(mp[1]*100)}% / {round(mp[2]*100)}%",
        "Folkets Streck": f"{m['s1']}% / {m['sx']}% / {m['s2']}%",
        "Rent Spelvärde (1/X/2)": f"{'+' if v1>0 else ''}{round(v1*100,1)}% / {'+' if vX>0 else ''}{round(vX*100,1)}% / {'+' if v2>0 else ''}{round(v2*100,1)}%"
    })
    
    ai_payload.append(f"Match {m['match']}: {m['home']} - {m['away']} | Odds: {m['o1']}-{m['ox']}-{m['o2']} | Streck: {m['s1']}%-{m['sx']}%-{m['s2']}% | Rent Spelvärde: {round(v1*100)}% / {round(vX*100)}% / {round(v2*100)}%")

st.dataframe(pd.DataFrame(val_table), use_container_width=True, hide_index=True)

st.markdown("---")
st.subheader("3. Skicka Data till AI-Motorn för Djupanalys")
st.write("Eftersom oddsen och spelvärdet nu är framräknat, klicka på knappen nedan för att generera den färdiga analysinstruktionen till AI:n.")

prompt_text = f"""Kör Ajjes Stryktipsmodell för följande omgång. Budget: {budget} kr.
Hämta dagsaktuell och verifierad information om xG, statistik, lagform, skador/avstängningar samt tabellmotivation för dessa 13 matcher.
Väg samman all data matematiskt med de odds, streck och spelvärden som anges här nedanför. Bygg det mest optimala systemet (spikar/garderingar) inom budgeten och ge en tydlig motivering till varje val:

""" + "\n".join(ai_payload)

st.text_area("Kopiera denna text och klistra in i AI-chatten:", prompt_text, height=250)
