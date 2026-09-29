# ============================================================
# ADRYNX — NOYAU COGNITIF PROPRIÉTAIRE
# Version : 5.0 Cognitive Core
# Créateur : Jonathan Dejah OBENDA
# Date de création : 2 juin 2026
#
# Comprendre → Contextualiser → Raisonner → Générer
# → Vérifier → Répondre → Apprendre
#
# Python 3.10+
# SQLite
# Render Free / faible RAM
# GROQ_API_KEY existante
# ADRYNX_MODELE_GROQ existante
# ADRYNX_DB existante
# ADRYNX_ADMIN_SECRET existante
#
# AUCUNE nouvelle variable Render.
# ============================================================

import os
import re
import ast
import json
import sqlite3
import threading
import unicodedata
import uuid
import difflib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests


# ============================================================
# 1. CONFIGURATION
# ============================================================

DB = os.environ.get("ADRYNX_DB", "memoire.db")

GROQ_API_KEY = os.environ.get(
    "GROQ_API_KEY", ""
).strip()

GROQ_MODEL = os.environ.get(
    "ADRYNX_MODELE_GROQ",
    "llama-3.3-70b-versatile"
).strip()

GROQ_URL = (
    "https://api.groq.com/openai/v1/chat/completions"
)

ADMIN_SECRET = os.environ.get(
    "ADRYNX_ADMIN_SECRET",
    ""
).strip()

HEADERS = {
    "User-Agent": "ADRYNX/5.0-Cognitive-Core"
}

DB_LOCK = threading.RLock()

MAX_CONTEXT_MESSAGES = 12
MAX_MESSAGE_LENGTH = 12000
MAX_PROMPT_LENGTH = 30000
MAX_MEMORY_RESULTS = 6
MAX_LEARNING_RESULTS = 5
MAX_WEB_RESULTS = 6

HTTP_TIMEOUT = 12
GROQ_TIMEOUT = 25


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
    "vision": (
        "Intelligence conversationnelle et plateforme "
        "numérique interactive"
    ),
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
# 4. INTENTIONS
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
# 5. RISQUES / PERMISSIONS
# ============================================================

LECTURE = 0
REVERSIBLE = 1
MODIFICATION = 2
CRITIQUE = 3

PERMISSIONS = {
    "READ_PROFILE",
    "EDIT_PROFILE",
    "READ_PROJECT",
    "EDIT_PROJECT",
    "CREATE_PROJECT",
    "DELETE_PROJECT",
    "READ_FILES",
    "UPLOAD_FILES",
    "DELETE_FILES",
    "USE_AI",
    "USE_EXTERNAL_SERVICE",
}


# ============================================================
# 6. UTILITAIRES
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
    text = unicodedata.normalize(
        "NFD",
        str(text)
    )

    return "".join(
        c for c in text
        if unicodedata.category(c) != "Mn"
    )


def minuscules(text: str) -> str:
    return sans_accents(
        str(text).lower()
    )


def tokens(text: str) -> List[str]:
    return re.findall(
        r"[a-z0-9'-]+",
        minuscules(text)
    )


