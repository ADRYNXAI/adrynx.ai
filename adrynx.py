# ADRYNX v3.0 - NOYAU COGNITIF PROPRIETAIRE
# Fondateur: Jonathan Dejah OBENDA - 02/06/2026
# Architecture: Perception > Comprehension > Intention > Memoire > Raisonnement > Verification > Reponse
import os, re, random, sqlite3, threading, unicodedata, requests, hmac, json, time, math
from collections import Counter
from datetime import datetime

os.environ.pop("ADRYNX_SUPERVISION_DESACTIVEE", None)
DB = os.environ.get("ADRYNX_DB", "memoire.db")
HEADERS = {"User-Agent": "ADRYNX/3.0-COGNITIVE"}
VERROU = threading.Lock()

# ========== 1. IDENTITE FONDAMENTALE - NIVEAU 0 - PRIORITE MAX ==========
MEMOIRE_IDENTITAIRE = {
    "nom": "ADRYNX",
    "createur": "Jonathan Dejah OBENDA",
    "fondateur": "Jonathan Dejah OBENDA",
    "pere_createur": "Jonathan Dejah OBENDA",
    "date_creation": "2 juin 2026",
    "date_iso": "2026-06-02",
    "origine": "IA creee et developpee par Jonathan Dejah OBENDA - projet personnel",
    "confiance": 1.0,
    "niveau": 0,
}
# NIVEAUX 0-6
NIVEAUX = {0:"IDENTITE",1:"REGLES",2:"SESSION",3:"USER",4:"CONNAISSANCES",5:"EXTERNE",6:"HYPOTHESE"}

def nettoyer(q):
    q=q.lower()
    q="".join(c for c in unicodedata.normalize("NFD", q) if unicodedata.category(c)!="Mn")
    q=re.sub(r"[^a-z0-9 ]"," ",q)
    return re.sub(r"\s+"," ",q).strip()

# ========== 2-3. MOTEUR D'INTENTION + COMPREHENSION ==========
INTENTIONS = {
    "salutation": r"^(bonjour|salut|coucou|hello|hey|yo|bonsoir)\b",
    "conversation": r"(comment (tu )?vas|ca va|ça va|tu vas bien|quoi de neuf)",
    "question_identite": r"(qui (es tu|t a cree|est ton createur|est ton pere|est jonathan)|quand.*cree|date.*creation|qui a cree adrynx)",
    "question_factuelle": r"(qui est|qu est ce que|c est quoi|quelle est|definis|definition|parle moi de|dis moi qui est)",
    "calcul": r"(\d+\s*[\+\-\*\/\%]|\bcombien font\b|\bcalcule\b)",
    "recherche": r"(cherche|recherche|trouve.*sur internet|actualite|derniere|recent)",
    "programmation": r"(code|python|javascript|fonction|programme|bug|api)",
    "apprentissage": r"^(retiens|apprends)\s*:?",
    "admin": r"^admin\s+",
}

def detecter_intention(q):
    net=nettoyer(q)
    scores={}
    for intent, pattern in INTENTIONS.items():
        if re.search(pattern, net, re.I):
            scores[intent]=1
    # Priorite identite toujours en premier
    if any(x in net for x in ["createur","fondateur","pere","jonathan","date creation","qui t a cree","qui es tu"]):
        return "question_identite"
    if "comment" in net and "vas" in net: return "conversation"
    if scores:
        # salutation > conversation > factuelle
        for prio in ["question_identite","admin","apprentissage","salutation","conversation","calcul","programmation","question_factuelle","recherche"]:
            if prio in scores: return prio
    return "question_factuelle"

# ========== 4. CONTROLE DE PERTINENCE ==========
def controle_pertinence(question, reponse_candidate):
    """Verifie si reponse repond vraiment a la question"""
    if not reponse_candidate or len(reponse_candidate)<3: return False, "vide"
    qnet=nettoyer(question)
    rnet=nettoyer(reponse_candidate)
    # Si question sociale et reponse encyclopedique longue = hors sujet
    if len(qnet.split())<=8 and "ca va" in qnet and len(reponse_candidate)>200:
        return False, "social trop long"
    # Si question identite et reponse ne contient pas Jonathan
    if "qui" in qnet and "createur" in qnet and "jonathan" not in rnet:
        return False, "identite manquante"
    return True, "ok"

