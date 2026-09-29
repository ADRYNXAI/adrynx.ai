# ADRYNX AI v2.4 - PANTIN - Enfant sous contrôle des Parents Gardiens GRATUITS
# Principe: ADRYNX = enfant qui propose, Parents = Groq/HF/OpenRouter corrigent avant envoi
# Ordre: social -> admin -> apprentissage -> correction -> calcul -> pronom -> cache -> enfant(internet) -> VALIDATION PARENTS -> reponse finale + apprentissage
import ast, base64, hmac, operator, os, random, re, sqlite3, threading, unicodedata, requests

DB = os.environ.get("ADRYNX_DB", "memoire.db")
HEADERS = {"User-Agent": "ADRYNX-AI/2.4-PANTIN"}
VERROU = threading.Lock()

conn = sqlite3.connect(DB, check_same_thread=False)
conn.execute("CREATE TABLE IF NOT EXISTS connaissances_publiques (question TEXT PRIMARY KEY, reponse TEXT, source TEXT DEFAULT 'enfant')")
conn.execute("CREATE TABLE IF NOT EXISTS connaissances_privees (telephone TEXT NOT NULL, question TEXT NOT NULL, reponse TEXT, PRIMARY KEY (telephone, question))")
conn.execute("CREATE TABLE IF NOT EXISTS comptes (telephone TEXT PRIMARY KEY, premium INTEGER DEFAULT 0, quota INTEGER DEFAULT 0, bloque INTEGER DEFAULT 0, derniere_activite TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS avis (id INTEGER PRIMARY KEY AUTOINCREMENT, telephone TEXT, question TEXT, reponse TEXT, satisfait INTEGER, motif TEXT, commentaire TEXT, capture_nom TEXT, capture_b64 TEXT, cree_le TEXT, email_envoye INTEGER DEFAULT 0)")
conn.execute("CREATE TABLE IF NOT EXISTS lecons_parents (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, reponse_enfant TEXT, reponse_parent TEXT, parent TEXT, cree_le TEXT)")
conn.commit()
for col in ("ALTER TABLE comptes ADD COLUMN bloque INTEGER DEFAULT 0","ALTER TABLE comptes ADD COLUMN derniere_activite TEXT","ALTER TABLE connaissances_publiques ADD COLUMN source TEXT DEFAULT 'enfant'"):
    try: conn.execute(col); conn.commit()
    except: pass

_contextes={}; _VERROU_CONTEXTE=threading.Lock()
def _contexte(tel):
    k=tel or "anonyme"
    with _VERROU_CONTEXTE:
        if k not in _contextes: _contextes[k]={"sujet":None}
        return _contextes[k]

def nettoyer(q):
    q=q.lower(); q="".join(c for c in unicodedata.normalize("NFD", q) if unicodedata.category(c)!="Mn")
    q=re.sub(r"[^a-z0-9 ]"," ",q); return re.sub(r"\s+"," ",q).strip()

SALUTATIONS_RE=re.compile(r"^(?:bonjour|bonsoir|salut|coucou|hello|hey|yo)[\s!.,]*$",re.I)
REMERCIEMENTS_RE=re.compile(r"^(?:merci(?:\s+beaucoup|\s+bien)?|je te remercie)[\s!.,]*$",re.I)
AU_REVOIR_RE=re.compile(r"^(?:au revoir|a\s*\+|[àa]\s*bient[oô]t|bonne (?:journee|soiree)|bye)[\s!.,]*$",re.I)
_REP_SALUT=["Bonjour! Je suis ADRYNX, à votre service. Comment puis-je vous aider?","Salut! ADRYNX à l'écoute, que puis-je faire pour toi?"]
_REP_MERCI=["Avec plaisir!","De rien, n'hésite pas si tu as d'autres questions."]
_REP_AUREV=["Au revoir! À bientôt.","Bonne journée, à la prochaine!"]
def detecter_social(q):
    s=q.strip()
    if SALUTATIONS_RE.match(s): return random.choice(_REP_SALUT)
    if REMERCIEMENTS_RE.match(s): return random.choice(_REP_MERCI)
    if AU_REVOIR_RE.match(s): return random.choice(_REP_AUREV)
    return None

