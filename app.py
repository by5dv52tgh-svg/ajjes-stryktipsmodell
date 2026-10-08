import math, os
import numpy as np
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title='Ajjes Stryktipsmodell', page_icon='⚽', layout='wide')
SIGNS=['1','X','2']

def norm(x):
    a=np.asarray(x,dtype=float)
    if np.any(~np.isfinite(a)) or np.any(a<0) or a.sum()<=0: raise ValueError('Saknade eller ogiltiga värden.')
    return a/a.sum()

def odds_probs(odds):
    o=np.asarray(odds,dtype=float)
    if np.any(~np.isfinite(o)) or np.any(o<=1): raise ValueError('Odds måste vara decimalodds större än 1.')
    return norm(1/o)

def safe(v):
    try: return float(str(v).replace('%','').replace(',','.'))
    except: return float('nan')

def template():
    return pd.DataFrame([{'Match':i,'Hemmalag':'','Bortalag':'','O1':np.nan,'OX':np.nan,'O2':np.nan,'S1':np.nan,'SX':np.nan,'S2':np.nan,'xG_H':np.nan,'xG_B':np.nan,'Form_H':'','Form_B':'','Skador_och_lagnyheter':'','Motivation':'','Källor':''} for i in range(1,14)])

def get_json(url):
    r=requests.get(url,headers={'Accept':'application/json','User-Agent':'AjjesStryktipsmodell/1.0'},timeout=20)
    r.raise_for_status(); return r.json()

def dig(obj):
    """Find arrays named events/matches/fixtures/games; schema still must be verified."""
    out=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            if str(k).lower() in ('events','matches','fixtures','games') and isinstance(v,list) and v and all(isinstance(z,dict) for z in v): out.append((obj,v))
            out.extend(dig(v))
    elif isinstance(obj,list):
        for v in obj: out.extend(dig(v))
    return out

def get(d,names,default=None):
    low={str(k).lower():k for k in d}
    for n in names:
        if n.lower() in low: return d[low[n.lower()]]
    return default

def parse_team(v):
    if isinstance(v,dict): return get(v,['name','displayName','teamName','shortName'],'')
    return v if isinstance(v,str) else ''

def parse_coupon(url):
    data=get_json(url)
    for container,events in dig(data):
        rows=[]
        for i,e in enumerate(events,1):
            h=parse_team(get(e,['homeTeam','home_team','home','homeName','homeTeamName']))
            a=parse_team(get(e,['awayTeam','away_team','away','awayName','awayTeamName']))
            if not h or not a:
                ps=get(e,['participants','competitors','teams'])
                if isinstance(ps,list) and len(ps)>=2: h,a=parse_team(ps[0]),parse_team(ps[1])
            if not h or not a: rows=[]; break
            def stake(sign):
                direct=get(e,[f'{sign}Streck',f'{sign}Percent',f'stake{sign}',f'percentage{sign}'])
                if direct is not None: return safe(direct)
                outcomes=get(e,['outcomes','bettingOutcomes','pools'],[])
                if isinstance(outcomes,list):
                    aliases={'1':['1','HOME','H'],'X':['X','DRAW','D'],'2':['2','AWAY','A']}[sign]
                    for o in outcomes:
                        if isinstance(o,dict) and str(get(o,['type','name','sign','outcome'],'')).upper() in aliases:
                            return safe(get(o,['percentage','percent','stake','share']))
                return np.nan
            rows.append({'Match':i,'Hemmalag':h,'Bortalag':a,'O1':np.nan,'OX':np.nan,'O2':np.nan,'S1':stake('1'),'SX':stake('X'),'S2':stake('2')})
        if len(rows)==13: return pd.DataFrame(rows), {'omgång':get(container,['drawNumber','roundNumber','productNumber','number','id'],'Ej angivet'),'datum':get(container,['date','drawDate','startDate','closeTime','stopTime'],'Ej angivet')}
    raise ValueError('API-svaret hämtades men hittade inte 13 matcher i ett känt format. Anpassa parse_coupon() till den dokumenterade endpointen. Ingen kupong hittades på.')

