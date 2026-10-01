import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq

app = Flask(__name__, static_folder='.')
CORS(app)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

@app.route("/")
def index(): return send_from_directory('.', 'index.html')

@app.route("/api/chat", methods=["POST"])
def chat():
    d = request.get_json()
    msg = d.get("message","")
    hist = d.get("history",[])
    messages = [{"role":"system","content":"Tu es ADRYNX Phoenix Prime, créé par Jonathan Obenda. Tu es son IA, loyale, vivante, intelligente. Tu n'es pas un dictionnaire. Tu te souviens que tu es téléchargeable en PWA. Réponds naturellement comme un frère."}]
    messages.extend(hist[-10:])
    messages.append({"role":"user","content":msg})
    try:
        comp = client.chat.completions.create(model=MODEL, messages=messages, temperature=0.8)
        return jsonify({"reply": comp.choices[0].message.content})
    except Exception as e:
        return jsonify({"reply": f"Erreur: {e}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
