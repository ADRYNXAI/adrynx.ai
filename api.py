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
    return JSONResponse({"error":"admin.html manquant"}, status_code=404)

@app.get("/app.js")
async def serve_appjs():
    return FileResponse("app.js", media_type="application/javascript") if os.path.exists("app.js") else JSONResponse({},404)

@app.get("/style.css")
async def serve_css():
    return FileResponse("style.css") if os.path.exists("style.css") else JSONResponse({},404)

@app.get("/manifest.json")
async def manifest():
    return FileResponse("manifest.json") if os.path.exists("manifest.json") else JSONResponse({})

@app.get("/sw.js")
async def sw():
    return FileResponse("sw.js", media_type="application/javascript") if os.path.exists("sw.js") else JSONResponse({},404)

@app.get("/health")
async def health():
    db = load_db()
    return {"status":"online","users":len(db["users"])}

@app.post("/api/admin/login")
async def admin_login(req: Request):
    data=await req.json()
    if data.get("password")==ADMIN_PASSWORD:
        return {"token":ADMIN_TOKEN}
    return JSONResponse({"error":"wrong"},401)

@app.get("/api/admin/data")
async def admin_data(req: Request):
    if req.headers.get("X-Admin-Token")!=ADMIN_TOKEN:
        return JSONResponse({"error":"unauth"},401)
    return load_db()

@app.post("/api/admin/user")
async def admin_user_action(req: Request):
    if req.headers.get("X-Admin-Token")!=ADMIN_TOKEN:
        return JSONResponse({"error":"unauth"},401)
    data=await req.json(); db=load_db(); uid=data.get("id"); act=data.get("action")
    for u in db["users"]:
        if u["id"]==uid:
            if act=="premium": u["premium"]=True
            if act=="unlimited": u["unlimited"]=True; u["premium"]=True
            if act=="delete": db["users"]=[x for x in db["users"] if x["id"]!=uid]; break
    save_db(db); return {"ok":True}

@app.post("/api/admin/validate")
async def admin_validate(req: Request):
    if req.headers.get("X-Admin-Token")!=ADMIN_TOKEN:
        return JSONResponse({"error":"unauth"},401)
    data=await req.json(); db=load_db(); tid=data.get("id")
    db["transactions"]=[t for t in db["transactions"] if t["id"]!=tid]; save_db(db); return {"ok":True}

@app.post("/api/chat")
async def chat_api(req: Request):
    try:
        data=await req.json()
        message=data.get("message",""); history=data.get("history",[]); image=data.get("image")
        mode=data.get("mode","general")
        user_id=req.headers.get("X-User-Id", f"user_{os.urandom(3).hex()}")
        db=load_db()
        user=next((u for u in db["users"] if u["id"]==user_id), None)
        if not user:
            user={"id":user_id,"date":datetime.now().strftime("%d/%m %H:%M"),"premium":user_id=="jonathan_admin_unlimited","unlimited":user_id=="jonathan_admin_unlimited","messages":0,"images":0,"last_reset":datetime.now().isoformat()}
            db["users"].append(user)
        if "messages" not in user: user["messages"]=0
        if "images" not in user: user["images"]=0
        if "last_reset" not in user: user["last_reset"]=datetime.now().isoformat()
        try:
            last=datetime.fromisoformat(user["last_reset"])
            if datetime.now()-last>timedelta(hours=24):
                user["messages"]=0; user["images"]=0; user["last_reset"]=datetime.now().isoformat()
        except: pass
        if user_id=="jonathan_admin_unlimited": user["premium"]=True; user["unlimited"]=True
        save_db(db)
        if not message and not image:
            return JSONResponse({"reply":"Dis quelque chose"})
        is_vip=user.get("unlimited") or user.get("premium")
        low=message.lower()
        if image and not is_vip:
            return {"reply":"Photo reserve Premium 1000F"}
        if not is_vip:
            time.sleep(1)
        keys=["genere","genere","image","dessine","photo","imagine","affiche"]
        is_img=any(k in low for k in keys)
        if is_img:
            clean=low
            for w in ["genere","genere moi","moi","une image de","une image","image de","stp","please","tu peux","affiche","cree","une photo de","photo de"]:
                clean=clean.replace(w,"")
            clean=clean.strip() or "futuristic Brazzaville Congo"
            safe=clean[:350]
            enc=urllib.parse.quote(safe)
            # GRATUIT - PAS DE FLUX-PRO
            if not is_vip and user.get("images",0)>=3:
                url=f"https://image.pollinations.ai/prompt/{enc}?width=512&height=512&model=turbo&nologo=true&seed={os.urandom(2).hex()}"
                return {"reply":f"3/3 HD atteintes<br><img src='{url}' style='width:100%;border-radius:12px'/><br>Passe Premium 1000F"}
            url=f"https://image.pollinations.ai/prompt/{enc}?width=1024&height=1024&model=flux&nologo=true&seed={os.urandom(2).hex()}"
            if not is_vip:
                user["images"]+=1
                save_db(db)
            return {"reply":f"Image {safe}<br><img src='{url}' style='width:100%;border-radius:12px'/><br><a href='{url}' target='_blank'>Telecharger HD</a>"}
        if not is_vip and user["messages"]>=25:
            return {"reply":"Limite 25 messages/jour atteinte. Premium 1000F/semaine."}
        sys_prompt=MODES.get(mode, MODES["general"])
        final_hist=[] if not is_vip else history[-6:]
        full=f"[{sys_prompt}] Utilisateur: {message}"
        reply=ai.ask(full, final_hist, image_base64=image, is_premium=is_vip)
        if not is_img:
            user["messages"]+=1
            save_db(db)
        return {"reply": reply}
    except Exception as e:
        print(f"ERROR {e}")
        return {"reply": f"Erreur {str(e)[:200]}"}

@app.post("/api/image")
async def gen_image(req: Request):
    try:
        data=await req.json()
        prompt=data.get("prompt","ADRYNX logo fire")[:350]
        enc=urllib.parse.quote(prompt)
        url=f"https://image.pollinations.ai/prompt/{enc}?width=1024&height=1024&model=flux&nologo=true&seed={os.urandom(2).hex()}"
        return {"image_url": url, "prompt": prompt}
    except Exception as e:
        return {"image_url":"https://image.pollinations.ai/prompt/ADRYNX?width=1024&height=1024&model=flux&nologo=true","prompt":"ADRYNX"}
