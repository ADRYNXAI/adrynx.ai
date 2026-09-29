# ADRYNX v2.5 PANTIN PRO - FIX HORS-SUJET
import os, re, random, sqlite3, threading, unicodedata, requests, ast, operator, math, hmac, base64
from collections import Counter

os.environ.pop("ADRYNX_SUPERVISION_DESACTIVEE", None) # FORCE parents actifs

DB = os.environ.get("ADRYNX_DB", "memoire.db")
HEADERS = {"User-Agent": "ADRYNX/2.5"}
VERROU = threading.Lock()
conn = sqlite3.connect(DB, check_same_thread=False)
conn.execute("CREATE TABLE IF NOT EXISTS connaissances_publiques (question TEXT PRIMARY KEY, reponse TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS connaissances_privees (telephone TEXT NOT NULL, question TEXT NOT NULL, reponse TEXT, PRIMARY KEY (telephone, question))")
conn.execute("CREATE TABLE IF NOT EXISTS comptes (telephone TEXT PRIMARY KEY, premium INTEGER DEFAULT 0, quota INTEGER DEFAULT 0, bloque INTEGER DEFAULT 0, derniere_activite TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS avis (id INTEGER PRIMARY KEY AUTOINCREMENT, telephone TEXT, question TEXT, reponse TEXT, satisfait INTEGER, motif TEXT, commentaire TEXT, cree_le TEXT, email_envoye INTEGER DEFAULT 0)")
conn.execute("CREATE TABLE IF NOT EXISTS corrections (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, reponse TEXT, type TEXT, cree_le TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS lecons_parents (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, reponse_enfant TEXT, reponse_parent TEXT, parent TEXT, cree_le TEXT)")
conn.commit()

_contextes={}; _VC=threading.Lock()
def _contexte(t):
    k=t or "anonyme"
    with _VC:
        if k not in _contextes: _contextes[k]={"sujet":None}
        return _contextes[k]
def _cle(t,a): return t or ("anon:"+str(a)[:64] if a else None)
def nettoyer(q):
    q=q.lower(); q="".join(c for c in unicodedata.normalize("NFD", q) if unicodedata.category(c)!="Mn")
    q=re.sub(r"[^a-z0-9 ]"," ",q); return re.sub(r"\s+"," ",q).strip()

# --- SOCIAL CORRIGE ---
def detecter_social(q):
    net=nettoyer(q.strip())
    if len(net.split())<=8 and ("ca va" in net or "comment vas" in net or "comment va" in net or "tu vas bien" in net):
        return random.choice(["Ça va très bien merci! Et toi?","Je vais bien! Que puis-je faire pour toi?"])
    if re.match(r"^(bonjour|salut|coucou|hello|hey)[\s!.,]*$", q.strip(), re.I): return "Bonjour! Je suis ADRYNX, à ton service."
    if re.match(r"^(merci|je te remercie)[\s!.,]*$", q.strip(), re.I): return "Avec plaisir!"
    if re.match(r"^(au revoir|bye)[\s!.,]*$", q.strip(), re.I): return "Au revoir!"
    return None

def lire_connaissance(cle,tel):
    t=tel or "anonyme"
    with VERROU:
        r=conn.execute("SELECT reponse FROM connaissances_privees WHERE telephone=? AND question=?",(t,cle)).fetchone()
        if r: return r[0]
        r=conn.execute("SELECT reponse FROM connaissances_publiques WHERE question=?",(cle,)).fetchone()
        return r[0] if r else None
def ecrire_publique(cle,rep):
    with VERROU: conn.execute("INSERT OR REPLACE INTO connaissances_publiques (question,reponse) VALUES (?,?)",(cle,rep)); conn.commit()
def ecrire_privee(cle,rep,tel):
    with VERROU: conn.execute("INSERT OR REPLACE INTO connaissances_privees (telephone,question,reponse) VALUES (?,?,?)",(tel or "anonyme",cle,rep)); conn.commit()

# --- PARENTS GARDIENS ---
PROMPT='Question: "{q}" Réponse enfant: "{r}" Si hors-sujet, donne meilleure réponse courte 2-4 phrases français. Sinon renvoie même réponse. Réponse finale uniquement.'
def _groq(q,rep):
    k=os.environ.get("GROQ_API_KEY")
    if not k: return None
    try:
        pr=PROMPT.format(q=q,r=rep[:800])
        j=requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization":f"Bearer {k}","Content-Type":"application/json"}, json={"model":os.environ.get("ADRYNX_MODELE_GROQ","llama-3.3-70b-versatile"),"messages":[{"role":"user","content":pr}],"max_tokens":350,"temperature":0.3}, timeout=15).json()
        return j["choices"][0]["message"]["content"].strip()
    except: return None
