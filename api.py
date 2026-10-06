from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3, time

app = FastAPI(title="ADRYNX PHOENIX PRIME COMMUNITY")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- Limite 25/j intacte ---
def check_limit(uid):
    con=sqlite3.connect("memoire.db")
    con.execute("CREATE TABLE IF NOT EXISTS limits (user_id TEXT, date TEXT, count INT, PRIMARY KEY(user_id,date))")
    today=time.strftime("%Y-%m-%d")
    r=con.execute("SELECT count FROM limits WHERE user_id=? AND date=?",(uid,today)).fetchone()
    con.close()
    return r[0] if r else 0

# --- Routes Statiques Locales (Logs verts) ---
@app.get("/robots.txt")
def robots(): return FileResponse("robots.txt")
@app.get("/sitemap.xml")
def sitemap(): return FileResponse("sitemap.xml")
@app.get("/orb.mp4")
def orb(): return FileResponse("orb.mp4", media_type="video/mp4")
@app.get("/icon-192.png")
def i192(): return FileResponse("icon-192.png")
@app.get("/icon-512.png")
def i512(): return FileResponse("icon-512.png")
@app.get("/style.css")
def css(): return FileResponse("style.css")
@app.get("/sw.js")
def sw(): return FileResponse("sw.js")
@app.get("/manifest.json")
def mani(): return FileResponse("manifest.json")

# --- Pages ---
@app.get("/")
def root(): return FileResponse("landing.html")
@app.get("/app")
def app_page(): return FileResponse("index.html")
@app.get("/pay")
def pay(): return FileResponse("pay.html")
@app.get("/admin")
def admin(): return FileResponse("admin.html")

# --- Chat + Image (ton adrynx.py intact) ---
@app.post("/api/chat")
async def chat(req: Request):
    from adrynx import repondre
    d=await req.json()
    uid=d.get("user_id","anon")[:50]
    q=d.get("message","")[:2000]
    mode=d.get("mode","general")
    is_vip=d.get("is_vip",False)
    if check_limit(uid)>=25 and not is_vip:
        return {"reponse":"🔥 Limite 25/25 atteinte aujourd'hui. Passe Premium 1000F/semaine sur /pay pour illimité - MTN 061174945 OBENDA JONATHAN"}
    rep=repondre(q, mode=mode, user_id=uid)
    return {"reponse": rep}

@app.post("/api/pay/request")
async def pay_req(req: Request):
    return {"ok":True, "mtn":"061174945", "nom":"OBENDA JONATHAN", "montant":"1000F", "whatsapp":"https://wa.me/242061174945"}

# --- COMMUNITY V13 - Dans le thème Systalink ---
from community import router as community_router
app.include_router(community_router)
