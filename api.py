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


PAGE_HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>ADRYNX AI</title>
<style>
  :root {
    --fond: #0b0d12; --carte: #151922; --carte2: #1c212c; --bord: #262c3a;
    --texte: #e8eaf0; --doux: #8b93a7; --accent: #4f7cff; --accent2: #7b5cff;
    --ok: #35c27a; --err: #ff5d6c;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    background: radial-gradient(1100px 520px at 50% -10%, #1a2140 0%, var(--fond) 60%);
    color: var(--texte);
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
    display: flex; flex-direction: column;
  }
  header {
    display: flex; align-items: center; gap: 12px; padding: 12px 16px;
    border-bottom: 1px solid var(--bord); background: rgba(11,13,18,.7);
    backdrop-filter: blur(8px);
  }
  .logo {
    width: 38px; height: 38px; border-radius: 12px; display: grid; place-items: center;
    font-weight: 800; background: linear-gradient(135deg, var(--accent), var(--accent2));
    box-shadow: 0 4px 16px rgba(79,124,255,.35);
  }
  header h1 { font-size: 1.05rem; margin: 0; }
  header p { margin: 0; font-size: .76rem; color: var(--doux); }
  #badge_tel {
    margin-left: auto; display: none; font-size: .76rem; color: var(--ok);
    background: rgba(53,194,122,.1); border: 1px solid rgba(53,194,122,.3);
    padding: 4px 10px; border-radius: 999px; white-space: nowrap;
  }
  main { flex: 1; overflow-y: auto; padding: 16px; scroll-behavior: smooth; }
  .conteneur { max-width: 720px; margin: 0 auto; display: flex; flex-direction: column; gap: 12px; }

  #zone_tel {
    background: var(--carte); border: 1px solid var(--bord); border-radius: 16px;
    padding: 14px; transition: opacity .4s, transform .4s, max-height .4s, padding .4s, margin .4s;
    max-height: 260px; overflow: hidden;
  }
  #zone_tel.cache { opacity: 0; transform: translateY(-10px); max-height: 0; padding-top: 0; padding-bottom: 0; border-width: 0; margin: 0; }
  #zone_tel label { display: block; font-size: .85rem; margin-bottom: 8px; }
  #zone_tel small { display: block; color: var(--doux); margin-top: 8px; font-size: .75rem; }
  .rangee { display: flex; gap: 8px; }
  input, textarea, select {
    font: inherit; color: var(--texte); background: var(--carte2);
    border: 1px solid var(--bord); border-radius: 12px; padding: 12px 14px; outline: none;
  }
  input:focus, textarea:focus, select:focus { border-color: var(--accent); }
  .rangee input { flex: 1; min-width: 0; }
  button {
    font: inherit; color: #fff; border: none; border-radius: 12px; padding: 12px 18px; cursor: pointer;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
  }
  button:disabled { opacity: .5; cursor: default; }
  #erreur_tel { color: var(--err); font-size: .8rem; margin-top: 8px; display: none; }

  .ligne { display: flex; gap: 8px; align-items: flex-end; animation: entree .25s ease; }
  .ligne.moi { justify-content: flex-end; }
  .avatar {
    width: 28px; height: 28px; flex: none; border-radius: 9px; display: grid; place-items: center;
    font-size: .7rem; font-weight: 800; background: linear-gradient(135deg, var(--accent), var(--accent2));
  }
  .msg { padding: 10px 14px; border-radius: 16px; max-width: 82%; line-height: 1.45; white-space: pre-wrap; overflow-wrap: anywhere; }
  .moi .msg { background: linear-gradient(135deg, var(--accent), var(--accent2)); border-bottom-right-radius: 4px; }
  .adrynx .msg { background: var(--carte); border: 1px solid var(--bord); border-bottom-left-radius: 4px; }
  .systeme { align-self: center; text-align: center; font-size: .82rem; color: var(--ok);
    background: rgba(53,194,122,.08); border: 1px solid rgba(53,194,122,.25);
    padding: 8px 14px; border-radius: 12px; animation: entree .3s ease; }
  .points span { display: inline-block; width: 7px; height: 7px; margin-right: 4px; border-radius: 50%;
    background: var(--doux); animation: saut 1.2s infinite; }
  .points span:nth-child(2) { animation-delay: .15s; }
  .points span:nth-child(3) { animation-delay: .3s; }
  .note_attente { display: block; font-size: .75rem; color: var(--doux); margin-top: 6px; }

  .avis { margin-left: 36px; display: flex; align-items: center; gap: 8px; font-size: .8rem; color: var(--doux); }
  .avis button { padding: 4px 10px; background: var(--carte2); border: 1px solid var(--bord); font-size: .9rem; }
  .avis button:hover { border-color: var(--accent); }

  footer { padding: 10px 12px calc(10px + env(safe-area-inset-bottom)); border-top: 1px solid var(--bord); background: rgba(11,13,18,.85); }
  #formulaire { max-width: 720px; margin: 0 auto; display: flex; gap: 8px; }
  #champ { flex: 1; min-width: 0; border-radius: 999px; padding: 13px 18px; }
  #bouton { border-radius: 999px; width: 48px; padding: 0; font-size: 1.1rem; }

  .fond_modale { position: fixed; inset: 0; background: rgba(0,0,0,.72); display: flex; align-items: center; justify-content: center; padding: 16px; z-index: 10; }
  .modale { background: var(--carte); border: 1px solid var(--bord); border-radius: 18px; padding: 20px; width: 100%; max-width: 440px; display: flex; flex-direction: column; gap: 8px; }
  .modale h3 { margin: 0 0 4px; }
  .modale label { font-size: .82rem; color: var(--doux); }
  .modale_actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 8px; }
  #annuler_plainte { background: var(--carte2); border: 1px solid var(--bord); }

  @keyframes entree { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
  @keyframes saut { 0%, 60%, 100% { transform: translateY(0); } 30% { transform: translateY(-5px); } }
</style>
</head>
<body>
  <header>
    <div class="logo">A</div>
    <div><h1>ADRYNX AI</h1><p>Calcul, connaissances et recherche en direct</p></div>
    <div id="badge_tel"></div>
  </header>

  <main id="zone_chat">
    <div class="conteneur">
      <div id="zone_tel">
        <label for="champ_tel">📱 Ton numéro Mobile Money</label>
        <div class="rangee">
          <input id="champ_tel" type="tel" inputmode="tel" placeholder="+242 06 123 45 67" autocomplete="off">
          <button id="bouton_tel" type="button">Valider</button>
        </div>
        <div id="erreur_tel">Numéro invalide : entre 8 à 15 chiffres, avec ou sans +.</div>
        <small>Il te permet de retrouver ton compte et tes avantages premium.</small>
      </div>
      <div id="fil" class="conteneur"></div>
    </div>
  </main>

  <footer>
    <form id="formulaire" autocomplete="off">
      <input id="champ" placeholder="Pose ta question..." enterkeyhint="send" autofocus>
      <button id="bouton" type="submit" aria-label="Envoyer">➤</button>
    </form>
  </footer>

<script>
const zoneChat = document.getElementById("zone_chat");
const fil = document.getElementById("fil");
const formulaire = document.getElementById("formulaire");
const champ = document.getElementById("champ");
const bouton = document.getElementById("bouton");
const zoneTel = document.getElementById("zone_tel");
const champTel = document.getElementById("champ_tel");
const boutonTel = document.getElementById("bouton_tel");
const erreurTel = document.getElementById("erreur_tel");
const badgeTel = document.getElementById("badge_tel");

function defiler() { zoneChat.scrollTo({ top: zoneChat.scrollHeight, behavior: "smooth" }); }

function ajouterMessage(texte, auteur) {
  const ligne = document.createElement("div");
  ligne.className = "ligne " + (auteur === "moi" ? "moi" : "adrynx");
  if (auteur !== "moi") {
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = "A";
    ligne.appendChild(avatar);
  }
  const bulle = document.createElement("div");
  bulle.className = "msg";
  bulle.textContent = texte;
  ligne.appendChild(bulle);
  fil.appendChild(ligne);
  defiler();
  return { ligne, bulle };
}

function messageSysteme(texte) {
  const div = document.createElement("div");
  div.className = "systeme";
  div.textContent = texte;
  fil.appendChild(div);
  defiler();
}

/* ---------- numéro de téléphone ---------- */
function numeroValide(saisie) {
  const propre = saisie.replace(/[\s.\-()]/g, "");
  return /^\+?\d{8,15}$/.test(propre) ? propre : null;
}
function masquer(numero) {
  if (numero.length <= 6) return numero;
  return numero.slice(0, 4) + "•".repeat(numero.length - 6) + numero.slice(-2);
}
function appliquerTelephone(numero, annoncer) {
  zoneTel.classList.add("cache");
  badgeTel.textContent = "📱 " + masquer(numero);
  badgeTel.style.display = "block";
  if (annoncer) {
    messageSysteme("✓ Ton numéro " + masquer(numero) + " a bien été enregistré. Tu peux maintenant poser tes questions.");
    champ.focus();
  }
}

boutonTel.addEventListener("click", () => {
  const numero = numeroValide(champTel.value);
  if (!numero) {
    erreurTel.style.display = "block";
    champTel.focus();
    return;
  }
  erreurTel.style.display = "none";
  try { localStorage.setItem("adrynx_telephone", numero); } catch (e) {}
  appliquerTelephone(numero, true);
});
champTel.addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); boutonTel.click(); }
});

