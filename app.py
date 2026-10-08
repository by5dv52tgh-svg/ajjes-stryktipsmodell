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

def get_crowd_probabilities(r):
    """Hämtar och normaliserar folkets streck"""
    try:
        v = [float(r.get("stake_1", 0)), float(r.get("stake_x", 0)), float(r.get("stake_2", 0))]
        return norm3(v) if sum(v) > 0 else np.ones(3) / 3
    except (ValueError, TypeError):
        return np.ones(3) / 3

def get_factor_probabilities(r, prefix, fallback_p):
    """Hämtar statistikkomponenter (form, xG etc.). Använder odds som fallback om tomt."""
    try:
        v = [r.get(f"{prefix}_1"), r.get(f"{prefix}_x"), r.get(f"{prefix}_2")]
        if all(pd.isna(x) or str(x).strip() == "" for x in v):
            return fallback_p, False
        v_clean = [float(x) if pd.notna(x) and str(x).strip() != "" else 33.333 for x in v]
        return norm3(v_clean), True
    except (ValueError, TypeError):
        return fallback_p, False

def calculate_ajje_probabilities(r, w):
    """Väger samman alla tillgängliga faktorer till Ajjes slutgiltiga sannolikhet"""
    market_p = get_implicit_probabilities(r.get("odds_1"), r.get("odds_x"), r.get("odds_2"))
    crowd_p = get_crowd_probabilities(r)
    stats_p, has_stats = get_factor_probabilities(r, "stats", market_p)
    form_p, has_form = get_factor_probabilities(r, "form", market_p)
    injury_p, has_injury = get_factor_probabilities(r, "injury", market_p)
    motivation_p, has_motivation = get_factor_probabilities(r, "motivation", market_p)
    
    # Sammanvägning (Linear Opinion Pool) där summan alltid blir exakt 100%
    p = (
        market_p * w.get("odds", 0.30) +
        crowd_p * w.get("crowd", 0.15) +
        stats_p * w.get("stats", 0.20) +
        form_p * w.get("form", 0.10) +
        injury_p * w.get("injury", 0.08) +
        motivation_p * w.get("motivation", 0.07)
    )
    
    status_flags = {
        "odds": True if pd.notna(r.get("odds_1")) and str(r.get("odds_1")).strip() != "" else False,
        "crowd": True if pd.notna(r.get("stake_1")) and str(r.get("stake_1")).strip() != "" else False,
        "stats": has_stats, "form": has_form, "injury": has_injury, "motivation": has_motivation
    }
    return norm3(p), market_p, crowd_p, status_flags

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

# --- GRÄNSSNITT (STREAMLIT) ---

st.title("⚽ Ajjes Stryktipsmodell")
st.caption("Ett professionellt, datadrivet analysverktyg — sannolikheter, värde och systemoptimering.")

# Standardvikter enligt din kravspecifikation
weights_default = {"odds": 30, "crowd": 15, "stats": 20, "form": 10, "injury": 8, "motivation": 7}

with st.sidebar:
    st.header("Modellkonfiguration")
    st.subheader("Justera vikter (%)")
    vals = {k: st.slider(k.capitalize(), 0, 100, v) for k, v in weights_default.items()}
    total_w = sum(vals.values()) or 1
    w = {k: v / total_w for k, v in vals.items()}
    st.markdown("---")
    budget = st.selectbox("Systembudget (kr)", [64, 128, 256, 512, 1024], index=2)
    st.info("💡 H2H (Inbördes möten) är helt bortkopplad (0% vikt) enligt modellens regler.")

t1, t2, t3 = st.tabs(["📊 Aktuell omgång", "⏳ Historiskt backtest", "📑 Dataformat & Regler"])

