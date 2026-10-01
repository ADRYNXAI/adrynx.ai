import os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

try:
    import adrynx
    print("ADRYNX OK")
except Exception as e:
    import traceback
    print(f"ADRYNX FAIL: {e}")
    traceback.print_exc()
    adrynx = None

app = FastAPI(title="ADRYNX API", version="7.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://adrynx-ai.onrender.com","https://www.adrynx-ai.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
PHOENIX_VIDEO = "https://files.catbox.moe/y2nvi4.mp4"

class Ask(BaseModel):
    message: Optional[str] = None
    q: Optional[str] = None
    telephone: Optional[str] = "anon"
    anon: Optional[str] = None
    conversation_id: Optional[str] = None

def owner(value):
    value = (value or "anon").strip()
    return value[:120] or "anon"

# FICHIER HTML PRINCIPAL
@app.get("/", response_class=HTMLResponse)
def root():
    f = BASE_DIR / "index.html"
    if f.is_file():
        return FileResponse(str(f), media_type="text/html")
    return HTMLResponse('<h1>ADRYNX</h1><p>API active.</p><a href="/api/health">health</a>')

# FICHIERS STATIQUES
@app.get("/app.js")
def serve_app_js():
    f = BASE_DIR / "app.js"
    if not f.is_file(): raise HTTPException(status_code=404, detail="app.js introuvable.")
    return FileResponse(str(f), media_type="application/javascript")

@app.get("/style.css")
def serve_style_css():
    f = BASE_DIR / "style.css"
    if not f.is_file(): raise HTTPException(status_code=404, detail="style.css introuvable.")
    return FileResponse(str(f), media_type="text/css")

# --- ETAPE 2 : APP MOBILE - AJOUT SANS CASSER ---
@app.get("/manifest.json")
def serve_manifest():
    f = BASE_DIR / "manifest.json"
    if not f.is_file():
        # Ne bloque pas Render si le fichier n'existe pas encore
        raise HTTPException(status_code=404, detail="manifest.json pas encore créé - fais étape 3")
    return FileResponse(str(f), media_type="application/manifest+json")

@app.get("/sw.js")
def serve_sw():
    f = BASE_DIR / "sw.js"
    if not f.is_file():
        raise HTTPException(status_code=404, detail="sw.js pas encore créé - fais étape 3")
    return FileResponse(str(f), media_type="application/javascript", headers={"Cache-Control": "no-cache"})

@app.get("/robots.txt")
def serve_robots():
    f = BASE_DIR / "robots.txt"
    if not f.is_file(): raise HTTPException(status_code=404, detail="robots.txt introuvable.")
    return FileResponse(str(f), media_type="text/plain")

@app.get("/sitemap.xml")
def serve_sitemap():
    f = BASE_DIR / "sitemap.xml"
    if not f.is_file(): raise HTTPException(status_code=404, detail="sitemap.xml introuvable.")
    return FileResponse(str(f), media_type="application/xml")

@app.get("/favicon.ico")
def serve_favicon():
    f = BASE_DIR / "favicon.ico"
    if not f.is_file(): raise HTTPException(status_code=404, detail="favicon.ico introuvable.")
    return FileResponse(str(f), media_type="image/x-icon")

@app.get("/health")
@app.get("/api/health")
def health():
    return {"ok": True, "service": "ADRYNX", "version": "7.0", "video_core": PHOENIX_VIDEO, "groq_configured": bool(os.getenv("GROQ_API_KEY")), "adrynx_loaded": adrynx is not None}

@app.post("/ask")
@app.post("/api/ask")
def ask(req: Ask):
    if adrynx is None: raise HTTPException(status_code=500, detail="adrynx.py non charge")
    message = (req.message or req.q or "").strip()
    if not message: raise HTTPException(status_code=400, detail="message requis")
    current_owner = owner(req.telephone or req.anon)
    try:
        result = adrynx.traiter_question(message, current_owner, req.conversation_id)
        if not isinstance(result, dict): raise RuntimeError("resultat invalide")
        if result.get("ok") is False: raise HTTPException(status_code=500, detail=result.get("error","erreur"))
        return result
    except HTTPException: raise
    except Exception as e:
        print(f"API ERROR {e}")
        raise HTTPException(status_code=500, detail=f"Erreur ADRYNX : {e}")

@app.get("/api/dashboard")
def dashboard(telephone: str = "anon"):
    if adrynx is None: raise HTTPException(status_code=500, detail="adrynx non charge")
    try:
        result = adrynx.dashboard(owner(telephone))
        return {"ok": True, "dashboard": result}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/clean")
def emergency_clean(x_admin_token: Optional[str] = Header(default=None)):
    expected = os.getenv("ADMIN_SECRET")
    if not expected: raise HTTPException(status_code=503, detail="ADMIN_SECRET non configure")
    if x_admin_token!= expected: raise HTTPException(status_code=403, detail="acces refuse")
    import sqlite3
    conn = None
    try:
        db = BASE_DIR / "adrynx.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE IF NOT EXISTS intent_examples (id INTEGER PRIMARY KEY, phrase TEXT, intent TEXT)")
        conn.execute("DELETE FROM intent_examples WHERE length(phrase) < 4")
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM intent_examples").fetchone()[0]
        return {"ok": True, "message": f"{count} conserves"}
    finally:
        if conn: conn.close()
