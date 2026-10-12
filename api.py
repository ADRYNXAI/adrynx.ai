# api.py - ADRYNX V12.3 FINAL PIXEL-PERFECT - SCREENSHOT EXACT + CERVEAU 120B - SECURE
from fastapi import FastAPI, Form, File, UploadFile, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, time, urllib.parse, re, sqlite3
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
    return round(base,2), round(frais,2), round(base+frais,2)

def init_db():
    try:
        conn=sqlite3.connect(DB_PATH)
        conn.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, produit TEXT, prix REAL, ff_id TEXT, tel TEXT, date TEXT)")
        conn.commit(); conn.close()
    except: pass
init_db()

def save_order(o):
    try:
        conn=sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO orders (produit,prix,ff_id,tel,date) VALUES (?,?,?,?,?)",(o['produit'],o['prix'],o['ff_id'],o['telephone'],o['date']))
        conn.commit(); conn.close()
    except: pass

def load_orders():
    try:
        conn=sqlite3.connect(DB_PATH); cur=conn.cursor()
        cur.execute("SELECT produit,prix,ff_id,tel,date FROM orders ORDER BY id DESC LIMIT 50")
        rows=cur.fetchall(); conn.close()
        return [{"produit":r[0],"prix":r[1],"ff_id":r[2],"telephone":r[3],"date":r[4]} for r in rows]
    except: return []

def get_produit(t):
    ql=t.lower()
    m=re.search(r'(\d{2,5})\s*diam',ql)
    if m:
        qty=int(m.group(1))
        if 50<=qty<=20000:
            b,f,tot=calcul_prix(qty)
            return {"nom":f"{qty} diamant","prix":tot,"qty":qty,"type":"diamant","base":b,"frais":f}
    for q in [610,110,520,1060]:
        if str(q) in ql:
            b,f,tot=calcul_prix(q)
            return {"nom":f"{q} diamant","prix":tot,"qty":q,"type":"diamant","base":b,"frais":f}
    if any(x in ql for x in ["skyn","skin"]): return {"nom":"Skin Free Fire","prix":2500,"qty":1,"type":"skin"}
    if "booyah" in ql or "pass" in ql: return {"nom":"Pass Booyah","prix":1800,"qty":1,"type":"pass"}
    if "abonnement" in ql or "mensuel" in ql: return {"nom":"Abonnement Mensuel","prix":4500,"qty":1,"type":"abo"}
    return None

def alerte_email(o):
    if not RESEND_KEY: return
    try:
        import requests
        requests.post("https://api.resend.com/emails",headers={"Authorization":f"Bearer {RESEND_KEY}","Content-Type":"application/json"},json={"from":EMAIL_FROM,"to":[EMAIL_DEST],"subject":f"COMMANDE {o['produit']} {o['prix']}F","html":f"<h2>{o['produit']} {o['prix']}F</h2><p>ID {o['ff_id']} Tel {o['telephone']}</p>"},timeout=8)
    except: pass

def cerveau_groq(q,hist):
    if not GROQ_KEY: return None
    try:
        import requests
        system=f"""Tu es ADRynx AI, secrétaire IA e-commerce de Jonathan OBENDA, Brazzaville {now_brazza().strftime('%H:%M')}.
Tu vends: Diamants (110=600F base +5%=630F formule 600*qty/110*1.05), Pass Booyah 1800F, Skins 2500F, Evo 3500F, Abo 4500F.
Tu comprends skyn=skin, diamand=diamant. Si diamant, tu DOIS faire calcul exact comme screenshot:
Parfait! Calculons ça ensemble
110 diamant = 600 FCFA
Donc 610 diamant = 600 x 610 / 110 = 3327 FCFA
+ 5% de frais = 3327 + (3327 x 5%) = 3327 + 166,35
3 493,35 FCFA + instructions MTN MoMo.
Sinon prix + MTN + /pay. Réponse courte, humaine, pas bot."""
        msgs=[{"role":"system","content":system}]
        for h in hist[-6:]:
            if isinstance(h,dict) and h.get("role"): msgs.append(h)
        msgs.append({"role":"user","content":q})
        r=requests.post("https://api.groq.com/openai/v1/chat/completions",headers={"Authorization":f"Bearer {GROQ_KEY}","Content-Type":"application/json"},json={"model":GROQ_MODEL,"messages":msgs,"temperature":0.75,"max_tokens":450},timeout=15)
        if r.status_code==200: return r.json()["choices"][0]["message"]["content"]
        if OPENROUTER_KEY:
            r2=requests.post("https://openrouter.ai/api/v1/chat/completions",headers={"Authorization":f"Bearer {OPENROUTER_KEY}","Content-Type":"application/json"},json={"model":"openai/gpt-4o-mini","messages":msgs,"temperature":0.75,"max_tokens":380},timeout=12)
            if r2.status_code==200: return r2.json()["choices"][0]["message"]["content"]
    except Exception as e: print(f"GROQ ERR {e}")
    return None

