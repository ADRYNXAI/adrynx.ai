# community.py - EVOLUE - Feed / Poser / Astuces / Top - Ne coupe jamais api.py
import sqlite3, time
from fastapi import APIRouter, Request
from datetime import datetime

router = APIRouter()
DB = "community.db"

def get_con():
    con = sqlite3.connect(DB, check_same_thread=False, timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS questions (id INTEGER PRIMARY KEY, user_id TEXT, q TEXT, r TEXT, ts REAL, likes INT DEFAULT 0)")
    con.execute("CREATE TABLE IF NOT EXISTS astuces (id INTEGER PRIMARY KEY, titre TEXT, contenu TEXT, ts REAL)")
    con.commit()
    return con

def _seed_astuces(con):
    # EVOLUTION : on ne sème qu'une fois, sinon tu as des doublons
    try:
        if con.execute("SELECT COUNT(*) FROM astuces").fetchone()[0] == 0:
            base = [
                ("Deploy Render", "uvicorn api:app --host 0.0.0.0 --port $PORT"),
                ("Orbe offline", "sw.js cache-first orb.mp4"),
                ("Groq Free", "openai/gpt-oss-120b"),
                ("PWA Brazzaville", "icons locaux"),
            ]
            for t, c in base:
                con.execute("INSERT INTO astuces (titre,contenu,ts) VALUES (?,?,?)", (t, c, time.time()))
            con.commit()
    except Exception as e:
        print(f"Seed astuces fail: {e}")

@router.get("/api/community/feed")
def feed():
    con = None
    try:
        con = get_con()
        _seed_astuces(con)
        rows = []
        for x in con.execute("SELECT user_id,q,r,ts,likes FROM questions ORDER BY ts DESC LIMIT 50"):
            try:
                rows.append({
                    "uid": (x[0] or "anon")[:8],
                    "q": x[1] or "",
                    "r": (x[2] or "")[:500],
                    "time": datetime.fromtimestamp(x[3] or time.time()).strftime("%d/%m %H:%M"),
                    "likes": x[4] or 0,
                })
            except:
                continue
        return rows
    except Exception as e:
        print(f"Feed fail: {e}")
        return []
    finally:
        if con:
            try: con.close()
            except: pass

@router.post("/api/community/post")
async def post(req: Request):
    con = None
    try:
        d = await req.json()
        q = str(d.get("q", "") or "").strip()[:500]
        r = str(d.get("r", "") or "").strip()[:2000]
        uid = str(d.get("user_id", "anon") or "anon")[:20]
        if not q or not r:
            return {"ok": False, "error": "Question et réponse obligatoires"}
        con = get_con()
        con.execute("INSERT INTO questions (user_id,q,r,ts) VALUES (?,?,?,?)", (uid, q, r, time.time()))
        con.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}
    finally:
        if con:
            try: con.close()
            except: pass

@router.get("/api/community/astuces")
def astuces():
    con = None
    try:
        con = get_con()
        _seed_astuces(con)
        r = [{"t": x[0], "c": x[1]} for x in con.execute("SELECT titre,contenu FROM astuces ORDER BY id ASC")]
        return r
    except Exception as e:
        print(f"Astuces fail: {e}")
        return []
    finally:
        if con:
            try: con.close()
            except: pass

@router.get("/api/community/top")
def top():
    con = None
    try:
        con = get_con()
        r = [{"uid": (x[0] or "anon")[:8], "count": x[1]} for x in con.execute("SELECT user_id,COUNT(*) c FROM questions GROUP BY user_id ORDER BY c DESC LIMIT 10")]
        return r
    except Exception as e:
        print(f"Top fail: {e}")
        return []
    finally:
        if con:
            try: con.close()
            except: pass

# EVOLUTION : like, pour que le Feed vive, sans casser l'ancien Feed
@router.post("/api/community/like")
async def like(req: Request):
    con = None
    try:
        d = await req.json()
        qid = int(d.get("id", 0))
        con = get_con()
        con.execute("UPDATE questions SET likes = likes + 1 WHERE id=?", (qid,))
        con.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}
    finally:
        if con:
            try: con.close()
            except: pass
