const chat=document.getElementById('chat'),input=document.getElementById('input'),fileInput=document.getElementById('fileInput');
const preview=document.getElementById('preview');
let history=JSON.parse(localStorage.getItem('adrynx_h')||'[]');
let isPremium = localStorage.getItem('adrynx_premium') === '1';
let pendingImage = null;
let msgCount = parseInt(localStorage.getItem('adrynx_count')||'0');

function updateBadge(){
  const b=document.getElementById('premiumBadge');
  if(b) b.textContent=isPremium?'PREMIUM 1000F':'GRATUIT '+msgCount+'/3';
  const p=document.getElementById('planText');
  if(p) p.textContent=isPremium?'Plan Premium':'Plan Gratuit';
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

 if(!isPremium && msgCount>=3){
   add("🔒 <b>Limite gratuite atteinte (3/3).</b><br>Premium 1000F = Photos/PDF + Images illimitées + Vocal.<br>Paye MTN MoMo/Airtel Money et tape <code>activatePremium()</code>.","ai");
   return;
 }

 // DETECTION GENERATION IMAGE
 if(q.toLowerCase().startsWith("génère") || q.toLowerCase().startsWith("genere") || q.toLowerCase().startsWith("crée une image") || q.toLowerCase().startsWith("cree une image")){
   add(q,'user');
   input.value='';
   const loader=add('🎨 Génération image gratuite (Pollinations)...','ai');
   try{
     const r=await fetch('/api/image',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:q})});
     const data=await r.json();
     loader.innerHTML=`Image: ${q}<br><img src="${data.image_url}" onload="window.scrollTo(0,document.body.scrollHeight)" />`;
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
  const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:q,history,image:pendingImage})});
  const data=await r.json();
  loader.innerHTML=data.reply;
  history.push({role:"assistant",content:data.reply});
  localStorage.setItem('adrynx_h',JSON.stringify(history.slice(-30)));
  if(!isPremium){ msgCount++; localStorage.setItem('adrynx_count',msgCount); updateBadge(); }
  pendingImage=null;
 }catch(e){loader.innerHTML="Je suis là même offline. Réessaie. 🔥"}
}

function triggerFile(){
  if(!isPremium){add("🔒 Analyse Photo/PDF = PREMIUM 1000F. Tape <code>activatePremium()</code> après paiement 1000F.","ai");return;}
  fileInput.click();
}

// Compression auto pour Groq <4MB
fileInput.addEventListener('change',e=>{
 const file=e.target.files[0]; if(!file)return;
 const reader=new FileReader();
 reader.onload=()=>{
   pendingImage=reader.result.split(',')[1];
   if(preview){
     preview.src=reader.result;
     preview.style.display='block';
   }
   add(`📄 ${file.name} prêt - j'analyse...`,'user');
   input.value=`Analyse ce cours: ${file.name} et explique point par point comme un prof`;
   send();
 };
 reader.readAsDataURL(file);
});

window.send=send; window.triggerFile=triggerFile;
window.startVoice=()=>{
 const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
 if(!SR){alert("Micro non supporté sur ce navigateur");return;}
 const rec=new SR(); rec.lang='fr-FR'; rec.start();
 rec.onresult=ev=>{input.value=ev.results[0][0].transcript; send();};
};
window.activatePremium=()=>{ localStorage.setItem('adrynx_premium','1'); isPremium=true; updateBadge(); add("✅ PREMIUM ACTIVÉ! Merci. Tu as débloqué PDF, Photos, Images illimitées. 🔥","ai"); };
window.newChat=newChat;

input.addEventListener('keydown',e=>{if(e.key==='Enter')send()});
history.forEach(m=>{
  if(!m.content.includes('[IMAGE]')) add(m.content,m.role==='user'?'user':'ai');
});
if(!history.length) add("Je suis ADRYNX Phoenix Prime, créée par Jonathan Obenda 🇨🇬<br>Envoie ton cours (photo/PDF) je l'explique, ou dis 'génère une image de...'.","ai");
updateBadge();