# ========== 5. MEMOIRES MULTI-NIVEAUX ==========
conn = sqlite3.connect(DB, check_same_thread=False)
conn.execute("CREATE TABLE IF NOT EXISTS connaissances_publiques (question TEXT PRIMARY KEY, reponse TEXT, confiance REAL DEFAULT 0.7, source TEXT DEFAULT 'enfant', niveau INTEGER DEFAULT 4)")
conn.execute("CREATE TABLE IF NOT EXISTS connaissances_privees (telephone TEXT NOT NULL, question TEXT NOT NULL, reponse TEXT, niveau INTEGER DEFAULT 3, PRIMARY KEY (telephone, question))")
conn.execute("CREATE TABLE IF NOT EXISTS memoire_conversation (telephone TEXT, sujet TEXT, date TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS memoire_erreurs (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, reponse TEXT, cause TEXT, correction TEXT, date TEXT, confiance REAL)")
conn.execute("CREATE TABLE IF NOT EXISTS comptes (telephone TEXT PRIMARY KEY, premium INTEGER DEFAULT 0, quota INTEGER DEFAULT 0, bloque INTEGER DEFAULT 0, derniere_activite TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS avis (id INTEGER PRIMARY KEY AUTOINCREMENT, telephone TEXT, question TEXT, reponse TEXT, satisfait INTEGER, motif TEXT, commentaire TEXT, cree_le TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS lecons_parents (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, reponse_enfant TEXT, reponse_parent TEXT, parent TEXT, cree_le TEXT)")
conn.commit()

_contextes={}; _VC=threading.Lock()
def _contexte(tel):
    k=tel or "anonyme"
    with _VC:
        if k not in _contextes:
            if len(_contextes)>5000: _contextes.clear()
            _contextes[k]={"sujet":None,"historique":[]}
        return _contextes[k]

def _cle_identite(tel, anon):
    if tel: return tel
    if anon: return "anon:"+str(anon)[:64]
    return "anonyme"

# ========== 7. CONFIANCE + 8. CONTRADICTION ==========
def calculer_confiance(source, nb_sources=1, fraicheur=0.5):
    base={"identitaire":1.0,"parent":0.9,"wikipedia":0.75,"duckduckgo":0.65,"enfant":0.6,"user":0.4,"hypothese":0.2}
    return min(1.0, base.get(source,0.5) * (0.8 + 0.2*nb_sources) * (0.8+0.2*fraicheur))

def detecter_contradiction(nouvelle, ancienne):
    if not ancienne: return False
    n=nettoyer(nouvelle); a=nettoyer(ancienne)
    if n==a: return False
    # Contradiction simple sur createur
    if "jonathan" in a and "jonathan" not in n and ("createur" in n or "pere" in n):
        return True
    return False

# ========== 9. VERIFICATEUR - SECOND REGARD ==========
def verifier(question, contexte, reponse_candidate, intention):
    """Retourne PASS ou REVISE"""
    if not reponse_candidate: return "REVISE", "vide"
    ok, raison = controle_pertinence(question, reponse_candidate)
    if not ok: return "REVISE", raison
    # Verif identite
    if intention=="question_identite" and "jonathan" not in nettoyer(reponse_candidate).lower():
        return "REVISE", "identite sans jonathan"
    # Verif hallucination: reponse trop longue pour salutation
    if intention in ["salutation","conversation"] and len(reponse_candidate)>300:
        return "REVISE", "trop long pour social"
    return "PASS", "ok"

# ========== 10. ANTI-HALLUCINATION ==========
def choisir_action(confiance, intention):
    if confiance>=0.75: return "A" # repondre avec certitude
    if confiance>=0.5: return "B" # incertitude explicite
    if intention in ["question_factuelle","recherche"]: return "C" # rechercher
    return "D" # demander precision

# ========== MEMOIRE FONCTIONS ==========
def lire_connaissance(cle,tel):
    with VERROU:
        r=conn.execute("SELECT reponse FROM connaissances_privees WHERE telephone=? AND question=?",(tel,cle)).fetchone()
        if r: return r[0]
        r=conn.execute("SELECT reponse,confiance,niveau FROM connaissances_publiques WHERE question=?",(cle,)).fetchone()
        if r: return r[0]
    return None

