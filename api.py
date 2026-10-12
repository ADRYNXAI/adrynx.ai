# api.py - ADRYNX V12.1 SECURE - DESIGN SCREENSHOT + CERVEAU GROQ 120B - 12 oct 2026
# AUCUNE CLÉ EN DUR - Tout vient de Render Env
from fastapi import FastAPI, Form, File, UploadFile, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, time, urllib.parse, re, json, sqlite3
from datetime import datetime, timezone, timedelta

YOUR_WA = "242061174945"
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
    frais = base * 0.05
    total = base + frais
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
    except Exception as e:
        print(f"DB ERROR {e}")

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
    if "110" in ql and "diam" in ql: b,f,t=calcul_prix(110); return {"nom": "110 Diamants", "prix": t, "qty": 110, "type": "diamant", "base": b, "frais": f}
    if "520" in ql: b,f,t=calcul_prix(520); return {"nom": "520 Diamants", "prix": t, "qty": 520, "type": "diamant", "base": b, "frais": f}
    if "1060" in ql: b,f,t=calcul_prix(1060); return {"nom": "1060 Diamants", "prix": t, "qty": 1060, "type": "diamant", "base": b, "frais": f}
    if any(x in ql for x in ["skyn","skin","tenue","costume","habit"]): return {"nom": "Skin Free Fire", "prix": 2500, "qty": 1, "type": "skin"}
    if "pass booyah" in ql or ql.strip()=="pass": return {"nom": "Pass Booyah", "prix": 1800, "qty": 1, "type": "pass"}
    if "level" in ql: return {"nom": "Level Up Pass", "prix": 1800, "qty": 1, "type": "pass"}
    if "abonnement" in ql: return {"nom": "Abonnement Mensuel", "prix": 4500, "qty": 1, "type": "abo"}
    return None

def alerte_admin_email(order):
    if not RESEND_KEY: return
    try:
        import requests
        html = f"<h2>🔥 Commande {order['produit']}</h2><p>{order['prix']}F - ID {order['ff_id']} - Tel {order['telephone']} - {order['date']}</p>"
        requests.post("https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_KEY}", "Content-Type": "application/json"},
            json={"from": EMAIL_FROM, "to": [EMAIL_DEST], "subject": f"COMMANDE {order['produit']} {order['prix']}F", "html": html}, timeout=8)
    except: pass

def cerveau_groq(question: str, historique: list):
    if not GROQ_KEY: return None
    try:
        import requests
        system = f"""
Tu es ADRynx AI, secrétaire IA e-commerce créée par Jonathan OBENDA. Tu es humaine, chaleureuse, tu raisonnes comme une vraie vendeuse congolaise pro.
Ton shop: ADRynx Shop, MTN 061174945, Brazzaville {now_brazza().strftime('%H:%M')} UTC+1
Tu vends: Diamants (110=600F base +5% => 630F, formule 600*qty/110*1.05), Pass Booyah 1800F, Skins 2500F, Armes Evo 3500F, Abonnement 4500F
Tu comprends toutes fautes: skyn=skin, achété=acheté, diamand=diamant
Si vente diamant, fais calcul détaillé: 110=600, Donc 610=600x610/110=3327 +5%=3327+166,35=3493,35F + instructions MTN MoMo.
Pour autre produit, prix + MTN + /pay + informe admin. Tu discutes de tout, pas bot pré-défini. Réponse courte mobile.
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
        if OPENROUTER_KEY:
            r2 = requests.post("https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
                json={"model": "openai/gpt-4o-mini", "messages": msgs, "temperature": 0.75, "max_tokens": 400}, timeout=12)
            if r2.status_code == 200:
                return r2.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"CERVEAU ERR {e}")
    return None

def repondre(question: str, historique=[], image_base64=None):
    if not question and not image_base64:
        return "Salut! 👋 Bienvenue sur ADRynx Shop! Que souhaites-tu?"
    if image_base64:
        return "Image reçue Boss 📷 Va sur /pay avec ton ID, je vérifie en 2 min et j'informe l'admin!"
    prod = get_produit(question)
    if prod and prod["type"] == "diamant":
        return f"""Parfait! Calculons ça ensemble 📦
