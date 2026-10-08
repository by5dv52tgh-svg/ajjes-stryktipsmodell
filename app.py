import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Ajjes Spelmotor", page_icon="⚽", layout="wide")
SIGNS = ["1", "X", "2"]

def norm3(v):
    a = np.maximum(np.asarray(v, dtype=float), 1e-9)
    return a / a.sum()

def get_clean_float(val):
    if pd.isna(val): return 0.0
    try: return float(str(val).replace(",", ".").replace("%", "").strip())
    except: return 0.0

with st.sidebar:
    st.header("Modellkonfiguration")
    budget = st.selectbox("Välj din Systembudget (kr)", [1, 2, 4, 8, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 486, 512, 729, 1024, 1458, 2048], index=12)

st.title("⚽ Ajjes Spelmotor & Live AI")
up = st.file_uploader("Ladda upp veckans Stryktipsomgång (CSV från Numbers)", type=["csv"])

if up:
    try:
        df = pd.read_csv(up, sep=None, engine='python', header=None)
        final_data = []
        match_idx = 1
        for _, r in df.iterrows():
            if len(r) < 9: continue
            if "hemma" in "".join([str(x) for x in r]).lower(): continue
            h, a = str(r.iloc[1]).strip(), str(r.iloc[2]).strip()
            if h == "" or h.lower() == "nan": continue
            s1, sx, s2 = get_clean_float(r.iloc[3]), get_clean_float(r.iloc[4]), get_clean_float(r.iloc[5])
            o1, ox, o2 = get_clean_float(r.iloc[6]), get_clean_float(r.iloc[7]), get_clean_float(r.iloc[8])
            final_data.append({"Match": match_idx, "Hemmalag": h, "Bortalag": a, "O1": o1, "OX": ox, "O2": o2, "S1": s1, "SX": sx, "S2": s2})
            match_idx += 1
            if match_idx > 13: break
            
        f_df = pd.DataFrame(final_data)
        st.markdown("### 1. Verifierad data från din CSV-fil")
        st.dataframe(f_df, use_container_width=True, hide_index=True)
        
        probs, crowd_probs, out_table, match_strings = [], [], [], []
        for idx, r in f_df.iterrows():
            mp = norm3([1/r["O1"] if r["O1"]>0 else 3, 1/r["OX"] if r["OX"]>0 else 3, 1/r["O2"] if r["O2"]>0 else 3])
            cp = norm3([r["S1"], r["SX"], r["S2"]])
            p = norm3(mp * 0.60 + cp * 0.40)
            probs.append(p)
            crowd_probs.append(cp)
            v = p - cp
            
            p_pct = np.round(p * 100, 1)
            s_pct = [round(r["S1"]), round(r["SX"]), round(r["S2"])]
            v_pct = np.round(v * 100, 1)
            
            out_table.append({
                "Match": f"{r['Match']}. {r['Hemmalag']} – {r['Bortalag']}",
                "Ajjes Sannolikhet (1/X/2)": f"{p_pct[0]}% / {p_pct[1]}% / {p_pct[2]}%",
                "Dina Streck (1/X/2)": f"{s_pct[0]}% / {s_pct[1]}% / {s_pct[2]}%",
                "Matematiskt Spelvärde": f"{'+' if v_pct[0]>0 else ''}{v_pct[0]}% / {'+' if v_pct[1]>0 else ''}{v_pct[1]}% / {'+' if v_pct[2]>0 else ''}{v_pct[2]}%"
            })
            match_strings.append(f"Match {r['Match']}: {r['Hemmalag']}-{r['Bortalag']} (Odds: {r['O1']}-{r['OX']}-{r['O2']} | Streck: {r['S1']}%-{r['SX']}%-{r['S2']}%)")
            
        st.markdown("### 2. Matematisk Analysöversikt (Spelvärde)")
        st.dataframe(pd.DataFrame(out_table), use_container_width=True, hide_index=True)
        
        sel = [[int(np.argmax(p))] for p in probs]
        rows = 1
        candidates = []
        for i, (p, cp) in enumerate(zip(probs, crowd_probs)):
            for s in range(3):
                if s != sel[i][0]:
                    candidates.append((p[s] + max(0, p[s] - cp[s]) * 2.0, i, s))
        candidates.sort(key=lambda x: x[0], reverse=True)
        for _, i, s in candidates:
            if s in sel[i]: continue
            current_options = len(sel[i])
            proposed_rows = (rows // current_options) * (current_options + 1)
            if proposed_rows <= budget:
                rows = proposed_rows
                sel[i].append(s)
                
        st.markdown("### 3. Optimerat Systembygge")
        c1, c2, c3 = st.columns(3)
        c1.metric("Vald budget", f"{budget} kr")
        c2.metric("Beräknade rader", f"{rows} st")
        c3.metric("Faktisk kostnad", f"{rows} kr")
        
        detail = []
        system_summary = []
        for i, s in enumerate(sel):
            r_d = f_df.iloc[i]
            signs_text = "".join(SIGSigns[x] if 'SIGSigns' in locals() else SIGNS[x] for x in sorted(s))
            detail.append({"Match": f"{i+1}. {r_d['Hemmalag']} – {r_d['Bortalag']}", "Dina Tecken": signs_text, "Typ": "Spik" if len(s)==1 else ("Halvgardering" if len(s)==2 else "Helgardering")})
            system_summary.append(f"M{i+1}: {signs_text}")
            
        st.dataframe(pd.DataFrame(detail), use_container_width=True, hide_index=True)
        
        st.markdown("### 💬 Fråga Ajjes AI om Live-Fakta & Skador")
        if "messages" not in st.session_state: st.session_state.messages = []
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]): st.write(msg["content"])
            
        if q := st.chat_input("Fråga t.ex: Hämta skador för Man Utd, eller varför spikar vi match 2?"):
            with st.chat_message("user"): st.write(q)
            st.session_state.messages.append({"role": "user", "content": q})
            
            full_prompt = f"Analysera enligt Ajjes Stryktipsmodell. Systemrad: {', '.join(system_summary)}. Budget: {budget} kr. Utgå från dagsaktuell, verklig fotbollsfakta, formkurvor, xG och skador för denna omgång och besvara: {q}"
            
            with st.chat_message("assistant"):
                st.write("⚠️ **AI-Analys aktiverad!** Kopiera texten i rutan nedanför och klistra in den direkt till mig här i vår stora chatt, så skannar jag av sportdatabaserna live efter skador, avstängningar, xG och formkurvor för just den här spelomgången!")
                st.text_area("Kopiera den här texten och klistra in till mig i chatten:", full_prompt, height=120)
            st.session_state.messages.append({"role": "assistant", "content": "Klistra in texten här i chatten så kör vi djupanalysen live!"})
    except Exception as e:
        st.error(f"Ett fel uppstod vid beräkning: {e}")
else:
    st.info("👋 Välkommen Ajje! Ladda upp din exporterade CSV-fil från Numbers ovanför.")