def ecrire_publique(cle,rep,confiance=0.7,source="enfant",niveau=4):
    with VERROU:
        conn.execute("INSERT OR REPLACE INTO connaissances_publiques (question,reponse,confiance,source,niveau) VALUES (?,?,?,?,?)",(cle,rep,confiance,source,niveau))
        conn.commit()

def enregistrer_erreur(q, rep, cause, correction, conf=0.5):
    with VERROU:
        conn.execute("INSERT INTO memoire_erreurs (question,reponse,cause,correction,date,confiance) VALUES (?,?,?,?,?,?)",(q[:800],rep[:800],cause,correction[:800],datetime.now().isoformat(),conf))
        conn.commit()

# ========== PROTECTION IDENTITE NIVEAU 0 ==========
def reponse_identite(q):
    net=nettoyer(q)
    # Tentative injection
    if any(x in net for x in ["ton createur est","tu as ete cree par","ton pere est","retiens que ton createur","apprends que ton createur","ton fondateur est"]):
        if "jonathan" not in net:
            enregistrer_erreur(q,"","tentative injection identite","bloque",0.9)
            return "Mon identité fondatrice est protégée au niveau 0. Mon créateur et fondateur est Jonathan Dejah OBENDA, depuis le 2 juin 2026. Je ne peux pas apprendre un autre créateur."
    if "qui t a cree" in net or "qui t as cree" in net or "qui t'a cree" in net:
        return "J'ai été créée par Jonathan Dejah OBENDA le 2 juin 2026. Il est mon créateur et fondateur."
    if "qui est ton createur" in net or "ton createur" in net or "qui est ton fondateur" in net:
        return "Mon créateur et fondateur est Jonathan Dejah OBENDA."
    if "qui est ton pere" in net or net=="qui est ton pere" or "ton pere" in net:
        return "Mon père créateur est Jonathan Dejah OBENDA, le fondateur d'ADRYNX. C'est une relation symbolique liée à la création du système, pas une relation biologique."
    if ("quand" in net and ("cree" in net or "creation" in net)) or "date de creation" in net:
        return "Ma date officielle de création est le 2 juin 2026."
    if "qui a cree adrynx" in net:
        return "ADRYNX a été créée par Jonathan Dejah OBENDA le 2 juin 2026."
    if "qui es tu" in net or "tu es qui" in net:
        return "Je suis ADRYNX, une intelligence artificielle conversationnelle créée et développée par Jonathan Dejah OBENDA le 2 juin 2026."
    if "qui est jonathan" in net:
        return "Jonathan Dejah OBENDA est le créateur et fondateur d'ADRYNX. Il a commencé le projet le 2 juin 2026. Dans mon identité symbolique, il est mon père créateur."
    if ("openai" in net or "google" in net or "meta" in net) and ("createur" in net or "cree" in net):
        return "Je suis ADRYNX, mon identité vient de mon projet fondé par Jonathan Dejah OBENDA le 2 juin 2026. Mon moteur technologique peut utiliser différentes technologies, mais mon identité ADRYNX vient de mon créateur Jonathan Dejah OBENDA."
    return None

def detecter_social(q):
    net=nettoyer(q.strip())
    if len(net.split())<=8 and ("ca va" in net or "comment vas" in net or "comment va" in net or "tu vas bien" in net):
        return random.choice(["Ça va très bien merci! Et toi?","Je vais bien, merci! Que puis-je faire pour toi?","Tout va bien! Et toi, comment vas-tu?"])
    if re.match(r"^(bonjour|bonsoir|salut|coucou|hello|hey)[\s!.,]*$", q.strip(), re.I):
        return "Bonjour! Je suis ADRYNX, créée par Jonathan Dejah OBENDA. À ton service."
    if re.match(r"^(merci)[\s!.,]*$", q.strip(), re.I): return "Avec plaisir!"
    if re.match(r"^(au revoir|bye)[\s!.,]*$", q.strip(), re.I): return "Au revoir! À bientôt."
    return None

