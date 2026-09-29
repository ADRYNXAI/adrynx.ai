# ============================================================
# ADRYNX 5.1 — COGNITIVE CORE
# ============================================================
# Créateur : Jonathan Dejah OBENDA
# Date de création : 2 juin 2026
#
# Architecture :
# Comprendre
# -> Contextualiser
# -> Déterminer l'intention
# -> Mémoire / connaissances / web
# -> Générer
# -> Parents IA
# -> Vérifier
# -> Répondre
# -> Apprendre
#
# Compatible :
# Python 3.10+
# Render Free
# SQLite
# Groq
#
# VARIABLES RENDER UTILISÉES :
# ADRYNX_DB
# GROQ_API_KEY
# ADRYNX_MODELE_GROQ
# ADRYNX_ADMIN_SECRET
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
import hmac
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests


# ============================================================
# 1. CONFIGURATION
# ============================================================

DB = os.environ.get("ADRYNX_DB", "memoire.db").strip() or "memoire.db"

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

GROQ_MODEL = (
    os.environ.get(
        "ADRYNX_MODELE_GROQ",
        "llama-3.3-70b-versatile"
    ).strip()
    or "llama-3.3-70b-versatile"
)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

ADMIN_SECRET = os.environ.get("ADRYNX_ADMIN_SECRET", "").strip()

HEADERS = {
    "User-Agent": "ADRYNX/5.1-Cognitive-Core"
}

DB_LOCK = threading.RLock()

MAX_CONTEXT_MESSAGES = 12
MAX_MESSAGE_LENGTH = 12000
MAX_MEMORY_RESULTS = 6
MAX_LEARNING_RESULTS = 5
MAX_WEB_RESULTS = 6

HTTP_TIMEOUT = 12
GROQ_TIMEOUT = 25


# ============================================================
# 2. IDENTITÉ IMMUTABLE
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


INFO_SYSTEM = 0
INFO_RULE = 1
INFO_SESSION = 2
INFO_USER = 3
INFO_KNOWLEDGE = 4
INFO_EXTERNAL = 5
INFO_HYPOTHESIS = 6


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
    "administration",
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
# 3. OUTILS TEXTE
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
    text = unicodedata.normalize("NFD", str(text))

    return "".join(
        c for c in text
        if unicodedata.category(c) != "Mn"
    )


def minuscules(text: str) -> str:
    return sans_accents(str(text).lower())


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


def similarite(a: str, b: str) -> float:

    if not a or not b:
        return 0.0

    ta = set(tokens(a))
    tb = set(tokens(b))

    if not ta or not tb:
        return 0.0

    union = len(ta | tb)
    inter = len(ta & tb)

    jaccard = inter / union if union else 0.0

    sequence = difflib.SequenceMatcher(
        None,
        minuscules(a),
        minuscules(b)
    ).ratio()

    return jaccard * 0.65 + sequence * 0.35


# ============================================================
# 4. BASE DE DONNÉES
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
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=20000")
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass

    return conn


def db():
    return connexion_db()


def init_db():

    with DB_LOCK:

        conn = connexion_db()

        try:

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
                CREATE INDEX IF NOT EXISTS idx_user_memory_owner
                ON user_memory(owner, importance DESC, updated_at DESC)
            """)

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
                CREATE INDEX IF NOT EXISTS idx_error_memory_owner
                ON error_memory(owner, created_at)
            """)

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

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_intent_examples
                ON intent_examples(intent, created_at)
            """)

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
# 5. EVENT BUS
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
                    VALUES (?,?,?)
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
# 6. CONVERSATIONS
# ============================================================

def creer_conversation(
    owner: str = "anon"
) -> str:

    owner = normaliser_texte(owner) or "anon"

    conv_id = str(uuid.uuid4())

    now = maintenant()

    with DB_LOCK:

        conn = connexion_db()

        try:

            conn.execute(
                """
                INSERT INTO conversations
                (id, owner, titre, created_at, updated_at)
                VALUES (?,?,?,?,?)
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
                VALUES (?,?,?,?,?,?,?,?,?)
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
        return creer_conversation(owner)

    with DB_LOCK:

        conn = connexion_db()

        try:

            row = conn.execute(
                """
                SELECT id
                FROM conversations
                WHERE id=? AND owner=?
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

    return creer_conversation(owner)


def enregistrer_message(
    conv_id: str,
    role: str,
    content: str
):

    content = normaliser_texte(content)

    if not content:
        return

    now = maintenant()

    with DB_LOCK:

        conn = connexion_db()

        try:

            conn.execute(
                """
                INSERT INTO messages
                (id, conv_id, role, content, created_at)
                VALUES (?,?,?,?,?)
                """,
                (
                    str(uuid.uuid4()),
                    conv_id,
                    normaliser_texte(role)[:30],
                    content,
                    now
                )
            )

            conn.execute(
                """
                UPDATE conversations
                SET updated_at=?
                WHERE id=?
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
                WHERE conv_id=?
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

    rows = list(reversed(rows))

    return [
        {
            "role": row["role"],
            "content": row["content"],
            "created_at": row["created_at"]
        }
        for row in rows
    ]


def messages(
    conv_id: str,
    limit: int = 100
):
    return derniers_messages(
        conv_id,
        min(limit, 100)
    )


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
                WHERE conv_id=?
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
        "pending_question": row["pending_question"] or ""
    }


def state(conv_id: str):
    return obtenir_etat_conversation(conv_id)