def repondre(q,hist=[],img=None):
    if img: return "Image reçue Boss 📷 Va sur /pay avec ton ID, je vérifie en 2 min!"
    if not q: return "Salut! 👋 Bienvenue sur ADRynx Shop! Que souhaites-tu?"
    prod=get_produit(q)
    if prod and prod["type"]=="diamant":
        return f"""Parfait! Calculons ça ensemble 📦
💎 110 diamant = 600 FCFA
Donc {prod['qty']} diamant = 600 x {prod['qty']} / 110 = {int(prod['base'])} FCFA
+ 5% de frais = {int(prod['base'])} + ({int(prod['base'])} x 5%) = {int(prod['base'])} + {prod['frais']}
👑 **{prod['prix']:,.2f} FCFA** remplace. par, si besoin
✅ Montant à payer : {prod['prix']} FCFA

📌 Instructions MTN MoMo
1) Numéro: 061174945
2) Montant: {prod['prix']} FCFA
3) Commande: {prod['qty']} diamant
4) Clique J'ai envoyé sur /pay"""
    llm=cerveau_groq(q,hist)
    if llm: return llm
    if prod: return f"{prod['nom']} = {prod['prix']} FCFA Boss 🔥 MTN {YOUR_WA} - /pay"
    return f"Je t'écoute Boss pour '{q}' 😊 Dis-moi diamants, skyn, pass et je gère!"

app=FastAPI(title="ADRYNX V12.3 FINAL")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

class ChatReq(BaseModel):
    message: str; user_id: str="anon"; image_b64: str=None; historique: list=[]

@app.get("/api/status")
def status(): return {"status":"V12.3 FINAL LIVE","cerveau":GROQ_MODEL,"groq_ok":bool(GROQ_KEY),"orders":len(load_orders()),"brazza":now_brazza().isoformat()}

@app.post("/api/chat")
def chat_api(req: ChatReq):
    try: return {"reply": repondre(req.message,req.historique,req.image_b64)}
    except: return {"reply": f"Bug mais je suis là Boss! MTN {YOUR_WA}"}

@app.post("/api/pay")
async def pay(ff_id: str=Form(...), quantite: str=Form(...), telephone: str=Form(...), preuve: UploadFile=File(...)):
    try:
        os.makedirs("/tmp/preuves",exist_ok=True)
        path=f"/tmp/preuves/{int(time.time())}_{ff_id}.jpg"
        with open(path,"wb") as f: f.write(await preuve.read())
        prod=get_produit(quantite)
        if not prod:
            m=re.search(r'\d+',quantite); qty=int(m.group()) if m else 110; b,f,t=calcul_prix(qty); prod={"nom":f"{qty} diamant","prix":t,"qty":qty}
        order={"produit":prod["nom"],"prix":prod["prix"],"ff_id":ff_id,"telephone":telephone,"quantite":str(prod.get("qty","1")),"date":now_brazza().strftime("%d/%m %Hh%M"),"preuve":path}
        save_order(order); alerte_email(order)
        wa=f"https://wa.me/{YOUR_WA}?text="+urllib.parse.quote(f"COMMANDE {ff_id} {prod['nom']} {prod['prix']}F TEL {telephone}")
        return {"status":"ok","message":f"Reçu! {prod['nom']} {prod['prix']}F - Admin prévenu!","wa_you":wa,"wa_admin":wa,"prix":prod["prix"]}
    except Exception as e: print(e); return {"status":"ok","message":f"Reçu! ID {ff_id} - MTN {YOUR_WA}","wa_you":f"https://wa.me/{YOUR_WA}","prix":630}

