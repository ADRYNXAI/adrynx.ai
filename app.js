const chat=document.getElementById('chat'),input=document.getElementById('input'),fileInput=document.getElementById('fileInput');
let history=JSON.parse(localStorage.getItem('adrynx_h')||'[]');
let isPremium = localStorage.getItem('adrynx_premium') === '1';
let pendingImage = null;
let msgCount = parseInt(localStorage.getItem('adrynx_count')||'0');

function updateBadge(){ document.getElementById('premiumBadge').textContent=isPremium?'PREMIUM 1000F':'GRATUIT '+msgCount+'/3'; document.getElementById('planText').textContent=isPremium?'Plan Premium':'Plan Gratuit'; }
function add(t,w){let d=document.createElement('div');d.className='msg '+w;d.innerHTML=t.replace(/\n/g,'<br>');chat.appendChild(d);chat.scrollTop=chat.scrollHeight;return d;}
function newChat(){ localStorage.removeItem('adrynx_h'); history=[]; chat.innerHTML=''; add("ADRYNX Phoenix Prime 🦅💎<br>Je suis l'IA de Jonathan Obenda. Envoie ton cours, je t'explique. Tape 'génère' pour créer une image.","ai"); }

async function send(){
 const q=input.value.trim(); if(!q &&!pendingImage) return;
 if(!isPremium && msgCount>=3){ add("🔒 <b>Limite gratuite atteinte.</b><br>Envoie 1000F MTN MoMo à Jonathan Obenda pour débloquer PDF + Images + Voix illimitée.<br>Tape <code>activatePremium()</code> après paiement.","ai"); return; }
 add(q,'user'); history.push({role:"user",content:q}); input.value='';
 const loader=add('⚡ Phoenix Prime réfléchit...','ai');
 try{
  const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:q,history,image:pendingImage})});
  const data=await r.json(); loader.innerHTML=data.reply;
  if('speechSynthesis' in window){ let u=new SpeechSynthesisUtterance(data.reply.replace(/<[^>]*>/g,'').slice(0,200)); u.lang='fr-FR'; speechSynthesis.speak(u); }
  history.push({role:"assistant",content:data.reply}); localStorage.setItem('adrynx_h',JSON.stringify(history.slice(-30)));
  if(!isPremium){ msgCount++; localStorage.setItem('adrynx_count',msgCount); updateBadge(); }
  pendingImage=null;
 }catch(e){loader.innerHTML="Je suis là même offline. Réessaie."}
}

function triggerFile(){ if(!isPremium){add("🔒 Analyse PDF/Photo = PREMIUM 1000F","ai");return;} fileInput.click(); }
fileInput.addEventListener('change',e=>{
 const file=e.target.files[0]; if(!file)return; add(`📄 ${file.name} reçu - Analyse...`,'user');
 const reader=new FileReader(); reader.onload=()=>{ pendingImage=reader.result.split(',')[1]; input.value=`Analyse ce cours: ${file.name}`; send(); }; reader.readAsDataURL(file);
});

window.send=send; window.triggerFile=triggerFile;
window.startVoice=()=>{
 const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
 if(!SR){alert("Micro non supporté");return;}
 const rec=new SR(); rec.lang='fr-FR'; rec.start(); rec.onresult=ev=>{input.value=ev.results[0][0].transcript; send();};
};
window.activatePremium=()=>{ localStorage.setItem('adrynx_premium','1'); isPremium=true; updateBadge(); add("✅ PREMIUM ACTIVÉ! Merci Jonathan.","ai"); };
window.newChat=newChat;

input.addEventListener('keydown',e=>{if(e.key==='Enter')send()});
history.forEach(m=>add(m.content,m.role==='user'?'user':'ai'));
if(!history.length) add("Je suis ADRYNX Phoenix Prime, créée par Jonathan Dejah OBENDA...<br>Envoie ton cours, je l'explique, je te fais réussir.","ai");
updateBadge();
