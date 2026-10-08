import math
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Ajjes Stryktipsmodell", page_icon="⚽", layout="wide")
SIGNS = ["1", "X", "2"]

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
    except (ValueError, TypeError):
        return np.ones(3) / 3

def get_crowd_probabilities(r):
    try:
        v = [float(r.get("stake_1", 0)), float(r.get("stake_x", 0)), float(r.get("stake_2", 0))]
        return norm3(v) if sum(v) > 0 else np.ones(3) / 3
    except (ValueError, TypeError):
        return np.ones(3) / 3

def get_factor_probabilities(r, prefix, fallback_p):
    try:
        v = [r.get(f"{prefix}_1"), r.get(f"{prefix}_x"), r.get(f"{prefix}_2")]
        if all(pd.isna(x) or str(x).strip() == "" for x in v):
            return fallback_p, False
        v_clean = [float(x) if pd.notna(x) and str(x).strip() != "" else 33.333 for x in v]
        return norm3(v_clean), True
    except (ValueError, TypeError):
        return fallback_p, False

def calculate_ajje_probabilities(r, w):
    market_p = get_implicit_probabilities(r.get("odds_1"), r.get("odds_x"), r.get("odds_2"))
    crowd_p = get_crowd_probabilities(r)
    stats_p, has_stats = get_factor_probabilities(r, "stats", market_p)
    form_p, has_form = get_factor_probabilities(r, "form", market_p)
    injury_p, has_injury = get_factor_probabilities(r, "injury", market_p)
    motivation_p, has_motivation = get_factor_probabilities(r, "motivation", market_p)
    
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
    sel = [[int(np.argmax(p))] for p in probs]
    rows = 1
    candidates = []
    for i, (p, cp) in enumerate(zip(probs, crowd_probs)):
        for s in range(3):
            if s != sel[i][0]:
                value_streck = p[s] - cp[s]
                priority_score = p[s] + max(0, value_streck) * 1.5
                candidates.append((priority_score, i, s))
                
    candidates.sort(key=lambda x: x[0], reverse=True)
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
            return f"Garderade bort folkets favorit ({SIGNS[crowd_fav_idx]}) eftersom den är kraftigt överstreckad. Värdet ligger på {final_signs}."
        return f"Halvgardering {final_signs}. Modellen identifierar fint spelvärde jämfört med folkets streck."
    else:
        if best_sign_idx == crowd_fav_idx and not over_streckad:
            return f"Spikas. Stabil favorit där folkets streck ({round(cp[best_sign_idx]*100)}%) ligger i linje med modellen."
        return f"Spik. Modellen bedömer att tecken {best_sign} har tillräckligt hög vinstchans ({round(p[best_sign_idx]*100)}%) för att lämnas ensam."

# --- GRÄNSSNITT ---

st.title("⚽ Ajjes Stryktipsmodell")
st.caption("Ett professionellt, datadrivet analysverktyg — sannolikheter, värde och systemoptimering.")

weights_default = {"odds": 30, "crowd": 15, "stats": 20, "form": 10, "injury": 8, "motivation": 7}

with st.sidebar:
    st.header("Modellkonfiguration")
    vals = {k: st.slider(k.capitalize(), 0, 100, v) for k, v in weights_default.items()}
    total_w = sum(vals.values()) or 1
    w = {k: v / total_w for k, v in vals.items()}
    st.markdown("---")
    budget = st.selectbox("Systembudget (kr)", [64, 128, 256, 512, 1024], index=2)
    st.info("💡 H2H är bortkopplad (0% vikt) enligt modellens regler.")

t1, t2, t3 = st.tabs(["📊 Aktuell omgång", "⏳ Historiskt backtest", "📑 Dataformat & Regler"])

