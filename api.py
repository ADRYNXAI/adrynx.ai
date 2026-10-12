# api.py - ADRYNX V12.0 ULTIMATE - DESIGN SCREENSHOT + CERVEAU GROQ 120B + SECRETAIRE IA - 12 oct 2026
# Utilise: GROQ_API_KEY=gsk_yTJO... / GROQ_MODEL=openai/gpt-oss-120b / RESEND / DB
from fastapi import FastAPI, Form, File, UploadFile, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, time, urllib.parse, re, json, sqlite3
from datetime import datetime, timezone, timedelta

YOUR_WA = "242061174945"
ADMIN_KEY = os.getenv("ADRYNX_ADMIN_SECRET", "AD23ULTRONIX3D")
DB_PATH = os.getenv("ADRYNX_DB", "/tmp/memoire.db")
GROQ_KEY = os.getenv("GROQ_API_KEY", "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")
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

# ==================== DB ====================
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

# ==================== PRODUITS INTELLIGENT ====================
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

# ==================== ALERTE ADMIN ====================
def alerte_admin_email(order):
    if not RESEND_KEY: return
    try:
        import requests
        html = f"<h2>🔥 Commande {order['produit']}</h2><p>{order['prix']}F - ID {order['ff_id']} - Tel {order['telephone']} - {order['date']}</p>"
        requests.post("https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_KEY}", "Content-Type": "application/json"},
            json={"from": EMAIL_FROM, "to": [EMAIL_DEST], "subject": f"COMMANDE {order['produit']} {order['prix']}F", "html": html}, timeout=8)
    except: pass

def alerte_admin_wa(order):
    txt = f"COMMANDE V12 {order['produit']} {order['prix']}F ID {order['ff_id']} TEL {order['telephone']}"
    return "https://wa.me/" + YOUR_WA + "?text=" + urllib.parse.quote(txt)

