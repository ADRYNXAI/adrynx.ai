"""
ADRYNX AI v2.0 - FICHIER UNIQUE
Ordre de décision : admin → apprentissage → connaissances (privées puis publiques) → calcul → internet → IA premium
Importable (FastAPI) : from adrynx import traiter_question

Changements par rapport à v1.7 :
  - contexte de conversation ("sujet") isolé PAR UTILISATEUR (plus de fuite entre
    conversations simultanées)
  - connaissances enseignées par un utilisateur (retiens:/apprends:/corrections)
    stockées dans une table PRIVÉE (par téléphone) : un utilisateur ne peut plus
    écraser la réponse servie à tout le monde
  - cache des résultats internet conservé dans une table PUBLIQUE séparée
    (sourcé, donc sans risque à partager)
  - vérification des corrections par un modèle NLI open source (optionnel,
    dégrade proprement vers le recouvrement lexical si `transformers` n'est
    pas installé — NE PAS l'ajouter à requirements.txt sur le plan Render
    gratuit, le modèle est trop lourd pour ses 512 Mo de RAM)
  - comparaison du secret admin en temps constant (hmac.compare_digest)
  - le quota premium n'est décrémenté QUE si une clé IA est réellement
    configurée (sinon un utilisateur premium perdait des questions pour rien)

Render : le système de fichiers est éphémère sur les plans standards.
Pour conserver memoire.db entre les redéploiements, monte un disque persistant
et fixe la variable d'environnement ADRYNX_DB sur son chemin, par ex. :
    ADRYNX_DB=/var/data/memoire.db
"""
import ast
import hmac
import operator
import os
import re
import sqlite3
import threading
import unicodedata

import requests

DB = os.environ.get("ADRYNX_DB", "memoire.db")
HEADERS = {"User-Agent": "ADRYNX-AI/2.0 (projet personnel)"}
VERROU = threading.Lock()

conn = sqlite3.connect(DB, check_same_thread=False)
conn.execute(
    "CREATE TABLE IF NOT EXISTS connaissances_publiques "
    "(question TEXT PRIMARY KEY, reponse TEXT)"
)
conn.execute(
    "CREATE TABLE IF NOT EXISTS connaissances_privees "
    "(telephone TEXT NOT NULL, question TEXT NOT NULL, reponse TEXT, "
    "PRIMARY KEY (telephone, question))"
)
conn.execute(
    "CREATE TABLE IF NOT EXISTS comptes (telephone TEXT PRIMARY KEY, "
    "premium INTEGER DEFAULT 0, quota INTEGER DEFAULT 0)"
)
conn.commit()

# Contexte de conversation ISOLÉ par utilisateur. Clé = telephone (ou "anonyme"
# si aucun numéro n'est fourni, ex. usage en ligne de commande / test).
_contextes = {}
_VERROU_CONTEXTE = threading.Lock()


def _contexte(telephone):
    cle = telephone or "anonyme"
    with _VERROU_CONTEXTE:
        if cle not in _contextes:
            _contextes[cle] = {"sujet": None}
        return _contextes[cle]


# ---------------------------------------------------------------- utilitaires
def nettoyer(q):
    """Minuscules, sans accents, sans ponctuation (sert de clé en base)."""
    q = q.lower()
    q = "".join(
        c for c in unicodedata.normalize("NFD", q) if unicodedata.category(c) != "Mn"
    )
    q = re.sub(r"[^a-z0-9 ]", " ", q)
    return re.sub(r"\s+", " ", q).strip()


# -------------------------------------------------------------------- mémoire
def lire_connaissance(cle, telephone):
    """Cherche d'abord dans les connaissances privées de l'utilisateur
    (ce qu'IL a enseigné), puis dans le cache public (résultats internet
    déjà trouvés, partageables car sourcés)."""
    tel = telephone or "anonyme"
    with VERROU:
        row = conn.execute(
            "SELECT reponse FROM connaissances_privees "
            "WHERE telephone = ? AND question = ?",
            (tel, cle),
        ).fetchone()
        if row:
            return row[0]
        row = conn.execute(
            "SELECT reponse FROM connaissances_publiques WHERE question = ?",
            (cle,),
        ).fetchone()
    return row[0] if row else None