_EXCLUSIONS_TYPE=re.compile(r"\best\s+(?:un|une)\s+(?:roman|film|jeu vid[ée]o|album|chanson|s[ée]rie(?: t[ée]l[ée]vis[ée]e)?|personnage|manga|bande dessin[ée]e|nouvelle)\b",re.I)
SUPERLATIF_RE=re.compile(r"\b(?:le plus |la plus |les plus )(?:grand|petit|long|large|haut|peupl[ée]|important)e?s?\b",re.I)

def lire_connaissance(cle,tel):
    t=tel or "anonyme"
    with VERROU:
        r=conn.execute("SELECT reponse FROM connaissances_privees WHERE telephone=? AND question=?",(t,cle)).fetchone()
        if r: return r[0]
        r=conn.execute("SELECT reponse FROM connaissances_publiques WHERE question=?",(cle,)).fetchone()
    if r and _EXCLUSIONS_TYPE.search(r[0][:200]): return None
    return r[0] if r else None

def ecrire_privee(cle,rep,tel):
    t=tel or "anonyme"
    with VERROU: conn.execute("INSERT OR REPLACE INTO connaissances_privees (telephone,question,reponse) VALUES (?,?,?)",(t,cle,rep)); conn.commit()
def ecrire_publique(cle,rep,source="enfant"):
    with VERROU:
        try: conn.execute("INSERT OR REPLACE INTO connaissances_publiques (question,reponse,source) VALUES (?,?,?)",(cle,rep,source))
        except: conn.execute("INSERT OR REPLACE INTO connaissances_publiques (question,reponse) VALUES (?,?)",(cle,rep))
        conn.commit()
def ecrire_lecon(q,rep_enfant,rep_parent,parent):
    with VERROU: conn.execute("INSERT INTO lecons_parents (question,reponse_enfant,reponse_parent,parent,cree_le) VALUES (?,?,?,?,datetime('now'))",(q[:1000],rep_enfant[:2000],rep_parent[:2000],parent)); conn.commit()

def apprendre(q,tel):
    m=re.match(r"^\s*(?:retiens|apprends)\s*:?\s*(.+?)\s*=\s*(.+)$",q,re.I)
    if not m: return None
    ecrire_privee(nettoyer(m.group(1)),m.group(2).strip(),tel)
    return "C'est noté (pour toi uniquement)."

OPS={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Mod:operator.mod,ast.Pow:operator.pow,ast.USub:operator.neg,ast.UAdd:operator.pos}
MOTS_CALCUL={"combien","font","fait","calcule","calcul","resultat","de","est","egal","a","quel","quelle","le","la","donne","moi","cela","ca","sont"}
def _evaluer(n):
    if isinstance(n,ast.Expression): return _evaluer(n.body)
    if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)): return n.value
    if isinstance(n,ast.BinOp) and type(n.op) in OPS:
        a,b=_evaluer(n.left),_evaluer(n.right)
        if isinstance(n.op,ast.Pow) and abs(b)>100: raise ValueError("puissance trop grande")
        return OPS[type(n.op)](a,b)
    if isinstance(n,ast.UnaryOp) and type(n.op) in OPS: return OPS[type(n.op)](_evaluer(n.operand))
    raise ValueError("non autorisée")
def calculer(q):
    expr=q.lower().replace(",",".").replace("÷","/").replace("×","*")
    expr=re.sub(r"(?<=\d)\s*x\s*(?=\d)","*",expr)
    m=re.search(r"[\d(.][\d+\-*/%().\s]*[\d)]|\d",expr)
    if not m or not re.search(r"[+\-*/%]",m.group(0)): return None
    reste=nettoyer(expr[:m.start()]+" "+expr[m.end():])
    if any(w not in MOTS_CALCUL for w in reste.split()): return None
    try: res=_evaluer(ast.parse(m.group(0).strip(),mode="eval"))
    except ZeroDivisionError: return "Division par zéro impossible."
    except: return None
    if isinstance(res,float): res=int(res) if res.is_integer() else round(res,10)
    return str(res)

