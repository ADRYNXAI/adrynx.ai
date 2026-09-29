# ============================================================
# ADRYNX — NOYAU COGNITIF
# Version : 5.1
# Créateur : Jonathan Dejah OBENDA
# Date de création : 2 juin 2026
#
# Architecture :
# Comprendre
# → Contextualiser
# → Déterminer l'intention
# → Décider recherche / mémoire
# → Générer
# → Parent 1 : pertinence
# → Parent 2 : fiabilité
# → Contrôle local
# → Répondre
# → Apprendre
#
# Compatible :
# - Python 3.10+
# - SQLite
# - Render Free / RAM limitée
# - Groq
#
# Variables Render utilisées UNIQUEMENT :
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
DB_PATH = DB

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = (
    os.environ.get("ADRYNX_MODELE_GROQ", "llama-3.3-70b-versatile").strip()
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
GROQ_TIMEOUT = 30


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


# ============================================================
# 3. HIÉRARCHIE DE L'INFORMATION
# ============================================================

INFO_SYSTEM = 0
INFO_RULE = 1
INFO_SESSION = 2
INFO_USER = 3
INFO_KNOWLEDGE = 4
INFO_EXTERNAL = 5
INFO_HYPOTHESIS = 6


# ============================================================
# 4. INTENTIONS / MODES
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
# 5. UTILITAIRES
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
        r"[a-z0-9À-ÿ'-]+",
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
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    return text.strip()[:12000]


def limiter_texte(text: Any, limite: int) -> str:
    return normaliser_texte(text)[:limite]


def json_safe(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )
    except Exception:
        return "{}"


def lire_json(value: Any, default: Any = None) -> Any:
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
        minuscules(b),
    ).ratio()

    return jaccard * 0.65 + sequence * 0.35


def owner_normalise(owner: Any) -> str:
    value = normaliser_texte(owner)

    if not value:
        return "anon"

    return value[:120]


# Alias utile pour compatibilité éventuelle.
owner = owner_normalise


# ============================================================
# 6. BASE SQLITE
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
                exist_ok=True,
            )

    except Exception:
        pass


_preparer_dossier_db()


def connexion_db():
    conn = sqlite3.connect(
        DB,
        timeout=20,
        check_same_thread=False,
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

            # Index de performance.
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conv
                ON messages(conv_id, created_at)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_owner
                ON user_memory(owner, importance, updated_at)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_episode_owner
                ON episodic_memory(owner, created_at)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_errors_owner
                ON error_memory(owner, created_at)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_corrections_owner
                ON response_corrections(owner, created_at)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_intent_examples
                ON intent_examples(intent, created_at)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_actions_user
                ON actions_log(user_id, created_at)
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

    def emit(
        self,
        event_type: str,
        payload: Dict[str, Any],
    ):
        event = {
            "type": event_type,
            "payload": payload,
            "created_at": maintenant(),
        }

        try:
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
                            event["created_at"],
                        ),
                    )

                    conn.commit()

                finally:
                    conn.close()

        except Exception:
            pass

        with self.lock:
            listeners = list(self.listeners)

        for listener in listeners:
            try:
                listener(event)
            except Exception:
                pass


BUS = EventBus()


# ============================================================
# 8. CONVERSATIONS
# ============================================================

def creer_conversation(owner: str = "anon") -> str:
    owner = owner_normalise(owner)

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
                    now,
                ),
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
                    now,
                ),
            )

            conn.commit()

        finally:
            conn.close()

    return conv_id


def new_conversation(
    owner: str = "anon",
    titre: str = "Nouvelle conversation",
) -> str:

    conv_id = creer_conversation(owner)

    if titre and titre != "Nouvelle conversation":
        with DB_LOCK:
            conn = connexion_db()

            try:
                conn.execute(
                    """
                    UPDATE conversations
                    SET titre=?
                    WHERE id=? AND owner=?
                    """,
                    (
                        normaliser_texte(titre)[:200],
                        conv_id,
                        owner_normalise(owner),
                    ),
                )

                conn.commit()

            finally:
                conn.close()

    return conv_id


def verifier_conversation(
    conv_id: Optional[str],
    owner: str,
) -> str:

    owner = owner_normalise(owner)

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
                    owner,
                ),
            ).fetchone()

        finally:
            conn.close()

    if row:
        return conv_id

    return creer_conversation(owner)


def enregistrer_message(
    conv_id: str,
    role: str,
    content: str,
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
                    now,
                ),
            )

            conn.execute(
                """
                UPDATE conversations
                SET updated_at=?
                WHERE id=?
                """,
                (
                    now,
                    conv_id,
                ),
            )

            conn.commit()

        finally:
            conn.close()


