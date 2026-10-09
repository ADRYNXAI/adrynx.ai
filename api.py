from fastapi import FastAPI, Request, Header
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3, time, os, json

app = FastAPI(title="ADRYNX PHOENIX PRIME V15")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# TON MOT DE PASSE ADMIN ICI
ADMIN_PASSWORD = "ADRYNX2026"
ADMIN_TOKEN = "adrynx_boss_2026"

def get_con(db):
    con=sqlite3.connect(db, check_same_thread=False, timeout=10)
    return con

def check_limit(uid):
    try:
        con=get_con("memoire.db")
        con.execute("CREATE TABLE IF NOT EXISTS limits (user_id TEXT, date TEXT, count INT, PRIMARY KEY(user_id,date))")
        today=time.strftime("%Y-%m-%d")
        r=con.execute("SELECT count FROM limits WHERE user_id=? AND date=?",(uid,today)).fetchone()
        con.close(); return r[0] if r else 0
    except: return 0

def init_settings():
    con=get_con("settings.db")
    con.execute("CREATE TABLE IF NOT EXISTS settings (user_id TEXT PRIMARY KEY, style TEXT, chaleur TEXT, enthousiasme TEXT, emojis TEXT, couleur TEXT, memoire TEXT)")
    con.commit(); con.close()
    con=get_con("memoire.db")
    con.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, tel TEXT, date TEXT, premium INTEGER, unlimited INTEGER, messages INTEGER, images INTEGER)")
    con.execute("CREATE TABLE IF NOT EXISTS transactions (id TEXT PRIMARY KEY, user_id TEXT, tel TEXT, ref TEXT, amount TEXT, date TEXT)")
    con.commit(); con.close()
init_settings()

@app.get("/robots.txt")
def robots(): return FileResponse("robots.txt") if os.path.exists("robots.txt") else JSONResponse({})
@app.get("/sitemap.xml")
def sitemap(): return FileResponse("sitemap.xml") if os.path.exists("sitemap.xml") else JSONResponse({})
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

# --- ADMIN ---
@app.post("/api/admin/login")
async def admin_login(req: Request):
    d=await req.json()
    if d.get("password") == ADMIN_PASSWORD:
        return {"token": ADMIN_TOKEN}
    return JSONResponse({"error":"Mauvais"}, status_code=401)

@app.get("/api/admin/data")
def admin_data(x_admin_token: str = Header(None)):
    if x_admin_token!= ADMIN_TOKEN:
        return JSONResponse(status_code=401, content={"error":"Non autorisé"})
    con=get_con("memoire.db")
    try:
        users = con.execute("SELECT * FROM users").fetchall()
        txs = con.execute("SELECT * FROM transactions").fetchall()
        con.close()
        return {
            "users": [{"id":r[0],"tel":r[1],"date":r[2],"premium":bool(r[3]),"unlimited":bool(r[4]),"messages":r[5],"images":r[6]} for r in users],
            "transactions": [{"id":r[0],"user_id":r[1],"tel":r[2],"ref":r[3],"amount":r[4],"date":r[5]} for r in txs]
        }
    except:
        con.close()
        return {"users":[],"transactions":[]}

@app.post("/api/admin/user")
async def admin_user(req: Request, x_admin_token: str = Header(None)):
    if x_admin_token!= ADMIN_TOKEN: return JSONResponse(status_code=401, content={})
    d=await req.json()
    con=get_con("memoire.db")
    uid, act = d.get("id"), d.get("action")
    if act=="premium": con.execute("UPDATE users SET premium=1 WHERE id=?",(uid,))
    if act=="unlimited": con.execute("UPDATE users SET unlimited=1 WHERE id=?",(uid,))
    if act=="ban": con.execute("UPDATE users SET premium=0, unlimited=0 WHERE id=?",(uid,))
    if act=="delete": con.execute("DELETE FROM users WHERE id=?",(uid,))
    con.commit(); con.close()
    return {"ok":True}

@app.post("/api/admin/validate")
async def admin_val(req: Request, x_admin_token: str = Header(None)):
    if x_admin_token!= ADMIN_TOKEN: return JSONResponse(status_code=401, content={})
    d=await req.json()
    con=get_con("memoire.db")
    con.execute("DELETE FROM transactions WHERE id=?",(d.get("id"),))
    con.commit(); con.close()
    return {"ok":True}

@app.post("/api/chat")
async def chat(req: Request):
    try:
        from adrynx import repondre
        d=await req.json()
        uid=d.get("user_id","anon")[:50]
        if check_limit(uid)>=25 and not d.get("is_vip",False):
            return {"reponse":"🔥 Limite 25/25. Premium 1000F/semaine /pay - MTN 061174945"}
        rep=repondre(d.get("message","")[:2000], mode=d.get("mode","general"), user_id=uid)
        return {"reponse": rep}
    except Exception as e:
        return {"reponse": f"ADRYNX respire... réessaie: {str(e)[:80]}"}

@app.post("/api/pay/request")
async def pay_req(req: Request):
    return {"ok":True,"mtn":"061174945","nom":"OBENDA JONATHAN"}

@app.get("/api/settings/{user_id}")
def get_settings(user_id: str):
    con=get_con("settings.db")
    r=con.execute("SELECT style,chaleur,enthousiasme,emojis,couleur,memoire FROM settings WHERE user_id=?",(user_id,)).fetchone()
    con.close()
    if not r: return {"style":"Par défaut","chaleur":"Par défaut","enthousiasme":"Par défaut","emojis":"Par défaut","couleur":"Orange","memoire":"Activé"}
    return {"style":r[0],"chaleur":r[1],"enthousiasme":r[2],"emojis":r[3],"couleur":r[4],"memoire":r[5]}

@app.post("/api/settings/save")
async def save_settings(req: Request):
    d=await req.json(); uid=d.get("user_id","anon")
    con=get_con("settings.db")
    con.execute("INSERT OR REPLACE INTO settings VALUES (?,?,?,?,?,?,?)",(uid,d.get("style","Par défaut"),d.get("chaleur","Par défaut"),d.get("enthousiasme","Par défaut"),d.get("emojis","Par défaut"),d.get("couleur","Orange"),d.get("memoire","Activé")))
    con.commit(); con.close()
    return {"ok":True}

@app.get("/api/utilisation/{user_id}")
def utilisation(user_id: str):
    return {"limite":f"{check_limit(user_id)}/25 aujourd'hui","reset":"Demain 00:00 Brazzaville","credits":"Gratuit"}

try:
    from community import router as community_router
    app.include_router(community_router)
except Exception as e:
    print(f"Community off: {e}")