DEBUTS=re.compile(r"^(?:qui (?:est|etait|était|sont)|c'est qui|c'est quoi|qu'est[- ]ce (?:que|qu')\s*(?:c'est )?|que sais[- ]tu (?:de|sur)|parle[- ]moi (?:de|d')|dis[- ]moi qui est|comment s'appelle|quel est le nom (?:de|d')|quel(?:le)?s? (?:est|sont)|definition (?:de|d')|définition (?:de|d'))\s*(?:(?:l[ae]s?|un|une|des|du|de|d')\s*)?",re.I)
MOTS_PARASITES=re.compile(r"^(?:mais|donc|alors|bon|non)\s+",re.I)
MOT_ACTUEL=re.compile(r"\b(?:l'|le |la |les )?actuel(?:le)?s?\b\s*",re.I)
def extraire_sujet(q):
    b=q.strip().rstrip("?!. "); m=DEBUTS.match(b)
    if m and b[m.end():].strip(): return b[m.end():].strip()
    if 0 < len(b.split()) <=3: return b
    return None
def simplifier_pour_recherche(q):
    b=q.strip().rstrip("?!. "); prev=None
    while prev!=b:
        prev=b; b=MOTS_PARASITES.sub("",b); m=DEBUTS.match(b)
        if m and b[m.end():].strip(): b=b[m.end():].strip()
    b=MOT_ACTUEL.sub("",b).strip(); return b or q.strip().rstrip("?!. ")
def remplacer_pronoms(q,tel):
    s=_contexte(tel)["sujet"]
    if not s: return q
    q=re.sub(r"-\s*(?:il|elle)\b"," "+s,q,flags=re.I); return re.sub(r"\b(?:il|elle)\b",s,q,flags=re.I)

CONSEIL_RE=re.compile(r"\b(?:comment (?:devenir|etre) (?:bon|bonne|meilleur|meilleure)\b|comment progresser\b|comment m ameliorer\b|comment ameliorer\b|(?:astuce|astuces|conseil|conseils|methode|methodes) pour\b|je veux devenir (?:meilleur|meilleure|bon|bonne)\b)")
def demande_de_conseil(q): return bool(CONSEIL_RE.search(nettoyer(q)))
APPROFONDIR_RE=re.compile(r"\b(?:raconte\w*|racontez\w*|expliqu\w*\s+en\s+detail|l histoire de|quelles sont les etapes|en detail)\b")
def demande_approfondie(q): return bool(APPROFONDIR_RE.search(nettoyer(q)))

def rechercher_internet(question,approfondi=False):
    req=simplifier_pour_recherche(question); superlatif=bool(SUPERLATIF_RE.search(question))
    if not approfondi:
        try:
            r=requests.get("https://api.duckduckgo.com/",params={"q":req,"format":"json","no_html":"1","kl":"fr-fr"},headers=HEADERS,timeout=10)
            txt=r.json().get("AbstractText")
            if txt: return txt
        except: pass
    try:
        api="https://fr.wikipedia.org/w/api.php"; reqs=[req]
        if superlatif: reqs.insert(0,"liste "+req)
        cands=[]
        for sr in reqs:
            r=requests.get(api,params={"action":"query","format":"json","list":"search","srsearch":sr,"srlimit":3},headers=HEADERS,timeout=10)
            cands.extend(r.json()["query"]["search"])
        for cand in cands:
            r=requests.get(api,params={"action":"query","format":"json","prop":"extracts","exintro":0 if approfondi else 1,"explaintext":1,"redirects":1,"titles":cand["title"]},headers=HEADERS,timeout=10)
            for page in r.json()["query"]["pages"].values():
                ext=page.get("extract","")
                if len(ext)<=40: continue
                if _EXCLUSIONS_TYPE.search(ext[:200]): continue
                return ext[:6000 if approfondi else 3000]
    except: pass
    return None

