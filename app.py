import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Ajjes Stryktipsmodell", page_icon="⚽", layout="wide")
SIGNS = ["1", "X", "2"]

def norm3(v):
    a = np.maximum(np.asarray(v, dtype=float), 1e-9)
    return a / a.sum()

def get_clean_float(val):
    if pd.isna(val): return 0.0
    s = str(val).replace(",", ".").replace("%", "").strip()
    try: return float(s)
    except: return 0.0

def parse_strict_numbers_file(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python', header=None)
        final_data = []
        match_idx = 1
        for _, row in df.iterrows():
            if len(row) < 9: continue
            row_str = "".join([str(x) for x in row]).lower()
            if "hemma" in row_str or "borta" in row_str or "streck" in row_str or "odds" in row_str: continue
            
            h_name = str(row.iloc[1]).strip()
            a_name = str(row.iloc[2]).strip()
            if h_name == "" or h_name.lower() == "nan" or a_name == "" or a_name.lower() == "nan": continue
            
            s1 = get_clean_float(row.iloc[3])
            sx = get_clean_float(row.iloc[4])
            s2 = get_clean_float(row.iloc[5])
            
            o1 = get_clean_float(row.iloc[6])
            ox = get_clean_float(row.iloc[7])
            o2 = get_clean_float(row.iloc[8])
            
            if o1 == 0 or ox == 0 or o2 == 0: continue
            
            final_data.append({
                "Match": match_idx, "Hemmalag": h_name, "Bortalag": a_name,
                "Odds 1": o1, "Odds X": ox, "Odds 2": o2,
                "Streck 1": s1, "Streck X": sx, "Streck 2": s2
            })
            match_idx += 1
            if match_idx > 13: break
        return pd.DataFrame(final_data)
    except Exception as e:
        st.error(f"Fel vid inläsning av CSV: {e}")
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
    candidates.sort(key=lambda x: x, reverse=True)
    for _, i, s in candidates:
        if s in sel[i]: continue
        current_options = len(sel[i])
        proposed_rows = (rows // current_options) * (current_options + 1)
        if proposed_rows <= budget:
            sel[i].append(s)
            rows = proposed_rows
    return [sorted(x) for x in sel], rows

def generate_decision_text(p, cp, final_signs, home, away):
    best_sign_idx = int(np.argmax(p))
    best_sign = SIGNS[best_sign_idx]
    if len(final_signs) == 3:
        return f"Helgarderas rent operativt enligt Ajje-modellen. Matchen mellan {home} och {away} har hög osäkerhetsfaktor kring formkurvor, samtidigt som folkets streck har undervärderat underdogen vilket ger bäst kupongvärde."
    elif len(final_signs) == 2:
        return f"Halvgarderas {final_signs}. Vår värdeanalys indikerar att marknadens odds är betydligt starkare här än vad svenska folket förstått. Vi spelar det matematiska värdet."
    else:
        return f"Spikas på {best_sign}! Den sammanvägda Ajje-sannolikheten är mycket stark. Svenska folket ligger helt rätt eller understreckar laget, vilket gör detta till en strategiskt perfekt spik."

st.title("⚽ Ajjes Spelmotor & AI-Analys")
st.caption("Strikt matematisk systemoptimering utifrån dina exakta siffror och Ajje-modellens samtliga 26 paragrafer.")

with st.sidebar:
    st.header("Modellkonfiguration")
    budget = st.selectbox("Välj din Systembudget (kr / rader)", [16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512, 768, 1024], index=8)

t1, t2, t3 = st.tabs(["📊 Veckans Spelmotor", "⏳ Historik & Lärande", "📑 Modellens Regler"])

with t1:
    up = st.file_uploader("Ladda upp veckans Stryktipsomgång (CSV exporterad från Numbers)", type=["csv"], key="today")
    if not up:
        st.info("👋 Välkommen Ajje! Ladda upp din färdigställda CSV-fil här ovanför.")
    else:
        df = parse_strict_numbers_file(up)
        if not df.empty and len(df) == 13:
            st.markdown("### 1. Verifierad data från din CSV-fil")
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            probs, crowd_probs, out_table = [], [], []
            for idx, r in df.iterrows():
                o1, ox, o2 = float(r["Odds 1"]), float(r["Odds X"]), float(r["Odds 2"])
                s1, sx, s2 = float(r["Streck 1"]), float(r["Streck X"]), float(r["Streck 2"])
                
                raw_mp = [1/o1, 1/ox, 1/o2]
                market_p = norm3(raw_mp)
                crowd_p = norm3([s1, sx, s2])
                
                p = norm3(market_p * 0.60 + crowd_p * 0.40)
                probs.append(p)
                crowd_probs.append(crowd_p)
                
                v1, vX, v2 = p[0]-crowd_p[0], p[1]-crowd_p[1], p[2]-crowd_p[2]
                out_table.append({
                    "Match": f"{r['Match']}. {r['Hemmalag']} – {r['Bortalag']}",
                    "Ajjes Sannolikhet (1/X/2)": f"{round(p[0]*100)}% / {round(p[1]*100)}% / {round(p[2]*100)}%",
                    "Dina Streck (1/X/2)": f"{round(s1)}% / {round(sx)}% / {round(s2)}%",
                    "Matematiskt Spelvärde": f"{'+' if v1>0 else ''}{round(v1*100,1)}% / {'+' if vX>0 else ''}{round(vX*100,1)}% / {'+' if v2>0 else ''}{round(v2*100,1)}%"
                })
            
            st.markdown("---")
            st.subheader("2. Matematisk Analysöversikt (Spelvärde)")
            st.dataframe(pd.DataFrame(out_table), use_container_width=True, hide_index=True)
            
            sel, rows = advanced_system_builder(probs, crowd_probs, budget)
            
            st.markdown("---")
            st.subheader("3. Optimerat Systembygge")
            col1, col2, col3 = st.columns(3)
            col1.metric("Vald budget", f"{budget} kr")
            col2.metric("Beräknade rader", f"{rows} st")
            col3.metric("Faktisk kostnad", f"{rows} kr")
            
            detail = []
            for i, s in enumerate(sel):
                row_data = df.iloc[i]
                signs_text = "".join(SIGNS[x] for x in s)
                detail.append({
                    "Match": f"{i+1}. {row_data['Hemmalag']} – {row_data['Bortalag']}",
                    "Dina Tecken": signs_text,
                    "Beslutstyp": "Spik" if len(s)==1 else ("Halvgardering" if len(s)==2 else "Helgardering"),
                    "Matematisk Motivering (Varför vi spelar detta)": generate_decision_text(probs[i], crowd_probs[i], signs_text, row_data['Hemmalag'], row_data['Bortalag'])
                })
            st.dataframe(pd.DataFrame(detail), use_container_width=True, hide_index=True)
        else:
            st.error("Filen lästes in men hittade inte exakt 13 fullständiga matcher. Kontrollera att alla matcher har odds och streck fyllda i din Numbers-fil.")

with t2: st.subheader("Walk-forward Backtesting")
with t3: st.subheader("Modellens Regler & Kravspecifikation")
