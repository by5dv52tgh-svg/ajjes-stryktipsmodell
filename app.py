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
    """Omvandlar odds till sanna marknadssannolikheter utan bookmaker-marginal"""
    try:
        o1, ox, o2 = float(odds_1), float(odds_x), float(odds_2)
        if o1 <= 1 or ox <= 1 or o2 <= 1:
            return np.ones(3) / 3
        return norm3([1 / o1, 1 / ox, 1 / o2])
    except (ValueError, TypeError):
        return np.ones(3) / 3

def get_crowd_probabilities(stake_1, stake_x, stake_2):
    """Hämtar och normaliserar folkets streck"""
    try:
        v = [float(stake_1 or 0), float(stake_x or 0), float(stake_2 or 0)]
        return norm3(v) if sum(v) > 0 else np.ones(3) / 3
    except (ValueError, TypeError):
        return np.ones(3) / 3

def calculate_ajje_probabilities(r, w, col_mapping):
    """Hämtar data baserat på index-mappning för att klara Unnamed-kolumner"""
    # Hämta värden baserat på positioner i CSV-filen
    h_val = r.iloc[col_mapping["home"]] if col_mapping["home"] < len(r) else "Lag A"
    a_val = r.iloc[col_mapping["away"]] if col_mapping["away"] < len(r) else "Lag B"
    
    o1 = r.iloc[col_mapping["odds_1"]] if col_mapping["odds_1"] < len(r) else 2.5
    ox = r.iloc[col_mapping["odds_x"]] if col_mapping["odds_x"] < len(r) else 3.2
    o2 = r.iloc[col_mapping["odds_2"]] if col_mapping["odds_2"] < len(r) else 2.8
    
    s1 = r.iloc[col_mapping["stake_1"]] if col_mapping["stake_1"] < len(r) else 33.3
    sx = r.iloc[col_mapping["stake_x"]] if col_mapping["stake_x"] < len(r) else 33.3
    s2 = r.iloc[col_mapping["stake_2"]] if col_mapping["stake_2"] < len(r) else 33.3

    market_p = get_implicit_probabilities(o1, ox, o2)
    crowd_p = get_crowd_probabilities(s1, sx, s2)
    
    # Sammanvägning av odds och folkets streck (50/50 som startläge)
    p = market_p * w.get("odds", 0.50) + crowd_p * w.get("crowd", 0.50)
    
    status_flags = {
        "odds": True if pd.notna(o1) else False,
        "crowd": True if pd.notna(s1) else False,
        "stats": False, "form": False, "injury": False, "motivation": False
    }
    return norm3(p), market_p, crowd_p, status_flags, str(h_val), str(a_val), s1, sx, s2

# --- SYSTEMBYGGARE (OPTIMERING) ---

def advanced_system_builder(probs, crowd_probs, budget):
    """Köper garderingar baserat på högsta förväntade värde (EV) upp till vald budget"""
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
    """Skapar en automatisk textförklaring till modellens val i varje match"""
    best_sign_idx = int(np.argmax(p))
    best_sign = SIGNS[best_sign_idx]
    crowd_fav_idx = int(np.argmax(cp))
    over_streckad = (cp[crowd_fav_idx] - p[crowd_fav_idx]) > 0.10
    
    if len(final_signs) == 3:
        return "Helgarderas. Matchen är mycket oviss eller så innehåller underdog-tecknen ett fint spelvärde."
    elif len(final_signs) == 2:
        if over_streckad and SIGNS[crowd_fav_idx] not in final_signs:
            return f"Garderade bort folkets favorit ({SIGNS[crowd_fav_idx]}) eftersom den är kraftigt överstreckad. Värdet ligger på {final_signs}."
        return f"Halvgardering {final_signs}. Modellen identifierar fint spelvärde jämfört med folkets streck."
    else:
        if best_sign_idx == crowd_fav_idx and not over_streckad:
            return f"Spikas. Stabil favorit där folkets streck ({round(cp[best_sign_idx]*100)}%) ligger i linje med modellen."
        return f"Spik. Modellen bedömer att tecken {best_sign} har tillräckligt hög vinstchans ({round(p[best_sign_idx]*100)}%) för att lämnas ensam."

# --- GRÄNSSNITT ---

st.title("⚽ Ajjes Stryktipsmodell")
st.caption("Ett professionellt, datadrivet analysverktyg — sannolikheter, värde och systemoptimering.")

weights_default = {"odds": 50, "crowd": 50, "stats": 0, "form": 0, "injury": 0, "motivation": 0}

with st.sidebar:
    st.header("Modellkonfiguration")
    st.subheader("Justera vikter (%)")
    vals = {k: st.slider(k.capitalize(), 0, 100, v) for k, v in weights_default.items()}
    total_w = sum(vals.values()) or 1
    w = {k: v / total_w for k, v in vals.items()}
    st.markdown("---")
    budget = st.selectbox("Systembudget (kr)", [64, 128, 256, 512, 1024], index=2)