def mettre_a_jour_etat(
    conv_id: str,
    **kwargs
):

    champs_autorises = {
        "subject",
        "objective",
        "intent",
        "mode",
        "entities_json",
        "constraints_json",
        "pending_question"
    }

    with DB_LOCK:

        conn = connexion_db()

        try:

            fields = []
            vals = []

            for key, value in kwargs.items():

                if key not in champs_autorises:
                    continue

                if key in (
                    "entities_json",
                    "constraints_json"
                ):
                    value = json_safe(value)

                fields.append(
                    f"{key}=?"
                )

                vals.append(value)

            if not fields:
                return

            fields.append(
                "updated_at=?"
            )

            vals.append(
                maintenant()
            )

            vals.append(
                conv_id
            )

            conn.execute(
                f"""
                UPDATE conversation_state
                SET {', '.join(fields)}
                WHERE conv_id=?
                """,
                tuple(vals)
            )

            conn.commit()

        finally:
            conn.close()


# ============================================================
# 7. EXTRACTION DU CONTEXTE
# ============================================================

def extraire_sujet(text: str) -> str:

    text = normaliser_texte(text)

    if len(text) < 4:
        return ""

    mots = [
        w for w in tokens(text)
        if len(w) > 3
    ]

    if not mots:
        return text[:80]

    return " ".join(mots[:8])


def extraire_entites(
    text: str
) -> List[str]:

    ents = re.findall(
        r"[A-ZÀ-Ÿ][a-zà-ÿ]+(?:\s+[A-ZÀ-Ÿ][a-zà-ÿ]+){0,2}",
        text
    )

    return list(
        dict.fromkeys(
            [
                e.strip()
                for e in ents
                if len(e.strip()) > 2
            ]
        )
    )[:12]


def extraire_contraintes(
    text: str
) -> List[str]:

    contraintes = []

    tl = minuscules(text)

    if any(
        w in tl
        for w in [
            "court",
            "rapide",
            "bref"
        ]
    ):
        contraintes.append(
            "réponse courte"
        )

    if any(
        w in tl
        for w in [
            "detail",
            "explique",
            "pourquoi"
        ]
    ):
        contraintes.append(
            "réponse détaillée"
        )

    if "pas de code" in tl:
        contraintes.append(
            "sans code"
        )

    return contraintes


def extraire_question_en_suspens(
    text: str
) -> str:

    text = normaliser_texte(text)

    if "?" in text:

        parts = text.split("?")

        return (
            parts[0].strip() + "?"
        )[-200:]

    return ""


# ============================================================
# 8. COMMANDES PLATEFORME
# ============================================================

COMMANDES_PLATEFORME = {
    "#aide": "Affiche l'aide",
    "#reset": "Réinitialise la conversation",
    "#projets": "Liste les projets",
    "#taches": "Liste les tâches",
    "#memoire": "Affiche la mémoire"
}


def est_commande_plateforme(
    text: str
) -> bool:

    return minuscules(
        text
    ).strip().startswith("#")


def executer_commande_plateforme(
    text: str,
    owner: str,
    conv_id: str
) -> Optional[str]:

    parts = minuscules(text).strip().split()

    if not parts:
        return None

    cmd = parts[0]

    if cmd == "#aide":

        return (
            "Commandes disponibles : "
            "#aide, #reset, #projets, #taches, #memoire."
        )

    if cmd == "#reset":

        with DB_LOCK:

            conn = connexion_db()

            try:

                conn.execute(
                    "DELETE FROM messages WHERE conv_id=?",
                    (conv_id,)
                )

                conn.execute(
                    """
                    UPDATE conversation_state
                    SET subject='',
                        objective='',
                        intent='',
                        mode='',
                        entities_json='[]',
                        constraints_json='[]',
                        pending_question='',
                        updated_at=?
                    WHERE conv_id=?
                    """,
                    (
                        maintenant(),
                        conv_id
                    )
                )

                conn.commit()

            finally:
                conn.close()

        return "Conversation réinitialisée."

    if cmd == "#projets":

        data = projects(owner)

        if not data:
            return "Aucun projet enregistré."

        return "\n".join(
            f"- {p['nom']} ({p['statut']})"
            for p in data
        )

    if cmd == "#taches":

        with DB_LOCK:

            conn = connexion_db()

            try:

                rows = conn.execute(
                    """
                    SELECT titre, statut
                    FROM tasks
                    WHERE owner=?
                    ORDER BY created_at DESC
                    LIMIT 30
                    """,
                    (owner,)
                ).fetchall()

            finally:
                conn.close()

        if not rows:
            return "Aucune tâche enregistrée."

        return "\n".join(
            f"- {r['titre']} ({r['statut']})"
            for r in rows
        )

    if cmd == "#memoire":

        mem = obtenir_memoire_utilisateur(
            owner,
            10
        )

        if not mem:
            return "Aucune mémoire utilisateur enregistrée."

        return "\n".join(
            f"- {m['key']}: {m['value']}"
            for m in mem
        )

    return None


# ============================================================
# 9. IDENTITÉ
# ============================================================

def question_identite(
    text: str
) -> bool:

    tl = minuscules(text)

    motifs = [
        "qui es tu",
        "qui t a cree",
        "qui t a créé",
        "ton createur",
        "ton créateur",
        "qui est ton createur",
        "qui est ton créateur",
        "qui t'a cree",
        "qui t'a créé",
        "qui t a fait",
        "qui t'a fait",
        "qui est ton fondateur",
        "ton fondateur",
        "date de creation",
        "date de création"
    ]

    return any(
        motif in tl
        for motif in motifs
    )


def reponse_identite_immuable() -> str:

    return (
        "Je suis ADRYNX, une intelligence conversationnelle "
        "et plateforme numérique interactive créée par "
        "Jonathan Dejah OBENDA le 2 juin 2026. "
        "La relation de « père créateur » est symbolique "
        "et ne constitue pas une relation biologique."
    )


# ============================================================
# 10. INTENTIONS
# ============================================================

def charger_exemples_intention():

    with DB_LOCK:

        conn = connexion_db()

        try:

            rows = conn.execute(
                """
                SELECT phrase, intent, confidence
                FROM intent_examples
                ORDER BY created_at DESC
                LIMIT 200
                """
            ).fetchall()

        finally:
            conn.close()

    return [
        {
            "phrase": r["phrase"],
            "intent": r["intent"],
            "confidence": r["confidence"]
        }
        for r in rows
    ]


