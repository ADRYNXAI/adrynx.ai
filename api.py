"""
ADRYNX - API WEB (FastAPI)
A mettre dans le MEME dossier que adrynx.py.

Lancement local :
    pip install fastapi uvicorn python-multipart
    uvicorn api:app --reload
Puis ouvrir : http://127.0.0.1:8000

Nouveau : /admin?secret=TON_SECRET_ADMIN
    Tableau de bord protégé (même secret que ADRYNX_ADMIN_SECRET) qui
    affiche le nombre d'utilisateurs/premium/bloqués et un bouton
    Bloquer/Débloquer par numéro de téléphone. Nécessite python-multipart
    (pour lire le formulaire de blocage) — ajoute-le à requirements.txt.
"""
import html

from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from adrynx import (
    bloquer_utilisateur,
    compter_comptes,
    debloquer_utilisateur,
    enregistrer_avis,
    envoyer_email_plainte,
    lister_comptes,
    lister_plaintes,
    traiter_question,
    verifier_secret_admin,
)

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


class Avis(BaseModel):
    telephone: str | None = None
    question: str
    reponse: str
    satisfait: bool
    motif: str | None = None
    commentaire: str | None = None
    capture_nom: str | None = None
    capture_b64: str | None = None  # data URL : data:image/png;base64,...


@app.post("/api/avis")
def poser_avis(a: Avis):
    """👍 : simplement enregistré. 👎 : enregistré ET envoyé par email au
    service client ADRYNX (si l'email est configuré sur le serveur)."""
    avis_id = enregistrer_avis(
        a.telephone, a.question, a.reponse, a.satisfait,
        a.motif, a.commentaire, a.capture_nom, a.capture_b64,
    )
    if a.satisfait:
        return {"id": avis_id, "email_envoye": False}
    succes, message = envoyer_email_plainte(avis_id)
    return {"id": avis_id, "email_envoye": succes, "message": message}


@app.get("/", response_class=HTMLResponse)
def page_accueil():
    return PAGE_HTML