# ========== PARENTS GARDIENS - PANTIN ==========
PROMPT_PARENT = """Tu es le parent gardien d'ADRYNX, une IA enfant. Ton rôle: corriger sa réponse si elle est hors-sujet, fausse ou maladroite.
Question: "{question}"
Réponse enfant: "{reponse_enfant}"
Tâche: Si réponse enfant adaptée, renvoie même réponse. Si hors-sujet ou bêtise, FOURNIS meilleure réponse courte (2-4 phrases), français simple. Réponse finale uniquement."""

def _demander_groq_parent(question, rep_enfant):
    cle=os.environ.get("GROQ_API_KEY")
    if not cle: return None
    try:
        prompt=PROMPT_PARENT.format(question=question,reponse_enfant=rep_enfant[:1000])
        r=requests.post("https://api.groq.com/openai/v1/chat/completions",headers={"Authorization":f"Bearer {cle}","Content-Type":"application/json"},json={"model":os.environ.get("ADRYNX_MODELE_GROQ","llama-3.3-70b-versatile"),"messages":[{"role":"system","content":"Tu es correcteur bienveillant. Réponds en français."},{"role":"user","content":prompt}],"max_tokens":400,"temperature":0.3},timeout=20)
        return r.json()["choices"][0]["message"]["content"].strip()
    except: return None

def _demander_hf_parent(question, rep_enfant):
    cle=os.environ.get("HF_TOKEN")
    if not cle: return None
    try:
        model=os.environ.get("ADRYNX_MODELE_HF","meta-llama/Llama-3.2-3B-Instruct")
        prompt=PROMPT_PARENT.format(question=question,reponse_enfant=rep_enfant[:1000])+"\nRéponse corrigée:"
        r=requests.post(f"https://api-inference.huggingface.co/models/{model}",headers={"Authorization":f"Bearer {cle}"},json={"inputs":prompt,"parameters":{"max_new_tokens":350,"temperature":0.4,"return_full_text":False}},timeout=30)
        data=r.json()
        if isinstance(data,list) and data and "generated_text" in data[0]: return data[0]["generated_text"].strip()
        if isinstance(data,dict) and "generated_text" in data: return data["generated_text"].strip()
        return None
    except: return None

def _demander_openrouter_parent(question, rep_enfant):
    cle=os.environ.get("OPENROUTER_API_KEY")
    if not cle: return None
    try:
        prompt=PROMPT_PARENT.format(question=question,reponse_enfant=rep_enfant[:1000])
        r=requests.post("https://openrouter.ai/api/v1/chat/completions",headers={"Authorization":f"Bearer {cle}","Content-Type":"application/json","HTTP-Referer":"https://adrynx-ai.onrender.com","X-Title":"ADRYNX"},json={"model":os.environ.get("ADRYNX_MODELE_OPENROUTER","meta-llama/llama-3.2-3b-instruct:free"),"messages":[{"role":"system","content":"Tu es parent gardien, corrige avec bienveillance en français."},{"role":"user","content":prompt}],"max_tokens":400,"temperature":0.3},timeout=25)
        return r.json()["choices"][0]["message"]["content"].strip()
    except: return None

def valider_avec_parents(question, reponse_enfant):
    if not reponse_enfant or len(reponse_enfant)<5: reponse_enfant="Je ne sais pas."
    reponses_parents=[]
    for nom,fn in [("groq",_demander_groq_parent),("hf",_demander_hf_parent),("openrouter",_demander_openrouter_parent)]:
        rep=fn(question,reponse_enfant)
        if rep and len(rep)>10:
            if nettoyer(rep)==nettoyer(reponse_enfant): continue
            reponses_parents.append((nom,rep))
            if len(rep)!=len(reponse_enfant) and "je ne sais pas" in reponse_enfant.lower(): break
    if not reponses_parents: return reponse_enfant, "enfant", False
    meilleur_nom, meilleure_rep = reponses_parents[0]
    try: ecrire_lecon(question, reponse_enfant, meilleure_rep, meilleur_nom)
    except: pass
    try: ecrire_publique(nettoyer(question), meilleure_rep, source=meilleur_nom)
    except: pass
    return meilleure_rep, meilleur_nom, True