def derniers_messages(
    conv_id: str,
    limit: int = MAX_CONTEXT_MESSAGES,
) -> List[Dict[str, Any]]:

    limit = max(
        1,
        min(limit, 30),
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
                    limit,
                ),
            ).fetchall()

        finally:
            conn.close()

    rows = list(reversed(rows))

    return [
        {
            "role": row["role"],
            "content": row["content"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def messages(
    conv_id: str,
    limit: int = 100,
) -> List[Dict[str, Any]]:

    limit = max(
        1,
        min(limit, 200),
    )

    with DB_LOCK:
        conn = connexion_db()

        try:
            rows = conn.execute(
                """
                SELECT role, content, created_at
                FROM messages
                WHERE conv_id=?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (
                    conv_id,
                    limit,
                ),
            ).fetchall()

        finally:
            conn.close()

    return [
        {
            "role": row["role"],
            "content": row["content"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def obtenir_etat_conversation(
    conv_id: str,
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
                (conv_id,),
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
            "pending_question": "",
        }

    return {
        "subject": row["subject"] or "",
        "objective": row["objective"] or "",
        "intent": row["intent"] or "",
        "mode": row["mode"] or "",
        "entities": lire_json(
            row["entities_json"],
            [],
        ),
        "constraints": lire_json(
            row["constraints_json"],
            [],
        ),
        "pending_question": row["pending_question"] or "",
    }


def state(conv_id: str) -> Dict[str, Any]:
    return obtenir_etat_conversation(conv_id)


def mettre_a_jour_etat(
    conv_id: str,
    **kwargs,
):

    allowed = {
        "subject",
        "objective",
        "intent",
        "mode",
        "entities_json",
        "constraints_json",
        "pending_question",
    }

    with DB_LOCK:
        conn = connexion_db()

        try:
            fields = []
            vals = []

            for key, value in kwargs.items():

                if key not in allowed:
                    continue

                if key in (
                    "entities_json",
                    "constraints_json",
                ):
                    value = json_safe(value)

                fields.append(f"{key}=?")
                vals.append(value)

            if not fields:
                return

            fields.append("updated_at=?")
            vals.append(maintenant())
            vals.append(conv_id)

            conn.execute(
                f"""
                UPDATE conversation_state
                SET {', '.join(fields)}
                WHERE conv_id=?
                """,
                tuple(vals),
            )

            conn.commit()

        finally:
            conn.close()


# ============================================================
# 9. EXTRACTION DU CONTEXTE
# ============================================================

def extraire_sujet(
    text: str,
) -> str:

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
    text: str,
) -> List[str]:

    text = normaliser_texte(text)

    candidats = re.findall(
        r"[A-ZÀ-Ÿ][a-zà-ÿ0-9.-]+"
        r"(?:\s+[A-ZÀ-Ÿ][a-zà-ÿ0-9.-]+){0,3}",
        text,
    )

    # Termes techniques / marques / acronymes.
    candidats += re.findall(
        r"\b[A-Z]{2,}[0-9A-Z.-]*\b",
        text,
    )

    candidats += re.findall(
        r"\b(?:GPT|Python|FastAPI|Groq|Render|SQLite)"
        r"(?:[-. ][0-9A-Za-z]+)*\b",
        text,
        flags=re.IGNORECASE,
    )

    resultat = []

    for item in candidats:
        item = item.strip()

        if len(item) > 2 and item not in resultat:
            resultat.append(item)

    return resultat[:15]


def extraire_contraintes(
    text: str,
) -> List[str]:

    contraintes = []
    tl = minuscules(text)

    if any(
        w in tl
        for w in (
            "court",
            "rapide",
            "bref",
            "resume",
        )
    ):
        contraintes.append("réponse courte")

    if any(
        w in tl
        for w in (
            "detail",
            "detaillé",
            "explique",
            "pourquoi",
            "en profondeur",
        )
    ):
        contraintes.append("réponse détaillée")

    if "pas de code" in tl:
        contraintes.append("sans code")

    if any(
        x in tl
        for x in (
            "etape par etape",
            "étape par étape",
            "pas a pas",
            "pas-à-pas",
        )
    ):
        contraintes.append("étapes détaillées")

    if any(
        x in tl
        for x in (
            "en francais",
            "en français",
        )
    ):
        contraintes.append("français")

    if any(
        x in tl
        for x in (
            "en anglais",
            "english",
        )
    ):
        contraintes.append("anglais")

    if "seulement la reponse" in tl:
        contraintes.append("réponse directe")

    return list(dict.fromkeys(contraintes))


def extraire_question_en_suspens(
    text: str,
) -> str:

    text = normaliser_texte(text)

    if "?" not in text:
        return ""

    parts = text.split("?")

    return (
        parts[0].strip() + "?"
    )[-200:]


# ============================================================
# 10. COMMANDES PLATEFORME
# ============================================================

COMMANDES_PLATEFORME = {
    "#aide": "Affiche l'aide de la plateforme",
    "#reset": "Réinitialise la conversation",
    "#projets": "Liste les projets",
    "#taches": "Liste les tâches",
    "#memoire": "Affiche la mémoire utilisateur",
}


def est_commande_plateforme(
    text: str,
) -> bool:

    return minuscules(text).strip().startswith("#")


def executer_commande_plateforme(
    text: str,
    owner: str,
    conv_id: str,
) -> Optional[str]:

    parts = minuscules(text).strip().split()

    if not parts:
        return None

    cmd = parts[0]

    if cmd == "#aide":
        return (
            "Commandes disponibles :\n"
            "#aide — afficher l'aide\n"
            "#reset — réinitialiser la conversation\n"
            "#projets — afficher les projets\n"
            "#taches — afficher les tâches\n"
            "#memoire — afficher la mémoire utilisateur"
        )

    if cmd == "#reset":

        with DB_LOCK:
            conn = connexion_db()

            try:
                conn.execute(
                    "DELETE FROM messages WHERE conv_id=?",
                    (conv_id,),
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
                        conv_id,
                    ),
                )

                conn.commit()

            finally:
                conn.close()

        return "Conversation réinitialisée."

    if cmd == "#projets":
        projets = projects(owner)

        if not projets:
            return "Aucun projet enregistré."

        return "\n".join(
            f"• {p['nom']} — {p['statut']} — {p['progression']}%"
            for p in projets
        )

    if cmd == "#taches":

        with DB_LOCK:
            conn = connexion_db()

            try:
                rows = conn.execute(
                    """
                    SELECT titre, statut, echeance
                    FROM tasks
                    WHERE owner=?
                    ORDER BY created_at DESC
                    LIMIT 30
                    """,
                    (owner,),
                ).fetchall()

            finally:
                conn.close()

        if not rows:
            return "Aucune tâche enregistrée."

        return "\n".join(
            f"• {r['titre']} — {r['statut']}"
            + (
                f" — échéance : {r['echeance']}"
                if r["echeance"]
                else ""
            )
            for r in rows
        )

    if cmd == "#memoire":
        mem = obtenir_memoire_utilisateur(
            owner,
            20,
        )

        if not mem:
            return "Aucune mémoire utilisateur enregistrée."

        return "\n".join(
            f"• {m['key']} : {m['value']}"
            for m in mem
        )

    return None


# ============================================================
# 11. IDENTITÉ
# ============================================================

def question_identite(
    text: str,
) -> bool:

    tl = minuscules(text)

    motifs = [
        "qui es tu",
        "qui es-tu",
        "qui t a cree",
        "qui t'as cree",
        "qui t a créé",
        "qui t'as créé",
        "ton createur",
        "ton créateur",
        "qui est ton createur",
        "qui est ton créateur",
        "qui est ton fondateur",
        "qui t a fonde",
        "qui t'as fonde",
        "qui t'a fonde",
        "date de creation",
        "date de création",
        "quand as tu ete cree",
        "quand as tu été créé",
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
        "Notre relation est définie symboliquement comme "
        "celle d'un père créateur ; elle n'est pas biologique."
    )


# ============================================================
# 12. EXEMPLES D'INTENTION
# ============================================================

def charger_exemples_intention() -> List[Dict[str, Any]]:

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
            "confidence": r["confidence"],
        }
        for r in rows
    ]


# ============================================================
# 13. DÉTECTION SOCIALE
# ============================================================

def detecter_social(
    text: str,
) -> Optional[str]:

    tl = minuscules(
        normaliser_texte(text)
    )

    tl = re.sub(
        r"[!?.,;:]+$",
        "",
        tl,
    ).strip()

    salutations = {
        "bonjour",
        "bonsoir",
        "salut",
        "hello",
        "hey",
        "yo",
        "bjr",
        "coucou",
    }

    if tl in salutations:
        return (
            "Bonjour ! 👋 "
            "Je suis ADRYNX. "
            "Que veux-tu faire ?"
        )

    if tl in {
        "ca va",
        "ca va",
        "comment vas tu",
        "comment vas-tu",
        "comment tu vas",
        "tu vas bien",
        "ça va",
        "ça va ?",
    }:
        return (
            "Je vais bien, merci ! "
            "Je suis prêt à continuer avec toi. "
            "Qu'est-ce qu'on fait maintenant ?"
        )

    if tl in {
        "tu fais quoi",
        "que fais tu",
        "qu est ce que tu fais",
    }:
        return (
            "Je suis là pour comprendre ta demande, "
            "raisonner dessus et t'aider à avancer."
        )

    return None


# ============================================================
# 14. DÉTECTION D'INTENTION CONTEXTUELLE
# ============================================================

def est_suivi_contextuel(
    text: str,
    etat: Dict[str, Any],
    historique: List[Dict[str, Any]],
) -> bool:

    tl = minuscules(text).strip()

    phrases = [
        "fais le",
        "fais-la",
        "fais-le",
        "continue",
        "continue ca",
        "continue ça",
        "vas-y",
        "ok fais",
        "maintenant",
        "celui-la",
        "celui-là",
        "celle-la",
        "celle-là",
        "ce projet",
        "cette partie",
        "la suite",
        "et maintenant",
        "oui fais",
    ]

    if any(
        phrase in tl
        for phrase in phrases
    ):
        return True

    if len(tokens(tl)) <= 5:
        if (
            etat.get("pending_question")
            or etat.get("subject")
            or len(historique) >= 2
        ):
            pronoms = {
                "oui",
                "non",
                "lui",
                "elle",
                "il",
                "ça",
                "ca",
                "celui",
                "celle",
                "ici",
                "maintenant",
            }

            if any(
                t in pronoms
                for t in tokens(tl)
            ):
                return True

    return False


def detecter_intention(
    text: str,
    etat: Optional[Dict[str, Any]] = None,
    historique: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, float]:

    text = normaliser_texte(text)

    if not text:
        return "inconnue", 0.2

    etat = etat or {}
    historique = historique or []

    tl = minuscules(text)
    ts = tokens(text)

    # --------------------------------------------------------
    # PRIORITÉ 1 : identité explicite
    # --------------------------------------------------------

    if question_identite(text):
        return "identite", 0.99

    # --------------------------------------------------------
    # PRIORITÉ 2 : commandes
    # --------------------------------------------------------

    if tl.startswith("#"):
        return "plateforme", 0.99

    # --------------------------------------------------------
    # PRIORITÉ 3 : social réel
    # --------------------------------------------------------

    social = detecter_social(text)

    if social:
        if any(
            x in tl
            for x in (
                "bonjour",
                "salut",
                "hello",
                "bonsoir",
                "coucou",
                "bjr",
                "yo",
            )
        ):
            return "salutation", 0.99

        return "conversation", 0.99

    # --------------------------------------------------------
    # PRIORITÉ 4 : suivi contextuel
    # --------------------------------------------------------

    if est_suivi_contextuel(
        text,
        etat,
        historique,
    ):
        return "suivi", 0.92

    # --------------------------------------------------------
    # EXEMPLES APPRIS
    # --------------------------------------------------------

    exemples = charger_exemples_intention()

    best_intent = "inconnue"
    best_score = 0.0

    for ex in exemples:

        intent = ex["intent"]

        if intent not in INTENTIONS:
            continue

        score = similarite(
            text,
            ex["phrase"],
        )

        confidence = float(
            ex["confidence"] or 0.5
        )

        score *= (
            0.75 + min(
                0.25,
                max(0.0, confidence) * 0.25,
            )
        )

        if score > best_score:
            best_score = score
            best_intent = intent

    if best_score >= 0.82:
        return (
            best_intent,
            min(0.95, best_score),
        )

    # --------------------------------------------------------
    # RÈGLES SÉMANTIQUES LÉGÈRES
    # --------------------------------------------------------

    if any(
        x in tl
        for x in (
            "explique",
            "expliquer",
            "pourquoi",
            "comment fonctionne",
            "c est quoi",
            "qu est ce que",
            "définition",
            "definition",
        )
    ):
        return "explication", 0.82

    if any(
        x in tl
        for x in (
            "code",
            "programme",
            "python",
            "javascript",
            "fastapi",
            "sql",
            "fonction",
            "bug",
            "erreur de code",
        )
    ):
        return "programmation", 0.82

    if any(
        x in tl
        for x in (
            "cherche",
            "recherche",
            "internet",
            "actualite",
            "actualité",
            "derniere version",
            "dernière version",
            "aujourd hui",
            "aujourd'hui",
            "actuellement",
        )
    ):
        return "recherche", 0.85

    if any(
        x in tl
        for x in (
            "compare",
            "comparaison",
            "difference entre",
            "différence entre",
        )
    ):
        return "comparaison", 0.82

    if any(
        x in tl
        for x in (
            "traduis",
            "traduire",
            "traduction",
        )
    ):
        return "traduction", 0.82

    if any(
        x in tl
        for x in (
            "corrige",
            "corriger",
            "correction",
        )
    ):
        return "correction", 0.82

    if any(
        x in tl
        for x in (
            "calcule",
            "combien font",
            "combien fait",
            "résous",
            "resous",
        )
    ):
        return "calcul", 0.85

    if any(
        x in tl
        for x in (
            "crée",
            "cree",
            "génère",
            "genere",
            "conçois",
            "concois",
            "dessine",
        )
    ):
        return "creation", 0.78

    if any(
        x in tl
        for x in (
            "que penses-tu",
            "qu en penses-tu",
            "ton avis",
            "opinion",
        )
    ):
        return "opinion", 0.78

    if any(
        x in tl
        for x in (
            "comment faire",
            "comment utiliser",
            "comment configurer",
            "donne-moi les étapes",
            "donne moi les etapes",
        )
    ):
        return "instruction", 0.8

    # --------------------------------------------------------
    # Calcul évident
    # --------------------------------------------------------

    if re.search(
        r"\d+\s*[\+\-\*\/\%]\s*\d+",
        text,
    ):
        return "calcul", 0.75

    # --------------------------------------------------------
    # Question factuelle
    # --------------------------------------------------------

    if (
        "?" in text
        and len(ts) <= 12
    ):
        return "factuelle", 0.65

    # --------------------------------------------------------
    # Message court mais non social
    # --------------------------------------------------------

    if len(ts) <= 3:
        return "conversation", 0.55

    # --------------------------------------------------------
    # FALLBACK GÉNÉRALISTE
    # --------------------------------------------------------

    return "inconnue", 0.35


# ============================================================
# 15. DÉTERMINATION DU MODE
# ============================================================

def determiner_mode(
    intent: str,
    text: str,
    etat: Dict[str, Any],
) -> str:

    mapping = {
        "salutation": "SOCIAL",
        "conversation": "SOCIAL",
        "suivi": "ASSISTANCE",
        "programmation": "TECHNIQUE",
        "calcul": "TECHNIQUE",
        "instruction": "TECHNIQUE",
        "explication": "PEDAGOGIQUE",
        "raisonnement": "PEDAGOGIQUE",
        "recherche": "RECHERCHE",
        "factuelle": "INFORMATIF",
        "creation": "CREATIF",
        "comparaison": "ANALYTIQUE",
        "opinion": "ANALYTIQUE",
        "identite": "DIALOGUE",
        "traduction": "ASSISTANCE",
        "correction": "ASSISTANCE",
        "clarification": "DIALOGUE",
        "ambiguite": "DIALOGUE",
    }

    if intent in mapping:
        return mapping[intent]

    return etat.get("mode") or "INFORMATIF"


# ============================================================
# 16. CALCUL SÉCURISÉ
# ============================================================

def calcul_securise(
    text: str,
) -> Optional[str]:

    try:

        expr = re.search(
            r"([\d\.\s\+\-\*\/\%\(\)\^]+)",
            text,
        )

        if not expr:
            return None

        code = expr.group(1).strip()

        if len(code) > 80:
            return None

        # ^ devient puissance Python.
        code = code.replace("^", "**")

        node = ast.parse(
            code,
            mode="eval",
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
        )

        for n in ast.walk(node):
            if not isinstance(n, allowed):
                return None

            if isinstance(n, ast.Constant):
                if not isinstance(
                    n.value,
                    (int, float),
                ):
                    return None

                if abs(n.value) > 10**12:
                    return None

        res = eval(
            compile(
                node,
                "<calc>",
                "eval",
            ),
            {"__builtins__": {}},
            {},
        )

        if isinstance(
            res,
            (int, float),
        ):
            if abs(res) > 10**15:
                return None

        return f"{code} = {res}"

    except Exception:
        return None


# ============================================================
# 17. MÉMOIRE UTILISATEUR
# ============================================================

def obtenir_memoire_utilisateur(
    owner: str,
    limit: int = MAX_MEMORY_RESULTS,
) -> List[Dict[str, Any]]:

    owner = owner_normalise(owner)

    limit = max(
        1,
        min(limit, 100),
    )

    with DB_LOCK:
        conn = connexion_db()

        try:
            rows = conn.execute(
                """
                SELECT memory_key,
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
                    limit,
                ),
            ).fetchall()

        finally:
            conn.close()

    return [
        {
            "key": r["memory_key"],
            "value": r["memory_value"],
            "category": r["category"],
            "confidence": r["confidence"],
        }
        for r in rows
    ]


def sauvegarder_memoire_utilisateur(
    owner: str,
    key: str,
    value: str,
    category: str = "user",
    confidence: float = 0.7,
    importance: float = 0.5,
):

    owner = owner_normalise(owner)

    key = normaliser_texte(key)[:120]
    value = normaliser_texte(value)[:500]

    if not key or not value:
        return

    confidence = max(
        0.0,
        min(1.0, float(confidence)),
    )

    importance = max(
        0.0,
        min(1.0, float(importance)),
    )

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
                    category=excluded.category,
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
                    now,
                ),
            )

            conn.commit()

        finally:
            conn.close()