# ------------------------------------------------------------- tableau de bord admin
@app.get("/admin", response_class=HTMLResponse)
def page_admin(secret: str = ""):
    if not verifier_secret_admin(secret):
        return HTMLResponse(
            "<h1>Accès refusé</h1><p>Secret admin manquant ou invalide "
            "(ajoute ?secret=TON_SECRET à l'URL).</p>",
            status_code=403,
        )

    stats = compter_comptes()
    comptes = lister_comptes()
    secret_e = html.escape(secret)

    lignes = ""
    for c in comptes:
        tel_e = html.escape(c["telephone"])
        action = "debloquer" if c["bloque"] else "bloquer"
        libelle = "Débloquer" if c["bloque"] else "Bloquer"
        couleur = "#ff5566" if c["bloque"] else "#2b6cff"
        lignes += f"""
        <tr>
          <td>{tel_e}</td>
          <td>{'Oui' if c['premium'] else 'Non'}</td>
          <td>{c['quota']}</td>
          <td>{'🚫 Bloqué' if c['bloque'] else 'Actif'}</td>
          <td>{html.escape(c['derniere_activite'] or 'jamais')}</td>
          <td>
            <form method="post" action="/admin/action" style="display:inline">
              <input type="hidden" name="secret" value="{secret_e}">
              <input type="hidden" name="telephone" value="{tel_e}">
              <input type="hidden" name="action" value="{action}">
              <button type="submit" style="background:{couleur}">{libelle}</button>
            </form>
          </td>
        </tr>"""

    if not comptes:
        lignes = "<tr><td colspan='6' style='text-align:center;color:#888'>Aucun utilisateur enregistré pour l'instant.</td></tr>"

    lignes_plaintes = ""
    for p in lister_plaintes():
        lignes_plaintes += f"""
        <tr>
          <td>#{p['id']}</td>
          <td>{html.escape(p['cree_le'] or '')}</td>
          <td>{html.escape(p['telephone'] or 'anonyme')}</td>
          <td>{html.escape(p['motif'] or '')}</td>
          <td>{html.escape(p['question'] or '')}</td>
          <td>{html.escape(p['commentaire'] or '')}</td>
          <td>{'📎' if p['a_capture'] else ''}</td>
          <td>{'✉️ envoyé' if p['email_envoye'] else '⚠️ non envoyé'}</td>
        </tr>"""
    if not lignes_plaintes:
        lignes_plaintes = "<tr><td colspan='8' style='text-align:center;color:#888'>Aucune plainte pour l'instant.</td></tr>"

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ADRYNX — Tableau de bord</title>
<style>
  body {{
    font-family: system-ui, -apple-system, Segoe UI, Arial, sans-serif;
    background: #0f1115; color: #eee; margin: 0; padding: 24px 16px 60px;
  }}
  h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
  .stats {{ display: flex; gap: 16px; margin: 20px 0; flex-wrap: wrap; }}
  .stat {{
    background: #1a1d24; padding: 14px 22px; border-radius: 12px;
    border: 1px solid #23262f; min-width: 120px; text-align: center;
  }}
  .stat b {{ display: block; font-size: 1.6rem; }}
  .stat span {{ color: #999; font-size: .85rem; }}
  table {{
    width: 100%; border-collapse: collapse; margin-top: 10px;
    background: #1a1d24; border-radius: 12px; overflow: hidden;
  }}
  th, td {{ padding: 10px 14px; border-bottom: 1px solid #23262f; text-align: left; font-size: .9rem; }}
  th {{ color: #999; font-weight: 600; }}
  button {{
    border: none; color: white; padding: 6px 14px; border-radius: 8px;
    cursor: pointer; font-size: .85rem;
  }}
  .tableau_scroll {{ overflow-x: auto; }}
</style>
</head>
<body>
  <h1>Tableau de bord ADRYNX</h1>
  <div class="stats">
    <div class="stat"><b>{stats['total']}</b><span>utilisateurs</span></div>
    <div class="stat"><b>{stats['premium']}</b><span>premium</span></div>
    <div class="stat"><b>{stats['bloques']}</b><span>bloqués</span></div>
  </div>
  <div class="tableau_scroll">
    <table>
      <tr><th>Téléphone</th><th>Premium</th><th>Quota</th><th>Statut</th><th>Dernière activité</th><th>Action</th></tr>
      {lignes}
    </table>
  </div>

  <h1 style="margin-top:32px">Plaintes</h1>
  <div class="tableau_scroll">
    <table>
      <tr><th>N°</th><th>Date</th><th>Utilisateur</th><th>Motif</th><th>Question</th><th>Commentaire</th><th>Capture</th><th>Email</th></tr>
      {lignes_plaintes}
    </table>
  </div>
</body>
</html>""")


@app.post("/admin/action")
def action_admin(secret: str = Form(...), telephone: str = Form(...), action: str = Form(...)):
    if not verifier_secret_admin(secret):
        return HTMLResponse("Accès refusé", status_code=403)
    if action == "bloquer":
        bloquer_utilisateur(telephone)
    elif action == "debloquer":
        debloquer_utilisateur(telephone)
    return RedirectResponse(url=f"/admin?secret={secret}", status_code=303)


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
  .avis { align-self: flex-start; font-size: .85rem; color: #999; display: flex; align-items: center; gap: 8px; }
  .avis button { padding: 4px 10px; font-size: 1rem; background: #23262f; }
  .fond_modale { position: fixed; inset: 0; background: rgba(0,0,0,.7); display: flex; align-items: center; justify-content: center; padding: 16px; z-index: 10; }
  .modale { background: #1a1d24; padding: 20px; border-radius: 14px; width: 100%; max-width: 420px; display: flex; flex-direction: column; gap: 8px; }
  .modale h3 { margin: 0 0 6px; }
  .modale label { font-size: .85rem; color: #999; }
  .modale select, .modale textarea { padding: 10px; border-radius: 10px; border: 1px solid #333; background: #0f1115; color: white; font-size: 1rem; font-family: inherit; }
  .modale_actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 8px; }
  .modale_actions button { padding: 10px 16px; }
  #annuler_plainte { background: #444; }
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

async function envoyerAvis(donnees) {
  try {
    await fetch("/api/avis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ telephone: localStorage.getItem("adrynx_telephone") || null, ...donnees }),
    });
  } catch (err) { /* un avis raté ne doit jamais bloquer le chat */ }
}

function ajouterAvis(question, reponse) {
  const zone = document.createElement("div");
  zone.className = "avis";
  zone.innerHTML = '<span>Es-tu satisfait de cette réponse ?</span><button type="button" class="oui">👍 Oui</button><button type="button" class="non">👎 Non</button>';
  fil.appendChild(zone);
  zone.querySelector(".oui").addEventListener("click", () => {
    zone.textContent = "Merci pour ton retour !";
    envoyerAvis({ question, reponse, satisfait: true });
  });
  zone.querySelector(".non").addEventListener("click", () => ouvrirPlainte(question, reponse, zone));
}

function ouvrirPlainte(question, reponse, zone) {
  const fond = document.createElement("div");
  fond.className = "fond_modale";
  fond.innerHTML = '<div class="modale"><h3>Précise la raison de ta plainte</h3>'
    + '<label>Motif</label><select id="motif_plainte"><option value="hors_sujet">Réponse hors sujet</option><option value="incomplete">Réponse incomplète</option><option value="incorrecte">Réponse incorrecte</option><option value="autre">Autre</option></select>'
    + '<label>Détails</label><textarea id="commentaire_plainte" rows="4" placeholder="Décris ce qui ne va pas..."></textarea>'
    + '<label>Capture d\'écran du bug (optionnel) : fais ta capture, puis joins-la ici</label><input type="file" id="capture_plainte" accept="image/*">'
    + '<div class="modale_actions"><button type="button" id="annuler_plainte">Annuler</button><button type="button" id="envoyer_plainte">Envoyer</button></div></div>';
  document.body.appendChild(fond);
  fond.querySelector("#annuler_plainte").addEventListener("click", () => fond.remove());
  fond.querySelector("#envoyer_plainte").addEventListener("click", async () => {
    const bouton_envoi = fond.querySelector("#envoyer_plainte");
    bouton_envoi.disabled = true;
    bouton_envoi.textContent = "Envoi...";
    const fichier = fond.querySelector("#capture_plainte").files[0];
    let capture_b64 = null, capture_nom = null;
    if (fichier) {
      capture_nom = fichier.name;
      capture_b64 = await new Promise((ok) => {
        const lecteur = new FileReader();
        lecteur.onload = () => ok(lecteur.result);
        lecteur.readAsDataURL(fichier);
      });
    }
    await envoyerAvis({
      question, reponse, satisfait: false,
      motif: fond.querySelector("#motif_plainte").value,
      commentaire: fond.querySelector("#commentaire_plainte").value.trim(),
      capture_nom, capture_b64,
    });
    fond.remove();
    zone.textContent = "Merci, ta plainte a été transmise à l'équipe ADRYNX.";
  });
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
    ajouterAvis(texte, data.texte);
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