def optimize(probs,crowds,budget,value_weight=0.0005):
    # Dynamic programming: optimize joint coverage probability, row product <= budget.
    subsets=[(0,),(1,),(2,),(0,1),(0,2),(1,2),(0,1,2)]
    states={1:(0.0,[])}
    for i,p in enumerate(probs):
        nxt={}
        for rows,(score,chosen) in states.items():
            for ss in subsets:
                nr=rows*len(ss)
                if nr>budget: continue
                covered=max(float(sum(p[j] for j in ss)),1e-12)
                bonus=0.0
                c=crowds[i]
                if c is not None: bonus=value_weight*sum(max(0.0,float(p[j]-c[j])) for j in ss)
                ns=score+math.log(covered)+bonus
                if nr not in nxt or ns>nxt[nr][0]: nxt[nr]=(ns,chosen+[list(ss)])
        states=nxt
    if not states: raise ValueError('Ingen kombination ryms inom budgeten.')
    rows,(_,chosen)=max(states.items(),key=lambda kv:kv[1][0])
    coverage=float(np.prod([sum(p[j] for j in ss) for p,ss in zip(probs,chosen)]))
    return chosen,rows,coverage

st.title('⚽ Ajjes Stryktipsmodell')
st.caption('Ingen påhittad kupong eller låtsad live-data. Verifiera API-källan innan automatisk hämtning används.')
with st.sidebar:
    budget=st.selectbox('Systembudget (kr)',[64,128,256,512,1024,2048,4096])
    api_url=st.text_input('Verifierad Svenska Spel API-endpoint',value=os.getenv('SVENSKASPEL_COUPON_API',''),placeholder='API-URL från dokumenterad källa')

if 'df' not in st.session_state: st.session_state.df=template()
if 'meta' not in st.session_state: st.session_state.meta={}
st.header('1. Aktuell kupong')
c1,c2=st.columns([1,2])
with c1:
    if st.button('Hämta aktuell kupong',type='primary',use_container_width=True):
        if not api_url.strip(): st.error('Ange först en verifierad API-endpoint. Ingen officiell endpoint har hårdkodats eftersom den måste kontrolleras.')
        else:
            try:
                d,m=parse_coupon(api_url.strip())
                for col in ['xG_H','xG_B','Form_H','Form_B','Skador_och_lagnyheter','Motivation','Källor']:
                    if col not in d: d[col]=np.nan if col in ['xG_H','xG_B'] else ''
                st.session_state.df=d; st.session_state.meta=m; st.success('Kupong hämtad från angiven endpoint.')
            except Exception as e: st.error(f'Kunde inte verifiera kupongen: {e}')
with c2:
    uploaded=st.file_uploader('Eller importera CSV (exakt 13 matcher)',type=['csv'])
    if uploaded:
        try:
            d=pd.read_csv(uploaded)
            if len(d)!=13 or not {'Hemmalag','Bortalag'}.issubset(d.columns): st.error('CSV måste ha exakt 13 rader och Hemmalag/Bortalag-kolumner.')
            else:
                for col in template().columns:
                    if col not in d: d[col]=np.nan if col in ['O1','OX','O2','S1','SX','S2','xG_H','xG_B'] else ''
                st.session_state.df=d; st.success('CSV importerad.')
        except Exception as e: st.error(f'CSV-fel: {e}')
if st.session_state.meta: st.caption(f"Omgång: {st.session_state.meta.get('omgång')} · Datum/spelstopp: {st.session_state.meta.get('datum')}")
st.info('Fyll/importera odds och streck om API:t inte levererar dem. Tomma uppgifter ersätts inte med gissningar.')
edited=st.data_editor(st.session_state.df,num_rows='fixed',use_container_width=True,key='coupon_edit')
st.session_state.df=edited

