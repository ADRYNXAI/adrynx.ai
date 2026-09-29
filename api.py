from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

HTML = """
<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ADRYNX PHOENIX VIDEO - Futur</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@700&family=Inter:wght@400;600&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
body{background:#050507;color:#EDEEF0;font-family:'Inter',sans-serif;height:100vh;display:flex;overflow:hidden}
#particles{position:fixed;inset:0;z-index:0}
.sidebar{width:280px;background:rgba(18,18,20,0.88);backdrop-filter:blur(24px);border-right:1px solid rgba(139,92,246,0.28);z-index:2;display:flex;flex-direction:column}
.logo-box{padding:22px;text-align:center;border-bottom:1px solid rgba(255,255,255,0.06)}
.phoenix-wrap{width:122px;height:122px;margin:0 auto;position:relative;border-radius:50%;overflow:hidden;box-shadow:0 0 28px #8B5CF6, 0 0 60px #00D9FF;animation:float 3s ease-in-out infinite;cursor:pointer;border:2px solid rgba(139,92,246,0.4)}
.phoenix-wrap video{width:100%;height:100%;object-fit:cover}
.phoenix-wrap:hover{transform:scale(1.14);box-shadow:0 0 40px #8B5CF6, 0 0 80px #00D9FF}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
.logo-text{font-family:'Space Grotesk';font-size:26px;letter-spacing:5px;font-weight:700;margin-top:14px;background:linear-gradient(90deg,#8B5CF6,#00D9FF);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.slogan{font-size:11px;color:#8B5CF6;letter-spacing:2.5px;margin-top:4px;opacity:0.9}
.menu{padding:16px;flex:1;overflow:auto}
.menu h4{font-size:10px;color:#6E6E77;letter-spacing:1.5px;margin:18px 0 8px;text-transform:uppercase}
.menu a{display:flex;gap:10px;padding:10px 12px;border-radius:10px;color:#A1A1AA;text-decoration:none;font-size:13.5px;transition:0.2s;border:1px solid transparent}
.menu a:hover,.menu a.active{background:rgba(139,92,246,0.15);border-color:rgba(139,92,246,0.35);color:white;box-shadow:0 0 20px rgba(139,92,246,0.25)}
.main{flex:1;z-index:2;display:flex;flex-direction:column;background:radial-gradient(600px at 20% 0%, rgba(139,92,246,0.18), transparent), radial-gradient(600px at 80% 100%, rgba(0,217,255,0.12), transparent)}
.top{height:64px;border-bottom:1px solid rgba(255,255,255,0.06);display:flex;align-items:center;justify-content:space-between;padding:0 28px;backdrop-filter:blur(12px)}
.card{background:rgba(23,23,26,0.88);backdrop-filter:blur(18px);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:18px;transition:0.3s}
.card:hover{border-color:rgba(139,92,246,0.45);transform:translateY(-2px);box-shadow:0 10px 30px rgba(0,0,0,0.6), 0 0 25px rgba(139,92,246,0.18)}
.btn{padding:10px 18px;border-radius:10px;border:none;font-weight:700;cursor:pointer}
.btn-p{background:linear-gradient(90deg,#8B5CF6,#7C3AED);color:white;box-shadow:0 0 20px rgba(139,92,246,0.6)}
.btn-momo{background:#00D395;color:black;font-weight:900;box-shadow:0 0 20px rgba(0,211,149,0.5);width:100%;margin-top:14px;padding:14px}
.chat{width:380px;background:rgba(18,18,20,0.92);backdrop-filter:blur(24px);border-left:1px solid rgba(139,92,246,0.18);z-index:2;display:flex;flex-direction:column}
.msg{padding:12px 14px;border-radius:14px;margin-bottom:10px;font-size:13.5px;line-height:1.5;border:1px solid rgba(255,255,255,0.06)}
.msg.me{background:linear-gradient(90deg,#8B5CF6,#7C3AED);color:white;border:none;margin-left:20px}
</style></head><body>
<canvas id="particles"></canvas>
<div class="sidebar">
<div class="logo-box">
<div class="phoenix-wrap" onclick="this.firstElementChild.play()">
<video autoplay loop muted playsinline poster="">
<source src="https://files.catbox.moe/y2nvi4.mp4" type="video/mp4">
</video>
</div>
<div class="logo-text">ADRYNX</div>
<div class="slogan">Plutôt que l'impossible</div>
</div>
<div class="menu">
<h4>Workspace Futur</h4>
<a class="active">⬣ Dashboard Phoenix Vidéo</a>
<a>⚡ Orchestrateur IA</a>
<a>📦 Projets Vivants</a>
<h4>Afrique Pay</h4>
<a>💳 Mobile Money LIVE <span style="margin-left:auto;background:#00D395;color:black;padding:2px 6px;border-radius:20px;font-size:10px;font-weight:800">ON</span></a>
<a>🌍 Templates Congo</a>
<h4>Energy</h4>
<a>🔥 Phénix Vidéo : Actif</a>
</div>
<div style="padding:16px;border-top:1px solid rgba(255,255,255,0.06);display:flex;gap:10px;align-items:center"><div style="width:36px;height:36px;background:linear-gradient(135deg,#8B5CF6,#00D9FF);border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800">J</div><div><div style="font-size:13px;font-weight:700">Jonathan • Brazzaville</div><div style="font-size:11px;color:#00D395">● Phoenix Video Live</div></div></div>
</div>
<div class="main">
<div class="top"><div><h2 style="font-family:'Space Grotesk'">Command Center Phoenix</h2><p style="color:#6E6E77;font-size:12px">Logo vidéo vivant • Particules • Brazzaville Node</p></div><div style="display:flex;gap:8px"><button class="btn" style="background:#232326;color:white">+ New Universe</button><button class="btn btn-p">✨ Deploy Phoenix</button></div></div>
<div style="padding:24px;overflow:auto;flex:1;display:grid;grid-template-columns:1fr 1fr;gap:16px">
<div class="card"><h4 style="color:#A1A1AA;font-size:11px">⚡ PHÉNIX VIDEO CORE</h4><b style="font-size:28px;background:linear-gradient(90deg,#8B5CF6,#00D9FF);-webkit-background-clip:text;-webkit-text-fill-color:transparent">LIVE</b><p style="color:#6E6E77;font-size:12px;margin-top:8px">Vidéo autoplay • Loop infini • Catbox CDN</p></div>
<div class="card"><h4 style="color:#A1A1AA;font-size:11px">💎 CRISTAL ENGINE</h4><b style="font-size:28px">98.2% Précision</b><p style="color:#6E6E77;font-size:12px;margin-top:8px">adrynx.py + phoenix.mp4 fusionnés</p></div>
<div class="card" style="grid-column:span 2"><h3>Projets qui brisent l'impossible →</h3><div style="display:flex;gap:12px;margin-top:12px"><div style="flex:1;background:rgba(255,255,255,0.04);padding:12px;border-radius:10px"><b>🚀 Boutique Brazza Futur</b><p style="font-size:12px;color:#A1A1AA">Paiement Airtel + MTN + M-Pesa • Design futuriste</p><div style="height:4px;background:#2A2A2E;border-radius:4px;margin-top:8px"><div style="width:92%;height:100%;background:linear-gradient(90deg,#8B5CF6,#00D9FF)"></div></div></div><div style="flex:1;background:rgba(255,255,255,0.04);padding:12px;border-radius:10px"><b>🧬 ADRYNX v6 Phoenix</b><p style="font-size:12px;color:#A1A1AA">Le premier OS avec logo vivant d'Afrique</p></div></div><button class="btn btn-momo">💳 ACTIVER PAIEMENT 5000 FCFA - MOBILE MONEY FUTUR</button></div>
</div>
</div>
<div class="chat"><div style="padding:16px;border-bottom:1px solid rgba(255,255,255,0.06)"><b>✨ Phoenix Chat Vidéo</b><span style="float:right;font-size:10px;color:#8B5CF6">GPT-5 • Mémoire Cristal</span></div><div style="flex:1;padding:16px;overflow:auto"><div class="msg me">Montre le phénix vidéo en live</div><div class="msg"><b style="color:#8B5CF6">ADRYNX Phoenix:</b> C'est fait Jonathan. Le phénix est vivant et respire. Au survol il pulse, au clic il explose. C'est ton branding qui respire. Prêt pour conquérir Brazzaville et le monde ?</div></div><div style="padding:12px;border-top:1px solid rgba(255,255,255,0.06);display:flex;gap:8px"><input placeholder="Commande Phoenix... /payer /creer" style="flex:1;background:rgba(255,255,255,0.06);border:1px solid rgba(139,92,246,0.2);border-radius:10px;padding:10px;color:white"><button class="btn btn-p">➤</button></div></div>
<script>
const c=document.getElementById('particles'),x=c.getContext('2d');function r(){c.width=innerWidth;c.height=innerHeight}r();onresize=r;
let p=[];for(let i=0;i<90;i++)p.push({x:Math.random()*innerWidth,y:Math.random()*innerHeight,vx:(Math.random()-0.5)*0.6,vy:(Math.random()-0.5)*0.6,s:Math.random()*2+0.5});
(function a(){x.clearRect(0,0,c.width,c.height);p.forEach(o=>{o.x+=o.vx;o.y+=o.vy;if(o.x<0||o.x>c.width)o.vx*=-1;if(o.y<0||o.y>c.height)o.vy*=-1;x.beginPath();x.arc(o.x,o.y,o.s,0,6.28);x.fillStyle=o.s>1.6?'#8B5CF6':'#00D9FF';x.globalAlpha=0.5;x.fill();});requestAnimationFrame(a)})();
</script></body></html>
"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML

@app.get("/health")
async def health():
    return {"status":"PHOENIX VIDEO LIVE - https://files.catbox.moe/y2nvi4.mp4"}