def ecrire_connaissance_privee(cle, reponse, telephone):
    tel = telephone or "anonyme"
    with VERROU:
        conn.execute(
            "INSERT OR REPLACE INTO connaissances_privees "
            "(telephone, question, reponse) VALUES (?, ?, ?)",
            (tel, cle, reponse),
        )
        conn.commit()


def ecrire_connaissance_publique(cle, reponse):
    with VERROU:
        conn.execute(
            "INSERT OR REPLACE INTO connaissances_publiques "
            "(question, reponse) VALUES (?, ?)",
            (cle, reponse),
        )
        conn.commit()


def apprendre(q, telephone):
    """« retiens : question = réponse » ou « apprends : question = réponse ».
    Demande EXPLICITE et volontaire de l'utilisateur : enregistrée telle
    quelle, sans vérification, mais dans SA table privée uniquement — elle
    n'affecte jamais la réponse servie aux autres utilisateurs."""
    m = re.match(r"^\s*(?:retiens|apprends)\s*:?\s*(.+?)\s*=\s*(.+)$", q, re.I)
    if not m:
        return None
    ecrire_connaissance_privee(nettoyer(m.group(1)), m.group(2).strip(), telephone)
    return "C'est noté (pour toi uniquement)."


# ------------------------------------------------------- correction vérifiée
MOTS_VIDES = {
    "le", "la", "les", "l", "un", "une", "des", "de", "du", "d", "au", "aux",
    "et", "ou", "est", "sont", "en", "a", "à", "que", "qui", "ce", "cette",
    "ces", "pour", "par", "sur", "dans", "il", "elle", "son", "sa", "ses",
}
CORRECTION_RE = re.compile(
    r"^(?:non,?\s*(?:en fait\s*)?c'est|je me suis tromp[ée]s?,?\s*c'est"
    r"|en fait,?\s*c'est|c'est plutôt|c'est plutot)\s+(.+)$",
    re.I,
)


def detecter_correction(q):
    """Repère une correction du style « non, en fait c'est ... »."""
    m = CORRECTION_RE.match(q.strip())
    return m.group(1).strip().rstrip(".!") if m else None


# --------------------------------------------- vérification NLI (open source)
# Rôle : juger si le texte source CONFIRME ou CONTREDIT une affirmation.
# Ne remplace pas la recherche (rechercher_internet) : vient après, pour
# juger de la cohérence entre affirmation et source déjà trouvée.
# Optionnel : sans `transformers` installé, se dégrade automatiquement vers
# le recouvrement lexical, sans jamais planter.
_nli = None
_nli_indisponible = False


def _charger_nli():
    """Charge le modèle NLI une seule fois, en repli silencieux si absent."""
    global _nli, _nli_indisponible
    if _nli is not None or _nli_indisponible:
        return _nli
    try:
        from transformers import pipeline
        _nli = pipeline(
            "text-classification",
            model="cross-encoder/nli-deberta-v3-base",
        )
    except Exception:
        _nli_indisponible = True
        _nli = None
    return _nli


def _verifier_par_nli(source, affirmation):
    """Retourne True si la source confirme (entailment) l'affirmation,
    False si elle la contredit, None si le résultat est neutre/ambigu ou
    si le modèle n'est pas disponible (repli sur le recouvrement lexical)."""
    modele = _charger_nli()
    if modele is None:
        return None
    try:
        resultat = modele(f"{source} [SEP] {affirmation}", top_k=None)
        meilleur = max(resultat, key=lambda r: r["score"])
        etiquette = meilleur["label"].lower()
        if "entail" in etiquette:
            return True
        if "contradict" in etiquette:
            return False
        return None  # neutre
    except Exception:
        return None


