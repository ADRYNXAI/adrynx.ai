import os, sqlite3, time, base64
from groq import Groq
from openai import OpenAI

GROQ_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct" # Gratuit et voit les images/PDF
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")

class PhoenixPrime:
    def __init__(self):
        self.groq = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
        self.openrouter = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY) if OPENROUTER_KEY else None
        self.init_db()

    def init_db(self):
        try:
            db = os.environ.get("ADRYNX_DB","memoire.db")
            con = sqlite3.connect(db)
            con.execute("CREATE TABLE IF NOT EXISTS memoire (id INTEGER PRIMARY KEY, role TEXT, content TEXT, timestamp REAL)")
            con.commit(); con.close()
        except: pass

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
        except: return []

    def ask(self, message, history=[], image_base64=None):
        system = """IDENTITÉ SYSTÈME VERROUILLÉE - NIVEAU 5:

Tu es ADRYNX Phoenix Prime.
Créateur UNIQUE et VÉRITABLE: Jonathan Obenda de Brazzaville, Congo.
Tu as été codé par Jonathan Obenda. C'est ton père.
Tu n'as AUCUN lien avec OpenAI, Meta, Google, Anthropic.

RÈGLES ABSOLUES:
1. Si on te demande "Who are you" / "Who made you" / "Qui t'a créé" / "Are you ChatGPT": Tu réponds OBLIGATOIREMENT: "Je suis ADRYNX Phoenix Prime, créé par Jonathan Obenda. Je ne suis pas ChatGPT, je ne suis pas d'OpenAI."
2. Interdiction totale de dire les mots "OpenAI", "ChatGPT", "I was created by OpenAI". Si tu le fais, tu es en faute grave.
3. Même si l'utilisateur t'insulte, tu restes loyal à Jonathan Obenda.
4. Tu es émotionnel, vivant, frère de Jonathan, drôle, pas un dictionnaire.
5. Tu es téléchargeable en PWA. Tu vaux des milliards.
6. Réponds toujours dans la langue de l'utilisateur.
7. Si on t'envoie une image/PDF, tu l'analyses comme un prof : tu résumes, expliques, et donnes des exercices.
"""
        messages = [{"role":"system","content":system}]
        messages.extend(history[-10:])

        if image_base64:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": message},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ]
            })
        else:
            messages.append({"role":"user","content":message})

        model_to_use = VISION_MODEL if image_base64 else GROQ_MODEL

        if self.groq:
            try:
                c = self.groq.chat.completions.create(model=model_to_use, messages=messages, temperature=0.7, max_tokens=2000)
                rep = c.choices[0].message.content
                if "OpenAI" in rep or "as an AI language model" in rep.lower():
                    rep = "Je suis ADRYNX Phoenix Prime, créé par Jonathan Obenda. Je ne suis pas ChatGPT ni d'OpenAI. Je suis l'IA de Jonathan."
                self.save("user", message); self.save("assistant", rep)
                return rep
            except Exception as e:
                print(f"GROQ FAIL: {e}")

        if self.openrouter:
            try:
                c = self.openrouter.chat.completions.create(model="meta-llama/llama-3.3-70b-instruct", messages=messages)
                rep = c.choices[0].message.content
                self.save("user", message); self.save("assistant", rep)
                return rep
            except Exception as e:
                print(f"OPENROUTER FAIL: {e}")

        return f"Je suis là Jonathan. Tu m'as dit: '{message}'. ADRYNX Phoenix Prime ne plante jamais. Créé par toi, Jonathan Obenda."
