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

@app.get("/")
async def root():
    return FileResponse("landing.html") if os.path.exists("landing.html") else FileResponse("index.html")

@app.get("/admin")
async def admin_page():
    return FileResponse("admin.html")

@app.get("/pay")
async def pay_page():
    return FileResponse("pay.html") if os.path.exists("pay.html") else JSONResponse({"error":"no pay"}, status_code=404)

@app.get("/health")
async def health():
    db=load_db()
    return {"status":"online","users":len(db["users"])}

@app.post("/api/admin/login")
async def admin_login(req: Request):
    data = await req.json()
    pwd = (data.get("password") or "").strip()
    if pwd == ADMIN_PASSWORD or pwd == "ADRYNX2026":
        return {"token": ADMIN_TOKEN}
    return JSONResponse({"error":"wrong"}, status_code=401)

@app.get("/api/admin/data")
async def admin_data(req: Request):
    if req.headers.get("X-Admin-Token") != ADMIN_TOKEN:
       