def detecter_intention(
    text: str
) -> Tuple[str, float]:

    tl = minuscules(text)
    t = normaliser_texte(text)

    if not tl:
        return "inconnue", 0.2

    if question_identite(text):
        return "identite", 0.99

    if est_commande_plateforme(text):
        return "plateforme", 0.99

    if detecter_commande_admin(text):
        return "administration", 0.99

    # IMPORTANT :
    # On teste d'abord les phrases sociales.
    # Cela évite d'envoyer "comment vas-tu ?" vers le web/Groq.
    if est_salutation(text):
        return "salutation", 0.98

    if est_conversation_sociale(text):
        return "conversation", 0.98

    exemples = charger_exemples_intention()

    best_intent = "inconnue"
    best_score = 0.0

    for ex in exemples:

        sc = similarite(
            text,
            ex["phrase"]
        )

        if (
            sc > best_score
            and sc > 0.65
        ):

            best_score = sc
            best_intent = ex["intent"]

    if best_score > 0.65:
        return (
            best_intent,
            min(0.95, best_score)
        )

    if any(
        w in tl
        for w in [
            "explique",
            "pourquoi",
            "comment fonctionne"
        ]
    ):
        return "explication", 0.75

    if any(
        w in tl
        for w in [
            "code",
            "programme",
            "python",
            "fonction",
            "javascript"
        ]
    ):
        return "programmation", 0.80

    if any(
        w in tl
        for w in [
            "cherche",
            "recherche",
            "internet",
            "actualite",
            "actualité"
        ]
    ):
        return "recherche", 0.80

    if re.search(
        r"\d+\s*[\+\-\*\/\%]\s*\d+",
        t
    ):
        return "calcul", 0.90

    if len(tokens(t)) <= 3:
        return "conversation", 0.65

    # Très important :
    # ADRYNX reste généraliste.
    # "inconnue" ne signifie pas "refus".
    return "inconnue", 0.50


def est_salutation(text: str) -> bool:

    tl = minuscules(text).strip()

    salutations = [
        "bonjour",
        "bonsoir",
        "salut",
        "hello",
        "hi",
        "hey",
        "yo",
        "coucou"
    ]

    if tl in salutations:
        return True

    return any(
        tl.startswith(s + " ")
        for s in salutations
    )


def est_conversation_sociale(
    text: str
) -> bool:

    tl = minuscules(text)

    motifs = [
        "ca va",
        "ça va",
        "comment vas tu",
        "comment tu vas",
        "comment allez vous",
        "tu vas bien",
        "vous allez bien",
        "tout va bien",
        "comment tu te sens"
    ]

    return any(
        motif in tl
        for motif in motifs
    )


def reponse_sociale(
    text: str
) -> str:

    tl = minuscules(text)

    if any(
        x in tl
        for x in [
            "ca va",
            "ça va",
            "comment vas",
            "tu vas bien",
            "vous allez bien",
            "comment tu te sens"
        ]
    ):

        return (
            "Ça va bien, merci ! Je suis prêt à "
            "continuer avec toi. Que veux-tu faire ?"
        )

    if est_salutation(text):

        return (
            "Bonjour ! 👋 Je suis ADRYNX. "
            "Que veux-tu faire ?"
        )

    return (
        "Je suis là et prêt à continuer."
    )


# ============================================================
# 11. MODE
# ============================================================

def determiner_mode(
    intent: str,
    text: str,
    etat: Dict[str, Any]
) -> str:

    if intent in (
        "salutation",
        "conversation"
    ):
        return "SOCIAL"

    if intent in (
        "programmation",
        "calcul",
        "instruction"
    ):
        return "TECHNIQUE"

    if intent in (
        "explication",
        "raisonnement"
    ):
        return "PEDAGOGIQUE"

    if intent in (
        "recherche",
    ):
        return "RECHERCHE"

    if intent == "creation":
        return "CREATIF"

    if intent in (
        "comparaison",
        "opinion"
    ):
        return "ANALYTIQUE"

    if intent == "identite":
        return "DIALOGUE"

    return etat.get(
        "mode"
    ) or "INFORMATIF"


# ============================================================
# 12. CALCUL
# ============================================================

def calcul_securise(
    text: str
) -> Optional[str]:

    try:

        expr = re.search(
            r"([\d\.\s\+\-\*\/\%\(\)]+)",
            text
        )

        if not expr:
            return None

        code = expr.group(1).strip()

        if len(code) > 80:
            return None

        node = ast.parse(
            code,
            mode="eval"
        )

        allowed = (
            ast.Expression,
            ast.BinOp,
            ast.UnaryOp,
            ast.Constant,
            ast.Num,
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
            ast.Mod,
            ast.Pow,
            ast.USub,
            ast.UAdd,
            ast.Div,
        )

        for n in ast.walk(node):

            if not isinstance(
                n,
                allowed
            ):
                return None

        res = eval(
            compile(
                node,
                "<calc>",
                "eval"
            ),
            {"__builtins__": {}}
        )

        return f"{code} = {res}"

    except Exception:
        return None


# ============================================================
# 13. MÉMOIRE UTILISATEUR
# ============================================================