def demander_ia_externe_direct(question):
    for fn in [_demander_groq_parent, _demander_hf_parent, _demander_openrouter_parent]:
        rep=fn(question,"Je ne sais pas.")
        if rep and len(rep)>10 and "je ne sais pas" not in rep.lower()[:50]: return rep
    return None

def lire_compte(tel):
    with VERROU: row=conn.execute("SELECT premium,quota FROM comptes WHERE telephone=?",(tel,)).fetchone()
    return {"premium":bool(row[0]),"quota":row[1]} if row else {"premium":False,"quota":0}
def activer_ou_recharger(tel,q):
    with VERROU: conn.execute("INSERT INTO comptes (telephone,premium,quota) VALUES (?,1,?) ON CONFLICT(telephone) DO UPDATE SET premium=1,quota=quota+excluded.quota",(tel,q)); conn.commit()
def desactiver_premium(tel):
    with VERROU: conn.execute("INSERT INTO comptes (telephone,premium,quota) VALUES (?,0,0) ON CONFLICT(telephone) DO UPDATE SET premium=0",(tel,)); conn.commit()
def consommer_quota(tel):
    with VERROU:
        row=conn.execute("SELECT premium,quota FROM comptes WHERE telephone=?",(tel,)).fetchone()
        if not row or not row[0] or row[1]<=0: return False
        conn.execute("UPDATE comptes SET quota=quota-1 WHERE telephone=?",(tel,)); conn.commit(); return True
def enregistrer_activite(tel):
    if not tel: return
    with VERROU: conn.execute("INSERT INTO comptes (telephone) VALUES (?) ON CONFLICT(telephone) DO NOTHING",(tel,)); conn.execute("UPDATE comptes SET derniere_activite=datetime('now') WHERE telephone=?",(tel,)); conn.commit()
def est_bloque(tel):
    if not tel: return False
    with VERROU: row=conn.execute("SELECT bloque FROM comptes WHERE telephone=?",(tel,)).fetchone()
    return bool(row and row[0])
def bloquer_utilisateur(tel):
    with VERROU: conn.execute("INSERT INTO comptes (telephone,bloque) VALUES (?,1) ON CONFLICT(telephone) DO UPDATE SET bloque=1",(tel,)); conn.commit()
def debloquer_utilisateur(tel):
    with VERROU: conn.execute("INSERT INTO comptes (telephone,bloque) VALUES (?,0) ON CONFLICT(telephone) DO UPDATE SET bloque=0",(tel,)); conn.commit()
def lister_comptes():
    with VERROU: rows=conn.execute("SELECT telephone,premium,quota,bloque,derniere_activite FROM comptes ORDER BY (derniere_activite IS NULL),derniere_activite DESC").fetchall()
    return [{"telephone":t,"premium":bool(p),"quota":q,"bloque":bool(b),"derniere_activite":v} for t,p,q,b,v in rows]
def compter_comptes():
    c=lister_comptes(); return {"total":len(c),"premium":sum(1 for x in c if x["premium"]),"bloques":sum(1 for x in c if x["bloque"])}
def verifier_secret_admin(s):
    sr=os.environ.get("ADRYNX_ADMIN_SECRET")
    if not sr or not s: return False
    return hmac.compare_digest(s.encode(),sr.encode())
