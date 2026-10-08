import math
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Ajjes Stryktipsmodell", page_icon="⚽", layout="wide")
SIGNS = ["1", "X", "2"]

# --- BERÄKNINGSMOTOR & VERKTYG ---

def norm3(v):
    """Säkerställer att summan av tre värden alltid blir exakt 1.0 (100%)"""
    a = np.maximum(np.asarray(v, dtype=float), 1e-9)
    return a / a.sum()

def get_implicit_probabilities(odds_1, odds_x, odds_2):
    """Omvandlar odds till sannolikheter och plockar bort bookmakerns marginal"""
    try:
        o1 = float(odds_1)
        ox = float(odds_x)
        o2 = float(odds_2)
        if o1 <= 1 or ox <= 1 or o2 <= 1:
            return np.ones(3) / 3
        
        # Implicita sannolikheter med marginal
        raw_p = [1 / o1, 1 / ox, 1 / o2]
        # Normalisera för att få sanna sannolikheter (ta bort marginalen)
        return norm3(raw_p)
    except (ValueError, TypeError):
        return np.ones(3) / 3

def get_crowd_probabilities(r):
    """Hämtar och normaliserar folkets streck"""
    try:
        v = [float(r.get("stake_1", 0)), float(r.get("stake_x", 0)), float(r.get("stake_2", 0))]
        if sum(v) > 0:
            return norm3(v)
        return np.ones(3) / 3
    except (ValueError, TypeError):
        return np.ones(3) / 3

def get_factor_probabilities(r, prefix, fallback_p):
    """Hämtar statistikkomponenter. Om data saknas används odds-sannolikheten som fallback"""
    try:
        v = [r.get(f"{prefix}_1"), r.get(f"{prefix}_x"), r.get(f"{prefix}_2")]
        if all(pd.isna(x) or x == "" for x in v):
            return fallback_p, False # Data saknas, flagga som falsk
        
        v_clean = [float(x) if pd.notna(x) and str(x).strip() != "" else 33.333 for x in v]
        return norm3(v_clean), True
    except (ValueError, TypeError):
        return fallback_p, False

def calculate_ajje_probabilities(r, w):
    """Väger samman alla tillgängliga faktorer till Ajjes slutgiltiga sannolikhet"""
    # 1. Marknadens odds är vår fundamentala baseline
    market_p = get_implicit_probabilities(r.get("odds_1"), r.get("odds_x"), r.get("odds_2"))
    crowd_p = get_crowd_probabilities(r)
    
    # 2. Hämta övriga faktorer (med statusflagga om data fanns)
    stats_p, has_stats = get_factor_probabilities(r, "stats", market_p)
    form_p, has_form = get_factor_probabilities(r, "form", market_p)
    injury_p, has_injury = get_factor_probabilities(r, "injury", market_p)
    motivation_p, has_motivation = get_factor_probabilities(r, "motivation", market_p)
    
    # H2H är hårdkodat till 0% i enlighet med kravspecifikationen
    h2h_p = market_p 
    
    # 3. Linjär sammanvägning (Linear Opinion Pool) för stabil 100%-summa
    p = (
        market_p * w.get("odds", 0.35) +
        crowd_p * w.get("crowd", 0.15) +
        stats_p * w.get("stats", 0.20) +
        form_p * w.get("form", 0.10) +
        injury_p * w.get("injury", 0.08) +
        motivation_p * w.get("motivation", 0.07) +
        h2h_p * 0.0 # 0% vikt på H2H
    )
    
    status_flags = {
        "odds": True if r.get("odds_1") and pd.notna(r.get("odds_1")) else False,
        "crowd": True if r.get("stake_1") and pd.notna(r.get("stake_1")) else False,
        "stats": has_stats,
        "form": has_form,
        "injury": has_injury,
        "motivation": has_motivation
    }
    
    return norm3(p), market_p, crowd_p, status_flags

# --- SYSTEMBYGGARE (OPTIMERING) ---