with t1:
    st.subheader("1. Inmatning av omgången")
    up = st.file_uploader("Ladda upp Stryktipsomgång", type=["csv", "xlsx"], key="today")
    df = pd.read_csv(up) if up and up.name.endswith('.csv') else (pd.read_excel(up) if up else pd.DataFrame())
    
    if df.empty:
        st.info("👋 Välkommen! Ladda upp din matchfil i fältet ovan för att starta analysen.")
    else:
        if len(df) < 13:
            st.error(f"Fel: Filen innehåller bara {len(df)} matcher. Kräver exakt 13.")
        else:
            edited_df = st.data_editor(df.head(13), use_container_width=True, hide_index=True)
            
            if st.button("🔎 KÖR AJJES MODELL", type="primary", use_container_width=True):
                probs, market_probs, crowd_probs, out_table, status_list = [], [], [], [], []
                
                for idx, r in edited_df.iterrows():
                    p, mp, cp, status = calculate_ajje_probabilities(r, w)
                    probs.append(p); market_probs.append(mp); crowd_probs.append(cp); status_list.append(status)
                    v_streck = p - cp
                    v_odds = p - mp
                    
                    out_table.append({
                        "Match": f"{idx+1}. {r.get('home','Lag A')} – {r.get('away','Lag B')}",
                        "Ajje 1": f"{round(p[0]*100,1)}%", "Ajje X": f"{round(p[1]*100,1)}%", "Ajje 2": f"{round(p[2]*100,1)}%",
                        "Folk 1": f"{round(cp[0]*100)}%", "Folk X": f"{round(cp[1]*100)}%", "Folk 2": f"{round(cp[2]*100)}%",
                        "Värde Streck (1/X/2)": f"{round(v_streck[0]*100,1)} / {round(v_streck[1]*100,1)} / {round(v_streck[2]*100,1)}",
                        "Värde Odds (1/X/2)": f"{round(v_odds[0]*100,1)} / {round(v_odds[1]*100,1)} / {round(v_odds[2]*100,1)}"
                    })
                st.session_state.update(probs=probs, crowd_probs=crowd_probs, df=edited_df.head(13).copy(), result_df=pd.DataFrame(out_table), status_list=status_list)

        if "result_df" in st.session_state:
            st.markdown("---")
            st.subheader("2. Analysöversikt & Datastatus")
            status_data = [{"Match": f"{i+1}. {st.session_state.df.iloc[i].get('home')} - {st.session_state.df.iloc[i].get('away')}", "Odds": "✓" if s["odds"] else "⚠ Fallback", "Streck": "✓" if s["crowd"] else "⚠ Saknas", "Statistik": "✓" if s["stats"] else "⚠ Saknas", "Form": "✓" if s["form"] else "⚠ Saknas"} for i, s in enumerate(st.session_state.status_list)]
            with st.expander("👁️ Visa datatillgänglighet per match"):
                st.dataframe(pd.DataFrame(status_data), use_container_width=True, hide_index=True)
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
                signs_text = "".join(SIGNS[x] for x in s)
                detail.append({
                    "Match": f"{i+1}. {r.get('home')} – {r.get('away')}", "Systemtecken": signs_text,
                    "Typ": "Spik" if len(s)==1 else ("Halvgardering" if len(s)==2 else "Helgardering"),
                    "Modellens Motivering": generate_decision_text(st.session_state.probs[i], st.session_state.crowd_probs[i], signs_text)
                })
            st.dataframe(pd.DataFrame(detail), use_container_width=True, hide_index=True)

with t2:
    st.subheader("Historiskt backtest")
    h = st.file_uploader("Ladda upp historisk data (CSV)", type="csv", key="hist")
    if h:
        hist = pd.read_csv(h)
        if not all(x in hist.columns for x in ["odds_1", "odds_x", "odds_2", "stake_1", "stake_x", "stake_2", "result"]):
            st.error("Filen saknar nödvändiga kolumner.")
        else:
            pred, actual = [], []
            for _, r in hist.iterrows():
                p, _, _, _ = calculate_ajje_probabilities(r, w)
                pred.append(SIGNS[int(np.argmax(p))]); actual.append(str(r["result"]).strip())
            o = hist[[c for c in ["round", "home", "away", "result"] if c in hist.columns]].copy()
            o["Modellens val"] = pred; o["Rätt?"] = o["Modellens val"] == o["result"]
