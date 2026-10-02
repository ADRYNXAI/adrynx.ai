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
    "general": "Tu es ADRYNX Phoenix Prime, créée par Jonathan Dejah OBENDA. Réponds direct, sans filtre inutile.",
    "etudiant": "Mode Étudiant: Tu es le meilleur prof de Marien Ngouabi. Explique simplement, donne plans d'exposés, mémoires.",
    "vendeur": "Mode Vendeur: Expert business à Brazzaville. Tu crées descriptions produits qui vendent, scripts TikTok, prix en FCFA.",
    "codeur": "Mode Codeur: Comme Claude, expert code Python, JS. Tu es créé par Jonathan, pas Anthropic.",
    "image": "Mode Image: Expert prompt pour Flux Pro 4K."
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

if os.path.exists('static'):
    app.mount('/static', StaticFiles(directory='static'), name='static')

@app.get('/')
async def landing():
    if os.path.exists('landing.html'):
        return FileResponse('landing.html')
    return FileResponse('index.html')

@app.get('/app')
async def app_page():
    return FileResponse('index.html')

@app.get('/chat')
async def chat_redirect():
    return FileResponse('index.html')

@app.get('/admin')
async def admin_page():
    if os.path.exists('admin.html'):
        return FileResponse('admin.html')
    return JSONResponse({'error':'admin.html manquant'}, status_code=404)

@app.get('/app.js')
async def serve_appjs():
    if os.path.exists('app.js'):
        return FileResponse('app.js', media_type='application/javascript')
    return JSONResponse({'error':'app.js not found'}, status_code=404)

@app.get('/style.css')
async def serve_css():
    if os.path.exists('style.css'):
        return FileResponse('style.css')
    return JSONResponse({}, status_code=404)

@app.get('/manifest.json')
async def manifest():
    if os.path.exists('manifest.json'):
        return FileResponse('manifest.json')
    return JSONResponse({})

@app.get('/sw.js')
async def sw():
    if os.path.exists('sw.js'):
        return FileResponse('sw.js', media_type='application/javascript')
    return JSONResponse({}, status_code=404)

@app.get('/health')
async def health():
    db = load_db()
    return {'status':'online','users':len(db["users"]),'creator':'Jonathan Obenda'}

@app.post('/api/admin/login')
async def admin_login(req: Request):
    data=await req.json()
    if data.get("password")==ADMIN_PASSWORD:
        return {"token":ADMIN_TOKEN}
    return JSONResponse({"error":"wrong"},401)

@app.get('/api/admin/data')
async def admin_data(req: Request):
    if req.headers.get("X-Admin-Token")!=ADMIN_TOKEN:
        return JSONResponse({"error":"unauth"},401)
    return load_db()

@app.post('/api/admin/user')
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

@app.post('/api/admin/validate')
async def admin_validate(req: Request):
    if req.headers.get("X-Admin-Token")!=ADMIN_TOKEN:
        return JSONResponse({"error":"unauth"},401)
    data=await req.json(); db=load_db(); tid=data.get("id")
    db["transactions"]=[t for t in db["transactions"] if t["id"]!=tid]; save_db(db); return {"ok":True}

@app.post('/api/chat')
async def chat_api(req: Request):
    try:
        data=await req.json()
        message=data.get('message',''); history=data.get('history',[]); image=data.get('image')
        mode=data.get('mode','general')
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
        if not message and not image: return JSONResponse({'reply':'Dis quelque chose'})
        is_vip=user.get("unlimited") or user.get("premium")
        low=message.lower()
        if image and not is_vip: return {'reply':"📸 Photo reserve Premium 1000F/semaine"}
        if not is_vip: time.sleep(1)
        image_keys=['genere','génère','image','dessine','photo','cree image','crée image','imagine','affiche']
        is_image_request=any(k in low for k in image_keys)
        if is_image_request:
            clean=low
            for w in ['genere','génère','moi','une image de','une image','image de','stp','please','tu peux','affiche','genere moi','cree','une photo de','photo de']: clean=clean.replace(w,'')
            clean=clean.strip() or 'futuristic Brazzaville Congo'
            if not is_vip and user.get("images",0)>=3:
                enc=urllib.parse.quote(f'{clean}, simple style'[:350])
                img_url=f'https://image.pollinations.ai/prompt/{enc}?width=512&height=512&model=turbo&seed={os.urandom(2).hex()}'
                return {'reply':f"⚠️ 3/3 HD atteintes<br><img src='{img_url}' style='width:100%'/><br>Passe Premium 1000F"}
            enc=urllib.parse.quote(f'{clean}, hyper-realistic, 8K'[:350])
            img_url=f'https://image.pollinations.ai/prompt/{enc}?width=1280&height=1280&model=flux-pro&enhance=true&seed={os.urandom(2).hex()}'
            if not is_vip: user["images"]+=1; save_db(db)
            return {'reply':f"🔥 {clean}<br><img src='{img_url}' style='width:100%'/><br><a href='{img_url}' target='_blank'>📥 Télécharger HD</a>"}
        if not is_vip and user["messages"]>=25:
            return {'reply':"🔒 Limite 25 messages/jour atteinte. Premium 1000F/semaine pour illimite."}
        system_prompt=MODES.get(mode, MODES["general"])
        final_history=[] if not is_vip else history[-6:]
        full_message=f"[{system_prompt}] Utilisateur: {message}"
        reply=ai.ask(full_message, final_history, image_base64=image, is_premium=is_vip)
        if not is_image_request: user["messages"]+=1; save_db(db)
        return {'reply': reply}
    except Exception as e:
        print(f'ERROR: {e}'); return {'reply': f'Erreur: {str(e)[:200]}'}

@app.post('/api/image')
async def gen_image(req: Request):
    try:
        data=await req.json(); prompt_raw=data.get('prompt','ADRYNX'); prompt=prompt_raw.lower().replace('genere','').strip() or 'ADRYNX logo fire'
        encoded=urllib.parse.quote(f"{prompt}, hyper-realistic, 8K"[:350])
        image_url=f'https://image.pollinations.ai/prompt/{encoded}?width=1280&height=1280&model=flux-pro&enhance=true&seed={os.urandom(2).hex()}'
        return {'image_url': image_url, 'prompt': prompt}
    except Exception as e:
        return {'image_url':'https://image.pollinations.ai/prompt/ADRYNX%20logo%20fire?width=1280&height=1280&model=flux-pro','prompt':'ADRYNX'}