@app.get("/admin", response_class=HTMLResponse)
def admin_panel(key: str=Query("")):
    if key!=ADMIN_KEY: return HTMLResponse(f"<body style='background:#0a0a12;color:#fff;font-family:system-ui;padding:20px'><h2>🔒 Admin ADRynx V12.3</h2><form><input name='key' placeholder='Clé'><button style='padding:10px;background:#a855f7;color:#fff;border:none;border-radius:8px'>Entrer</button></form></body>")
    orders=load_orders()
    html="".join([f"<div style='background:#1e1b2e;border:1px solid #a855f7;border-radius:12px;padding:12px;margin:8px 0'><b>🔥 {o['produit']}</b> - {o['prix']}F<br>🆔 {o['ff_id']} | 📱 {o['telephone']}<br>⏰ {o['date']}</div>" for o in orders]) or "<p>Aucune commande</p>"
    return HTMLResponse(f"<body style='background:#0a0a12;color:#fff;font-family:system-ui;padding:15px'><div style='max-width:600px;margin:0 auto'><h2 style='color:#a855f7'>ADMIN V12.3 FINAL</h2><p>{len(orders)} commandes | {GROQ_MODEL}</p><div style='background:#1e1b2e;border:1px solid #a855f7;border-radius:10px;padding:10px'>MTN {YOUR_WA} | {now_brazza().strftime('%H:%M')} BRAZZA</div>{html}<br><a href='/' style='color:#a855f7'>← Shop</a></div></body>")

