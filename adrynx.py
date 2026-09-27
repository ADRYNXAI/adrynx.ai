"""
ADRYNX AI v2.1 - FICHIER UNIQUE
Ordre de décision : social → admin → apprentissage → correction → calcul →
                     pronom → connaissances → conseil (Groq gratuit) →
                     internet → IA premium
Importable (FastAPI) : from adrynx import traiter_question

Changements v2.1 (correctifs suite aux plaintes utilisateurs) :
  - (Bug A) interception des salutations/remerciements/adieux AVANT toute
    recherche internet : "Bonjour" ne tombe plus sur l'article Wikipédia
    sur les salutations.
  - (Bug B) détection des demandes de conseil/méthode ("comment devenir bon
    en X", "des astuces pour...") : Wikipédia n'a pas d'article pour ce
    type de question, donc on ne le cherche plus. On tente d'abord Groq
    (gratuit, pas de carte bancaire) ; sinon on retombe sur le circuit IA
    premium existant, ou un message honnête plutôt qu'un extrait hors
    sujet.
  - (Bug C) filtrage des résultats Wikipédia par catégorie : on écarte
    désormais un extrait qui commence par "est un roman / film / jeu
    vidéo / chanson / etc." quand la question attend un fait concret. Pour
    les questions avec un superlatif ("le plus grand/long..."), on essaie
    en priorité une recherche orientée "liste" (ex. "liste des fleuves...")
    qui tombe plus souvent sur la bonne page de classement.
  - (Bug D) profondeur de réponse adaptative : les questions du type
    "raconte-moi l'histoire de...", "explique en détail...", "quelles sont
    les étapes de..." déclenchent une extraction Wikipédia plus longue
    (extrait complet, pas juste l'intro) et un résumé plus généreux, au
    lieu d'être toujours coupées à 3 phrases.

IMPORTANT — nettoyage du cache après déploiement : les mauvaises réponses
déjà vues (ex. "fleuve" -> roman, "maths" -> histoire) sont probablement
déjà mémorisées dans connaissances_publiques (c'est un cache de résultats
internet, donc sans risque à vider). Après avoir déployé ce correctif,
exécute une fois :
    sqlite3 memoire.db "DELETE FROM connaissances_publiques;"
(ou cible des lignes précises avec un WHERE si tu préfères garder le reste
du cache). Ne touche pas à connaissances_privees : ce sont des informations
enseignées explicitement par les utilisateurs (retiens:/apprends:).

Render : le système de fichiers est éphémère sur les plans standards.
Pour conserver memoire.db entre les redéploiements, monte un disque persistant
et fixe la variable d'environnement ADRYNX_DB sur son chemin, par ex. :
    ADRYNX_DB=/var/data/memoire.db
"""
import ast
import hmac
import operator
import os
import random
import re
import sqlite3
import threading
import unicodedata

import requests

DB = os.environ.get("ADRYNX_DB", "memoire.db")
HEADERS = {"User-Agent": "ADRYNX-AI/2.1 (projet personnel)"}
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


# ------------------------------------------------------- (Bug A) small talk
SALUTATIONS_RE = re.compile(r"^(?:bonjour|bonsoir|salut|coucou|hello|hey|yo)[\s!.,]*$", re.I)
REMERCIEMENTS_RE = re.compile(r"^(?:merci(?:\s+beaucoup|\s+bien)?|je te remercie)[\s!.,]*$", re.I)
AU_REVOIR_RE = re.compile(r"^(?:au revoir|a\s*\+|[àa]\s*bient[oô]t|bonne (?:journee|soiree)|bye)[\s!.,]*$", re.I)

_REPONSES_SALUTATION = [
    "Bonjour ! Je suis ADRYNX, à votre service. Comment puis-je vous aider ?",
    "Salut ! ADRYNX à l'écoute, que puis-je faire pour toi ?",
    "Bonjour, ADRYNX ici. Dis-moi ce dont tu as besoin.",
]
_REPONSES_REMERCIEMENT = [
    "Avec plaisir !",
    "De rien, n'hésite pas si tu as d'autres questions.",
]
_REPONSES_AU_REVOIR = [
    "Au revoir ! À bientôt.",
    "Bonne journée, à la prochaine !",
]


