import math
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Ajjes Stryktipsmodell", page_icon="⚽", layout="wide")
SIGNS = ["1", "X", "2"]

# --- GLOBAL LAGDATABAS FÖR EXAKT MATCHNING ---
ALL_TEAMS = [
    "Manchester United", "Manchester City", "Sheffield United", "Sheffield Wednesday",
    "Aston Villa", "Newcastle United", "West Ham United", "Brighton & Hove Albion", 
    "Brighton", "Tottenham Hotspur", "Tottenham", "Nottingham Forest", "Nottingham",
    "Crystal Palace", "Wolverhampton Wanderers", "Wolverhampton", "Wolves",
    "West Bromwich Albion", "West Brom", "Blackburn Rovers", "Blackburn",
    "Cardiff City", "Cardiff", "Stoke City", "Stoke", "Derby County", "Derby",
    "Preston North End", "Preston", "Queens Park Rangers", "QPR",
    "Sheffield Utd", "Sheffield Wed", "Leeds United", "Leeds",
    "Arsenal", "Chelsea", "Liverpool", "Bournemouth", "Brentford", "Sunderland",
    "Ipswich Town", "Ipswich", "Fulham", "Bolton Wanderers", "Bolton", "Wrexham",
    "Middlesbrough", "Millwall", "Watford", "Burnley", "Huddersfield Town", "Huddersfield",
    "Lincoln City", "Lincoln", "Everton", "Leicester City", "Leicester", "Southampton",
    "Luton Town", "Luton", "Portsmouth", "Coventry City", "Coventry", "Hull City", "Hull",
    "Norwich City", "Norwich", "Plymouth Argyle", "Plymouth", "Bristol City", "Swansea City", "Swansea",
    "Oxford United", "Oxford"
]

# --- BERÄKNINGSMOTOR & VERKTYG ---

def norm3(v):
    a = np.maximum(np.asarray(v, dtype=float), 1e-9)
    return a / a.sum()

def get_implicit_probabilities(odds_1, odds_x, odds_2):
    try:
        o1, ox, o2 = float(odds_1), float(odds_x), float(odds_2)
        if o1 <= 1 or ox <= 1 or o2 <= 1:
            return np.ones(3) / 3
        return norm3([1 / o1, 1 / ox, 1 / o2])
    except:
        return np.ones(3) / 3

def get_crowd_probabilities(s1, sx, s2):
    try:
        v = [float(s1 or 0), float(sx or 0), float(s2 or 0)]
        return norm3(v) if sum(v) > 0 else np.ones(3) / 3
    except:
        return np.ones(3) / 3

def clean_and_split_teams(combined_text):
    """Lagar trasiga ord och separerar hemma/borta via lagdatabasen"""
    # Laga kända fil- och text-delningsfel från rådata
    t = combined_text.replace("brentf ord", "Brentford").replace("Brentf ord", "Brentford")
    t = t.replace("brighto n", "Brighton").replace("Brighto n", "Brighton")
    t = t.replace("bournemout h", "Bournemouth").replace("Bournemout h", "Bournemouth")
    t = t.replace("bournmout h", "Bournemouth").replace("Bournmout h", "Bournemouth")
    t = t.replace("shef field", "Sheffield").replace("Shef field", "Sheffield")
    t = t.replace("wolv erhampton", "Wolverhampton").replace("Wolv erhampton", "Wolverhampton")
    
    t_clean = t.strip()
    sorted_teams = sorted(ALL_TEAMS, key=len, reverse=True)
    
    home_team = "Lag A"
    away_team = "Lag B"
    
    # Hitta hemmalaget först baserat på databasen
    for team in sorted_teams:
        if t_clean.lower().startswith(team.lower()):
            home_team = team
            remaining = t_clean[len(team):].strip()
            
            # Städa bort eventuella skiljetecken i mitten
            if remaining.lower().startswith("vs "): remaining = remaining[3:].strip()
            if remaining.lower().startswith("- "): remaining = remaining[2:].strip()
            
            away_team = remaining
            # Snygga till bortalagets namn om det finns i databasen
            for t2 in sorted_teams:
                if remaining.lower() == t2.lower() or remaining.lower().startswith(t2.lower()):
                    away_team = t2
                    break
            return home_team, away_team
            
    return home_team, away_team

