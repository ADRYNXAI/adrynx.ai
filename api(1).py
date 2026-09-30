import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ADRYNX MINIMAL")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(".").resolve()

@app.get("/", response_class=HTMLResponse)
def root():
    f = BASE_DIR / "index.html"
    if f.is_file():
        return FileResponse(str(f), media_type="text/html")
    return HTMLResponse("<h1>ADRYNX MINIMAL OK</h1>")

@app.get("/app.js")
def js():
    f = BASE_DIR / "app.js"
    return FileResponse(str(f), media_type="application/javascript") if f.is_file() else HTMLResponse("not found", status_code=404)

@app.get("/style.css")
def css():
    f = BASE_DIR / "style.css"
    return FileResponse(str(f), media_type="text/css") if f.is_file() else HTMLResponse("not found", status_code=404)

@app.get("/api/health")
def health():
    return {"ok": True, "minimal": True, "groq": bool(os.getenv("GROQ_API_KEY"))}

@app.post("/api/ask")
def ask():
    return {"ok": True, "message": "minimal mode - adrynx.py desactive pour test"}