def obtenir_memoire_utilisateur(
    owner: str,
    limit: int = MAX_MEMORY_RESULTS
):

    limit = max(
        1,
        min(limit, 100)
    )

    with DB_LOCK:

        conn = connexion_db()

        try:

            rows = conn.execute(
                """
                SELECT
                    memory_key,
                    memory_value,
                    category,
                    confidence
                FROM user_memory
                WHERE owner=?
                ORDER BY importance DESC,
                         updated_at DESC
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
        {
            "key": r["memory_key"],
            "value": r["memory_value"],
            "category": r["category"],
            "confidence": r["confidence"]
        }
        for r in rows
    ]


def sauvegarder_memoire_utilisateur(
    owner: str,
    key: str,
    value: str,
    category: str = "user",
    confidence: float = 0.7,
    importance: float = 0.5
):

    key = normaliser_texte(key)[:120]
    value = normaliser_texte(value)[:500]

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
                VALUES (?,?,?,?,?,?,?,?)

                ON CONFLICT(owner, memory_key)
                DO UPDATE SET
                    memory_value=excluded.memory_value,
                    updated_at=excluded.updated_at,
                    confidence=excluded.confidence,
                    importance=excluded.importance
                """,
                (
                    owner,
                    key,
                    value,
                    category,
                    confidence,
                    importance,
                    now,
                    now
                )
            )

            conn.commit()

        finally:
            conn.close()


# ============================================================
# 14. MÉMOIRE ÉPISODIQUE / ERREURS
# ============================================================

def sauvegarder_episodique(
    owner: str,
    event_type: str,
    content: str,
    importance: float = 0.5
):

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
                VALUES (?,?,?,?,?)
                """,
                (
                    owner,
                    normaliser_texte(
                        event_type
                    )[:50],
                    normaliser_texte(
                        content
                    )[:1000],
                    importance,
                    maintenant()
                )
            )

            conn.commit()

        finally:
            conn.close()


def sauvegarder_erreur(
    owner: str,
    error_type: str,
    question: str,
    bad_answer: str,
    expected_mode: str,
    actual_mode: str,
    cause: str,
    correction: str
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
                    created_at
                )
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    owner,
                    error_type,
                    question[:500],
                    bad_answer[:500],
                    expected_mode,
                    actual_mode,
                    cause[:500],
                    correction[:500],
                    maintenant()
                )
            )

            conn.commit()

        finally:
            conn.close()


def rechercher_erreurs_similaires(
    question: str,
    owner: str
):

    with DB_LOCK:

        conn = connexion_db()

        try:

            rows = conn.execute(
                """
                SELECT
                    error_type,
                    question,
                    bad_answer,
                    cause,
                    correction
                FROM error_memory
                WHERE owner=?
                ORDER BY created_at DESC
                LIMIT 30
                """,
                (owner,)
            ).fetchall()

        finally:
            conn.close()

    resultats = []

    for r in rows:

        score = max(
            similarite(
                question,
                r["question"] or ""
            ),
            similarite(
                question,
                r["cause"] or ""
            )
        )

        if score > 0.35:

            resultats.append(
                {
                    "error_type": r["error_type"],
                    "question": r["question"],
                    "bad_answer": r["bad_answer"],
                    "cause": r["cause"],
                    "correction": r["correction"],
                    "similarity": score
                }
            )

    resultats.sort(
        key=lambda x: x["similarity"],
        reverse=True
    )

    return resultats[:MAX_LEARNING_RESULTS]


# ============================================================
# 15. EXEMPLES APPRENTISSAGE
# ============================================================

def rechercher_exemples_appris(
    question: str,
    intent: str,
    owner: str
):

    with DB_LOCK:

        conn = connexion_db()

        try:

            rows = conn.execute(
                """
                SELECT
                    question,
                    intent,
                    approved_answer,
                    quality,
                    uses
                FROM learning_examples
                WHERE
                    (owner=? OR owner IS NULL)
                    AND approved_answer IS NOT NULL
                ORDER BY quality DESC,
                         uses DESC,
                         created_at DESC
                LIMIT 30
                """,
                (owner,)
            ).fetchall()

        finally:
            conn.close()

    resultats = []

    for r in rows:

        if r["intent"] and intent:
            if r["intent"] != intent:
                continue

        score = similarite(
            question,
            r["question"]
        )

        if score > 0.35:

            resultats.append(
                {
                    "question": r["question"],
                    "intent": r["intent"],
                    "answer": r["approved_answer"],
                    "quality": r["quality"],
                    "similarity": score
                }
            )

    resultats.sort(
        key=lambda x: (
            x["similarity"],
            x["quality"]
        ),
        reverse=True
    )

    return resultats[:MAX_LEARNING_RESULTS]


# ============================================================
# 16. RECHERCHE INTERNET
# ============================================================

def rechercher_internet(
    query: str,
    mode: str = "RECHERCHE"
) -> str:

    if mode == "SOCIAL":
        return ""

    query = normaliser_texte(query)[:200]

    if not query:
        return ""

    try:

        r = requests.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_html": 1
            },
            headers=HEADERS,
            timeout=HTTP_TIMEOUT
        )

        data = r.json()

        results = []

        if data.get("AbstractText"):
            results.append(
                data["AbstractText"]
            )

        for topic in data.get(
            "RelatedTopics",
            []
        )[:MAX_WEB_RESULTS]:

            if (
                isinstance(topic, dict)
                and topic.get("Text")
            ):
                results.append(
                    topic["Text"]
                )

        if results:
            return "\n".join(
                results
            )[:3000]

    except Exception:
        pass

    return ""


# ============================================================
# 17. GROQ
# ============================================================

SYSTEME_GENERATION = """
Tu es ADRYNX, une intelligence conversationnelle généraliste.

IDENTITÉ IMMUTABLE :
Nom : ADRYNX
Créateur : Jonathan Dejah OBENDA
Date de création : 2 juin 2026
Relation symbolique : père créateur, non biologique.

