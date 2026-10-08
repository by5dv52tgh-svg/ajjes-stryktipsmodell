import numpy as np, pandas as pd, streamlit as st
st.set_page_config(page_title="Ajjes Stryktipsmodell", page_icon="⚽", layout="wide")
SIGNS = ["1", "X", "2"]

def norm3(v):
    a = np.maximum(np.asarray(v, dtype=float), 1e-9)
    return a / a.sum()

def parse_file(file):
    try:
        df = pd.read_csv(file, sep=None, engine='python').dropna(how='all').head(13)
        res = []
        for i, r in enumerate(df.itertuples(index=False)):
            vals = [x for x in list(r) if pd.notna(x) and str(x).strip() != ""]
            if len(vals) < 3 or "home" in str(vals).lower() or "match" in str(vals).lower(): continue
            h, a = str(vals[1]).strip(), str(vals[2]).strip()
            num = [float(str(x).replace("%","").strip()) for x in vals if str(x).replace("%","").strip().replace(".","",1).isdigit()]
            s = num[1:4] if (num and int(num[0]) == i+1) else num[:3]
            s1, sx, s2 = (s[0] if len(s)>0 else 33), (s[1] if len(s)>1 else 33), (s[2] if len(s)>2 else 33)
            tot = s1 + sx + s2 if (s1 + sx + s2) > 0 else 100
            o1, ox, o2 = round(1 / max((s1/tot)*0.9, 0.05), 2), round(1 / max((sx/tot)*0.9, 0.05), 2), round(1 / max((s2/tot)*0.9, 0.05), 2)
            res.append({"Match": i+1, "Hemmalag": h, "Bortalag": a, "Odds 1": o1, "Odds X": ox, "Odds 2": o2, "Streck 1": int(s1), "Streck X": int(sx), "Streck 2": int(s2)})
        return pd.DataFrame(res)
    except: return pd.DataFrame()

def build_sys(probs, cp, budget):
    sel = [[int(np.argmax(p))] for p in probs]
    rows, cand = 1, []
    for i, (p, c) in enumerate(zip(probs, cp)):
        for s in range(3):
            if s != sel[i]: cand.append((p[s] + max(0, p[s] - c[s]) * 1.5, i, s))
    cand.sort(reverse=True)
    for _, i, s in cand:
        if s in sel[i]: continue
        cur = len(sel[i])
        prop = (rows // cur) * (cur + 1)
        if prop <= budget: sel[i].append(s); rows = prop
    return [sorted(x) for x in sel], rows

st.title("⚽ Ajjes Stryktipsmodell")
budget = st.sidebar.selectbox("Systembudget (kr)", [16, 64, 256, 1024, 4096], index=2)
up = st.file_uploader("Ladda upp CSV från Numbers", type=["csv"])

if up:
    df = parse_file(up)
    if not df.empty:
        st.subheader("1. Förhandsgranskning")
        st.dataframe(df, use_container_width=True, hide_index=True)
        probs, cp, out = [], [], []
        for idx, r in df.iterrows():
            mp = norm3([1/r["Odds 1"], 1/r["Odds X"], 1/r["Odds 2"]])
            c = norm3([r["Streck 1"], r["Streck X"], r["Streck 2"]])
            p = norm3(mp * 0.5 + c * 0.5)
            probs.append(p); cp.append(c)
            v = p - c
            out.append({"Match": f"{idx+1}. {r['Hemmalag']} - {r['Bortalag']}", "Ajje 1": f"{round(p[0]*100,1)}%", "Ajje X": f"{round(p[1]*100,1)}%", "Ajje 2": f"{round(p[2]*100,1)}%", "Folk 1": f"{r['Streck 1']}%", "Folk X": f"{r['Streck X']}%", "Folk 2": f"{r['Streck 2']}%", "Spelvärde": f"{round(v[0]*100,1)}% / {round(v[1]*100,1)}% / {round(v[2]*100,1)}%"})
        st.subheader("2. Analysöversikt")
        st.dataframe(pd.DataFrame(out), use_container_width=True, hide_index=True)
        sel, rows = build_sys(probs, cp, budget)
        st.subheader("3. Optimerat Systembygge")
        st.info(f"**Rader:** {rows} st  |  **Kostnad:** {rows} kr  |  **Rad:** {' – '.join(''.join(SIGNS[s] for s in x) for x in sel)}")
        detail = [{"Match": f"{i+1}. {df.iloc[i]['Hemmalag']} - {df.iloc[i]['Bortalag']}", "Tecken": "".join(SIGNS[x] for x in s)} for i, s in enumerate(sel)]
        st.dataframe(pd.DataFrame(detail), use_container_width=True, hide_index=True)
