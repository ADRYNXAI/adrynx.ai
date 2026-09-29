import os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field
import adrynx
import verification

app = FastAPI(title="ADRYNX API", version="5.2", description="API cognitive PHOENIX FIX")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_PATHS = [BASE_DIR / "index.html", BASE_DIR / "frontend" / "index.html", BASE_DIR / "static" / "index.html"]

PHOENIX_VIDEO = "https://files.catbox.moe/y2nvi4.mp4"

class Ask(BaseModel):
    message: Optional[str] = None
    q: Optional[str] = None
    telephone: Optional[str] = "anon"
    anon: Optional[str] = None
    conversation_id: Optional[str] = None
class Feedback(BaseModel):
    telephone: Optional[str] = "anon"; question: str; reponse: str; satisfait: bool = False; motif: Optional[str] = ""; commentaire: Optional[str] = ""; correction: Optional[str] = ""
class Project(BaseModel):
    telephone: Optional[str] = "anon"; nom: str = Field(min_length=1, max_length=200); objectif: Optional[str] = ""
class Task(BaseModel):
    telephone: Optional[str] = "anon"; titre: str = Field(min_length=1, max_length=300); project_id: Optional[str] = None
class Conversation(BaseModel):
    telephone: Optional[str] = "anon"; titre: Optional[str] = "Nouvelle conversation"
class VerificationRequest(BaseModel):
    telephone: str
class VerificationCode(BaseModel):
    telephone: str; code: str

def owner(value): return ((value or "anon").strip()[:120] or "anon")
def trouver_frontend():
    for chemin in FRONTEND_PATHS:
        if chemin.is_file(): return chemin
    return None

@app.get("/", response_class=HTMLResponse)
def root():
    frontend = trouver_frontend()
    if frontend: return FileResponse(path=str(frontend), media_type="text/html")
    chemins_recherches = [str(chemin) for chemin in FRONTEND_PATHS]
    return HTMLResponse(f"<h1>ADRYNX</h1><p>Frontend introuvable. Cherché: {chemins_recherches}</p><a href='/api/health'>/api/health</a>", status_code=500)

@app.get("/health")
@app.get("/api/health")
def health():
    return {"ok": True, "service": "ADRYNX", "version": "5.2-phoenix-fix", "video_core": PHOENIX_VIDEO, "groq_configured": bool(getattr(adrynx, "GROQ_API_KEY", None)), "model": getattr(adrynx, "GROQ_MODEL", None), "learning": "memory_examples_not_local_fine_tuning", "verification": verification.verification_active()}

# ============================================================
# IA - AVEC BLOQUEUR ANTI-WIKIPEDIA
# ============================================================
@app.post("/ask")
@app.post("/api/ask")
def ask(req: Ask):
    msg = (req.message or req.q or "").strip()
    if not msg: raise HTTPException(status_code=400, detail="message/q requis")

    # --- FIX NUCLEAIRE : bloque Cc, Slt, Quoi, etc. avant d'appeler les parents ---
    low = msg.lower().strip()
    bloqueurs = {"cc","c c","cc?","slt","salut","yo","hey","wesh","bjr","bonjour","quoi","quoi?","comment","comment?","cc mon ami"}
    if low in bloqueurs or len(low) <= 2:
        return {
            "ok": True,
            "reponse": "Cc! C'est ADRYNX 🔥 Je suis en ligne. On lance quoi?",
            "intent": "salutation",
            "source": "noyau-direct-fix",
            "video": PHOENIX_VIDEO
        }

    return adrynx.traiter_question(msg, owner(req.telephone or req.anon), req.conversation_id)

# Le reste de ton code reste identique
@app.get("/api/verification/status")
def verification_status(): return {"ok": True, "verification": verification.informations_verification()}
@app.post("/api/verification/sms/request")
def verification_sms_request(req: VerificationRequest):
    ok, message = verification.demander_code_sms(req.telephone)
    if not ok: raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message}
@app.post("/api/verification/sms/verify")
def verification_sms_verify(req: VerificationCode):
    token, message = verification.verifier_code_sms(req.telephone, req.code)
    if not token: raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message, "token": token}
@app.post("/api/conversations")
def create_conv(req: Conversation):
    conversation_id = adrynx.new_conversation(owner(req.telephone), req.titre or "Nouvelle conversation")
    return {"ok": True, "conversation_id": conversation_id}
@app.get("/api/conversations")
def list_conv(telephone="anon"):
    c = adrynx.db()
    rows = c.execute("SELECT id, owner, titre, created_at, updated_at FROM conversations WHERE owner=? ORDER BY updated_at DESC LIMIT 50", (owner(telephone),)).fetchall()
    c.close()
    return {"ok": True, "conversations": [dict(row) for row in rows]}
@app.get("/api/conversations/{cid}")
def get_conv(cid, telephone="anon"):
    c = adrynx.db()
    row = c.execute("SELECT id, owner, titre, created_at, updated_at FROM conversations WHERE id=? AND owner=?", (cid, owner(telephone))).fetchone()
    c.close()
    if not row: raise HTTPException(status_code=404, detail="Conversation introuvable")
    return {"ok": True, "conversation": dict(row), "state": adrynx.state(cid), "messages": adrynx.messages(cid, 100)}
@app.get("/api/dashboard")
def dash(telephone="anon"): return {"ok": True, "dashboard": adrynx.dashboard(owner(telephone))}
@app.get("/api/projects")
def get_projects(telephone="anon"): return {"ok": True, "projects": adrynx.projects(owner(telephone))}
@app.post("/api/projects")
def post_project(req: Project): return {"ok": True, "project": adrynx.project(owner(req.telephone), req.nom, req.objectif or "")}
@app.post("/api/tasks")
def post_task(req: Task): return {"ok": True, "task": adrynx.task(owner(req.telephone), req.titre, req.project_id)}
@app.post("/api/feedback")
def feedback(req: Feedback): return adrynx.enregistrer_feedback(owner(req.telephone), req.question, req.reponse, req.satisfait, req.motif or "", req.commentaire or "", req.correction or "")
@app.get("/api/learning/stats")
def learning_stats(): return {"ok": True, "stats": adrynx.stats_apprentissage()}
@app.get("/api/admin/learning/export")
def export_learning(x_adrynx_admin_secret: Optional[str] = Header(None)):
    if not adrynx.verifier_admin(x_adrynx_admin_secret): raise HTTPException(status_code=403, detail="Accès administrateur refusé")
    return {"ok": True, "format": "jsonl", "data": adrynx.exporter_apprentissage()}
@app.websocket("/ws/{owner_id}")
async def ws(websocket: WebSocket, owner_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            question = str(data.get("message") or data.get("q") or "").strip()
            if not question: continue
            # même bloqueur en WS
            if question.lower().strip() in {"cc","slt","salut","yo"}:
                await websocket.send_json({"type": "answer", "data": {"ok": True, "reponse": "Cc! C'est ADRYNX 🔥", "intent": "salutation"}})
                continue
            resultat = adrynx.traiter_question(question, owner_id, data.get("conversation_id"))
            await websocket.send_json({"type": "answer", "data": resultat})
    except WebSocketDisconnect: pass
    except Exception as exc:
        try: await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception: pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), reload=False)
