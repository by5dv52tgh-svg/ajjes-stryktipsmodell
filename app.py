import math
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Ajjes Stryktipsmodell", page_icon="⚽", layout="wide")
SIGNS=["1","X","2"]

def norm3(v):
    a=np.maximum(np.asarray(v,dtype=float),1e-9); return a/a.sum()

def implied(odds): return norm3([1/max(float(x),1e-6) for x in odds])

def crowd(r):
    v=[r.get("stake_1",0),r.get("stake_x",0),r.get("stake_2",0)]
    return norm3(v) if sum(float(x or 0) for x in v)>0 else np.ones(3)/3

def factor(r,prefix):
    v=[r.get(f"{prefix}_1",np.nan),r.get(f"{prefix}_x",np.nan),r.get(f"{prefix}_2",np.nan)]
    if all(pd.isna(x) for x in v): return np.ones(3)/3
    v=[33.333 if pd.isna(x) else float(x) for x in v]; return norm3(v)

def model(r,w):
    odds=[r.get("odds_1",np.nan),r.get("odds_x",np.nan),r.get("odds_2",np.nan)]
    m=implied(odds) if all(pd.notna(x) and float(x)>1 for x in odds) else np.ones(3)/3
    parts=[(m,w["odds"]),(crowd(r),w["crowd"]),(factor(r,"stats"),w["stats"]),(factor(r,"form"),w["form"]),(factor(r,"injury"),w["injury"]),(factor(r,"motivation"),w["motivation"])]
    lp=sum(weight*np.log(np.maximum(p,1e-9)) for p,weight in parts); p=np.exp(lp-lp.max()); return norm3(p)

def system_builder(probs,values,budget):
    sel=[[int(np.argmax(p))] for p in probs]; rows=1
    cand=[]
    for i,(p,v) in enumerate(zip(probs,values)):
        for s in range(3):
            if s!=sel[i][0]: cand.append((p[s]*(1+max(v[s],0)),i,s))
    for _,i,s in sorted(cand,reverse=True):
        if s in sel[i]: continue
        nr=rows*(len(sel[i])+1)//len(sel[i])
        if nr<=budget: sel[i].append(s); rows=nr
    return [sorted(x) for x in sel],math.prod(len(x) for x in sel)

weights_default={"odds":.50,"crowd":.20,"stats":.10,"form":.08,"injury":.07,"motivation":.05}

st.title("⚽ Ajjes Stryktipsmodell")
st.caption("Privat analysverktyg — sannolikheter, värde, system och backtest.")
with st.sidebar:
    st.header("Modellvikter")
    vals={k:st.slider(k.capitalize(),0,100,round(v*100)) for k,v in weights_default.items()}
    total=sum(vals.values()) or 1; w={k:v/total for k,v in vals.items()}
    budget=st.selectbox("Systembudget (kr)",[64,128,256,512,1024],index=1)
    st.info("H2H har ingen egen vikt i grundmodellen.")

t1,t2,t3=st.tabs(["Dagens omgång","Backtest","Data & regler"])
with t1:
    st.subheader("1. Lägg in 13 matcher")
    up=st.file_uploader("Ladda upp CSV",type="csv",key="today")
    if up: df=pd.read_csv(up)
    else:
        df=pd.read_csv("/mnt/data/ajjes_stryktipsmodell/stryktips_template.csv") if Path("/mnt/data/ajjes_stryktipsmodell/stryktips_template.csv").exists() else pd.DataFrame()
    if df.empty:
        st.warning("Ladda upp en CSV med 13 matcher.")
    else:
        st.dataframe(df.head(13),use_container_width=True,hide_index=True)
        if len(df)>=13 and st.button("🔎 Kör Ajjes modell",type="primary",use_container_width=True):
            probs=[]; vals_out=[]; out=[]
            for _,r in df.iloc[:13].iterrows():
                p=model(r,w); c=crowd(r); v=p-c; probs.append(p); vals_out.append(v)
                out.append({"Match":f"{r.get('home','')} – {r.get('away','')}","1 %":round(p[0]*100,1),"X %":round(p[1]*100,1),"2 %":round(p[2]*100,1),"Bäst":SIGNS[int(p.argmax())],"Värde 1":round(v[0]*100,1),"Värde X":round(v[1]*100,1),"Värde 2":round(v[2]*100,1)})
            st.session_state.update(probs=probs,vals=vals_out,df=df.iloc[:13].copy(),result=pd.DataFrame(out))
        if "result" in st.session_state:
            st.subheader("2. Modellens prognoser")
            st.dataframe(st.session_state.result,use_container_width=True,hide_index=True)
            sel,rows=system_builder(st.session_state.probs,st.session_state.vals,budget)
            st.subheader("3. System")
            a,b,c=st.columns(3); a.metric("Budget",f"{budget} kr"); b.metric("Rader",rows); c.metric("Kostnad",f"{rows} kr")
            st.code(" – ".join("".join(SIGNS[s] for s in x) for x in sel))
            detail=[]
            for i,s in enumerate(sel):
                r=st.session_state.df.iloc[i]; detail.append({"Match":f"{r.get('home','')} – {r.get('away','')}","System":"".join(SIGNS[x] for x in s),"Tecken":len(s)})
            st.dataframe(pd.DataFrame(detail),use_container_width=True,hide_index=True)
with t2:
    st.subheader("Historiskt backtest")
    h=st.file_uploader("Historisk CSV",type="csv",key="hist")
    if h:
        hist=pd.read_csv(h); req=["odds_1","odds_x","odds_2","stake_1","stake_x","stake_2","result"]
        miss=[x for x in req if x not in hist.columns]
        if miss: st.error("Saknade kolumner: "+", ".join(miss))
        else:
            hist=hist[hist.result.isin(SIGNS)].copy(); pred=[]; actual=[]; bs=[]
            for _,r in hist.iterrows():
                p=model(r,w); pred.append(SIGNS[int(p.argmax())]); actual.append(r.result); y=np.array([r.result==s for s in SIGNS],dtype=float); bs.append(np.mean((p-y)**2))
            acc=np.mean(np.array(pred)==np.array(actual)) if actual else 0
            a,b=st.columns(2); a.metric("Bästa-tecken träff",f"{acc*100:.1f}%"); b.metric("Brier score",f"{np.mean(bs):.4f}" if bs else "–")
            o=hist[[c for c in ["round","home","away","result"] if c in hist.columns]].copy(); o["modell"]=pred; o["rätt"]=o.modell==o.result; st.dataframe(o,use_container_width=True,hide_index=True)
            st.warning("Ett seriöst backtest måste använda många historiska omgångar och bara information som fanns före respektive match.")
with t3:
    st.subheader("CSV-regler")
    st.markdown("**Obligatoriska:** `home, away, odds_1, odds_x, odds_2, stake_1, stake_x, stake_2`\n\n**Frivilliga:** `stats_1/x/2, form_1/x/2, injury_1/x/2, motivation_1/x/2, result`.\n\nOdds normaliseras till marknadssannolikheter. Streck visar folkets fördelning. Modellen blandar komponenterna i log-skala. Systemkostnad = exakt antal rader × 1 kr. 1X = 2 varianter, 1X2 = 3.")
    st.download_button("⬇️ Ladda ner CSV-mall",data=pd.DataFrame(columns=["round","match","home","away","odds_1","odds_x","odds_2","stake_1","stake_x","stake_2","stats_1","stats_x","stats_2","form_1","form_x","form_2","injury_1","injury_x","injury_2","motivation_1","motivation_x","motivation_2","result"]).to_csv(index=False),file_name="ajjes_stryktips_mall.csv",mime="text/csv")
