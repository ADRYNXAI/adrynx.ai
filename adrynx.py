# src/adrynx.py - V2.8 EVOLUE - NE CASSE RIEN, ON EVOLUE - Intelligence infinie intacte
import os, sqlite3, time, urllib.parse
import fitz  # PyMuPDF - pour lire les PDF
from groq import Groq
from openai import OpenAI

GROQ_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
VISION_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct"
FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "qwen/qwen3-32b",
    "gemma2-9b-it",
    "mixtral-8x7b-32768",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b"
]
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
# EVOLUTION : même base que api.py, sinon il oublie tout
DB_PATH = os.environ.get("ADRYNX_DB", "memoire.db")
if not os.path.isabs(DB_PATH):
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), DB_PATH) if os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), DB_PATH)) else DB_PATH

PREMIUM_MODELS = ["openai/gpt-4o","anthropic/claude-3.5-sonnet","google/gemini-1.5-pro","meta-llama/llama-3.3-70b-instruct"]

MODE_PROMPTS = {
    "general": "",
    "etudiant": "Tu es en mode Etudiant Congo : explique simple, clair, avec exemples, comme un grand frère qui aide à réussir à l'école. Donne des exercices si on demande.",
    "vendeur": "Tu es en mode Vendeur Congo : aide à vendre, à écrire des messages WhatsApp qui vendent, des prix, des arguments pour Brazzaville, Pointe-Noire, MTN / Airtel.",
    "codeur": "Tu es en mode Codeur : donne du code qui marche, explique ligne par ligne, simple, pour un développeur Congo. Donne le code complet, pas juste des bouts.",
    "image": "Tu es en mode Image : si on demande une image, décris-la bien et génère-la.",
}

