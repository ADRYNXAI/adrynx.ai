import os, urllib.parse
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from adrynx import PhoenixPrime

app = FastAPI()
ai = PhoenixPrime()

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

@app.get("/manifest.json")
async def manifest():
    if os.path.exists("manifest.json"):
        return FileResponse("manifest.json")
    return JSONResponse({})

@app.get("/health")
async def health():
    return {"status":"online","model": os.environ.get("GROQ_MODEL","openai/gpt-oss-120b"), "creator":"Jonathan Obenda"}

@app.post("/api/chat")
async def chat(req: Request):
    try:
        data = await req.json()
        message = data.get("message","")
        history = data.get("history",[])
        image = data.get("image")
        if not message and not image:
            return JSONResponse({"reply":"Dis quelque chose Jonathan"})
        reply = ai.ask(message, history, image_base64=image)
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
