import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from adrynx import PhoenixPrime
import requests

app = Flask(__name__, static_folder='.')
CORS(app)
brain = PhoenixPrime()

@app.route("/")
def home(): 
    # Landing en page d'accueil pour vendre 1000F
    if os.path.exists("landing.html"):
        return send_from_directory('.', 'landing.html')
    return send_from_directory('.', 'index.html')

@app.route("/app")
def app_page():
    return send_from_directory('.', 'index.html')

@app.route("/<path:path>")
def static_files(path): 
    # Empêche de bloquer /api
    if path.startswith("api/"):
        return jsonify({"error":"use POST"}), 404
    return send_from_directory('.', path)

@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(force=True)
        msg = data.get("message","").strip()
        hist = data.get("history",[]) or []
        img = data.get("image")
        if not msg and not img: 
            return jsonify({"reply":"Envoie un message ou une photo de ton cours"}), 400
        reply = brain.ask(msg, hist, image_base64=img)
        return jsonify({"reply": reply})
    except Exception as e:
        print(f"CHAT ERROR: {e}")
        return jsonify({"reply": f"Phoenix Prime est en ligne. Redémarre. Erreur: {str(e)[:150]}"}), 200

@app.route("/api/image", methods=["POST"])
def image_gen():
    try:
        data = request.get_json(force=True)
        prompt = data.get("prompt","").strip()
        if not prompt: return jsonify({"error":"prompt vide"}), 400
        # 100% GRATUIT via Pollinations - pas de clé
        encoded = requests.utils.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?model=flux&width=1024&height=1024&nologo=true&seed={os.urandom(2).hex()}"
        return jsonify({"image_url": url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/health")
def health(): 
    return jsonify({"status":"ADRYNX Phoenix Prime ONLINE", "model": os.environ.get("GROQ_MODEL","llama-3.1-8b-instant")})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
