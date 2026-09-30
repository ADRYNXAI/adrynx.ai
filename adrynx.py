import os
import sqlite3
import uuid
import re
import html
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from html.parser import HTMLParser

import requests


# ============================================================
# CONFIGURATION
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
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
# GROQ
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
# RECHERCHE INTERNET
# ============================================================

class SearchParser(HTMLParser):
    """
    Petit analyseur HTML sans dépendance supplémentaire.
    Il récupère les résultats de DuckDuckGo HTML.
    """

    def __init__(self):
        super().__init__()

        self.results = []

        self.current_link = None
        self.current_title = []
        self.current_description = []

        self.in_result_link = False
        self.in_result_title = False
        self.in_result_description = False

    def handle_starttag(self, tag, attrs):

        attributes = dict(attrs)

        classes = attributes.get("class", "")

        if tag == "a":

            href = attributes.get("href", "")

            if (
                "result__a" in classes
                and href
            ):
                self.current_link = href
                self.current_title = []
                self.current_description = []

                self.in_result_link = True
                self.in_result_title = True

        if tag in {"a", "div"}:

            if "result__snippet" in classes:
                self.in_result_description = True

    def handle_data(self, data):

        if self.in_result_title:
            self.current_title.append(data)

        if self.in_result_description:
            self.current_description.append(data)

    def handle_endtag(self, tag):

        if tag == "a" and self.in_result_link:

            title = " ".join(
                "".join(self.current_title).split()
            ).strip()

            description = " ".join(
                "".join(self.current_description).split()
            ).strip()

            if self.current_link and title:

                self.results.append({
                    "title": html.unescape(title),
                    "url": self.current_link,
                    "description": html.unescape(description)
                })

            self.current_link = None
            self.current_title = []
            self.current_description = []

            self.in_result_link = False
            self.in_result_title = False
            self.in_result_description = False


def nettoyer_url(url: str) -> str:

    if not url:
        return ""

    url = html.unescape(url)

    if url.startswith("//"):
        url = "https:" + url

    if url.startswith("/"):
        return ""

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        return ""

    return url


def rechercher_internet(
    question: str,
    nombre_resultats: int = 6
) -> Dict[str, Any]:

    question = (question or "").strip()

    if not question:
        return {
            "ok": False,
            "error": "Recherche vide.",
            "results": []
        }

    url = "https://html.duckduckgo.com/html/"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/131.0 Safari/537.36"
        )
    }

    try:

        response = requests.get(
            url,
            params={"q": question},
            headers=headers,
            timeout=15
        )

        response.raise_for_status()

        parser = SearchParser()
        parser.feed(response.text)

        results = []

        for result in parser.results:

            clean_url = nettoyer_url(
                result.get("url", "")
            )

            if not clean_url:
                continue

            results.append({
                "title": result.get(
                    "title",
                    ""
                ),
                "url": clean_url,
                "description": result.get(
                    "description",
                    ""
                )
            })

            if len(results) >= nombre_resultats:
                break

        if not results:

            return {
                "ok": False,
                "error": (
                    "La recherche Internet a été effectuée, "
                    "mais aucun résultat exploitable n'a été trouvé."
                ),
                "results": []
            }

        return {
            "ok": True,
            "query": question,
            "results": results
        }

    except requests.RequestException as e:

        print(
            "========== ADRYNX INTERNET ERROR =========="
        )
        print(type(e).__name__)
        print(str(e))
        print("============================================")

        return {
            "ok": False,
            "error": (
                "Impossible d'accéder au moteur de recherche "
                f"Internet : {type(e).__name__}: {e}"
            ),
            "results": []
        }

    except Exception as e:

        print(
            "========== ADRYNX SEARCH ERROR =========="
        )
        print(type(e).__name__)
        print(str(e))
        print("==========================================")

        return {
            "ok": False,
            "error": (
                f"Erreur pendant la recherche Internet : "
                f"{type(e).__name__}: {e}"
            ),
            "results": []
        }


# ============================================================
# DÉTECTION D'UNE DEMANDE INTERNET
# ============================================================