ADMIN_RE=re.compile(r"^admin\s+(\S+)\s+(activer|desactiver|d[ée]sactiver|recharger|statut|bloquer|debloquer|d[ée]bloquer)\s+(\+?[\d\s]{6,})(?:\s+(\d+))?\s*$",re.I)
VIDER_CACHE_RE=re.compile(r"^admin\s+(\S+)\s+vider\s+cache\s*$",re.I)
STATS_RE=re.compile(r"^admin\s+(\S+)\s+stats\s*$",re.I)
LISTE_RE=re.compile(r"^admin\s+(\S+)\s+(?:liste|utilisateurs|users)\s*$",re.I)
def traiter_commande_admin(q):
    sr=os.environ.get("ADRYNX_ADMIN_SECRET")
    def inv(s):
        if not sr: return "Admin désactivé."
        if not hmac.compare_digest(s.encode(),sr.encode()): return "Code admin incorrect."
        return None
    m=VIDER_CACHE_RE.match(q.strip())
    if m:
        e=inv(m.group(1))
        if e: return e
        with VERROU: n=conn.execute("SELECT COUNT(*) FROM connaissances_publiques").fetchone()[0]; conn.execute("DELETE FROM connaissances_publiques"); conn.commit()
        return f"Cache vidé ({n}). Leçons conservées."
    m=STATS_RE.match(q.strip())
    if m:
        e=inv(m.group(1))
        if e: return e
        s=compter_comptes(); return f"{s['total']} users, {s['premium']} premium, {s['bloques']} bloqués."
    m=LISTE_RE.match(q.strip())
    if m:
        e=inv(m.group(1))
        if e: return e
        comptes=lister_comptes()
        if not comptes: return "Aucun utilisateur."
        lignes=[f"{c['telephone']} - prem:{'oui' if c['premium'] else 'non'}" for c in comptes]
        return "\n".join(lignes)
    m=ADMIN_RE.match(q.strip())
    if not m: return None
    sec,act,tel_brut,mont=m.groups(); e=inv(sec)
    if e: return e
    tel=re.sub(r"\s+","",tel_brut); act=act.lower().replace("é","e"); qdef=int(os.environ.get("ADRYNX_QUOTA_DEFAUT","50"))
    if act=="activer": activer_ou_recharger(tel,qdef); return f"Compte {tel} activé {qdef}."
    if act=="recharger": n=int(mont) if mont else qdef; activer_ou_recharger(tel,n); return f"{n} ajoutées à {tel}."
    if act=="desactiver": desactiver_premium(tel); return f"{tel} gratuit."
    if act=="statut": c=lire_compte(tel); return f"{tel}: premium={'oui' if c['premium'] else 'non'}, quota={c['quota']}"
    if act=="bloquer": bloquer_utilisateur(tel); return f"{tel} bloqué."
    if act=="debloquer": debloquer_utilisateur(tel); return f"{tel} débloqué."
    return None

def enregistrer_avis(tel,q,rep,sat,motif=None,com=None,cap_nom=None,cap_b64=None):
    if cap_b64 and len(cap_b64)>4000000: cap_b64,cap_nom=None,None
    with VERROU:
        cur=conn.execute("INSERT INTO avis (telephone,question,reponse,satisfait,motif,commentaire,capture_nom,capture_b64,cree_le) VALUES (?,?,?,?,?,?,?,?,datetime('now'))",(tel,(q or "")[:2000],(rep or "")[:4000],int(bool(sat)),motif,(com or "")[:3000],cap_nom,cap_b64)); conn.commit(); return cur.lastrowid
def lister_plaintes(lim=200):
    with VERROU: rows=conn.execute("SELECT id,telephone,question,reponse,motif,commentaire,cree_le,email_envoye,(capture_b64 IS NOT NULL) FROM avis WHERE satisfait=0 ORDER BY id DESC LIMIT?",(lim,)).fetchall()
    return [{"id":r[0],"telephone":r[1],"question":r[2],"reponse":r[3],"motif":r[4],"commentaire":r[5],"cree_le":r[6],"email_envoye":bool(r[7]),"a_capture":bool(r[8])} for r in rows]
