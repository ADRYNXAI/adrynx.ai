# ============================================================
# ADRYNX — NOYAU COGNITIF PROPRIÉTAIRE
# Version : 5.0 Cognitive Core
# Créateur : Jonathan Dejah OBENDA
# Date de création : 2 juin 2026
#
# Objectif :
# Comprendre → Contextualiser → Raisonner → Générer
# → Vérifier → Répondre → Apprendre
#
# Compatible :
# - Python 3.10+
# - SQLite
# - Render Free / faible RAM
# - GROQ_API_KEY existante
# - ADRYNX_MODELE_GROQ existante
# - ADRYNX_DB existante
# - ADRYNX_ADMIN_SECRET existante
#
# IMPORTANT :
# Ce fichier ne nécessite aucune nouvelle variable Render.
# ============================================================

import os
import re
import json
import sqlite3
import threading
import unicodedata
import uuid
import time
import difflib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests


# ============================================================
# 1. CONFIGURATION
# ============================================================

DB = os.environ.get("ADRYNX_DB", "memoire.db")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

GROQ_MODEL = os.environ.get(
    "ADRYNX_MODELE_GROQ",
    "llama-3.3-70b-versatile"
).strip()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

ADMIN_SECRET = os.environ.get("ADRYNX_ADMIN_SECRET", "")

HEADERS = {
    "User-Agent": "ADRYNX/5.0-Cognitive-Core"
}

DB_LOCK = threading.RLock()

MAX_CONTEXT_MESSAGES = 12
MAX_MESSAGE_LENGTH = 12000
MAX_PROMPT_LENGTH = 30000
MAX_MEMORY_RESULTS = 6
MAX_LEARNING_RESULTS = 5

HTTP_TIMEOUT = 12

# ============================================================
# 2. IDENTITÉ FONDAMENTALE — IMMUTABLE
# ============================================================

IDENTITE_ADRYNX = {
    "name": "ADRYNX",
    "creator": "Jonathan Dejah OBENDA",
    "founder": "Jonathan Dejah OBENDA",
    "creation_date": "2 juin 2026",
    "creation_date_iso": "2026-06-02",
    "symbolic_relation": "père créateur",
    "symbolic_relation_note": (
        "Relation symbolique liée à la création du système. "
        "Elle ne constitue pas une relation biologique."
    ),
    "vision": "Intelligence conversationnelle et plateforme numérique interactive",
    "immutable": True,
}


# ============================================================
# 3. HIÉRARCHIE DES INFORMATIONS
# ============================================================

INFO_SYSTEM = 0
INFO_RULE = 1
INFO_SESSION = 2
INFO_USER = 3
INFO_KNOWLEDGE = 4
INFO_EXTERNAL = 5
INFO_HYPOTHESIS = 6


# ============================================================
# 4. TYPES D'INTENTION
# ============================================================

INTENTIONS = {
    "salutation",
    "conversation",
    "factuelle",
    "explication",
    "calcul",
    "raisonnement",
    "recherche",
    "programmation",
    "creation",
    "traduction",
    "correction",
    "opinion",
    "comparaison",
    "instruction",
    "ambiguite",
    "clarification",
    "suivi",
    "identite",
    "plateforme",
    "feedback",
    "inconnue",
}

MODES = {
    "SOCIAL",
    "INFORMATIF",
    "PEDAGOGIQUE",
    "TECHNIQUE",
    "CREATIF",
    "ANALYTIQUE",
    "RESOLUTION",
    "PLANIFICATION",
    "RECHERCHE",
    "ASSISTANCE",
    "DIALOGUE",
}


# ============================================================
# 5. OUTILS DE BASE
# ============================================================

def maintenant() -> str:
    return datetime.now(timezone.utc).isoformat()


def normaliser_texte(text: Any) -> str:
    if text is None:
        return ""

    text = str(text).strip()

    text = unicodedata.normalize("NFKC", text)

    text = re.sub(r"\s+", " ", text)

    return text[:MAX_MESSAGE_LENGTH]


def sans_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text)

    return "".join(
        c for c in text
        if unicodedata.category(c) != "Mn"
    )


def minuscules(text: str) -> str:
    return sans_accents(text.lower())


def tokens(text: str) -> List[str]:
    text = minuscules(text)

    return re.findall(
        r"[a-z0-9àâäçéèêëîïôöùûüÿœ'-]+",
        text
    )


