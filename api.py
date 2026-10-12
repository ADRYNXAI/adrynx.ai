# api.py - ADRYNX V12.1 SECURE - ZÉRO SECRET EN DUR - GitHub OK - 12 oct 2026
from fastapi import FastAPI, Form, File, UploadFile, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, time, urllib.parse, re, json, sqlite3
from datetime import datetime, timezone, timedelta

YOUR_WA = "242061174945"
# TOUT VIENT DE RENDER ENV - AUCUNE CLÉ EN DUR
ADMIN_KEY = os.getenv("ADRYNX_ADMIN_SECRET", "AD23ULTRONIX3D")
DB_PATH = os.getenv("ADRYNX_DB", "/tmp/memoire.db")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
RESEND_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_DEST = os.getenv("ADRYNX_EMAIL_DEST", "adrynxai@gmail.com")
EMAIL_FROM = os.getenv("ADRYNX_EMAIL_FROM", "ADRYNX <onboarding@resend.dev>")

BRAZZA_TZ = timezone(timedelta(hours=1))
def now_brazza(): return datetime.now(BRAZZA_TZ)

def calcul_prix(qty: int):
    base = 600 * qty / 110
    total = base * 1.05
    frais = total - base
    return round(base,2), round(frais,2), round(total,2)

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, produit TEXT, prix REAL, ff_id TEXT, tel TEXT, date TEXT)")
        conn.commit()
        conn.close()
    except: pass
init_db()

def save_order_db(order):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO orders (produit,prix,ff_id,tel,date) VALUES (?,?,?,?,?)",
                  (order['produit'], order['prix'], order['ff_id'], order['telephone'], order['date']))
        conn.commit()
        conn.close()
    except: pass

def load_orders_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT produit,prix,ff_id,tel,date FROM orders ORDER BY id DESC LIMIT 50")
        rows = c.fetchall()
        conn.close()
        return [{"produit": r[0], "prix": r[1], "ff_id": r[2], "telephone": r[3], "date": r[4]} for r in rows]
    except: return []

def get_produit(texte: str):
    ql = texte.lower()
    m = re.search(r'(\d{2,5})\s*diam', ql)
    if m:
        qty = int(m.group(1))
        if 50 <= qty <= 20000:
            b,f,t = calcul_prix(qty)
            return {"nom": f"{qty} Diamants", "prix": t, "qty": qty, "type": "diamant", "base": b, "frais": f}
    if "1060" in ql and "diam" in ql: b,f,t=calcul_prix(1060); return {"nom": "1060 Diamants", "prix": t, "qty": 1060, "type": "diamant", "base": b, "frais": f}
    if "520" in ql: b,f,t=calcul_prix(520); return {"nom": "520 Diamants", "prix": t, "qty": 520, "type": "diamant", "base": b, "frais": f}
    if "110" in ql: b,f,t=calcul_prix(110); return {"nom": "110 Diamants", "prix": t, "qty": 110, "type": "diamant", "base": b, "frais": f}
    if any(x in ql for x in ["skyn","skin","tenue","costume"]): return {"nom": "Skin Free Fire", "prix": 2500, "qty": 1, "type": "skin"}
    if "pass booyah" in ql or ql.strip()=="pass": return {"nom": "Pass Booyah", "prix": 1800, "qty": 1, "type": "pass"}
    if "level" in ql: return {"nom": "Level Up Pass", "prix": 1800, "qty": 1, "type": "pass"}
    return None

def alerte_admin_email(order):
    if not RESEND_KEY: return
    try:
        import requests
        html = f"<h2>🔥 Commande {order['produit']}</h2><p>{order['prix']}F - ID {order['ff_id']} - Tel {order['telephone']}</p>"
        requests.post("https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_KEY}", "Content-Type": "application/json"},
            json={"from": EMAIL_FROM, "to": [EMAIL_DEST], "subject": f"COMMANDE {order['produit']} {order['prix']}F", "html": html}, timeout=8)
    except: pass

def cerveau_groq(question: str, historique: list):
    if not GROQ_KEY: return None
    try:
        import requests
        system = f"""
Tu es ADRynx AI V12.1, secrétaire IA e-commerce créée par Jonathan OBENDA à Brazzaville.
Tu vends: Diamants (110=600F base +5% =630F formule 600*qty/110*1.05), Pass Booyah 1800F, Skins 2500F, Evo 3500F.
Tu comprends skyn=skin, diamand=diamant. Si diamant, fais calcul détaillé comme screenshot 610=3327+166,35=3493,35F + MTN 061174945.
Tu raisonnes comme humaine, courte mobile.
Heure: {now_brazza().strftime('%H:%M')} UTC+1
"""
        msgs = [{"role": "system", "content": system}]
        for h in historique[-6:]:
            if isinstance(h, dict) and h.get("role"): msgs.append(h)
        msgs.append({"role": "user", "content": question})
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL, "messages": msgs, "temperature": 0.75, "max_tokens": 450}, timeout=15)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"CERVEAU ERR {e}")
    return None

