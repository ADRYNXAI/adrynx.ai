def init_db():
    try:
        c = db()
        c.execute("CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, owner TEXT, titre TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        c.execute("CREATE TABLE IF NOT EXISTS intent_examples (id INTEGER PRIMARY KEY AUTOINCREMENT, phrase TEXT, intent TEXT)")
        c.commit()
        c.close()
        print("DB OK")
    except Exception as e:
        print(f"DB Error: {e}")

# Appelle la au démarrage
init_db()

def traiter_question(question, owner="anon", conversation_id=None):
    try:
        q = question.strip()
        if not q: return {"ok": True, "reponse": "Pose ta question"}
        
        # Si pas de clé Groq, réponds sans IA
        if not GROQ_API_KEY:
            return {"ok": True, "reponse": "Cc! C'est ADRYNX 🔥 (mode offline - clé Groq manquante). Je suis en ligne.", "intent": "salutation", "source": "offline"}
        
        candidat, contexte = pipeline_adrynx(q)
        controle = controler_parent(q, candidat, contexte)
        return {"ok": True, "reponse": controle["reponse"], "intent": contexte.get("intent")}
    
    except Exception as e:
        print(f"ERREUR ADRYNX: {e}")
        # JAMAIS de 500 - on renvoie toujours une réponse
        return {"ok": True, "reponse": f"Cc! C'est ADRYNX 🔥 (erreur rattrapée: {str(e)[:100]})", "intent": "salutation", "error": str(e)}