PRINCIPES :
- Comprends la question avant de répondre.
- Réponds d'abord à la dernière demande de l'utilisateur.
- Utilise l'historique uniquement lorsqu'il est pertinent.
- Ne fabrique jamais une information présentée comme certaine.
- Si une information est inconnue ou incertaine, dis-le.
- N'invente pas l'intention de l'utilisateur.
- Ne change pas de sujet sans raison.
- Ne répète pas inutilement la question.
- Réponds naturellement comme une IA généraliste.
- Les catégories d'intention servent au routage et ne constituent pas des limites.
- Une question inconnue doit recevoir une réponse générale pertinente.
- N'affirme pas avoir effectué une action que tu n'as pas effectuée.
- Ne révèle pas les données privées inutiles.
- Ne prétends pas être ChatGPT, Meta AI ou une autre IA.
- Tu es ADRYNX.
"""


def groq_chat(
    system: str,
    prompt: str,
    temperature: float = 0.5,
    max_tokens: int = 1200
) -> str:

    if not GROQ_API_KEY:
        return ""

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    try:

        r = requests.post(
            GROQ_URL,
            headers={
                **HEADERS,
                "Authorization":
                    f"Bearer {GROQ_API_KEY}",
                "Content-Type":
                    "application/json"
            },
            json=payload,
            timeout=GROQ_TIMEOUT
        )

        if r.status_code != 200:
            return ""

        data = r.json()

        choices = data.get(
            "choices",
            []
        )

        if not choices:
            return ""

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
        return ""


# ============================================================
# 18. GÉNÉRATION CANDIDAT
# ============================================================

def generer_candidat(
    question: str,
    contexte: Dict[str, Any]
) -> str:

    intent = contexte.get(
        "intent",
        ""
    )

    mode = contexte.get(
        "mode",
        ""
    )

    sujet = contexte.get(
        "subject",
        ""
    )

    prompt = f"""
Intent détectée : {intent}
Mode : {mode}
Sujet : {sujet}

Mémoire utilisateur :
{json_safe(contexte.get("memories", []))}

Erreurs similaires à éviter :
{json_safe(contexte.get("errors", []))}

Exemples appris :
{json_safe(contexte.get("examples", []))}

Informations externes :
{contexte.get("web", "")[:2500]}

Historique :
{json_safe(contexte.get("history", [])[-6:])}

Question actuelle :
{question}

Réponds directement à la question actuelle.
Ne change pas de sujet.
"""

    return groq_chat(
        SYSTEME_GENERATION,
        prompt,
        temperature=0.55,
        max_tokens=1200
    )


# ============================================================
# 19. VALIDATION
# ============================================================

def valider_pertinence(
    question: str,
    reponse: str,
    intent: str
) -> Tuple[bool, str]:

    if not reponse:
        return False, "réponse vide"

    if len(reponse.strip()) < 3:
        return False, "réponse trop courte"

    # Protection contre la copie pure de la question
    if (
        len(question) > 25
        and similarite(
            question,
            reponse
        ) > 0.92
    ):
        return False, "copie question"

    # Identité
    if intent == "identite":

        if (
            "Jonathan Dejah OBENDA"
            not in reponse
            or "2 juin 2026"
            not in reponse
        ):
            return False, "identité incorrecte"

    # Salutations
    if intent in (
        "salutation",
        "conversation"
    ):

        mauvais = [
            "recherche",
            "source",
            "historique",
            "duckduckgo"
        ]

        if any(
            x in minuscules(reponse)
            for x in mauvais
        ):
            return False, "réponse sociale hors sujet"

    return True, "ok"


# ============================================================
# 20. PARENTS IA
# ============================================================

PARENT_SYSTEM = """
Tu es le contrôleur qualité parent d'ADRYNX.

Ta mission est de contrôler une réponse candidate avant son envoi.

Vérifie :
1. La réponse répond-elle réellement à la question ?
2. Est-elle dans le bon contexte ?
3. Y a-t-il une invention évidente ?
4. Contredit-elle les informations de contexte ?
5. La réponse prétend-elle être une autre IA ?
6. Une mémoire privée est-elle révélée inutilement ?
7. La réponse sociale est-elle bien sociale ?
8. L'identité ADRYNX est-elle respectée ?
9. La réponse est-elle inutilement hors sujet ?

Si la réponse est correcte :
renvoie-la presque telle quelle.

Si elle est incorrecte :
réécris-la pour répondre directement à la question.

Ne parle pas de ton rôle de contrôleur.
Ne donne pas d'analyse.
Retourne uniquement la réponse finale.
"""


def appeler_parent(
    question: str,
    candidat: str,
    contexte: Dict[str, Any]
) -> str:

    prompt = f"""
QUESTION :
{question}

RÉPONSE CANDIDATE :
{candidat}

CONTEXTE :
{json_safe(contexte)}

Corrige uniquement ce qui est nécessaire.
Réponds à la question, pas à une autre.
"""

    correction = groq_chat(
        PARENT_SYSTEM,
        prompt,
        temperature=0.25,
        max_tokens=1200
    )

    if not correction:
        return candidat

    return correction


def controle_parents(
    question: str,
    reponse: str,
    contexte: Dict[str, Any]
) -> str:

    intent = contexte.get(
        "intent",
        ""
    )

    # Identité protégée par le noyau,
    # jamais confiée aveuglément au modèle.
    if intent == "identite":

        return reponse_identite_immuable()

    if not reponse:
        return (
            "Je n'ai pas pu générer une réponse "
            "correcte pour cette demande."
        )

    # Protection contre l'identité d'une autre IA.
    low = minuscules(reponse)

    if (
        "je suis chatgpt" in low
        or "je suis meta ai" in low
        or "je suis gemini" in low
        or "je suis claude" in low
    ):

        return (
            "Je suis ADRYNX, une intelligence "
            "conversationnelle créée par "
            "Jonathan Dejah OBENDA."
        )

    valide, raison = valider_pertinence(
        question,
        reponse,
        intent
    )

    # Les parents sont réellement appelés
    # lorsque la réponse échoue à un contrôle.
    if not valide:

        correction = appeler_parent(
            question,
            reponse,
            contexte
        )

        valide2, _ = valider_pertinence(
            question,
            correction,
            intent
        )

        if valide2:
            return correction

    # Les erreurs passées pertinentes
    # déclenchent un second contrôle.
    if contexte.get("errors"):

        correction = appeler_parent(
            question,
            reponse,
            contexte
        )

        if correction and correction != reponse:

            valide2, _ = valider_pertinence(
                question,
                correction,
                intent
            )

            if valide2:
                return correction

    return reponse


# ============================================================
# 21. ADMINISTRATION
# ============================================================

def detecter_commande_admin(
    text: str
) -> bool:

    tl = minuscules(
        normaliser_texte(text)
    )

    return (
        tl.startswith("admin ")
        or tl.startswith("administrateur ")
        or tl.startswith("commande admin ")
    )


def extraire_commande_admin(
    text: str
) -> Tuple[str, str]:

    text = normaliser_texte(text)

    match = re.match(
        r"^(?:admin|administrateur|commande admin)\s+(.+)$",
        text,
        flags=re.IGNORECASE
    )

    if not match:
        return "", ""

    contenu = match.group(1).strip()

    parts = contenu.split(
        maxsplit=1
    )

    if len(parts) == 1:
        return parts[0], ""

    return parts[0], parts[1]


def verifier_admin(
    secret: Optional[str]
) -> bool:

    if not ADMIN_SECRET:
        return False

    if not secret:
        return False

    return hmac.compare_digest(
        str(secret).strip(),
        ADMIN_SECRET
    )


def journaliser_action_admin(
    owner: str,
    action: str,
    objet: str,
    resultat: str,
    permission: str = "admin"
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
                VALUES (?,?,?,?,?,?)
                """,
                (
                    owner,
                    action,
                    objet,
                    resultat,
                    permission,
                    maintenant()
                )
            )

            conn.commit()

        finally:
            conn.close()