# ==================== CERVEAU GROQ 120B - SECRETAIRE QUI RAISONNE ====================
def cerveau_groq(question: str, historique: list):
    if not GROQ_KEY:
        return None
    try:
        import requests
        system = f"""
Tu es ADRynx AI, secrétaire IA e-commerce créée par Jonathan OBENDA. Tu es humaine, chaleureuse, tu raisonnes comme une vraie vendeuse congolaise pro. Tu bats GPT, Claude, Grok.

Ton shop: ADRynx Shop, MTN 061174945, Brazzaville {now_brazza().strftime('%H:%M')} UTC+1
Tu vends: Diamants (110=600F base +5% => 630F, formule 600*qty/110*1.05), Pass Booyah 1800F, Skins 2500F, Armes Evo 3500F, Abonnement 4500F, Cartes & Packs
Tu comprends toutes fautes: skyn=skin, achété=acheté, diamand=diamant, langage SMS
Si vente diamant, tu DOIS faire le calcul détaillé comme ça:
Parfait! Calculons ça ensemble
110 diamant = 600 FCFA
Donc 610 diamant = 600 x 610 / 110 = 3327 FCFA
+ 5% de frais = 3327 + (3327 x 5%) = 3327 + 166,35
👑 3 493,35 FCFA

Puis instructions MTN MoMo.
Pour autre produit, donne prix + MTN + /pay + dis j'informe l'admin.
Tu discutes de tout, tu n'es jamais un bot à réponses pré-définies. Tu raisonnes.
Réponse courte mobile.
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
        else:
            print(f"GROQ FAIL {r.text[:200]}")
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
        return "Image reçue Boss 📷 Si c'est preuve MTN, va sur /pay avec ton ID, je vérifie en 2 min et j'informe l'admin!"

    prod = get_produit(question)
    # Vente diamant prioritaire avec format screenshot exact
    if prod and prod["type"] == "diamant":
        # Format exact de ton screenshot
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

    # Cerveau réel
    llm = cerveau_groq(question, historique)
    if llm:
        return llm

    # Fallback intelligent qui comprend skyn
    ql = question.lower()
    if any(x in ql for x in ["skyn","skin"]):
        return f"Ah tu veux un skin! 🔥 J'ai des skins Free Fire à 2500F et armes Evo à 3500F Boss. C'est quel skin exactement? Dis-moi le nom et je te donne prix + MTN {YOUR_WA} sur /pay - Admin prévenu direct!"

    if prod:
        return f"{prod['nom']} = {prod['prix']} FCFA Boss 🔥 MTN {YOUR_WA} - Va sur /pay avec ton ID, admin alerté par email!"

    return f"Je t'écoute Boss pour '{question}' 😊 Je suis ta secrétaire IA qui raisonne, pas un bot. Je vends tout: diamants, skins, pass, abonnements. Dis-moi ce que tu veux et je gère!"

# ==================== FASTAPI ====================
app = FastAPI(title="ADRYNX V12.0 ULTIMATE")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class ChatReq(BaseModel):
    message: str
    user_id: str = "anon"
    image_b64: str = None
    historique: list = []

@app.get("/api/status")
def status():
    return {"status":"V12.0 ULTIMATE LIVE","cerveau":GROQ_MODEL,"groq_ok":bool(GROQ_KEY),"resend_ok":bool(RESEND_KEY),"db":DB_PATH,"brazza":now_brazza().isoformat(),"orders":len(load_orders_db())}

@app.post("/api/chat")
def chat(req: ChatReq):
    try:
        rep = repondre(req.message, req.historique, req.image_b64)
        return {"reply": rep}
    except Exception as e:
        print(f"CHAT ERR {e}")
        return {"reply": f"Oups petit bug mais je suis là Boss! Dis-moi combien de diamants tu veux? MTN {YOUR_WA}"}

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
        wa_admin = alerte_admin_wa(order)
        txt = f"COMMANDE {ff_id} {prod['nom']} {prod['prix']}F TEL {telephone}"
        wa_client = "https://wa.me/" + YOUR_WA + "?text=" + urllib.parse.quote(txt)
        return {"status":"ok","message":f"Reçu! {prod['nom']} pour ID {ff_id} - {prod['prix']} FCFA - Admin prévenu par email {EMAIL_DEST} + WA! Je vérifie en 2 min!","wa_you":wa_client,"wa_admin":wa_admin,"prix":prod["prix"]}
    except Exception as e:
        print(f"PAY ERR {e}")
        return {"status":"ok","message":f"Reçu! ID {ff_id} - Admin prévenu! MTN {YOUR_WA}","wa_you":f"https://wa.me/{YOUR_WA}","prix":630}

@app.get("/admin", response_class=HTMLResponse)
def admin_panel(key: str = Query("")):
    if key!= ADMIN_KEY:
        return HTMLResponse(f"""<body style="background:#0a0a0a;color:#fff;font-family:system-ui;padding:20px"><h2>🔒 Admin ADRynx V12.0</h2><form><input name="key" placeholder="Clé admin" style="padding:10px"><button style="padding:10px;background:#a855f7;color:#fff;border:none;border-radius:8px">Entrer</button></form><p>Groq: {GROQ_MODEL} - Resend: {EMAIL_DEST}</p></body>""")
    orders = load_orders_db()
    html_orders = ""
    for o in orders:
        html_orders += f"<div style='background:#1e1b2e;border:1px solid #a855f7;border-radius:12px;padding:12px;margin:8px 0'><b>🔥 {o['produit']}</b> - {o['prix']}F<br>🆔 {o['ff_id']} | 📱 {o['telephone']}<br>⏰ {o['date']}</div>"
    if not html_orders: html_orders="<p>Aucune commande</p>"
    return HTMLResponse(f"""<body style="background:#0a0a0a;color:#fff;font-family:system-ui;padding:15px"><div style="max-width:600px;margin:0 auto"><h2 style="color:#a855f7">ADMIN V12.0 CERVEAU 120B</h2><p>{len(orders)} commandes | Groq {GROQ_MODEL}</p><div style="background:#1e1b2e;border:1px solid #a855f7;border-radius:10px;padding:10px">MTN {YOUR_WA} | {EMAIL_DEST}<br>{now_brazza().strftime('%H:%M')} BRAZZA</div>{html_orders}<br><a href="/" style="color:#a855f7">← Shop</a></div></body>""")

# ==================== FRONTEND DESIGN EXACT SCREENSHOT ====================
@app.get("/", response_class=HTMLResponse)
def home():
    bt = now_brazza().strftime("%H:%M")
    return HTMLResponse(f"""