function telephoneEnregistre() {
  try { return localStorage.getItem("adrynx_telephone") || null; } catch (e) { return null; }
}

/* ---------- avis et plaintes ---------- */
async function envoyerAvis(donnees) {
  try {
    await fetch("/api/avis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({ telephone: telephoneEnregistre() }, donnees)),
    });
  } catch (err) { /* un avis raté ne doit jamais bloquer le chat */ }
}

function ajouterAvis(question, reponse) {
  const zone = document.createElement("div");
  zone.className = "avis";
  zone.innerHTML = `<span>Es-tu satisfait de cette réponse ?</span>
    <button type="button" class="oui">👍 Oui</button>
    <button type="button" class="non">👎 Non</button>`;
  fil.appendChild(zone);
  zone.querySelector(".oui").addEventListener("click", () => {
    zone.textContent = "Merci pour ton retour !";
    envoyerAvis({ question: question, reponse: reponse, satisfait: true });
  });
  zone.querySelector(".non").addEventListener("click", () => ouvrirPlainte(question, reponse, zone));
  defiler();
}

function ouvrirPlainte(question, reponse, zone) {
  const fond = document.createElement("div");
  fond.className = "fond_modale";
  fond.innerHTML = `<div class="modale">
    <h3>Précise la raison de ta plainte</h3>
    <label>Motif</label>
    <select id="motif_plainte">
      <option value="hors_sujet">Réponse hors sujet</option>
      <option value="incomplete">Réponse incomplète</option>
      <option value="incorrecte">Réponse incorrecte</option>
      <option value="autre">Autre</option>
    </select>
    <label>Détails</label>
    <textarea id="commentaire_plainte" rows="4" placeholder="Décris ce qui ne va pas..."></textarea>
    <label>Capture d’écran du bug (facultatif) : fais ta capture, puis joins-la ici</label>
    <input type="file" id="capture_plainte" accept="image/*">
    <div class="modale_actions">
      <button type="button" id="annuler_plainte">Annuler</button>
      <button type="button" id="envoyer_plainte">Envoyer</button>
    </div>
  </div>`;
  document.body.appendChild(fond);
  fond.querySelector("#annuler_plainte").addEventListener("click", () => fond.remove());
  fond.querySelector("#envoyer_plainte").addEventListener("click", async () => {
    const boutonEnvoi = fond.querySelector("#envoyer_plainte");
    boutonEnvoi.disabled = true;
    boutonEnvoi.textContent = "Envoi...";
    const fichier = fond.querySelector("#capture_plainte").files[0];
    let capture_b64 = null, capture_nom = null;
    if (fichier) {
      capture_nom = fichier.name;
      capture_b64 = await new Promise((ok) => {
        const lecteur = new FileReader();
        lecteur.onload = () => ok(lecteur.result);
        lecteur.onerror = () => ok(null);
        lecteur.readAsDataURL(fichier);
      });
    }
    await envoyerAvis({
      question: question, reponse: reponse, satisfait: false,
      motif: fond.querySelector("#motif_plainte").value,
      commentaire: fond.querySelector("#commentaire_plainte").value.trim(),
      capture_nom: capture_nom, capture_b64: capture_b64,
    });
    fond.remove();
    zone.textContent = "Merci, ta plainte a été transmise à l’équipe ADRYNX.";
  });
}