def detecter_social(q):
    """Retourne une réponse toute faite si q est une simple formule de
    politesse (salutation, remerciement, adieu), sans autre contenu."""
    q_strip = q.strip()
    if SALUTATIONS_RE.match(q_strip):
        return random.choice(_REPONSES_SALUTATION)
    if REMERCIEMENTS_RE.match(q_strip):
        return random.choice(_REPONSES_REMERCIEMENT)
    if AU_REVOIR_RE.match(q_strip):
        return random.choice(_REPONSES_AU_REVOIR)
    return None


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
    if row and _EXCLUSIONS_TYPE.search(row[0][:200]):
        # Entrée mise en cache par erreur avant le correctif du Bug C
        # (ex. réponse sur un roman/film au lieu du fait attendu).
        return None
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
        return None
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


# --------------------------------------------------- (Bug B) demande de conseil
CONSEIL_RE = re.compile(
    r"\b(?:comment (?:devenir|etre) (?:bon|bonne|meilleur|meilleure)\b"
    r"|comment progresser\b|comment m ameliorer\b|comment ameliorer\b"
    r"|(?:astuce|astuces|conseil|conseils|methode|methodes) pour\b"
    r"|je veux devenir (?:meilleur|meilleure|bon|bonne)\b"
    r"|je voudrais devenir (?:meilleur|meilleure|bon|bonne)\b)"
)


def demande_de_conseil(q):
    """Détecte une demande de conseil/méthode ('comment devenir bon en X',
    'des astuces pour...'). Wikipédia n'a pas d'article pour ce genre de
    question : il ne faut donc pas le chercher là."""
    return bool(CONSEIL_RE.search(nettoyer(q)))


# ------------------------------------------------- (Bug D) profondeur voulue
APPROFONDIR_RE = re.compile(
    r"\b(?:raconte\w*|racontez\w*|expliqu\w*\s+en\s+detail|l histoire de"
    r"|quelles sont les etapes|en detail)\b"
)


def demande_approfondie(q):
    """Détecte une demande de récit/développement ('raconte-moi l'histoire
    de...', 'explique en détail...') qui doit renvoyer plus qu'une intro."""
    return bool(APPROFONDIR_RE.search(nettoyer(q)))


# --------------------------------------------------- (Bug C) filtrage Wikipédia
_EXCLUSIONS_TYPE = re.compile(
    r"\best\s+(?:un|une)\s+(?:roman|film|jeu vid[ée]o|album|chanson|"
    r"s[ée]rie(?: t[ée]l[ée]vis[ée]e)?|personnage|manga|bande dessin[ée]e|"
    r"nouvelle)\b",
    re.I,
)
SUPERLATIF_RE = re.compile(
    r"\b(?:le plus |la plus |les plus )(?:grand|petit|long|large|haut|"
    r"peupl[ée]|important)e?s?\b",
    re.I,
)


# ------------------------------------------------------------------- internet
def rechercher_internet(question, approfondi=False):
    """Retourne un texte, ou None si rien trouvé / erreur réseau.
    Si approfondi=True, tente de récupérer plus que la seule intro
    Wikipédia (utile pour "raconte-moi l'histoire de...")."""
    requete = simplifier_pour_recherche(question)
    est_superlatif = bool(SUPERLATIF_RE.search(question))

    if not approfondi:
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
        requetes_wikipedia = [requete]
        if est_superlatif:
            # Privilégier une éventuelle page de classement pour les
            # superlatifs ("le plus grand/long/..."), qui répond
            # directement par une liste plutôt qu'un article isolé.
            requetes_wikipedia.insert(0, "liste " + requete)

        candidats = []
        for srsearch in requetes_wikipedia:
            r = requests.get(
                api,
                params={"action": "query", "format": "json", "list": "search",
                        "srsearch": srsearch, "srlimit": 3},
                headers=HEADERS,
                timeout=10,
            )
            candidats.extend(r.json()["query"]["search"])

        for candidat in candidats:
            r = requests.get(
                api,
                params={"action": "query", "format": "json", "prop": "extracts",
                        "exintro": 0 if approfondi else 1, "explaintext": 1,
                        "redirects": 1, "titles": candidat["title"]},
                headers=HEADERS,
                timeout=10,
            )
            for page in r.json()["query"]["pages"].values():
                extrait = page.get("extract", "")
                if len(extrait) <= 40:
                    continue
                if _EXCLUSIONS_TYPE.search(extrait[:200]):
                    continue  # roman/film/jeu vidéo... : mauvaise catégorie
                return extrait[:6000 if approfondi else 3000]
    except (requests.RequestException, ValueError, KeyError):
        pass
    return None