# --- TAB 1: AKTUELL OMGÅNG ---
with t1:
    st.subheader("1. Inmatning av omgången")
    up = st.file_uploader("Ladda upp veckans Stryktipsomgång (CSV eller XLSX)", type=["csv", "xlsx"], key="today")
    
    if not up:
        st.info("👋 Välkommen! Ladda upp din matchfil (.csv) ovan för att starta veckans analys.")
    else:
        # FIXEN: sep=None och engine='python' gör att Pandas automatiskt kan läsa filer med semikolon (;)
        try:
            if up.name.endswith('.csv'):
                df = pd.read_csv(up, sep=None, engine='python')
            else:
                df = pd.read_excel(up)
                
            # Om filen har ett tomt index eller konstiga semikolontecken i kolumnnamnen, städa upp dem
            df.columns = [c.strip().replace(';', '') for c in df.columns]
            
            if len(df) < 13:
                st.error(f"Fel: Filen innehåller bara {len(df)} matcher. Stryktipset kräver exakt 13 matcher.")
            else:
                st.markdown("### Förhandsgranskning / Redigera data")
                edited_df = st.data_editor(df.head(13), use_container_width=True, hide_index=True)
                
                if st.button("🔎 KÖR AJJES MODELL", type="primary", use_container_width=True):
                    probs, market_probs, crowd_probs, out_table, status_list = [], [], [], [], []
                    
                    for idx, r in edited_df.iterrows():
                        p, mp, cp, status = calculate_ajje_probabilities(r, w)
                        probs.append(p); market_probs.append(mp); crowd_probs.append(cp); status_list.append(status)
                        v_streck = p - cp
                        v_odds = p - mp
                        
                        # Försök hämta lagnamn, hantera om kolumnen råkar ha ett semikolon i sig
                        h_name = r.get('home', r.get(';home', 'Lag A'))
                        a_name = r.get('away', r.get(';away', 'Lag B'))
                        
                        out_table.append({
                            "Match": f"{idx+1}. {h_name} – {a_name}",
                            "Ajje 1": f"{round(p[0]*100,1)}%", "Ajje X": f"{round(p[1]*100,1)}%", "Ajje 2": f"{round(p[2]*100,1)}%",
                            "Folk 1": f"{round(cp[0]*100)}%", "Folk X": f"{round(cp[1]*100)}%", "Folk 2": f"{round(cp[2]*100)}%",
                            "Värde Streck (1/X/2)": f"{round(v_streck[0]*100,1)} / {round(v_streck[1]*100,1)} / {round(v_streck[2]*100,1)}",
                            "Värde Odds (1/X/2)": f"{round(v_odds[0]*100,1)} / {round(v_odds[1]*100,1)} / {round(v_odds[2]*100,1)}"
                        })
                    st.session_state.update(probs=probs, crowd_probs=crowd_probs, df=edited_df.head(13).copy(), result_df=pd.DataFrame(out_table), status_list=status_list)
        except Exception as e:
            st.error(f"Ett fel uppstod vid inläsning av filen. Säkerställ att kolumnnamnen är korrekta. Felmeddelande: {e}")

    if "result_df" in st.session_state and up:
        st.markdown("---")
        st.subheader("2. Analysöversikt & Datastatus")
        st.dataframe(st.session_state.result_df, use_container_width=True, hide_index=True)
        
        sel, rows = advanced_system_builder(st.session_state.probs, st.session_state.crowd_probs, budget)
        st.markdown("---")
        st.subheader("3. Optimerat Systembygge")
        a, b, c = st.columns(3)
        a.metric("Målbudget", f"{budget} kr"); b.metric("Beräknade rader", f"{rows} st"); c.metric("Slutlig kostnad", f"{rows} kr")
        st.info(f"**Systemrad:** {' – '.join(''.join(SIGNS[s] for s in x) for x in sel)}")
        
        detail = []
        for i, s in enumerate(sel):
            r = st.session_state.df.iloc[i]
            h_name = r.get('home', r.get(';home', 'Lag A'))
            a_name = r.get('away', r.get(';away', 'Lag B'))
            signs_text = "".join(SIGNS[x] for x in s)
            detail.append({
