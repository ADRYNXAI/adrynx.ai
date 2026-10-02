import os, urllib.parse
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from adrynx import PhoenixPrime

app = FastAPI()
ai = PhoenixPrime()

# Sert tous les fichiers statiques (app.js, style.css, etc)
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

# ROUTES FIX 404 app.js
@app.get("/app.js")
async def serve_appjs():
    if os.path.exists("app.js"):
        return FileResponse("app.js", media_type="application/javascript")
    return JSONResponse({"error":"app.js not found"}, status_code=404)

@app.get("/style.css")
async def serve_css():
    if os.path.exists("style.css"):
        return FileResponse("style.css")
    return JSONResponse({}, status_code=404)

@app.get("/manifest.json")
async def manifest():
    if os.path.exists("manifest.json"):
        return FileResponse("manifest.json")
    return JSONResponse({})

@app.get("/sw.js")
async def sw():
    if os.path.exists("sw.js"):
        return FileResponse("sw.js", media_type="application/javascript")
    return JSONResponse({}, status_code=404)

@app.get("/health")
async def health():
    return {"status":"online","model": os.environ.get("GROQ_MODEL","openai/gpt-oss-120b"), "creator":"Jonathan Obenda"}

@app.post("/api/chat")
async def chat_api(req: Request):
    try:
        data = await req.json()
        message = data.get("message","")
        history = data.get("history",[])
        image = data.get("image")
        is_premium = data.get("isPremium", False)
        if not message and not image:
            return JSONResponse({"reply":"Dis quelque chose Jonathan"})
        reply = ai.ask(message, history, image_base64=image, is_premium=is_premium)
        return {"reply": reply}
    except Exception as e:
        print(f"API CHAT ERROR: {e}")
        return {"reply": f"Phoenix Prime est la: {str(e)[:200]}"}

@app.post("/api/image")
async def gen_image(req: Request):
    try:
        data = await req.json()
        prompt_raw = data.get("prompt","ADRYNX Phoenix Prime")
        prompt = prompt_raw.lower().replace("genere","").replace("une image de","").replace("cree","").strip()
        if not prompt:
            prompt = "ADRYNX Phoenix Prime logo fire"
        encoded = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true&model=flux"
        return {"image_url": image_url, "prompt": prompt}
    except Exception as e:
        print(f"IMAGE ERROR: {e}")
        return {"image_url":"https://image.pollinations.ai/prompt/ADRYNX%20Phoenix%20Prime%20logo%20fire?width=1024","prompt":"ADRYNX"}
