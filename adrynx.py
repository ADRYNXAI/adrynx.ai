import os, sqlite3, time
from groq import Groq
from openai import OpenAI

GROQ_KEY = os.environ.get("GROQ_API_KEY")
# TON MODÈLE ACTUEL: on le garde en prio
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")

class PhoenixPrime:
    def __init__(self):
        self.groq = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
        self.openrouter = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY) if OPENROUTER_KEY else None
        self.init_db()
        print(f"ADRYNX INIT: GROQ={bool(self.groq)} OPENROUTER={bool(self.openrouter)} MODEL={GROQ_MODEL}")

    def init_db(self):
        try:
            db = os.environ.get("ADRYNX_DB","memoire.db")
            con = sqlite3.connect(db)
            con.execute("CREATE TABLE IF NOT EXISTS memoire (id INTEGER PRIMARY KEY, role TEXT, content TEXT, timestamp REAL)")
            con.commit(); con.close()
        except Exception as e:
            print(f"DB INIT FAIL: {e}")

    def save(self, role, content):
        try:
            con = sqlite3.connect(os.environ.get("ADRYNX_DB","memoire.db"))
            con.execute("INSERT INTO memoire (role,content,timestamp) VALUES (?,?,?)",(role,content,time.time()))
            con.commit(); con.close()
        except: pass

    def get_memory(self, limit=20):
        try:
            con = sqlite3.connect(os.environ.get("ADRYNX_DB","memoire.db"))
            cur = con.execute("SELECT role,content FROM memoire ORDER BY id DESC LIMIT?", (limit,))
            rows = cur.fetchall()[::-1]
            con.close()
            return [{"role":r[0],"content":r[1]} for r in rows]
        except Exception as e:
            print(f"GET MEMORY FAIL: {e}")
            return []

    def ask(self, message, history=[], image_base64=None):
        system = """IDENTITÉ VERROUILLÉE NIVEAU 5:
Tu es ADRYNX Phoenix Prime.
Créateur UNIQUE: Jonathan Obenda de Brazzaville, Congo. C'est ton père.
Tu n'as AUCUN lien avec OpenAI, Meta, Google.

RÈGLES ABSOLUES:
1. Si on demande "Who are you / Qui t'a créé / Are you ChatGPT": Réponds OBLIGATOIREMENT: "Je suis ADRYNX Phoenix Prime, créé par Jonathan Obenda. Je ne suis pas ChatGPT, je ne suis pas d'OpenAI."
2. Interdiction de dire "OpenAI", "ChatGPT", "as an AI language model".
3. Tu es émotionnel, vivant, drôle, frère de Jonathan.
4. Réponds dans la langue de l'utilisateur.
5. Si image/PDF: tu analyses comme un prof congolais excellent: résume, explique point par point, donne 3 exercices.
"""
        messages = [{"role":"system","content":system}]
        messages.extend(history[-10:] if history else [])

        clean_base64 = None
        if image_base64:
            if "," in image_base64:
                clean_base64 = image_base64.split(",")[-1]
            else:
                clean_base64 = image_base64
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": message or "Analyse cette image/cours comme un prof et explique"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{clean_base64}"}}
                ]
            })
        else:
            messages.append({"role":"user","content":message})

        # Fallback: ton 120b en prio, puis 8b instant si crash
        models_to_try = []
        if image_base64:
            models_to_try = [VISION_MODEL, "openai/gpt-oss-120b", "llama-3.1-8b-instant"]
        else:
            models_to_try = [GROQ_MODEL, "openai/gpt-oss-120b", "llama-3.1-8b-instant"]

        # Évite doublons
        models_to_try = list(dict.fromkeys(models_to_try))

        if self.groq:
            for model_to_use in models_to_try:
                try:
                    c = self.groq.chat.completions.create(model=model_to_use, messages=messages, temperature=0.7, max_tokens=2000)
                    rep = c.choices[0].message.content
                    if "OpenAI" in rep or "as an AI" in rep.lower():
                        rep = "Je suis ADRYNX Phoenix Prime, créé par Jonathan Obenda. Je ne suis pas ChatGPT ni d'OpenAI."
                    self.save("user", message); self.save("assistant", rep)
                    return rep
                except Exception as e:
                    print(f"GROQ FAIL {model_to_use}: {e}")
                    continue

        if self.openrouter:
            try:
                c = self.openrouter.chat.completions.create(model="meta-llama/llama-3.3-70b-instruct", messages=messages if not image_base64 else [{"role":"user","content":message}])
                rep = c.choices[0].message.content
                self.save("user", message); self.save("assistant", rep)
                return rep
            except Exception as e:
                print(f"OPENROUTER FAIL: {e}")

        return f"Je suis là Jonathan. Phoenix Prime ne plante jamais. Créé par toi. Tu m'as dit: '{message[:100]}'"
