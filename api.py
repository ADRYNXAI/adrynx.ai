import os, base64
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from adrynx import PhoenixPrime
import requests

app = Flask(__name__, static_folder='.')
CORS(app)
brain = PhoenixPrime()

@app.route("/")
def home(): return send_from_directory('.', 'index.html')
@app.route("/<path:path>")
def static_files(path): return send_from_directory('.', path)

@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(force=True)
        msg = data.get("message","").strip()
        hist = data.get("history",[])
        img = data.get("image") # base64
        if not msg: return jsonify({"reply":"Dis quelque chose Jonathan"}), 400
        reply = brain.ask(msg, hist, image_base64=img)
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"reply": f"Phoenix Prime est en ligne même en cas d'erreur. Erreur: {str(e)[:200]}"}), 200

@app.route("/api/image", methods=["POST"])
def image_gen():
    # GENERATION IMAGE 100% GRATUITE via Pollinations
    try:
        data = request.get_json()
        prompt = data.get("prompt","")
        # MODE PREMIUM: tu fais payer 1000F avant d'appeler cette route
        url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?model=flux&nologo=true"
        return jsonify({"image_url": url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/health")
def health(): return jsonify({"status":"ADRYNX Phoenix Prime ONLINE", "model": os.environ.get("GROQ_MODEL")})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