# ============================================================
# 18. MÉMOIRE ÉPISODIQUE / ERREURS
# ============================================================

def sauvegarder_episodique(
    owner: str,
    event_type: str,
    content: str,
    importance: float = 0.5,
):

    owner = owner_normalise(owner)

    with DB_LOCK:
        conn = connexion_db()

        try:
            conn.execute(
                """
                INSERT INTO episodic_memory
                (owner, event_type, content, importance, created_at)
                VALUES (?,?,?,?,?)
                """,
                (
                    owner,
                    normaliser_texte(event_type)[:50],
                    normaliser_texte(content)[:1000],
                    max(0.0, min(1.0, importance)),
                    maintenant(),
                ),
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
    correction: str,
):

    owner = owner_normalise(owner)

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
                    normaliser_texte(error_type)[:100],
                    normaliser_texte(question)[:500],
                    normaliser_texte(bad_answer)[:500],
                    normaliser_texte(expected_mode)[:50],
                    normaliser_texte(actual_mode)[:50],
                    normaliser_texte(cause)[:500],
                    normaliser_texte(correction)[:500],
                    maintenant(),
                ),
            )

            conn.commit()

        finally:
            conn.close()


def rechercher_erreurs_similaires(
    question: str,
    owner: str,
) -> List[Dict[str, Any]]:

    owner = owner_normalise(owner)

    with DB_LOCK:
        conn = connexion_db()

        try:
            rows = conn.execute(
                """
                SELECT error_type,
                       question,
                       bad_answer,
                       expected_mode,
                       actual_mode,
                       cause,
                       correction
                FROM error_memory
                WHERE owner=?
                ORDER BY created_at DESC
                LIMIT 30
                """,
                (owner,),
            ).fetchall()

        finally:
            conn.close()

    resultats = []

    for r in rows:

        score_question = similarite(
            question,
            r["question"] or "",
        )

        score_cause = similarite(
            question,
            r["cause"] or "",
        )

        score = max(
            score_question,
            score_cause * 0.8,
        )

        if score >= 0.45:

            resultats.append(
                {
                    "error_type": r["error_type"],
                    "question": r["question"],
                    "bad_answer": r["bad_answer"],
                    "expected_mode": r["expected_mode"],
                    "actual_mode": r["actual_mode"],
                    "cause": r["cause"],
                    "correction": r["correction"],
                    "similarity": round(score, 3),
                }
            )

    resultats.sort(
        key=lambda x: x["similarity"],
        reverse=True,
    )

    return resultats[:5]