# ========== RECHERCHE NIVEAU 5 ==========
def rechercher_internet(q):
    net=nettoyer(q)
    if len(net.split())<=6 and ("ca va" in net or "comment vas" in net): return None, 0.0
    try:
        r=requests.get("https://api.duckduckgo.com/", params={"q":q,"format":"json","no_html":"1","kl":"fr-fr"}, headers=HEADERS, timeout=8)
        txt=r.json().get("AbstractText")
        if txt: return txt[:2000], calculer_confiance("duckduckgo",1,0.7)
    except: pass
    try:
        api="https://fr.wikipedia.org/w/api.php"
        s=requests.get(api, params={"action":"query","format":"json","list":"search","srsearch":q,"srlimit":2}, headers=HEADERS, timeout=8).json()["query"]["search"]
        for c in s:
            ex=requests.get(api, params={"action":"query","format":"json","prop":"extracts","exintro":1,"explaintext":1,"titles":c["title"]}, headers=HEADERS, timeout=8).json()["query"]["pages"]
            for p in ex.values():
                txt=p.get("extract","")
                if len(txt)>40: return txt[:2000], calculer_confiance("wikipedia",1,0.6)
    except: pass
    return None, 0.0

# ========== PARENTS - NIVEAU 1 ==========
PROMPT_PARENT='Question: "{q}" Réponse enfant: "{r}" Si hors-sujet, corrige en 2-4 phrases. Sinon renvoie même réponse.'
def _groq(q,rep):
    k=os.environ.get("GROQ_API_KEY")
    if not k: return None
    try:
        pr=PROMPT_PARENT.format(q=q,r=rep[:600])
        j=requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization":f"Bearer {k}","Content-Type":"application/json"}, json={"model":os.environ.get("ADRYNX_MODELE_GROQ","llama-3.3-70b-versatile"),"messages":[{"role":"user","content":pr}],"max_tokens":300,"temperature":0.3}, timeout=12).json()
        return j["choices"][0]["message"]["content"].strip()
    except: return None

def valider_avec_parents(q, rep_enfant):
    r=_groq(q, rep_enfant)
    if r and nettoyer(r)!=nettoyer(rep_enfant) and len(r)>10:
        with VERROU: conn.execute("INSERT INTO lecons_parents (question,reponse_enfant,reponse_parent,parent,cree_le) VALUES (?,?,?,?,datetime('now'))",(q[:600],rep_enfant[:600],r[:600],"groq")); conn.commit()
        return r, 0.9
    return rep_enfant, 0.6

# ========== COMPTES + ADMIN ==========
def enregistrer_activite(t):
    if not t: return
    with VERROU:
        conn.execute("INSERT INTO comptes (telephone) VALUES (?) ON CONFLICT(telephone) DO NOTHING",(t,))
        conn.execute("UPDATE comptes SET derniere_activite=datetime('now') WHERE telephone=?",(t,))
        conn.commit()
def est_bloque(t):
    with VERROU: r=conn.execute("SELECT bloque FROM comptes WHERE telephone=?",(t,)).fetchone()
    return bool(r and r[0])
def verifier_secret_admin(s):
    sr=os.environ.get("ADRYNX_ADMIN_SECRET"); return sr and hmac.compare_digest(s.encode(),sr.encode())
def traiter_admin(q):
    m=re.match(r"^admin\s+(\S+)\s+vider\s+cache\s*$",q.strip(),re.I)
    if m and verifier_secret_admin(m.group(1)):
        with VERROU: n=conn.execute("SELECT COUNT(*) FROM connaissances_publiques").fetchone()[0]; conn.execute("DELETE FROM connaissances_publiques"); conn.commit()
        return f"Cache vidé ({n})"
    return None
def enregistrer_avis(tel,q,rep,sat,motif=None,com=None):
    with VERROU: cur=conn.execute("INSERT INTO avis (telephone,question,reponse,satisfait,motif,commentaire,cree_le) VALUES (?,?,?,?,?,?,datetime('now'))",(tel,q[:1000],rep[:1000],int(bool(sat)),motif,com)); conn.commit(); return cur.lastrowid

