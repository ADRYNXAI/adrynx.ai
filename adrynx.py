"""
ADRYNX AI v1.3 - FICHIER UNIQUE
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
HEADERS = {"User-Agent": "ADRYNX-AI/1.3 (projet personnel)"}
VERROU = threading.Lock()

conn = sqlite3.connect(DB, check_same_thread=False)
conn.execute(
    "CREATE TABLE IF NOT EXISTS connaissances (question TEXT PRIMARY KEY, reponse TEXT)"
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
    """« retiens : question = réponse » ou « apprends : question = réponse »."""
    m = re.match(r"^\s*(?:retiens|apprends)\s*:?\s*(.+?)\s*=\s*(.+)$", q, re.I)
    if not m:
        return None
    ecrire_connaissance(nettoyer(m.group(1)), m.group(2).strip())
    return "C'est noté."


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
    r"|quel(?:le)? est|definition (?:de|d')|définition (?:de|d'))\s*"
    r"(?:(?:l[ae]s?|un|une|des|du|de|d')\s*)?",
    re.I,
)


def extraire_sujet(q):
    """Retourne le sujet de la question (avec accents), ou None."""
    brut = q.strip().rstrip("?!. ")
    m = DEBUTS.match(brut)
    if m and brut[m.end():].strip():
        return brut[m.end():].strip()
    if 0 < len(brut.split()) <= 3:
        return brut
    return None


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
    try:
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": question, "format": "json", "no_html": "1", "kl": "fr-fr"},
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
                    "srsearch": question, "srlimit": 1},
            headers=HEADERS,
            timeout=10,
        )
        resultats = r.json()["query"]["search"]
        if resultats:
            r = requests.get(
                api,
                params={"action": "query", "format": "json", "prop": "extracts",
                        "exintro": 1, "explaintext": 1, "redirects": 1,
                        "titles": resultats[0]["title"]},
                headers=HEADERS,
                timeout=10,
            )
            for page in r.json()["query"]["pages"].values():
                if page.get("extract"):
                    return page["extract"][:3000]
    except (requests.RequestException, ValueError, KeyError):
        pass
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
def traiter_question(q):
    q = (q or "").strip()
    if not q:
        return "Pose-moi une question."

    # 1. apprentissage explicite
    reponse = apprendre(q)
    if reponse:
        return reponse

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
    return "Aucune information trouvée."


repondre = traiter_question  # alias pour api.py


if __name__ == "__main__":
    print("ADRYNX v1.3 chargé")
    print("ADRYNX prêt (quitter : quit / exit)")
    while True:
        try:
            saisie = input("\nVous : ")
        except (EOFError, KeyboardInterrupt):
            break
        if saisie.strip().lower() in ("quit", "exit", "quitter"):
            break
        print("ADRYNX :", traiter_question(saisie))
