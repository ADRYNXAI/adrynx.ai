"""
ADRYNX - API WEB (FastAPI)
A mettre dans le MEME dossier que adrynx.py.

Lancement local :
    pip install fastapi uvicorn
    uvicorn api:app --reload
Puis ouvrir : http://127.0.0.1:8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from adrynx import traiter_question

app = FastAPI(title="ADRYNX AI")

# Pendant les tests, on autorise toutes les origines.
# A restreindre (ex: ["https://tonsite.com"]) avant une vraie mise en ligne publique.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Question(BaseModel):
    texte: str
    telephone: str | None = None


class Reponse(BaseModel):
    texte: str


@app.post("/api/question", response_model=Reponse)
def poser_question(q: Question):
    reponse = traiter_question(q.texte, telephone=q.telephone)
    return Reponse(texte=reponse)


@app.get("/", response_class=HTMLResponse)
def page_accueil():
    return PAGE_HTML


PAGE_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ADRYNX AI</title>
<style>
  :root { color-scheme: light dark; }
  body {
    font-family: system-ui, -apple-system, Segoe UI, Arial, sans-serif;
    max-width: 720px;
    margin: 0 auto;
    padding: 24px 16px 100px;
    background: #0f1115;
    color: #eee;
  }
  h1 { text-align: center; font-size: 1.4rem; margin-bottom: 4px; }
  p.sous_titre { text-align: center; color: #999; margin-top: 0; font-size: .9rem; }
  #fil { display: flex; flex-direction: column; gap: 10px; margin-top: 20px; }
  .msg { padding: 10px 14px; border-radius: 12px; max-width: 85%; line-height: 1.4; white-space: pre-wrap; }
  .utilisateur { align-self: flex-end; background: #2b6cff; color: white; }
  .adrynx { align-self: flex-start; background: #23262f; }
  .attente { align-self: flex-start; background: #23262f; opacity: .6; font-style: italic; }
  form {
    position: fixed; bottom: 0; left: 0; right: 0;
    display: flex; gap: 8px; padding: 12px;
    background: #0f1115; border-top: 1px solid #23262f;
  }
  form > div { max-width: 720px; margin: 0 auto; display: flex; gap: 8px; width: 100%; }
  input {
    flex: 1; padding: 12px 14px; border-radius: 10px; border: 1px solid #333;
    background: #1a1d24; color: white; font-size: 1rem;
  }
  button {
    padding: 12px 18px; border-radius: 10px; border: none;
    background: #2b6cff; color: white; font-size: 1rem; cursor: pointer;
  }
  button:disabled { opacity: .5; cursor: default; }
  #zone_tel { display: flex; gap: 8px; margin-top: 16px; }
  #zone_tel input { flex: 1; padding: 10px 12px; border-radius: 10px; border: 1px solid #333; background: #1a1d24; color: white; }
  #zone_tel button { padding: 10px 14px; border-radius: 10px; border: none; background: #444; color: white; cursor: pointer; }
</style>
</head>
<body>
  <h1>ADRYNX AI</h1>
  <p class="sous_titre">Calcul, connaissances, et recherche en direct</p>

  <div id="zone_tel">
    <input id="champ_tel" placeholder="Ton numéro Mobile Money (optionnel)" autocomplete="off">
    <button id="bouton_tel" type="button">Valider</button>
  </div>

  <div id="fil"></div>

  <form id="formulaire">
    <div>
      <input id="champ" autocomplete="off" placeholder="Pose ta question..." autofocus>
      <button id="bouton" type="submit">Envoyer</button>
    </div>
  </form>

<script>
const fil = document.getElementById("fil");
const formulaire = document.getElementById("formulaire");
const champ = document.getElementById("champ");
const bouton = document.getElementById("bouton");
const champTel = document.getElementById("champ_tel");
const boutonTel = document.getElementById("bouton_tel");

champTel.value = localStorage.getItem("adrynx_telephone") || "";
boutonTel.addEventListener("click", () => {
  localStorage.setItem("adrynx_telephone", champTel.value.trim());
  boutonTel.textContent = "Enregistré ✓";
  setTimeout(() => (boutonTel.textContent = "Valider"), 1500);
});

function ajouterMessage(texte, classe) {
  const div = document.createElement("div");
  div.className = "msg " + classe;
  div.textContent = texte;
  fil.appendChild(div);
  window.scrollTo(0, document.body.scrollHeight);
  return div;
}

formulaire.addEventListener("submit", async (e) => {
  e.preventDefault();
  const texte = champ.value.trim();
  if (!texte) return;

  ajouterMessage(texte, "utilisateur");
  champ.value = "";
  champ.disabled = true;
  bouton.disabled = true;
  const attente = ajouterMessage("ADRYNX réfléchit...", "attente");

  try {
    const r = await fetch("/api/question", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texte, telephone: localStorage.getItem("adrynx_telephone") || null }),
    });
    if (!r.ok) throw new Error("Erreur serveur");
    const data = await r.json();
    attente.remove();
    ajouterMessage(data.texte, "adrynx");
  } catch (err) {
    attente.remove();
    ajouterMessage("Erreur : impossible de contacter le serveur.", "adrynx");
  } finally {
    champ.disabled = false;
    bouton.disabled = false;
    champ.focus();
  }
});
</script>
</body>
</html>
"""
