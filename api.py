import os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import adrynx
import verification

app = FastAPI(title="ADRYNX API", version="6.2-secours")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR = Path(__file__).resolve().parent
PHOENIX_VIDEO = "https://files.catbox.moe/y2nvi4.mp4"

class Ask(BaseModel):
    message: Optional[str] = None
    q: Optional[str] = None
    telephone: Optional[str] = "anon"
    anon: Optional[str] = None
    conversation_id: Optional[str] = None

def owner(v): return (v or "anon").strip()[:120] or "anon"

@app.get("/", response_class=HTMLResponse)
def root():
    p = BASE_DIR / "index.html"
    if p.is_file(): return FileResponse(str(p), media_type="text/html")
    return HTMLResponse(f"<h1>ADRYNX</h1><p>Video: {PHOENIX_VIDEO}</p><a href='/api/health'>/api/health</a>")

@app.get("/health")
@app.get("/api/health")
def health():
    return {"ok": True, "service": "ADRYNX", "version": "6.2-secours-anti500", "video_core": PHOENIX_VIDEO, "groq_configured": bool(os.getenv("GROQ_API_KEY"))}

@app.post("/ask")
@app.post("/api/ask")
def ask(req: Ask):
    try:
        msg = (req.message or req.q or "").strip()
        if not msg: raise HTTPException(400, "message/q requis")
        low = msg.lower().strip()
        if low in {"cc","c c","cc?","slt","salut","yo","hey","wesh","bjr","bonjour","quoi","admin ad23ultronix3d vider cash"} or len(low) <= 4:
            return {"ok": True, "reponse": "Cc! C'est ADRYNX 🔥 Je suis en ligne. On lance quoi?", "intent": "salutation", "source": "secours-direct", "video": PHOENIX_VIDEO}
        return adrynx.traiter_question(msg, owner(req.telephone or req.anon), req.conversation_id)
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"ok": True, "reponse": "Cc! C'est ADRYNX 🔥 Système en redémarrage. Réessaie.", "intent": "salutation", "error": str(e)}

@app.get("/api/admin/clean")
def emergency_clean():
    try:
        import sqlite3
        c = sqlite3.connect(BASE_DIR / "adrynx.db")
        c.execute("CREATE TABLE IF NOT EXISTS intent_examples (id INTEGER PRIMARY KEY, phrase TEXT, intent TEXT)")
        c.execute("DELETE FROM intent_examples WHERE length(phrase) < 4")
        c.execute("DELETE FROM intent_examples WHERE lower(phrase) IN ('cc','slt','salut','yo','quoi')")
        cnt = c.execute("SELECT COUNT(*) FROM intent_examples").fetchone()[0]
        c.commit(); c.close()
        return {"ok": True, "message": f"Nettoyé. Reste {cnt} exemples"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/api/dashboard")
def dash(telephone="anon"):
    try: return {"ok": True, "dashboard": adrynx.dashboard(owner(telephone))}
    except: return {"ok": True, "dashboard": {"video": PHOENIX_VIDEO}}
