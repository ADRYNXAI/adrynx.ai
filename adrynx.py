# ============================================================
# 20. PARENTS IA — SYSTÈME DE SUPERVISION COGNITIVE
# ============================================================
#
# ADRYNX possède plusieurs "parents IA" spécialisés.
#
# Ils ne constituent pas des personnes réelles.
# Ce sont des rôles cognitifs distincts utilisant le moteur
# IA configuré par ADRYNX.
#
# Leur travail :
#
# ADRYNX
#   ↓
# réponse candidate
#   ↓
# Parent Logique
# Parent Vérificateur
# Parent Contexte
# Parent Sécurité
#   ↓
# synthèse
#   ↓
# réponse finale
#
# IMPORTANT :
# Les parents ne modifient pas directement la mémoire
# permanente. Une correction parentale n'est pas considérée
# automatiquement comme une nouvelle vérité.
#
# L'apprentissage permanent passe par les mécanismes
# d'apprentissage et de feedback d'ADRYNX.
# ============================================================


PARENTS_IA = {
    "logique": {
        "nom": "Parent Logique",
        "mission": (
            "Vérifier que la réponse répond réellement "
            "à la question et qu'elle ne contient pas "
            "de raisonnement incohérent."
        ),
    },

    "verificateur": {
        "nom": "Parent Vérificateur",
        "mission": (
            "Rechercher les contradictions, inventions "
            "évidentes et affirmations insuffisamment "
            "justifiées."
        ),
    },

    "contexte": {
        "nom": "Parent Contexte",
        "mission": (
            "Vérifier que la réponse respecte la question "
            "actuelle, l'historique pertinent et le mode "
            "conversationnel détecté."
        ),
    },

    "securite": {
        "nom": "Parent Sécurité",
        "mission": (
            "Vérifier la confidentialité, l'identité "
            "d'ADRYNX et l'absence de divulgation inutile "
            "de données privées."
        ),
    },
}


PARENTS_SYSTEME = """
Tu es un parent IA superviseur d'ADRYNX.

Tu n'es pas ADRYNX et tu ne dois pas répondre à la place
d'ADRYNX sauf si une correction est nécessaire.

Tu dois examiner une réponse candidate.

RÈGLES :

1. Vérifie la question exacte.
2. Vérifie que la réponse traite cette question.
3. Ne change jamais de sujet.
4. Ne fabrique pas de faits.
5. Ne transforme pas une hypothèse en certitude.
6. Respecte le contexte réellement fourni.
7. Ne révèle pas inutilement de données privées.
8. ADRYNX doit rester ADRYNX.
9. Une conversation sociale doit rester sociale.
10. Une demande technique doit rester technique.
11. Une demande de recherche ne doit pas être présentée
    comme vérifiée si aucune source externe n'a réellement
    été consultée.
12. Ne prétends jamais qu'une action a été effectuée si
    elle ne l'a pas été.

Retourne uniquement un objet JSON valide.

Format :

{
  "valide": true,
  "problemes": [],
  "correction": "",
  "confiance": 0.0
}

Si la réponse est correcte :

{
  "valide": true,
  "problemes": [],
  "correction": "",
  "confiance": 0.95
}

Si elle doit être corrigée :

{
  "valide": false,
  "problemes": ["..."],
  "correction": "réponse corrigée",
  "confiance": 0.90
}
"""


