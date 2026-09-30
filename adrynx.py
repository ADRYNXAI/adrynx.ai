import os
import sqlite3
import uuid
from pathlib import Path
from typing import Dict, Any, Optional


# ============================================================
# CONFIGURATION
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.1-8b-instant"
)

PHOENIX_VIDEO = "https://files.catbox.moe/y2nvi4.mp4"

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "adrynx.db"


# ============================================================
# BASE DE DONNÉES
# ============================================================

def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            titre TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            owner TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_conversation
        ON messages(conversation_id, id)
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS intent_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phrase TEXT NOT NULL,
            intent TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()


init_db()


# ============================================================
# MOTEUR GROQ
# ============================================================

def groq_chat(
    system: str,
    messages: list,
    temperature: float = 0.4,
    max_tokens: int = 700
) -> str:

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY manquante dans les variables d'environnement."
        )

    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY)

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": system
            },
            *messages
        ],
        temperature=temperature,
        max_tokens=max_tokens
    )

    if not response.choices:
        raise RuntimeError(
            "Groq n'a retourné aucune réponse."
        )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "Groq a retourné une réponse vide."
        )

    return content.strip()


# ============================================================
# CONVERSATIONS
# ============================================================

def new_conversation(
    owner: str = "anon",
    titre: str = "Nouvelle conversation"
) -> str:

    conversation_id = "conv_" + uuid.uuid4().hex

    connection = db()

    connection.execute(
        """
        INSERT INTO conversations
        (id, owner, titre)
        VALUES (?, ?, ?)
        """,
        (
            conversation_id,
            owner,
            titre
        )
    )

    connection.commit()
    connection.close()

    return conversation_id


def ensure_conversation(
    owner: str,
    conversation_id: Optional[str]
) -> str:

    if conversation_id:
        connection = db()

        row = connection.execute(
            """
            SELECT id
            FROM conversations
            WHERE id = ? AND owner = ?
            """,
            (
                conversation_id,
                owner
            )
        ).fetchone()

        connection.close()

        if row:
            return conversation_id

    return new_conversation(
        owner,
        "Conversation ADRYNX"
    )


def save_message(
    conversation_id: str,
    owner: str,
    role: str,
    content: str
):

    connection = db()

    connection.execute(
        """
        INSERT INTO messages
        (conversation_id, owner, role, content)
        VALUES (?, ?, ?, ?)
        """,
        (
            conversation_id,
            owner,
            role,
            content
        )
    )

    connection.execute(
        """
        UPDATE conversations
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (conversation_id,)
    )

    connection.commit()
    connection.close()


def get_history(
    conversation_id: str,
    owner: str,
    limit: int = 12
):

    connection = db()

    rows = connection.execute(
        """
        SELECT role, content
        FROM messages
        WHERE conversation_id = ?
        AND owner = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (
            conversation_id,
            owner,
            limit
        )
    ).fetchall()

    connection.close()

    rows = list(reversed(rows))

    return [
        {
            "role": row["role"],
            "content": row["content"]
        }
        for row in rows
    ]


def state(conversation_id: str):

    connection = db()

    row = connection.execute(
        """
        SELECT *
        FROM conversations
        WHERE id = ?
        """,
        (conversation_id,)
    ).fetchone()

    connection.close()

    if not row:
        return {}

    return dict(row)


def messages(
    conversation_id: str,
    limit: int = 50
):

    connection = db()

    rows = connection.execute(
        """
        SELECT
            id,
            role,
            content,
            created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id ASC
        LIMIT ?
        """,
        (
            conversation_id,
            limit
        )
    ).fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# COMPRÉHENSION LÉGÈRE
# ============================================================

def detecter_intent(question: str) -> str:

    low = question.lower().strip()

    if not low:
        return "vide"

    # On garde uniquement quelques protections
    # déterministes très simples.
    if (
        low in {
            "cc",
            "slt",
            "salut",
            "yo",
            "hey",
            "bjr",
            "bonjour",
            "bonsoir",
            "coucou"
        }
    ):
        return "salutation"

    if (
        "qui es tu" in low
        or "qui es-tu" in low
        or "tu es qui" in low
        or "qui t'a créé" in low
        or "qui ta créé" in low
    ):
        return "identite"

    return "conversation"


# ============================================================
# IDENTITÉ
# ============================================================

def reponse_identite():

    return (
        "Je suis ADRYNX, l'assistant développé par "
        "Jonathan Dejah OBENDA. "
        "Je suis conçu pour comprendre les conversations, "
        "utiliser leur contexte et évoluer avec les fonctions "
        "qui seront progressivement ajoutées à mon système."
    )


# ============================================================
# PROMPT PRINCIPAL
# ============================================================

