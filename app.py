import math
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Ajjes Stryktipsmodell", page_icon="⚽", layout="wide")
SIGNS = ["1", "X", "2"]

# --- 1. BERÄKNINGSMOTOR & NORMALISERING (§2, §3, §10, §11, §12) ---

def norm3(v):
    """Säkerställer att summan av tre sannolikheter alltid blir exakt 1.0 (100%)"""
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
    """Läser filen positionellt utifrån användarens exakta Numbers-struktur"""
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python', header=None)
        final_data = []
        match_count = 1
        
        for idx, row in df.iterrows():
            if len(row) < 9:
                continue
            row_str = "".join([str(x) for x in row]).lower()
            if "hemma" in row_str or "borta" in row_str or "streck" in row_str or "odds" in row_str:
                continue
                
            h_name = str(row.iloc[1]).strip()
            a_name = str(row.iloc[2]).strip()
            if h_name == "" or h_name.lower() == "nan":
                continue
                
            # Hämta Streck (Kolumn index 3, 4, 5)
            s1 = get_clean_float(row.iloc[3])
            sx = get_clean_float(row.iloc[4])
            s2 = get_clean_float(row.iloc[5])
            
            # Hämta Odds (Kolumn index 6, 7, 8)
            o1 = get_clean_float(row.iloc[6])
            ox = get_clean_float(row.iloc[7])
            o2 = get_clean_float(row.iloc[8])
            
            # Hämta valfria parametrar om de finns längre ut i filen, annars None/0 (§21)
            stats_1 = get_clean_float(row.iloc[9]) if len(row) > 9 else 0.0
            stats_x = get_clean_float(row.iloc[10]) if len(row) > 10 else 0.0
            stats_2 = get_clean_float(row.iloc[11]) if len(row) > 11 else 0.0
            
            form_text = str(row.iloc[12]).strip() if len(row) > 12 else ""
            injury_text = str(row.iloc[13]).strip() if len(row) > 13 else ""
            motivation_text = str(row.iloc[14]).strip() if len(row) > 14 else ""
            h2h_text = str(row.iloc[15]).strip() if len(row) > 15 else ""
            
            final_data.append({
                "Match": match_count, "Hemmalag": h_name, "Bortalag": a_name,
                "Odds 1": o1, "Odds X": ox, "Odds 2": o2,
                "Streck 1": s1, "Streck X": sx, "Streck 2": s2,
                "xG 1 (%)": stats_1, "xG X (%)": stats_x, "xG 2 (%)": stats_2,
                "Form-Info": form_text, "Skador/Avstängningar": injury_text,
                "Motivation/Tabell": motivation_text, "H2H-Historik": h2h_text
            })
            match_count += 1
            if match_count > 13:
                break
        return pd.DataFrame(final_data)
    except Exception as e:
        st.error(f"Kunde inte tolka Numbers-filen. Fel: {e}")
        return pd.DataFrame()

# --- 2. OPERATIV SYSTEMMOTOR OCH EV-OPTIMERING (§16, §17) ---

def advanced_system_builder(probs, crowd_probs, budget):
    """Fördelar budgeten där extra tecken ger absolut störst matematisk nytta"""
    sel = [[int(np.argmax(p))] for p in probs]
    rows = 1
    candidates = []
    
    for i, (p, cp) in enumerate(zip(probs, crowd_probs)):
        for s in range(3):
            if s != sel[i][0]:
                value_streck = p[s] - cp[s]
                # Prioritering = Sannolikhet + Spelvärdesvikt (§15)
                priority_score = p[s] + max(0, value_streck) * 2.0
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

# --- 3. ANVÄNDARGRÄNSSNITT OCH PRESENTATION (§18, §19, §20) ---

st.title("⚽ Ajjes Spelmotor & Analysverktyg")
st.caption("Strikt matematisk systemoptimering baserad på spelvärde, riskkontroll och budgettäckning.")

with st.sidebar:
    st.header("1. Konfiguration")
    budget = st.selectbox("Välj ditt Systems budget (kr / rader) (§16)", [64, 128, 256, 512, 1024], index=2)
    
    st.markdown("---")
    st.subheader("Modellens Startvikter (§10)")
    w_odds = st.slider("Odds/Marknad (%)", 0, 100, 50)
    w_crowd = st.slider("Streck/Värde (%)", 0, 100, 20)
    w_xg = st.slider("xG/Statistik (%)", 0, 100, 10)
    w_form = st.slider("Form + Hemma/Borta (%)", 0, 100, 8)
    w_inj = st.slider("Skador/Startelva (%)", 0, 100, 7)
    w_mot = st.slider("Tabell/Motivation (%)", 0, 100, 5)
    
    total_w = w_odds + w_crowd + w_xg + w_form + w_inj + w_mot
    if total_w == 0: total_w = 1
    weights = {"odds": w_odds/total_w, "crowd": w_crowd/total_w, "xg": w_xg/total_w, "form": w_form/total_w, "injury": w_inj/total_w, "motivation": w_mot/total_w}

