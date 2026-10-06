import sqlite3, time
from fastapi import APIRouter, Request
from datetime import datetime
router=APIRouter()
DB="community.db"

def get_con():
    con=sqlite3.connect(DB, check_same_thread=False, timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS questions (id INTEGER PRIMARY KEY, user_id TEXT, q TEXT, r TEXT, ts REAL, likes INT DEFAULT 0)")
    con.execute("CREATE TABLE IF NOT EXISTS astuces (id INTEGER PRIMARY KEY, titre TEXT, contenu TEXT, ts REAL)")
    return con

@router.get("/api/community/feed")
def feed():
    try:
        con=get_con()
        if con.execute("SELECT COUNT(*) FROM astuces").fetchone()[0]==0:
            for t,c in [("Deploy Render","uvicorn api:app --host 0.0.0.0 --port $PORT"),("Orbe offline","sw.js cache-first orb.mp4"),("Groq Free","openai/gpt-oss-120b"),("PWA Brazzaville","icons locaux")]:
                con.execute("INSERT INTO astuces (titre,contenu,ts) VALUES (?,?,?)",(t,c,time.time()))
            con.commit()
        rows=[{"uid":x[0][:8],"q":x[1],"r":x[2][:500],"time":datetime.fromtimestamp(x[3]).strftime("%d/%m %H:%M"),"likes":x[4]} for x in con.execute("SELECT user_id,q,r,ts,likes FROM questions ORDER BY ts DESC LIMIT 50")]
        con.close()
        return rows
    except Exception as e:
        return []

@router.post("/api/community/post")
async def post(req: Request):
    try:
        d=await req.json()
        con=get_con()
        con.execute("INSERT INTO questions (user_id,q,r,ts) VALUES (?,?,?,?)",(d.get("user_id","anon")[:20],d.get("q","")[:500],d.get("r","")[:2000],time.time()))
        con.commit(); con.close()
        return {"ok":True}
    except Exception as e:
        return {"ok":False, "error": str(e)[:100]}

@router.get("/api/community/astuces")
def astuces():
    try:
        con=get_con(); r=[{"t":x[0],"c":x[1]} for x in con.execute("SELECT titre,contenu FROM astuces")]; con.close(); return r
    except: return []

@router.get("/api/community/top")
def top():
    try:
        con=get_con(); r=[{"uid":x[0][:8],"count":x[1]} for x in con.execute("SELECT user_id,COUNT(*) c FROM questions GROUP BY user_id ORDER BY c DESC LIMIT 10")]; con.close(); return r
    except: return []