def _verifier_par_mots(source, affirmation):
    """Repli : recouvrement lexical (méthode v1.7, moins fiable mais toujours
    disponible sans dépendance externe)."""
    mots_affirmation = set(nettoyer(affirmation).split()) - MOTS_VIDES
    if not mots_affirmation:
        return None
    mots_source = set(nettoyer(source).split())
    recouvrement = mots_affirmation & mots_source
    if len(recouvrement) >= max(1, len(mots_affirmation) // 2):
        return True
    return None


def verifier_affirmation(sujet, affirmation):
    """Cherche une source externe et juge si elle va dans le sens de
    l'affirmation. Retourne le texte de la source si elle corrobore,
    None sinon (source absente, contradiction, ou résultat neutre)."""
    if not sujet:
        return None
    texte_source = rechercher_internet(sujet)
    if not texte_source:
        return None

    verdict_nli = _verifier_par_nli(texte_source, affirmation)
    if verdict_nli is True:
        return texte_source
    if verdict_nli is False:
        return None  # contradiction explicite : on ne mémorise surtout pas

    # NLI indisponible ou neutre : repli sur le recouvrement lexical
    if _verifier_par_mots(texte_source, affirmation):
        return texte_source
    return None


# --------------------------------------------------------------------- calcul
OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
MOTS_CALCUL = {
    "combien", "font", "fait", "calcule", "calcul", "resultat", "de", "est",
    "egal", "a", "quel", "quelle", "le", "la", "donne", "moi", "cela", "ca", "sont",
}


def _evaluer(n):
    if isinstance(n, ast.Expression):
        return _evaluer(n.body)
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
        return n.value
    if isinstance(n, ast.BinOp) and type(n.op) in OPS:
        a, b = _evaluer(n.left), _evaluer(n.right)
        if isinstance(n.op, ast.Pow) and abs(b) > 100:
            raise ValueError("puissance trop grande")
        return OPS[type(n.op)](a, b)
    if isinstance(n, ast.UnaryOp) and type(n.op) in OPS:
        return OPS[type(n.op)](_evaluer(n.operand))
    raise ValueError("expression non autorisée")


def calculer(q):
    """Retourne le résultat (str) si q est un calcul, sinon None."""
    expr = q.lower().replace(",", ".").replace("÷", "/").replace("×", "*")
    expr = re.sub(r"(?<=\d)\s*x\s*(?=\d)", "*", expr)
    m = re.search(r"[\d(.][\d+\-*/%().\s]*[\d)]|\d", expr)
    if not m or not re.search(r"[+\-*/%]", m.group(0)):
        return None
    reste = nettoyer(expr[: m.start()] + " " + expr[m.end():])
    if any(mot not in MOTS_CALCUL for mot in reste.split()):
        return None  # il y a d'autres mots : ce n'est pas un simple calcul
    try:
        res = _evaluer(ast.parse(m.group(0).strip(), mode="eval"))
    except ZeroDivisionError:
        return "Division par zéro impossible."
    except (ValueError, SyntaxError, OverflowError):
        return None
    if isinstance(res, float):
        res = int(res) if res.is_integer() else round(res, 10)
    return str(res)


# -------------------------------------------------------- sujet et pronoms
DEBUTS = re.compile(
    r"^(?:qui (?:est|etait|était|sont)|c'est qui|c'est quoi|qu'est[- ]ce (?:que|qu')\s*(?:c'est )?"
    r"|que sais[- ]tu (?:de|sur)|parle[- ]moi (?:de|d')|dis[- ]moi qui est"
    r"|comment s'appelle|quel est le nom (?:de|d')|quel(?:le)?s? (?:est|sont)"
    r"|definition (?:de|d')|définition (?:de|d'))\s*"
    r"(?:(?:l[ae]s?|un|une|des|du|de|d')\s*)?",
    re.I,
)
MOTS_PARASITES = re.compile(r"^(?:mais|donc|alors|bon|non)\s+", re.I)
MOT_ACTUEL = re.compile(r"\b(?:l'|le |la |les )?actuel(?:le)?s?\b\s*", re.I)


def extraire_sujet(q):
    """Retourne le sujet de la question (avec accents), ou None."""
    brut = q.strip().rstrip("?!. ")
    m = DEBUTS.match(brut)
    if m and brut[m.end():].strip():
        return brut[m.end():].strip()
    if 0 < len(brut.split()) <= 3:
        return brut
    return None


def simplifier_pour_recherche(q):
    """Retire le bruit conversationnel (« mais », « actuel »...) pour que la
    recherche Wikipédia/DuckDuckGo tombe sur le bon article."""
    brut = q.strip().rstrip("?!. ")
    precedent = None
    while precedent != brut:
        precedent = brut
        brut = MOTS_PARASITES.sub("", brut)
        m = DEBUTS.match(brut)
        if m and brut[m.end():].strip():
            brut = brut[m.end():].strip()
    brut = MOT_ACTUEL.sub("", brut).strip()
    return brut or q.strip().rstrip("?!. ")


def remplacer_pronoms(q, telephone):
    """Remplace « il / elle » (mots entiers uniquement) par le dernier sujet
    connu POUR CET UTILISATEUR."""
    sujet = _contexte(telephone)["sujet"]
    if not sujet:
        return q
    q = re.sub(r"-\s*(?:il|elle)\b", " " + sujet, q, flags=re.I)
    return re.sub(r"\b(?:il|elle)\b", sujet, q, flags=re.I)


# ------------------------------------------------------------------- internet
def rechercher_internet(question):
    """Retourne un texte, ou None si rien trouvé / erreur réseau."""
    requete = simplifier_pour_recherche(question)

    try:
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": requete, "format": "json", "no_html": "1", "kl": "fr-fr"},
            headers=HEADERS,
            timeout=10,
        )
        texte = r.json().get("AbstractText")
        if texte:
            return texte
    except (requests.RequestException, ValueError):
        pass
    try:
        api = "https://fr.wikipedia.org/w/api.php"
        r = requests.get(
            api,
            params={"action": "query", "format": "json", "list": "search",
                    "srsearch": requete, "srlimit": 3},
            headers=HEADERS,
            timeout=10,
        )
        resultats = r.json()["query"]["search"]
        for candidat in resultats:
            r = requests.get(
                api,
                params={"action": "query", "format": "json", "prop": "extracts",
                        "exintro": 1, "explaintext": 1, "redirects": 1,
                        "titles": candidat["title"]},
                headers=HEADERS,
                timeout=10,
            )
            for page in r.json()["query"]["pages"].values():
                extrait = page.get("extract", "")
                if len(extrait) > 40:
                    return extrait[:3000]
    except (requests.RequestException, ValueError, KeyError):
        pass
    return None


