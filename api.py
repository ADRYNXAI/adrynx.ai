from fastapi import FastAPI, Request, Header, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3, time, os, uuid

app = FastAPI(title="ADRYNX PHOENIX PRIME V16")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

ADMIN_PASSWORD = "ADRYNX2026"
ADMIN_TOKEN = "adrynx_boss_2026"

def get_con(db):
    return sqlite3.connect(db, check_same_thread=False, timeout=10)

def check_limit(uid):
    try:
        con=get_con("memoire.db")
        con.execute("CREATE TABLE IF NOT EXISTS limits (user_id TEXT, date TEXT, count INT, PRIMARY KEY(user_id,date))")
        today=time.strftime("%Y-%m-%d")
        r=con.execute("SELECT count FROM limits WHERE user_id=? AND date=?",(uid,today)).fetchone()
        con.close()
        return r[0] if r else 0
    except: return 0

def bump_limit(uid):
    try:
        con=get_con("memoire.db")
        con.execute("CREATE TABLE IF NOT EXISTS limits (user_id TEXT, date TEXT, count INT, PRIMARY KEY(user_id,date))")
        today=time.strftime("%Y-%m-%d")
        con.execute("INSERT INTO limits VALUES (?,?,1) ON CONFLICT(user_id,date) DO UPDATE SET count=count+1",(uid,today))
        con.commit(); con.close()
    except: pass

def init_db():
    con=get_con("settings.db")
    con.execute("CREATE TABLE IF NOT EXISTS settings (user_id TEXT PRIMARY KEY, style TEXT, chaleur TEXT, enthousiasme TEXT, emojis TEXT, couleur TEXT, memoire TEXT)")
    con.commit(); con.close()
    con=get_con("memoire.db")
    con.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, tel TEXT, date TEXT, premium INTEGER, unlimited INTEGER, messages INTEGER, images INTEGER)")
    con.execute("CREATE TABLE IF NOT EXISTS transactions (id TEXT PRIMARY KEY, user_id TEXT, tel TEXT, ref TEXT, amount TEXT, date TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS limits (user_id TEXT, date TEXT, count INT, PRIMARY KEY(user_id,date))")
    con.commit(); con.close()
init_db()

def safe_file(name):
    # Ne plante plus si le fichier n'existe pas
    if name and os.path.exists(name):
        return FileResponse(name)
    return JSONResponse({"error":"Fichier non trouve: "+str(name)}, status_code=404)

@app.get("/")
def root(): return safe_file("landing.html")
@app.get("/app")
def app_page(): return safe_file("index.html")
@app.get("/vocal.html")
def vocal_page(): return safe_file("index.html")
@app.get("/pay")
def pay(): return safe_file("pay.html")
@app.get("/admin")
def admin(): return safe_file("admin.html")
@app.get("/favicon.ico")
def favicon(): return safe_file("icon-192.png")
@app.get("/robots.txt")
def robots(): return safe_file("robots.txt")
@app.get("/sitemap.xml")
def sitemap(): return safe_file("sitemap.xml")
@app.get("/orb.mp4")
def orb(): return safe_file("orb.mp4")
@app.get("/icon-192.png")
def i192(): return safe_file("icon-192.png")
@app.get("/icon-512.png")
def i512(): return safe_file("icon-512.png")
@app.get("/style.css")
def css(): return safe_file("style.css")
@app.get("/sw.js")
def sw(): return safe_file("sw.js")
@app.get("/manifest.json")
def mani(): return safe_file("manifest.json")

@app.post("/api/admin/login")
async def admin_login(req: Request):
    d=await req.json()
    if d.get("password") == ADMIN_PASSWORD:
        return {"token": ADMIN_TOKEN}
    return JSONResponse({"error":"Mauvais mot de passe"}, status_code=401)

@app.get("/api/admin/data")
def admin_data(x_admin_token: str = Header(None)):
    if x_admin_token!= ADMIN_TOKEN:
        return JSONResponse({"error":"Non autorisé"}, status_code=401)
    con=get_con("memoire.db")
    users = con.execute("SELECT * FROM users").fetchall()
    txs = con.execute("SELECT * FROM transactions").fetchall()
    con.close()
    return {
        "users": [{"id":r[0],"tel":r[1],"date":r[2],"premium":bool(r[3]),"unlimited":bool(r[4]),"messages":r[5],"images":r[6]} for r in users],
        "transactions": [{"id":r[0],"user_id":r[1],"tel":r[2],"ref":r[3],"amount":r[4],"date":r[5]} for r in txs]
    }

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
        uid=str(d.get("user_id","anon"))[:50]
        if check_limit(uid)>=25 and not d.get("is_vip",False):
            return {"reponse":"🔥 Limite 25/25. Premium 1000F/semaine /pay - MTN 061174945"}
        rep=repondre(d.get("message","")[:2000], mode=d.get("mode","general"), user_id=uid)
        bump_limit(uid)
        return {"reponse": rep}
    except Exception as e:
        return {"reponse": f"ADRYNX respire... réessaie: {str(e)[:80]}"}

def _extract_pdf_text(chemin):
    # Plan B : extrait le texte sans dépendre de _phoenix
    texte=""
    try:
        # Essaie pypdf / PyPDF2
        try:
            from pypdf import PdfReader
        except:
            from PyPDF2 import PdfReader
        reader=PdfReader(chemin)
        for p in reader.pages[:15]:
            try: texte+=(p.extract_text() or "")+"\n"
            except: pass
    except Exception:
        pass
    if not texte.strip():
        # Essaie fitz / PyMuPDF
        try:
            import fitz
            doc=fitz.open(chemin)
            for p in doc:
                texte+=p.get_text()+"\n"
            doc.close()
        except Exception:
            pass
    return texte.strip()[:12000]

@app.post("/api/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    chemin=None
    try:
        contenu = await file.read()
        if len(contenu)>10*1024*1024:
            return {"reponse":"Chef, ce PDF est trop lourd. Envoie un PDF de moins de 10Mo."}
        if not (file.filename or "").lower().endswith(".pdf"):
            return {"reponse":"Chef, envoie un vrai fichier .pdf."}
        chemin = f"/tmp/{uuid.uuid4().hex}.pdf"
        with open(chemin, "wb") as f:
            f.write(contenu)
        # 1. On essaie d'abord ta fonction d'origine
        try:
            from adrynx import _phoenix
            if hasattr(_phoenix, "resumer_pdf"):
                reponse = _phoenix.resumer_pdf(chemin, question="Résume ce PDF en français simple, pour Jonathan")
                if reponse and len(str(reponse).strip())>10:
                    return {"reponse": str(reponse)}
        except Exception:
            pass
        # 2. Plan B : extraction + repondre()
        texte=_extract_pdf_text(chemin)
        if not texte:
            return {"reponse":"Chef, je n'ai pas pu lire ce PDF. Il est peut-être scanné en image, ou protégé. Essaie un autre PDF avec du vrai texte."}
        from adrynx import repondre
        prompt=f"Voici le texte d'un PDF que Jonathan vient d'envoyer. Résume-le en français simple, clair, avec les points importants en liste. Texte :\n\n{texte}"
        rep=repondre(prompt, mode="general", user_id="pdf_user")
        return {"reponse": rep}
    except Exception as e:
        return {"reponse": f"Erreur PDF : {str(e)[:100]}"}
    finally:
        if chemin and os.path.exists(chemin):
            try: os.remove(chemin)
            except: pass

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
    d=await req.json()
    uid=d.get("user_id","anon")
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
