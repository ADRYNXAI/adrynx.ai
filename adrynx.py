ponse(final),
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