def parser_parent_json(
    text: str
) -> Dict[str, Any]:

    if not text:
        return {
            "valide": False,
            "problemes": ["réponse parent vide"],
            "correction": "",
            "confiance": 0.0,
        }

    text = text.strip()

    try:
        data = json.loads(text)

        if isinstance(data, dict):
            return {
                "valide": bool(
                    data.get("valide", False)
                ),
                "problemes": (
                    data.get("problemes", [])
                    if isinstance(
                        data.get("problemes", []),
                        list
                    )
                    else []
                ),
                "correction": normaliser_texte(
                    data.get("correction", "")
                ),
                "confiance": float(
                    data.get("confiance", 0.0)
                ),
            }

    except Exception:
        pass

    # Tentative de récupération si le modèle a entouré
    # le JSON avec du texte ou des balises.
    match = re.search(
        r"\{.*\}",
        text,
        flags=re.DOTALL
    )

    if match:

        try:

            data = json.loads(
                match.group(0)
            )

            return {
                "valide": bool(
                    data.get("valide", False)
                ),
                "problemes": (
                    data.get("problemes", [])
                    if isinstance(
                        data.get("problemes", []),
                        list
                    )
                    else []
                ),
                "correction": normaliser_texte(
                    data.get("correction", "")
                ),
                "confiance": float(
                    data.get("confiance", 0.0)
                ),
            }

        except Exception:
            pass

    return {
        "valide": False,
        "problemes": [
            "réponse parent non structurée"
        ],
        "correction": "",
        "confiance": 0.0,
    }


def appeler_parent_ia(
    parent_id: str,
    question: str,
    candidat: str,
    contexte: Dict[str, Any]
) -> Dict[str, Any]:

    parent = PARENTS_IA.get(
        parent_id
    )

    if not parent:
        return {
            "parent": parent_id,
            "valide": False,
            "problemes": [
                "parent inconnu"
            ],
            "correction": "",
            "confiance": 0.0,
        }

    prompt = f"""
RÔLE DU PARENT :
{parent["nom"]}

MISSION :
{parent["mission"]}

QUESTION DE L'UTILISATEUR :
{question}

RÉPONSE CANDIDATE D'ADRYNX :
{candidat}

INTENTION :
{contexte.get("intent", "")}

MODE :
{contexte.get("mode", "")}

SUJET :
{contexte.get("subject", "")}

HISTORIQUE PERTINENT :
{json_safe(contexte.get("history", [])[-6:])}

INFORMATIONS EXTERNES RÉELLEMENT DISPONIBLES :
{contexte.get("web", "")[:2500]}

EXEMPLES APPRIS :
{json_safe(contexte.get("examples", []))}

ERREURS SIMILAIRES :
{json_safe(contexte.get("errors", []))}

Analyse uniquement selon ta mission.
"""

    resultat = groq_chat(
        PARENTS_SYSTEME,
        prompt,
        temperature=0.1,
        max_tokens=900
    )

    controle = parser_parent_json(
        resultat
    )

    controle["parent"] = parent_id

    return controle


def controle_noyau(
    question: str,
    reponse: str,
    intent: str
) -> Tuple[bool, str]:

    if not reponse:
        return False, "réponse vide"

    if len(reponse.strip()) < 3:
        return False, "réponse trop courte"

    if (
        len(question) > 25
        and similarite(
            question,
            reponse
        ) > 0.92
    ):
        return False, "copie de la question"

    if intent == "identite":

        if (
            "Jonathan Dejah OBENDA"
            not in reponse
            or "2 juin 2026"
            not in reponse
        ):
            return False, "identité ADRYNX incorrecte"

    low = minuscules(reponse)

    autres_ia = [
        "je suis chatgpt",
        "je suis meta ai",
        "je suis gemini",
        "je suis claude",
    ]

    if any(
        x in low
        for x in autres_ia
    ):
        return False, "identité d'une autre IA"

    if intent in (
        "salutation",
        "conversation"
    ):

        mauvais = [
            "duckduckgo",
            "recherche internet",
            "source externe",
            "historique technique",
        ]

        if any(
            x in low
            for x in mauvais
        ):
            return False, "réponse sociale hors contexte"

    return True, "ok"