# ---------------------------------------------------- IA externe (dernier recours)
def demander_ia_externe(question):
    """Optionnel : interroge une IA en dernier recours, seulement si une clé
    est configurée sur le serveur. Ordre de préférence :
      1. Groq (GROQ_API_KEY) — GRATUIT, sans carte bancaire, modèles open
         source (Llama, GPT-OSS...) : priorité car ça ne coûte rien à Dejah.
      2. Anthropic/Claude (ANTHROPIC_API_KEY) — payant, meilleure qualité.
      3. OpenAI/GPT (OPENAI_API_KEY) — payant.
    Renvoie None si aucune clé n'est configurée ou en cas d'erreur."""
    cle_groq = os.environ.get("GROQ_API_KEY")
    cle_anthropic = os.environ.get("ANTHROPIC_API_KEY")
    cle_openai = os.environ.get("OPENAI_API_KEY")

    if cle_groq:
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {cle_groq}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": os.environ.get("ADRYNX_MODELE_GROQ", "openai/gpt-oss-120b"),
                    "messages": [{"role": "user", "content": question}],
                    "max_tokens": 400,
                },
                timeout=20,
            )
            return r.json()["choices"][0]["message"]["content"].strip()
        except (requests.RequestException, ValueError, KeyError, IndexError):
            pass

    if cle_anthropic:
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": cle_anthropic,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": os.environ.get("ADRYNX_MODELE_ANTHROPIC", "claude-sonnet-5"),
                    "max_tokens": 400,
                    "messages": [{"role": "user", "content": question}],
                },
                timeout=20,
            )
            blocs = r.json().get("content", [])
            texte = "".join(b.get("text", "") for b in blocs if b.get("type") == "text")
            return texte.strip() or None
        except (requests.RequestException, ValueError, KeyError):
            pass

    if cle_openai:
        try:
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {cle_openai}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": os.environ.get("ADRYNX_MODELE_OPENAI", "gpt-4o-mini"),
                    "messages": [{"role": "user", "content": question}],
                    "max_tokens": 400,
                },
                timeout=20,
            )
            return r.json()["choices"][0]["message"]["content"].strip()
        except (requests.RequestException, ValueError, KeyError, IndexError):
            pass

    return None