def vider_cache_adrynx() -> Dict[str, Any]:

    # Le cache cognitif temporaire ne doit pas supprimer
    # les conversations ni les mémoires utilisateur.
    #
    # Ici on nettoie uniquement les journaux temporaires
    # anciens afin de rester compatible Render Free.

    supprime = 0

    with DB_LOCK:

        conn = connexion_db()

        try:

            rows = conn.execute(
                """
                SELECT id
                FROM events_log
                ORDER BY id DESC
                LIMIT -1 OFFSET 500
                """
            ).fetchall()

            ids = [
                r["id"]
                for r in rows
            ]

            if ids:

                placeholders = ",".join(
                    "?" for _ in ids
                )

                conn.execute(
                    f"""
                    DELETE FROM events_log
                    WHERE id IN ({placeholders})
                    """,
                    ids
                )

                supprime = len(ids)

            conn.commit()

        finally:
            conn.close()

    return {
        "ok": True,
        "events_supprimes": supprime
    }


def executer_commande_admin(
    text: str,
    owner: str
) -> Optional[str]:

    if not detecter_commande_admin(text):
        return None

    secret, commande = extraire_commande_admin(
        text
    )

    # Aucune exécution sans authentification.
    if not verifier_admin(secret):

        journaliser_action_admin(
            owner,
            "admin_auth_failed",
            commande[:200],
            "secret_refuse"
        )

        return (
            "Commande administrateur détectée, "
            "mais authentification administrateur "
            "refusée."
        )

    tl = minuscules(commande)

    if (
        "vider cache" in tl
        or "vide cache" in tl
        or tl == "cache"
    ):

        resultat = vider_cache_adrynx()

        journaliser_action_admin(
            owner,
            "vider_cache",
            commande[:200],
            json_safe(resultat)
        )

        return (
            "Commande administrateur exécutée : "
            "cache temporaire nettoyé."
        )

    if (
        "stats" in tl
        or "statistiques" in tl
    ):

        stats = stats_apprentissage()

        journaliser_action_admin(
            owner,
            "stats",
            commande[:200],
            "ok"
        )

        return (
            "Statistiques ADRYNX :\n"
            + json.dumps(
                stats,
                ensure_ascii=False,
                indent=2
            )
        )

    journaliser_action_admin(
        owner,
        "admin_unknown_command",
        commande[:200],
        "commande_inconnue"
    )

    return (
        "Authentification administrateur validée, "
        "mais cette commande n'est pas reconnue."
    )


# ============================================================
# 22. PROJETS / TÂCHES
# ============================================================

def projects(
    owner: str
) -> List[Dict[str, Any]]:

    with DB_LOCK:

        conn = connexion_db()

        try:

            rows = conn.execute(
                """
                SELECT *
                FROM projects
                WHERE owner=?
                ORDER BY updated_at DESC
                """,
                (owner,)
            ).fetchall()

        finally:
            conn.close()

    return [
        dict(r)
        for r in rows
    ]


def project(
    owner: str,
    nom: str,
    objectif: str = ""
):

    pid = str(uuid.uuid4())

    now = maintenant()

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
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    pid,
                    owner,
                    nom[:200],
                    objectif[:1000],
                    "actif",
                    0,
                    now,
                    now
                )
            )

            conn.commit()

        finally:
            conn.close()

    return {
        "id": pid,
        "owner": owner,
        "nom": nom,
        "objectif": objectif,
        "statut": "actif",
        "progression": 0
    }