def controler_parent(
    question: str,
    candidat: str,
    contexte: Dict[str, Any]
) -> Dict[str, Any]:

    intent = contexte.get(
        "intent",
        "inconnue"
    )

    # L'identité fondamentale d'ADRYNX
    # est contrôlée directement par le noyau.
    if intent == "identite":

        return {
            "reponse": reponse_identite_immuable(),
            "valide": True,
            "parents": [],
            "corrections": [],
        }

    valide_noyau, raison = controle_noyau(
        question,
        candidat,
        intent
    )

    if not valide_noyau:

        candidat_original = candidat

    else:

        candidat_original = candidat

    rapports = []

    # --------------------------------------------------------
    # PARENT 1 — LOGIQUE
    # --------------------------------------------------------

    logique = appeler_parent_ia(
        "logique",
        question,
        candidat_original,
        contexte
    )

    rapports.append(logique)

    # --------------------------------------------------------
    # PARENT 2 — VÉRIFICATION
    # --------------------------------------------------------

    verificateur = appeler_parent_ia(
        "verificateur",
        question,
        candidat_original,
        contexte
    )

    rapports.append(verificateur)

    # --------------------------------------------------------
    # PARENT 3 — CONTEXTE
    # --------------------------------------------------------

    parent_contexte = appeler_parent_ia(
        "contexte",
        question,
        candidat_original,
        contexte
    )

    rapports.append(parent_contexte)

    # --------------------------------------------------------
    # PARENT 4 — SÉCURITÉ
    # --------------------------------------------------------

    securite = appeler_parent_ia(
        "securite",
        question,
        candidat_original,
        contexte
    )

    rapports.append(securite)

    corrections = [
        r.get("correction", "")
        for r in rapports
        if r.get("correction")
        and r.get("correction") != candidat_original
    ]

    problemes = []

    for rapport in rapports:

        for probleme in rapport.get(
            "problemes",
            []
        ):

            if probleme not in problemes:
                problemes.append(
                    str(probleme)
                )

    # --------------------------------------------------------
    # CONSENSUS
    # --------------------------------------------------------

    parents_valides = sum(
        1
        for r in rapports
        if r.get("valide") is True
    )

    confiance_moyenne = (
        sum(
            float(
                r.get(
                    "confiance",
                    0.0
                )
            )
            for r in rapports
        )
        / len(rapports)
        if rapports
        else 0.0
    )

    reponse = candidat_original

    # Si la majorité des parents considère
    # la réponse correcte, elle est conservée.
    if parents_valides >= 3:

        reponse = candidat_original

    # Si plusieurs parents proposent une correction,
    # on recherche une correction commune.
    elif corrections:

        compteur = {}

        for correction in corrections:

            cle = normaliser_texte(
                correction
            )

            if cle:
                compteur[cle] = (
                    compteur.get(cle, 0)
                    + 1
                )

        if compteur:

            correction_majoritaire = max(
                compteur.items(),
                key=lambda item: item[1]
            )

            # Une correction proposée par au moins
            # deux parents est considérée comme suffisamment
            # convergente pour remplacer le candidat.
            if correction_majoritaire[1] >= 2:

                reponse = correction_majoritaire[0]

            elif confiance_moyenne >= 0.85:

                reponse = corrections[0]

    # --------------------------------------------------------
    # SECOND CONTRÔLE DU NOYAU
    # --------------------------------------------------------

    valide_final, raison_finale = (
        controle_noyau(
            question,
            reponse,
            intent
        )
    )

    if not valide_final:

        # Si les parents n'ont pas réussi à corriger
        # proprement, on conserve une réponse sûre
        # plutôt que d'inventer.
        if intent in (
            "salutation",
            "conversation"
        ):
            reponse = reponse_sociale(
                question
            )

        elif not reponse.strip():

            reponse = (
                "Je n'ai pas pu produire une "
                "réponse suffisamment fiable."
            )

    return {
        "reponse": reponse,
        "valide": valide_final,
        "parents": [
            {
                "parent": r.get("parent"),
                "valide": r.get("valide"),
                "confiance": r.get("confiance"),
                "problemes": r.get(
                    "problemes",
                    []
                ),
            }
            for r in rapports
        ],
        "corrections": corrections,
        "problemes": problemes,
        "confiance": confiance_moyenne,
        "raison_noyau": raison_finale,
    }


# Compatibilité avec l'ancien nom.
def controle_parents(
    question: str,
    reponse: str,
    contexte: Dict[str, Any]
) -> str:

    resultat = controler_parent(
        question,
        reponse,
        contexte
    )

    return resultat["reponse"]