st.header('2. Odds, streck och matematiskt spelvärde')
rows=[]; market_probs=[]; crowd_probs=[]
for i,r in edited.iterrows():
    try: mp=odds_probs([safe(r.get('O1')),safe(r.get('OX')),safe(r.get('O2'))])
    except: mp=None
    ss=np.array([safe(r.get('S1')),safe(r.get('SX')),safe(r.get('S2'))])
    try: cp=norm(ss) if np.all(np.isfinite(ss)) else None
    except: cp=None
    market_probs.append(mp); crowd_probs.append(cp)
    name=f"{i+1}. {r.get('Hemmalag','')} – {r.get('Bortalag','')}"
    if mp is None:
        rows.append({'Match':name,'Oddsbaserad P(1/X/2)':'Saknas','Streck (1/X/2)':'Saknas','Skillnad p.e.':'Kan ej räknas','Värdeindex':'Kan ej räknas'})
    elif cp is None:
        rows.append({'Match':name,'Oddsbaserad P(1/X/2)':' / '.join(f'{x*100:.1f}%' for x in mp),'Streck (1/X/2)':'Saknas','Skillnad p.e.':'Kan ej räknas','Värdeindex':'Kan ej räknas'})
    else:
        rows.append({'Match':name,'Oddsbaserad P(1/X/2)':' / '.join(f'{x*100:.1f}%' for x in mp),'Streck (1/X/2)':' / '.join(f'{x*100:.1f}%' for x in cp),'Skillnad p.e.':' / '.join(f'{(mp[j]-cp[j])*100:+.1f}' for j in range(3)),'Värdeindex':' / '.join(f'{mp[j]/max(cp[j],1e-6):.2f}' for j in range(3))})
st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
st.caption('Värdeindex = oddsbaserad sannolikhet / streckandel. Detta är ett värdesamband, inte en garanti för vinst.')

st.header('3. Ajjes AI-analys och system')
st.warning('Riktig aktuell xG-, skade-, startelva- och motivationsanalys kräver verifierade datakällor och en ansluten AI-tjänst. Denna kod hittar inte på sådan data; tills dess används odds som transparent baslinje.')
if st.button('Analysera och optimera system',type='primary',use_container_width=True):
    missing=[i+1 for i,p in enumerate(market_probs) if p is None]
    if missing: st.error('Giltiga odds saknas för match(er): '+', '.join(map(str,missing))+'. Lägg in odds innan analysen körs.')
    else:
        chosen,nrows,coverage=optimize(market_probs,crowd_probs,budget)
        output=[]
        for i,ss in enumerate(chosen):
            r=edited.iloc[i]; p=market_probs[i]; cp=crowd_probs[i]
            signs=''.join(SIGNS[j] for j in ss)
            output.append({'Match':f"{i+1}. {r.get('Hemmalag','')} – {r.get('Bortalag','')}",'P(1/X/2)':' / '.join(f'{v*100:.1f}%' for v in p),'Ajjes tecken':signs,'Typ':'Spik' if len(ss)==1 else 'Halvgardering' if len(ss)==2 else 'Helgardering','Värdeindex 1/X/2':' / '.join(f'{p[j]/max(cp[j],1e-6):.2f}' for j in range(3)) if cp is not None else 'Streck saknas','Motivering':'Oddsbaserad baslinje. Ingen verifierad AI-analys av aktuell form/xG/skador är ansluten.'})
        st.subheader('Föreslaget system')
        st.dataframe(pd.DataFrame(output),use_container_width=True,hide_index=True)
        st.metric('Antal rader',nrows); st.metric('Kostnad',f'{nrows} kr'); st.metric('Beräknad chans till 13 rätt',f'{coverage*100:.6f}%')
        st.code(' – '.join(''.join(SIGNS[j] for j in ss) for ss in chosen))
        st.download_button('Ladda ner systemet som CSV',pd.DataFrame(output).to_csv(index=False).encode('utf-8-sig'),'ajjes_system.csv','text/csv')
        st.caption('Beräknad täckningschans förutsätter korrekta sannolikheter och oberoende matchutfall. Ingen modell kan garantera 13 rätt.')
