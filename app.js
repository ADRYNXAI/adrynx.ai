const chat=document.getElementById('chat'),input=document.getElementById('input'),fileInput=document.getElementById('fileInput');
const preview=document.getElementById('preview');
let history=JSON.parse(localStorage.getItem('adrynx_h')||'[]');
let isPremium = localStorage.getItem('adrynx_premium') === '1';
let pendingImage = null;
let msgCount = parseInt(localStorage.getItem('adrynx_count')||'0');
const FREE_LIMIT = 25;

function updateBadge(){
  const b=document.getElementById('premiumBadge');
  if(b) b.textContent=isPremium?`PREMIUM 1000F`:`GRATUIT ${msgCount}/${FREE_LIMIT}`;
  const p=document.getElementById('planText');
  if(p) p.textContent=isPremium?'Plan Premium 1000F/semaine':'Plan Gratuit';
}
function add(t,w){
  let d=document.createElement('div');
  d.className='msg '+w;
  d.innerHTML=t.replace(/\n/g,'<br>');
  chat.appendChild(d);
  chat.scrollTop=chat.scrollHeight;
  return d;
}
function newChat(){
  localStorage.removeItem('adrynx_h');
  history=[];
  chat.innerHTML='';
  add("ADRYNX Phoenix Prime 🦅💎<br>Je suis l'IA de Jonathan Obenda. Envoie ton cours, je t'explique. Tape <b>'génère une image de...'</b> pour créer.","ai");
}
async function send(){
 const q=input.value.trim();
 if(!q &&!pendingImage) return;
 if(!isPremium && msgCount>=FREE_LIMIT){
   add(`🔒 <b>Limite gratuite atteinte (${FREE_LIMIT}/${FREE_LIMIT}).</b><br>💎 Passe Premium <b>1000F/semaine</b> = Accès GPT-4o, Claude 3.5, Gemini Pro + Photos/PDF illimités + Images + Vocal.<br>Paye MTN MoMo/Airtel Money et tape <code>activatePremium()</code>.`,"ai");
   return;
 }
 if(q.toLowerCase().startsWith("génère") || q.toLowerCase().startsWith("genere") || q.toLowerCase().includes("image de") || q.toLowerCase().startsWith("cree une image")){
   add(q,'user');
   input.value='';
   const loader=add('🎨 Génération image gratuite (Pollinations)...','ai');
   try{
     const r=await fetch('/api/image',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:q})});
     const data=await r.json();
     loader.innerHTML=`Image: ${q}<br><img src="${data.image_url}" style="max-width:100%;border-radius:12px;margin-top:8px" onload="chat.scrollTop=chat.scrollHeight" />`;
     history.push({role:"user",content:q});
     history.push({role:"assistant",content:`[IMAGE] ${data.image_url}`});
   }catch(e){loader.innerHTML="Erreur image, réessaie."}
   return;
 }
 add(q,'user');
 history.push({role:"user",content:q});
 input.value='';
 if(preview){ preview.style.display='none'; preview.src=''; }
 const loader=add('⚡ Phoenix Prime réfléchit...','ai');
 try{
  const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:q,history,image:pendingImage,isPremium:isPremium})});
  const data=await r.json();
  loader.innerHTML=data.reply.replace(/\n/g,'<br>');
  history.push({role:"assistant",content:data.reply});
  localStorage.setItem('adrynx_h',JSON.stringify(history.slice(-30)));
  if(!isPremium){ msgCount++; localStorage.setItem('adrynx_count',msgCount); updateBadge(); }
  pendingImage=null;
 }catch(e){loader.innerHTML="Je suis là même offline. Réessaie. 🔥"}
}
function triggerFile(){
  if(!isPremium){add("🔒 Analyse Photo/PDF = PREMIUM 1000F/semaine. Tape <code>activatePremium()</code> après paiement.","ai");return;}
  fileInput.click();
}
fileInput.addEventListener('change',e=>{
 const file=e.target.files