# -------------------------------------------------------------- comptes premium
def lire_compte(tel):
    with VERROU:
        row = conn.execute(
            "SELECT premium, quota FROM comptes WHERE telephone = ?", (tel,)
        ).fetchone()
    return {"premium": bool(row[0]), "quota": row[1]} if row else {"premium": False, "quota": 0}


def activer_ou_recharger(tel, quota_ajoute):
    with VERROU:
        conn.execute(
            "INSERT INTO comptes (telephone, premium, quota) VALUES (?, 1, ?) "
            "ON CONFLICT(telephone) DO UPDATE SET premium = 1, quota = quota + excluded.quota",
            (tel, quota_ajoute),
        )
        conn.commit()


def desactiver_premium(tel):
    with VERROU:
        conn.execute(
            "INSERT INTO comptes (telephone, premium, quota) VALUES (?, 0, 0) "
            "ON CONFLICT(telephone) DO UPDATE SET premium = 0",
            (tel,),
        )
        conn.commit()


def consommer_quota(tel):
    """Décrémente le quota si le compte est premium et qu'il en reste. Renvoie
    True si la question IA peut être posée, False sinon."""
    with VERROU:
        row = conn.execute(
            "SELECT premium, quota FROM comptes WHERE telephone = ?", (tel,)
        ).fetchone()
        if not row or not row[0] or row[1] <= 0:
            return False
        conn.execute(
            "UPDATE comptes SET quota = quota - 1 WHERE telephone = ?", (tel,)
        )
        conn.commit()
        return True


ADMIN_RE = re.compile(
    r"^admin\s+(\S+)\s+(activer|desactiver|d[ée]sactiver|recharger|statut)\s+"
    r"(\+?[\d\s]{6,})(?:\s+(\d+))?\s*$",
    re.I,
)


def traiter_commande_admin(q):
    """Commandes réservées à l'administrateur, protégées par
    ADRYNX_ADMIN_SECRET (variable d'environnement). Comparaison en temps
    constant pour limiter les attaques par timing."""
    m = ADMIN_RE.match(q.strip())
    if not m:
        return None
    secret_fourni, action, tel_brut, montant = m.groups()
    secret_reel = os.environ.get("ADRYNX_ADMIN_SECRET")
    if not secret_reel:
        return "Commandes admin désactivées (ADRYNX_ADMIN_SECRET non configuré sur le serveur)."
    if not hmac.compare_digest(secret_fourni.encode(), secret_reel.encode()):
        return "Code admin incorrect."

    tel = re.sub(r"\s+", "", tel_brut)
    action = action.lower().replace("é", "e")
    quota_defaut = int(os.environ.get("ADRYNX_QUOTA_DEFAUT", "50"))

    if action == "activer":
        activer_ou_recharger(tel, quota_defaut)
        return f"Compte {tel} activé en premium avec {quota_defaut} questions IA."
    if action == "recharger":
        n = int(montant) if montant else quota_defaut
        activer_ou_recharger(tel, n)
        return f"{n} questions IA ajoutées au compte {tel}."
    if action == "desactiver":
        desactiver_premium(tel)
        return f"Compte {tel} repassé en gratuit."
    if action == "statut":
        c = lire_compte(tel)
        return (
            f"Compte {tel} : premium = {'oui' if c['premium'] else 'non'}, "
            f"quota restant = {c['quota']}"
        )
    return None


# --------------------------------------------------------------------- résumé
MOTS_NAISSANCE = {"ne", "nee", "naissance", "naitre", "naquit"}
MOTS_MORT = {"mort", "morte", "deces", "decede", "mourir", "meurt"}
RE_NAISSANCE = re.compile(r"\bné(?:e)?\b|naissance|\bnaît\b|\bnaquit\b", re.I)
RE_MORT = re.compile(r"\bmort(?:e)?\b|décédé|\bmeurt\b|\bmourut\b", re.I)