# ============================================================
# 19. EXEMPLES D'APPRENTISSAGE
# ============================================================

def rechercher_exemples_appris(
    question: str,
    intent: str,
    owner: str,
) -> List[Dict[str, Any]]:

    owner = owner_normalise(owner)

    with DB_LOCK:
        conn = connexion_db()

        try:
            rows = conn.execute(
                """
                SELECT question,
                       intent,
                       candidate,
                       approved_answer,
                       quality,
                       uses
                FROM learning_examples
                WHERE owner=? OR owner IS NULL
                ORDER BY quality DESC,
                         uses DESC,
                         created_at DESC
                LIMIT 40
                """,
                (owner,),
            ).fetchall()

        finally:
            conn.close()

    resultats = []

    for r in rows:

        score = similarite(
            question,
            r["question"] or "",
        )

        if r["intent"] == intent:
            score += 0.08

        if score >= 0.42:

            resultats.append(
                {
                    "question": r["question"],
                    "intent": r["intent"],
                    "candidate": r["candidate"],
                    "approved_answer": r["approved_answer"],
                    "quality": r["quality"],
                    "similarity": round(
                        min(score, 1.0),
                        3,
                    ),
                }
            )

    resultats.sort(
        key=lambda x: (
            x["similarity"],
            x["quality"] or 0,
        ),
        reverse=True,
    )

    return resultats[:MAX_LEARNING_RESULTS]


# ============================================================
# 20. RECHERCHE INTERNET
# ============================================================

def demande_recherche_web(
    question: str,
    intent: str,
    mode: str,
) -> bool:

    tl = minuscules(question)

    if mode == "SOCIAL":
        return False

    if intent in {
        "salutation",
        "conversation",
        "suivi",
    }:
        return False

    indicateurs = [
        "aujourd",
        "actuellement",
        "maintenant",
        "derniere",
        "dernière",
        "recent",
        "récent",
        "recente",
        "récente",
        "actualite",
        "actualité",
        "news",
        "prix actuel",
        "cours actuel",
        "version actuelle",
        "version la plus recente",
        "version la plus récente",
        "qui est actuellement",
        "où se trouve",
        "ou se trouve",
        "horaire",
        "horaires",
        "meteo",
        "météo",
    ]

    if any(
        x in tl
        for x in indicateurs
    ):
        return True

    if intent == "recherche":
        return True

    return False


def rechercher_internet(
    query: str,
    mode: str = "RECHERCHE",
) -> str:

    if mode == "SOCIAL":
        return ""

    query = normaliser_texte(query)[:200]

    if not query:
        return ""

    try:
        response = requests.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_html": 1,
            },
            headers=HEADERS,
            timeout=HTTP_TIMEOUT,
        )

        response.raise_for_status()

        data = response.json()

        results = []

        if data.get("AbstractText"):
            results.append(
                data["AbstractText"]
            )

        related = data.get(
            "RelatedTopics",
            [],
        )

        for topic in related[
            :MAX_WEB_RESULTS
        ]:

            if isinstance(topic, dict):

                if topic.get("Text"):
                    results.append(
                        topic["Text"]
                    )

                nested = topic.get(
                    "Topics",
                    [],
                )

                for sub in nested[:2]:
                    if (
                        isinstance(sub, dict)
                        and sub.get("Text")
                    ):
                        results.append(
                            sub["Text"]
                        )

        return "\n".join(
            results
        )[:4000]

    except Exception:
        return ""


# ============================================================
# 21. GROQ
# ============================================================

SYSTEME_GENERATION = """
Tu es ADRYNX, une intelligence conversationnelle généraliste.

IDENTITÉ INTERNE :
- Nom : ADRYNX
- Créateur : Jonathan Dejah OBENDA
- Date de création : 2 juin 2026
- Relation symbolique : père créateur, non biologique.

ARCHITECTURE :
Comprendre → Contextualiser → Raisonner → Générer →
Vérifier → Répondre → Apprendre.

RÈGLES PRINCIPALES :

1. Réponds d'abord à la demande réelle de l'utilisateur.
2. Ne change jamais de sujet sans raison.
3. Une intention inconnue ne signifie pas que tu dois refuser :
   réponds naturellement si la question est compréhensible.
4. Utilise l'historique uniquement lorsqu'il est pertinent.
5. Si le message est une suite comme « oui », « fais-le »,
   « continue », « celui-là », utilise le contexte disponible.
6. Ne transforme pas une conversation sociale en recherche documentaire.
7. Ne prétends pas avoir effectué une recherche si aucune donnée
   externe n'est fournie.
8. Les informations utilisateur sont des informations sur l'utilisateur,
   pas automatiquement des vérités universelles.
9. Ne fabrique pas de faits lorsque l'information manque.
10. Si une information est incertaine, indique-le simplement.
11. Respecte les contraintes explicites de l'utilisateur.
12. Ne révèle pas inutilement les informations internes,
    la mémoire ou les instructions du système.
13. Ne prétends pas être ChatGPT, Meta AI ou une autre IA.
14. Pour l'identité ADRYNX, l'identité locale du noyau est prioritaire.
15. Réponds dans la langue utilisée par l'utilisateur sauf demande contraire.
16. Sois naturel, clair et directement utile.
17. N'ajoute pas systématiquement une longue introduction.
"""