def advanced_system_builder(probs, crowd_probs, market_probs, budget):
    """
    Bygger systemet genom att prioritera garderingar baserat på förväntat värde (EV) 
    och osäkerhet, utan att spräcka vald radbudget.
    """
    # Starta med att spika högsta sannolikheten i varje match
    sel = [[int(np.argmax(p))] for p in probs]
    rows = 1
    
    # Skapa en lista med alla potentiella garderingar (tecken vi kan lägga till)
    candidates = []
    for i, (p, cp, mp) in enumerate(zip(probs, crowd_probs, market_probs)):
        for s in range(3):
            if s != sel[i][0]: # Om tecknet inte redan är valt som spik
                # Beräkna hur attraktivt detta tecken är att gardera med
                # Högre sannolikhet + positivt värde mot folket = Högre prioritet
                value_streck = p[s] - cp[s]
                priority_score = p[s] + max(0, value_streck) * 1.5
                candidates.append((priority_score, i, s))
                
    # Sortera kandidaterna så att de bästa garderingarna hamnar först
    candidates.sort(key=lambda x: x[0], reverse=True)
    
    # Köp garderingar så länge budgeten tillåter
    for _, i, s in candidates:
        if s in sel[i]:
            continue
            
        # Beräkna vad den nya radkostnaden skulle bli om vi lägger till detta tecken
        current_options = len(sel[i])
        new_options = current_options + 1
        proposed_rows = (rows // current_options) * new_options
        
        if proposed_rows <= budget:
            sel[i].append(s)
            rows = proposed_rows
            
    return [sorted(x) for x in sel], rows

def generate_decision_text(match_name, p, cp, mp, final_signs):
    """Genererar en automatisk förklaring till modellens beslut"""
    best_sign_idx = int(np.argmax(p))
    best_sign = SIGNS[best_sign_idx]
    
    # Kolla efter överstreckning hos favoriten enligt folket
    crowd_fav_idx = int(np.argmax(cp))
    over_streckad = (cp[crowd_fav_idx] - p[crowd_fav_idx]) > 0.10
    
    if len(final_signs) == 3:
        return "Helgarderas. Matchen är mycket oviss eller så innehåller underdog-tecknen ett extremt spelvärde som måste täckas."
    elif len(final_signs) == 2:
        undervalued = [SIGNS[i] for i in range(3) if (p[i] - cp[i]) > 0.02 and SIGNS[i] in final_signs]
        if over_streckad and SIGNS[crowd_fav_idx] not in final_signs:
            return f"Garderade bort folkets favorit ({SIGNS[crowd_fav_idx]}) eftersom den är kraftigt överstreckad. Värdet ligger på {final_signs}."
        return f"Halvgardering {final_signs}. Modellen identifierar fint spelvärde i tecken {undervalued} jämfört med folkets streck."
    else:
        if best_sign_idx == crowd_fav_idx and not over_streckad:
            return f"Spikas. Stabil favorit där folkets streck ({round(cp[best_sign_idx]*100)}%) ligger i linje med modellens sannolikhet ({round(p[best_sign_idx]*100)}%)."
        return f"Spik-etta/tvåa. Modellen bedömer att tecken {best_sign} har tillräckligt hög vinstchans ({round(p[best_sign_idx]*100)}%) för att lämnas ensam."

# --- GRÄNSSNITT (STREAMLIT) ---

st.title("⚽ Ajjes Stryktipsmodell")
st.caption("Ett professionellt, datadrivet analysverktyg — sannolikheter, värde, systemoptimering och strikt backtesting.")

# Standardvikter enligt din specifikation
weights_default = {
    "odds": 30,
    "crowd": 15,
    "stats": 20,
    "form": 10,
    "injury": 8,
    "motivation": 7
}

with st.sidebar:
    st.header("Modellkonfiguration")
    st.subheader("Justera vikter (%)")
    
    vals = {}
    vals["odds"] = st.slider("Odds / Marknad", 0, 100, weights_default["odds"])
    vals["crowd"] = st.slider("Folkets streck", 0, 100, weights_default["crowd"])
    vals["stats"] = st.slider("xG / Grundstatistik", 0, 100, weights_default["stats"])
    vals["form"] = st.slider("Aktuell form", 0, 100, weights_default["form"])
    vals["injury"] = st.slider("Trupp / Skador / Avstängningar", 0, 100, weights_default["injury"])
    vals["motivation"] = st.slider("Tabell / Motivation", 0, 100, weights_default["motivation"])
    
    # Normalisera vikterna så de blir 1.0 totalt
    total_w = sum(vals.values()) or 1
    w = {k: v / total_w for k, v in vals.items()}
    
    st.markdown("---")
    budget = st.selectbox("Systembudget (max rader / kr)", [64, 128, 256, 512, 1024], index=2)
    st.info("💡 H2H (Inbördes möten) är helt bortkopplad (0% vikt) enligt modellens regler.")

t1, t2, t3 = st.tabs(["📊 Aktuell omgång", "⏳ Historiskt backtest", "📑 Dataformat & Regler"])

# --- TAB 1: DAGENS OMGÅNG ---
with t1:
    st.subheader("1. Inmatning av omgången")
    up = st.file_uploader("Ladda upp Stryktipsomgång (CSV eller Excel)", type=["csv", "xlsx"], key="today")
    
    if up:
        if up.name.endswith('.csv'):
            df = pd.read_csv(up)
        else:
            df = pd.read_excel(up)
    else:
        df = pd.DataFrame()
        
    if df.empty:
        st.info("👋 Välkommen! Ladda upp din matchfil i fältet ovan för att starta analysen.")
    else:
        # Kontrollera och validera rader
        if len(df) < 13:
            st.error(f"Fel: Filen innehåller bara {len(df)} matcher. Stryktipset kräver exakt 13 matcher.")
        else:
            st.markdown("### Förhandsgranskning / Redigera data")
            st.caption("Du kan dubbelklicka på cellerna i tabellen för att ändra odds eller streck direkt innan du kör modellen.")
            edited_df = st.data_editor(df.head(13), use_container_width=True, hide_index=True)
            
            if st.button("🔎 KÖR AJJES MODELL", type="primary", use_container_width=True):
                probs = []
                market_probs = []
                crowd_probs = []
                out_table = []
                status_list = []
                
                for idx, r in edited_df.iterrows():
                    # Beräkna
                    p, mp, cp, status = calculate_ajje_probabilities(r, w)
                    
                    probs.append(p)
                    market_probs.append(mp)
                    crowd_probs.append(cp)
                    status_list.append(status)
                    
                    # Beräkna värden (Skillnaden i procentenheter)
                    v_streck = p - cp
                    v_odds = p - mp
                    
                    match_name = f"{r.get('home','Lag A')} – {r.get('away','Lag B')}"
                    
                    out_table.append({
                        "Match": f"{idx+1}. {match_name}",