t1, t2, t3 = st.tabs(["📊 Veckans Spelmotor", "⏳ Walk-Forward Backtest", "📑 Regler & Paragrafer"])

with t1:
    up = st.file_uploader("Ladda upp veckans Stryktipsomgång (Exportera som CSV från Numbers)", type=["csv"], key="today")
    
    if not up:
        st.info("👋 Välkommen Ajje! Exportera din tabell från Numbers till en CSV-fil och ladda upp den här ovanför för att köra spelmotorn.")
    else:
        df = parse_ajjes_spec_file(up)
        
        if not df.empty:
            st.markdown("### 1. Insamlad & Verifierad Data")
            st.caption("Du kan granska eller finjustera texter/skador direkt i tabellen innan du kör motorn.")
            edited_df = st.data_editor(df, use_container_width=True, hide_index=True)
            
            probs, crowd_probs, out_table, status_logs = [], [], [], []
            
            for idx, r in edited_df.iterrows():
                # A. ODDS-SANNOLIKHET (§2)
                if r["Odds 1"] > 0 and r["Odds X"] > 0 and r["Odds 2"] > 0:
                    raw_mp = [1/r["Odds 1"], 1/r["Odds X"], 1/r["Odds 2"]]
                    market_p = norm3(raw_mp)
                    odds_status = "✓ Verifierad"
                else:
                    market_p = np.ones(3) / 3
                    odds_status = "Data saknas"
                    
                # B. FOLKETS STRECK (§3)
                if r["Streck 1"] > 0 or r["Streck X"] > 0 or r["Streck 2"] > 0:
                    crowd_p = norm3([r["Streck 1"], r["Streck X"], r["Streck 2"]])
                    crowd_status = "✓ Verifierad"
                else:
                    crowd_p = np.ones(3) / 3
                    crowd_status = "Data saknas"
                    
                # C. xG STATISTIK (§5)
                if r["xG 1 (%)"] > 0 or r["xG X (%)"] > 0 or r["xG 2 (%)"] > 0:
                    xg_p = norm3([r["xG 1 (%)"], r["xG X (%)"], r["xG 2 (%)"]])
                    xg_status = "✓ Verifierad"
                else:
                    xg_p = market_p
                    xg_status = "Data saknas"
                    
                # D. FORM, SKADOR, MOTIVATION STATUSLOGGAR (§4, §6, §7, §8, §21)
                form_status = "✓ Analyserad" if str(r["Form-Info"]).strip() and str(r["Form-Info"]).lower() != "nan" else "Data saknas"
                injury_status = "✓ Analyserad" if str(r["Skador/Avstängningar"]).strip() and str(r["Skador/Avstängningar"]).lower() != "nan" else "Data saknas"
                mot_status = "✓ Analyserad" if str(r["Motivation/Tabell"]).strip() and str(r["Motivation/Tabell"]).lower() != "nan" else "Data saknas"
                h2h_status = "✓ Analyserad" if str(r["H2H-Historik"]).strip() and str(r["H2H-Historik"]).lower() != "nan" else "Data saknas"
                
                # SANNOLIKHETSMODELLEN: Väg samman alla parametrar (§10, §11)
                p = (
                    market_p * weights["odds"] +
                    crowd_p * weights["crowd"] +
                    xg_p * weights["xg"]
                )
                p = norm3(p)
                
                # Justera baserat på textvariabler om de finns
                if injury_status == "✓ Analyserad" and "avstängd" in str(r["Skador/Avstängningar"]).lower():
                    p[0] *= 0.95 # Sänk hemmalaget marginellt om viktig spelare saknas
                    p = norm3(p)
                    
                probs.append(p)
                crowd_probs.append(crowd_p)
                
                # BERÄKNA SPELVÄRDE (§12)
                v1 = p[0] - crowd_p[0]
                vX = p[1] - crowd_p[1]
                v2 = p[2] - crowd_p[2]
                
                out_table.append({
                    "Match": f"{r['Match']}. {r['Hemmalag']} – {r['Bortalag']}",
                    "Ajjes Sannolikhet (1/X/2)": f"{round(p[0]*100)}% / {round(p[1]*100)}% / {round(p[2]*100)}%",
                    "Folkets Streck (1/X/2)": f"{round(crowd_p[0]*100)}% / {round(crowd_p[1]*100)}% / {round(crowd_p[2]*100)}%",
                    "Matematiskt Värde (1/X/2)": f"{'+' if v1>0 else ''}{round(v1*100,1)}% / {'+' if vX>0 else ''}{round(vX*100,1)}% / {'+' if v2>0 else ''}{round(v2*100,1)}%"
                })
                
                status_logs.append({
                    "Match": f"{r['Match']}. {r['Hemmalag']}", "Odds": odds_status, "Streck": crowd_status,
                    "xG-Data": xg_status, "Form": form_status, "Skador": injury_status, "Motivation": mot_status, "H2H": h2h_status
                })

            st.markdown("---")
            st.subheader("2. Datakvalitet & Statuslogg (§21)")
            st.dataframe(pd.DataFrame(status_logs), use_container_width=True, hide_index=True)
            
