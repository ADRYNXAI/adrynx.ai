from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3, time, os

app = FastAPI(title="ADRYNX PHOENIX PRIME COMMUNITY")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def check_limit(uid):
    try:
        con=sqlite3.connect("memoire.db", check_same_thread=False)
        con.execute("CREATE TABLE IF NOT EXISTS limits (user_id TEXT, date TEXT, count INT, PRIMARY KEY(user_id,date))")
        today=time.strftime("%Y-%m-%d")
        r=con.execute("SELECT count FROM limits WHERE user_id=? AND date=?",(uid,today)).fetchone()
        con.close()
        return r[0] if r else 0
    except: return 0

# --- Fichiers statiques SANS crash ---
@app.get("/robots.txt")
def robots():
    return FileResponse("robots.txt") if os.path.exists("robots.txt") else JSONResponse({"ok":True})
@app.get("/sitemap.xml")
def sitemap():
    return FileResponse("sitemap.xml") if os.path.exists("sitemap.xml") else JSONResponse({"ok":True})
@app.get("/orb.mp4")
def orb(): return FileResponse("orb.mp4")
@app.get("/icon-192.png")
def i192(): return FileResponse("icon-192.png")
@app.get("/icon-512.png")
def i512(): return FileResponse("icon-512.png")
@app.get("/style.css")
def css(): return FileResponse("style.css") if os.path.exists("style.css") else JSONResponse({})
@app.get("/sw.js")
def sw(): return FileResponse("sw.js")
@app.get("/manifest.json")
def mani(): return FileResponse("manifest.json")

@app.get("/")
def root(): return FileResponse("landing.html")
@app.get("/app")
def app_page(): return FileResponse("index.html")
@app.get("/pay")
def pay(): return FileResponse("pay.html")
@app.get("/admin")
def admin(): return FileResponse("admin.html")

@app.post("/api/chat")
async def chat(req: Request):
    try:
        from adrynx import repondre
        d=await req.json()
        uid=d.get("user_id","anon")[:50]
        q=d.get("message","")[:2000]
        mode=d.get("mode","general")
        is_vip=d.get("is_vip",False)
        if check_limit(uid)>=25 and not is_vip:
            return {"reponse":"🔥 Limite 25/25 atteinte. Passe Premium 1000F sur /pay - MTN 061174945"}
        rep=repondre(q, mode=mode, user_id=uid)
        return {"reponse": rep}
    except Exception as e:
        return {"reponse": f"ADRYNX en pause 2s: {str(e)[:100]}"}

@app.post("/api/pay/request")
async def pay_req(req: Request):
    return {"ok":True, "mtn":"061174945", "nom":"OBENDA JONATHAN"}

# --- COMMUNITY FIX - ne fait plus crasher le serveur ---
try:
    from community import router as community_router
    app.include_router(community_router)
except Exception as e:
    print(f"Community non chargé: {e}")

# PAS de app.mount("/", StaticFiles) - c'était ça qui tuait /app