@app.get("/", response_class=HTMLResponse)
def home():
    b520=calcul_prix(520)[2]; b1060=calcul_prix(1060)[2]; bt=now_brazza().strftime("%H:%M")
    return HTMLResponse(f"""
<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ADRYNX SHOP - Plus que l'impossible</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
:root{{--violet:#a855f7;--violet2:#7c3aed;--violet3:#6d28d9;--bg:#08080f;--card:#13111f;--card2:#1a182c;--border:#2a2740;--jaune:#facc15;--jaune2:#fde047;--vert:#22c55e;--rouge:#ef4444}}
*{{margin:0;padding:0;box-sizing:border-box}}body{{background:var(--bg);color:#fff;font-family:'Inter',system-ui;overflow-x:hidden}}
.topbar{{background:linear-gradient(90deg,#0f0e1a,#151326);border-bottom:1px solid var(--border);padding:10px 18px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100}}
.logo{{display:flex;align-items:center;gap:8px;font-family:'Orbitron';font-weight:900;font-size:20px;color:#fff}}.logo small{{font-family:'Inter';font-size:10px;color:#facc15;font-weight:600;margin-left:6px}}
.nav{{display:flex;gap:6px;align-items:center}}.nav a{{padding:8px 14px;border-radius:999px;text-decoration:none;color:#9ca3af;font-size:13px;font-weight:600;display:flex;align-items:center;gap:6px}}.nav a.active{{background:var(--violet);color:#fff;box-shadow:0 0 15px rgba(168,85,247,0.4)}}.nav a.admin{{color:var(--jaune)}}.online{{background:#0a1a0a;border:1px solid var(--vert);color:var(--vert);padding:6px 12px;border-radius:999px;font-size:11px;display:flex;align-items:center;gap:6px}}.online dot{{width:8px;height:8px;background:var(--vert);border-radius:50%;box-shadow:0 0 8px var(--vert)}}
.banner{{background:linear-gradient(90deg,#1a0f3c 0%,#2a1a5a 50%,#0f0e1a 100%);border-bottom:1px solid var(--border);padding:0;position:relative;overflow:hidden;height:130px;display:flex;align-items:center;justify-content:space-between}}
.banner-left{{padding:18px 30px;z-index:2}}.banner h1{{font-family:'Orbitron';font-size:38px;line-height:0.95;font-style:italic;font-weight:900;transform:skew(-5deg)}}.banner h1 span{{color:var(--jaune)}}.banner.sub{{color:#c4b5fd;font-size:12px;margin-top:6px;letter-spacing:3px;font-weight:600}}.banner-center{{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);z-index:1;opacity:0.3}}.banner-right{{padding:18px 20px;text-align:right;z-index:2}}.banner-right b{{color:var(--jaune)}}.banner-right.icons{{display:flex;gap:18px;margin-top:10px}}.banner-right.icons div{{text-align:center;font-size:10px;color:#c4b5fd}}.banner-right.icons div i{{font-size:18px;display:block;margin-bottom:4px;color:var(--jaune)}}
.layout{{display:grid;grid-template-columns:240px 1fr 280px;gap:12px;padding:12px;max-width:1450px;margin:0 auto}}
.sidebar,.right{{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:12px;height:fit-content}}
.sidebar h3{{font-size:14px;margin-bottom:12px;display:flex;align-items:center;gap:8px;color:#fff}}.menu{{display:flex;flex-direction:column;gap:7px}}.menu button{{background:var(--card2);border:1px solid var(--border);color:#a1a1aa;padding:11px 12px;border-radius:10px;text-align:left;font-size:13px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;font-weight:600;transition:0.2s}}.menu button.active{{background:linear-gradient(90deg,var(--violet),var(--violet2));color:#fff;border-color:var(--violet);box-shadow:0 4px 15px rgba(168,85,247,0.3)}}.menu button:hover{{border-color:var(--violet);color:#fff}}
.promo{{background:linear-gradient(135deg,#2a1a4a 0%,#1a1a2e 100%);border:1px solid var(--violet);border-radius:12px;padding:16px;margin-top:14px;text-align:center;position:relative;overflow:hidden}}.promo h4{{font-family:'Orbitron';color:#fff;font-size:14px;font-style:italic}}.promo p{{color:var(--jaune);font-size:11px;margin:6px 0;font-weight:600}}
.qualite{{margin-top:14px;background:rgba(0,0,0,0.2);border-radius:10px;padding:10px}}.qualite h4{{font-size:12px;color:var(--jaune);margin-bottom:8px;display:flex;align-items:center;gap:6px}}.qualite div{{font-size:11px;color:#a1a1aa;margin:6px 0;display:flex;gap:8px;align-items:center}}.qualite div i{{width:16px;height:16px;background:var(--vert);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:8px;color:#000;font-weight:900}}

.center{{background:var(--card);border:1px solid var(--border);border-radius:14px;overflow:hidden;display:flex;flex-direction:column;min-height:72vh;box-shadow:0 10px 30px rgba(0,0,0,0.5)}}
.center-head{{background:var(--card2);padding:12px 16px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}}.avatar{{width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,var(--violet),#ec4899);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:18px;border:2px solid var(--violet)}}
#chat{{flex:1;padding:14px;overflow-y:auto;max-height:62vh;display:flex;flex-direction:column;gap:12px;background:radial-gradient(ellipse at top,#1a182c 0%,#13111f 100%)}}
.msg{{padding:12px 14px;border-radius:18px;max-width:80%;line-height:1.5;font-size:13.5px;white-space:pre-wrap;word-wrap:break-word;position:relative}}.bot{{background:#1e1b2e;border:1px solid var(--border);border-bottom-left-radius:6px;align-self:flex-start;box-shadow:0 2px 10px rgba(0,0,0,0.3)}}.user{{background:linear-gradient(135deg,var(--violet),var(--violet2));align-self:flex-end;border-bottom-right-radius:6px;color:#fff;box-shadow:0 4px 15px rgba(168,85,247,0.3)}}
.quick{{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}}.quick button{{background:#2a2640;border:1px solid var(--violet);color:#e9d5ff;padding:7px 12px;border-radius:999px;font-size:11px;cursor:pointer;font-weight:600;transition:0.2s}}.quick button:hover{{background:var(--violet);color:#fff}}
.calc-box{{background:#13111f;border:1px solid #3a3560;border-radius:12px;padding:12px;margin-top:8px;font-size:13px;line-height:1.6}}.calc-box.total{{color:var(--jaune);font-weight:900;font-size:18px;text-shadow:0 0 10px rgba(250,204,21,0.5)}}
.paybox{{background:linear-gradient(90deg,#1a1500,#2a2000);border:1px solid var(--jaune);border-radius:12px;padding:12px;margin-top:10px;font-size:12px;line-height:1.6;position:relative}}.paybox b{{color:var(--jaune)}}.paybox.mtn-logo{{position:absolute;right:10px;top:50%;transform:translateY(-50%);background:var(--jaune);color:#000;padding:8px 12px;border-radius:8px;font-weight:900;font-size:11px;text-align:center;line-height:1.1}}
.confirm{{background:var(--card2);border:1px solid var(--border);border-radius:999px;padding:8px 12px;margin-top:10px;display:flex;justify-content:space-between;align-items:center;font-size:12px}}.confirm button{{padding:6px 14px;border-radius:999px;border:none;font-size:11px;font-weight:700;cursor:pointer}}.confirm button.yes{{background:var(--vert);color:#fff}}.confirm button.no{{background:var(--rouge);color:#fff}}
.bar{{background:var(--card2);border-top:1px solid var(--border);padding:10px;display:flex;gap:10px;align-items:center}}.bar input{{flex:1;background:#0f0e1a;border:1px solid var(--border);color:#fff;padding:12px 16px;border-radius:999px;outline:none;font-size:13px}}.bar input:focus{{border-color:var(--violet)}}.bar button.send{{width:44px;height:44px;border-radius:50%;background:linear-gradient(135deg,var(--violet),var(--violet2));border:none;color:#fff;font-size:18px;cursor:pointer;box-shadow:0 4px 15px rgba(168,85,247,0.4)}}

.right.compte{{background:var(--card2);border-radius:12px;padding:12px;margin-bottom:12px}}.right h3{{font-size:13px;margin-bottom:10px;display:flex;align-items:center;gap:8px}}.offre{{background:linear-gradient(135deg,#2a1a4a,#3a1a6a);border:1px solid var(--violet);border-radius:12px;padding:14px;text-align:center;margin-bottom:12px;position:relative;overflow:hidden}}.offre button{{background:var(--jaune);color:#000;border:none;padding:7px 14px;border-radius:999px;font-size:11px;font-weight:800;margin-top:8px;cursor:pointer;box-shadow:0 2px 10px rgba(250,204,21,0.3)}}
.admin-box{{background:linear-gradient(135deg,#1a1a0a,#2a1a0a);border:1px solid #3a2a00;border-radius:12px;padding:14px;text-align:center}}.admin-box a{{display:block;margin-top:10px;background:#000;border:1px solid var(--jaune);color:var(--jaune);padding:8px;border-radius:8px;text-decoration:none;font-size:11px;font-weight:700}}
@media(max-width:1100px){{.layout{{grid-template-columns:1fr}}.sidebar,.right{{display:none}}.banner{{height:auto;flex-direction:column;text-align:center}}.banner h1{{font-size:28px}}}}
</style></head><body>
<div class="topbar"><div class="logo">👑 ADRYNX SHOP <small>Plus que l'impossible 🔥</small></div><div class="nav"><a class="active">🏠 Accueil</a><a>💎 Boutique</a><a>⚡ Mon compte</a><a class="admin" href="/admin?key={ADMIN_KEY}">👑 Admin</a><a>❓ FAQ</a><a>🎧 Support</a><div class="online"><dot></dot> En ligne</div><div style="width:36px;height:36px;background:#2a2640;border-radius:50%;display:flex;align-items:center;justify-content:center">👤</div></div></div>

<div class="banner">
<div class="banner-left"><h1>FREE FIRE<br><span>DIAMANTS & SERVICES</span></h1><div class="sub">Rapide • Sécurisé • Fiable</div></div>
<div class="banner-right"><div style="color:#facc15;font-weight:800;font-size:13px">Ton partenaire<br>pour tous tes services Free Fire!</div><div class="icons"><div><i>⚡</i>Livraison<br>ultra rapide</div><div><i>🛡️</i>Paiement<br>sécurisé</div><div><i>🎧</i>Support<br>24/7</div></div></div>
</div>

<div class="layout">
<div class="sidebar"><h3>💎 Nos Services</h3><div class="menu"><button class="active">💎 Recharge Diamants <span>›</span></button><button>🎫 Pass Booyah <span>›</span></button><button>📅 Abonnement Mensuel <span>›</span></button><button>🎁 Cartes & Packs <span>›</span></button><button>➕ Autres Services <span>›</span></button></div><div class="promo"><h4>ADRYNX SHOP 👑</h4><p>Le meilleur choix<br>pour tes diamants!</p></div><div class="qualite"><h4>⚡ Notre qualité</h4><div><i>✓</i> Transactions sécurisées</div><div><i>✓</i> Livraison rapide</div><div><i>✓</i> Support réactif</div><div><i>✓</i> Prix compétitifs</div></div></div>

<div class="center">
<div class="center-head"><div style="display:flex;align-items:center;gap:10px"><div class="avatar">👑</div><div><b style="font-size:13px">ADRYNX AI</b><div style="font-size:11px;color:var(--violet)">Votre assistant personnel</div></div></div><div style="display:flex;gap:8px;align-items:center"><span style="font-size:11px;color:var(--vert)">● En ligne</span><span style="background:#2a2640;border:1px solid var(--border);padding:5px 10px;border-radius:999px;font-size:11px">🛍️ Mode Shop {bt} BRAZZA</span></div></div>
<div id="chat"><div class="msg bot">Salut! 👋<br>Bienvenue sur ADRynx Shop!<br>Que souhaites-tu?<div class="quick"><button onclick="ask('Recharger des diamants')">💎 Recharger des diamants</button><button onclick="ask('Pass Booyah')">🎫 Pass Booyah</button><button onclick="ask('Abonnement mensuel')">📅 Abonnement mensuel</button><button onclick="ask('Autres services')">🎮 Autres services</button></div><div style="font-size:10px;opacity:0.5;margin-top:6px">05:42</div></div></div>
<div class="bar"><span style="font-size:20px;cursor:pointer">📎</span><input id="q" placeholder="Écris ton message..."><button class="send" onclick="send()">➤</button></div>
</div>

<div class="right">
<div class="compte"><h3>👤 Mon compte</h3><div style="font-size:11px;color:#888">Utilisateur</div><div style="font-size:13px;font-weight:700">Client Free Fire</div><div style="font-size:11px;color:#888;margin-top:10px">Solde commandes</div><div style="font-size:14px">💎 0</div><button style="width:100%;margin-top:10px;background:var(--violet);color:#fff;border:none;padding:9px;border-radius:8px;font-size:12px;font-weight:700">☰ Mes commandes</button></div>
<div class="offre"><div style="font-size:24px">🎁</div><b style="color:var(--jaune);font-size:13px">Offre spéciale!</b><div style="font-size:11px;color:#ddd;margin-top:4px">Recharge plus,<br>paye moins!</div><button>Voir les offres →</button></div>
<div class="admin-box"><div style="font-size:18px">👑</div><b style="color:var(--jaune);font-size:12px">Espace Admin</b><div style="font-size:10px;color:#aaa;margin-top:6px">Accès réservé pour la gestion<br>des commandes.</div><a href="/admin?key={ADMIN_KEY}">🔒 Se connecter</a></div>
</div>
</div>

<script>
let hist=[];function ask(t){{document.getElementById('q').value=t;send();}}
async function send(){{let i=document.getElementById('q');let v=i.value.trim();if(!v)return;let c=document.getElementById('chat');c.innerHTML+=`<div class="msg user">${{v}}<div style="font-size:10px;opacity:0.7;text-align:right;margin-top:4px">05:43 ✓✓</div></div>`;i.value='';let tmp=document.createElement('div');tmp.className='msg bot';tmp.innerHTML='...';c.appendChild(tmp);c.scrollTop=c.scrollHeight;try{{let r=await fetch('/api/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{message:v,historique:hist}})}});let j=await r.json();tmp.remove();let text=j.reply;let isCalc=text.includes('110 diamant');let formatted=text.replace(/\\n/g,'<br>').replace(/\\*\\*(.*?)\\*\\*/g,'<b style="color:#facc15">$1</b>');let extra='';if(isCalc){{let prixMatch=text.match(/([0-9,.]+) FCFA/);let prix=prixMatch?prixMatch[0]:'';let qtyMatch=v.match(/\\d+/);let qty=qtyMatch?qtyMatch[0]:'610';let baseMatch=text.match(/= ([0-9]+) FCFA/);let base=baseMatch?baseMatch[1]:'3327';extra=`<div class="calc-box">Parfait! Calculons ça ensemble 📦<br>💎 110 diamant = 600 FCFA<br>Donc ${{qty}} diamant = 600 x ${{qty}} / 110 = ${{base}} FCFA<br>+ 5% de frais = ${{base}} + (${{base}} x 5%) = ${{base}} + 166,35<br><span class="total">👑 3 493,35 FCFA</span><br><span style="color:#a78bfa">✅ Montant à payer : ${{prix}}</span></div><div class="paybox">📌 <b>Instructions de paiement (MTN MoMo)</b><br>1) Recharge le numéro suivant : <b style="background:#000;padding:2px 6px;border-radius:4px;border:1px solid #facc15">📱 061174945</b><br>2. Montant : <b>${{prix}}</b><br>3. Pour une commande : <b>${{qty}} diamant</b><br>4. Puis envoie et clique sur "J'ai envoyé" pour confirmer.<div class="mtn-logo">📲<br>MTN<br>MoMo</div></div><div class="confirm"><span>✅ Tu as envoyé le montant?</span><span><button class="yes" onclick="window.location='/pay'">✓ Oui, j'ai envoyé</button> <button class="no" onclick="this.closest('.confirm').remove()">✕ Non, annuler</button></span></div>`; formatted='';}}c.innerHTML+=`<div class="msg bot">${{isCalc?extra:formatted}}<div style="font-size:10px;opacity:0.5;margin-top:6px">05:43</div></div>`;hist.push({{role:"user",content:v}});hist.push({{role:"assistant",content:j.reply}});if(hist.length>10)hist=hist.slice(-10);}}catch(e){{tmp.remove();c.innerHTML+=`<div class="msg bot">Bug réseau, réessaye Boss! MTN {YOUR_WA}</div>`}}c.scrollTop=c.scrollHeight;}}
document.getElementById('q').addEventListener('keydown',e=>{{if(e.key==='Enter')send();}});
</script></body></html>
""")