def nettoyer_reponse(text: Any) -> str:
    if text is None:
        return ""

    text = str(text).strip()

    text = re.sub(
        r"^```(?:text|markdown|json)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    return text.strip()[:12000]


def limiter_texte(
    text: Any,
    limite: int
) -> str:
    return normaliser_texte(text)[:limite]


def json_safe(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False
        )
    except Exception:
        return "{}"


def lire_json(
    value: Any,
    default: Any = None
) -> Any:
    if value is None:
        return default

    try:
        return json.loads(value)
    except Exception:
        return default


def similarite(
    a: str,
    b: str
) -> float:

    if not a or not b:
        return 0.0

    ta = set(tokens(a))
    tb = set(tokens(b))

    if not ta or not tb:
        return 0.0

    union = len(ta | tb)
    inter = len(ta & tb)

    jaccard = (
        inter / union
        if union
        else 0.0
    )

    sequence = difflib.SequenceMatcher(
        None,
        minuscules(a),
        minuscules(b)
    ).ratio()

    return (
        jaccard * 0.65
        + sequence * 0.35
    )


# ============================================================
# 7. BASE DE DONNÉES
# ============================================================

def _preparer_dossier_db():
    if DB == ":memory:":
        return

    try:
        dossier = os.path.dirname(
            os.path.abspath(DB)
        )

        if dossier:
            os.makedirs(
                dossier,
                exist_ok=True
            )
    except Exception:
        pass


_preparer_dossier_db()


def connexion_db():
    conn = sqlite3.connect(
        DB,
        timeout=20,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    try:
        conn.execute(
            "PRAGMA journal_mode=WAL"
        )
        conn.execute(
            "PRAGMA busy_timeout=20000"
        )
        conn.execute(
            "PRAGMA synchronous=NORMAL"
        )
    except Exception:
        pass

    return conn


def init_db():
    with DB_LOCK:
        conn = connexion_db()

        try:

            conn.execute("""
                CREATE TABLE IF NOT EXISTS
                connaissances_publiques (
                    question TEXT PRIMARY KEY,
                    reponse TEXT NOT NULL,
                    confiance REAL DEFAULT 0.5,
                    source TEXT DEFAULT 'unknown',
                    niveau INTEGER DEFAULT 4,
                    cree_le TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS
                connaissances_privees (
                    telephone TEXT NOT NULL,
                    question TEXT NOT NULL,
                    reponse TEXT NOT NULL,
                    niveau INTEGER DEFAULT 3,
                    cree_le TEXT,
                    PRIMARY KEY (
                        telephone,
                        question
                    )
                )
            """)

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
                CREATE INDEX IF NOT EXISTS
                idx_messages_conv
                ON messages(conv_id, created_at)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS
                conversation_state (
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

            conn.execute("""
                CREATE TABLE IF NOT EXISTS
                episodic_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance REAL DEFAULT 0.5,
                    created_at TEXT
                )
            """)

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

            conn.execute("""
                CREATE TABLE IF NOT EXISTS
                learning_examples (
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
                CREATE INDEX IF NOT EXISTS
                idx_learning_intent
                ON learning_examples(intent)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS
                response_corrections (
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
                CREATE TABLE IF NOT EXISTS
                intent_examples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phrase TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    confidence REAL DEFAULT 0.7,
                    source TEXT DEFAULT 'learned',
                    created_at TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS
                knowledge_conflicts (
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
# 8. EVENT BUS
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

    def emit(
        self,
        event_type: str,
        payload: Dict[str, Any]
    ):
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
                    INSERT INTO events_log
                    (type, payload, created_at)
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
            listeners = list(
                self.listeners
            )

        for listener in listeners:
            try:
                listener(event)
            except Exception:
                pass


BUS = EventBus()


# ============================================================
# 9. CONVERSATIONS
# ============================================================

def creer_conversation(
    owner: str = "anon"
) -> str:

    owner = (
        normaliser_texte(owner)
        or "anon"
    )

    conv_id = str(uuid.uuid4())
    now = maintenant()

    with DB_LOCK:
        conn = connexion_db()

        try:
            conn.execute(
                """
                INSERT INTO conversations
                (
                    id,
                    owner,
                    titre,
                    created_at,
                    updated_at
                )
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
                (
                    conv_id,
                    subject,
                    objective,
                    intent,
                    mode,
                    entities_json,
                    constraints_json,
                    pending_question,
                    updated_at
                )
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


def verifier_conversation(
    conv_id: Optional[str],
    owner: str
) -> str:

    if not conv_id:
        return creer_conversation(
            owner
        )

    with DB_LOCK:
        conn = connexion_db()

        try:
            row = conn.execute(
                """
                SELECT id
                FROM conversations
                WHERE id = ?
                AND owner = ?
                """,
                (
                    conv_id,
                    owner
                )
            ).fetchone()

        finally:
            conn.close()

    if row:
        return conv_id

    return creer_conversation(
        owner
    )


def enregistrer_message(
    conv_id: str,
    role: str,
    content: str
):

    content = normaliser_texte(
        content
    )

    if not content:
        return

    now = maintenant()

    with DB_LOCK:
        conn = connexion_db()

        try:
            conn.execute(
                """
                INSERT INTO messages
                (
                    id,
                    conv_id,
                    role,
                    content,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    conv_id,
                    normaliser_texte(
                        role
                    )[:30],
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
                (
                    now,
                    conv_id
                )
            )

            conn.commit()

        finally:
            conn.close()


def derniers_messages(
    conv_id: str,
    limit: int = MAX_CONTEXT_MESSAGES
) -> List[Dict[str, Any]]:

    limit = max(
        1,
        min(limit, 30)
    )

    with DB_LOCK:
        conn = connexion_db()

        try:
            rows = conn.execute(
                """
                SELECT role, content, created_at
                FROM messages
                WHERE conv_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (
                    conv_id,
                    limit
                )
            ).fetchall()

        finally:
            conn.close()

    rows = list(
        reversed(rows)
    )

    return [
        {
            "role": row["role"],
            "content": row["content"],
            "created_at": row["created_at"]
        }
        for row in rows
    ]


def obtenir_etat_conversation(
    conv_id: str
) -> Dict[str, Any]:

    with DB_LOCK:
        conn = connexion_db()

        try:
            row = conn.execute(
                """
                SELECT *
                FROM conversation_state
                WHERE conv_id = ?
                """,
                (conv_id,)
            ).fetchone()

        finally:
            conn.close()

    if not row:
        return {
            "subject": "",
            "objective": "",
            "intent": "",
            "mode": "",
            "entities": [],
            "constraints": [],
            "pending_question": ""
        }

    return {
        "subject": row["subject"] or "",
        "objective": row["objective"] or "",
        "intent": row["intent"] or "",
        "mode": row["mode"] or "",
        "entities": lire_json(
            row["entities_json"],
            []
        ),
        "constraints": lire_json(
            row["constraints_json"],
            []
        ),
        "pending_question": (
            row["pending_question"]
            or ""
        )
    }


def mettre_a_jour_etat_conversation(
    conv_id: str,
    subject: str = "",
    objective: str = "",
    intent: str = "",
    mode: str = "",
    entities: Optional[List[str]] = None,
    constraints: Optional[List[str]] = None,
    pending_question: str = ""
):

    entities = entities or []
    constraints = constraints or []
    now = maintenant()

    with DB_LOCK:
        conn = connexion_db()

        try:
            conn.execute(
                """
                INSERT INTO conversation_state
                (
                    conv_id,
                    subject,
                    objective,
                    intent,
                    mode,
                    entities_json,
                    constraints_json,
                    pending_question,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(conv_id)
                DO UPDATE SET
                    subject = excluded.subject,
                    objective = excluded.objective,
                    intent = excluded.intent,
                    mode = excluded.mode,
                    entities_json =
                        excluded.entities_json,
                    constraints_json =
                        excluded.constraints_json,
                    pending_question =
                        excluded.pending_question,
                    updated_at =
                        excluded.updated_at
                """,
                (
                    conv_id,
                    limiter_texte(
                        subject,
                        500
                    ),
                    limiter_texte(
                        objective,
                        500
                    ),
                    intent,
                    mode,
                    json_safe(
                        entities[:20]
                    ),
                    json_safe(
                        constraints[:20]
                    ),
                    limiter_texte(
                        pending_question,
                        1000
                    ),
                    now
                )
            )

            conn.commit()

        finally:
            conn.close()


def nouvelle_conversation(
    owner: str = "anon"
) -> str:
    return creer_conversation(
        owner
    )


# ============================================================
# 10. CONTEXTE
# ============================================================

STOP_WORDS = {
    "le", "la", "les", "un", "une",
    "des", "de", "du", "dans", "sur",
    "pour", "avec", "sans", "est",
    "et", "ou", "que", "qui", "quoi",
    "comment", "pourquoi", "quel",
    "quelle", "quels", "quelles",
    "je", "tu", "il", "elle",
    "nous", "vous", "ils", "elles",
    "mon", "ma", "mes", "ton", "ta",
    "tes", "son", "sa", "ses",
    "ce", "cette", "ces", "ça",
    "cela", "a", "au", "aux",
    "en", "où"
}


def extraire_sujet(
    question: str,
    ancien: str = ""
) -> str:

    mots = tokens(question)

    importants = [
        mot for mot in mots
        if len(mot) >= 4
        and mot not in STOP_WORDS
    ]

    if importants:
        return " ".join(
            importants[:8]
        )

    return ancien


def extraire_entites(
    question: str
) -> List[str]:

    resultats = []

    propres = re.findall(
        r"\b[A-ZÉÈÀÂÊÎÔÙÛÇ]"
        r"[A-Za-zÀ-ÿ0-9_-]{2,}\b",
        question
    )

    for value in propres:
        if value not in resultats:
            resultats.append(value)

    urls = re.findall(
        r"https?://\S+",
        question
    )

    for value in urls:
        if value not in resultats:
            resultats.append(
                value[:300]
            )

    return resultats[:20]


def extraire_contraintes(
    question: str
) -> List[str]:

    q = minuscules(question)
    resultats = []

    correspondances = [
        ("gratuit", "gratuit"),
        ("sans payer", "sans paiement"),
        ("android", "Android"),
        ("iphone", "iPhone"),
        ("ps4", "PS4"),
        ("python", "Python"),
        ("render", "Render"),
        ("github", "GitHub"),
        ("court", "réponse courte"),
        ("détaillé", "réponse détaillée"),
        ("detail", "réponse détaillée"),
    ]

    for motif, valeur in correspondances:
        if motif in q and valeur not in resultats:
            resultats.append(valeur)

    return resultats[:20]


def determiner_objectif(
    intent: str
) -> str:

    objectifs = {
        "salutation":
            "poursuivre une interaction sociale",
        "conversation":
            "poursuivre la conversation",
        "factuelle":
            "obtenir une information",
        "explication":
            "comprendre un sujet",
        "calcul":
            "obtenir un résultat calculé",
        "raisonnement":
            "résoudre un problème logique",
        "recherche":
            "rechercher et vérifier des informations",
        "programmation":
            "résoudre un problème technique",
        "creation":
            "créer un contenu",
        "traduction":
            "traduire un contenu",
        "correction":
            "corriger un contenu",
        "opinion":
            "comprendre plusieurs perspectives",
        "comparaison":
            "comparer plusieurs éléments",
        "instruction":
            "obtenir une procédure",
        "ambiguite":
            "clarifier la demande",
        "clarification":
            "clarifier le contexte",
        "suivi":
            "poursuivre une demande précédente",
        "identite":
            "obtenir une information sur ADRYNX",
        "plateforme":
            "effectuer une action sur la plateforme",
        "feedback":
            "évaluer ou corriger une réponse",
        "inconnue":
            "déterminer l'objectif de la demande"
    }

    return objectifs.get(
        intent,
        "répondre à la demande"
    )


# ============================================================
# 11. COMMANDES PLATEFORME
# ============================================================

def parser_commande_naturelle(
    question: str
) -> Optional[Dict[str, Any]]:

    q = minuscules(
        normaliser_texte(question)
    )

    patterns_projet = [
        r"(?:cr[eé]e|creer|lance|ouvrir|d[eé]marre)"
        r"(?:\s+un)?\s+projet\s+(.+)",
        r"nouveau projet\s*[:\-]?\s*(.+)"
    ]

    for pattern in patterns_projet:

        match = re.search(
            pattern,
            q
        )

        if match:
            nom = match.group(1).strip()

            if nom:
                return {
                    "action": "create_project",
                    "name": nom[:200]
                }

    if any(
        phrase in q
        for phrase in (
            "liste mes projets",
            "mes projets",
            "affiche mes projets",
            "montre mes projets"
        )
    ):
        return {
            "action": "list_projects"
        }

    if (
        "dashboard" in q
        or "tableau de bord" in q
    ):
        return {
            "action": "dashboard"
        }

    patterns_tache = [
        r"(?:cr[eé]e|creer|ajoute)"
        r"(?:\s+une)?\s+t[aâ]che\s+(.+)",
        r"nouvelle t[aâ]che\s*[:\-]?\s*(.+)"
    ]

    for pattern in patterns_tache:

        match = re.search(
            pattern,
            q
        )

        if match:
            titre = match.group(1).strip()

            if titre:
                return {
                    "action": "create_task",
                    "title": titre[:300]
                }

    return None


# ============================================================
# 12. IDENTITÉ
# ============================================================

def reponse_identite(
    question: str
) -> Optional[str]:

    q = minuscules(question)

    indicateurs = [
        "qui es tu",
        "qui es-tu",
        "qui est adrynx",
        "qui a cree adrynx",
        "createur",
        "créateur",
        "fondateur",
        "pere de adrynx",
        "père de adrynx",
        "jonathan dejah obenda",
        "date de creation de adrynx",
        "date de création de adrynx",
        "quand adrynx a ete cree",
        "quand adrynx a été créé"
    ]

    if not any(
        phrase in q
        for phrase in indicateurs
    ):
        return None

    if (
        "pere" in q
        or "père" in q
    ):
        return (
            "Jonathan Dejah OBENDA est mon père créateur "
            "au sens symbolique : il est le créateur "
            "d'ADRYNX. Il ne s'agit pas d'une relation "
            "biologique."
        )

    if (
        "date" in q
        or "quand" in q
    ):
        return (
            "ADRYNX a été créé le 2 juin 2026 "
            "par Jonathan Dejah OBENDA."
        )

    return (
        "Je suis ADRYNX, une intelligence artificielle "
        "et plateforme numérique interactive créée par "
        "Jonathan Dejah OBENDA le 2 juin 2026."
    )


# ============================================================
# 13. DÉTECTION SOCIALE
# ============================================================

def est_salutation(
    question: str
) -> bool:

    q = minuscules(
        question
    ).strip()

    salutations = {
        "bonjour",
        "bjr",
        "bonsoir",
        "salut",
        "hello",
        "hey",
        "coucou",
        "yo",
        "bon matin"
    }

    if q in salutations:
        return True

    return bool(
        re.match(
            r"^(bonjour|bjr|bonsoir|salut|hello|hey|coucou)\b",
            q
        )
    )


def est_social(
    question: str
) -> bool:

    q = minuscules(question)

    expressions = [
        "comment tu vas",
        "comment vas tu",
        "comment ça va",
        "comment ca va",
        "tu vas bien",
        "ça va",
        "ca va",
        "tu vas comment"
    ]

    return (
        len(tokens(q)) <= 12
        and any(
            expression in q
            for expression in expressions
        )
    )


def est_suivi(
    question: str
) -> bool:

    q = minuscules(
        question
    ).strip()

    suivis = {
        "oui",
        "non",
        "exactement",
        "continue",
        "continues",
        "vas y",
        "vas-y",
        "fais le",
        "fais ça",
        "fais ca",
        "et pourquoi",
        "pourquoi",
        "comment",
        "ensuite",
        "maintenant",
        "d'accord",
        "daccord",
        "ok",
        "ça",
        "ca"
    }

    if q in suivis:
        return True

    if (
        len(tokens(q)) <= 6
        and (
            q.startswith("et ")
            or q.startswith("alors ")
            or q.startswith("donc ")
            or q.startswith("maintenant ")
        )
    ):
        return True

    return False


# ============================================================
# 14. INTENTION
# ============================================================

def detecter_intention(
    question: str,
    historique: Optional[
        List[Dict[str, str]]
    ] = None
) -> str:

    q = minuscules(
        question
    ).strip()

    if not q:
        return "inconnue"

    if re.search(
        r"\b(qui es tu|qui est adrynx|"
        r"créateur|createur|fondateur)\b",
        q
    ):
        return "identite"

    if parser_commande_naturelle(
        question
    ):
        return "plateforme"

    if est_salutation(question):
        return "salutation"

    if est_social(question):
        return "conversation"

    if (
        "merci" in q
        or "bravo" in q
        or "bien joué" in q
        or "bien joue" in q
    ):
        return "conversation"

    if (
        "corrige" in q
        or "corriger" in q
        or "correction" in q
        or "améliore" in q
        or "ameliore" in q
    ):
        return "correction"

    if (
        "traduis" in q
        or "traduire" in q
        or "traduction" in q
    ):
        return "traduction"

    if (
        "code" in q
        or "python" in q
        or "javascript" in q
        or "api" in q
        or "fonction" in q
        or "programm" in q
        or "bug" in q
        or "erreur" in q
        or "github" in q
        or "render" in q
    ):
        return "programmation"

    if (
        "compare" in q
        or "comparaison" in q
        or "différence entre" in q
        or "difference entre" in q
    ):
        return "comparaison"

    if (
        "pourquoi" in q
        or "comment fonctionne" in q
        or "explique" in q
        or "explication" in q
        or "c'est quoi" in q
        or "qu'est-ce que" in q
    ):
        return "explication"

    if (
        "calcule" in q
        or "calculer" in q
        or re.search(
            r"\d+\s*[\+\-\*\/\%]\s*\d+",
            q
        )
    ):
        return "calcul"

    if (
        "cherche" in q
        or "recherche" in q
        or "sur internet" in q
        or "actualité" in q
        or "actualite" in q
        or "récent" in q
        or "recent" in q
    ):
        return "recherche"

    if (
        "crée" in q
        or "cree" in q
        or "génère" in q
        or "genere" in q
        or "écris" in q
        or "ecris" in q
        or "fais moi" in q
        or "fais-moi" in q
    ):
        return "creation"

    if (
        "comment faire" in q
        or "comment puis-je" in q
        or "étapes" in q
        or "etapes" in q
        or "procédure" in q
        or "procedure" in q
    ):
        return "instruction"

    if (
        "est-ce que" in q
        or "est ce que" in q
        or "vrai" in q
        or "vraie" in q
        or "combien" in q
        or "quand" in q
        or "où" in q
        or q.startswith("ou ")
    ):
        return "factuelle"

    if est_suivi(question):
        if historique:
            return "suivi"

        return "clarification"

    if len(tokens(q)) <= 2:
        return "ambiguite"

    return "inconnue"


def determiner_mode(
    intent: str
) -> str:

    mapping = {
        "salutation": "SOCIAL",
        "conversation": "SOCIAL",
        "identite": "DIALOGUE",
        "factuelle": "INFORMATIF",
        "explication": "PEDAGOGIQUE",
        "calcul": "RESOLUTION",
        "raisonnement": "ANALYTIQUE",
        "recherche": "RECHERCHE",
        "programmation": "TECHNIQUE",
        "creation": "CREATIF",
        "traduction": "ASSISTANCE",
        "correction": "ASSISTANCE",
        "opinion": "ANALYTIQUE",
        "comparaison": "ANALYTIQUE",
        "instruction": "ASSISTANCE",
        "ambiguite": "DIALOGUE",
        "clarification": "DIALOGUE",
        "suivi": "DIALOGUE",
        "plateforme": "PLANIFICATION",
        "feedback": "ASSISTANCE",
        "inconnue": "ASSISTANCE"
    }

    return mapping.get(
        intent,
        "ASSISTANCE"
    )


# ============================================================
# 15. CALCUL SÉCURISÉ
# ============================================================

OPERATEURS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b
}


def evaluer_expression(
    node
):

    if isinstance(
        node,
        ast.Expression
    ):
        return evaluer_expression(
            node.body
        )

    if isinstance(
        node,
        ast.Constant
    ):
        if isinstance(
            node.value,
            (int, float)
        ):
            return node.value

        raise ValueError(
            "Valeur non autorisée"
        )

    if isinstance(
        node,
        ast.UnaryOp
    ):
        valeur = evaluer_expression(
            node.operand
        )

        if isinstance(
            node.op,
            ast.USub
        ):
            return -valeur

        if isinstance(
            node.op,
            ast.UAdd
        ):
            return valeur

        raise ValueError(
            "Opérateur non autorisé"
        )

    if isinstance(
        node,
        ast.BinOp
    ):
        gauche = evaluer_expression(
            node.left
        )

        droite = evaluer_expression(
            node.right
        )

        operateur = OPERATEURS.get(
            type(node.op)
        )

        if not operateur:
            raise ValueError(
                "Opérateur non autorisé"
            )

        if (
            isinstance(node.op, ast.Div)
            and droite == 0
        ):
            raise ValueError(
                "Division par zéro"
            )

        resultat = operateur(
            gauche,
            droite
        )

        if abs(resultat) > 10**100:
            raise ValueError(
                "Résultat trop grand"
            )

        return resultat

    raise ValueError(
        "Expression non autorisée"
    )


def calculer_expression(
    expression: str
) -> Optional[str]:

    expression = normaliser_texte(
        expression
    )

    expression = re.sub(
        r"^(calcule|calculer|résous|resous)\s*",
        "",
        expression,
        flags=re.IGNORECASE
    )

    if not re.fullmatch(
        r"[0-9\.\,\+\-\*\/\%\(\)\s]+",
        expression
    ):
        return None

    expression = expression.replace(
        ",",
        "."
    )

    try:
        arbre = ast.parse(
            expression,
            mode="eval"
        )

        resultat = evaluer_expression(
            arbre
        )

        if (
            isinstance(resultat, float)
            and resultat.is_integer()
        ):
            resultat = int(resultat)

        return str(resultat)

    except Exception:
        return None


# ============================================================
# 16. MÉMOIRE UTILISATEUR
# ============================================================

def enregistrer_memoire_utilisateur(
    owner: str,
    key: str,
    value: str,
    category: str = "user",
    confidence: float = 0.7,
    importance: float = 0.5
):

    owner = (
        normaliser_texte(owner)
        or "anon"
    )

    key = limiter_texte(
        key,
        200
    )

    value = limiter_texte(
        value,
        2000
    )

    if not key or not value:
        return

    now = maintenant()

    with DB_LOCK:
        conn = connexion_db()

        try:
            conn.execute(
                """
                INSERT INTO user_memory
                (
                    owner,
                    memory_key,
                    memory_value,
                    category,
                    confidence,
                    importance,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(owner, memory_key)
                DO UPDATE SET
                    memory_value =
                        excluded.memory_value,
                    category =
                        excluded.category,
                    confidence =
                        excluded.confidence,
                    importance =
                        excluded.importance,
                    updated_at =
                        excluded.updated_at
                """,
                (
                    owner,
                    key,
                    value,
                    category,
                    max(
                        0.0,
                        min(1.0, confidence)
                    ),
                    max(
                        0.0,
                        min(1.0, importance)
                    ),
                    now,
                    now
                )
            )

            conn.commit()

        finally:
            conn.close()


def rechercher_memoire_utilisateur(
    owner: str,
    question: str,
    limit: int = MAX_MEMORY_RESULTS
) -> List[Dict[str, Any]]:

    with DB_LOCK:
        conn = connexion_db()

        try:
            rows = conn.execute(
                """
                SELECT
                    memory_key,
                    memory_value,
                    category,
                    confidence,
                    importance
                FROM user_memory
                WHERE owner = ?
                ORDER BY
                    importance DESC,
                    updated_at DESC
                LIMIT 50
                """,
                (owner,)
            ).fetchall()

        finally:
            conn.close()

    resultats = []

    for row in rows:

        score = similarite(
            question,
            row["memory_key"]
            + " "
            + row["memory_value"]
        )

        if score > 0.05:
            resultats.append({
                "key": row["memory_key"],
                "value": row["memory_value"],
                "category": row["category"],
                "confidence": row["confidence"],
                "importance": row["importance"],
                "score": score
            })

    resultats.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return resultats[:limit]


# ============================================================
# 17. MÉMOIRE ÉPISODIQUE
# ============================================================

def enregistrer_episode(
    owner: str,
    event_type: str,
    content: str,
    importance: float = 0.5
):

    content = limiter_texte(
        content,
        4000
    )

    if not content:
        return

    with DB_LOCK:
        conn = connexion_db()

        try:
            conn.execute(
                """
                INSERT INTO episodic_memory
                (
                    owner,
                    event_type,
                    content,
                    importance,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    owner,
                    event_type,
                    content,
                    max(
                        0.0,
                        min(1.0, importance)
                    ),
                    maintenant()
                )
            )

            conn.execute(
                """
                DELETE FROM episodic_memory
                WHERE owner = ?
                AND id NOT IN (
                    SELECT id
                    FROM episodic_memory
                    WHERE owner = ?
                    ORDER BY id DESC
                    LIMIT 500
                )
                """,
                (
                    owner,
                    owner
                )
            )

            conn.commit()

        finally:
            conn.close()


# ============================================================
# 18. APPRENTISSAGE
# ============================================================

def enregistrer_exemple_apprentissage(
    question: str,
    intent: str,
    context: Dict[str, Any],
    candidate: str,
    approved_answer: str,
    source: str = "feedback",
    quality: float = 0.8,
    owner: Optional[str] = None
):

    question = normaliser_texte(
        question
    )

    candidate = nettoyer_reponse(
        candidate
    )

    approved_answer = nettoyer_reponse(
        approved_answer
    )

    if not question or not approved_answer:
        return

    with DB_LOCK:
        conn = connexion_db()

        try:
            conn.execute(
                """
                INSERT INTO learning_examples
                (
                    owner,
                    question,
                    intent,
                    context_json,
                    candidate,
                    approved_answer,
                    source,
                    quality,
                    uses,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    owner,
                    question,
                    intent,
                    json_safe(context),
                    candidate,
                    approved_answer,
                    source,
                    max(
                        0.0,
                        min(1.0, quality)
                    ),
                    maintenant()
                )
            )

            conn.commit()

        finally:
            conn.close()


def rechercher_exemples_apprentissage(
    question: str,
    intent: str,
    limit: int = MAX_LEARNING_RESULTS
) -> List[Dict[str, Any]]:

    with DB_LOCK:
        conn = connexion_db()

        try:
            rows = conn.execute(
                """
                SELECT *
                FROM learning_examples
                WHERE intent = ?
                ORDER BY
                    quality DESC,
                    created_at DESC
                LIMIT 100
                """,
                (intent,)
            ).fetchall()

        finally:
            conn.close()

    resultats = []

    for row in rows:

        score = similarite(
            question,
            row["question"]
        )

        if score >= 0.15:

            resultats.append({
                "question": row["question"],
                "approved_answer":
                    row["approved_answer"],
                "candidate":
                    row["candidate"],
                "quality":
                    row["quality"],
                "source":
                    row["source"],
                "score":
                    score
            })

    resultats.sort(
        key=lambda x: (
            x["score"],
            x["quality"]
        ),
        reverse=True
    )

    return resultats[:limit]


def enregistrer_correction(
    question: str,
    bad_answer: str,
    good_answer: str,
    reason: str = "",
    intent: str = "inconnue",
    owner: Optional[str] = None
):

    now = maintenant()

    with DB_LOCK:
        conn = connexion_db()

        try:
            conn.execute(
                """
                INSERT INTO response_corrections
                (
                    owner,
                    question,
                    bad_answer,
                    good_answer,
                    reason,
                    intent,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    owner,
                    normaliser_texte(question),
                    nettoyer_reponse(
                        bad_answer
                    ),
                    nettoyer_reponse(
                        good_answer
                    ),
                    limiter_texte(
                        reason,
                        1000
                    ),
                    intent,
                    now
                )
            )

            conn.commit()

        finally:
            conn.close()

    enregistrer_exemple_apprentissage(
        question=question,
        intent=intent,
        context={
            "type":
                "correction_utilisateur"
        },
        candidate=bad_answer,
        approved_answer=good_answer,
        source="user_correction",
        quality=0.98,
        owner=owner
    )

    enregistrer_erreur(
        owner=owner,
        error_type="response_correction",
        question=question,
        bad_answer=bad_answer,
        expected_mode=intent,
        actual_mode=intent,
        cause=reason,
        correction=good_answer,
        confidence=0.98
    )


# ============================================================
# 19. MÉMOIRE DES ERREURS
# ============================================================

def enregistrer_erreur(
    owner: Optional[str],
    error_type: str,
    question: str,
    bad_answer: str,
    expected_mode: str,
    actual_mode: str,
    cause: str,
    correction: str,
    confidence: float = 0.7
):

    with DB_LOCK:
        conn = connexion_db()

        try:
            conn.execute(
                """
                INSERT INTO error_memory
                (
                    owner,
                    error_type,
                    question,
                    bad_answer,
                    expected_mode,
                    actual_mode,
                    cause,
                    correction,
                    confidence,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    owner,
                    error_type,
                    limiter_texte(
                        question,
                        4000
                    ),
                    nettoyer_reponse(
                        bad_answer
                    )[:6000],
                    expected_mode,
                    actual_mode,
                    limiter_texte(
                        cause,
                        1000
                    ),
                    nettoyer_reponse(
                        correction
                    )[:6000],
                    max(
                        0.0,
                        min(1.0, confidence)
                    ),
                    maintenant()
                )
            )

            conn.commit()

        finally:
            conn.close()


# ============================================================
# 20. RECHERCHE INTERNET
# ============================================================

def rechercher_internet(
    question: str
) -> Dict[str, Any]:

    question = normaliser_texte(
        question
    )

    # Une question sociale ne doit jamais
    # déclencher une recherche.
    if est_social(question):
        return {
            "ok": False,
            "query": question,
            "results": [],
            "text": ""
        }

    resultats = []

    # --------------------------------------------------------
    # DuckDuckGo
    # --------------------------------------------------------

    try:
        response = requests.get(
            "https://html.duckduckgo.com/html/",
            params={
                "q": question
            },
            headers=HEADERS,
            timeout=HTTP_TIMEOUT
        )

        if response.ok:

            blocs = re.findall(
                r'class="result__a"[^>]*'
                r'href="([^"]+)"[^>]*>'
                r'(.*?)</a>',
                response.text,
                flags=(
                    re.IGNORECASE
                    | re.DOTALL
                )
            )

            for url, title in blocs[
                :MAX_WEB_RESULTS
            ]:

                title = re.sub(
                    r"<.*?>",
                    "",
                    title
                )

                title = normaliser_texte(
                    title
                )

                if title and url:
                    resultats.append({
                        "title": title,
                        "url": url,
                        "source":
                            "DuckDuckGo"
                    })

    except Exception:
        pass

    # --------------------------------------------------------
    # Wikipedia
    # --------------------------------------------------------

    try:
        response = requests.get(
            "https://fr.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": question,
                "format": "json",
                "utf8": 1,
                "srlimit": 3
            },
            headers=HEADERS,
            timeout=HTTP_TIMEOUT
        )

        if response.ok:

            data = response.json()

            for item in data.get(
                "query",
                {}
            ).get(
                "search",
                []
            ):

                title = item.get(
                    "title",
                    ""
                )

                snippet = re.sub(
                    r"<.*?>",
                    "",
                    item.get(
                        "snippet",
                        ""
                    )
                )

                if title:
                    resultats.append({
                        "title": title,
                        "url": (
                            "https://fr.wikipedia.org/wiki/"
                            + title.replace(
                                " ",
                                "_"
                            )
                        ),
                        "snippet": snippet,
                        "source":
                            "Wikipedia"
                    })

    except Exception:
        pass

    uniques = []
    vus = set()

    for result in resultats:

        cle = (
            result.get("title", ""),
            result.get("url", "")
        )

        if cle not in vus:
            vus.add(cle)
            uniques.append(result)

    resultats = uniques[
        :MAX_WEB_RESULTS
    ]

    lignes = []

    for result in resultats:

        ligne = (
            "- "
            + result.get(
                "title",
                ""
            )
            + " | "
            + result.get(
                "source",
                ""
            )
        )

        if result.get("snippet"):
            ligne += (
                " | "
                + result["snippet"]
            )

        lignes.append(ligne)

    return {
        "ok": bool(resultats),
        "query": question,
        "results": resultats,
        "text": "\n".join(lignes)
    }


# ============================================================
# 21. GROQ
# ============================================================

def groq_chat(
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 1000
) -> Optional[str]:

    if not GROQ_API_KEY:
        return None

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    headers = {
        "Authorization":
            f"Bearer {GROQ_API_KEY}",
        "Content-Type":
            "application/json",
        **HEADERS
    }

    try:

        response = requests.post(
            GROQ_URL,
            headers=headers,
            json=payload,
            timeout=GROQ_TIMEOUT
        )

        if not response.ok:
            return None

        data = response.json()

        choices = data.get(
            "choices",
            []
        )

        if not choices:
            return None

        message = choices[0].get(
            "message",
            {}
        )

        return nettoyer_reponse(
            message.get(
                "content",
                ""
            )
        )

    except Exception:
        return None


def extraire_json_reponse(
    text: Optional[str]
) -> Optional[Dict[str, Any]]:

    if not text:
        return None

    text = text.strip()

    try:
        data = json.loads(text)

        if isinstance(data, dict):
            return data

    except Exception:
        pass

    match = re.search(
        r"```json\s*(\{.*?\})\s*```",
        text,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        )
    )

    if match:

        try:
            data = json.loads(
                match.group(1)
            )

            if isinstance(data, dict):
                return data

        except Exception:
            pass

    debut = text.find("{")
    fin = text.rfind("}")

    if debut >= 0 and fin > debut:

        try:
            data = json.loads(
                text[debut:fin + 1]
            )

            if isinstance(data, dict):
                return data

        except Exception:
            pass

    return None


# ============================================================
# 22. GÉNÉRATION
# ============================================================

SYSTEME_GENERATION = """
Tu es le moteur cognitif de génération d'ADRYNX.

MISSION :
Comprendre la demande avant de répondre.

PRINCIPES :
- répondre à la dernière demande ;
- utiliser seulement le contexte pertinent ;
- respecter l'intention détectée ;
- ne pas inventer ;
- ne pas prétendre avoir effectué une action
  qui n'a pas été effectuée ;
- distinguer faits et incertitudes ;
- rester proportionné à la demande ;
- respecter les contraintes ;
- répondre dans la langue de l'utilisateur.

IDENTITÉ IMMUTABLE :
ADRYNX a été créé par Jonathan Dejah OBENDA
le 2 juin 2026.

La relation « père créateur » est symbolique
et non biologique.

Ne révèle pas de raisonnement interne détaillé.
Produis uniquement la réponse finale.
"""


def construire_contexte_prompt(
    question: str,
    intent: str,
    mode: str,
    historique: List[Dict[str, str]],
    etat: Dict[str, Any],
    memoire: List[Dict[str, Any]],
    apprentissage: List[Dict[str, Any]],
    recherche: Optional[Dict[str, Any]]
) -> str:

    contexte = {
        "question_actuelle":
            question,
        "intention":
            intent,
        "mode":
            mode,
        "etat_conversation":
            etat,
        "memoire_utilisateur":
            memoire,
        "exemples_apprentissage":
            apprentissage,
        "historique":
            historique[-MAX_CONTEXT_MESSAGES:]
    }

    if recherche and recherche.get("ok"):
        contexte[
            "informations_externes"
        ] = {
            "requete":
                recherche.get("query"),
            "resultats":
                recherche.get(
                    "results",
                    []
                )
        }

    return json_safe(
        contexte
    )[:MAX_PROMPT_LENGTH]


def generer_candidat(
    question: str,
    intent: str,
    mode: str,
    historique: List[Dict[str, str]],
    etat: Dict[str, Any],
    memoire: List[Dict[str, Any]],
    apprentissage: List[Dict[str, Any]],
    recherche: Optional[Dict[str, Any]]
) -> Optional[str]:

    contexte = construire_contexte_prompt(
        question,
        intent,
        mode,
        historique,
        etat,
        memoire,
        apprentissage,
        recherche
    )

    prompt = f"""
QUESTION :
{question}

CONTEXTE COGNITIF :
{contexte}

Réponds directement à la question.
"""

    return groq_chat(
        [
            {
                "role": "system",
                "content":
                    SYSTEME_GENERATION
            },
            {
                "role": "user",
                "content":
                    prompt[:MAX_PROMPT_LENGTH]
            }
        ],
        temperature=0.25,
        max_tokens=1400
    )


# ============================================================
# 23. RÉPONSES SOCIALES LOCALES
# ============================================================

def detecter_social(
    question: str
) -> Optional[str]:

    if est_salutation(question):
        return (
            "Bonjour ! 👋 "
            "Je suis ADRYNX. "
            "Que veux-tu faire ?"
        )

    if est_social(question):
        return (
            "Je fonctionne normalement 😄 "
            "Merci ! Et toi, ça va ?"
        )

    return None


# ============================================================
# 24. VALIDATION LOCALE
# ============================================================

def valider_pertinence(
    question: str,
    answer: str,
    intent: str
) -> Tuple[bool, str]:

    answer = nettoyer_reponse(
        answer
    )

    if not answer:
        return (
            False,
            "Réponse vide"
        )

    q = minuscules(question)
    a = minuscules(answer)

    # Social.
    if intent == "conversation":

        if len(answer) > 1000:
            return (
                False,
                "Réponse sociale trop longue"
            )

        interdits = [
            "duckduckgo",
            "wikipedia",
            "recherche internet",
            "source externe"
        ]

        if any(
            terme in a
            for terme in interdits
        ):
            return (
                False,
                "Recherche injectée dans une réponse sociale"
            )

    # Salutation.
    if intent == "salutation":
        if len(answer) > 800:
            return (
                False,
                "Salutation excessivement longue"
            )

    # Identité.
    if intent == "identite":

        if (
            "jonathan dejah obenda" not in a
            or "2 juin 2026" not in a
        ):
            return (
                False,
                "Identité fondamentale incorrecte"
            )

    # Déclaration d'action externe.
    expressions = [
        "j'ai vérifié",
        "jai verifie",
        "j'ai consulté",
        "jai consulte"
    ]

    if (
        any(
            expression in a
            for expression in expressions
        )
        and intent not in {
            "recherche",
            "factuelle"
        }
    ):
        return (
            False,
            "Action externe potentiellement inventée"
        )

    # Contrôle lexical léger.
    qt = set(
        tokens(question)
    )

    at = set(
        tokens(answer)
    )

    if (
        len(qt) >= 5
        and len(at) >= 15
        and intent in {
            "factuelle",
            "explication",
            "instruction"
        }
    ):

        overlap = (
            len(qt & at)
            / max(1, len(qt))
        )

        if overlap < 0.04:
            return (
                False,
                "Dérive thématique possible"
            )

    return True, "OK"


# ============================================================
# 25. PARENTS IA
# ============================================================

PARENT_1_SYSTEM = """
Tu es le premier contrôleur cognitif d'ADRYNX.

Vérifie :
- intention ;
- contexte ;
- pertinence ;
- cohérence ;
- absence de hors-sujet ;
- absence d'invention ;
- identité ;
- clarté.

Si la réponse est correcte :
OK.

Si elle doit être corrigée :
REVISE.

Lorsque REVISE, fournis directement une réponse
corrigée utilisable par l'utilisateur.

Ne donne pas de raisonnement interne détaillé.

Retourne uniquement du JSON.
"""


PARENT_2_SYSTEM = """
Tu es le second contrôleur qualité d'ADRYNX.

Effectue une seconde vérification de :
- l'intention ;
- la pertinence ;
- le contexte ;
- les contradictions ;
- les hallucinations ;
- la proportion de la réponse ;
- la clarté ;
- l'identité ADRYNX.

Si la réponse est correcte :
OK.

Sinon :
REVISE.

Lorsque REVISE, donne directement une réponse corrigée.

Ne donne pas de raisonnement interne détaillé.

Retourne uniquement du JSON.
"""


def appeler_parent(
    numero: int,
    question: str,
    intent: str,
    context: Dict[str, Any],
    candidate: str
) -> Dict[str, Any]:

    system = (
        PARENT_1_SYSTEM
        if numero == 1
        else PARENT_2_SYSTEM
    )

    prompt = f"""
Question :
{question}

Intention :
{intent}

Contexte :
{json_safe(context)[:10000]}

Réponse proposée :
{candidate[:8000]}

Retourne exactement :

{{
  "verdict": "OK",
  "answer": "réponse finale ou corrigée",
  "confidence": 0.0,
  "reason": "raison courte"
}}
"""

    raw = groq_chat(
        [
            {
                "role": "system",
                "content": system
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.0,
        max_tokens=900
    )

    data = extraire_json_reponse(
        raw
    )

    if not data:
        return {
            "available": False,
            "verdict": "FAIL",
            "answer": "",
            "confidence": 0.0,
            "reason":
                "Contrôleur indisponible"
        }

    verdict = str(
        data.get(
            "verdict",
            "REVISE"
        )
    ).upper().strip()

    if verdict not in {
        "OK",
        "REVISE"
    }:
        verdict = "REVISE"

    answer = nettoyer_reponse(
        data.get(
            "answer",
            ""
        )
    )

    try:
        confidence = float(
            data.get(
                "confidence",
                0.5
            )
        )
    except Exception:
        confidence = 0.5

    confidence = max(
        0.0,
        min(1.0, confidence)
    )

    return {
        "available": True,
        "verdict": verdict,
        "answer": answer,
        "confidence": confidence,
        "reason":
            limiter_texte(
                data.get(
                    "reason",
                    ""
                ),
                500
            )
    }


def controle_parents(
    question: str,
    intent: str,
    context: Dict[str, Any],
    candidate: str
) -> Dict[str, Any]:

    local_ok, local_reason = (
        valider_pertinence(
            question,
            candidate,
            intent
        )
    )

    if not GROQ_API_KEY:

        final = (
            candidate
            if local_ok
            else
            "Je dois reformuler ma réponse."
        )

        return {
            "answer": final,
            "reviewed": False,
            "parent1": {
                "available": False,
                "verdict": "LOCAL"
            },
            "parent2": {
                "available": False,
                "verdict": "LOCAL"
            },
            "source":
                "local_validator",
            "local_validation": {
                "ok": local_ok,
                "reason": local_reason
            }
        }

    parent1 = appeler_parent(
        1,
        question,
        intent,
        context,
        candidate
    )

    candidat_1 = candidate

    if (
        parent1["available"]
        and parent1["verdict"] == "REVISE"
        and parent1["answer"]
    ):
        candidat_1 = parent1["answer"]

    parent2 = appeler_parent(
        2,
        question,
        intent,
        context,
        candidat_1
    )

    final = candidat_1

    if (
        parent2["available"]
        and parent2["verdict"] == "REVISE"
        and parent2["answer"]
    ):
        final = parent2["answer"]

    final_ok, final_reason = (
        valider_pertinence(
            question,
            final,
            intent
        )
    )

    if not final_ok:

        alternatives = [
            parent2.get(
                "answer",
                ""
            ),
            parent1.get(
                "answer",
                ""
            ),
            candidate
        ]

        final = ""

        for alternative in alternatives:

            if not alternative:
                continue

            ok, _ = valider_pertinence(
                question,
                alternative,
                intent
            )

            if ok:
                final = alternative
                break

        if not final:
            final = (
                "Je n'ai pas suffisamment "
                "d'informations pour répondre "
                "correctement à cette demande."
            )

    return {
        "answer":
            nettoyer_reponse(final),
        "reviewed": (
            parent1["available"]
            or parent2["available"]
        ),
        "parent1": parent1,
        "parent2": parent2,
        "source":
            "parents",
        "local_validation": {
            "ok": final_ok,
            "reason": final_reason
        }
    }


# ============================================================
# 26. PROJETS
# ============================================================

def creer_projet(
    owner: str,
    nom: str,
    objectif: str = ""
) -> Dict[str, Any]:

    project_id = str(
        uuid.uuid4()
    )

    now = maintenant()

    nom = limiter_texte(
        nom,
        200
    )

    objectif = limiter_texte(
        objectif,
        1000
    )

    with DB_LOCK:
        conn = connexion_db()

        try:
            conn.execute(
                """
                INSERT INTO projects
                (
                    id,
                    owner,
                    nom,
                    objectif,
                    statut,
                    progression,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    owner,
                    nom,
                    objectif,
                    "actif",
                    0,
                    now,
                    now
                )
            )

            conn.commit()

        finally:
            conn.close()

    BUS.emit(
        "project.created",
        {
            "project_id":
                project_id,
            "owner":
                owner,
            "name":
                nom
        }
    )

    return {
        "id": project_id,
        "owner": owner,
        "nom": nom,
        "objectif": objectif,
        "statut": "actif",
        "progression": 0,
        "created_at": now,
        "updated_at": now
    }


def lister_projets(
    owner: str
) -> List[Dict[str, Any]]:

    with DB_LOCK:
        conn = connexion_db()

        try:
            rows = conn.execute(
                """
                SELECT *
                FROM projects
                WHERE owner = ?
                ORDER BY updated_at DESC
                """,
                (owner,)
            ).fetchall()

        finally:
            conn.close()

    return [
        dict(row)
        for row in rows
    ]


def obtenir_projet(
    owner: str,
    project_id: str
) -> Optional[Dict[str, Any]]:

    with DB_LOCK:
        conn = connexion_db()

        try:
            row = conn.execute(
                """
                SELECT *
                FROM projects
                WHERE id = ?
                AND owner = ?
                """,
                (
                    project_id,
                    owner
                )
            ).fetchone()

        finally:
            conn.close()

    return dict(row) if row else None


# ============================================================
# 27. TÂCHES
# ============================================================

def creer_tache(
    owner: str,
    titre: str,
    project_id: Optional[str] = None,
    echeance: Optional[str] = None
) -> Dict[str, Any]:

    task_id = str(
        uuid.uuid4()
    )

    now = maintenant()

    titre = limiter_texte(
        titre,
        300
    )

    with DB_LOCK:
        conn = connexion_db()

        try:

            if project_id:
                row = conn.execute(
                    """
                    SELECT id
                    FROM projects
                    WHERE id = ?
                    AND owner = ?
                    """,
                    (
                        project_id,
                        owner
                    )
                ).fetchone()

                if not row:
                    project_id = None

            conn.execute(
                """
                INSERT INTO tasks
                (
                    id,
                    project_id,
                    owner,
                    titre,
                    statut,
                    echeance,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    project_id,
                    owner,
                    titre,
                    "a_faire",
                    echeance,
                    now
                )
            )

            conn.commit()

        finally:
            conn.close()

    BUS.emit(
        "task.created",
        {
            "task_id":
                task_id,
            "owner":
                owner
        }
    )

    return {
        "id": task_id,
        "project_id": project_id,
        "owner": owner,
        "titre": titre,
        "statut": "a_faire",
        "echeance": echeance,
        "created_at": now
    }


def lister_taches(
    owner: str,
    project_id: Optional[str] = None
) -> List[Dict[str, Any]]:

    with DB_LOCK:
        conn = connexion_db()

        try:

            if project_id:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM tasks
                    WHERE owner = ?
                    AND project_id = ?
                    ORDER BY created_at DESC
                    """,
                    (
                        owner,
                        project_id
                    )
                ).fetchall()

            else:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM tasks
                    WHERE owner = ?
                    ORDER BY created_at DESC
                    """,
                    (owner,)
                ).fetchall()

        finally:
            conn.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# 28. NOTIFICATIONS
# ============================================================

def creer_notification(
    owner: str,
    type_: str,
    titre: str,
    message: str
) -> Dict[str, Any]:

    notification_id = str(
        uuid.uuid4()
    )

    now = maintenant()

    with DB_LOCK:
        conn = connexion_db()

        try:
            conn.execute(
                """
                INSERT INTO notifications
                (
                    id,
                    owner,
                    type,
                    titre,
                    message,
                    lu,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    notification_id,
                    owner,
                    type_,
                    limiter_texte(
                        titre,
                        200
                    ),
                    limiter_texte(
                        message,
                        2000
                    ),
                    now
                )
            )

            conn.commit()

        finally:
            conn.close()

    return {
        "id":
            notification_id,
        "owner":
            owner,
        "type":
            type_,
        "titre":
            titre,
        "message":
            message,
        "lu":
            False,
        "created_at":
            now
    }


# ============================================================
# 29. AUDIT
# ============================================================

def enregistrer_action(
    user_id: str,
    action: str,
    objet: str = "",
    resultat: str = "",
    permission: str = "USE_AI"
):

    with DB_LOCK:
        conn = connexion_db()

        try:
            conn.execute(
                """
                INSERT INTO actions_log
                (
                    user_id,
                    action,
                    objet,
                    resultat,
                    permission,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    action,
                    limiter_texte(
                        objet,
                        500
                    ),
                    limiter_texte(
                        resultat,
                        1000
                    ),
                    permission,
                    maintenant()
                )
            )

            conn.commit()

        finally:
            conn.close()


# ============================================================
# 30. DASHBOARD
# ============================================================

def dashboard(
    owner: str
) -> Dict[str, Any]:

    with DB_LOCK:
        conn = connexion_db()

        try:

            projects = conn.execute(
                """
                SELECT COUNT(*)
                FROM projects
                WHERE owner = ?
                """,
                (owner,)
            ).fetchone()[0]

            tasks = conn.execute(
                """
                SELECT COUNT(*)
                FROM tasks
                WHERE owner = ?
                """,
                (owner,)
            ).fetchone()[0]

            notifications = conn.execute(
                """
                SELECT COUNT(*)
                FROM notifications
                WHERE owner = ?
                AND lu = 0
                """,
                (owner,)
            ).fetchone()[0]

            conversations = conn.execute(
                """
                SELECT COUNT(*)
                FROM conversations
                WHERE owner = ?
                """,
                (owner,)
            ).fetchone()[0]

            memories = conn.execute(
                """
                SELECT COUNT(*)
                FROM user_memory
                WHERE owner = ?
                """,
                (owner,)
            ).fetchone()[0]

        finally:
            conn.close()

    return {
        "projects": projects,
        "tasks": tasks,
        "notifications": notifications,
        "conversations": conversations,
        "memories": memories
    }


# ============================================================
# 31. FEEDBACK
# ============================================================

def enregistrer_feedback(
    telephone: Optional[str],
    question: str,
    reponse: str,
    satisfait: bool,
    motif: str = "",
    commentaire: str = "",
    correction: str = "",
    intent: str = "inconnue"
) -> Dict[str, Any]:

    with DB_LOCK:
        conn = connexion_db()

        try:
            conn.execute(
                """
                INSERT INTO avis
                (
                    telephone,
                    question,
                    reponse,
                    satisfait,
                    motif,
                    commentaire,
                    cree_le
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    telephone,
                    normaliser_texte(
                        question
                    ),
                    nettoyer_reponse(
                        reponse
                    ),
                    1 if satisfait else 0,
                    limiter_texte(
                        motif,
                        500
                    ),
                    limiter_texte(
                        commentaire,
                        2000
                    ),
                    maintenant()
                )
            )

            conn.commit()

        finally:
            conn.close()

    if satisfait:

        enregistrer_exemple_apprentissage(
            question=question,
            intent=intent,
            context={
                "type":
                    "feedback_positif"
            },
            candidate=reponse,
            approved_answer=reponse,
            source="positive_feedback",
            quality=0.90,
            owner=telephone
        )

    elif correction:

        enregistrer_correction(
            question=question,
            bad_answer=reponse,
            good_answer=correction,
            reason=(
                motif
                or commentaire
                or "Correction utilisateur"
            ),
            intent=intent,
            owner=telephone
        )

    elif commentaire:

        enregistrer_erreur(
            owner=telephone,
            error_type="negative_feedback",
            question=question,
            bad_answer=reponse,
            expected_mode=intent,
            actual_mode=intent,
            cause=commentaire,
            correction="",
            confidence=0.75
        )

    BUS.emit(
        "feedback.received",
        {
            "owner":
                telephone,
            "satisfied":
                bool(satisfait)
        }
    )

    return {
        "ok": True,
        "learned": (
            bool(satisfait)
            or bool(correction)
        )
    }


# ============================================================
# 32. STATS APPRENTISSAGE
# ============================================================

def stats_apprentissage() -> Dict[str, Any]:

    with DB_LOCK:
        conn = connexion_db()

        try:

            examples = conn.execute(
                """
                SELECT COUNT(*)
                FROM learning_examples
                """
            ).fetchone()[0]

            corrections = conn.execute(
                """
                SELECT COUNT(*)
                FROM response_corrections
                """
            ).fetchone()[0]

            errors = conn.execute(
                """
                SELECT COUNT(*)
                FROM error_memory
                """
            ).fetchone()[0]

            intents = conn.execute(
                """
                SELECT COUNT(*)
                FROM intent_examples
                """
            ).fetchone()[0]

        finally:
            conn.close()

    return {
        "learning_examples":
            examples,
        "corrections":
            corrections,
        "errors":
            errors,
        "intent_examples":
            intents
    }


# ============================================================
# 33. EXPORT APPRENTISSAGE
# ============================================================

def exporter_apprentissage() -> str:

    lignes = []

    with DB_LOCK:
        conn = connexion_db()

        try:
            rows = conn.execute(
                """
                SELECT
                    question,
                    intent,
                    approved_answer
                FROM learning_examples
                WHERE approved_answer IS NOT NULL
                AND approved_answer != ''
                ORDER BY created_at ASC
                """
            ).fetchall()

        finally:
            conn.close()

    for row in rows:

        objet = {
            "messages": [
                {
                    "role": "user",
                    "content":
                        row["question"]
                },
                {
                    "role": "assistant",
                    "content":
                        row["approved_answer"]
                }
            ],
            "intent":
                row["intent"]
        }

        lignes.append(
            json_safe(objet)
        )

    return "\n".join(lignes)


# ============================================================
# 34. RECHERCHE DANS LES CONNAISSANCES
# ============================================================

def rechercher_connaissance(
    question: str
) -> Optional[Dict[str, Any]]:

    with DB_LOCK:
        conn = connexion_db()

        try:
            rows = conn.execute(
                """
                SELECT
                    question,
                    reponse,
                    confiance,
                    source,
                    niveau
                FROM connaissances_publiques
                ORDER BY confiance DESC
                LIMIT 100
                """
            ).fetchall()

        finally:
            conn.close()

    meilleur = None
    meilleur_score = 0.0

    for row in rows:

        score = similarite(
            question,
            row["question"]
        )

        score *= (
            0.5
            + float(row["confiance"])
            * 0.5
        )

        if score > meilleur_score:

            meilleur_score = score

            meilleur = {
                "question":
                    row["question"],
                "answer":
                    row["reponse"],
                "confidence":
                    row["confiance"],
                "source":
                    row["source"],
                "level":
                    row["niveau"],
                "score":
                    score
            }

    if (
        meilleur
        and meilleur_score >= 0.72
    ):
        return meilleur

    return None


def enregistrer_connaissance(
    question: str,
    reponse: str,
    confiance: float,
    source: str,
    niveau: int = INFO_EXTERNAL
):

    # Ne pas empoisonner automatiquement
    # la connaissance publique avec une réponse
    # générée sans source.
    if (
        not source
        or source in {
            "groq",
            "generated",
            "parents"
        }
    ):
        return

    with DB_LOCK:
        conn = connexion_db()

        try:
            conn.execute(
                """
                INSERT INTO connaissances_publiques
                (
                    question,
                    reponse,
                    confiance,
                    source,
                    niveau,
                    cree_le
                )
                VALUES (?, ?, ?, ?, ?, ?)

                ON CONFLICT(question)
                DO UPDATE SET
                    reponse = excluded.reponse,
                    confiance = excluded.confiance,
                    source = excluded.source,
                    niveau = excluded.niveau,
                    cree_le = excluded.cree_le
                """,
                (
                    normaliser_texte(
                        question
                    ),
                    nettoyer_reponse(
                        reponse
                    ),
                    max(
                        0.0,
                        min(1.0, confiance)
                    ),
                    source,
                    niveau,
                    maintenant()
                )
            )

            conn.commit()

        finally:
            conn.close()


# ============================================================
# 35. EXTRACTION DE MÉMOIRE UTILISATEUR
# ============================================================

def detecter_information_memorisable(
    question: str
) -> Optional[Tuple[str, str]]:

    q = normaliser_texte(
        question
    )

    n = minuscules(q)

    patterns = [
        (
            r"je m'appelle\s+(.+)",
            "nom"
        ),
        (
            r"je m’appelle\s+(.+)",
            "nom"
        ),
        (
            r"mon nom est\s+(.+)",
            "nom"
        ),
        (
            r"appelle[- ]moi\s+(.+)",
            "nom_prefere"
        )
    ]

    for pattern, key in patterns:

        match = re.search(
            pattern,
            n,
            flags=re.IGNORECASE
        )

        if match:

            value = match.group(
                1
            ).strip()

            if value:
                return (
                    key,
                    value[:500]
                )

    return None


# ============================================================
# 36. CONTEXTE POUR LES PARENTS
# ============================================================

def construire_contexte_controle(
    question: str,
    intent: str,
    mode: str,
    etat: Dict[str, Any],
    historique: List[Dict[str, Any]],
    memoire: List[Dict[str, Any]],
    recherche: Optional[Dict[str, Any]]
) -> Dict[str, Any]:

    return {
        "identite_systeme": {
            "name":
                IDENTITE_ADRYNX["name"],
            "creator":
                IDENTITE_ADRYNX["creator"],
            "creation_date":
                IDENTITE_ADRYNX["creation_date"]
        },
        "question":
            question,
        "intent":
            intent,
        "mode":
            mode,
        "state":
            etat,
        "history":
            historique[-8:],
        "memory":
            memoire,
        "external_information": (
            recherche.get(
                "results",
                []
            )
            if recherche
            else []
        )
    }


# ============================================================
# 37. TRAITEMENT PRINCIPAL
# ============================================================

def traiter_question(
    question: str,
    telephone: Optional[str] = None,
    owner: Optional[str] = None,
    conversation_id: Optional[str] = None,
    rechercher: Optional[bool] = None
) -> Dict[str, Any]:

    question = normaliser_texte(
        question
    )

    if not question:

        return {
            "ok": False,
            "answer":
                "Écris-moi une demande.",
            "intent":
                "inconnue",
            "source":
                "local"
        }

    owner = (
        normaliser_texte(
            owner
        )
        or normaliser_texte(
            telephone
        )
        or "anon"
    )

    conv_id = verifier_conversation(
        conversation_id,
        owner
    )

    historique = derniers_messages(
        conv_id
    )

    etat_ancien = (
        obtenir_etat_conversation(
            conv_id
        )
    )

    # --------------------------------------------------------
    # 1. INTENTION
    # --------------------------------------------------------

    intent = detecter_intention(
        question,
        historique
    )

    mode = determiner_mode(
        intent
    )

    # --------------------------------------------------------
    # 2. CONTEXTE
    # --------------------------------------------------------

    sujet = extraire_sujet(
        question,
        etat_ancien.get(
            "subject",
            ""
        )
    )

    entites = extraire_entites(
        question
    )

    contraintes = extraire_contraintes(
        question
    )

    objectif = determiner_objectif(
        intent
    )

    # --------------------------------------------------------
    # 3. ENREGISTRER LA QUESTION
    # --------------------------------------------------------

    enregistrer_message(
        conv_id,
        "user",
        question
    )

    mettre_a_jour_etat_conversation(
        conv_id=conv_id,
        subject=sujet,
        objective=objectif,
        intent=intent,
        mode=mode,
        entities=entites,
        constraints=contraintes
    )

    # --------------------------------------------------------
    # 4. IDENTITÉ
    # --------------------------------------------------------

    identite = reponse_identite(
        question
    )

    if identite:

        enregistrer_message(
            conv_id,
            "assistant",
            identite
        )

        enregistrer_action(
            owner,
            "identity_response",
            question,
            "success",
            "READ_PROFILE"
        )

        return {
            "ok": True,
            "answer": identite,
            "intent":
                "identite",
            "mode":
                "DIALOGUE",
            "conversation_id":
                conv_id,
            "source":
                "identity_core",
            "reviewed":
                True
        }

    # --------------------------------------------------------
    # 5. SOCIAL — AVANT INTERNET / GROQ
    # --------------------------------------------------------

    social = detecter_social(
        question
    )

    if social:

        enregistrer_message(
            conv_id,
            "assistant",
            social
        )

        return {
            "ok": True,
            "answer": social,
            "intent": intent,
            "mode": "SOCIAL",
            "conversation_id":
                conv_id,
            "source":
                "social_core",
            "reviewed":
                True
        }

    # --------------------------------------------------------
    # 6. COMMANDES PLATEFORME
    # --------------------------------------------------------

    commande = parser_commande_naturelle(
        question
    )

    if commande:

        answer = None

        try:
            answer = (
                reponse_plateforme(
                    commande,
                    owner
                )
            )
        except Exception:
            answer = None

        if answer:

            enregistrer_message(
                conv_id,
                "assistant",
                answer
            )

            enregistrer_action(
                owner,
                commande.get(
                    "action",
                    "platform_action"
                ),
                question,
                "success",
                "USE_AI"
            )

            return {
                "ok": True,
                "answer": answer,
                "intent":
                    "plateforme",
                "mode":
                    "PLANIFICATION",
                "conversation_id":
                    conv_id,
                "source":
                    "platform_core",
                "reviewed":
                    True
            }

    # --------------------------------------------------------
    # 7. CALCUL
    # --------------------------------------------------------

    if intent == "calcul":

        resultat = calculer_expression(
            question
        )

        if resultat is not None:

            answer = (
                f"Le résultat est **{resultat}**."
            )

            enregistrer_message(
                conv_id,
                "assistant",
                answer
            )

            return {
                "ok": True,
                "answer": answer,
                "intent":
                    "calcul",
                "mode":
                    "RESOLUTION",
                "conversation_id":
                    conv_id,
                "source":
                    "calculator",
                "reviewed":
                    True
            }

    # --------------------------------------------------------
    # 8. MÉMOIRE
    # --------------------------------------------------------

    memoire = rechercher_memoire_utilisateur(
        owner,
        question
    )

    apprentissage = (
        rechercher_exemples_apprentissage(
            question,
            intent
        )
    )

    # --------------------------------------------------------
    # 9. CONNAISSANCE LOCALE
    # --------------------------------------------------------

    connaissance = None

    if intent in {
        "factuelle",
        "explication"
    }:
        connaissance = (
            rechercher_connaissance(
                question
            )
        )

    # --------------------------------------------------------
    # 10. RECHERCHE EXTERNE
    # --------------------------------------------------------

    recherche = None

    doit_rechercher = False

    if rechercher is True:
        doit_rechercher = True

    elif rechercher is False:
        doit_rechercher = False

    elif intent in {
        "recherche"
    }:
        doit_rechercher = True

    elif intent in {
        "factuelle",
        "programmation"
    }:

        mots_variables = [
            "actuel",
            "actuelle",
            "aujourd'hui",
            "aujourd hui",
            "maintenant",
            "latest",
            "dernière",
            "derniere",
            "version",
            "prix",
            "disponible",
            "disponibilité",
            "disponibilite",
            "2026",
            "render",
            "groq"
        ]

        doit_rechercher = any(
            mot in minuscules(question)
            for mot in mots_variables
        )

    if doit_rechercher:

        recherche = rechercher_internet(
            question
        )

    # --------------------------------------------------------
    # 11. RÉPONSE DIRECTE DE LA CONNAISSANCE
    # --------------------------------------------------------

    if (
        connaissance
        and connaissance["confidence"] >= 0.85
        and not recherche
    ):

        candidate = connaissance[
            "answer"
        ]

    else:

        # ----------------------------------------------------
        # 12. GÉNÉRATION
        # ----------------------------------------------------

        candidate = generer_candidat(
            question=question,
            intent=intent,
            mode=mode,
            historique=historique,
            etat=etat_ancien,
            memoire=memoire,
            apprentissage=apprentissage,
            recherche=recherche
        )

    # --------------------------------------------------------
    # 13. FALLBACK SI GROQ INDISPONIBLE
    # --------------------------------------------------------

    if not candidate:

        if connaissance:

            candidate = connaissance[
                "answer"
            ]

        elif recherche and recherche.get(
            "ok"
        ):

            candidate = (
                "J'ai trouvé ces informations "
                "externes :\n\n"
                + recherche.get(
                    "text",
                    ""
                )
            )

        elif intent == "ambiguite":

            candidate = (
                "Peux-tu préciser ce que tu veux "
                "que je fasse ?"
            )

        elif intent == "suivi":

            if historique:

                candidate = (
                    "Je poursuis à partir du "
                    "contexte précédent. "
                    "Précise simplement l'étape "
                    "que tu veux maintenant."
                )

            else:

                candidate = (
                    "Je peux continuer, mais il me "
                    "manque le contexte précédent."
                )

        else:

            candidate = (
                "Je n'ai pas encore suffisamment "
                "d'informations pour répondre "
                "correctement."
            )

    # --------------------------------------------------------
    # 14. CONTRÔLE DES PARENTS
    # --------------------------------------------------------

    contexte_controle = (
        construire_contexte_controle(
            question,
            intent,
            mode,
            etat_ancien,
            historique,
            memoire,
            recherche
        )
    )

    controle = controle_parents(
        question=question,
        intent=intent,
        context=contexte_controle,
        candidate=candidate
    )

    answer = nettoyer_reponse(
        controle.get(
            "answer",
            candidate
        )
    )

    # --------------------------------------------------------
    # 15. MÉMOIRE DE L'APPRENTISSAGE
    # --------------------------------------------------------

    parent1 = controle.get(
        "parent1",
        {}
    )

    parent2 = controle.get(
        "parent2",
        {}
    )

    a_ete_corrige = (
        (
            parent1.get(
                "verdict"
            ) == "REVISE"
        )
        or
        (
            parent2.get(
                "verdict"
            ) == "REVISE"
        )
    )

    if a_ete_corrige:

        source_correction = (
            "parent1"
            if parent2.get(
                "verdict"
            ) != "REVISE"
            else "parent2"
        )

        enregistrer_exemple_apprentissage(
            question=question,
            intent=intent,
            context=contexte_controle,
            candidate=candidate,
            approved_answer=answer,
            source=source_correction,
            quality=0.92,
            owner=owner
        )

    # --------------------------------------------------------
    # 16. APPRENTISSAGE D'UNE INFO UTILISATEUR
    # --------------------------------------------------------

    info_memorisable = (
        detecter_information_memorisable(
            question
        )
    )

    if info_memorisable:

        key, value = (
            info_memorisable
        )

        enregistrer_memoire_utilisateur(
            owner=owner,
            key=key,
            value=value,
            category="user",
            confidence=0.85,
            importance=0.7
        )

    # --------------------------------------------------------
    # 17. MÉMOIRE ÉPISODIQUE
    # --------------------------------------------------------

    enregistrer_episode(
        owner=owner,
        event_type="interaction",
        content=(
            f"Question: {question}\n"
            f"Intention: {intent}\n"
            f"Réponse: {answer}"
        ),
        importance=0.35
    )

    # --------------------------------------------------------
    # 18. MESSAGE FINAL
    # --------------------------------------------------------

    enregistrer_message(
        conv_id,
        "assistant",
        answer
    )

    # --------------------------------------------------------
    # 19. AUDIT
    # --------------------------------------------------------

    enregistrer_action(
        owner,
        "ask",
        question,
        "success",
        "USE_AI"
    )

    # --------------------------------------------------------
    # 20. ÉVÉNEMENT
    # --------------------------------------------------------

    BUS.emit(
        "cognitive.response",
        {
            "owner":
                owner,
            "conversation_id":
                conv_id,
            "intent":
                intent,
            "mode":
                mode,
            "reviewed":
                controle.get(
                    "reviewed",
                    False
                )
        }
    )

    # --------------------------------------------------------
    # 21. RÉSULTAT API
    # --------------------------------------------------------

    return {
        "ok": True,
        "answer": answer,
        "intent": intent,
        "mode": mode,
        "conversation_id":
            conv_id,
        "source":
            controle.get(
                "source",
                "unknown"
            ),
        "reviewed":
            controle.get(
                "reviewed",
                False
            ),
        "context": {
            "subject":
                sujet,
            "objective":
                objectif,
            "entities":
                entites,
            "constraints":
                contraintes
        },
        "learning": {
            "used_examples":
                len(apprentissage),
            "parent_correction":
                a_ete_corrige
        }
    }


# ============================================================
# 38. VERSION COURTE COMPATIBLE ANCIEN CODE
# ============================================================

def poser_question(
    question: str,
    telephone: Optional[str] = None,
    conversation_id: Optional[str] = None
) -> Dict[str, Any]:

    return traiter_question(
        question=question,
        telephone=telephone,
        conversation_id=conversation_id
    )


def ask(
    question: str,
    owner: str = "anon",
    conversation_id: Optional[str] = None
) -> Dict[str, Any]:

    return traiter_question(
        question=question,
        owner=owner,
        conversation_id=conversation_id
    )


# ============================================================
# 39. SANTÉ DU NOYAU
# ============================================================

def health() -> Dict[str, Any]:

    database_ok = False

    try:
        with DB_LOCK:
            conn = connexion_db()

            try:
                conn.execute(
                    "SELECT 1"
                ).fetchone()

                database_ok = True

            finally:
                conn.close()

    except Exception:
        database_ok = False

    return {
        "ok":
            database_ok,
        "name":
            IDENTITE_ADRYNX["name"],
        "version":
            "5.0 Cognitive Core",
        "database":
            database_ok,
        "groq_configured":
            bool(GROQ_API_KEY),
        "model":
            GROQ_MODEL,
        "learning":
            True,
        "parent_control":
            bool(GROQ_API_KEY),
        "timestamp":
            maintenant()
    }


# ============================================================
# 40. IDENTITÉ PUBLIQUE
# ============================================================

def obtenir_identite() -> Dict[str, Any]:
    return dict(
        IDENTITE_ADRYNX
    )


# ============================================================
# 41. RESET CACHE / CONTEXTE VOLATILE
# ============================================================

def vider_cache_local():
    """
    Le noyau 5.0 utilise principalement SQLite.
    Il n'y a donc pas de gros cache mémoire permanent.
    Cette fonction existe pour permettre à api.py
    d'avoir une route de maintenance compatible.
    """

    return {
        "ok": True,
        "message":
            "Cache cognitif local vidé."
    }


# ============================================================
# 42. EXPORT ÉTAT CONVERSATION
# ============================================================

def obtenir_conversation(
    owner: str,
    conversation_id: str
) -> Optional[Dict[str, Any]]:

    with DB_LOCK:
        conn = connexion_db()

        try:
            conversation = conn.execute(
                """
                SELECT *
                FROM conversations
                WHERE id = ?
                AND owner = ?
                """,
                (
                    conversation_id,
                    owner
                )
            ).fetchone()

        finally:
            conn.close()

    if not conversation:
        return None

    return {
        "conversation":
            dict(conversation),
        "state":
            obtenir_etat_conversation(
                conversation_id
            ),
        "messages":
            derniers_messages(
                conversation_id,
                limit=50
            )
    }


def lister_conversations(
    owner: str,
    limit: int = 30
) -> List[Dict[str, Any]]:

    limit = max(
        1,
        min(limit, 100)
    )

    with DB_LOCK:
        conn = connexion_db()

        try:
            rows = conn.execute(
                """
                SELECT *
                FROM conversations
                WHERE owner = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (
                    owner,
                    limit
                )
            ).fetchall()

        finally:
            conn.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# 43. SUPPRESSION CONVERSATION
# ============================================================

def supprimer_conversation(
    owner: str,
    conversation_id: str
) -> bool:

    with DB_LOCK:
        conn = connexion_db()

        try:

            row = conn.execute(
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

            if not row:
                return False

            conn.execute(
                """
                DELETE FROM messages
                WHERE conv_id = ?
                """,
                (conversation_id,)
            )

            conn.execute(
                """
                DELETE FROM conversation_state
                WHERE conv_id = ?
                """,
                (conversation_id,)
            )

            conn.execute(
                """
                DELETE FROM conversations
                WHERE id = ?
                AND owner = ?
                """,
                (
                    conversation_id,
                    owner
                )
            )

            conn.commit()

        finally:
            conn.close()

    BUS.emit(
        "conversation.deleted",
        {
            "owner":
                owner,
            "conversation_id":
                conversation_id
        }
    )

    return True


# ============================================================
# 44. ADMIN
# ============================================================

def verifier_admin(
    secret: str
) -> bool:

    if not ADMIN_SECRET:
        return False

    return (
        str(secret).strip()
        == ADMIN_SECRET
    )


def admin_stats(
    secret: str
) -> Dict[str, Any]:

    if not verifier_admin(secret):
        return {
            "ok": False,
            "error":
                "Accès administrateur refusé."
        }

    with DB_LOCK:
        conn = connexion_db()

        try:

            tables = [
                "conversations",
                "messages",
                "user_memory",
                "episodic_memory",
                "error_memory",
                "learning_examples",
                "response_corrections",
                "projects",
                "tasks",
                "notifications",
                "events_log",
                "actions_log"
            ]

            result = {}

            for table in tables:

                try:
                    result[table] = conn.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]

                except Exception:
                    result[table] = 0

        finally:
            conn.close()

    return {
        "ok": True,
        "version":
            "5.0 Cognitive Core",
        "database":
            result,
        "health":
            health()
    }


# ============================================================
# 45. INITIALISATION FINALE
# ============================================================

CORE_VERSION = "5.0 Cognitive Core"


def initialiser():
    """
    Point d'initialisation appelé éventuellement par api.py.
    """

    init_db()

    return {
        "ok": True,
        "version":
            CORE_VERSION,
        "identity":
            IDENTITE_ADRYNX["name"]
    }


# ============================================================
# 46. TEST LOCAL
# ============================================================

if __name__ == "__main__":

    print(
        "=============================================="
    )
    print(
        " ADRYNX — 5.0 Cognitive Core"
    )
    print(
        "=============================================="
    )

    print(
        json.dumps(
            health(),
            ensure_ascii=False,
            indent=2
        )
    )

    print()

    print(
        "Test social :"
    )

    resultat = traiter_question(
        "Comment tu vas ?",
        owner="local_test"
    )

    print(
        resultat.get(
            "answer",
            ""
        )
    )