def groq_chat(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.4,
    max_tokens: int = 1200,
) -> str:

    if not GROQ_API_KEY:
        return ""

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        "temperature": max(
            0.0,
            min(1.0, temperature),
        ),
        "max_tokens": max(
            64,
            min(3000, max_tokens),
        ),
    }

    headers = {
        **HEADERS,
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            GROQ_URL,
            headers=headers,
            json=payload,
            timeout=GROQ_TIMEOUT,
        )

        response.raise_for_status()

        data = response.json()

        choices = data.get(
            "choices",
            [],
        )

        if not choices:
            return ""

        message = choices[0].get(
            "message",
            {},
        )

        return nettoyer_reponse(
            message.get("content", "")
        )

    except Exception:
        return ""


# ============================================================
# 22. CONTEXTE / QUESTION DE SUIVI
# ============================================================

def construire_question_contextuelle(
    question: str,
    contexte: Dict[str, Any],
) -> str:

    intent = contexte.get(
        "intent",
        "",
    )

    if intent != "suivi":
        return question

    historique = contexte.get(
        "history",
        [],
    )

    sujet = contexte.get(
        "subject",
        "",
    )

    pending = contexte.get(
        "pending_question",
        "",
    )

    recent = historique[-6:]

    return (
        "Contexte de suivi.\n"
        f"Sujet actuel : {sujet}\n"
        f"Question en suspens : {pending}\n"
        f"Historique récent : {json_safe(recent)}\n"
        f"Nouvelle instruction : {question}\n\n"
        "Comprends ce que l'utilisateur veut continuer "
        "avant de répondre."
    )


# ============================================================
# 23. GÉNÉRATION CANDIDAT
# ============================================================

def generer_candidat(
    question: str,
    contexte: Dict[str, Any],
) -> str:

    question_contextuelle = construire_question_contextuelle(
        question,
        contexte,
    )

    prompt = f"""
INTENTION :
{contexte.get("intent", "")}

CONFIANCE INTENTION :
{contexte.get("intent_confidence", 0)}

MODE :
{contexte.get("mode", "")}

SUJET :
{contexte.get("subject", "")}

ENTITÉS :
{json_safe(contexte.get("entities", []))}

CONTRAINTES :
{json_safe(contexte.get("constraints", []))}

MÉMOIRE UTILISATEUR :
{json_safe(contexte.get("memories", []))}

ERREURS PASSÉES À ÉVITER :
{json_safe(contexte.get("errors", []))}

EXEMPLES D'APPRENTISSAGE :
{json_safe(contexte.get("examples", []))}

INFORMATIONS EXTERNES :
{contexte.get("web", "")[:2500]}

HISTORIQUE :
{json_safe(contexte.get("history", [])[-6:])}

QUESTION UTILISATEUR :
{question_contextuelle}

Génère uniquement la réponse destinée à l'utilisateur.
Réponds directement à sa demande.
"""

    return groq_chat(
        SYSTEME_GENERATION,
        prompt,
        temperature=0.55,
        max_tokens=1400,
    )


# ============================================================
# 24. VALIDATION LOCALE DE PERTINENCE
# ============================================================

