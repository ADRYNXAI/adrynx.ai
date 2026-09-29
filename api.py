from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import os

app = FastAPI(title="ADRYNX - Linear OS Congo")

# Import ton moteur existant
try:
    from adrynx import ADRYNX_ENGINE
except:
    ADRYNX_ENGINE = None

HTML_LINEAR = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ADRYNX — Workspace</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box;font-family:'Inter',sans-serif}
body{background:#0E0E10;color:#EDEEF0;display:flex;height:100vh;overflow:hidden}
.sidebar{width:260px;background:#121214;border-right:1px solid #1F1F23;display:flex;flex-direction:column;justify-content:space-between}
.main{flex:1;display:flex;flex-direction:column}
.topbar{height:56px;border-bottom:1px solid #1F1F23;display:flex;align-items:center;justify-content:space-between;padding:0 24px}
.logo{font-weight:800;font-size:20px;letter-spacing:-0.5px;display:flex;align-items:center;gap:8px}
.logo span{background:#8B5CF6;padding:2px 8px;border-radius:6px;font-size:12px}
.menu{padding:16px}
.menu h4{color:#6E6E77;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px}
.menu a{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;color:#A1A1AA;text-decoration:none;font-size:14px}
.menu a.active,.menu a:hover{background:#1E1E22;color:white}
.dashboard{padding:24px;overflow-y:auto;flex:1}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:20px 0}
.card{background:#17171A;border:1px solid #232326;border-radius:12px;padding:16px}
.card h3{font-size:13px;color:#A1A1AA;margin-bottom:8px}
.card b{font-size:22px}
.projects{display:grid;grid-template-columns:1.5fr 1fr;gap:16px}
.proj-list,.templates{background:#17171A;border:1px solid #232326;border-radius:12px;padding:16px}
.btn{background:#8B5CF6;color:white;border:none;padding:10px 16px;border-radius:8px;font-weight:600;cursor:pointer}
.btn-black{background:#232326;color:white}
.chat{width:380px;background:#121214;border-left:1px solid #1F1F23;display:flex;flex-direction:column}
.chatbox{flex:1;padding:16px;overflow-y:auto}
.msg{background:#232326;padding:12px;border-radius:12px;margin-bottom:12px;font-size:14px;line-height:1.5}
.msg.me{background:#8B5CF6;color:white;margin-left:30px}
.inputbar{padding:12px;border-top:1px solid #1F1F23;display:flex;gap:8px}
.inputbar input{flex:1;background:#1E1E22;border:1px solid #2A2A2E;border-radius:8px;padding:10px;color:white}
.mobile-badge{background:#00D395;color:black;padding:4px 8px;border-radius:20px;font-size:11px;font-weight:700}
</style>
</head>
<body>
<div class="sidebar">
<div>
<div style="padding:16px" class="logo">⬣ ADRYNX <span>PRO</span></div>
<div class="menu">
<h4>Workspace</h4>
<a class="active">🏠 Home</a>
<a>📥 Inbox <span style="margin-left:auto;background:#2A2A2E;padding:2px 6px;border-radius:4px">3</span></a>
<a>🔍 Search</a>
<h4>Projects</h4>
<a>🚀 Lancement Boutique Brazza</a>
<a>🧪 Recherche Marché</a>
<a>📢 Campagne Mobile Money</a>
<h4>AI Agents</h4>
<a>✨ Assistant Écriture</a>
<a>📊 Analyste Data</a>
</div>
</div>
<div style="padding:16px;border-top:1px solid #1F1F23;display:flex;justify-content:space-between;align-items:center">
<div style="display:flex;gap:8px;align-items:center"><div style="width:32px;height:32px;background:#8B5CF6;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700">J</div><div><div style="font-size:13px;font-weight:600">Jonathan</div><div style="font-size:11px;color:#6E6E77">Brazzaville • Pro</div></div></div>
</div>
</div>

<div class="main">
<div class="topbar">
<div><h2>Dashboard</h2><p style="color:#6E6E77;font-size:13px">Bienvenue Jonathan — voici ton workspace aujourd'hui</p></div>
<div style="display:flex;gap:8px"><button class="btn-black btn">+ New Doc</button><button class="btn">✨ New AI Chat</button></div>
</div>
<div class="dashboard">
<div class="cards">
<div class="card"><h3>✨ Tokens Used</h3><b>12.4K / 50K</b><p style="font-size:12px;color:#6E6E77;margin-top:6px">24% limite • +12% cette semaine</p></div>
<div class="card"><h3>⚡ AI Calls</h3><b>342 calls</b><p style="font-size:12px;color:#6E6E77;margin-top:6px">98% réussite • Projet Congo</p></div>
<div class="card"><h3>📄 Active Docs</h3><b>18 docs</b><p style="font-size:12px;color:#6E6E77;margin-top:6px">5 mis à jour aujourd'hui</p></div>
<div class="card"><h3>👥 Team <span class="mobile-badge">Mobile Money ON</span></h3><b>6 membres</b><p style="font-size:12px;color:#6E6E77;margin-top:6px">Paiement Airtel • MTN • M-Pesa</p></div>
</div>

<div class="projects">
<div class="proj-list">
<h3 style="margin-bottom:12px">Recent Projects →</h3>
<div style="background:#1E1E22;padding:12px;border-radius:10px;margin-bottom:12px"><b>🚀 Boutique Brazza</b> <span style="background:#2A2A2E;padding:2px 6px;border-radius:6px;font-size:11px">En cours</span><p style="font-size:13px;color:#A1A1AA;margin-top:6px">Business plan + calcul prix FCFA + Mobile Money</p><div style="height:4px;background:#2A2A2E;border-radius:4px;margin-top:10px"><div style="width:70%;height:100%;background:#8B5CF6"></div></div></div>
<div style="background:#1E1E22;padding:12px;border-radius:10px"><b>🧪 Recherche Marché Congo</b> <span style="background:#0A3D2E;color:#00D395;padding:2px 6px;border-radius:6px;font-size:11px">Complété</span><p style="font-size:13px;color:#A1A1AA;margin-top:6px">12 papiers analysés sur paiement mobile Afrique</p></div>
</div>
<div class="templates">
<h3>Templates • Browse →</h3>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px">
<div style="background:#1E1E22;padding:10px;border-radius:8px;font-size:13px"><b>📝 Business Plan Congo</b><br><span style="color:#6E6E77">Avec prix FCFA + Mobile Money</span></div>
<div style="background:#1E1E22;padding:10px;border-radius:8px;font-size:13px"><b>📢 Pub MTN/Airtel</b><br><span style="color:#6E6E77">Génère campagne SMS</span></div>
<div style="background:#1E1E22;padding:10px;border-radius:8px;font-size:13px"><b>📊 Analyse Ventes</b><br><span style="color:#6E6E77">CSV + insights</span></div>
<div style="background:#1E1E22;padding:10px;border-radius:8px;font-size:13px"><b>📄 Devis Pro</b><br><span style="color:#6E6E77">Facture Mobile Money</span></div>
</div>
<button onclick="pay()" style="width:100%;margin-top:16px;background:#00D395;color:black;border:none;padding:12px;border-radius:8px;font-weight:800;cursor:pointer">💳 Payer 5000 FCFA avec Mobile Money</button>
</div>
</div>
</div>
</div>

<div class="chat">
<div style="padding:16px;border-bottom:1px solid #1F1F23;display:flex;justify-content:space-between"><b>✨ ADRYNX Chat</b><span style="font-size:11px;color:#6E6E77">GPT-5 • Contexte Projet</span></div>
<div class="chatbox" id="chatbox">
<div class="msg me">Résume le lancement Q1 risques et next steps en 4 points</div>
<div class="msg"><b>ADRYNX:</b> Voici le résumé pour Boutique Brazza Q1:<br>• Risque: Délai fournisseur → solution: backup Pointe-Noire<br>• Risque: Frais MTN 18% au dessus → réduire et pousser Airtel Money<br>• Next: Finaliser page avec prix FCFA d'ici Mercredi<br>• Next: Tester paiement M-Pesa avant lancement</div>
</div>
<div class="inputbar">
<input id="inp" placeholder="Ask ADRYNX anything... @K pour commandes, /payer pour Mobile Money">
<button class="btn" onclick="send()">➤</button>
</div>
</div>

<script>
function pay(){
 alert('ADRYNX Mobile Money: Redirection Airtel Money / MTN MoMo - 5000 FCFA - Intégration en cours. API: adrynx.py');
 window.open('https://www.mtn.cg/momo','_blank');
}
function send(){
 let i=document.getElementById('inp');
 let box=document.getElementById('chatbox');
 if(!i.value) return;
 box.innerHTML+=`<div class='msg me'>${i.value}</div>`;
 let q=i.value; i.value='';
 fetch('/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message:q})})
 .then(r=>r.json()).then(d=>{
   box.innerHTML+=`<div class='msg'><b>ADRYNX:</b> ${d.reply || 'Traitement en cours... Je crée le projet pour toi.'}</div>`;
   box.scrollTop=box.scrollHeight;
 }).catch(()=>{ box.innerHTML+=`<div class='msg'><b>ADRYNX:</b> Mode démo local - Connecte adrynx.py pour réponse IA réelle.</div>`; })
}
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML_LINEAR

@app.post("/chat")
async def chat_api(request: Request):
    data = await request.json()
    msg = data.get("message","")
    if ADRYNX_ENGINE:
        try:
            reply = ADRYNX_ENGINE.process(msg)
            return {"reply": reply}
        except Exception as e:
            return {"reply": f"Erreur moteur: {e} - Message reçu: {msg}"}
    return {"reply": f"ADRYNX a bien reçu: '{msg}'. Connecte ton adrynx.py pour activer l'IA complète + paiement Mobile Money."}

@app.get("/health")
async def health():
    return {"status":"live", "platform":"ADRYNX Linear OS v5 Congo", "engine": bool(ADRYNX_ENGINE)}
