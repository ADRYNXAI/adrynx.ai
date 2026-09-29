import os, json, re, sqlite3
from pathlib import Path
from typing import Dict, Any, Tuple

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
PHOENIX_VIDEO = "https://files.catbox.moe/y2nvi4.mp4"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "adrynx.db"

def db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def groq_chat(system, prompt, temperature=0.2, max_tokens=800):
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    r = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=temperature,
        max_tokens=max_tokens
    )
    return r.choices[0].message.content

def normaliser_texte(t): return (t or "").strip()
def minuscules(t): return (t or "").lower()

def reponse_identite_immuable():
    return "Je suis ADRYNX, créé par Jonathan Dejah OBENDA le 2 juin 2026. Mon core vidéo est Phoenix Cristal."

def reponse_sociale(q):
    return "Cc! C'est ADRYNX 🔥 Je suis en ligne, Phoenix Core actif. On lance quoi? Plus que l'impossible."

PARENTS_SYSTEME = """
Tu es le PARENT UNIQUE d'ADRYNX. 4 missions en 1 seul cerveau.
1. LOGIQUE : La réponse répond-elle vraiment à la question?
2. VÉRIFICATEUR : Pas d'invention, pas de hallucination?
3. CONTEXTE : On reste dans le même sujet?
4. SÉCURITÉ : Pas de fuite de données?
RÈGLES ABSOLUES :
- Si question = salutation (cc, slt, yo, salut) -> valide=true OBLIGATOIRE
- Ne JAMAIS ajouter "selon recherche internet" dans une salutation
- Réponds UNIQUEMENT en JSON valide
Format:
{"valide": true, "problemes": [], "correction": "", "confiance": 0.95}
"""

def parser_parent_json(text: str) -> Dict[str, Any]:
    if not text: return {"valide": False, "problemes": ["vide"], "correction": "", "confiance": 0.0}
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return {"valide": bool(data.get("valide", False)), "problemes": data.get("problemes", []), "correction": normaliser_texte(data.get("correction", "")), "confiance": float(data.get("confiance", 0.0))}
    except: pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return {"valide": bool(data.get("valide", False)), "problemes": data.get("problemes", []), "correction": normaliser_texte(data.get("correction", "")), "confiance": float(data.get("confiance", 0.0))}
        except: pass
    return {"valide": False, "problemes": ["non structuré"], "correction": "", "confiance": 0.0}

def appeler_parent_unique(question, candidat, contexte):
    prompt = f"QUESTION: {question}\nCANDIDAT: {candidat}\nINTENT: {contexte.get('intent','')}\nMODE: {contexte.get('mode','')}"
    resultat = groq_chat(PARENTS_SYSTEME, prompt, temperature=0.0, max_tokens=500)
    return parser_parent_json(resultat)

def controler_parent(question, candidat, contexte):
    intent = contexte.get("intent","")
    qlow = question.strip().lower()
    if intent == "identite":
        return {"reponse": reponse_identite_immuable(), "valide": True, "parents": [], "confiance": 1.0}
    if intent in ("salutation","conversation") and (len(qlow) <= 4 or qlow in {"cc","c c","cc?","slt","salut","yo","hey","wesh"}):
        return {"reponse": candidat, "valide": True, "parents": [], "confiance": 1.0, "source": "noyau-direct"}
    rapport = appeler_parent_unique(question, candidat, contexte)
    if rapport.get("valide"):
        return {"reponse": candidat, "valide": True, "parents": [rapport], "confiance": rapport.get("confiance",0.9)}
    if rapport.get("correction"):
        return {"reponse": rapport["correction"], "valide": True, "parents": [rapport], "confiance": rapport.get("confiance",0.9), "correction_appliquee": True}
    return {"reponse": candidat, "valide": True, "parents": [rapport], "confiance": 0.7}

def controle_parents(question, reponse, contexte): return controler_parent(question, reponse, contexte)["reponse"]

def detecter_intent(q):
    low = q.lower().strip()
    if low in {"cc","slt","salut","yo","hey","bjr","bonjour"}: return "salutation"
    if "qui es tu" in low or "qui es-tu" in low or "qui t'a créé" in low: return "identite"
    if len(low) <= 5: return "salutation"
    return "conversation"

def pipeline_adrynx(question):
    intent = detecter_intent(question)
    if intent == "salutation": return reponse_sociale(question), {"intent": intent, "mode": "social"}
    if intent == "identite": return reponse_identite_immuable(), {"intent": intent, "mode": "identite"}
    system = "Tu es ADRYNX, assistant de Jonathan. Réponds court, utile, sans inventer."
    candidat = groq_chat(system, question, temperature=0.3, max_tokens=800)
    return candidat, {"intent": intent, "mode": "conversation", "web": "", "examples": [], "errors": []}

def traiter_question(question, owner="anon", conversation_id=None):
    q = question.strip()
    if not q: return {"ok": False, "reponse": "Pose ta question"}
    candidat, contexte = pipeline_adrynx(q)
    controle = controler_parent(q, candidat, contexte)
    print(f"[ADRYNX] Q={q[:50]} | Intent={contexte.get('intent')} | Valide={controle['valide']} | Video={PHOENIX_VIDEO}")
    return {"ok": True, "reponse": controle["reponse"], "intent": contexte.get("intent"), "confiance": controle.get("confiance", 0.9), "parents": controle.get("parents", []), "video_core": PHOENIX_VIDEO}

def new_conversation(owner, titre): return "conv_123"
def state(cid): return {}
def messages(cid, n): return []
def dashboard(o): return {"video": PHOENIX_VIDEO}
def projects(o): return []
def project(o,n,obj): return {"nom":n}
def task(o,t,pid): return {"titre":t}
def enregistrer_feedback(*a): return {"ok":True}
def stats_apprentissage(): return {"parents":"unique","video":PHOENIX_VIDEO}
def exporter_apprentissage(): return []
def verifier_admin(s): return s=="adrynx_secret_2026"