def valider_pertinence(
    question: str,
    reponse: str,
    intent: str,
    contexte: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:

    contexte = contexte or {}

    if not reponse:
        return False, "réponse vide"

    if len(reponse.strip()) < 4:
        return False, "réponse trop courte"

    # Ne pas accepter une simple copie de la question.
    if (
        similarite(
            question,
            reponse,
        ) > 0.94
        and len(question) > 20
    ):
        return False, "copie de la question"

    tl = minuscules(reponse)

    # Mauvaise identité.
    if (
        "je suis chatgpt" in tl
        or "je suis meta ai" in tl
        or "je suis gemini" in tl
        or "je suis claude" in tl
    ):
        return False, "identité externe"

    # Conversation sociale : détecter quelques réponses
    # manifestement hors sujet.
    if intent in {
        "salutation",
        "conversation",
    }:

        termes_hors_sujet = [
            "créé par jonathan",
            "créateur",
            "date de création",
            "python",
            "sqlite",
            "groq",
            "président",
            "politique",
        ]

        if any(
            terme in tl
            for terme in termes_hors_sujet
        ):
            return False, "réponse sociale hors sujet"

    # Identité.
    if intent == "identite":

        if (
            "jonathan dejah obenda"
            not in tl
            or "2 juin 2026"
            not in tl
        ):
            return False, "identité incomplète"

    return True, "ok"


# ============================================================
# 25. PARENT 1 — PERTINENCE / INTENTION
# ============================================================

PARENT_1_SYSTEM = """
Tu es PARENT 1 d'ADRYNX.

Ta mission est de vérifier uniquement la qualité cognitive
et la pertinence de la réponse.

Vérifie :
- l'intention réelle de l'utilisateur ;
- le sujet ;
- le contexte ;
- les contraintes ;
- le risque de hors-sujet ;
- la cohérence avec le dernier message.

Tu ne dois pas inventer de nouvelles informations.

Retourne STRICTEMENT un JSON :
{
  "decision": "PASS" ou "REVISE",
  "reason": "raison courte",
  "answer": "réponse corrigée"
}

Si la réponse est correcte, recopie-la dans answer.
"""


def appeler_parent_1(
    question: str,
    candidat: str,
    contexte: Dict[str, Any],
) -> Dict[str, Any]:

    prompt = f"""
QUESTION :
{question}

INTENTION :
{contexte.get("intent", "")}

MODE :
{contexte.get("mode", "")}

SUJET :
{contexte.get("subject", "")}

CONTRAINTES :
{json_safe(contexte.get("constraints", []))}

HISTORIQUE :
{json_safe(contexte.get("history", [])[-6:])}

CANDIDAT :
{candidat}
"""

    raw = groq_chat(
        PARENT_1_SYSTEM,
        prompt,
        temperature=0.1,
        max_tokens=1000,
    )

    if not raw:
        return {
            "decision": "PASS",
            "reason": "parent indisponible",
            "answer": candidat,
        }

    try:
        data = json.loads(raw)

        decision = str(
            data.get(
                "decision",
                "PASS",
            )
        ).upper()

        answer = nettoyer_reponse(
            data.get(
                "answer",
                candidat,
            )
        )

        return {
            "decision": (
                "REVISE"
                if decision == "REVISE"
                else "PASS"
            ),
            "reason": str(
                data.get(
                    "reason",
                    "",
                )
            )[:500],
            "answer": answer or candidat,
        }

    except Exception:
        return {
            "decision": "PASS",
            "reason": "format parent non exploitable",
            "answer": candidat,
        }


# ============================================================
# 26. PARENT 2 — FIABILITÉ / HALLUCINATION
# ============================================================

PARENT_2_SYSTEM = """
Tu es PARENT 2 d'ADRYNX.

Ta mission est de vérifier la fiabilité finale.

Vérifie :
- hallucinations évidentes ;
- contradictions avec le contexte fourni ;
- fausses affirmations sur l'identité ADRYNX ;
- invention de recherches ou de sources ;
- fuite d'informations privées ;
- cohérence générale ;
- niveau de certitude.

Tu ne dois pas transformer une réponse correcte
en une réponse inutilement différente.

Retourne STRICTEMENT un JSON :
{
  "decision": "PASS" ou "REVISE",
  "reason": "raison courte",
  "answer": "réponse corrigée"
}
"""


def appeler_parent_2(
    question: str,
    candidat: str,
    contexte: Dict[str, Any],
) -> Dict[str, Any]:

    prompt = f"""
QUESTION :
{question}

IDENTITÉ ADRYNX :
{json_safe(IDENTITE_ADRYNX)}

MÉMOIRE :
{json_safe(contexte.get("memories", []))}

INFORMATIONS WEB :
{contexte.get("web", "")[:2500]}

ERREURS CONNUES :
{json_safe(contexte.get("errors", []))}

RÉPONSE À VÉRIFIER :
{candidat}
"""

    raw = groq_chat(
        PARENT_2_SYSTEM,
        prompt,
        temperature=0.1,
        max_tokens=1000,
    )

    if not raw:
        return {
            "decision": "PASS",
            "reason": "parent indisponible",
            "answer": candidat,
        }

    try:
        data = json.loads(raw)

        decision = str(
            data.get(
                "decision",
                "PASS",
            )
        ).upper()

        answer = nettoyer_reponse(
            data.get(
                "answer",
                candidat,
            )
        )

        return {
            "decision": (
                "REVISE"
                if decision == "REVISE"
                else "PASS"
            ),
            "reason": str(
                data.get(
                    "reason",
                    "",
                )
            )[:500],
            "answer": answer or candidat,
        }

    except Exception:
        return {
            "decision": "PASS",
            "reason": "format parent non exploitable",
            "answer": candidat,
        }


# ============================================================
# 27. CONTRÔLE LOCAL FINAL
# ============================================================

def controle_local_final(
    question: str,
    reponse: str,
    contexte: Dict[str, Any],
) -> str:

    intent = contexte.get(
        "intent",
        "",
    )

    # L'identité du noyau ne dépend jamais de Groq.
    if intent == "identite":
        return reponse_identite_immuable()

    # Correction des identités externes.
    tl = minuscules(reponse)

    if (
        "je suis chatgpt" in tl
        or "je suis meta ai" in tl
        or "je suis gemini" in tl
        or "je suis claude" in tl
    ):
        return (
            re.sub(
                r"(?i)je suis chatgpt",
                "je suis ADRYNX",
                reponse,
            )
            .replace(
                "Meta AI",
                "ADRYNX",
            )
            .replace(
                "Gemini",
                "ADRYNX",
            )
            .replace(
                "Claude",
                "ADRYNX",
            )
        )

    return nettoyer_reponse(reponse)


# ============================================================
# 28. CONTRÔLE DOUBLE
# ============================================================

def controle_parents(
    question: str,
    reponse: str,
    contexte: Dict[str, Any],
) -> str:

    if not reponse:
        return (
            "Je n'ai pas réussi à produire une réponse "
            "fiable pour cette demande."
        )

    # Contrôle local immédiat.
    valide, raison = valider_pertinence(
        question,
        reponse,
        contexte.get("intent", ""),
        contexte,
    )

    candidat = reponse

    # Si problème local, on demande directement au Parent 1.
    if not valide:

        p1 = appeler_parent_1(
            question,
            candidat,
            contexte,
        )

        candidat = p1.get(
            "answer",
            candidat,
        )

    else:

        # Même quand la réponse semble bonne,
        # Parent 1 vérifie réellement.
        p1 = appeler_parent_1(
            question,
            candidat,
            contexte,
        )

        if p1.get("decision") == "REVISE":
            candidat = p1.get(
                "answer",
                candidat,
            )

    # Parent 2 vérifie ensuite le résultat.
    p2 = appeler_parent_2(
        question,
        candidat,
        contexte,
    )

    if p2.get("decision") == "REVISE":
        candidat = p2.get(
            "answer",
            candidat,
        )

    # Contrôle local final.
    candidat = controle_local_final(
        question,
        candidat,
        contexte,
    )

    # Si une correction parent a rendu la réponse
    # manifestement hors sujet, on conserve le candidat
    # original plutôt que d'envoyer une mauvaise réponse.
    valide_final, _ = valider_pertinence(
        question,
        candidat,
        contexte.get("intent", ""),
        contexte,
    )

    if not valide_final:

        if contexte.get("intent") in {
            "salutation",
            "conversation",
        }:
            social = detecter_social(question)

            if social:
                return social

        if contexte.get("intent") == "identite":
            return reponse_identite_immuable()

        return reponse or candidat

    return candidat


# ============================================================
# 29. RECHERCHE D'UN SUIVI
# ============================================================

def reconstruire_question_suivi(
    question: str,
    historique: List[Dict[str, Any]],
    etat: Dict[str, Any],
) -> str:

    if not est_suivi_contextuel(
        question,
        etat,
        historique,
    ):
        return question

    return construire_question_contextuelle(
        question,
        {
            "intent": "suivi",
            "subject": etat.get("subject", ""),
            "pending_question": etat.get(
                "pending_question",
                "",
            ),
            "history": historique,
        },
    )


# ============================================================
# 30. ADMINISTRATION
# ============================================================

def verifier_admin(
    secret: Optional[str],
) -> bool:

    if not ADMIN_SECRET:
        return False

    if not secret:
        return False

    try:
        return hmac.compare_digest(
            str(secret),
            str(ADMIN_SECRET),
        )
    except Exception:
        return False


def enregistrer_action_admin(
    user_id: str,
    action: str,
    objet: str,
    resultat: str,
    permission: str = "ADMIN",
):

    try:
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
                        user_id,
                        action,
                        objet,
                        resultat,
                        permission,
                        maintenant(),
                    ),
                )

                conn.commit()

            finally:
                conn.close()

    except Exception:
        pass


def commande_admin_locale(
    question: str,
) -> Optional[str]:

    tl = minuscules(
        normaliser_texte(question)
    )

    # Le secret admin n'est volontairement pas deviné
    # ou généré par l'IA.
    if not tl.startswith("admin "):
        return None

    # Cette commande est uniquement reconnue comme commande.
    # L'autorisation réelle doit être fournie via le mécanisme
    # admin de l'API / secret, pas par une chaîne tapée dans
    # une conversation publique.
    if "vider cache" in tl:
        return (
            "Commande administrateur détectée. "
            "Une authentification administrateur explicite "
            "est requise pour l'exécuter."
        )

    return (
        "Commande administrateur détectée, "
        "mais l'action demandée n'est pas disponible "
        "dans ce noyau."
    )


# ============================================================
# 31. PROJETS / TÂCHES
# ============================================================

def projects(
    owner: str,
) -> List[Dict[str, Any]]:

    owner = owner_normalise(owner)

    with DB_LOCK:
        conn = connexion_db()

        try:
            rows = conn.execute(
                """
                SELECT id,
                       nom,
                       objectif,
                       statut,
                       progression,
                       created_at,
                       updated_at
                FROM projects
                WHERE owner=?
                ORDER BY updated_at DESC
                LIMIT 100
                """,
                (owner,),
            ).fetchall()

        finally:
            conn.close()

    return [
        dict(row)
        for row in rows
    ]


def project(
    owner: str,
    nom: str,
    objectif: str = "",
) -> Dict[str, Any]:

    owner = owner_normalise(owner)

    project_id = str(uuid.uuid4())
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
                    project_id,
                    owner,
                    normaliser_texte(nom)[:200],
                    normaliser_texte(objectif)[:1000],
                    "actif",
                    0,
                    now,
                    now,
                ),
            )

            conn.commit()

        finally:
            conn.close()

    return {
        "id": project_id,
        "owner": owner,
        "nom": normaliser_texte(nom)[:200],
        "objectif": normaliser_texte(objectif)[:1000],
        "statut": "actif",
        "progression": 0,
    }