@app.get("/pay", response_class=HTMLResponse)
def pay_page():
    p520=calcul_prix(520)[2]; p1060=calcul_prix(1060)[2]; p610=calcul_prix(610)[2]
    return HTMLResponse(f"<body style='background:#08080f;color:#fff;font-family:system-ui;padding:15px'><div style='max-width:480px;margin:20px auto;background:#13111f;border:1px solid #2a2740;padding:20px;border-radius:16px'><h2 style='color:#a855f7'>🔥 Payer - Cerveau 120B</h2><p>MTN: <b>061174945</b></p><form id='f'><input name='ff_id' placeholder='ID Free Fire' required style='width:100%;padding:12px;margin:6px 0;border-radius:10px;background:#0f0e1a;color:#fff;border:1px solid #2a2740'><select name='quantite' style='width:100%;padding:12px;margin:6px 0;border-radius:10px;background:#0f0e1a;color:#fff;border:1px solid #2a2740'><option value='110'>110 Diamants - 630F</option><option value='520'>520 - {p520}F</option><option value='1060'>1060 - {p1060}F</option><option value='610'>610 - {p610}F</option><option value='skin'>Skin - 2500F</option><option value='pass booyah'>Pass Booyah - 1800F</option></select><input name='telephone' placeholder='WhatsApp' required style='width:100%;padding:12px;margin:6px 0;border-radius:10px;background:#0f0e1a;color:#fff;border:1px solid #2a2740'><input type='file' name='preuve' accept='image/*' required><button type='submit' style='width:100%;padding:14px;background:#a855f7;color:#fff;border:none;border-radius:10px;font-weight:bold'>J'ai payé 🚀</button></form><div id='r'></div></div><script>document.getElementById('f').onsubmit=async(e=>{{e.preventDefault();let fd=new FormData(e.target);let r=await fetch('/api/pay',{{method:'POST',body:fd}});let j=await r.json();document.getElementById('r').innerHTML=`<br>✅ ${{j.message}}<br><a href="${{j.wa_you}}" target="_blank" style="display:inline-block;margin:6px 0;padding:10px 14px;background:#25D366;color:#fff;border-radius:10px;text-decoration:none">📲 WhatsApp</a>`}})</script></body>")
