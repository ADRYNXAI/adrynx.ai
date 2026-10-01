const chat=document.getElementById('chat'),input=document.getElementById('input'),btn=document.getElementById('sendBtn');
let history=JSON.parse(localStorage.getItem('adrynx_h')||'[]');
function add(t,w){let d=document.createElement('div');d.className='msg '+w;d.innerHTML=t.replace(/\n/g,'<br>');chat.appendChild(d);chat.scrollTop=chat.scrollHeight;return d;}
async function send(){
 const q=input.value.trim();if(!q)return;add(q,'user');history.push({role:"user",content:q});input.value='';input.focus();
 const loader=add('⚡ Phoenix Prime réfléchit...','ai');
 try{
  const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:q,history})});
  const data=await r.json();loader.innerHTML=data.reply;history.push({role:"assistant",content:data.reply});localStorage.setItem('adrynx_h',JSON.stringify(history.slice(-30)));
 }catch(e){loader.innerHTML="Je suis là même offline. Réessaie, je te réponds."}
}
window.send=send;btn.addEventListener('click',send);input.addEventListener('keydown',e=>{if(e.key==='Enter')send()});
history.forEach(m=>add(m.content,m.role==='user'?'user':'ai'));
if(!history.length)add("ADRYNX Phoenix Prime 🦅💎<br>Je suis l'IA de Jonathan Obenda. Téléchargeable, imbattable, je ne plante jamais. Parle-moi.","ai");
