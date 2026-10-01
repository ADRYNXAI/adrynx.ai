import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from adrynx import PhoenixPrime

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
        if not msg: return jsonify({"reply":"Dis quelque chose Jonathan"}), 400
        reply = brain.ask(msg, hist)
        return jsonify({"reply": reply})
    except Exception as e:
        # NE PLANTE JAMAIS
        return jsonify({"reply": f"Phoenix Prime est en ligne même en cas d'erreur. Erreur capturée: {str(e)[:200]}. Réessaie, je suis là."}), 200

@app.route("/api/health")
def health(): return jsonify({"status":"ADRYNX Phoenix Prime ONLINE", "model": os.environ.get("GROQ_MODEL"), "memory":"ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