/* ---------- envoi d'une question ---------- */
formulaire.addEventListener("submit", async (e) => {
  e.preventDefault();
  const texte = champ.value.trim();
  if (!texte) return;

  ajouterMessage(texte, "moi");
  champ.value = "";
  champ.disabled = true;
  bouton.disabled = true;

  const attente = ajouterMessage("", "adrynx");
  attente.bulle.innerHTML = '<span class="points"><span></span><span></span><span></span></span>';
  const reveil = setTimeout(() => {
    const note = document.createElement("span");
    note.className = "note_attente";
    note.textContent = "Le serveur se réveille, patiente quelques secondes…";
    attente.bulle.appendChild(note);
    defiler();
  }, 6000);

  try {
    const r = await fetch("/api/question", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texte: texte, telephone: telephoneEnregistre() }),
    });
    if (!r.ok) throw new Error("Erreur serveur");
    const data = await r.json();
    clearTimeout(reveil);
    attente.ligne.remove();
    ajouterMessage(data.texte, "adrynx");
    ajouterAvis(texte, data.texte);
  } catch (err) {
    clearTimeout(reveil);
    attente.ligne.remove();
    ajouterMessage("Erreur : impossible de contacter le serveur. Réessaie dans un instant.", "adrynx");
  } finally {
    champ.disabled = false;
    bouton.disabled = false;
    champ.focus();
  }
});

/* ---------- démarrage ---------- */
const numeroSauve = telephoneEnregistre();
if (numeroSauve) { appliquerTelephone(numeroSauve, false); }
ajouterMessage("Bonjour ! Je suis ADRYNX. Pose-moi une question, un calcul, ou demande-moi un conseil.", "adrynx");
</script>
</body>
</html>
"""
