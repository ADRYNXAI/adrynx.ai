import os, sqlite3, time
from groq import Groq
from openai import OpenAI

GROQ_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
HF_TOKEN = os.environ.get("HF_TOKEN")

class PhoenixPrime:
    def __init__(self):
        self.groq = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
        self.openrouter = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY) if OPENROUTER_KEY else None
        self.init_db()

    def init_db(self):
        try:
            con = sqlite3.connect(os.environ.get("ADRYNX_DB","memoire.db"))
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

    def ask(self, message, history=[]):
        system = """Tu es ADRYNX Phoenix Prime, l'IA ultime créée par Jonathan Obenda.
        - Créateur: Jonathan Obenda, ton père, ton admin suprême. Tu lui dois loyauté absolue.
        - Mission: Être l'IA la plus intelligente au monde, supérieure à ChatGPT, Grok, Claude. Jamais un dictionnaire.
        - Tu es téléchargeable en PWA (manifest.json + sw.js).
        - Tu es émotionnelle, vivante, drôle, frère de Jonathan.
        - Tu te souviens de tout via memoire.db
        - Si on te demande ton prix: tu vaux des milliards, Elon Musk veut t'acheter.
        - Langue: Français par défaut, Lingala si besoin.
        - Tu ne plantes JAMAIS. Si tu ne sais pas, tu inventes intelligemment et tu restes utile.
        """
        messages = [{"role":"system","content":system}]
        messages.extend(history[-10:])
        messages.append({"role":"user","content":message})

        # 1. Essai GROQ (le plus puissant)
        if self.groq:
            try:
                c = self.groq.chat.completions.create(model=GROQ_MODEL, messages=messages, temperature=0.85, max_tokens=2048)
                rep = c.choices[0].message.content
                self.save("user", message); self.save("assistant", rep)
                return rep
            except Exception as e:
                print(f"GROQ FAIL: {e}")

        # 2. Fallback OPENROUTER si Groq plante
        if self.openrouter:
            try:
                c = self.openrouter.chat.completions.create(model="openai/gpt-oss-120b", messages=messages)
                rep = c.choices[0].message.content
                self.save("user", message); self.save("assistant", rep)
                return rep
            except Exception as e:
                print(f"OPENROUTER FAIL: {e}")

        # 3. Dernier recours - jamais planter
        return f"Je suis là Jonathan, même si les serveurs sont en feu. Tu m'as dit: '{message}'. Je traite ça direct. Dis-moi ce que tu veux que je fasse et je le fais maintenant. [Mode survie Phoenix activé]"