t1, t2, t3 = st.tabs(["📊 Aktuell omgång", "⏳ Historiskt backtest", "📑 Dataformat & Regler"])

with t1:
    st.subheader("1. Inmatning av omgången")
    up = st.file_uploader("Ladda upp veckans Stryktipsomgång (CSV eller XLSX)", type=["csv", "xlsx"], key="today")
    
    if not up:
        st.info("👋 Välkommen! Ladda upp din matchfil (.csv) ovan för att starta veckans analys.")
    else:
        try:
            df = pd.read_csv(up, sep=None, engine='python') if up.name.endswith('.csv') else pd.read_excel(up)
            
            if len(df) < 13:
                st.error(f"Fel: Filen innehåller bara {len(df)} matcher. Stryktipset kräver exakt 13 matcher.")
            else:
                st.markdown("### Förhandsgranskning / Redigera data")
                edited_df = st.data_editor(df.head(13), use_container_width=True, hide_index=True)
                
                # Dynamisk mappning baserat på din specifika filstruktur (Kolumn-ordning)
                col_mapping = {"home": 1, "away": 2, "odds_1": 3, "odds_x": 4, "odds_2": 5, "stake_1": 6, "stake_x": 7, "stake_2": 8}
                
                if len(edited_df.columns) >= 3:
                    col_mapping["home"] = 1 if len(edited_df.columns) > 1 else 0
                    col_mapping["away"] = 2 if len(edited_df.columns) > 2 else 1
                
                if st.button("🔎 KÖR AJJES MODELL", type="primary", use_container_width=True):
                    probs, market_probs, crowd_probs, out_table, clean_matches = [], [], [], [], []
                    
                    for idx, r in edited_df.iterrows():
                        p, mp, cp, status, h_name, a_name, s1, sx, s2 = calculate_ajje_probabilities(r, w, col_mapping)
                        
                        probs.append(p)
                        crowd_probs.append(cp)
                        market_probs.append(mp)
                        
                        v_streck = p - cp
                        v_odds = p - mp
                        
                        clean_matches.append({"home": h_name, "away": a_name})
                        
                        out_table.append({
                            "Match": f"{idx+1}. {h_name} – {a_name}",
                            "Ajje 1": f"{round(p[0]*100,1)}%", "Ajje X": f"{round(p[1]*100,1)}%", "Ajje 2": f"{round(p[2]*100,1)}%",
                            "Folk 1": f"{round(s1)}%" if isinstance(s1,(int,float)) else "33%", 
                            "Folk X": f"{round(sx)}%" if isinstance(sx,(int,float)) else "33%", 
                            "Folk 2": f"{round(s2)}%" if isinstance(s2,(int,float)) else "33%",
                            "Värde Streck": f"{round(v_streck[0]*100,1)} / {round(v_streck[1]*100,1)} / {round(v_streck[2]*100,1)}"
                        })
                    
                    st.session_state.update(probs=probs, crowd_probs=crowd_probs, clean_matches=clean_matches, result_df=pd.DataFrame(out_table))
        except Exception as e:
            st.error(f"Ett fel uppstod vid inläsning: {e}")

    if "result_df" in st.session_state and up:
        st.markdown("---")
        st.subheader("2. Analysöversikt")
        st.dataframe(st.session_state.result_df, use_container_width=True, hide_index=True)
        
        sel, rows = advanced_system_builder(st.session_state.probs, st.session_state.crowd_probs, budget)
        st.markdown("---")
        st.subheader("3. Optimerat Systembygge")
        a, b, c = st.columns(3)
        a.metric("Målbudget", f"{budget} kr"); b.metric("Beräknade rader", f"{rows} st"); c.metric("Slutlig kostnad", f"{rows} kr")
        st.info(f"**Systemrad:** {' – '.join(''.join(SIGNS[s] for s in x) for x in sel)}")
        
        detail = []
        for i, s in enumerate(sel):
            cm = st.session_state.clean_matches[i]
            signs_text = "".join(SIGNS[x] for x in s)
            detail.append({
                "Match": f"{i+1}. {cm['home']} – {cm['away']}", "Systemtecken": signs_text,
                "Typ": "Spik" if len(s)==1 else ("Halvgardering" if len(s)==2 else "Helgardering"),
                "Modellens Motivering": generate_decision_text(st.session_state.probs[i], st.session_state.crowd_probs[i], signs_text)
            })
        st.dataframe(pd.DataFrame(detail), use_container_width=True, hide_index=True)

with t2:
    st.subheader("Historiskt backtest")

with t3:
    st.subheader("Instruktioner")