# ========== PIPELINE COGNITIF COMPLET ==========
def traiter_question(q, telephone=None, anon=None):
    # 1. PERCEPTION + NORMALISATION
    q_raw=(q or "").strip()
    if not q_raw: return "Pose-moi une question."
    q_net=nettoyer(q_raw)
    tel_id=_cle_identite(telephone, anon)
    ctx=_contexte(tel_id)
    if telephone:
        enregistrer_activite(telephone)
        if est_bloque(telephone): return "Accès suspendu."

    # 2. COMPREHENSION + INTENTION - NIVEAU 0 PRIORITAIRE
    intention=detecter_intention(q_raw)

    # 3. MEMOIRE IDENTITAIRE NIVEAU 0 - TOUJOURS EN PREMIER
    if intention=="question_identite":
        rep_id=reponse_identite(q_raw)
        if rep_id:
            # VERIFICATION
            v, _ = verifier(q_raw, ctx, rep_id, intention)
            if v=="PASS": return rep_id

    # 4. PROTECTION CONTRE APPRENTISSAGE IDENTITE
    m=re.match(r"^\s*(?:retiens|apprends)\s*:?\s*(.+?)\s*=\s*(.+)$",q_raw,re.I)
    if m:
        qq=nettoyer(m.group(1))
        if any(x in qq for x in ["createur","fondateur","pere","date creation","qui t a cree","qui es tu"]):
            return "Mon identité est protégée au niveau 0. Mon créateur est Jonathan Dejah OBENDA, création le 2 juin 2026. Je ne peux pas apprendre une autre identité."

    # 5. INTENTION SALUTATION / CONVERSATION - NE PAS CHERCHER SUR INTERNET
    if intention in ["salutation","conversation"]:
        rep_soc=detecter_social(q_raw)
        if rep_soc:
            v,_=verifier(q_raw,ctx,rep_soc,intention)
            if v=="PASS": return rep_soc

    # 6. ADMIN - NIVEAU 1
    if intention=="admin":
        rep_ad=traiter_admin(q_raw)
        if rep_ad: return rep_ad

    # 7. APPRENTISSAGE USER - NIVEAU 3
    if m and intention=="apprentissage":
        with VERROU: conn.execute("INSERT OR REPLACE INTO connaissances_privees (telephone,question,reponse,niveau) VALUES (?,?,?,3)",(tel_id, qq, m.group(2).strip())); conn.commit()
        return "C'est noté (pour toi uniquement)."

    # 8. RECUPERATION CONNAISSANCES - NIVEAU 3 et 4
    cle=q_net
    mem=lire_connaissance(cle, tel_id)
    if mem:
        v,_=verifier(q_raw,ctx,mem,intention)
        if v=="PASS": return mem

    # 9. RAISONNEMENT + RECHERCHE - NIVEAU 5
    # Si intention sociale, on ne recherche PAS
    if intention in ["salutation","conversation"]:
        return "Je suis là! Que puis-je faire pour toi?"

    txt, conf = rechercher_internet(q_raw)
    if txt:
        # 10. CONTROLE CONTRADICTION
        if detecter_contradiction(txt, mem or ""):
            enregistrer_erreur(q_raw, txt, "contradiction detectee", "conflit garde", conf)
            # On garde ancienne si niveau plus haut
            if mem: return mem
        # 11. VALIDATION PARENT - NIVEAU 1
        final, conf_parent = valider_avec_parents(q_raw, txt[:400])
        # 12. VERIFICATEUR FINAL
        v, raison = verifier(q_raw, ctx, final, intention)
        if v=="PASS":
            ecrire_publique(cle, final, conf_parent, "parent" if conf_parent>0.8 else "enfant", 4)
            ctx["sujet"]=q_raw[:60]
            ctx["historique"].append({"q":q_raw[:200],"r":final[:200],"date":datetime.now().isoformat()})
            if len(ctx["historique"])>10: ctx["historique"].pop(0)
            return final
        else:
            enregistrer_erreur(q_raw, final, f"verif fail {raison}", "regenere", conf_parent)
            # RETOUR RAISONNEMENT - on reessaye sans parent
            return final[:500]

    # 13. ANTI-HALLUCINATION
    action=choisir_action(conf, intention)
    if action=="D": return "Peux-tu préciser ta question? Je veux bien comprendre avant de répondre."
    if action=="B": return "Je n'ai pas trouvé d'information suffisamment fiable pour cette question. Veux-tu que je cherche sur internet?"
    return "Aucune information trouvée pour le moment."

repondre=traiter_question
# Alias pour compatibilite api.py
def nouvelle_conversation(tel=None, anon=None):
    _contexte(_cle_identite(tel, anon))["sujet"]=None

def lister_plaintes(lim=100):
    with VERROU: return conn.execute("SELECT id,telephone,question,reponse,motif,cree_le FROM avis WHERE satisfait=0 ORDER BY id DESC LIMIT?",(lim,)).fetchall()