def nettoyer_reponse(text: Any) -> str:
    if text is None:
        return ""

    text = str(text).strip()

    text = re.sub(
        r"^```(?:text|markdown)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(r"\s*```$", "", text)

    return text.strip()[:12000]


def similarite(a: str, b: str) -> float:
    if not a or not b:
        return 0.0

    a_tokens = set(tokens(a))
    b_tokens = set(tokens(b))

    if not a_tokens or not b_tokens:
        return 0.0

    intersection = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)

    jaccard = intersection / union if union else 0.0

    sequence = difflib.SequenceMatcher(
        None,
        minuscules(a),
        minuscules(b)
    ).ratio()

    return (jaccard * 0.65) + (sequence * 0.35)


def json_safe(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False
        )
    except Exception:
        return "{}"


# ============================================================
# 6. BASE DE DONNÉES
# ============================================================

def connexion_db():
    conn = sqlite3.connect(
        DB,
        timeout=20,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=20000")
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass

    return conn


def init_db():
    with DB_LOCK:
        conn = connexion_db()

        try:
            # ------------------------------------------------
            # Connaissances
            # ------------------------------------------------

            conn.execute("""
                CREATE TABLE IF NOT EXISTS connaissances_publiques (
                    question TEXT PRIMARY KEY,
                    reponse TEXT NOT NULL,
                    confiance REAL DEFAULT 0.5,
                    source TEXT DEFAULT 'unknown',
                    niveau INTEGER DEFAULT 4,
                    cree_le TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS connaissances_privees (
                    telephone TEXT NOT NULL,
                    question TEXT NOT NULL,
                    reponse TEXT NOT NULL,
                    niveau INTEGER DEFAULT 3,
                    cree_le TEXT,
                    PRIMARY KEY (telephone, question)
                )
            """)

            # ------------------------------------------------
            # Conversations
            # ------------------------------------------------

            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    owner TEXT NOT NULL,
                    titre TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conv_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conv
                ON messages(conv_id, created_at)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_state (
                    conv_id TEXT PRIMARY KEY,
                    subject TEXT,
                    objective TEXT,
                    intent TEXT,
                    mode TEXT,
                    entities_json TEXT,
                    constraints_json TEXT,
                    pending_question TEXT,
                    updated_at TEXT
                )
            """)

            # ------------------------------------------------
            # Mémoire utilisateur
            # ------------------------------------------------

            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner TEXT NOT NULL,
                    memory_key TEXT NOT NULL,
                    memory_value TEXT NOT NULL,
                    category TEXT DEFAULT 'user',
                    confidence REAL DEFAULT 0.7,
                    importance REAL DEFAULT 0.5,
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(owner, memory_key)
                )
            """)

            # ------------------------------------------------
            # Mémoire épisodique
            # ------------------------------------------------

            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodic_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance REAL DEFAULT 0.5,
                    created_at TEXT
                )
            """)

            # ------------------------------------------------
            # Mémoire des erreurs
            # ------------------------------------------------

            conn.execute("""
                CREATE TABLE IF NOT EXISTS error_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner TEXT,
                    error_type TEXT NOT NULL,
                    question TEXT,
                    bad_answer TEXT,
                    expected_mode TEXT,
                    actual_mode TEXT,
                    cause TEXT,
                    correction TEXT,
                    confidence REAL DEFAULT 0.7,
                    created_at TEXT
                )
            """)

            # ------------------------------------------------
            # Apprentissage
            # ------------------------------------------------

            conn.execute("""
                CREATE TABLE IF NOT EXISTS learning_examples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner TEXT,
                    question TEXT NOT NULL,
                    intent TEXT,
                    context_json TEXT,
                    candidate TEXT,
                    approved_answer TEXT,
                    source TEXT,
                    quality REAL DEFAULT 0.5,
                    uses INTEGER DEFAULT 0,
                    created_at TEXT
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_learning_intent
                ON learning_examples(intent)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS response_corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner TEXT,
                    question TEXT NOT NULL,
                    bad_answer TEXT,
                    good_answer TEXT,
                    reason TEXT,
                    intent TEXT,
                    created_at TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS intent_examples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phrase TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    confidence REAL DEFAULT 0.7,
                    source TEXT DEFAULT 'learned',
                    created_at TEXT
                )
            """)

            # ------------------------------------------------
            # Contradictions
            # ------------------------------------------------

            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_conflicts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL,
                    information_a TEXT NOT NULL,
                    information_b TEXT NOT NULL,
                    source_a TEXT,
                    source_b TEXT,
                    date_a TEXT,
                    date_b TEXT,
                    confidence_a REAL,
                    confidence_b REAL,
                    status TEXT DEFAULT 'unresolved',
                    created_at TEXT
                )
            """)

            # ------------------------------------------------
            # Avis / feedback
            # ------------------------------------------------

            conn.execute("""
                CREATE TABLE IF NOT EXISTS avis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telephone TEXT,
                    question TEXT,
                    reponse TEXT,
                    satisfait INTEGER,
                    motif TEXT,
                    commentaire TEXT,
                    cree_le TEXT
                )
            """)

            # ------------------------------------------------
            # Plateforme
            # ------------------------------------------------

            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    owner TEXT NOT NULL,
                    nom TEXT NOT NULL,
                    objectif TEXT,
                    statut TEXT DEFAULT 'actif',
                    progression INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    owner TEXT NOT NULL,
                    titre TEXT NOT NULL,
                    statut TEXT DEFAULT 'a_faire',
                    echeance TEXT,
                    created_at TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    owner TEXT NOT NULL,
                    type TEXT NOT NULL,
                    titre TEXT NOT NULL,
                    message TEXT NOT NULL,
                    lu INTEGER DEFAULT 0,
                    created_at TEXT
                )
            """)

            # ------------------------------------------------
            # Événements / audit
            # ------------------------------------------------

            conn.execute("""
                CREATE TABLE IF NOT EXISTS events_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    payload TEXT,
                    created_at TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS actions_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    action TEXT,
                    objet TEXT,
                    resultat TEXT,
                    permission TEXT,
                    created_at TEXT
                )
            """)

            conn.commit()

        finally:
            conn.close()


init_db()


# ============================================================
# 7. EVENT BUS
# ============================================================

class EventBus:

    def __init__(self):
        self.listeners = []
        self.lock = threading.RLock()

    def subscribe(self, callback):
        with self.lock:
            if callback not in self.listeners:
                self.listeners.append(callback)

    def unsubscribe(self, callback):
        with self.lock:
            if callback in self.listeners:
                self.listeners.remove(callback)

    def emit(self, event_type: str, payload: Dict[str, Any]):
        event = {
            "type": event_type,
            "payload": payload,
            "created_at": maintenant()
        }

        with DB_LOCK:
            conn = connexion_db()

            try:
                conn.execute(
                    """
                    INSERT INTO events_log(type, payload, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (
                        event_type,
                        json_safe(payload),
                        event["created_at"]
                    )
                )

                conn.commit()

            finally:
                conn.close()

        with self.lock:
            listeners = list(self.listeners)

        for listener in listeners:
            try:
                listener(event)
            except Exception:
                pass


BUS = EventBus()


# ============================================================
# 8. MÉMOIRE DES CONVERSATIONS
# ============================================================

def creer_conversation(owner: str = "anon") -> str:
    conv_id = str(uuid.uuid4())
    now = maintenant()

    with DB_LOCK:
        conn = connexion_db()

        try:
            conn.execute(
                """
                INSERT INTO conversations
                (id, owner, titre, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    conv_id,
                    owner,
                    "Nouvelle conversation",
                    now,
                    now
                )
            )

            conn.execute(
                """
                INSERT INTO conversation_state
                (conv_id, subject, objective, intent, mode,
                 entities_json, constraints_json,
                 pending_question, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conv_id,
                    "",
                    "",
                    "",
                    "",
                    "[]",
                    "[]",
                    "",
                    now
                )
            )

            conn.commit()

        finally:
            conn.close()

    return conv_id


def verifier_conversation(conv_id: Optional[str], owner: str) -> str:
    if not conv_id:
        return creer_conversation(owner)

    with DB_LOCK:
        conn = connexion_db()

        try:
            row = conn.execute(
                """
                SELECT id
                FROM conversations
                WHERE id = ? AND owner = ?
                """,
                (conv_id, owner)
            ).fetchone()

        finally:
            conn.close()

    if row:
        return conv_id

    return creer_conversation(owner)


def enregistrer_message(
    conv_id: str,
    role: str,
    content: str
):
    content = normaliser_texte(content)

    if not content:
        return

    message_id = str(uuid.uuid4())
    now = maintenant()

    with DB_LOCK:
        conn = connexion_db()

        try:
            conn.execute(
                """
                INSERT INTO messages
                (id, conv_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    conv_id,
                    role,
                    content,
                    now
                )
            )

            conn.execute(
                """
                UPDATE conversations
                SET updated_at = ?
                WHERE id = ?
                """,
                (now, conv_id)
            )

            conn.commit()

        finally:
            conn.close()


def derniers_messages(
    conv_id: str,
    limit: 