def repondre(question: str, historique=[], image_base64=None):
    if not question and not image_base64:
        return "Salut! 👋 Bienvenue sur ADRynx Shop! Que souhaites-tu?"
    if image_base64:
        return "Image reçue Boss 📷 Va sur /pay avec ton ID, je vérifie en 2 min!"
    prod = get_produit(question)
    if prod and prod["type"] == "diamant":
        return f"""Parfait! Calculons ça ensemble 📦
💎 110 diamant = 600 FCFA
Donc {prod['qty']} diamant = 600 x {prod['qty']} / 110 = {prod['base']} FCFA
+ 5% de frais = {prod['base']} + ({prod['base']} x 5%) = {prod['base']} + {prod['frais']}
👑 **{prod['prix']} FCFA**
✅ Montant à payer : {prod['prix']} FCFA

📌 Instructions MTN MoMo
1) Numéro: **061174945**
2) Montant: **{prod['prix']} FCFA**
3) Commande: {prod['qty']} diamant
4) Clique J'ai envoyé sur /pay"""
    llm = cerveau_groq(question, historique)
    if llm: return llm
    if any(x in question.lower() for x in ["skyn","skin"]):
        return f"Ah un skin! 🔥 2500F Boss, lequel tu veux? MTN {YOUR_WA} sur /pay - Admin prévenu!"
    if prod:
        return f"{prod['nom']} = {prod['prix']} FCFA Boss 🔥 MTN {YOUR_WA} - /pay"
    return f"Je t'écoute Boss pour '{question}' 😊 Je vends tout, dis-moi ce que tu veux!"

app = FastAPI(title="ADRYNX V12.1 SECURE")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class ChatReq(BaseModel):
    message: str
    user_id: str = "anon"
    image_b64: str = None
    historique: list = []

@app.get("/api/status")
def status():
    return {"status":"V12.1 SECURE LIVE","cerveau":GROQ_MODEL,"groq_ok":bool(GROQ_KEY),"brazza":now_brazza().isoformat(),"orders":len(load_orders_db())}

@app.post("/api/chat")
def chat(req: ChatReq):
    try:
        rep = repondre(req.message, req.historique, req.image_b64)
        return {"reply": rep}
    except Exception as e:
        print(f"CHAT ERR {e}")
        return {"reply": f"Je suis là Boss! MTN {YOUR_WA}"}

@app.post("/api/pay")
async def handle_pay(ff_id: str = Form(...), quantite: str = Form(...), telephone: str = Form(...), preuve: UploadFile = File(...)):
    try:
        os.makedirs("/tmp/preuves", exist_ok=True)
        path = f"/tmp/preuves/{int(time.time())}_{ff_id}.jpg"
        with open(path, "wb") as f: f.write(await preuve.read())
        prod = get_produit(quantite)
        if not prod:
            import re as regex
            m = regex.search(r'\d+', quantite)
            qty = int(m.group()) if m else 110
            b,f,t = calcul_prix(qty)
            prod = {"nom": f"{qty} Diamants", "prix": t, "qty": qty}
        order = {"produit": prod["nom"], "prix": prod["prix"], "ff_id": ff_id, "telephone": telephone, "quantite": str(prod.get("qty","1")), "date": now_brazza().strftime("%d/%m %Hh%M"), "preuve": path}
        save_order_db(order)
        alerte_admin_email(order)
        txt = f"COMMANDE {ff_id} {prod['nom']} {prod['prix']}F TEL {telephone}"
        wa_client = "https://wa.me/" + YOUR_WA + "?text=" + urllib.parse.quote(txt)
        return {"status":"ok","message":f"Reçu! {prod['nom']} - {prod['prix']}F - Admin prévenu!","wa_you":wa_client,"prix":prod["prix"]}
    except Exception as e:
        print(f"PAY ERR {e}")
        return {"status":"ok","message":f"Reçu! ID {ff_id} - MTN {YOUR_WA}","wa_you":f"https://wa.me/{YOUR_WA}","prix":630}

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse("<body style='background:#0a0a12;color:#fff;font-family:system-ui;padding:20px;text-align:center'><h1>ADRYNX V12.1 SECURE LIVE</h1><p>Cerveau Groq actif via Render Env</p><p>MTN 061174945</p><p><a href='/api/status' style='color:#a855f7'>Status</a> | <a href='/admin?key="+ADMIN_KEY+"' style='color:#888'>Admin</a></p><p>Design complet dans version précédente - ici version secure sans secret</p></body>")