# ---------------------------------------------------- IA externe (dernier recours)
def _demander_groq(question):
    cle = os.environ.get("GROQ_API_KEY")
    if not cle:
        return None
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {cle}", "Content-Type": "application/json"},
            json={
                "model": os.environ.get("ADRYNX_MODELE_GROQ", "openai/gpt-oss-120b"),
                "messages": [{"role": "user", "content": question}],
                "max_tokens": 400,
            },
            timeout=20,
        )
        return r.json()["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None


def _demander_anthropic(question):
    cle = os.environ.get("ANTHROPIC_API_KEY")
    if not cle:
        return None
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": cle,
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
        return None


def _demander_openai(question):
    cle = os.environ.get("OPENAI_API_KEY")
    if not cle:
        return None
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {cle}", "Content-Type": "application/json"},
            json={
                "model": os.environ.get("ADRYNX_MODELE_OPENAI", "gpt-4o-mini"),
                "messages": [{"role": "user", "content": question}],
                "max_tokens": 400,
            },
            timeout=20,
        )
        return r.json()["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None


def demander_ia_externe(question):
    """Optionnel : interroge une IA en dernier recours, seulement si une clé
    est configurée sur le serveur. Ordre de préférence :
      1. Groq (GROQ_API_KEY) — GRATUIT, sans carte bancaire.
      2. Anthropic/Claude (ANTHROPIC_API_KEY) — payant, meilleure qualité.
      3. OpenAI/GPT (OPENAI_API_KEY) — payant.
    Renvoie None si aucune clé n'est configurée ou en cas d'erreur."""
    for fn in (_demander_groq, _demander_anthropic, _demander_openai):
        reponse = fn(question)
        if reponse:
            return reponse
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
VIDER_CACHE_RE = re.compile(r"^admin\s+(\S+)\s+vider\s+cache\s*$", re.I)


def traiter_commande_admin(q):
    """Commandes réservées à l'administrateur, protégées par
    ADRYNX_ADMIN_SECRET (variable d'environnement). Comparaison en temps
    constant pour limiter les attaques par timing."""
    secret_reel = os.environ.get("ADRYNX_ADMIN_SECRET")

    # "admin <secret> vider cache" : vide le cache PUBLIC (connaissances_publiques)
    # sans avoir besoin d'un accès shell/SSH au serveur — utile sur Render où
    # le plan gratuit ne donne pas toujours de terminal. Ne touche jamais aux
    # connaissances_privees (enseignées explicitement par les utilisateurs).
    m_vider = VIDER_CACHE_RE.match(q.strip())
    if m_vider:
        if not secret_reel:
            return "Commandes admin désactivées (ADRYNX_ADMIN_SECRET non configuré sur le serveur)."
        if not hmac.compare_digest(m_vider.group(1).encode(), secret_reel.encode()):
            return "Code admin incorrect."
        with VERROU:
            n = conn.execute("SELECT COUNT(*) FROM connaissances_publiques").fetchone()[0]
            conn.execute("DELETE FROM connaissances_publiques")
            conn.commit()
        return f"Cache public vidé ({n} entrées supprimées). Les connaissances privées (retiens:/apprends:) n'ont pas été touchées."

    m = ADMIN_RE.match(q.strip())
    if not m:
        return None
    secret_fourni, action, tel_brut, montant = m.groups()
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


def resumer(texte, question, max_car=450, max_phrases=3):
    """Réduit le texte à l'essentiel, en coupant toujours en fin de phrase.
    max_car/max_phrases sont augmentés pour les demandes de récit détaillé
    (cf. demande_approfondie)."""
    texte = re.sub(r"\s+", " ", texte)
    texte = re.sub(r"\s*\((?:[^()]*prononc[^()]*)\)", "", texte)
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
    for ph in phrases[:max_phrases]:
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

    # 0. (Bug A) salutations / politesse : interceptées avant toute recherche
    reponse = detecter_social(q)
    if reponse:
        return reponse

    # 1. commande admin
    reponse = traiter_commande_admin(q)
    if reponse:
        return reponse

    # 2. apprentissage explicite (privé à l'utilisateur, pas de vérification :
    # il l'assume sciemment, et ça n'affecte que lui)
    reponse = apprendre(q, telephone)
    if reponse:
        return reponse

    # 2 bis. correction naturelle : on VÉRIFIE via NLI/lexical avant de
    # mémoriser, et dans le cache PUBLIC.
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

    # 3. calcul
    reponse = calculer(q)
    if reponse is not None:
        return reponse

    # 4. pronom sans sujet connu (pour cet utilisateur)
    if not ctx["sujet"] and re.search(r"\b(?:il|elle)\b", q, re.I):
        return "De qui parles-tu ? Pose d'abord une question comme « qui est ... ? »."

    # 4 bis. pronoms -> dernier sujet DE CET UTILISATEUR, puis connaissances
    q_final = remplacer_pronoms(q, telephone)
    cle = nettoyer(q_final)
    reponse = lire_connaissance(cle, telephone)
    if reponse:
        return reponse

    # 5. (Bug B) demande de conseil/méthode : Wikipédia n'y répond pas, donc
    # on ne cherche pas sur internet pour ce type de question. Priorité à
    # Groq (gratuit) si configuré.
    conseil = demande_de_conseil(q_final)
    if conseil and os.environ.get("GROQ_API_KEY"):
        reponse_ia = _demander_groq(q_final)
        if reponse_ia:
            return reponse_ia + "\n\n(réponse générée, à vérifier par toi-même)"

    # 6. internet -> mémorisé dans le cache PUBLIC (sourcé, partageable).
    # Sauté pour les demandes de conseil (cf. étape 5).
    sujet = extraire_sujet(q_final)
    if not conseil:
        approfondi = demande_approfondie(q_final)
        reponse = rechercher_internet(q_final, approfondi=approfondi)
        if reponse:
            reponse = resumer(
                reponse, q_final,
                max_car=1800 if approfondi else 450,
                max_phrases=10 if approfondi else 3,
            )
            ecrire_connaissance_publique(cle, reponse)
            if sujet:
                ctx["sujet"] = sujet
            return reponse

    # 7. dernier recours, réservé aux comptes premium avec quota restant.
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

    if conseil:
        return (
            "Je n'ai pas de conseils tout prêts pour cette demande précise "
            "(Wikipédia ne peut pas répondre à ce genre de question). Passe "
            "en version premium pour une réponse plus personnalisée, ou "
            "reformule ta question de façon plus factuelle."
        )
    if telephone and not lire_compte(telephone)["premium"]:
        return (
            "Aucune information trouvée. Passe en version premium pour "
            "débloquer les réponses IA sur ce type de question."
        )
    return "Aucune information trouvée."


repondre = traiter_question  # alias pour api.py


if __name__ == "__main__":
    print("ADRYNX v2.1 chargé")
    print("ADRYNX prêt (quitter : quit / exit)")
    while True:
        try:
            saisie = input("\nVous : ")
        except (EOFError, KeyboardInterrupt):
            break
        if saisie.strip().lower() in ("quit", "exit", "quitter"):
            break
        print("ADRYNX :", traiter_question(saisie))