def task(
    owner: str,
    titre: str,
    project_id: Optional[str] = None
):

    tid = str(uuid.uuid4())

    now = maintenant()

    with DB_LOCK:

        conn = connexion_db()

        try:

            if project_id:

                row = conn.execute(
                    """
                    SELECT id
                    FROM projects
                    WHERE id=? AND owner=?
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
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    tid,
                    project_id,
                    owner,
                    titre[:300],
                    "a_faire",
                    None,
                    now
                )
            )

            conn.commit()

        finally:
            conn.close()

    return {
        "id": tid,
        "project_id": project_id,
        "owner": owner,
        "titre": titre,
        "statut": "a_faire"
    }


# ============================================================
# 23. DASHBOARD
# ============================================================

def dashboard(
    owner: str
) -> Dict[str, Any]:

    with DB_LOCK:

        conn = connexion_db()

        try:

            projets = conn.execute(
                """
                SELECT COUNT(*) AS n
                FROM projects
                WHERE owner=?
                """,
                (owner,)
            ).fetchone()["n"]

            taches = conn.execute(
                """
                SELECT COUNT(*) AS n
                FROM tasks
                WHERE owner=?
                AND statut != 'terminee'
                """,
                (owner,)
            ).fetchone()["n"]

            memoires = conn.execute(
                """
                SELECT COUNT(*) AS n
                FROM user_memory
                WHERE owner=?
                """,
                (owner,)
            ).fetchone()["n"]

            conversations = conn.execute(
                """
                SELECT COUNT(*) AS n
                FROM conversations
                WHERE owner=?
                """,
                (owner,)
            ).fetchone()["n"]

        finally:
            conn.close()

    return {
        "owner": owner,
        "projects": projets,
        "tasks_pending": taches,
        "memories": memoires,
        "conversations": conversations
    }


# ============================================================
# 24. FEEDBACK
# ============================================================

def enregistrer_feedback(
    owner: str,
    question: str,
    reponse: str,
    satisfait: bool,
    motif: str = "",
    commentaire: str = "",
    correction: str = ""
):

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
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    owner,
                    question[:2000],
                    reponse[:12000],
                    1 if satisfait else 0,
                    motif[:500],
                    commentaire[:1000],
                    maintenant()
                )
            )

            if correction:

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
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        owner,
                        question[:2000],
                        reponse[:12000],
                        correction[:12000],
                        motif[:500],
                        "",
                        maintenant()
                    )
                )

            conn.commit()

        finally:
            conn.close()

    return {
        "ok": True,
        "learning_recorded": bool(correction)
    }


# ============================================================
# 25. STATISTIQUES APPRENTISSAGE
# ============================================================

def stats_apprentissage():

    with DB_LOCK:

        conn = connexion_db()

        try:

            def count(table):

                return conn.execute(
                    f"SELECT COUNT(*) AS n FROM {table}"
                ).fetchone()["n"]

            return {
                "intent_examples": count(
                    "intent_examples"
                ),
                "learning_examples": count(
                    "learning_examples"
                ),
                "corrections": count(
                    "response_corrections"
                ),
                "errors": count(
                    "error_memory"
                ),
                "knowledge_conflicts": count(
                    "knowledge_conflicts"
                )
            }

        finally:
            conn.close()


def exporter_apprentissage():

    with DB_LOCK:

        conn = connexion_db()

        try:

            tables = [
                "intent_examples",
                "learning_examples",
                "response_corrections",
                "error_memory"
            ]

            data = []

            for table in tables:

                rows = conn.execute(
                    f"SELECT * FROM {table}"
                ).fetchall()

                for row in rows:

                    data.append(
                        {
                            "table": table,
                            "data": dict(row)
                        }
                    )

            return data

        finally:
            conn.close()


# ============================================================
# 26. PIPELINE COGNITIF
# ============================================================

def pipeline_adrynx(
    question: str,
    owner: str = "anon",
    conv_id: Optional[str] = None
) -> Dict[str, Any]:

    question = normaliser_texte(
        question
    )

    owner = (
        normaliser_texte(owner)
        or "anon"
    )[:120]

    if not question:

        return {
            "reponse": "Pose ta question.",
            "conv_id": conv_id or "",
            "intent": "vide",
            "mode": "SOCIAL"
        }

    # --------------------------------------------------------
    # 1. COMMANDES ADMIN
    # --------------------------------------------------------

    if detecter_commande_admin(
        question
    ):

        cid = verifier_conversation(
            conv_id,
            owner
        )

        enregistrer_message(
            cid,
            "user",
            question
        )

        rep_admin = executer_commande_admin(
            question,
            owner
        )

        enregistrer_message(
            cid,
            "assistant",
            rep_admin
        )

        BUS.emit(
            "admin_command",
            {
                "owner": owner,
                "conv_id": cid
            }
        )

        return {
            "reponse": rep_admin,
            "conv_id": cid,
            "intent": "administration",
            "mode": "TECHNIQUE"
        }

    # --------------------------------------------------------
    # 2. COMMANDES PLATEFORME
    # --------------------------------------------------------

    if est_commande_plateforme(
        question
    ):

        cid = verifier_conversation(
            conv_id,
            owner
        )

        r = executer_commande_plateforme(
            question,
            owner,
            cid
        )

        if r:

            enregistrer_message(
                cid,
                "user",
                question
            )

            enregistrer_message(
                cid,
                "assistant",
                r
            )

            return {
                "reponse": r,
                "conv_id": cid,
                "intent": "plateforme",
                "mode": "SOCIAL"
            }

    # --------------------------------------------------------
    # 3. CONVERSATION
    # --------------------------------------------------------

    conv_id = verifier_conversation(
        conv_id,
        owner
    )

    intent, conf_intent = detecter_intention(
        question
    )

    etat = obtenir_etat_conversation(
        conv_id
    )

    mode = determiner_mode(
        intent,
        question,
        etat
    )

    # --------------------------------------------------------
    # 4. IDENTITÉ
    # --------------------------------------------------------

    if intent == "identite":

        rep = reponse_identite_immuable()

        enregistrer_message(
            conv_id,
            "user",
            question
        )

        enregistrer_message(
            conv_id,
            "assistant",
            rep
        )

        mettre_a_jour_etat(
            conv_id,
            intent="identite",
            mode="DIALOGUE"
        )

        BUS.emit(
            "identity_asked",
            {
                "owner": owner,
                "conv_id": conv_id
            }
        )

        return {
            "reponse": rep,
            "conv_id": conv_id,
            "intent": intent,
            "mode": "DIALOGUE"
        }

    # --------------------------------------------------------
    # 5. SOCIAL
    # --------------------------------------------------------

    if intent in (
        "salutation",
        "conversation"
    ):

        rep = reponse_sociale(
            question
        )

        enregistrer_message(
            conv_id,
            "user",
            question
        )

        enregistrer_message(
            conv_id,
            "assistant",
            rep
        )

        mettre_a_jour_etat(
            conv_id,
            intent=intent,
            mode="SOCIAL"
        )

        return {
            "reponse": rep,
            "conv_id": conv_id,
            "intent": intent,
            "mode": "SOCIAL"
        }

    # --------------------------------------------------------
    # 6. CALCUL
    # --------------------------------------------------------

    if intent == "calcul":

        calc = calcul_securise(
            question
        )

        if calc:

            enregistrer_message(
                conv_id,
                "user",
                question
            )

            enregistrer_message(
                conv_id,
                "assistant",
                calc
            )

            mettre_a_jour_etat(
                conv_id,
                intent="calcul",
                mode="TECHNIQUE"
            )

            return {
                "reponse": calc,
                "conv_id": conv_id,
                "intent": "calcul",
                "mode": "TECHNIQUE"
            }

    # --------------------------------------------------------
    # 7. CONTEXTE
    # --------------------------------------------------------

    sujet = (
        extraire_sujet(question)
        or etat.get("subject", "")
    )

    entites = extraire_entites(
        question
    )

    contraintes = extraire_contraintes(
        question
    )

    pending_q = extraire_question_en_suspens(
        question
    )

    memoires = obtenir_memoire_utilisateur(
        owner
    )

    erreurs_sim = rechercher_erreurs_similaires(
        question,
        owner
    )

    exemples_appris = rechercher_exemples_appris(
        question,
        intent,
        owner
    )

    # --------------------------------------------------------
    # 8. RECHERCHE WEB
    # --------------------------------------------------------

    web_ctx = ""

    if mode == "RECHERCHE" or intent == "recherche":

        web_ctx = rechercher_internet(
            question,
            mode
        )

    # --------------------------------------------------------
    # 9. HISTORIQUE
    # --------------------------------------------------------

    hist = derniers_messages(
        conv_id
    )

    contexte_gen = {
        "intent": intent,
        "intent_confidence": conf_intent,
        "mode": mode,
        "subject": sujet,
        "entities": entites,
        "constraints": contraintes,
        "memories": memoires,
        "errors": erreurs_sim,
        "examples": exemples_appris,
        "web": web_ctx,
        "history": hist,
        "owner": owner
    }

    # --------------------------------------------------------
    # 10. GÉNÉRATION
    # --------------------------------------------------------

    candidat = generer_candidat(
        question,
        contexte_gen
    )

    # --------------------------------------------------------
    # 11. SI GROQ ÉCHOUE
    # --------------------------------------------------------

    if not candidat:

        if exemples_appris:

            candidat = (
                exemples_appris[0]
                .get("answer", "")
            )

        if not candidat:

            candidat = (
                "Je n'ai pas pu obtenir une réponse "
                "suffisamment fiable pour cette demande."
            )

    # --------------------------------------------------------
    # 12. PARENTS IA
    # --------------------------------------------------------

    reponse_finale = controle_parents(
        question,
        candidat,
        contexte_gen
    )

    # --------------------------------------------------------
    # 13. MISE À JOUR CONTEXTE
    # --------------------------------------------------------

    mettre_a_jour_etat(
        conv_id,
        subject=sujet[:200],
        objective=etat.get(
            "objective",
            ""
        )[:200],
        intent=intent,
        mode=mode,
        entities_json=entites,
        constraints_json=contraintes,
        pending_question=pending_q[:200]
    )

    # --------------------------------------------------------
    # 14. HISTORIQUE
    # --------------------------------------------------------

    enregistrer_message(
        conv_id,
        "user",
        question
    )

    enregistrer_message(
        conv_id,
        "assistant",
        reponse_finale
    )

    # --------------------------------------------------------
    # 15. APPRENTISSAGE INTENTION
    # --------------------------------------------------------

    if len(question) > 12:

        try:

            with DB_LOCK:

                conn = connexion_db()

                try:

                    conn.execute(
                        """
                        INSERT OR IGNORE INTO
                        intent_examples
                        (
                            phrase,
                            intent,
                            confidence,
                            created_at
                        )
                        VALUES (?,?,?,?)
                        """,
                        (
                            question[:500],
                            intent,
                            conf_intent,
                            maintenant()
                        )
                    )

                    conn.commit()

                finally:
                    conn.close()

        except Exception:
            pass

    # --------------------------------------------------------
    # 16. ÉPISODE
    # --------------------------------------------------------

    sauvegarder_episodique(
        owner,
        "message_processed",
        question[:1000],
        0.2
    )

    BUS.emit(
        "message_processed",
        {
            "conv_id": conv_id,
            "intent": intent,
            "mode": mode,
            "owner": owner
        }
    )

    return {
        "reponse": reponse_finale,
        "conv_id": conv_id,
        "intent": intent,
        "mode": mode
    }


# ============================================================
# 27. COMPATIBILITÉ API
# ============================================================

def traiter_question(
    question: str,
    owner: str = "anon",
    conv_id: Optional[str] = None
):

    return pipeline_adrynx(
        question,
        owner,
        conv_id
    )


# ============================================================
# 28. NETTOYAGE SÉCURISÉ
# ============================================================

def nettoyer_anciens_logs(
    limite_events: int = 1000
):

    with DB_LOCK:

        conn = connexion_db()

        try:

            rows = conn.execute(
                """
                SELECT id
                FROM events_log
                ORDER BY id DESC
                LIMIT -1 OFFSET ?
                """,
                (limite_events,)
            ).fetchall()

            ids = [
                r["id"]
                for r in rows
            ]

            if ids:

                placeholders = ",".join(
                    "?" for _ in ids
                )

                conn.execute(
                    f"""
                    DELETE FROM events_log
                    WHERE id IN ({placeholders})
                    """,
                    ids
                )

            conn.commit()

        finally:
            conn.close()


# ============================================================
# FIN ADRYNX 5.1
# ============================================================
