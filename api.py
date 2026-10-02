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
    if os.path.exists("sw.js