def task(
    owner: str,
    titre: str,
    project_id: Optional[str] = None,
) -> Dict[str, Any]:

    owner = owner_normalise(owner)

    task_id = str(uuid.uuid4())
    now = maintenant()

    if project_id:
        with DB_LOCK:
            conn = connexion_db()

            try:
                valid = conn.execute(
                    """
                    SELECT id
                    FROM projects
                    WHERE id=? AND owner=?
                    """,
                    (
                        project_id,
                        owner,
                    ),
                ).fetchone()

            finally:
                conn.close()

        if not valid:
            project_id = None

    with DB_LOCK:
        conn = connexion_db()

        try:
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
                    task_id,
                    project_id,
                    owner,
                    normaliser_texte(titre)[:300],
                    "a_faire",
                    None,
                    now,
                ),
            )

            conn.commit()

        finally:
            conn.close()

    return {
        "id": task_id,
        "project_id": project_id,
        "owner": owner,
        "titre": normaliser_texte(titre)[:300],
        "statut": "a_faire",
    }


# ============================================================
# 32. DASHBOARD
# ============================================================

def dashboard(
    owner: str,
) -> Dict[str, Any]:

    owner = owner_normalise(owner)

    with DB_LOCK:
        conn = connexion_db()

        try:

            projects_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM projects
                WHERE owner=?
                """,
                (owner,),
            ).fetchone()[0]

            tasks_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM tasks
                WHERE owner=?
                """,
                (owner,),
            ).fetchone()[0]

            memories_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM user_memory
                WHERE owner=?
                """,
                (owner,),
            ).fetchone()[0]

            conversations_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM conversations
                WHERE owner=?
                """,
                (owner,),
            ).fetchone()[0]

        finally:
            conn.close()

    return {
        "owner": owner,
        "projects": projects_count,
        "tasks": tasks_count,
        "memories": memories_count,
        "conversations": conversations_count,
    }


# ============================================================
# 33. FEEDBACK
# ============================================================

def enregistrer_feedback(
    owner: str,
    question: str,
    reponse: str,
    satisfait: bool,
    motif: str = "",
    commentaire: str = "",
    correction: str = "",
) -> Dict[str, Any]:

    owner = owner_normalise(owner)

    now = maintenant()

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
                    normaliser_texte(question)[:1000],
                    normaliser_texte(reponse)[:2000],
                    1 if satisfait else 0,
                    normaliser_texte(motif)[:300],
                    normaliser_texte(commentaire)[:1000],
                    now,
                ),
            )

            if not satisfait:

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
                        normaliser_texte(question)[:1000],
                        normaliser_texte(reponse)[:2000],
                        normaliser_texte(correction)[:2000],
                        normaliser_texte(motif)[:500],
                        "",
                        now,
                    ),
                )

            conn.commit()

        finally:
            conn.close()

    if not satisfait:
        sauvegarder_erreur(
            owner=owner,
            error_type="feedback_negatif",
            question=question,
            bad_answer=reponse,
            expected_mode="",
            actual_mode="",
            cause=motif or "réponse non satisfaisante",
            correction=correction or commentaire,
        )

    return {
        "ok": True,
        "learned": not satisfait,
    }


# ============================================================
# 34. APPRENTISSAGE VALIDÉ
# ============================================================

def apprendre_exemple_valide(
    owner: str,
    question: str,
    intent: str,
    contexte: Dict[str, Any],
    candidat: str,
    approved_answer: str,
    quality: float = 0.7,
):

    owner = owner_normalise(owner)

    # On n'enregistre pas tous les messages comme vérités.
    # Seulement les réponses ayant passé les contrôles.
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
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    owner,
                    normaliser_texte(question)[:1000],
                    intent,
                    json_safe({
                        "subject": contexte.get(
                            "subject",
                            "",
                        ),
                        "mode": contexte.get(
                            "mode",
                            "",
                        ),
                    }),
                    normaliser_texte(candidat)[:3000],
                    normaliser_texte(approved_answer)[:3000],
                    "parents_validated",
                    max(
                        0.0,
                        min(1.0, quality),
                    ),
                    0,
                    maintenant(),
                ),
            )

            conn.commit()

        finally:
            conn.close()


def apprendre_intention(
    question: str,
    intent: str,
    confidence: float,
):

    if (
        len(question) <= 12
        or intent not in INTENTIONS
        or confidence < 0.72
    ):
        return

    # Ne pas apprendre automatiquement une intention
    # faible ou inconnue.
    if intent == "inconnue":
        return

    try:
        with DB_LOCK:
            conn = connexion_db()

            try:
                conn.execute(
                    """
                    INSERT INTO intent_examples
                    (
                        phrase,
                        intent,
                        confidence,
                        source,
                        created_at
                    )
                    VALUES (?,?,?,?,?)
                    """,
                    (
                        question[:500],
                        intent,
                        confidence,
                        "validated_routing",
                        maintenant(),
                    ),
                )

                conn.commit()

            finally:
                conn.close()

    except Exception:
        pass


# ============================================================
# 35. STATS / EXPORT
# ============================================================

def stats_apprentissage() -> Dict[str, Any]:

    with DB_LOCK:
        conn = connexion_db()

        try:

            learning = conn.execute(
                "SELECT COUNT(*) FROM learning_examples"
            ).fetchone()[0]

            corrections = conn.execute(
                "SELECT COUNT(*) FROM response_corrections"
            ).fetchone()[0]

            errors = conn.execute(
                "SELECT COUNT(*) FROM error_memory"
            ).fetchone()[0]

            intents = conn.execute(
                "SELECT COUNT(*) FROM intent_examples"
            ).fetchone()[0]

            memories = conn.execute(
                "SELECT COUNT(*) FROM user_memory"
            ).fetchone()[0]

            conversations = conn.execute(
                "SELECT COUNT(*) FROM conversations"
            ).fetchone()[0]

        finally:
            conn.close()

    return {
        "learning_examples": learning,
        "response_corrections": corrections,
        "error_memory": errors,
        "intent_examples": intents,
        "user_memory": memories,
        "conversations": conversations,
    }


def exporter_apprentissage() -> List[Dict[str, Any]]:

    with DB_LOCK:
        conn = connexion_db()

        try:
            rows = conn.execute(
                """
                SELECT owner,
                       question,
                       intent,
                       candidate,
                       approved_answer,
                       source,
                       quality,
                       uses,
                       created_at
                FROM learning_examples
                ORDER BY created_at ASC
                """
            ).fetchall()

        finally:
            conn.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# 36. PIPELINE PRINCIPAL
# ============================================================