def parse_ajjes_robust_file(uploaded_file):
    """Läser filen rad för rad och extraherar all data helt felfritt"""
    try:
        lines = uploaded_file.getvalue().decode("utf-8").splitlines()
        final_data = []
        
        match_idx = 1
        for line in lines:
            if not line.strip():
                continue
            
            # Gör om alla semikolon till mellanslag och splitta till bitar
            cleaned_line = line.replace(";", " ")
            parts = [p.strip() for p in cleaned_line.split() if p.strip()]
            
            if len(parts) < 2 or "home" in parts or "Match" in parts:
                continue
                
            # Separera siffror och ord
            numbers = []
            words = []
            for p in parts:
                p_clean = p.replace("%", "")
                if p_clean.replace('.', '', 1).isdigit() or p_clean.isdigit():
                    numbers.append(float(p_clean))
                else:
                    words.append(p)
            
            # Om första siffran är matchnumret (1-13), plocka bort den så den inte stör oddsen
            if numbers and int(numbers[0]) == match_idx:
                numbers = numbers[1:]
                
            # Sätt ihop alla ord till en enda textsträng för att köra specialsepareringen
            combined_words = " ".join(words)
            home_team, away_team = clean_and_split_teams(combined_words)
            
            # Hämta odds och streck baserat på sifferlistan
            o1 = numbers[0] if len(numbers) > 0 else 2.10
            ox = numbers[1] if len(numbers) > 1 else 3.30
            o2 = numbers[2] if len(numbers) > 2 else 3.10
            s1 = numbers[3] if len(numbers) > 3 else 45.0
            sx = numbers[4] if len(numbers) > 4 else 30.0
            s2 = numbers[5] if len(numbers) > 5 else 25.0
            
            final_data.append({
                "Match": match_idx, "Hemmalag": home_team, "Bortalag": away_team,
                "Odds 1": o1, "Odds X": ox, "Odds 2": o2,
                "Streck 1": s1, "Streck X": sx, "Streck 2": s2
            })
            match_idx += 1
            if match_idx > 13:
                break
                
        while len(final_data) < 13:
            final_data.append({
                "Match": len(final_data)+1, "Hemmalag": "Väntar på data...", "Bortalag": "",
                "Odds 1": 2.5, "Odds X": 3.2, "Odds 2": 2.8, "Streck 1": 33.3, "Streck X": 33.3, "Streck 2": 33.3
            })
        return pd.DataFrame(final_data)
    except Exception as e:
        return pd.DataFrame([{"Match": i+1, "Hemmalag": f"Fel: {e}", "Bortalag": "", "Odds 1": 2.5, "Odds X": 3.2, "Odds 2": 2.8, "Streck 1": 33.3, "Streck X": 33.3, "Streck 2": 33.3} for i in range(13)])

# --- SYSTEMBYGGARE ---
def advanced_system_builder(probs, crowd_probs, budget):
    sel = [[int(np.argmax(p))] for p in probs]
    rows = 1
    candidates = []
    for i, (p, cp) in enumerate(zip(probs, crowd_probs)):
        for s in range(3):
            if s != sel[i]:
                value_streck = p[s] - cp[s]
                priority_score = p[s] + max(0, value_streck) * 1.5
                candidates.append((priority_score, i, s))
                
    candidates.sort(key=lambda x: x, reverse=True)
    for _, i, s in candidates:
        if s in sel[i]:
            continue
        current_options = len(sel[i])
        proposed_rows = (rows // current_options) * (current_options + 1)
        if proposed_rows <= budget:
            sel[i].append(s)
            rows = proposed_rows
    return [sorted(x) for x in sel], rows

def generate_decision_text(p, cp, final_signs):
    best_sign_idx = int(np.argmax(p))
    best_sign = SIGNS[best_sign_idx]
    crowd_fav_idx = int(np.argmax(cp))
    over_streckad = (cp[crowd_fav_idx] - p[crowd_fav_idx]) > 0.10
    
    if len(final_signs) == 3:
        return "Helgarderas. Matchen är mycket oviss eller så innehåller underdog-tecknen ett fint spelvärde."
    elif len(final_signs) == 2:
        if over_streckad and SIGNS[crowd_fav_idx] not in final_signs:
            return f"Garderade bort folkets favorit ({SIGNS[crowd_fav_idx]}) eftersom den är kraftigt överstreckad."
        return f"Halvgardering {final_signs}. Modellen identifierar fint spelvärde jämfört med folkets streck."
    else:
        if best_sign_idx == crowd_fav_idx and not over_streckad:
            return f"Spikas. Stabil favorit där folkets streck ligger i linje med modellen."
        return f"Spik. Modellen bedömer att tecken {best_sign} har tillräckligt hög vinstchans."

# --- GRÄNSSNITT ---
st.title("⚽ Ajjes Stryktipsmodell")
st.caption("Ett professionellt, datadrivet analysverktyg — sannolikheter, värde och systemoptimering.")

with st.sidebar:
    st.header("Modellkonfiguration")
    odds_w = st.slider("Odds / Marknad vikt", 0, 100, 50)
    crowd_w = st.slider("Folkets streck vikt", 0, 100, 50)
    w = {"odds": odds_w / 100, "crowd": crowd_w / 100}
    st.markdown("---")
    budget = st.selectbox("Systembudget (kr)", [64, 128, 256, 512, 1024], index=2)

t1, t2, t3 = st.tabs(["📊 Aktuell omgång", "⏳ Historiskt backtest", "📑 Dataformat & Regler"])

with t1:
    st.subheader("1. Inmatning av omgången")
    up = st.file_uploader("Ladda upp veckans Stryktipsomgång (CSV eller XLSX)", type=["csv", "xlsx"], key="today")
    
    if not up:
        st.info("👋 Välkommen! Ladda upp din matchfil (.csv) ovan för att starta veckans analys.")
    else:
        df = parse_ajjes_robust_file(up)
        
        st.markdown("### Förhandsgranskning / Redigera data")
        edited_df = st.data_editor(df, use_container_width=True, hide_index=True)
        
        if st.button("🔎 KÖR AJJES MODELL", type="primary", use_container_width=True):
            probs, crowd_probs, out_table, clean_matches = [], [], [], []
            
            for idx, r in edited_df.iterrows():
                h_name = r["Hemmalag"]
                a_name = r["Bortalag"]
                o1, ox, o2 = r["Odds 1"], r["Odds X"], r["Odds 2"]
                s1, sx, s2 = r["Streck 1"], r["Streck X"], r["Streck 2"]
                
                mp = get_implicit_probabilities(o1, ox, o2)
