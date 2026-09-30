import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

import adrynx

app = FastAPI(
title="ADRYNX API",
version="7.0"
)

app.add_middleware(
CORSMiddleware,
allow_origins=[
"https://adrynx-ai.onrender.com",
"https://www.adrynx-ai.onrender.com",
"https://adrynx.ai",
"https://www.adrynx.ai",
],
allow_credentials=True,
allow_methods=["GET", "POST"],
allow_headers=["*"],
)

BASE_DIR = Path(file).resolve().parent
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

@app.get("/", response_class=HTMLResponse)
def root():
index_file = BASE_DIR / "index.html"

if index_file.is_file():
    return FileResponse(
        str(index_file),
        media_type="text/html"
    )

return HTMLResponse(
    "<h1>ADRYNX</h1>"
    "<p>API active.</p>"
    "<p><a href='/api/health'>Health</a></p>"
)

@app.get("/health")
@app.get("/api/health")
def health():
return {
"ok": True,
"service": "ADRYNX",
"version": "7.0",
"video_core": PHOENIX_VIDEO,
"groq_configured": bool(os.getenv("GROQ_API_KEY"))
}

@app.get("/app.js")
def serve_app_js():
app_file = BASE_DIR / "app.js"

if not app_file.is_file():
    raise HTTPException(
        status_code=404,
        detail="app.js introuvable."
    )

return FileResponse(
    str(app_file),
    media_type="application/javascript"
)

@app.get("/style.css")
def serve_style_css():
style_file = BASE_DIR / "style.css"

if not style_file.is_file():
    raise HTTPException(
        status_code=404,
        detail="style.css introuvable."
    )

return FileResponse(
    str(style_file),
    media_type="text/css"
)

@app.get("/robots.txt")
def serve_robots():
f = BASE_DIR / "robots.txt"

if not f.is_file():
    raise HTTPException(
        status_code=404,
        detail="robots.txt introuvable."
    )

return FileResponse(
    str(f),
    media_type="text/plain"
)

@app.get("/sitemap.xml")
def serve_sitemap():
f = BASE_DIR / "sitemap.xml"

if not f.is_file():
    raise HTTPException(
        status_code=404,
        detail="sitemap.xml introuvable."
    )

return FileResponse(
    str(f),
    media_type="application/xml"
)

@app.get("/favicon.ico")
def serve_favicon():
f = BASE_DIR / "favicon.ico"

if not f.is_file():
    raise HTTPException(
        status_code=404,
        detail="favicon.ico introuvable."
    )

return FileResponse(
    str(f),
    media_type="image/x-icon"
)

@app.post("/ask")
@app.post("/api/ask")
def ask(req: Ask):
message = (req.message or req.q or "").strip()

if not message:
    raise HTTPException(
        status_code=400,
        detail="Le champ message ou q est requis."
    )

current_owner = owner(
    req.telephone or req.anon
)

try:
    result = adrynx.traiter_question(
        message,
        current_owner,
        req.conversation_id
    )

    if not isinstance(result, dict):
        raise RuntimeError(
            "ADRYNX a retourné un résultat invalide."
        )

    if result.get("ok") is False:
        raise HTTPException(
            status_code=500,
            detail=result.get(
                "error",
                "ADRYNX a rencontré une erreur."
            )
        )

    return result

except HTTPException:
    raise

except Exception as e:
    print(
        f"ADRYNX API ERROR: "
        f"{type(e).__name__}: {e}"
    )

    raise HTTPException(
        status_code=500,
        detail=f"Erreur ADRYNX : {type(e).__name__}: {e}"
    )

@app.get("/api/dashboard")
def dashboard(telephone: str = "anon"):
try:
result = adrynx.dashboard(
owner(telephone)
)

    return {
        "ok": True,
        "dashboard": result
    }

except Exception as e:
    print(
        f"DASHBOARD ERROR: {e}"
    )

    raise HTTPException(
        status_code=500,
        detail=f"Erreur dashboard : {e}"
    )

@app.get("/api/admin/clean")
def emergency_clean(
x_admin_token: Optional[str] = Header(default=None)
):
expected = os.getenv("ADMIN_SECRET")

if not expected:
    raise HTTPException(
        status_code=503,
        detail="ADMIN_SECRET non configure."
    )

if x_admin_token != expected:
    raise HTTPException(
        status_code=403,
        detail="Acces admin refuse."
    )

import sqlite3

database = BASE_DIR / "adrynx.db"
conn = None

try:
    conn = sqlite3.connect(database)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS intent_examples (
            id INTEGER PRIMARY KEY,
            phrase TEXT,
            intent TEXT
        )
        """
    )

    conn.execute(
        """
        DELETE FROM intent_examples
        WHERE length(phrase) < 4
        """
    )

    conn.commit()

    count = conn.execute(
        "SELECT COUNT(*) FROM intent_examples"
    ).fetchone()[0]

    return {
        "ok": True,
        "message": (
            f"Nettoyage termine. "
            f"{count} exemples conserves."
        )
    }

except Exception as e:
    print(
        f"CLEAN ERROR: {e}"
    )

    raise HTTPException(
        status_code=500,
        detail=f"Erreur nettoyage : {e}"
    )

finally:
    if conn:
        conn.close()
