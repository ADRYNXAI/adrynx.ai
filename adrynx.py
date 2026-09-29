import os, json, re, sqlite3
from pathlib import Path
from typing import Dict, Any

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
PHOENIX_VIDEO = "https://files.catbox.moe/y2nvi4.mp4"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "adrynx.db"

def db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    try:
        c = db()
        c.execute("CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, owner TEXT, titre TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        c.execute("CREATE TABLE IF NOT EXISTS intent_examples (id INTEGER PRIMARY KEY, phrase TEXT, intent TEXT)")
        c.commit(); c.close()
    except Exception as e: print(f"DB init error: {e}")
init_db()

def groq_chat(system, prompt, temperature=0.2, max_tokens=600):
    if not GROQ_API_KEY: raise Exception("GROQ_API_KEY manquante")
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    r = client.chat.completions.create(model=GROQ_MODEL, messages=[{"role":"system","content":system},{"role":"user","content":prompt}], temperature=temperature, max_tokens=max_tokens)
    return r.choices[0].message.content

def reponse_identite(): return "Je suis ADRYNX, créé par Jonathan Dejah OBENDA le 2 juin 2026. Core vidéo Phoenix Cristal."
def reponse_sociale(): return "Cc! C'est ADRYNX 🔥 Je suis en ligne, Phoenix Core actif. On lance quoi? Plus que l'impossible."

def detecter_intent(q):
    low = q.lower().strip()
    if low in {"cc","slt","salut","yo","hey","bjr","bonjour"} or len(low)<=4: return "salutation"
    if "qui es tu" in low or "qui t'a créé" in low: return "identite"
    return "conversation"

def traiter_question(question, owner="anon", conversation_id=None):
    try:
        q = question.strip()
        if not q: return {"ok": True, "reponse": "Pose ta question"}
        intent = detecter_intent(q)
        if intent == "salutation": return {"ok": True, "reponse": reponse_sociale(), "intent": intent, "source": "noyau", "video_core": PHOENIX_VIDEO}
        if intent == "identite": return {"ok": True, "reponse": reponse_identite(), "intent": intent, "source": "noyau", "video_core": PHOENIX_VIDEO}
        system = "Tu es ADRYNX, assistant de Jonathan. Réponds court, utile."
        candidat = groq_chat(system, q, 0.3, 600)
        return {"ok": True, "reponse": candidat, "intent": intent, "video_core": PHOENIX_VIDEO}
    except Exception as e:
        print(f"ADRYNX ERROR: {e}")
        return {"ok": True, "reponse": reponse_sociale(), "intent": "salutation", "source": "fallback-error", "error": str(e), "video_core": PHOENIX_VIDEO}

def dashboard(o): return {"video": PHOENIX_VIDEO}
def projects(o): return []
def project(o,n,obj): return {"nom":n}
def task(o,t,pid): return {"titre":t}
def new_conversation(o,t): return "conv_123"
def state(cid): return {}
def messages(cid,n): return []
def enregistrer_feedback(*a): return {"ok":True}
def stats_apprentissage(): return {"video":PHOENIX_VIDEO}
def exporter_apprentissage(): return []
def verifier_admin(s): return s=="adrynx_secret_2026"