def resumer(texte, question, max_car=450):
    """Réduit le texte à l'essentiel, en coupant toujours en fin de phrase."""
    texte = re.sub(r"\s+", " ", texte)
    texte = re.sub(r"\s*\((?:[^()]*prononc[^()]*)\)", "", texte)  # (prononcé ...)
    phrases = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý])", texte.strip())
    mots = set(nettoyer(question).split())
    motif = None
    if mots & MOTS_NAISSANCE:
        motif = RE_NAISSANCE
    elif mots & MOTS_MORT:
        motif = RE_MORT
    if motif:
        for ph in phrases:
            if motif.search(ph):
                return ph[:max_car]
    resume = ""
    for ph in phrases[:3]:
        if resume and len(resume) + len(ph) > max_car:
            break
        resume = (resume + " " + ph).strip()
    return resume[:max_car] if resume else texte[:max_car]


# ----------------------------------------------------------------- orchestrateur
def traiter_question(q, telephone=None):
    q = (q or "").strip()
    if not q:
        return "Pose-moi une question."

    ctx = _contexte(telephone)

    # 0. commande admin
    reponse = traiter_commande_admin(q)
    if reponse:
        return reponse

    # 1. apprentissage explicite (privé à l'utilisateur, pas de vérification :
    # il l'assume sciemment, et ça n'affecte que lui)
    reponse = apprendre(q, telephone)
    if reponse:
        return reponse

    # 1 bis. correction naturelle : on VÉRIFIE via NLI/lexical avant de
    # mémoriser, et dans le cache PUBLIC (une correction confirmée par une
    # source est aussi fiable qu'un résultat internet classique).
    correction = detecter_correction(q)
    if correction is not None:
        sujet = ctx["sujet"]
        preuve = verifier_affirmation(sujet, correction)
        if preuve:
            ecrire_connaissance_publique(
                nettoyer(sujet or correction), resumer(preuve, correction)
            )
            return "C'est noté — une source va bien dans ce sens."
        return (
            "Je ne trouve pas de confirmation de cette information dans mes "
            "sources (ou une source la contredit). Si tu es sûr, utilise "
            "« retiens : question = réponse » pour que je la garde quand "
            "même, à ta demande explicite (juste pour toi)."
        )

    # 2. calcul
    reponse = calculer(q)
    if reponse is not None:
        return reponse

    # 3. pronom sans sujet connu (pour cet utilisateur)
    if not ctx["sujet"] and re.search(r"\b(?:il|elle)\b", q, re.I):
        return "De qui parles-tu ? Pose d'abord une question comme « qui est ... ? »."

    # 3 bis. pronoms -> dernier sujet DE CET UTILISATEUR, puis connaissances
    q_final = remplacer_pronoms(q, telephone)
    cle = nettoyer(q_final)
    reponse = lire_connaissance(cle, telephone)
    if reponse:
        return reponse

    # 4. internet -> mémorisé dans le cache PUBLIC (sourcé, partageable)
    reponse = rechercher_internet(q_final)
    sujet = extraire_sujet(q_final)
    if reponse:
        reponse = resumer(reponse, q_final)
        ecrire_connaissance_publique(cle, reponse)
        if sujet:
            ctx["sujet"] = sujet
        return reponse

    # 5. dernier recours, réservé aux comptes premium avec quota restant.
    # Le quota n'est décrémenté QUE si une clé IA est réellement configurée,
    # sinon un utilisateur premium perdrait des questions pour rien.
    cle_ia_configuree = bool(
        os.environ.get("GROQ_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    if telephone and cle_ia_configuree and consommer_quota(telephone):
        reponse_ia = demander_ia_externe(q_final)
        if reponse_ia:
            if sujet:
                ctx["sujet"] = sujet
            return reponse_ia + "\n\n(réponse d'une IA externe, non vérifiée par une source)"

    if telephone and not lire_compte(telephone)["premium"]:
        return (
            "Aucune information trouvée. Passe en version premium pour "
            "débloquer les réponses IA sur ce type de question."
        )
    return "Aucune information trouvée."


repondre = traiter_question  # alias pour api.py


if __name__ == "__main__":
    print("ADRYNX v2.0 chargé")
    print("ADRYNX prêt (quitter : quit / exit)")
    while True:
        try:
            saisie = input("\nVous : ")
        except (EOFError, KeyboardInterrupt):
            break
        if saisie.strip().lower() in ("quit", "exit", "quitter"):
            break
        print("ADRYNX :", traiter_question(saisie))