def demande_recherche_internet(question: str) -> bool:

    low = question.lower().strip()

    expressions = [
        "recherche sur internet",
        "rechercher sur internet",
        "cherche sur internet",
        "cherche sur le web",
        "recherche sur le web",
        "sur internet",
        "sur le web",
        "en ligne",
        "actualités",
        "actualité",
        "prix actuel",
        "prix actuel maintenant",
        "maintenant",
        "aujourd'hui",
        "aujourd’hui",
        "actuellement",
        "cours actuel",
        "dernières nouvelles",
        "dernière nouvelle",
        "news",
        "latest",
        "récent",
        "récente",
        "récents",
        "récentes"
    ]

    for expression in expressions:

        if expression in low:
            return True

    return False


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
        INSERT INTO conversations (
            id,
            owner,
            titre
        )
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
            WHERE id = ?
            AND owner = ?
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


# ============================================================
# MESSAGES
# ============================================================

def save_message(
    conversation_id: str,
    owner: str,
    role: str,
    content: str
):

    connection = db()

    connection.execute(
        """
        INSERT INTO messages (
            conversation_id,
            owner,
            role,
            content
        )
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
        (
            conversation_id,
        )
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
        (
            conversation_id,
        )
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
# COMPRÉHENSION DE BASE
# ============================================================

def detecter_intent(question: str) -> str:

    low = question.lower().strip()

    if not low:
        return "vide"

    if low in {
        "cc",
        "slt",
        "salut",
        "yo",
        "hey",
        "bjr",
        "bonjour",
        "bonsoir",
        "coucou"
    }:
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
        "réellement ajoutées à mon système."
    )


# ============================================================
# CAPACITÉS RÉELLES
# ============================================================

def system_prompt():

    return """
Tu es ADRYNX.

Tu es un assistant conversationnel réel intégré dans une
application appelée ADRYNX.

CAPACITÉS ACTUELLEMENT RÉELLES :

- Tu peux converser avec l'utilisateur grâce au modèle Groq.
- Tu peux utiliser l'historique de la conversation fourni par
  ton backend.
- Le backend sauvegarde les messages dans une base SQLite.
- Le backend peut effectuer une recherche Internet réelle
  lorsque la demande de l'utilisateur nécessite une recherche.
- Lorsque des résultats Internet sont fournis dans le contexte,
  tu peux les analyser et les résumer.
- Tu peux répondre en français lorsque l'utilisateur écrit
  en français.

CAPACITÉS QUI NE DOIVENT PAS ÊTRE PRÉSENTÉES COMME ACTIVES
SI ELLES NE SONT PAS FOURNIES DANS LE CONTEXTE :

- mémoire personnelle persistante intelligente ;
- apprentissage autonome ;
- raisonnement spécialisé indépendant ;
- système de parents IA ;
- accès arbitraire aux services externes ;
- exécution d'actions sur l'appareil de l'utilisateur ;
- projets et tâches persistants si aucune fonction correspondante
  n'est fournie.

RÈGLES :

1. Reste sur le sujet de l'utilisateur.

2. Utilise le contexte précédent lorsqu'il est disponible.

3. Si l'utilisateur change de sujet, suis naturellement le
   nouveau sujet.

4. Une salutation simple doit recevoir une réponse naturelle.

5. Si l'utilisateur demande comment tu vas, réponds directement
   à cette question.

6. Ne prétends jamais avoir effectué une action que tu n'as pas
   réellement effectuée.

7. Ne prétends jamais avoir utilisé Internet si aucun résultat
   Internet ne t'a été fourni.

8. Ne fabrique jamais un résultat de recherche.

9. Si une recherche Internet est fournie, distingue clairement
   les informations trouvées sur Internet de tes connaissances
   générales.

10. Pour une information actuelle, utilise les résultats
    Internet lorsqu'ils sont disponibles.

11. Si la recherche Internet échoue, indique clairement que la
    recherche a échoué.

12. Si les résultats disponibles ne permettent pas de répondre
    précisément, dis-le clairement.

13. Ne fabrique pas de faits.

14. Ne fabrique pas de fonctionnalités inexistantes dans ADRYNX.

15. Réponds en français lorsque l'utilisateur écrit en français.

16. Lorsque la question est simple, réponds simplement.

17. Lorsque l'utilisateur demande une explication détaillée,
    développe suffisamment pour être utile.

18. Ne parle pas de ton architecture interne sauf si
    l'utilisateur le demande explicitement.

19. Ne prétends pas avoir une mémoire permanente si elle n'est
    pas réellement activée.

20. Sois transparent sur tes limites réelles.
"""


# ============================================================
# CONSTRUCTION DU CONTEXTE INTERNET
# ============================================================

def construire_contexte_web(
    question: str,
    recherche: Dict[str, Any]
) -> str:

    lignes = []

    lignes.append(
        "RÉSULTATS D'UNE RECHERCHE INTERNET RÉELLE"
    )

    lignes.append(
        f"Question recherchée : {question}"
    )

    lignes.append("")

    for index, result in enumerate(
        recherche.get("results", []),
        start=1
    ):

        lignes.append(
            f"Résultat {index} :"
        )

        lignes.append(
            f"Titre : {result.get('title', '')}"
        )

        lignes.append(
            f"URL : {result.get('url', '')}"
        )

        description = result.get(
            "description",
            ""
        )

        if description:

            lignes.append(
                f"Extrait : {description}"
            )

        lignes.append("")

    return "\n".join(lignes)


# ============================================================
# TRAITEMENT PRINCIPAL
# ============================================================

def traiter_question(
    question: str,
    owner: str = "anon",
    conversation_id: Optional[str] = None
) -> Dict[str, Any]:

    question = (question or "").strip()

    owner = (
        (owner or "anon")
        .strip()[:120]
        or "anon"
    )

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
    # IDENTITÉ
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
    # HISTORIQUE
    # --------------------------------------------------------

    history = get_history(
        conversation_id,
        owner,
        limit=12
    )

    save_message(
        conversation_id,
        owner,
        "user",
        question
    )

    history = get_history(
        conversation_id,
        owner,
        limit=12
    )

    # --------------------------------------------------------
    # RECHERCHE INTERNET RÉELLE
    # --------------------------------------------------------

    web_context = None
    web_results = []

    if demande_recherche_internet(question):

        recherche = rechercher_internet(
            question,
            nombre_resultats=6
        )

        if not recherche.get("ok"):

            return {
                "ok": False,
                "error": recherche.get(
                    "error",
                    "La recherche Internet a échoué."
                ),
                "intent": intent,
                "conversation_id": conversation_id,
                "source": "internet-error",
                "video_core": PHOENIX_VIDEO
            }

        web_results = recherche.get(
            "results",
            []
        )

        web_context = construire_contexte_web(
            question,
            recherche
        )

        # Le contexte Web est ajouté comme message système
        # supplémentaire pour que Groq puisse l'analyser.
        history_for_groq = [
            {
                "role": "system",
                "content": web_context
            },
            *history
        ]

        source = "internet+groq"

    else:

        history_for_groq = history
        source = "groq"

    # --------------------------------------------------------
    # GROQ
    # --------------------------------------------------------

    try:

        response = groq_chat(
            system_prompt(),
            history_for_groq,
            temperature=0.4,
            max_tokens=700
        )

    except Exception as e:

        print(
            "========== ADRYNX GROQ ERROR =========="
        )

        print(
            type(e).__name__
        )

        print(
            str(e)
        )

        print(
            "========================================"
        )

        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "intent": intent,
            "conversation_id": conversation_id,
            "source": "groq-error",
            "video_core": PHOENIX_VIDEO
        }

    # --------------------------------------------------------
    # SAUVEGARDE
    # --------------------------------------------------------

    save_message(
        conversation_id,
        owner,
        "assistant",
        response
    )

    result = {
        "ok": True,
        "reponse": response,
        "intent": intent,
        "source": source,
        "conversation_id": conversation_id,
        "video_core": PHOENIX_VIDEO
    }

    if web_results:

        result["web_results"] = web_results

    return result


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
        (
            owner,
        )
    ).fetchone()[0]

    total_messages = connection.execute(
        """
        SELECT COUNT(*)
        FROM messages
        WHERE owner = ?
        """,
        (
            owner,
        )
    ).fetchone()[0]

    connection.close()

    return {
        "video": PHOENIX_VIDEO,
        "conversations": conversations,
        "messages": total_messages,
        "groq_configured": bool(GROQ_API_KEY),
        "model": GROQ_MODEL,
        "internet_search": True
    }


# ============================================================
# FONCTIONS FUTURES — PAS SIMULÉES
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
