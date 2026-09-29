# ADRYNX v4.0.2 FIX - PLATEFORME INTERACTIVE - Jonathan Dejah OBENDA 02/06/2026
import os, re, sqlite3, threading, unicodedata, requests, hmac, json, uuid
from datetime import datetime
from enum import Enum

os.environ.pop("ADRYNX_SUPERVISION_DESACTIVEE", None)
DB = os.environ.get("ADRYNX_DB", "memoire.db")
HEADERS = {"User-Agent": "ADRYNX/4.0-PLATFORM"}
VERROU = threading.Lock()

MEMOIRE_IDENTITAIRE = {
    "nom": "ADRYNX", "createur": "Jonathan Dejah OBENDA",
    "fondateur": "Jonathan Dejah OBENDA", "pere_createur": "Jonathan Dejah OBENDA",
    "date_creation": "2 juin 2026", "date_iso": "2026-06-02",
    "vision": "Environnement numerique interactif",
    "formule": "IDENTITE+UTILISATEUR+CONTEXTE+IA+DONNEES+SERVICES+EVENEMENTS+INTERFACE+SECURITE+APPRENTISSAGE+OBSERVABILITE",
    "confiance": 1.0, "niveau": 0,
}

def nettoyer(q):
    q = q.lower()
    q = "".join(c for c in unicodedata.normalize("NFD", q) if unicodedata.category(c)!= "Mn")
    q = re.sub(r"[^a-z0-9 ]", " ", q)
    return re.sub(r"\s+", " ", q).strip()

class EventBus:
    def __init__(self):
        self._listeners = {}
        self._lock = threading.Lock()

    def on(self, event, fn):
        with self._lock:
            self._listeners.setdefault(event, []).append(fn)

    def emit(self, event, payload=None):
        payload = payload or {}
        payload["event"] = event
        payload["timestamp"] = datetime.now().isoformat()
        try:
            with VERROU:
                conn.execute("INSERT INTO events_log (id, type, payload, created_at) VALUES (?,?,?,?)",
                    (str(uuid.uuid4())[:8], event, json.dumps(payload, ensure_ascii=False)[:2000], datetime.now().isoformat()))
                conn.commit()
        except:
            pass
        with self._lock:
            for fn in self._listeners.get(event, []):
                try:
                    fn(payload)
                except:
                    pass
        return payload

BUS = EventBus()

# DB - SOURCE DE VERITE
conn = sqlite3.connect(DB, check_same_thread=False)
conn.execute("CREATE TABLE IF NOT EXISTS connaissances_publiques (question TEXT PRIMARY KEY, reponse TEXT, confiance REAL DEFAULT 0.7, source TEXT DEFAULT 'enfant', niveau INTEGER DEFAULT 4)")
conn.execute("CREATE TABLE IF NOT EXISTS connaissances_privees (telephone TEXT NOT NULL, question TEXT NOT NULL, reponse TEXT, niveau INTEGER DEFAULT 3, PRIMARY KEY (telephone, question))")
conn.execute("CREATE TABLE IF NOT EXISTS comptes (telephone TEXT PRIMARY KEY, premium INTEGER DEFAULT 0, quota INTEGER DEFAULT 0, bloque INTEGER DEFAULT 0, derniere_activite TEXT, profil_json TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS avis (id INTEGER PRIMARY KEY AUTOINCREMENT, telephone TEXT, question TEXT, reponse TEXT, satisfait INTEGER, motif TEXT, commentaire TEXT, cree_le TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, owner TEXT, nom TEXT, objectif TEXT, statut TEXT DEFAULT 'actif', progression INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, project_id TEXT, owner TEXT, titre TEXT, statut TEXT DEFAULT 'a_faire', echeance TEXT, created_at TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS files (id TEXT PRIMARY KEY, owner TEXT, project_id TEXT, nom TEXT, type TEXT, taille INTEGER, created_at TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS notifications (id TEXT PRIMARY KEY, owner TEXT, type TEXT DEFAULT 'INFORMATION', titre TEXT, message TEXT, lu INTEGER DEFAULT 0, created_at TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS events_log (id TEXT PRIMARY KEY, type TEXT, payload TEXT, created_at TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, owner TEXT, titre TEXT, created_at TEXT, updated_at TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, conv_id TEXT, role TEXT, content TEXT, created_at TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS actions_log (id TEXT PRIMARY KEY, user_id TEXT, action TEXT, objet TEXT, resultat TEXT, permission TEXT, created_at TEXT)")
conn.commit()

class NiveauRisque(Enum):
    LECTURE = 0
    REVERSIBLE = 1
    MODIFICATION = 2
    CRITIQUE = 3

