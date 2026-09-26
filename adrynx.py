"""
ADRYNX AI v1.8 - FICHIER UNIQUE
Ordre de décision : apprentissage → connaissances → calcul → internet
Importable (FastAPI) : from adrynx import traiter_question
"""
import ast
import operator
import os
import re
import sqlite3
import threading
import unicodedata

import requests

DB = os.environ.get("ADRYNX_DB", "memoire.db")
HEADERS = {"User-Agent": "ADRYNX-AI/1.8 (projet personnel)"}
VERROU = threading.Lock()

conn = sqlite3.connect(DB, check_same_thread=False)
conn.execute(
    "CREATE TABLE IF NOT EXISTS connaissances (question TEXT PRIMARY KEY, reponse TEXT)"
)
conn.execute(
    "CREATE TABLE IF NOT EXISTS comptes (telephone TEXT PRIMARY KEY, "
    "premium INTEGER DEFAULT 0, quota INTEGER DEFAULT 0)"
)
conn.commit()

contexte = {"sujet": None}


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
def lire_connaissance(cle):
    with VERROU:
        row = conn.execute(
            "SELECT reponse FROM connaissances WHERE question = ?", (cle,)
        ).fetchone()
    return row[0] if row else None


def ecrire_connaissance(cle, reponse):
    with VERROU:
        conn.execute(
            "INSERT OR REPLACE INTO connaissances (question, reponse) VALUES (?, ?)",
            (cle, reponse),
        )
        conn.commit()


def apprendre(q):
    """« retiens : question = réponse » ou « apprends : question = réponse ».
    C'est une demande EXPLICITE et volontaire de l'utilisateur : on l'enregistre
    telle quelle, sans vérification, car la personne l'assume sciemment."""
    m = re.match(r"^\s*(?:retiens|apprends)\s*:?\s*(.+?)\s*=\s*(.+)$", q, re.I)
    if not m:
        return None
    ecrire_connaissance(nettoyer(m.group(1)), m.group(2).strip())
    return "C'est noté."


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


def verifier_affirmation(sujet, affirmation):
    """Cherche une source externe qui va dans le sens de l'affirmation.
    Retourne le texte de la source si elle corrobore, sinon None."""
    if not sujet:
        return None
    texte_source = rechercher_internet(sujet)
    if not texte_source:
        return None
    mots_affirmation = set(nettoyer(affirmation).split()) - MOTS_VIDES
    if not mots_affirmation:
        return None
    mots_source = set(nettoyer(texte_source).split())
    recouvrement = mots_affirmation & mots_source
    if len(recouvrement) >= max(1, len(mots_affirmation) // 2):
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


def remplacer_pronoms(q):
    """Remplace « il / elle » (mots entiers uniquement) par le dernier sujet."""
    sujet = contexte["sujet"]
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
    """Optionnel : interroge Claude (Anthropic) ou GPT (OpenAI) en dernier
    recours, seulement si une clé d'API est configurée sur le serveur.
    Renvoie None si aucune clé n'est configurée ou en cas d'erreur."""
    cle_anthropic = os.environ.get("ANTHROPIC_API_KEY")
    cle_openai = os.environ.get("OPENAI_API_KEY")

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
    """Commandes réservées à Dejah, protégées par ADRYNX_ADMIN_SECRET (variable
    d'environnement). Sans cette variable configurée, ces commandes sont
    désactivées : personne ne peut s'auto-activer en premium."""
    m = ADMIN_RE.match(q.strip())
    if not m:
        return None
    secret_fourni, action, tel_brut, montant = m.groups()
    secret_reel = os.environ.get("ADRYNX_ADMIN_SECRET")
    if not secret_reel:
        return "Commandes admin désactivées (ADRYNX_ADMIN_SECRET non configuré sur le serveur)."
    if secret_fourni != secret_reel:
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

    # 0. commande admin (activation/rechargement premium par Dejah uniquement)
    reponse = traiter_commande_admin(q)
    if reponse:
        return reponse

    # 1. apprentissage explicite (l'utilisateur assume, pas de vérification)
    reponse = apprendre(q)
    if reponse:
        return reponse

    # 1 bis. correction naturelle ("non, en fait c'est...") : on VÉRIFIE avant
    # de mémoriser, on ne fait jamais confiance à une affirmation sur parole.
    correction = detecter_correction(q)
    if correction is not None:
        sujet = contexte["sujet"]
        preuve = verifier_affirmation(sujet, correction)
        if preuve:
            ecrire_connaissance(nettoyer(sujet or correction), resumer(preuve, correction))
            return "C'est noté — et une source va bien dans ce sens."
        return (
            "Je ne trouve pas de confirmation de cette information dans mes "
            "sources. Si tu es sûr, utilise « retiens : question = réponse » "
            "pour que je la garde quand même, à ta demande explicite."
        )

    # 2. calcul (avant tout nettoyage, sinon +, - et * disparaissent)
    reponse = calculer(q)
    if reponse is not None:
        return reponse

    # 3. pronom sans sujet connu : inutile de chercher au hasard sur internet
    if not contexte["sujet"] and re.search(r"\b(?:il|elle)\b", q, re.I):
        return "De qui parles-tu ? Pose d'abord une question comme « qui est ... ? »."

    # 3 bis. pronoms -> dernier sujet, puis connaissances
    q_final = remplacer_pronoms(q)
    cle = nettoyer(q_final)
    reponse = lire_connaissance(cle)
    if reponse:
        return reponse

    # 4. internet, et mémorisation du résultat
    reponse = rechercher_internet(q_final)
    sujet = extraire_sujet(q_final)
    if reponse:
        reponse = resumer(reponse, q_final)
        ecrire_connaissance(cle, reponse)
        if sujet:
            contexte["sujet"] = sujet
        return reponse

    # 5. dernier recours, réservé aux comptes premium avec du quota restant :
    # non mémorisé automatiquement, et toujours annoncé comme tel (transparence)
    cle_ia_configuree = bool(
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
    )
    if telephone and cle_ia_configuree and consommer_quota(telephone):
        reponse_ia = demander_ia_externe(q_final)
        if reponse_ia:
            if sujet:
                contexte["sujet"] = sujet
            return reponse_ia + "\n\n(réponse d'une IA externe, non vérifiée par une source)"

    if telephone and not lire_compte(telephone)["premium"]:
        return (
            "Aucune information trouvée. Passe en version premium pour "
            "débloquer les réponses IA sur ce type de question."
        )
    return "Aucune information trouvée."


repondre = traiter_question  # alias pour api.py


if __name__ == "__main__":
    print("ADRYNX v1.8 chargé")
    print("ADRYNX prêt (quitter : quit / exit)")
    while True:
        try:
            saisie = input("\nVous : ")
        except (EOFError, KeyboardInterrupt):
            break
        if saisie.strip().lower() in ("quit", "exit", "quitter"):
            break
        print("ADRYNX :", traiter_question(saisie))
