import os, urllib.parse, json, time
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from adrynx import PhoenixPrime

app = FastAPI()
ai = PhoenixPrime()

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ADRYNX2026")
ADMIN_TOKEN = "adrynx_admin_token_jonathan_secret_2026"
DB_FILE = "adrynx_db.json"

MODES = {
    "general": "Tu es ADRYNX Phoenix Prime, creee par Jonathan Dejah OBENDA.",
    "etudiant": "Mode Etudiant: meilleur prof Marien Ngouabi.",
    "vendeur": "Mode Vendeur: expert business Brazzaville.",
    "codeur": "Mode Codeur: expert code.",
    "image": "Mode Image: expert prompt Flux."
}

def load_db():
    if not os.path.exists(DB_FILE):
        return {"users": [], "transactions": []}
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except:
        return {"users": [], "transactions": []}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def landing():
    if os.path.exists("landing.html"):
        return FileResponse("landing.html")
    return FileResponse("index.html")

@app.get("/app")
async def app_page():
    return FileResponse("index.html")

@app.get("/chat")
async def chat_redirect():
    return FileResponse("index.html")

@app.get("/admin")
async def admin_page():
    if os.path.exists("admin.html"):
        return FileResponse("admin.html")
    return JSONResponse({"error": "admin.html manquant"}, status_code=404)

@app.get("/pay")
async def pay_page():
    if os.path.exists("pay.html"):
        return FileResponse("pay.html")
    return JSONResponse({"error": "pay.html manquant"}, status_code=404)

@app.get("/app.js")
async def serve_appjs():
    if os.path.exists("app.js"):
        return FileResponse("app.js", media_type="application/javascript")
    return JSONResponse({}, status_code=404)

@app.get("/style.css")
async def serve_css():
    if os.path.exists("style.css"):
        return FileResponse("style.css")
    return JSONResponse({}, status_code=404)

@app.get("/manifest.json")
async def manifest():
    if os.path.exists("manifest.json"):
        return FileResponse("manifest.json")
    return JSONResponse({})

@app.get("/sw.js")
async def sw():
    if os.path.exists("sw.js"):
        return FileResponse("sw.js", media_type="application/javascript")
    return JSONResponse({}, status_code=404)

@app.get("/health")
async def health():
    db = load_db()
    return {"status": "online", "users": len(db["users"])}

@app.post("/api/admin/login")
async def admin_login(req: Request):
    try:
        data = await req.json()
        pwd = (data.get("password") or "").strip()
        if pwd == ADMIN_PASSWORD or pwd == "ADRYNX2026":
            return {"token": ADMIN_TOKEN}
        return JSONResponse({"error": "wrong password"}, status_code=401)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/admin/data")
async def admin