def pipeline_adrynx(
    question: str,
    owner: str = "anon",
    conv_id: Optional[str] = None,
) -> Dict[str, Any]:

    owner = owner_normalise(owner)

    question = normaliser_texte(question)

    if not question:
        return {
            "reponse": "Pose ta question.",
            "conv_id": conv_id or "",
            "intent": "vide",
            "mode": "SOCIAL",
        }

    # --------------------------------------------------------
    # Conversation
    # --------------------------------------------------------

    conv_id = verifier_conversation(
        conv_id,
        owner,
    )

    # --------------------------------------------------------
    # Commandes plateforme
    # --------------------------------------------------------

    if est_commande_plateforme(question):

        response = executer_commande_plateforme(
            question,
            owner,
            conv_id,
        )

        if response:

            enregistrer_message(
                conv_id,
                "user",
                question,
            )

            enregistrer_message(
                conv_id,
                "assistant",
                response,
            )

            return {
                "reponse": response,
                "conv_id": conv_id,
                "intent": "plateforme",
                "mode": "ASSISTANCE",
            }

    # --------------------------------------------------------
    # Commandes admin : détectées séparément
    # --------------------------------------------------------

    admin_response = commande_admin_locale(
        question
    )

    if admin_response:

        enregistrer_message(
            conv_id,
            "user",
            question,
        )

        enregistrer_message(
            conv_id,
            "assistant",
            admin_response,
        )

        return {
            "reponse": admin_response,
            "conv_id": conv_id,
            "intent": "plateforme",
            "mode": "TECHNIQUE",
        }

    # --------------------------------------------------------
    # Historique + état AVANT intention
    # --------------------------------------------------------

    historique = derniers_messages(
        conv_id,
        MAX_CONTEXT_MESSAGES,
    )

    etat = obtenir_etat_conversation(
        conv_id
    )

    # --------------------------------------------------------
    # Intention contextuelle
    # --------------------------------------------------------

    intent, conf_intent = detecter_intention(
        question,
        etat,
        historique,
    )

    mode = determiner_mode(
        intent,
        question,
        etat,
    )

    # --------------------------------------------------------
    # Identité : contrôle local absolu
    # --------------------------------------------------------

    if intent == "identite":

        response = reponse_identite_immuable()

        enregistrer_message(
            conv_id,
            "user",
            question,
        )

        enregistrer_message(
            conv_id,
            "assistant",
            response,
        )

        mettre_a_jour_etat(
            conv_id,
            subject="identité ADRYNX",
            intent=intent,
            mode=mode,
            entities_json=extraire_entites(question),
            constraints_json=extraire_contraintes(question),
        )

        BUS.emit(
            "identity_asked",
            {
                "owner": owner,
                "conv_id": conv_id,
            },
        )

        return {
            "reponse": response,
            "conv_id": conv_id,
            "intent": intent,
            "mode": mode,
        }

    # --------------------------------------------------------
    # Social : contrôle local immédiat
    # --------------------------------------------------------

    social = detecter_social(
        question
    )

    if social:

        enregistrer_message(
            conv_id,
            "user",
            question,
        )

        enregistrer_message(
            conv_id,
            "assistant",
            social,
        )

        mettre_a_jour_etat(
            conv_id,
            subject="conversation",
            intent=intent,
            mode="SOCIAL",
            entities_json=[],
            constraints_json=extraire_contraintes(question),
            pending_question="",
        )

        BUS.emit(
            "message_processed",
            {
                "conv_id": conv_id,
                "intent": intent,
                "mode": "SOCIAL",
                "owner": owner,
            },
        )

        return {
            "reponse": social,
            "conv_id": conv_id,
            "intent": intent,
            "mode": "SOCIAL",
        }

    # --------------------------------------------------------
    # Calcul local
    # --------------------------------------------------------

    if intent == "calcul":

        calc = calcul_securise(
            question
        )

        if calc:

            enregistrer_message(
                conv_id,
                "user",
                question,
            )

            enregistrer_message(
                conv_id,
                "assistant",
                calc,
            )

            mettre_a_jour_etat(
                conv_id,
                subject="calcul",
                intent=intent,
                mode="TECHNIQUE",
                entities_json=[],
                constraints_json=extraire_contraintes(
                    question
                ),
            )

            return {
                "reponse": calc,
                "conv_id": conv_id,
                "intent": intent,
                "mode": "TECHNIQUE",
            }

    # --------------------------------------------------------
    # Extraction contexte
    # --------------------------------------------------------

    sujet_question = extraire_sujet(
        question
    )

    sujet = (
        sujet_question
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

    # --------------------------------------------------------
    # Mémoire
    # --------------------------------------------------------

    memoires = obtenir_memoire_utilisateur(
        owner
    )

    erreurs_sim = rechercher_erreurs_similaires(
        question,
        owner,
    )

    exemples_appris = rechercher_exemples_appris(
        question,
        intent,
        owner,
    )

    # --------------------------------------------------------
    # Recherche externe seulement si nécessaire
    # --------------------------------------------------------

    web_ctx = ""

    if demande_recherche_web(
        question,
        intent,
        mode,
    ):
        web_ctx = rechercher_internet(
            question,
            mode,
        )

    # --------------------------------------------------------
    # Contexte complet
    # --------------------------------------------------------

    contexte_gen = {
        "intent": intent,
        "intent_confidence": conf_intent,
        "mode": mode,
        "subject": sujet,
        "objective": etat.get(
            "objective",
            "",
        ),
        "entities": entites,
        "constraints": contraintes,
        "memories": memoires,
        "errors": erreurs_sim,
        "examples": exemples_appris,
        "web": web_ctx,
        "history": historique,
        "owner": owner,
        "pending_question": etat.get(
            "pending_question",
            "",
        ),
    }

    # --------------------------------------------------------
    # Génération
    # --------------------------------------------------------

    candidat = generer_candidat(
        question,
        contexte_gen,
    )

    # --------------------------------------------------------
    # Fallback si Groq indisponible
    # --------------------------------------------------------

    if not candidat:

        if web_ctx:
            candidat = (
                "J'ai trouvé ces informations externes :\n\n"
                + web_ctx[:3000]
            )

        elif erreurs_sim:

            candidat = (
                "Je n'ai pas réussi à générer une réponse "
                "fiable cette fois-ci. Je préfère ne pas "
                "inventer une réponse."
            )

        else:

            candidat = (
                "Je n'ai pas réussi à générer une réponse "
                "pour cette demande. Réessaie avec une "
                "formulation légèrement différente."
            )

    # --------------------------------------------------------
    # PARENTS IA
    # --------------------------------------------------------

    reponse_finale = controle_parents(
        question,
        candidat,
        contexte_gen,
    )

    # --------------------------------------------------------
    # Mise à jour de l'état
    # --------------------------------------------------------

    mettre_a_jour_etat(
        conv_id,
        subject=sujet[:200],
        objective=etat.get(
            "objective",
            "",
        )[:200],
        intent=intent,
        mode=mode,
        entities_json=entites,
        constraints_json=contraintes,
        pending_question=pending_q[:200],
    )

    # --------------------------------------------------------
    # Historique
    # --------------------------------------------------------

    enregistrer_message(
        conv_id,
        "user",
        question,
    )

    enregistrer_message(
        conv_id,
        "assistant",
        reponse_finale,
    )

    # --------------------------------------------------------
    # Apprentissage intention
    # uniquement si confiance suffisante
    # --------------------------------------------------------

    apprendre_intention(
        question,
        intent,
        conf_intent,
    )

    # --------------------------------------------------------
    # Exemple d'apprentissage validé
    # --------------------------------------------------------

    apprendre_exemple_valide(
        owner,
        question,
        intent,
        contexte_gen,
        candidat,
        reponse_finale,
        quality=0.8,
    )

    # --------------------------------------------------------
    # Événement
    # --------------------------------------------------------

    BUS.emit(
        "message_processed",
        {
            "conv_id": conv_id,
            "intent": intent,
            "mode": mode,
            "owner": owner,
        },
    )

    return {
        "reponse": reponse_finale,
        "conv_id": conv_id,
        "intent": intent,
        "mode": mode,
    }


# ============================================================
# 37. COMPATIBILITÉ API
# ============================================================

def traiter_question(
    question: str,
    owner: str = "anon",
    conv_id: Optional[str] = None,
) -> Dict[str, Any]:

    return pipeline_adrynx(
        question,
        owner,
        conv_id,
    )


# ============================================================
# FIN DU NOYAU ADRYNX
#
# IMPORTANT :
# FastAPI n'est volontairement PAS défini ici.
# api.py constitue la couche HTTP.
# ============================================================