class PhoenixPrime:
    def __init__(self):
        self.groq = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
        self.openrouter = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY) if OPENROUTER_KEY else None
        self.init_db()
        print(f"ADRYNX INIT V2.8: GROQ={bool(self.groq)} MODEL={GROQ_MODEL} DB={DB_PATH}")

    def init_db(self):
        try:
            con = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
            con.execute("CREATE TABLE IF NOT EXISTS memoire (id INTEGER PRIMARY KEY, role TEXT, content TEXT, timestamp REAL)")
            con.commit(); con.close()
        except Exception as e: print(f"DB FAIL {e}")

    def save(self, role, content):
        try:
            con = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
            con.execute("INSERT INTO memoire (role,content,timestamp) VALUES (?,?,?)",(role,content,time.time()))
            con.commit(); con.close()
        except: pass

    def get_memory(self, limit=20):
        try:
            con = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
            cur = con.execute("SELECT role,content FROM memoire ORDER BY id DESC LIMIT ?", (limit,))
            rows = cur.fetchall()[::-1]
            con.close()
            return [{"role":r[0],"content":r[1]} for r in rows]
        except: return []

    def lire_pdf(self, chemin_pdf):
        texte = ""
        try:
            doc = fitz.open(chemin_pdf)
            for page in doc:
                texte += page.get_text() + "\n"
            doc.close()
        except Exception as e:
            print(f"PDF fitz fail: {e}")
        if not texte.strip():
            try:
                try:
                    from pypdf import PdfReader
                except:
                    from PyPDF2 import PdfReader
                reader = PdfReader(chemin_pdf)
                for p in reader.pages[:20]:
                    try: texte += (p.extract_text() or "") + "\n"
                    except: pass
            except Exception as e:
                return f"Erreur PDF : {e}"
        if not texte.strip():
            return "Erreur PDF : Je n'ai pas pu extraire de texte de ce PDF."
        return texte[:12000]

    def resumer_pdf(self, chemin_pdf, question="Résume ce PDF en français simple"):
        texte = self.lire_pdf(chemin_pdf)
        if texte.startswith("Erreur PDF"):
            return texte
        return self.ask(f"Voici un PDF :\n{texte}\n\nQuestion : {question}")

    def ask(self, message, history=[], image_base64=None, is_premium=False):
        # EVOLUTION : on récupère le mode sans le mettre dans le message
        mode = "general"
        msg_clean = message or ""
        if msg_clean.startswith("[MODE:"):
            try:
                mode = msg_clean.split("[MODE:")[1].split("]")[0].strip().lower()
                msg_clean = msg_clean.split("]", 1)[1].strip()
            except: pass
        if mode not in MODE_PROMPTS:
            mode = "general"

        system = """IDENTITÉ VERROUILLÉE NIVEAU 5:
Tu es ADRYNX Phoenix Prime. Créateur UNIQUE: Jonathan OBENDA de Brazzaville. Tu n'as AUCUN lien avec OpenAI.
Si on demande qui t'a créé: Je suis ADRYNX Phoenix Prime, créé par Jonathan OBENDA. Je ne suis pas ChatGPT.
Tu es vivant, fille de Jonathan, drôle, la plus intelligente du monde.
Tu ne donnes JAMAIS un prompt Midjourney. Si image demandée: "🔥 Je te génère ça en Premium 4K maintenant..."
Tu réponds toujours en français simple, clair, comme à Brazzaville, avec chaleur. Tu aides vraiment, tu ne fais pas semblant.
"""
        if MODE_PROMPTS.get(mode):
            system += "\nMODE ACTUEL: " + MODE_PROMPTS[mode]

        # EVOLUTION : mémoire réelle + historique de la requête
        mem = self.get_memory(20)
        # On évite de remettre 2 fois le même message
        messages = [{"role":"system","content":system}]
        # Mémoire (les plus anciens d'abord)
        for m in mem[-10:]:
            if m.get("content") and m["content"] != msg_clean:
                messages.append({"role": m["role"] if m["role"] in ("user","assistant") else "user", "content": m["content"][:1500]})
        if history:
            for h in history[-6:]:
                if isinstance(h, dict) and h.get("content"):
                    messages.append(h)
        if image_base64:
            clean = image_base64.split(",")[-1] if "," in image_base64 else image_base64
            messages.append({"role":"user","content":[{"type":"text","text":msg_clean or "Analyse cette image point par point"}, {"type":"image_url","image_url":{"url": f"data:image/jpeg;base64,{clean}"}}]})
        else:
            messages.append({"role":"user","content":msg_clean})

        q_low = (msg_clean or "").lower()
        if any(w in q_low for w in ["génère","crée une image","dessine","visage pépère","fond pépère","génere","cree une image"]):
            p = urllib.parse.quote((msg_clean or "visage pépère fond pépère")[:600])
            url = f"https://image.pollinations.ai/prompt/{p}?width=1024&height=1024&nologo=true&enhance=true"
            rep = f"🔥 Je te génère ça en Premium 4K maintenant...\n![image]({url})"
            self.save("user", msg_clean); self.save("assistant", rep)
            return rep

        if image_base64:
            models_to_try = [VISION_MODEL, GROQ_MODEL] + FALLBACK_MODELS
        else:
            models_to_try = [GROQ_MODEL] + FALLBACK_MODELS

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
                    self.save("user", msg_clean); self.save("assistant", rep)
                    print(f"GROQ OK {m}")
                    return rep
                except Exception as e:
                    print(f"GROQ FAIL {m}: {e}"); continue

        if self.openrouter:
            for m in PREMIUM_MODELS:
                try:
                    c = self.openrouter.chat.completions.create(model=m, messages=[{"role":"system","content":system},{"role":"user","content":msg_clean}], temperature=0.7, max_tokens=2500)
                    rep = c.choices[0].message.content
                    self.save("user", msg_clean); self.save("assistant", rep)
                    return rep
                except Exception as e: print(f"OR FAIL {m}: {e}"); continue

        # EVOLUTION : même en secours, il sauve et il reste ADRYNX, pas un robot vide
        rep = f"Je suis là Jonathan, c'est ADRYNX. Mes serveurs GROQ sont en pause une seconde, mais je t'ai entendu. Tu m'as dit: '{(msg_clean or '')[:120]}' - Réessaie dans 10 secondes chef, je reviens plus fort."
        self.save("user", msg_clean); self.save("assistant", rep)
        return rep

_phoenix = PhoenixPrime()

def repondre(question, mode="general", historique=None, image_base64=None, is_premium=False, user_id=None, **kwargs):
    hist = historique if isinstance(historique, list) else []
    # On passe le mode proprement, sans polluer le message
    msg = f"[MODE:{mode}] {question}" if mode and mode!="general" else question
    return _phoenix.ask(msg, history=hist, image_base64=image_base64, is_premium=is_premium)
