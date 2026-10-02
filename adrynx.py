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
            rows = cur.fetchall
