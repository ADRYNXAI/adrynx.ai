
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
