from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import os
from adrynx import traiter_question, verifier_secret_admin, lister_comptes, compter_comptes, lister_plaintes

app = FastAPI(title="ADRYNX AI v2.4 PANTIN")

@app.get("/")
def root():
    return {"status":"ok","version":"2.4 PANTIN","message":"ADRYNX enfant sous contrôle parental - 3 gardiens actifs"}

@app.get("/health")
def health():
    return {
        "status":"ok",
        "version":"2.4 PANTIN",
        "mode":"enfant + parents validateurs",
        "brains":{
            "groq": bool(os.environ.get("GROQ_API_KEY")),
            "huggingface": bool(os.environ.get("HF_TOKEN")),
            "openrouter": bool(os.environ.get("OPENROUTER_API_KEY"))
        },
        "email_resend": bool(os.environ.get("RESEND_API_KEY")),
        "db": os.environ.get("ADRYNX_DB","memoire.db")
    }

@app.post("/ask")
async def ask(request: Request):
    data = await request.json()
    q = data.get("question","")
    tel = data.get("telephone")
    rep = traiter_question(q, tel)
    return {"reponse": rep}

@app.get("/admin")
def admin_page(secret: str = ""):
    if not verifier_secret_admin(secret):
        return HTMLResponse("<h1>Code admin incorrect</h1>", status_code=401)
    comptes = lister_comptes()
    stats = compter_comptes()
    plaintes = lister_plaintes(30)
    # Affiche aussi les leçons apprises par les parents
    import sqlite3
    conn = sqlite3.connect(os.environ.get("ADRYNX_DB","memoire.db"))
    try:
        lecons = conn.execute("SELECT question, reponse_enfant, reponse_parent, parent, cree_le FROM lecons_parents ORDER BY id DESC LIMIT 20").fetchall()
    except:
        lecons = []
    html = f"""
    <h1>ADRYNX v2.4 PANTIN - Admin</h1>
    <p><b>{stats['total']} users</b> - {stats['premium']} premium - {stats['bloques']} bloqués</p>
    <h2>Leçons des parents (cerveau qui évolue)</h2>
    <pre>{lecons}</pre>
    <h2>Comptes</h2>
    <pre>{comptes}</pre>
    <h2>Plaintes</h2>
    <pre>{plaintes}</pre>
    """
    return HTMLResponse(html)
