import os, urllib.parse, json, time
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
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
    if os.path.exists("landing.html"):
        return FileResponse("landing.html")
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
    return JSONResponse({"error": "pay manquant"}, status_code=404)

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
        return JSONResponse({"error": "wrong"}, status_code=401)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/admin/data")
async def admin_data(req: Request):
    if req.headers.get("X-Admin-Token") != ADMIN_TOKEN:
        return JSONResponse({"error": "unauth"}, status_code=401)
    return load_db()

@app.post("/api/admin/user")
async def admin_user_action(req: Request):
    if req.headers.get("X-Admin-Token") != ADMIN_TOKEN:
        return JSONResponse({"error": "unauth"}, status_code=401)
    data = await req.json()
    db = load_db()
    uid = data.get("id")
    act = data.get("action")
    for u in db["users"]:
        if u["id"] == uid:
            if act == "premium":
                u["premium"] = True
                u["unlimited"] = False
            elif act == "unlimited":
                u["premium"] = True
                u["unlimited"] = True
            elif act == "ban":
                u["premium"] = False
                u["unlimited"] = False
            elif act == "delete":
                db["users"] = [x for x in db["users"] if x["id"] != uid]
                break
    save_db(db)
    return {"ok": True}

@app.post("/api/admin/validate")
async def admin_validate(req: Request):
    if req.headers.get("X-Admin-Token") != ADMIN_TOKEN:
        return JSONResponse({"error": "unauth"}, status_code=401)
    data = await req.json()
    db = load_db()
    tid = data.get("id")
    db["transactions"] = [t for t in db["transactions"] if t["id"] != tid]
    save_db(db)
    return {"ok": True}

@app.post("/api/pay/request")
async def pay_request(req: Request):
    data = await req.json()
    db = load_db()
    db["transactions"].append({
        "id": f"tx_{os.urandom(4).hex()}",
        "user_id": data.get("user_id") or data.get("id"),
        "tel": data.get("tel"),
        "ref": data.get("ref") or data.get("trans"),
        "date": datetime.now().strftime("%d/%m %H:%M"),
        "amount": "1000F"
    })
    save_db(db)
    return {"ok": True}

@app.post("/api/chat")
async def chat_api(req: Request):
    try:
        data = await req.json()
        message = data.get("message", "")
        history = data.get("history", [])
        image = data.get("image")
        user_id = req.headers.get("X-User-Id", f"user_{os.urandom(3).hex()}")
        db = load_db()
        user = next((u for u in db["users"] if u["id"] == user_id), None)
        if not user:
            user = {
                "id": user_id,
                "date": datetime.now().strftime("%d/%m %H:%M"),
                "premium": False,
                "unlimited": False,
                "messages": 0,
                "images": 0,
                "last_reset": datetime.now().isoformat()
            }
            db["users"].append(user)
        if user_id == "jonathan_admin_unlimited":
            user["premium"] = True
            user["unlimited"] = True
        save_db(db)
        if not message and not image:
            return JSONResponse({"reply": "Dis quelque chose"})
        is_vip = user.get("premium") or user.get("unlimited")
        low = message.lower()
        keys = ["genere", "image", "dessine", "photo", "imagine", "affiche"]
        is_img = any(k in low for k in keys)
        if is_img:
            clean = low
            for w in ["genere moi", "une image de", "une image", "image de", "photo de"]:
                clean = clean.replace(w, "")
            safe = (clean.strip() or "Brazzaville")[:350]
            enc = urllib.parse.quote(safe)
            url = f"https://image.pollinations.ai/prompt/{enc}?width=1024&height=1024&model=flux&nologo=true&seed={os.urandom(2).hex()}"
            return {"reply": f"Image {safe}<br><img src='{url}' style='width:100%;border-radius:12px'/>"}
        reply = ai.ask(message, history[-6:], image_base64=image, is_premium=is_vip)
        return {"reply": reply}
    except Exception as e:
        return {"reply": f"Erreur {str(e)[:200]}"}

@app.post("/api/image")
async def gen_image(req: Request):
    data = await req.json()
    prompt = data.get("prompt", "ADRYNX")[:350]
    enc = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{enc}?width=1024&height=1024&model=flux&nologo=true"
    return {"image_url": url}
