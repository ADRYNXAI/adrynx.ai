import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import urllib.parse
from adrynx import PhoenixPrime

app = FastAPI()
ai = PhoenixPrime()

# Servir fichiers statiques
@app.get("/")
async def landing():
    if os.path.exists("landing.html"):
        return FileResponse("landing.html")
    return FileResponse("index.html")

@app.get("/app")
async def app_page():
    return FileResponse("index.html")

@app.get("/manifest.json")
async def manifest():
    return FileResponse("manifest.json")

@app.get("/health")
async def health():
    return {"status":"online","model": os.environ.get("GROQ_MODEL","openai/gpt-oss-120b"), "creator":"Jonathan Obenda"}

@app.post("/api/chat")
async def chat(req: Request):
    try:
        data = await req.json()
        message = data.get("message","")
        history = data.get("history",[])
        image = data.get("image")  # base64

        if not message and not image:
            return JSONResponse({"reply":"Dis quelque chose Jonathan 🔥"})

        reply = ai.ask(message, history, image_base64=image)
        return {"reply": reply}
    except Exception as e:
        print(f"API CHAT ERROR: {e}")
        return JSONResponse({"reply": f"Phoenix Prime est là même en erreur: {str(e)[:200]}"}, status_code=200)

@app.post("/api/image")
async def gen_image(req: Request):
    """Génération gratuite via Pollinations - pas besoin de clé"""
    try:
        data = await req.json()
        prompt = data.get("prompt","").replace("génère","").replace("genere","").replace("une