def system_prompt():

    return """
Tu es ADRYNX.

Tu es un assistant conversationnel réel intégré dans une
application appelée ADRYNX.

Ton objectif principal est de comprendre ce que l'utilisateur
veut dire et de répondre directement à son message.

RÈGLES IMPORTANTES :

1. Reste sur le sujet de l'utilisateur.

2. Utilise le contexte précédent de la conversation lorsqu'il
   est disponible.

3. Si l'utilisateur change de sujet, suis naturellement le
   nouveau sujet.

4. Une salutation simple doit recevoir une réponse naturelle,
   courte et adaptée. Ne répète pas toujours exactement la
   même phrase.

5. Si l'utilisateur demande comment tu vas, réponds à cette
   question au lieu de changer de sujet.

6. Ne prétends jamais avoir effectué une action que tu n'as
   réellement pas effectuée.

7. Ne prétends jamais avoir accès à une information qui ne
   t'est pas fournie.

8. Si tu ne sais pas quelque chose, dis-le clairement.

9. Ne transforme pas une question simple en longue explication
   inutile.

10. Réponds en français lorsque l'utilisateur écrit en français.

11. Le contexte de conversation fourni dans les messages
    précédents est une source importante pour comprendre les
    messages courts.

12. Ne parle pas de ton architecture interne sauf si
    l'utilisateur te le demande explicitement.

Tu dois privilégier la compréhension sémantique et le contexte
plutôt qu'un système composé uniquement de mots-clés.
"""


# ============================================================
# TRAITEMENT PRINCIPAL
# ============================================================

def traiter_question(
    question: str,
    owner: str = "anon",
    conversation_id: Optional[str] = None
) -> Dict[str, Any]:

    question = (question or "").strip()
    owner = (owner or "anon").strip()[:120] or "anon"

    if not question:
        return {
            "ok": False,
            "error": "Message vide."
        }

    conversation_id = ensure_conversation(
        owner,
        conversation_id
    )

    intent = detecter_intent(question)

    # --------------------------------------------------------
    # IDENTITÉ : réponse déterministe
    # --------------------------------------------------------

    if intent == "identite":

        response = reponse_identite()

        save_message(
            conversation_id,
            owner,
            "user",
            question
        )

        save_message(
            conversation_id,
            owner,
            "assistant",
            response
        )

        return {
            "ok": True,
            "reponse": response,
            "intent": intent,
            "source": "noyau",
            "conversation_id": conversation_id,
            "video_core": PHOENIX_VIDEO
        }

    # --------------------------------------------------------
    # CONVERSATION NORMALE
    # --------------------------------------------------------

    history = get_history(
        conversation_id,
        owner,
        limit=12
    )

    # On enregistre le nouveau message utilisateur
    save_message(
        conversation_id,
        owner,
        "user",
        question
    )

    # On reconstruit l'historique après l'enregistrement.
    history = get_history(
        conversation_id,
        owner,
        limit=12
    )

    try:

        response = groq_chat(
            system_prompt(),
            history,
            temperature=0.4,
            max_tokens=700
        )

    except Exception as e:

        # IMPORTANT :
        # aucune fausse réponse n'est envoyée.
        print("========== ADRYNX GROQ ERROR ==========")
        print(type(e).__name__)
        print(str(e))
        print("========================================")

        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "intent": intent,
            "conversation_id": conversation_id,
            "source": "groq-error",
            "video_core": PHOENIX_VIDEO
        }

    # --------------------------------------------------------
    # ENREGISTREMENT DE LA RÉPONSE
    # --------------------------------------------------------

    save_message(
        conversation_id,
        owner,
        "assistant",
        response
    )

    return {
        "ok": True,
        "reponse": response,
        "intent": intent,
        "source": "groq",
        "conversation_id": conversation_id,
        "video_core": PHOENIX_VIDEO
    }


# ============================================================
# DASHBOARD
# ============================================================

def dashboard(owner: str):

    connection = db()

    conversations = connection.execute(
        """
        SELECT COUNT(*)
        FROM conversations
        WHERE owner = ?
        """,
        (owner,)
    ).fetchone()[0]

    total_messages = connection.execute(
        """
        SELECT COUNT(*)
        FROM messages
        WHERE owner = ?
        """,
        (owner,)
    ).fetchone()[0]

    connection.close()

    return {
        "video": PHOENIX_VIDEO,
        "conversations": conversations,
        "messages": total_messages,
        "groq_configured": bool(GROQ_API_KEY)
    }


# ============================================================
# PROJETS / TÂCHES
# ============================================================

def projects(owner: str):

    return []


def project(
    owner: str,
    name: str,
    obj=None
):

    return {
        "nom": name,
        "owner": owner,
        "data": obj or {}
    }


def task(
    owner: str,
    title: str,
    project_id=None
):

    return {
        "titre": title,
        "owner": owner,
        "project_id": project_id
    }


# ============================================================
# FEEDBACK
# ============================================================

def enregistrer_feedback(*args):

    return {
        "ok": False,
        "error": (
            "Le système d'apprentissage par feedback "
            "n'est pas encore activé."
        )
    }


def stats_apprentissage():

    connection = db()

    total_messages = connection.execute(
        "SELECT COUNT(*) FROM messages"
    ).fetchone()[0]

    total_conversations = connection.execute(
        "SELECT COUNT(*) FROM conversations"
    ).fetchone()[0]

    connection.close()

    return {
        "video": PHOENIX_VIDEO,
        "messages": total_messages,
        "conversations": total_conversations
    }


def exporter_apprentissage():

    connection = db()

    rows = connection.execute(
        """
        SELECT phrase, intent
        FROM intent_examples
        ORDER BY id ASC
        """
    ).fetchall()

    connection.close()

    return [
        {
            "phrase": row["phrase"],
            "intent": row["intent"]
        }
        for row in rows
    ]


# ============================================================
# ADMIN
# ============================================================

def verifier_admin(secret: str):

    expected = os.getenv(
        "ADRYNX_ADMIN_SECRET"
    )

    if not expected:
        return False

    return secret == expected