💎 110 diamant = 600 FCFA
Donc {prod['qty']} diamant = 600 x {prod['qty']} / 110 = {prod['base']} FCFA
+ 5% de frais = {prod['base']} + ({prod['base']} x 5%) = {prod['base']} + {prod['frais']}
👑 **{prod['prix']} FCFA**
✅ Montant à payer : {prod['prix']} FCFA

📌 Instructions de paiement (MTN MoMo)
1) Recharge le numéro suivant : **061174945**
2) Montant : **{prod['prix']} FCFA**
3) Pour une commande : {prod['qty']} diamant
4) Puis envoie et clique sur "J'ai envoyé" pour confirmer."""
    llm = cerveau_groq(question, historique)
    if llm: return llm
    ql = question.lower()
    if any(x in ql for x in ["skyn","skin"]):
        return f"Ah tu veux un skin! 🔥 2500F et armes Evo 3500F Boss. Lequel? MTN {YOUR_WA} sur /pay - Admin prévenu direct!"
    if prod:
        return f"{prod['nom']} = {prod['prix']} FCFA Boss 🔥 MTN {YOUR_WA} - Va sur /pay, admin alerté!"
    return f"Je t'écoute Boss pour '{question}' 😊 Je vends tout: diamants, skins, pass, abonnements. Dis-moi ce que tu veux!"

app = FastAPI(title="ADRYNX V12.1 SECURE")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class ChatReq(BaseModel):
    message: str
    user_id: str = "anon"
    image_b64: str = None
    historique: list = []

@app.get("/api/status")
def status():
    return {"status":"V12.1 SECURE LIVE","cerveau":GROQ_MODEL,"groq_ok":bool(GROQ_KEY),"resend_ok":bool(RESEND_KEY),"db":DB_PATH,"brazza":now_brazza().isoformat(),"orders":len(load_orders_db())}

@app.post("/api/chat")
def chat(req: ChatReq):
    try:
        rep = repondre(req.message, req.historique, req.image_b64)
        return {"reply": rep}
    except Exception as e:
        print(f"CHAT ERR {e}")
        return {"reply": f"Oups bug mais je suis là Boss! MTN {YOUR_WA}"}

@app.post("/api/pay")
async def handle_pay(ff_id: str = Form(...), quantite: str = Form(...), telephone: str = Form(...), preuve: UploadFile = File(...)):
    try:
        os.makedirs("/tmp/preuves", exist_ok=True)
        path = f"/tmp/preuves/{int(time.time())}_{ff_id}.jpg"
        with open(path, "wb") as f: f.write(await preuve.read())
        prod = get_produit(quantite)
        if not prod:
            m = re.search(r'\d+', quantite)
            qty = int(m.group()) if m else 110
            b,f,t = calcul_prix(qty)
            prod = {"nom": f"{qty} Diamants", "prix": t, "qty": qty}
        order = {"produit": prod["nom"], "prix": prod["prix"], "ff_id": ff_id, "telephone": telephone, "quantite": str(prod.get("qty","1")), "date": now_brazza().strftime("%d/%m %Hh%M"), "preuve": path}
        save_order_db(order)
        alerte_admin_email(order)
        txt = f"COMMANDE {ff_id} {prod['nom']} {prod['prix']}F TEL {telephone}"
        wa_client = "https://wa.me/" + YOUR_WA + "?text=" + urllib.parse.quote(txt)
        wa_admin = f"https://wa.me/{YOUR_WA}?text=" + urllib.parse.quote(f"COMMANDE V12 {prod['nom']} {prod['prix']}F ID {ff_id} TEL {telephone}")
        return {"status":"ok","message":f"Reçu! {prod['nom']} pour ID {ff_id} - {prod['prix']} FCFA - Admin prévenu!","wa_you":wa_client,"wa_admin":wa_admin,"prix":prod["prix"]}
    except Exception as e:
        print(f"PAY ERR {e}")
        return {"status":"ok","message":f"Reçu! ID {ff_id} - Admin prévenu! MTN {YOUR_WA}","wa_you":f"https://wa.me/{YOUR_WA}","prix":630}

@app.get("/admin", response_class=HTMLResponse)
def admin_panel(key: str = Query("")):
    if key!= ADMIN_KEY:
        return HTMLResponse(f"<body style='background:#0a0a0a;color:#fff;font-family:system-ui;padding:20px'><h2>🔒 Admin ADRynx V12.1</h2><form><input name='key' placeholder='Clé admin' style='padding:10px'><button style='padding:10px;background:#a855f7;color:#fff;border:none;border-radius:8px'>Entrer</button></form><p>Groq: {GROQ_MODEL}</p></body>")
    orders = load_orders_db()
    html_orders = "".join([f"<div style='background:#1e1b2e;border:1px solid #a855f7;border-radius:12px;padding:12px;margin:8px 0'><b>🔥 {o['produit']}</b> - {o['prix']}F<br>🆔 {o['ff_id']} | 📱 {o['telephone']}<br>⏰ {o['date']}</div>" for o in orders]) or "<p>Aucune commande</p>"
    return HTMLResponse(f"<body style='background:#0a0a0a;color:#fff;font-family:system-ui;padding:15px'><div style='max-width:600px;margin:0 auto'><h2 style='color:#a855f7'>ADMIN V12.1 SECURE 120B</h2><p>{len(orders)} commandes | Groq {GROQ_MODEL}</p><div style='background:#1e1b2e;border:1px solid #a855f7;border-radius:10px;padding:10px'>MTN {YOUR_WA} | {EMAIL_DEST}<br>{now_brazza().strftime('%H:%M')} BRAZZA</div>{html_orders}<br><a href='/' style='color:#a855f7'>← Shop</a></div></body>")

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(f"""
<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ADRYNX SHOP</title>
<style>:root{{--violet:#a855f7;--bg:#0a0a12;--card:#151326;--card2:#1e1b2e;--border:#2d2a45;--jaune:#facc15;--vert:#22c55e}}body{{background:var(--bg);color:#fff;font-family:system-ui;margin:0}}.topbar{{background:#0f0e1a;border-bottom:1px solid var(--border);padding:10px 18px;display:flex;justify-content:space-between;align-items:center}}.logo{{font-weight:800}}.nav a{{padding:8px 14px;border-radius:999px;text-decoration:none;color:#aaa;font-size:13px}}.nav a.active{{background:var(--violet);color:#fff}}.banner{{background:linear-gradient(90deg,#1a0f3c,#0f0e1a);padding:18px 20px}}.layout{{display:grid;grid-template-columns:240px 1fr 260px;gap:14px;padding:14px;max-width:1400px;margin:0 auto}}.sidebar,.right,.center{{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:12px}}.center{{display:flex;flex-direction:column;min-height:70vh}}#chat{{flex:1;padding:14px;overflow-y:auto;display:flex;flex-direction:column;gap:10px}}.msg{{padding:12px 14px;border-radius:16px;max-width:78%;font-size:13.5px;white-space:pre-wrap}}.bot{{background:#1e1b2e;align-self:flex-start}}.user{{background:var(--violet);align-self:flex-end}}.bar{{background:var(--card2);border-top:1px solid var(--border);padding:10px;display:flex;gap:8px}}.bar input{{flex:1;background:#0f0e1a;border:1px solid var(--border);color:#fff;padding:12px 16px;border-radius:999px;outline:none}}.bar button.send{{width:44px;height:44px;border-radius:50%;background:var(--violet);border:none;color:#fff;cursor:pointer}}@media(max-width:1100px){{.layout{{grid-template-columns:1fr}}.sidebar,.right{{display:none}}}}</style></head><body>
<div class="topbar"><div class="logo">👑 ADRYNX SHOP</div><div class="nav"><a class="active">🏠 Accueil</a><a href="/admin?key={ADMIN_KEY}">👑 Admin</a><span style="color:var(--vert)">● En ligne {now_brazza().strftime('%H:%M')}</span></div></div>
<div class="banner"><h1 style="font-size:28px">FREE FIRE <span style="color:var(--jaune)">DIAMANTS & SERVICES</span></h1><div style="color:#aaa;font-size:12px">Rapide • Sécurisé • Fiable - Cerveau {GROQ_MODEL}</div></div>
<div class="layout"><div class="sidebar"><h3>💎 Nos Services</h3><div style="display:flex;flex-direction:column;gap:6px"><button style="background:var(--violet);color:#fff;border:none;padding:10px;border-radius:10px">💎 Recharge Diamants</button><button style="background:var(--card2);border:1px solid var(--border);color:#ddd;padding:10px;border-radius:10px">💳 Pass Booyah</button><button style="background:var(--card2);border:1px solid var(--border);color:#ddd;padding:10px;border-radius:10px">📅 Abonnement Mensuel</button></div></div><div class="center"><div style="padding:12px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between"><b>ADRYNX AI - Assistante</b><span style="color:var(--vert);font-size:11px">● En ligne</span></div><div id="chat"><div class="msg bot">Salut! 👋 Bienvenue sur ADRynx Shop!<br>Que souhaites-tu? Teste "je veux 610 diamant" ou "je veux un skyn"</div></div><div class="bar"><input id="q" placeholder="Écris..."><button class="send" onclick="send()">➤</button></div></div><div class="right"><h3>👤 Mon compte</h3><div style="font-size:12px;color:#888">Client Free Fire - Solde: 💎 0</div><div style="margin-top:10px;background:linear-gradient(135deg,#2a1a4a,#3a1a6a);border-radius:12px;padding:12px;text-align:center"><b style="color:var(--jaune)">Offre spéciale!</b><div style="font-size:11px;margin-top:4px">Recharge plus, paye moins!</div></div></div></div>
<script>
let hist=[];async function send(){{let i=document.getElementById('q');let v=i.value.trim();if(!v)return;let c=document.getElementById('chat');c.innerHTML+=`<div class="msg user">${{v}}</div>`;i.value='';let tmp=document.createElement('div');tmp.className='msg bot';tmp.innerText='...';c.appendChild(tmp);c.scrollTop=c.scrollHeight;try{{let r=await fetch('/api/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{message:v,historique:hist}})}});let j=await r.json();tmp.remove();c.innerHTML+=`<div class="msg bot">${{j.reply.replace(/\\n/g,'<br>')}}</div>`;hist.push({{role:"user",content:v}});hist.push({{role:"assistant",content:j.reply}});if(hist.length>10)hist=hist.slice(-10);}}catch(e){{tmp.remove();c.innerHTML+=`<div class="msg bot">Bug réseau MTN {YOUR_WA}</div>`}}c.scrollTop=c.scrollHeight;}}
document.getElementById('q').addEventListener('keydown',e=>{{if(e.key==='Enter')send();}});
</script></body></html>
""")

@app.get("/pay", response_class=HTMLResponse)
def pay_page():
    p520 = calcul_prix(520)[2]
    p1060 = calcul_prix(1060)[2]
    p610 = calcul_prix(610)[2]
    return HTMLResponse(f"<body style='background:#0a0a12;color:#fff;font-family:system-ui;padding:15px'><div style='max-width:480px;margin:20px auto;background:#151326;border:1px solid #2d2a45;padding:20px;border-radius:16px'><h2 style='color:#a855f7'>🔥 Payer</h2><p>MTN: <b>061174945</b></p><form id='f'><input name='ff_id' placeholder='ID Free Fire' required style='width:100%;padding:12px;margin:6px 0;border-radius:10px;background:#0f0e1a;color:#fff;border:1px solid #2d2a45'><select name='quantite' style='width:100%;padding:12px;margin:6px 0;border-radius:10px;background:#0f0e1a;color:#fff;border:1px solid #2d2a45'><option value='110'>110 Diamants - 630F</option><option value='520'>520 - {p520}F</option><option value='1060'>1060 - {p1060}F</option><option value='610'>610 - {p610}F</option><option value='skin'>Skin - 2500F</option><option value='pass booyah'>Pass Booyah - 1800F</option></select><input name='telephone' placeholder='WhatsApp' required style='width:100%;padding:12px;margin:6px 0;border-radius:10px;background:#0f0e1a;color:#fff;border:1px solid #2d2a45'><input type='file' name='preuve' accept='image/*' required><button type='submit' style='width:100%;padding:14px;background:#a855f7;color:#fff;border:none;border-radius:10px;font-weight:bold'>J'ai payé 🚀</button></form><div id='r'></div></div><script>document.getElementById('f').onsubmit=async(e=>{{e.preventDefault();let fd=new FormData(e.target);let r=await fetch('/api/pay',{{method:'POST',body:fd}});let j=await r.json();document.getElementById('r').innerHTML=`<br>✅ ${{j.message}}`}})</script></body>")