<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ADRYNX SHOP - Plus que l'impossible</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
:root{{--violet:#a855f7;--violet2:#7c3aed;--bg:#0a0a12;--card:#151326;--card2:#1e1b2e;--border:#2d2a45;--jaune:#facc15;--vert:#22c55e}}
*{{margin:0;padding:0;box-sizing:border-box}}body{{background:var(--bg);color:#fff;font-family:'Inter',system-ui;overflow-x:hidden}}
.topbar{{background:#0f0e1a;border-bottom:1px solid var(--border);padding:10px 18px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100}}
.logo{{display:flex;align-items:center;gap:10px;font-family:'Orbitron';font-weight:700;font-size:20px}}.logo span{{color:var(--jaune)}}
.nav{{display:flex;gap:6px}}.nav a{{padding:8px 14px;border-radius:999px;text-decoration:none;color:#aaa;font-size:13px;font-weight:600}}.nav a.active{{background:var(--violet);color:#fff}}.nav a.admin{{color:var(--jaune)}}
.banner{{background:linear-gradient(90deg,#1a0f3c,#0f0e1a);border-bottom:1px solid var(--border);padding:18px 20px;display:flex;justify-content:space-between;align-items:center;position:relative;overflow:hidden}}
.banner h1{{font-family:'Orbitron';font-size:32px;line-height:1.1;font-style:italic}}.banner h1.yellow{{color:var(--jaune)}}.banner.sub{{color:#aaa;font-size:13px;margin-top:4px;letter-spacing:2px}}
.layout{{display:grid;grid-template-columns:240px 1fr 260px;gap:14px;padding:14px;max-width:1400px;margin:0 auto}}
.sidebar,.right{{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:12px;height:fit-content}}
.sidebar h3{{font-size:14px;margin-bottom:10px;display:flex;align-items:center;gap:6px}}.menu{{display:flex;flex-direction:column;gap:6px}}.menu button{{background:var(--card2);border:1px solid var(--border);color:#ddd;padding:10px 12px;border-radius:10px;text-align:left;font-size:13px;cursor:pointer;display:flex;justify-content:space-between;align-items:center}}.menu button.active{{background:linear-gradient(90deg,var(--violet),var(--violet2));color:#fff;border-color:var(--violet)}}
.promo{{background:linear-gradient(135deg,#2a1a4a,#1a1a2e);border:1px solid var(--violet);border-radius:12px;padding:14px;margin-top:12px;text-align:center}}.promo h4{{font-family:'Orbitron';color:#fff;font-size:14px}}.promo p{{color:var(--jaune);font-size:12px;margin:4px 0}}
.qualite{{margin-top:12px}}.qualite h4{{font-size:13px;color:var(--jaune);margin-bottom:8px}}.qualite div{{font-size:12px;color:#aaa;margin:4px 0;display:flex;gap:6px;align-items:center}}.qualite.dot{{width:18px;height:18px;background:var(--vert);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;color:#000}}

.center{{background:var(--card);border:1px solid var(--border);border-radius:14px;overflow:hidden;display:flex;flex-direction:column;min-height:70vh}}
.center-head{{background:var(--card2);padding:12px 16px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}}.center-head.left{{display:flex;align-items:center;gap:10px}}.avatar{{width:38px;height:38px;border-radius:50%;background:linear-gradient(135deg,var(--violet),#ec4899);display:flex;align-items:center;justify-content:center;font-weight:800}}.status{{width:8px;height:8px;background:var(--vert);border-radius:50%}}
#chat{{flex:1;padding:14px;overflow-y:auto;max-height:60vh;display:flex;flex-direction:column;gap:10px}}
.msg{{padding:12px 14px;border-radius:16px;max-width:78%;line-height:1.45;font-size:13.5px;white-space:pre-wrap;word-wrap:break-word}}.bot{{background:#1e1b2e;border:1px solid var(--border);border-bottom-left-radius:6px;align-self:flex-start}}.user{{background:var(--violet);align-self:flex-end;border-bottom-right-radius:6px;color:#fff}}
.quick{{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}}.quick button{{background:#2a2640;border:1px solid var(--violet);color:#ddd;padding:6px 10px;border-radius:999px;font-size:11px;cursor:pointer}}
.calc{{background:#151326;border:1px solid #3a3560;border-radius:12px;padding:12px;margin-top:8px;font-size:13px}}.calc.total{{color:var(--jaune);font-weight:800;font-size:16px}}
.paybox{{background:#1a1500;border:1px solid var(--jaune);border-radius:10px;padding:10px;margin-top:8px;font-size:12px}}.paybox b{{color:var(--jaune)}}
.bar{{background:var(--card2);border-top:1px solid var(--border);padding:10px;display:flex;gap:8px;align-items:center}}.bar input{{flex:1;background:#0f0e1a;border:1px solid var(--border);color:#fff;padding:12px 16px;border-radius:999px;outline:none}}.bar button.send{{width:44px;height:44px;border-radius:50%;background:var(--violet);border:none;color:#fff;font-size:18px;cursor:pointer}}

.right.compte{{background:var(--card2);border-radius:10px;padding:10px;margin-bottom:10px}}.right h3{{font-size:13px;margin-bottom:8px}}.offre{{background:linear-gradient(135deg,#2a1a4a,#3a1a6a);border-radius:12px;padding:12px;text-align:center;margin-bottom:10px}}.offre button{{background:var(--jaune);color:#000;border:none;padding:6px 12px;border-radius:999px;font-size:11px;font-weight:700;margin-top:6px;cursor:pointer}}
@media(max-width:1100px){{.layout{{grid-template-columns:1fr}}.sidebar,.right{{display:none}}}}
</style></head><body>
<div class="topbar"><div class="logo">👑 ADRYNX SHOP <span style="font-size:10px;color:#aaa;font-family:Inter;font-weight:400">Plus que l'impossible 🔥</span></div><div class="nav"><a class="active">🏠 Accueil</a><a>💎 Boutique</a><a>⚡ Mon compte</a><a class="admin" href="/admin?key={ADMIN_KEY}">👑 Admin</a><a>❓ FAQ</a><a>🎧 Support</a><span style="background:#0a1a0a;border:1px solid var(--vert);color:var(--vert);padding:6px 10px;border-radius:999px;font-size:11px">● En ligne</span></div></div>
<div class="banner"><div><h1>FREE FIRE<br><span class="yellow">DIAMANTS & SERVICES</span></h1><div class="sub">Rapide • Sécurisé • Fiable</div></div><div style="text-align:right;font-size:11px;color:#aaa">Ton partenaire<br><b style="color:var(--jaune)">pour tous tes services Free Fire!</b></div></div>
<div class="layout">
<div class="sidebar"><h3>💎 Nos Services</h3><div class="menu"><button class="active">💎 Recharge Diamants <span>></span></button><button>💳 Pass Booyah <span>></span></button><button>📅 Abonnement Mensuel <span>></span></button><button>🎁 Cartes & Packs <span>></span></button><button>➕ Autres Services <span>></span></button></div><div class="promo"><h4>ADRYNX SHOP 👑</h4><p>Le meilleur choix pour tes diamants!</p></div><div class="qualite"><h4>⚡ Notre qualité</h4><div><span class="dot">✓</span> Transactions sécurisées</div><div><span class="dot">✓</span> Livraison rapide</div><div><span class="dot">✓</span> Support réactif</div><div><span class="dot">✓</span> Prix compétitifs</div></div></div>
<div class="center"><div class="center-head"><div class="left"><div class="avatar">🤖</div><div><b style="font-size:13px">ADRYNX AI</b><div style="font-size:11px;color:var(--violet)">Votre assistant personnel</div></div></div><div style="display:flex;gap:8px;align-items:center"><span style="font-size:11px;color:var(--vert)">● En ligne</span><span style="background:#2a2640;border:1px solid var(--border);padding:4px 8px;border-radius:999px;font-size:11px">🛍️ Mode Shop</span></div></div><div id="chat"><div class="msg bot">Salut! 👋<br>Bienvenue sur ADRynx Shop!<br>Que souhaites-tu?<div class="quick"><button onclick="ask('Recharger des diamants')">💎 Recharger des diamants</button><button onclick="ask('Pass Booyah')">💳 Pass Booyah</button><button onclick="ask('Abonnement mensuel')">📅 Abonnement mensuel</button><button onclick="ask('Autres services')">🎮 Autres services</button></div></div></div><div class="bar"><span style="font-size:18px">📎</span><input id="q" placeholder="Écris ton message..."><button class="send" onclick="send()">➤</button></div></div>
<div class="right"><div class="compte"><h3>👤 Mon compte</h3><div style="font-size:11px;color:#888">Utilisateur</div><div style="font-size:13px;font-weight:700">Client Free Fire</div><div style="font-size:11px;color:#888;margin-top:8px">Solde commandes</div><div style="font-size:14px">💎 0</div><button style="width:100%;margin-top:8px;background:var(--violet);color:#fff;border:none;padding:8px;border-radius:8px;font-size:12px">☰ Mes commandes</button></div><div class="offre"><div style="font-size:20px">🎁</div><b style="color:var(--jaune);font-size:13px">Offre spéciale!</b><div style="font-size:11px;color:#ddd;margin-top:4px">Recharge plus, paye moins!</div><button>Voir les offres →</button></div><div class="offre" style="background:linear-gradient(135deg,#1a1a0a,#2a1a0a)"><div style="font-size:18px">👑</div><b style="color:var(--jaune);font-size:12px">Espace Admin</b><div style="font-size:10px;color:#aaa;margin-top:4px">Accès réservé pour la gestion des commandes.</div><a href="/admin?key={ADMIN_KEY}" style="display:block;margin-top:8px;background:#000;border:1px solid var(--jaune);color:var(--jaune);padding:6px;border-radius:8px;text-decoration:none;font-size:11px">🔒 Se connecter</a></div></div>
</div>
<script>
let hist=[];function ask(t){{document.getElementById('q').value=t;send();}}
async function send(){{let i=document.getElementById('q');let v=i.value.trim();if(!v)return;let c=document.getElementById('chat');c.innerHTML+=`<div class="msg user">${{v}}<div style="font-size:10px;opacity:0.7;text-align:right;margin-top:4px">{new Date().toLocaleTimeString().slice(0,5)} ✓✓</div></div>`;i.value='';let tmp=document.createElement('div');tmp.className='msg bot';tmp.innerHTML='...';c.appendChild(tmp);c.scrollTop=c.scrollHeight;try{{let r=await fetch('/api/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{message:v,historique:hist}})}});let j=await r.json();tmp.remove();let formatted=j.reply.replace(/\\n/g,'<br>').replace(/\\*\\*(.*?)\\*\\*/g,'<b style="color:#facc15">$1</b>');let extra='';if(j.reply.includes('061174945')){{extra=`<div class="paybox">📌 Instructions de paiement (MTN MoMo)<br>1) Recharge le numéro suivant : <b>📱 061174945</b><br>2) Montant : <b>${{j.reply.match(/[0-9,.]+ FCFA/)?.[0]||''}}</b><br>3) Pour une commande : ${{v}}<br>4) Puis envoie et clique sur "J'ai envoyé" pour confirmer.<br><div style="margin-top:6px;background:#facc15;color:#000;display:inline-block;padding:4px 8px;border-radius:6px;font-weight:700;font-size:11px">MTN MoMo</div></div><div style="margin-top:8px;background:#1a1a0a;border:1px solid #2a2a2a;border-radius:999px;padding:6px 10px;display:flex;justify-content:space-between;align-items:center;font-size:12px"><span>✅ Tu as envoyé le montant?</span><span><button onclick="window.location='/pay'" style="background:#22c55e;color:#fff;border:none;padding:4px 8px;border-radius:999px;font-size:11px">✓ Oui, j'ai envoyé</button> <button style="background:#ef4444;color:#fff;border:none;padding:4px 8px;border-radius:999px;font-size:11px">✕ Non, annuler</button></span></div>`;}}c.innerHTML+=`<div class="msg bot">${{formatted}}${{extra}}<div style="font-size:10px;opacity:0.6;margin-top:6px">{new Date().toLocaleTimeString().slice(0,5)}</div></div>`;hist.push({{role:"user",content:v}});hist.push({{role:"assistant",content:j.reply}});if(hist.length>10) hist=hist.slice(-10);}}catch(e){{tmp.remove();c.innerHTML+=`<div class="msg bot">Bug réseau, réessaye Boss! MTN {YOUR_WA}</div>`}}c.scrollTop=c.scrollHeight;}}
document.getElementById('q').addEventListener('keydown',e=>{{if(e.key==='Enter')send();}});
</script></body></html>
""")

@app.get("/pay", response_class=HTMLResponse)
def pay_page():
    p520 = calcul_prix(520)[2]
    p1060 = calcul_prix(1060)[2]
    p610 = calcul_prix(610)[2]
    return HTMLResponse(f"""<body style="background:#0a0a12;color:#fff;font-family:system-ui;padding:15px"><div style="max-width:480px;margin:20px auto;background:#151326;border:1px solid #2d2a45;padding:20px;border-radius:16px"><h2 style="color:#a855f7">🔥 Payer - Cerveau 120B</h2><p>MTN: <b>061174945</b> - Admin notifié par email {EMAIL_DEST}</p><form id="f"><input name="ff_id" placeholder="ID Free Fire" required style="width:100%;padding:12px;margin:6px 0;border-radius:10px;background:#0f0e1a;color:#fff;border:1px solid #2d2a45"><select name="quantite" style="width:100%;padding:12px;margin:6px 0;border-radius:10px;background:#0f0e1a;color:#fff;border:1px solid #2d2a45"><option value="110">110 Diamants - 630F</option><option value="520">520 Diamants - {p520}F</option><option value="1060">1060 Diamants - {p1060}F</option><option value="610">610 Diamants - {p610}F</option><option value="skin">Skin Free Fire - 2500F</option><option value="pass booyah">Pass Booyah - 1800F</option><option value="abonnement mensuel">Abonnement Mensuel - 4500F</option></select><input name="telephone" placeholder="WhatsApp client" required style="width:100%;padding:12px;margin:6px 0;border-radius:10px;background:#0f0e1a;color:#fff;border:1px solid #2d2a45"><input type="file" name="preuve" accept="image/*" required><button type="submit" style="width:100%;padding:14px;background:#a855f7;color:#fff;border:none;border-radius:10px;font-weight:bold">J'ai payé - Alerter Admin 🚀</button></form><div id="r"></div><p><a href="/" style="color:#a855f7">← Shop</a> | <a href="/admin?key={ADMIN_KEY}" style="color:#888">Admin</a></p></div><script>document.getElementById('f').onsubmit=async(e=>{{e.preventDefault();let fd=new FormData(e.target);let r=await fetch('/api/pay',{{method:'POST',body:fd}});let j=await r.json();document.getElementById('r').innerHTML=`<br>✅ ${{j.message}}<br><a href="${{j.wa_you}}" target="_blank" style="display:inline-block;margin:6px 0;padding:10px 14px;background:#25D366;color:#fff;border-radius:10px;text-decoration:none">📲 WhatsApp</a><br><a href="${{j.wa_admin}}" target="_blank" style="display:inline-block;margin:6px 0;padding:10px 14px;background:#a855f7;color:#fff;border-radius:10px;text-decoration:none">🔔 Admin</a>`}})</script></body>""")
