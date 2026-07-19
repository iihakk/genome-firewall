"""Does the method transfer to a Gram-positive organism with entirely different biology?

Klebsiella resistance runs through beta-lactamases, porins and efflux. S. aureus runs through
mecA (an altered penicillin-binding protein), blaZ, and vancomycin pathway changes. If the
pipeline only worked because it was tuned to Gram-negative mechanisms, this is where it breaks.
"""
import csv, re, sys, numpy as np
from collections import defaultdict, Counter
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold, GroupShuffleSplit
from sklearn.metrics import roc_auc_score, balanced_accuracy_score
csv.field_size_limit(10**7)

def load(path):
    f=open(path,newline='',encoding='utf-8',errors='replace')
    rd=csv.reader(f,delimiter='\t'); h=next(rd)
    iA,iG,iAcc=h.index('AST_phenotypes'),h.index('AMR_genotypes'),h.index('asm_acc')
    feats,phen={},defaultdict(dict)
    for r in rd:
        if len(r)<=iA or not r[iA] or r[iA] in ('NULL','-'): continue
        g=r[iAcc] or f"row{len(feats)}"
        toks=set()
        for t in (r[iG] if len(r)>iG else '').split(','):
            t=t.strip()
            if not t or t.upper() in ('NULL','-'): continue
            if t.endswith('=MISTRANSLATION') or t.endswith('=PARTIAL'): continue
            if t.endswith('=POINT'): toks.add('POINT:'+re.split(r'_',t[:-6])[0].lower()); continue
            if re.search(r'fsTer|Ter\d*$',t): toks.add('TRUNC:'+re.split(r'_',t)[0].lower()); continue
            toks.add(re.sub(r'-\d+$','',t.split('=')[0]).lower())
        ph={}
        for part in r[iA].split(','):
            if '=' not in part: continue
            d,_,v=part.partition('='); v=v.strip().split('|')[0]
            if v in ('S','susceptible'): ph[d.strip().lower()]=0
            elif v in ('R','resistant','nonsusceptible'): ph[d.strip().lower()]=1
        if ph: feats[g],phen[g]=toks,ph
    return feats,phen

# Rule baseline for S. aureus — the textbook genotype->phenotype calls.
SA_RULES={
 'oxacillin':{'meca','mecc','mecr1','meci'},
 'cefoxitin':{'meca','mecc'},
 'penicillin':{'blaz','blai','blar1','meca'},
 'erythromycin':{'erm(a)','erm(b)','erm(c)','msr(a)','mph(c)'},
 'clindamycin':{'erm(a)','erm(b)','erm(c)','lnu(a)','vga(a)'},
 'tetracycline':{'tet(k)','tet(m)','tet(38)','tet(l)'},
 'gentamicin':{"aac(6')-aph(2'')",'ant(4)-ia','aph(3)-iii'},
 'trimethoprim-sulfamethoxazole':{'dfrg','dfrk','dfra','sul1','sul2'},
 'ciprofloxacin':{'POINT:gyra','POINT:grla','POINT:parc'},
 'rifampin':{'POINT:rpob'},
 'vancomycin':{'vana','vanb'},
 'linezolid':{'cfr','POINT:rrl','optra'},
}

feats,phen=load('data/ncbi_amr_saur.tsv')
print(f"S. aureus isolates with AST + genotype: {len(feats)}\n")
print(f"{'drug':<32}{'n':>5}{'%R':>5}{'AUC':>8}{'model bAcc':>12}{'rule bAcc':>11}{'delta':>8}")
print("-"*81)
gains=[]; aucs=[]
for drug,trig in SA_RULES.items():
    ids=[g for g in feats if drug in phen[g]]
    if len(ids)<120: continue
    y=np.array([phen[g][drug] for g in ids])
    if min(y.sum(),len(y)-y.sum())<25: continue
    cnt=Counter(t for g in ids for t in feats[g]); n=len(ids)
    vocab=sorted(t for t,c in cnt.items() if 0.02*n<=c<=0.98*n)
    if len(vocab)<3: continue
    vi={t:i for i,t in enumerate(vocab)}
    X=np.zeros((n,len(vocab)),np.int8)
    for r_,g in enumerate(ids):
        for t in feats[g]:
            if t in vi: X[r_,vi[t]]=1
    rule=np.array([1 if (feats[g]&trig) else 0 for g in ids])
    fire=rule.mean()
    if not (0.05<=fire<=0.95): continue          # same coverage guard as the Klebsiella work
    rb=balanced_accuracy_score(y,rule)
    oof=np.zeros(n)
    for a,b in StratifiedKFold(5,shuffle=True,random_state=0).split(X,y):
        m=CalibratedClassifierCV(HistGradientBoostingClassifier(max_iter=200,random_state=0),
                                 method='isotonic',cv=3).fit(X[a],y[a])
        oof[b]=m.predict_proba(X[b])[:,1]
    auc=roc_auc_score(y,oof); mb=balanced_accuracy_score(y,(oof>.5).astype(int))
    gains.append(mb-rb); aucs.append(auc)
    flag=" WIN" if mb-rb>0.02 else (" loss" if mb-rb<-0.02 else " tie")
    print(f"{drug:<32}{n:>5}{100*y.mean():>4.0f}%{auc:>8.3f}{mb:>12.3f}{rb:>11.3f}{mb-rb:>+8.3f}{flag}")
print("-"*81)
if gains:
    w=sum(1 for g in gains if g>0.02); t=sum(1 for g in gains if abs(g)<=0.02); l=sum(1 for g in gains if g<-0.02)
    print(f"\nmean AUC {np.mean(aucs):.3f} over {len(aucs)} drugs")
    print(f"vs clinical rule: wins {w}, ties {t}, losses {l}  (mean {np.mean(gains):+.3f})")
