# app.py - ADRYNX v6 - Command Center Phoenix FINAL
from flask import Flask, render_template_string, request, jsonify
import json, re

app = Flask(__name__)

PHOENIX_VIDEO = "https://files.catbox.moe/y2nvi4.mp4"

# --- PARENTS IA FIX ---
def reponse_sociale(q):
    return "Salut ! C'est ADRYNX. Je suis là. Tu veux qu'on lance quoi ? Plus que l'impossible 🚀"

def reponse_identite_immuable():
    return "Je suis ADRYNX, créé par Jonathan Dejah OBENDA le 2 juin 2026. Workspace futur Afrique."

# Remplace ton ancien controler_parent par celui-ci
def controler_parent_fix(question, candidat, contexte):
    intent = contexte.get("intent","")
    q = question.strip().lower()
    # BLOQUEUR 0 appel
    if len(q) <= 5 or intent in ("salutation","conversation"):
        if q in ["cc","c c","salut","slt","yo","cc?"]:
            return {"reponse": reponse_sociale(question), "valide": True}
    if intent == "identite":
        return {"reponse": reponse_identite_immuable(), "valide": True}
    return {"reponse": candidat, "valide": True}

# --- FRONTEND UNIQUE - SYNTHÈSE DES 3 IMAGES ---
HTML = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ADRYNX - Command Center Phoenix</title>
<style>
body{background:#05050A;color:white;font-family:Inter,sans-serif;margin:0;display:flex;height:100vh}
.sidebar{width:260px;background:rgba(255,255,255,0.03);border-right:1px solid #222;padding:20px}
.main{flex:1;padding:20px;overflow:auto}
.card{background:rgba(255,255,255,0.05);border:1px solid #222;border-radius:16px;padding:16px;margin-bottom:16px;backdrop-filter:blur(10px)}
.glow{box-shadow:0 0 20px #7B5CFF55}
video{width:100%;border-radius:12px}
.btn{width:100%;background:#00FF88;color:black;padding:16px;border-radius:12px;font-weight:bold;border:0;cursor:pointer;box-shadow:0 0 25px #00FF8855}
</style></head><body>
<div class="sidebar">
  <h2>ADRYNX <span style="color:#7B5CFF">.</span></h2>
  <p>WORKSPACE FUTUR / AFRIQUE PAY</p>
  <div class="card glow"><video src="{{video}}" autoplay muted loop playsinline></video><p>PHÉNIX VIDEO CORE LIVE</p></div>
  <div class="card">CRISTAL ENGINE 98.2% ON</div>
  <div class="card">Mobile Money LIVE ON</div>
  <p>Jonathan - Brazzaville</p>
</div>
<div class="main">
  <div style="display:flex;gap:16px"><div class="card" style="flex:1">Boutique Brazza Futur</div><div class="card" style="flex:1">ADRYNX v6</div></div>
  <button class="btn" onclick="alert('Paiement 5000 FCFA activé')">ACTIVER PAIEMENT 5000 FCFA</button>
  <div class="card" style="margin-top:20px"><h3>Phoenix Chat Vidéo</h3><div id="chat"></div>
  <input id="q" placeholder="Tape Cc..." style="width:80%;padding:12px;border-radius:8px;background:#111;color:white;border:1px solid #333"><button onclick="ask()" style="padding:12px">Envoyer</button></div>
</div>
<script>
async function ask(){
  let q=document.getElementById('q').value;
  document.getElementById('chat').innerHTML+=`<p><b>Toi:</b> ${q}</p>`;
  let r=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q})});
  let d=await r.json();
  document.getElementById('chat').innerHTML+=`<p><b>ADRYNX:</b> ${d.reponse}</p>`;
  document.getElementById('q').value='';
}
</script></body></html>
"""

@app.route("/")
def index():
    return render_template_string(HTML, video=PHOENIX_VIDEO)

@app.route("/ask", methods=["POST"])
def ask():
    data = request.json
    question = data.get("q","")
    # Ton pipeline normal ici
    intent = "salutation" if question.lower().strip() in ["cc","slt","salut","yo"] else "conversation"
    candidat = f"Reçu: {question} - On avance plus que l'impossible."
    
    contexte = {"intent": intent, "mode": "social"}
    final = controler_parent_fix(question, candidat, contexte)
    return jsonify(final)

if __name__ == "__main__":
    app.run(port=5000, debug=True)
