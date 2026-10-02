import os, urllib.parse, json, time
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from adrynx import PhoenixPrime

app = FastAPI()
ai = PhoenixPrime()

# --- ADMIN CONFIG ---
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ADRYNX2026")
ADMIN_TOKEN = "adrynx_admin_token_jonathan_secret_2026"
DB_FILE = "adrynx_db.json"

# --- NETFLIX DES IA : LES 4 MODES QUI COUTENT 0€ DE PLUS ---
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

@app.get('/
