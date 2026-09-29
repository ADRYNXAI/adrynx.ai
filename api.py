# api.py v4.0.1 FIX - Ton design plateforme interactive - Indentation corrigee
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import adrynx

app = FastAPI(title="ADRYNX Platform")

HTML = r"""
<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ADRYNX - Plateforme Interactive</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#0c0c0e;color:#e5e7eb;font-family:system-ui;display:flex;height:100dvh;flex-direction:column}
.top{display:flex;align-items:center;gap:10px;padding:12px 14px;background:#111113;border-bottom:1px solid #232326}
.logo{width:28px;height:28px;background:#4f7cff;border-radius:6px;display:grid;place-items:center;font-weight:800;color:white}
.t1{font-weight:700;font-size:14px}.t2{font-size:11px;color:#9ca3af}
.nav{display:flex;gap:6px;padding:8px 12px;background:#111113;border-bottom:1px solid #1f1f23;overflow:auto}
.nav button{background:#18181b;border:1px solid #27272a;color:#a1a1aa;padding:6px 12px;border-radius:20px;font-size:12px;cursor:pointer;white-space:nowrap}
.nav button.active{background:#4f7cff;color:white;border-color:#4f7cff}
.main{flex:1;display:flex;overflow:hidden}
.sidebar{width:220px;background:#111113;border-right:1px solid #232326;padding:10px;display:none}
@media(min-width:800px){.sidebar{display:block}}
.dash{background:#18181b;border:1px solid #232326;border-radius:12px;padding:12px;margin:12px;font-size:13px;line-height:1.6}
.dash b{color:#fff}
.phone{margin:12px;background:#18181b;border:1px solid #232326;border-radius:12px;padding:10px}
.phone label{font-size:11px;color:#a1a1aa}.row{display:flex;gap:6px;margin-top:6px}
.row input{flex:1;background:#0c0c0e;border:1px solid #2a2a2e;border-radius:8px;padding:8px;color:white}
.row button{background:#4f7cff;border:none;border-radius:8px;color:white;padding:0 12px;font-weight:600;cursor:pointer}
.chat{flex:1;display:flex;flex-direction:column;overflow:hidden}
#msgs{flex:1;overflow:auto;padding:12px;display:flex;flex-direction:column;gap:10px}
.msg{max-width:85%;padding:10px 14px;border-radius:16px;font-size:14px}
.bot{align-self:flex-start;background:#1f2937;color:#e5e7eb;display:flex;gap:8px;border-top-left-radius:4px}
.bot .a{width:22px;height:22px;background:#4f7cff;border-radius:50%;display:grid;place-items:center;font-size:11px;font-weight:700;color:white;min-width:22px}
.user{align-self:flex-end;background:#4f7cff;color:white;border-top-right-radius:4px}
.bar{padding:10px;background:#111113;border-top:1px solid #232326;display:flex;gap:8px}
.bar input{flex:1;background:#18181b;border:1px solid #27272a;border-radius:24px;padding:12px 16px;color:white;outline:none}
.bar button{width:42px;height:42px;border-radius:50%;background:#4f7cff;border:none;color:white;cursor:pointer}
.foot{text-align:center;font-size:10px;color:#52525b;padding:4px}
</style></head><body>
<div class="top"><div class="logo">A</div><div><div class="t1">ADRYNX AI</div><div class="t2">Plateforme Interactive - Jonathan Dejah OBENDA - 02/06/2026</div></div></div>
<div class="nav">
<button class="active" onclick="switchTab('chat',event)">Conversation</button>
<button onclick="switchTab('dashboard',event)">Tableau de bord vivant</button>
<button onclick="switchTab('projets',event)">Projets</button>
<button onclick="switchTab('fichiers',event)">Fichiers</button>
<button onclick="switchTab('profil',event)">Profil</button>
</div>
<div class="main">
<div class="sidebar" id="sidebar">
<div class="phone"><label>Mobile Money</label><div class="row"><input id="phone" placeholder="+242..."><button onclick="savePhone()">OK</button></div></div>
<div id="dash" class="dash">Chargement...</div>
</div>
<div class="chat">
<div id="msgs"><div class="msg bot"><div class="a">A</div><div>Bonjour! Je suis ADRYNX, orchestrateur de ta plateforme. Je comprends - personnalise - agis. Essaie: "Montre mes projets" ou "Cree un projet ADRYNX" ou "Tableau de bord".</div></div></div>
<div class="bar"><input id="q" placeholder="Pose ta question, commande naturelle..." onkeydown="if(event.key==='Enter')send()"><button onclick="send()">➤</button></div>
<div class="foot">adrynx-ai.onrender.com - SOURCE DE VERITE: serveur</div>
</div></div>
<script>
let phone=localStorage.getItem('adrynx_phone')||''; document.getElementById('phone').value=phone;
function savePhone(){
  phone=document.getElementById('phone').value.trim();
  localStorage.setItem('adrynx_phone',phone);
  loadDash();
}
async function switchTab(t,evt){
  document.querySelectorAll('.nav button').forEach(b=>b.classList.remove('active'));
  if(evt) evt.target.classList.add('active');
  if(t==='dashboard'){loadDash(); addBot('Voici ton tableau de bord vivant:');}
  if(t==='projets'){
    let r=await fetch('/api/projects?owner='+encodeURIComponent(phone||'anonyme'));
    let j=await r.json();
    let txt=j.length? j.map(p=>`[${p.id}] ${p.nom} ${p.progression}%`).join('\n') : 'Aucun projet';
    addBot(txt);
  }
  if(t==='chat'){addBot('Mode conversation actif. Contexte global conserve.');}
  if(t==='fichiers'){addBot('Module fichiers bientot disponible.');}
  if(t==='profil'){addBot('Profil: '+ (phone||'anonyme'));}
}
async function loadDash(){
  try{
    let r=await fetch('/api/dashboard?owner='+encodeURIComponent(phone||'anonyme'));
    let d=await r.json();
    document.getElementById('dash').innerHTML=`<b>${d.bonjour}</b><br>PROJETS -> ${d.projets}<br>TACHES -> ${d.taches}<br>MESSAGES -> ${d.messages}<br>ACTIVITE -> ${d.activite}<br>ADRYNX -> ${d.suggestion}`;
  }catch(e){}
}
function addUser(t){
  let d=document.createElement('div');d.className='msg user';d.textContent=t;
  document.getElementById('msgs').appendChild(d);
  document.getElementById('msgs').scrollTop=99999;
}
function addBot(t){
  let c=document.createElement('div');c.className='msg bot';
  let a=document.createElement('div');a.className='a';a.textContent='A';
  let b=document.createElement('div');b.innerText=t;
  c.appendChild(a);c.appendChild(b);
  document.getElementById('msgs').appendChild(c);
  document.getElementById('msgs').scrollTop=99999;
}
async function send(){
  let i=document.getElementById('q');let q=i.value.trim();if(!q)return;
  addUser(q); i.value='';
  let r=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q,telephone:phone})});
  let j=await r.json(); addBot(j.reponse); loadDash();
}
loadDash();
</script></body></html>
"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML

@app.post("/ask")
async def ask(req: Request):
    data = await req.json()
    q = data.get("question", "")
    tel = data.get("telephone", "")
    anon = req.client.host if req.client else "anon"
    rep = adrynx.traiter_question(q, telephone=tel or None, anon=anon)
    return JSONResponse({"reponse": rep})

@app.get("/api/dashboard")
async def dashboard(owner: str = "anonyme"):
    return adrynx.get_dashboard(owner or "anonyme")

@app.get("/api/projects")
async def projects(owner: str = "anonyme"):
    return adrynx.list_projects(owner or "anonyme")

@app.post("/api/projects")
async def create_proj(req: Request):
    data = await req.json()
    owner = data.get("owner", "anonyme")
    nom = data.get("nom", "Nouveau projet")
    pid = adrynx.create_project(owner, nom, data.get("objectif", ""))
    return {"id": pid, "nom": nom}

@app.get("/health")
async def health():
    return {"status": "ok", "version": "4.0-fix", "architecture": "monolithe modulaire + event bus"}