def envoyer_email_plainte(avis_id):
    rk=os.environ.get("RESEND_API_KEY"); ef=os.environ.get("ADRYNX_EMAIL_FROM","ADRYNX <onboarding@resend.dev>"); ed=os.environ.get("ADRYNX_EMAIL_DEST") or os.environ.get("ADRYNX_EMAIL_DESTINATAIRE","adrynxai@gmail.com")
    with VERROU: row=conn.execute("SELECT telephone,question,reponse,motif,commentaire FROM avis WHERE id=?",(avis_id,)).fetchone()
    if not row: return False,"Plainte introuvable"
    tel,q,rep,motif,com=row; contenu=f"Tel:{tel}\nMotif:{motif}\nQ:{q}\nR:{rep}\nCom:{com}"
    if rk:
        try:
            r=requests.post("https://api.resend.com/emails",headers={"Authorization":f"Bearer {rk}","Content-Type":"application/json"},json={"from":ef,"to":[ed],"subject":f"[ADRYNX] Plainte #{avis_id}","text":contenu},timeout=15)
            if r.status_code in (200,201):
                with VERROU: conn.execute("UPDATE avis SET email_envoye=1 WHERE id=?",(avis_id,)); conn.commit()
                return True,"Envoyé via Resend"
        except: pass
    return False,"Email non configuré"

def resumer(txt,q,max_car=450,max_phr=3):
    txt=re.sub(r"\s+"," ",txt); txt=re.sub(r"\s*\((?:[^()]*prononc[^()]*)\)","",txt)
    phr=re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý])",txt.strip()); mots=set(nettoyer(q).split()); motif=None
    if mots & {"ne","nee","naissance"}: motif=re.compile(r"\bné(?:e)?\b|naissance",re.I)
    if motif:
        for p in phr:
            if motif.search(p): return p[:max_car]
    res=""
    for p in phr[:max_phr]:
        if res and len(res)+len(p)>max_car: break
        res=(res+" "+p).strip()
    return res[:max_car] if res else txt[:max_car]

def traiter_question(q, telephone=None):
    q=(q or "").strip()
    if not q: return "Pose-moi une question."
    if telephone:
        enregistrer_activite(telephone)
        if est_bloque(telephone): return "Ton accès a été suspendu."
    ctx=_contexte(telephone)
    rep=detecter_social(q)
    if rep: return rep
    rep=traiter_commande_admin(q)
    if rep: return rep
    rep=apprendre(q,telephone)
    if rep: return rep
    rep=calculer(q)
    if rep is not None: return rep
    if not ctx["sujet"] and re.search(r"\b(?:il|elle)\b",q,re.I):
        return "De qui parles-tu? Pose d'abord « qui est...? »."
    q_final=remplacer_pronoms(q,telephone)
    cle=nettoyer(q_final)
    rep=lire_connaissance(cle,telephone)
    if rep:
        if len(rep)>30 and random.random()<0.3:
            rep_f,parent,corr=valider_avec_parents(q_final,rep)
            if corr: return rep_f
        return rep
    sujet=extraire_sujet(q_final)
    conseil=demande_de_conseil(q_final)
    reponse_enfant=None
    if not conseil:
        approfondi=demande_approfondie(q_final)
        txt=rechercher_internet(q_final,approfondi=approfondi)
        if txt:
            reponse_enfant=resumer(txt,q_final,max_car=1800 if approfondi else 450,max_phr=10 if approfondi else 3)
            if sujet: ctx["sujet"]=sujet
    if reponse_enfant:
        reponse_finale, parent_used, a_corrige = valider_avec_parents(q_final, reponse_enfant)
        ecrire_publique(cle, reponse_finale, source=parent_used if a_corrige else "enfant")
        return reponse_finale
    has_key=bool(os.environ.get("GROQ_API_KEY") or os.environ.get("HF_TOKEN") or os.environ.get("OPENROUTER_API_KEY"))
    if (telephone and has_key and consommer_quota(telephone)) or conseil:
        rep_parent=demander_ia_externe_direct(q_final)
        if rep_parent:
            if sujet: ctx["sujet"]=sujet
            ecrire_publique(cle, rep_parent, source="parent_direct")
            return rep_parent
    if telephone and not lire_compte(telephone)["premium"]:
        return "Aucune info trouvée. Passe en premium pour que mes parents m'aident."
    return "Aucune information trouvée."

repondre=traiter_question
