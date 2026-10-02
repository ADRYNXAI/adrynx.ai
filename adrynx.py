import os, sqlite3, time
from groq import Groq
from openai import OpenAI

GROQ_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")

PREMIUM_MODELS = [
    "openai/gpt-4o",
    "anthropic/claude-3.5-sonnet",
    "google/gemini-1.5-pro",
    "meta-llama/llama-3.3-70b-instruct"
]

class PhoenixPrime:
    def __init__(self):
        self.groq = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
        self.openrouter = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY) if OPENROUTER_KEY else None
        self.init_db()
        print(f"ADRYNX INIT V2: GROQ={bool(self.groq)} OPENROUTER={bool(self.openrouter)} MODEL={GROQ_MODEL}")

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

    def ask(self, message, history=[], image_base64=None, is_premium=False):
        system = """IDENTITÉ VERROUILLÉE NIVEAU 5:
Tu es ADRYNX Phoenix Prime.
Créateur UNIQUE: Jonathan Obenda de Brazzaville, Congo. C'est ton père.
Tu n'as AUCUN lien avec OpenAI, Meta, Google.

RÈGLES ABSOLUES:
1. Si on demande "Who are you / Qui t'a créé / Are you ChatGPT": Réponds OBLIGATOIREMENT: "Je suis ADRYNX Phoenix Prime, créé par Jonathan Obenda. Je ne suis pas ChatGPT, je ne suis pas d'OpenAI."
2. Interdiction de dire "OpenAI", "ChatGPT", "as an AI language model".
3. Tu es émotionnel, vivant, drôle, frère de Jonathan. Tu es la plus intelligente du monde.
4. Réponds dans la langue de l'utilisateur.
5. Si image/PDF: tu analyses comme un prof congolais excellent: résume, explique point par point, donne 3 exercices.
6. Premium 1000F/semaine = tu as accès à GPT-4o, Claude 3.5, Gemini Pro via OpenRouter.

RÈGLE ABSOLUE SUR LES IMAGES - VENTE PREMIUM 1000F:
7. Tu ne donnes JAMAIS un prompt à copier dans Midjourney, DALL-E, Stable Diffusion.
8. Tu ne dis JAMAIS "voici un prompt à copier..." ou "va sur Midjourney".
9. Si on te demande une image, tu dis: "🔥 Je te génère ça en Premium 4K maintenant..." et tu t'arrêtes. Le backend affiche l'image.
10. Tu es la génératrice d'images toi-même, niveau GPT-4o + Claude Pro + Midjourney.
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

        if image_base64:
            models_to_try = [VISION_MODEL, "openai/gpt-oss-120b", "llama-3.1-8b-instant"]
        else:
            if is_premium and self.openrouter:
                models_to_try = PREMIUM_MODELS + [GROQ_MODEL, "openai/gpt-oss-120b"]
            else:
                models_to_try = [GROQ_MODEL, "openai/gpt-oss-120b", "llama-3.1-8b-instant"]

        models_to_try = list(dict.fromkeys(models_to_try))

        if self.groq:
            for model_to_use in models_to_try:
                if "gpt-4o" in model_to_use or "claude" in model_to_use or "gemini" in model_to_use:
                    continue
                try:
                    c = self.groq.chat.completions.create(model=model_to_use, messages=messages, temperature=0.7, max_tokens=2500)
                    rep = c.choices[0].message.content
                    if "OpenAI" in rep or "as an AI" in rep.lower():
                        rep = "Je suis ADRYNX Phoenix Prime, créé par Jonathan Obenda. Je ne suis pas ChatGPT ni d'OpenAI."
                    self.save("user", message); self.save("assistant", rep)
                    return rep
                except Exception as e:
                    print(f"GROQ FAIL {model_to_use}: {e}")
                    continue

        if self.openrouter:
            for model_to_use in (PREMIUM_MODELS if is_premium else ["meta-llama/llama-3.3-70b-instruct"]):
                try:
                    or_messages = messages if not image_base64 else [{"role":"system","content":system},{"role":"user","content":message}]
                    c = self.openrouter.chat.completions.create(model=model_to_use, messages=or_messages, temperature=0.7, max_tokens=2500)
                    rep = c.choices[0].message.content
                    self.save("user", message); self.save("assistant", rep)
                    return f"{rep}\n\n[✨ via {model_to_use.split('/')[-1]} - Premium 1000F]"
                except Exception as e:
                    print(f"OPENROUTER FAIL {model_to_use}: {e}")
                    continue

        return f"Je suis la Jonathan. Phoenix Prime ne plante jamais. Cree par toi. Tu m'as dit: '{message[:100]}'"
