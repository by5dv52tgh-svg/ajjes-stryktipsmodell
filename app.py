import math
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Ajjes Stryktipsmodell", page_icon="⚽", layout="wide")
SIGNS = ["1", "X", "2"]

def norm3(v):
    a = np.maximum(np.asarray(v, dtype=float), 1e-9)
    return a / a.sum()

def get_clean_float(val):
    if pd.isna(val):
        return 0.0
    s = str(val).replace(",", ".").replace("%", "").strip()
    try:
        return float(s)
    except:
        return 0.0

def parse_ajjes_spec_file(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python', header=None)
        final_data = []
        match_count = 1
        for idx, row in df.iterrows():
            if len(row) < 9: continue
            row_str = "".join([str(x) for x in row]).lower()
            if "hemma" in row_str or "borta" in row_str or "streck" in row_str or "odds" in row_str: continue
            h_name = str(row.iloc[1]).strip()
            a_name = str(row.iloc[2]).strip()
            if h_name == "" or h_name.lower() == "nan": continue
            s1 = get_clean_float(row.iloc[3])
            sx = get_clean_float(row.iloc[4])
            s2 = get_clean_float(row.iloc[5])
            o1 = get_clean_float(row.iloc[6])
            ox = get_clean_float(row.iloc[7])
            o2 = get_clean_float(row.iloc[8])
            stats_1 = get_clean_float(row.iloc[9]) if len(row) > 9 else 0.0
            stats_x = get_clean_float(row.iloc[10]) if len(row) > 10 else 0.0
            stats_2 = get_clean_float(row.iloc[11]) if len(row) > 11 else 0.0
            form_text = str(row.iloc[12]).strip() if len(row) > 12 else ""
            injury_text = str(row.iloc[13]).strip() if len(row) > 13 else ""
            motivation_text = str(row.iloc[14]).strip() if len(row) > 14 else ""
            h2h_text = str(row.iloc[15]).strip() if len(row) > 15 else ""
            final_data.append({
                "Match": match_count, "Hemmalag": h_name, "Bortalag": a_name,
                "Odds 1": o1, "Odds X": ox, "Odds 2": o2, "Streck 1": s1, "Streck X": sx, "Streck 2": s2,
                "xG 1 (%)": stats_1, "xG X (%)": stats_x, "xG 2 (%)": stats_2,
                "Form-Info": form_text, "Skador/Avstängningar": injury_text, "Motivation/Tabell": motivation_text, "H2H-Historik": h2h_text
            })
            match_count += 1
            if match_count > 13: break
        return pd.DataFrame(final_data)
    except Exception as e:
        st.error(f"Kunde inte tolka Numbers-filen. Fel: {e}")
        return pd.DataFrame()
def advanced_system_builder(probs, crowd_probs, budget):
    sel = [[int(np.argmax(p))] for p in probs]
    rows = 1
    candidates = []
    for i, (p, cp) in enumerate(zip(probs, crowd_probs)):
        for s in range(3):
            if s != sel[i]:
                value_streck = p[s] - cp[s]
                priority_score = p[s] + max(0, value_streck) * 2.0
                candidates.append((priority_score, i, s))
    candidates.sort(key=lambda x: x[0], reverse=True)
    for _, i, s in candidates:
        if s in sel[i]: continue
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
        return "Helgarderas rent operativt. Matchen har hög osäkerhetsfaktor och strecken innehåller ett matematiskt övervärde."
    elif len(final_signs) == 2:
        val_signs = [SIGNS[x] for x in range(3) if (p[x] - cp[x]) > -0.03 and SIGNS[x] in final_signs]
        return f"Halvgarderas {final_signs} eftersom spelmotorn identifierar starkt spelvärde i tecken {val_signs}."
    else:
        if best_sign_idx == crowd_fav_idx and not over_streckad:
            return f"Spikas. Stabil och sund favorit där strecken stämmer väl överens med vinstchansen."
        return f"Klockren värdespik på {best_sign}! Sannolikheten försvarar att lämna tecknet ensamt utifrån din budget."

st.title("⚽ Ajjes Spelmotor & Analysverktyg")
st.caption("Strikt matematisk systemoptimering baserad på spelvärde, riskkontroll och budgettäckning.")

with st.sidebar:
    st.header("1. Konfiguration")
    budget = st.selectbox("Välj ditt Systems budget (kr / rader)", [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048], index=8)
    st.markdown("---")
    st.subheader("Modellens Startvikter")
    w_odds = st.slider("Odds/Marknad (%)", 0, 100, 50)
    w_crowd = st.slider("Streck/Värde (%)", 0, 100, 20)
    w_xg = st.slider("xG/Statistik (%)", 0, 100, 10)
    w_form = st.slider("Form + Hemma (%)", 0, 100, 20)
    total_w = w_odds + w_crowd + w_xg + w_form
    if total_w == 0: total_w = 1
    weights = {"odds": w_odds/total_w, "crowd": w_crowd/total_w, "xg": w_xg/total_w, "form": w_form/total_w}

t1, t2, t3 = st.tabs(["📊 Veckans Spelmotor", "⏳ Walk-Forward Backtest", "📑 Regler & Paragrafer"])

with t1:
    up = st.file_uploader("Ladda upp veckans Stryktipsomgång (CSV exporterad från Numbers)", type=["csv"], key="today")
    if not up:
        st.info("👋 Välkommen Ajje! Exportera din tabell från Numbers till en CSV-fil och ladda upp den här.")
    else:
        df = parse_ajjes_spec_file(up)
        if not df.empty:
            st.markdown("### 1. Insamlad & Verifierad Data")
            edited_df = st.data_editor(df, use_container_width=True, hide_index=True)
            probs, crowd_probs, out_table, status_logs = [], [], [], []
            for idx, r in edited_df.iterrows():
                raw_mp = [1/r["Odds 1"], 1/r["Odds X"], 1/r["Odds 2"]] if r["Odds 1"]>0 else [0.33,0.33,0.33]
                market_p = norm3(raw_mp)
                crowd_p = norm3([r["Streck 1"], r["Streck X"], r["Streck 2"]]) if r["Streck 1"]>0 else [0.33,0.33,0.33]
                xg_p = norm3([r["xG 1 (%)"], r["xG X (%)"], r["xG 2 (%)"]]) if r["xG 1 (%)"]>0 else market_p
                
                p = norm3(market_p * weights["odds"] + crowd_p * weights["crowd"] + xg_p * weights["xg"])
                probs.append(p)
                crowd_probs.append(crowd_p)
                
                v1, vX, v2 = p[0]-crowd_p[0], p[1]-crowd_p[1], p[2]-crowd_p[2]
                out_table.append({
                    "Match": f"{r['Match']}. {r['Hemmalag']} – {r['Bortalag']}",
                    "Ajjes Sannolikhet (1/X/2)": f"{round(p[0]*100)}% / {round(p[1]*100)}% / {round(p[2]*100)}%",
                    "Folkets Streck (1/X/2)": f"{round(crowd_p[0]*100)}% / {round(crowd_p[1]*100)}% / {round(crowd_p[2]*100)}%",
                    "Matematiskt Värde (1/X/2)": f"{'+' if v1>0 else ''}{round(v1*100,1)}% / {'+' if vX>0 else ''}{round(vX*100,1)}% / {'+' if v2>0 else ''}{round(v2*100,1)}%"
                })
            st.markdown("---")
            st.subheader("2. Ajjes Sannolikhets- & Värdeöversikt")
            st.dataframe(pd.DataFrame(out_table), use_container_width=True, hide_index=True)
            sel, rows = advanced_system_builder(probs, crowd_probs, budget)
            st.markdown("---")
            st.subheader("3. AJJES SLUTSYSTEM")
            a, b, c = st.columns(3)
            a.metric("Målbudget", f"{budget} kr")
            b.metric("Beräknade rader", f"{rows} st")
            c.metric("Faktisk kostnad", f"{rows} kr")
            detail = []
            for i, s in enumerate(sel):
                row_data = edited_df.iloc[i]
                signs_text = "".join(SIGNS[x] for x in s)
                detail.append({
                    "Match": f"{i+1}. {row_data['Hemmalag']} – {row_data['Bortalag']}",
                    "Systemtecken": signs_text,
                    "Typ": "Spik" if len(s)==1 else ("Halvgardering" if len(s)==2 else "Helgardering"),
                    "Matematisk Motivering": generate_decision_text(probs[i], crowd_probs[i], signs_text)
                })
            st.dataframe(pd.DataFrame(detail), use_container_width=True, hide_index=True)

with t2: st.subheader("Walk-forward Backtesting")
with t3: st.subheader("Modellens Paragrafer & Regler")
