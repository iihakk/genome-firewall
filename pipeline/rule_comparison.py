"""Honest comparison: model vs a PROPERLY specified ResFinder/PointFinder-style rule set."""
import csv,json,sys,re,numpy as np
from collections import defaultdict
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
csv.field_size_limit(10**7)
V=json.load(open('data/vocab_map.json'))
def lm(t):
    r=V.get(t)
    if not r or not r.get('family') or r.get('confidence',0)<0.5: return None
    fam=re.sub(r'[^A-Za-z0-9()\'-]','',r['family']).lower()
    if not fam or fam=='null': return None            # FIX: drop null-family tokens
    k=r.get('kind') or ''
    return f"{k[:5].upper()}:{fam}" if k in ('point_mutation','truncation') else fam

rows=list(csv.DictReader(open('data/ncbi_klebsiella.tsv'),delimiter='\t'))
phen=defaultdict(dict); feats={}
for r in rows:
    g=r['asm_acc']
    feats[g]={x for x in (lm(t) for t in (r['genotypes'] or '').split(';') if t) if x}
    for p in (r['phenotypes'] or '').split(';'):
        if '=' in p:
            d,_,v=p.partition('=')
            if v in ('Resistant','Susceptible'): phen[d.strip()][g]=1 if v=='Resistant' else 0

CARBA={'blakpc','blandm','blavim','blaimp','blaoxa-48','blaoxa48'}
# blaSHV is chromosomal in K. pneumoniae (92% of isolates) and blaTEM is broad-spectrum;
# neither marks ESBL activity without allele-level typing, so a correct rule excludes both.
ESBL={'blactx-m','blactxm'}
PORIN={'TRUNC:ompk35','TRUNC:ompk36','POINT:ompk35','POINT:ompk36'}
FQ={'POINT:gyra','POINT:parc','qnra','qnrb','qnrs','qnr'}
RULES={
 'meropenem':CARBA,'ertapenem':CARBA|PORIN,'imipenem':CARBA,
 'ceftazidime':CARBA|ESBL|{'blaampc'},'ceftriaxone':CARBA|ESBL|{'blaampc'},
 'cefotaxime':CARBA|ESBL|{'blaampc'},'cefepime':CARBA|ESBL,
 'ciprofloxacin':FQ,'levofloxacin':FQ,
 'gentamicin':{'aac(3)','rmt','arma'},'amikacin':{'rmt','arma',"aac(6')"},
 'tobramycin':{'aac(3)',"aac(6')",'ant(2)','rmt'},
 'trimethoprim-sulfamethoxazole':{'sul','dfr'},'tetracycline':{'tet'},
 'colistin':{'mcr','TRUNC:mgrb','POINT:mgrb','POINT:pmrb','POINT:phoq'}}

print(f"{'drug':<30}{'n':>5}{'RULE':>8}{'MODEL':>8}{'AUC':>8}{'delta':>9}")
print("-"*70)
gains=[]
for d,trig in RULES.items():
    ids=[g for g in phen.get(d,{}) if g in feats]
    if len(ids)<80: continue
    y=np.array([phen[d][g] for g in ids])
    if min(y.sum(),len(y)-y.sum())<20: continue
    rb=balanced_accuracy_score(y,np.array([1 if (feats[g]&trig) else 0 for g in ids]))
    cnt=defaultdict(int)
    for g in ids:
        for t in feats[g]: cnt[t]+=1
    n=len(ids); vocab=sorted(t for t,c in cnt.items() if 0.02*n<=c<=0.98*n)
    vi={t:i for i,t in enumerate(vocab)}
    X=np.zeros((n,len(vocab)),np.int8)
    for r_,g in enumerate(ids):
        for t in feats[g]:
            if t in vi: X[r_,vi[t]]=1
    oof=np.zeros(n)
    for tr,te in StratifiedKFold(5,shuffle=True,random_state=0).split(X,y):
        m=CalibratedClassifierCV(HistGradientBoostingClassifier(max_iter=250,random_state=0),method='isotonic',cv=3).fit(X[tr],y[tr])
        oof[te]=m.predict_proba(X[te])[:,1]
    mb=balanced_accuracy_score(y,(oof>0.5).astype(int)); auc=roc_auc_score(y,oof)
    gains.append(mb-rb)
    f=" WIN" if mb-rb>0.02 else (" loss" if mb-rb<-0.02 else " tie")
    print(f"{d:<30}{n:>5}{rb:>8.3f}{mb:>8.3f}{auc:>8.3f}{mb-rb:>+9.3f}{f}")
print("-"*70)
w=sum(1 for g in gains if g>0.02); t=sum(1 for g in gains if abs(g)<=0.02); l=sum(1 for g in gains if g<-0.02)
print(f"model WINS {w}, ties {t}, loses {l} of {len(gains)}")
print(f"mean gain over a correctly-specified rule: {np.mean(gains):+.3f}")