PERMISSIONS = ["READ_PROFILE","EDIT_PROFILE","READ_PROJECT","EDIT_PROJECT","CREATE_PROJECT","DELETE_PROJECT","READ_FILES","UPLOAD_FILES","DELETE_FILES","USE_AI","USE_EXTERNAL_SERVICE"]

def log_action(user_id, action, objet, resultat, perm="USE_AI"):
    with VERROU:
        conn.execute("INSERT INTO actions_log VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4())[:8], user_id, action, objet, resultat, perm, datetime.now().isoformat()))
        conn.commit()

def get_dashboard(owner):
    with VERROU:
        proj = conn.execute("SELECT COUNT(*) FROM projects WHERE owner=? AND statut='actif'", (owner,)).fetchone()[0]
        tasks = conn.execute("SELECT COUNT(*) FROM tasks WHERE owner=? AND statut!='termine'", (owner,)).fetchone()[0]
        msgs = conn.execute("SELECT COUNT(*) FROM notifications WHERE owner=? AND lu=0", (owner,)).fetchone()[0]
        last = conn.execute("SELECT derniere_activite FROM comptes WHERE telephone=?", (owner,)).fetchone()
        last_act = last[0] if last and last[0] else "maintenant"
    return {
        "bonjour": f"Bonjour {owner[:12]}.",
        "projets": f"{proj} actifs",
        "taches": f"{tasks} en attente",
        "messages": f"{msgs} nouveaux",
        "activite": f"derniere activite {last_act}",
        "suggestion": "1 suggestion pertinente" if proj > 0 else "Cree ton premier projet"
    }

def create_project(owner, nom, objectif=""):
    pid = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    with VERROU:
        conn.execute("INSERT INTO projects (id,owner,nom,objectif,statut,progression,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (pid, owner, nom, objectif, "actif", 0, now, now))
        conn.commit()
    BUS.emit("PROJECT_CREATED", {"project_id": pid, "owner": owner, "nom": nom})
    log_action(owner, "CREATE_PROJECT", pid, "SUCCESS", "CREATE_PROJECT")
    return pid

def list_projects(owner):
    with VERROU:
        rows = conn.execute("SELECT id,nom,objectif,statut,progression FROM projects WHERE owner=? ORDER BY updated_at DESC", (owner,)).fetchall()
    return [{"id": r[0], "nom": r[1], "objectif": r[2], "statut": r[3], "progression": r[4]} for r in rows]

def create_task(owner, project_id, titre):
    tid = str(uuid.uuid4())[:8]
    with VERROU:
        conn.execute("INSERT INTO tasks (id,project_id,owner,titre,statut,created_at) VALUES (?,?,?,?,?,?)",
            (tid, project_id, owner, titre, "a_faire", datetime.now().isoformat()))
        conn.commit()
    BUS.emit("TASK_CREATED", {"task_id": tid, "project_id": project_id})
    return tid

def add_notification(owner, type_, titre, message):
    nid = str(uuid.uuid4())[:8]
    with VERROU:
        conn.execute("INSERT INTO notifications (id,owner,type,titre,message,created_at) VALUES (?,?,?,?,?,?)",
            (nid, owner, type_, titre, message, datetime.now().isoformat()))
        conn.commit()
    BUS.emit("NOTIFICATION_CREATED", {"owner": owner, "type": type_})
    return nid

def parser_commande_naturelle(q):
    net = nettoyer(q)
    if "cree un projet" in net or "creer un projet" in net or "nouveau projet" in net:
        m = re.search(r"projet (?:appele |nomme |)?(.+)", q, re.I)
        nom = m.group(1).strip()[:60] if m else "Nouveau projet"
        return {"intent": "CREATE_PROJECT", "nom": nom, "niveau": NiveauRisque.MODIFICATION}
    if "montre mes projets" in net or "mes projets" in net or "liste" in net and "projets" in net:
        return {"intent": "LIST_PROJECTS", "niveau": NiveauRisque.LECTURE}
    if "cree une tache" in net or "nouvelle tache" in net:
        m = re.search(r"tache (.+)", q, re.I)
        titre = m.group(1).strip() if m else "Nouvelle tache"
        return {"intent": "CREATE_TASK", "titre": titre, "niveau": NiveauRisque.MODIFICATION}
    if "tableau de bord" in net or "dashboard" in net:
        return {"intent": "DASHBOARD", "niveau": NiveauRisque.LECTURE}
    return None

def reponse_identite(q):
    net = nettoyer(q)
    if "qui t a cree" in net or "qui t as cree" in net:
        return "J'ai ete creee par Jonathan Dejah OBENDA le 2 juin 2026. Il est mon createur et fondateur."
    if "qui est ton createur" in net or "ton createur" in net:
        return "Mon createur et fondateur est Jonathan Dejah OBENDA."
    if "qui est ton pere" in net or "ton pere" in net:
        return "Mon pere createur est Jonathan Dejah OBENDA, fondateur d'ADRYNX."
    if "quand" in net and "cree" in net:
        return "Ma date officielle de creation est le 2 juin 2026."
    if "qui es tu" in net:
        return "Je suis ADRYNX, IA creee par Jonathan Dejah OBENDA le 2 juin 2026. Orchestrateur de ta plateforme interactive."
    if "qui est jonathan" in net:
        return "Jonathan Dejah OBENDA est le createur et fondateur d'ADRYNX, projet demarre le 2 juin 2026."
    return None

def detecter_intention(q):
    net = nettoyer(q)
    if any(x in net for x in ["createur", "fondateur", "pere", "jonathan", "qui es tu"]):
        return "question_identite"
    if parser_commande_naturelle(q):
        return "commande_plateforme"
    if len(net.split()) <= 8 and ("ca va" in net or "comment vas" in net):
        return "conversation"
    if re.match(r"^(bonjour|salut|coucou|hello)", net):
        return "salutation"
    return "question_factuelle"

def detecter_social(q):
    net = nettoyer(q)
    if len(net.split()) <= 8 and ("ca va" in net or "comment vas" in net):
        return "Ca va tres bien merci! Et toi? Que veux-tu faire aujourd'hui? Projet, recherche ou discussion?"
    if re.match(r"^(bonjour|salut|coucou|hello)", net):
        return "Bonjour! Je suis ADRYNX, ton orchestrateur. Tableau de bord, projets, ou question?"
    return None

def rechercher_internet(q):
    if len(nettoyer(q).split()) <= 6 and "ca va" in nettoyer(q):
        return None
    try:
        r = requests.get("https://api.duckduckgo.com/", params={"q": q, "format": "json", "no_html": "1", "kl": "fr-fr"}, headers=HEADERS, timeout=7)
        txt = r.json().get("AbstractText")
        if txt:
            return txt[:1500]
    except:
        pass
    try:
        api = "https://fr.wikipedia.org/w/api.php"
        s = requests.get(api, params={"action": "query", "format": "json", "list": "search", "srsearch": q, "srlimit": 1}, headers=HEADERS, timeout=7).json()["query"]["search"]
        if s:
            ex = requests.get(api, params={"action": "query", "format": "json", "prop": "extracts", "exintro": 1, "explaintext": 1, "titles": s[0]["title"]}, headers=HEADERS, timeout=7).json()["query"]["pages"]
            for p in ex.values():
                if len(p.get("extract", "")) > 30:
                    return p["extract"][:1500]
    except:
        pass
    return None

def _groq(q, rep):
    k = os.environ.get("GROQ_API_KEY")
    if not k:
        return None
    try:
        j = requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"},
            json={"model": os.environ.get("ADRYNX_MODELE_GROQ", "llama-3.3-70b-versatile"), "messages": [{"role": "user", "content": f"Q:{q} R:{rep[:600]} Corrige si hors-sujet en 2-3 phrases."}], "max_tokens": 300}, timeout=10).json()
        return j["choices"][0]["message"]["content"].strip()
    except:
        return None

def lire_compte(t):
    with VERROU:
        r = conn.execute("SELECT premium,quota FROM comptes WHERE telephone=?", (t,)).fetchone()
    return {"premium": bool(r[0]), "quota": r[1]} if r else {"premium": False, "quota": 0}

def enregistrer_activite(t):
    if not t:
        return
    with VERROU:
        conn.execute("INSERT INTO comptes (telephone) VALUES (?) ON CONFLICT(telephone) DO NOTHING", (t,))
        conn.execute("UPDATE comptes SET derniere_activite=datetime('now') WHERE telephone=?", (t,))
        conn.commit()

def est_bloque(t):
    with VERROU:
        r = conn.execute("SELECT bloque FROM comptes WHERE telephone=?", (t,)).fetchone()
    return bool(r and r[0])

def compter_comptes():
    with VERROU:
        rows = conn.execute("SELECT premium,bloque FROM comptes").fetchall()
    return {"total": len(rows), "premium": sum(1 for p, b in rows if p), "bloques": sum(1 for p, b in rows if b)}

def lister_comptes():
    with VERROU:
        rows = conn.execute("SELECT telephone,premium,quota,bloque,derniere_activite FROM comptes ORDER BY derniere_activite DESC").fetchall()
    return [{"telephone": t, "premium": bool(p), "quota": q, "bloque": bool(b), "derniere_activite": d} for t, p, q, b, d in rows]

def verifier_secret_admin(s):
    sr = os.environ.get("ADRYNX_ADMIN_SECRET")
    return sr and hmac.compare_digest(s.encode(), sr.encode())

def traiter_admin(q):
    m = re.match(r"^admin\s+(\S+)\s+vider\s+cache\s*$", q.strip(), re.I)
    if m and verifier_secret_admin(m.group(1)):
        with VERROU:
            n = conn.execute("SELECT COUNT(*) FROM connaissances_publiques").fetchone()[0]
            conn.execute("DELETE FROM connaissances_publiques")
            conn.commit()
        return f"Cache vide ({n})"
    return None

def enregistrer_avis(tel, q, rep, sat, motif=None, com=None, capture_nom=None, capture_b64=None):
    with VERROU:
        cur = conn.execute("INSERT INTO avis (telephone,question,reponse,satisfait,motif,commentaire,cree_le) VALUES (?,?,?,?,?,?,datetime('now'))", (tel, q[:1000], rep[:1000], int(bool(sat)), motif, com))
        conn.commit()
        return cur.lastrowid

def lister_plaintes(lim=100):
    with VERROU:
        rows = conn.execute("SELECT id,telephone,question,reponse,motif,cree_le FROM avis WHERE satisfait=0 ORDER BY id DESC LIMIT?", (lim,)).fetchall()
    return rows

_contextes = {}
_VC = threading.Lock()

def _contexte(t):
    k = t or "anonyme"
    with _VC:
        if k not in _contextes:
            _contextes[k] = {"sujet": None}
        return _contextes[k]

def _cle(t, a):
    return t or ("anon:" + str(a)[:64] if a else "anonyme")

def lire_connaissance(cle, tel):
    with VERROU:
        r = conn.execute("SELECT reponse FROM connaissances_privees WHERE telephone=? AND question=?", (tel, cle)).fetchone()
        if r:
            return r[0]
        r = conn.execute("SELECT reponse FROM connaissances_publiques WHERE question=?", (cle,)).fetchone()
        return r[0] if r else None

def ecrire_publique(cle, rep):
    with VERROU:
        conn.execute("INSERT OR REPLACE INTO connaissances_publiques (question,reponse) VALUES (?,?)", (cle, rep))
        conn.commit()

# Pour websocket temps reel
_ws_broadcast = None

def set_broadcaster(fn):
    global _ws_broadcast
    _ws_broadcast = fn
    def _forward(payload):
        if _ws_broadcast:
            try:
                _ws_broadcast(payload)
            except:
                pass
    for ev in ["PROJECT_CREATED", "PROJECT_UPDATED", "TASK_CREATED", "NOTIFICATION_CREATED", "AI_RESPONSE_GENERATED"]:
        BUS.on(ev, _forward)

def traiter_question(q, telephone=None, anon=None):
    q_raw = (q or "").strip()
    if not q_raw:
        return "Pose-moi une question."
    tel = _cle(telephone, anon)
    enregistrer_activite(tel)
    if telephone and est_bloque(telephone):
        return "Acces suspendu."
    intention = detecter_intention(q_raw)

    if intention == "question_identite":
        rep = reponse_identite(q_raw)
        if rep:
            return rep

    cmd = parser_commande_naturelle(q_raw)
    if cmd:
        if cmd["intent"] == "CREATE_PROJECT":
            pid = create_project(tel, cmd["nom"])
            return f"Projet '{cmd['nom']}' cree avec succes. ID: {pid}. [Voir mes projets]"
        if cmd["intent"] == "LIST_PROJECTS":
            projs = list_projects(tel)
            if not projs:
                return "Aucun projet actif. Dis 'Cree un projet ADRYNX' pour commencer."
            txt = "\n".join([f"[{p['id']}] {p['nom']} - {p['progression']}%" for p in projs[:5]])
            return f"Tes projets actifs:\n{txt}"
        if cmd["intent"] == "DASHBOARD":
            dash = get_dashboard(tel)
            return f"{dash['bonjour']}\nAujourd'hui:\nPROJETS -> {dash['projets']}\nTACHES -> {dash['taches']}\nMESSAGES -> {dash['messages']}\nACTIVITE -> {dash['activite']}\nADRYNX -> {dash['suggestion']}"

    if intention in ["salutation", "conversation"]:
        s = detecter_social(q_raw)
        if s:
            return s

    a = traiter_admin(q_raw)
    if a:
        return a

    cle = nettoyer(q_raw)
    mem = lire_connaissance(cle, tel)
    if mem:
        return mem

    txt = rechercher_internet(q_raw)
    if txt:
        final = _groq(q_raw, txt) or txt
        ecrire_publique(cle, final[:800])
        BUS.emit("AI_RESPONSE_GENERATED", {"question": q_raw[:100], "owner": tel})
        return final

    return "Je n'ai pas trouve. Essaie 'Montre mes projets' ou 'Cree un projet X'."

repondre = traiter_question

def nouvelle_conversation(tel=None, anon=None):
    _contexte(_cle(tel, anon))["sujet"] = None
