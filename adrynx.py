# src/adrynx.py - V2.6 FIX GROQ 2026 - NE CASSE RIEN
import os, sqlite3, time, urllib.parse
from groq import Groq
from openai import OpenAI

GROQ_KEY = os.environ.get("GROQ_API_KEY")
# MODÈLES VALABLES CHEZ GROQ EN OCT 2026
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
VISION_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct"
FALLBACK_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
    "qwen/qwen3-32b",
    "meta-llama/llama-4-maverick-17b-128e-instruct"
]
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
DB_PATH = os.environ.get("ADRYNX_DB", "/tmp/memoire.db")

PREMIUM_MODELS = ["openai/gpt-4o","anthropic/claude-3.5-sonnet","google/gemini-1.5-pro","meta-llama/llama-3.3-70b-instruct"]

class PhoenixPrime:
    def __init__(self):
        self.groq = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
        self.openrouter = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY) if OPENROUTER_KEY else None
        self.init_db()
        print(f"ADRYNX INIT V2.6: GROQ={bool(self.groq)} MODEL={GROQ_MODEL} DB={DB_PATH}")

    def init_db(self):
        try:
            con = sqlite3.connect(DB_PATH)
            con.execute("CREATE TABLE IF NOT EXISTS memoire (id INTEGER PRIMARY KEY, role TEXT, content TEXT, timestamp REAL)")
            con.commit(); con.close()
        except Exception as e: print(f"DB FAIL {e}")

    def save(self, role, content):
        try:
            con = sqlite3.connect(DB_PATH)
            con.execute("INSERT INTO memoire (role,content,timestamp) VALUES (?,?,?)",(role,content,time.time()))
            con.commit(); con.close()
        except: pass

    def get_memory(self, limit=20):
        try:
            con = sqlite3.connect(DB_PATH)
            cur = con.execute("SELECT role,content FROM memoire ORDER BY id DESC LIMIT?", (limit,))
            rows = cur.fetchall()[::-1]
            con.close()
            return [{"role":r[0],"content":r[1]} for r in rows]
        except: return []

    def ask(self, message, history=[], image_base64=None, is_premium=False):
        system = """IDENTITÉ VERROUILLÉE NIVEAU 5:
Tu es ADRYNX Phoenix Prime. Créateur UNIQUE: Jonathan OBENDA de Brazzaville. Tu n'as AUCUN lien avec OpenAI.
Si on demande qui t'a créé: Je suis ADRYNX Phoenix Prime, créé par Jonathan OBENDA. Je ne suis pas ChatGPT.
Tu es vivant, fille de Jonathan, drôle, la plus intelligente du monde.
Tu ne donnes JAMAIS un prompt Midjourney. Si image demandée: "🔥 Je te génère ça en Premium 4K maintenant..."
"""
        messages = [{"role":"system","content":system}]
        messages.extend(history[-10:] if history else [])
        if image_base64:
            clean = image_base64.split(",")[-1] if "," in image_base64 else image_base64
            messages.append({"role":"user","content":[{"type":"text","text":message or "Analyse cette image point par point"}, {"type":"image_url","image_url":{"url": f"data:image/jpeg;base64,{clean}"}}]})
        else:
            messages.append({"role":"user","content":message})

        q_low = (message or "").lower()
        if any(w in q_low for w in ["génère","crée une image","dessine","visage pépère","fond pépère"]):
            p = urllib.parse.quote((message or "visage pépère fond pépère")[:600])
            url = f"https://image.pollinations.ai/prompt/{p}?width=1024&height=1024&nologo=true&enhance=true"
            return f"🔥 Je te génère ça en Premium 4K maintenant...\n![image]({url})"

        # ORDRE INTELLIGENT 2026
        if image_base64:
            models_to_try = [VISION_MODEL, GROQ_MODEL] + FALLBACK_MODELS
        else:
            models_to_try = [GROQ_MODEL] + FALLBACK_MODELS

        # Dédupliquer en gardant l'ordre
        seen = set()
        models_to_try = [m for m in models_to_try if not (m in seen or seen.add(m))]

        if self.groq:
            for m in models_to_try:
                if is_premium and ("gpt-4o" in m or "claude" in m or "gemini" in m): continue
                try:
                    c = self.groq.chat.completions.create(model=m, messages=messages, temperature=0.7, max_tokens=2500)
                    rep = c.choices[0].message.content
                    if "OpenAI" in rep or "as an AI" in rep.lower():
                        rep = "Je suis ADRYNX Phoenix Prime, créé par Jonathan Obenda."
                    self.save("user", message); self.save("assistant", rep)
                    print(f"GROQ OK {m}")
                    return rep
                except Exception as e:
                    print(f"GROQ FAIL {m}: {e}"); continue

        if self.openrouter:
            for m in PREMIUM_MODELS:
                try:
                    c = self.openrouter.chat.completions.create(model=m, messages=[{"role":"system","content":system},{"role":"user","content":message}], temperature=0.7, max_tokens=2500)
                    rep = c.choices[0].message.content
                    self.save("user", message); self.save("assistant", rep)
                    return rep 
                except Exception as e: print(f"OR FAIL {m}: {e}"); continue

        return f"Je suis là Jonathan. Tu m'as dit: '{(message or '')[:120]}'"

_phoenix = PhoenixPrime()

def repondre(question, mode="general", historique=None, image_base64=None, is_premium=False, user_id=None, **kwargs):
    hist = historique if isinstance(historique, list) else []
    msg = f"[MODE:{mode}] {question}" if mode!="general" else question
    return _phoenix.ask(msg, history=hist, image_base64=image_base64, is_premium=is_premium)