def _openrouter(q,rep):
    k=os.environ.get("OPENROUTER_API_KEY")
    if not k: return None
    try:
        pr=PROMPT.format(q=q,r=rep[:800])
        j=requests.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization":f"Bearer {k}","Content-Type":"application/json"}, json={"model":"meta-llama/llama-3.2-3b-instruct:free","messages":[{"role":"user","content":pr}],"max_tokens":350}, timeout=15).json()
        return j["choices"][0]["message"]["content"].strip()
    except: return None
def valider(q,rep_enfant):
    if not rep_enfant: rep_enfant="Je ne sais pas."
    for fn in (_groq,_openrouter):
        r=fn(q,rep_enfant)
        if r and nettoyer(r)!=nettoyer(rep_enfant) and len(r)>10:
            with VERROU: conn.execute("INSERT INTO lecons_parents (question,reponse_enfant,reponse_parent,parent,cree_le) VALUES (?,?,?,?,datetime('now'))",(q[:800],rep_enfant[:800],r[:800],"groq")); conn.commit()
            return r
    return rep_enfant

# --- INTERNET (bloque si social) ---
def rechercher_internet(q):
    net=nettoyer(q)
    if len(net.split())<=8 and ("ca va" in net or "comment vas" in net): return None
    try:
        r=requests.get("https://api.duckduckgo.com/", params={"q":q,"format":"json","no_html":"1","kl":"fr-fr"}, headers=HEADERS, timeout=8)
        txt=r.json().get("AbstractText")
        if txt: return txt[:2000]
    except: pass
    try:
        api="https://fr.wikipedia.org/w/api.php"
        s=requests.get(api, params={"action":"query","format":"json","list":"search","srsearch":q,"srlimit":2}, headers=HEADERS, timeout=8).json()["query"]["search"]
        for c in s:
            ex=requests.get(api, params={"action":"query","format":"json","prop":"extracts","exintro":1,"explaintext":1,"titles":c["title"]}, headers=HEADERS, timeout=8).json()["query"]["pages"]
            for p in ex.values():
                if len(p.get("extract",""))>40: return p["extract"][:2000]
    except: pass
    return None

# --- COMPTES ---
def lire_compte(t):
    with VERROU: r=conn.execute("SELECT premium,quota FROM comptes WHERE telephone=?",(t,)).fetchone()
    return {"premium":bool(r[0]),"quota":r[1]} if r else {"premium":False,"quota":0}
def est_bloque(t):
    with VERROU: r=conn.execute("SELECT bloque FROM comptes WHERE telephone=?",(t,)).fetchone()
    return bool(r and r[0])
def enregistrer_activite(t):
    if not t: return
    with VERROU: conn.execute("INSERT INTO comptes (telephone) VALUES (?) ON CONFLICT(telephone) DO NOTHING",(t,)); conn.execute("UPDATE comptes SET derniere_activite=datetime('now') WHERE telephone=?",(t,)); conn.commit()
def verifier_secret_admin(s):
    sr=os.environ.get("ADRYNX_ADMIN_SECRET"); return sr and hmac.compare_digest(s.encode(),sr.encode())
def traiter_admin(q):
    m=re.match(r"^admin\s+(\S+)\s+vider\s+cache\s*$",q.strip(),re.I)
    if m and verifier_secret_admin(m.group(1)):
        with VERROU: n=conn.execute("SELECT COUNT(*) FROM connaissances_publiques").fetchone()[0]; conn.execute("DELETE FROM connaissances_publiques"); conn.commit()
        return f"Cache vidé ({n})"
    return None
def enregistrer_avis(tel,q,rep,sat,motif=None,com=None,cap_nom=None,cap_b64=None):
    with VERROU: cur=conn.execute("INSERT INTO avis (telephone,question,reponse,satisfait,motif,commentaire,cree_le) VALUES (?,?,?,?,?,?,datetime('now'))",(tel,q[:1500],rep[:2000],int(bool(sat)),motif,com)); conn.commit(); return cur.lastrowid
def lister_plaintes(lim=50):
    with VERROU: rows=conn.execute("SELECT id,telephone,question,reponse,motif,cree_le FROM avis WHERE satisfait=0 ORDER BY id DESC LIMIT?",(lim,)).fetchall()
    return rows

# --- ORCHESTRATEUR ---
def traiter_question(q, telephone=None, anon=None):
    q=(q or "").strip()
    if not q: return "Pose-moi une question."
    if telephone:
        enregistrer_activite(telephone)
        if est_bloque(telephone): return "Accès suspendu."
    # 0 SOCIAL ABSOLU
    r=detecter_social(q)
    if r: return r
    r=traiter_admin(q)
    if r: return r
    cle=nettoyer(q)
    mem=lire_connaissance(cle, telephone or anon or "anonyme")
    if mem: return mem
    # ENFANT CHERCHE
    txt=rechercher_internet(q)
    if txt:
        # PARENT VALIDE
        final=valider(q, txt[:400])
        ecrire_publique(cle, final)
        _contexte(_cle(telephone,anon))["sujet"]=q[:50]
        return final
    return "Aucune info trouvée. Passe en premium pour que mes parents m'aident."
repondre=traiter_question
