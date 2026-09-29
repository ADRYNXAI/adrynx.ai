"""
ADRYNX - verification.py
Vérification du numéro de téléphone par SMS uniquement.

Compatible avec adrynx.py / api.py.
Telegram n'est pas utilisé.

Variables Render :
- ADRYNX_SESSION_SECRET
- ADRYNX_PREFIXES_AUTORISES (défaut : +242)
- ADRYNX_SMS_MAX_PAR_JOUR (défaut : 150)
- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- TWILIO_FROM
  OU
- TWILIO_MESSAGING_SERVICE_SID
"""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time

import requests


# ============================================================
# CONFIGURATION
# ============================================================

VERROU = threading.Lock()

DUREE_SESSION_JOURS = 90
DUREE_CODE = 300          # 5 minutes
ESSAIS_MAX = 5
DELAI_ENTRE_ENVOIS = 60  # 1 minute
ENVOIS_MAX_PAR_HEURE = 5


# OTP et limites restent en mémoire.
# Aucun code OTP n'est enregistré en clair.
_otp = {}
_envois = {}

_sms_du_jour = {
    "jour": "",
    "n": 0,
}


# ============================================================
# SECRET DE SESSION
# ============================================================

def _secret_session():
    """
    Récupère le secret utilisé pour signer les sessions.

    32 caractères ou plus sont recommandés.
    """
    secret = os.environ.get(
        "ADRYNX_SESSION_SECRET",
        "",
    )

    if len(secret) < 16:
        return None

    return secret.encode("utf-8")


# ============================================================
# INDICATIFS AUTORISÉS
# ============================================================

def prefixes_autorises():
    """
    Par défaut, ADRYNX accepte les numéros de la République du Congo.

    Exemple :
        +242
    """

    brut = os.environ.get(
        "ADRYNX_PREFIXES_AUTORISES",
        "+242",
    )

    prefixes = []

    for prefixe in brut.split(","):
        prefixe = prefixe.strip()

        if re.fullmatch(
            r"\+\d{1,4}",
            prefixe,
        ):
            prefixes.append(prefixe)

    return tuple(prefixes)


# ============================================================
# CONFIGURATION SMS
# ============================================================

def sms_configure():
    """
    Vérifie que Twilio et le secret de session sont configurés.
    """

    sid = os.environ.get(
        "TWILIO_ACCOUNT_SID"
    )

    auth = os.environ.get(
        "TWILIO_AUTH_TOKEN"
    )

    expediteur = (
        os.environ.get("TWILIO_FROM")
        or
        os.environ.get(
            "TWILIO_MESSAGING_SERVICE_SID"
        )
    )

    return bool(
        sid
        and auth
        and expediteur
        and _secret_session()
    )


def verification_active():
    """
    True si la vérification SMS peut fonctionner.
    """

    return sms_configure()


def canaux_disponibles():
    """
    Retourne les canaux réellement disponibles.

    Telegram est volontairement absent.
    """

    if sms_configure():
        return ["sms"]

    return []


# ============================================================
# NORMALISATION DU NUMÉRO
# ============================================================

def normaliser_telephone(saisie):
    """
    Convertit un numéro vers un format international.

    Exemple :

        +242 06 123 45 67

    devient :

        +242061234567
    """

    if not isinstance(
        saisie,
        str,
    ):
        return None

    numero = re.sub(
        r"[\s.\-()]",
        "",
        saisie.strip(),
    )

    if not re.fullmatch(
        r"\+\d{8,15}",
        numero,
    ):
        return None

    prefixes = prefixes_autorises()

    if prefixes and not numero.startswith(
        prefixes
    ):
        return None

    return numero


# ============================================================
# VÉRIFICATION D'UN NUMÉRO BLOQUÉ
# ============================================================

def _est_bloque(tel):
    """
    Utilise la fonction est_bloque() du noyau ADRYNX
    sans créer de problème d'import circulaire.
    """

    try:
        from adrynx import est_bloque

        return bool(
            est_bloque(tel)
        )

    except Exception:
        return False


# ============================================================
# BASE64
# ============================================================

def _b64(data):
    return base64.urlsafe_b64encode(
        data
    ).rstrip(b"=").decode("ascii")


def _unb64(value):
    padding = "=" * (
        -len(value) % 4
    )

    return base64.urlsafe_b64decode(
        value + padding
    )


# ============================================================
# CRÉATION DU TOKEN DE SESSION
# ============================================================

def creer_token(tel):
    """
    Crée un token de session signé avec HMAC-SHA256.

    Le token reste valide 90 jours.
    """

    cle = _secret_session()

    tel = normaliser_telephone(tel)

    if not cle:
        return None

    if not tel:
        return None

    if _est_bloque(tel):
        return None

    maintenant = int(
        time.time()
    )

    donnees = {
        "v": 1,
        "t": tel,
        "iat": maintenant,
        "exp": (
            maintenant
            + DUREE_SESSION_JOURS * 86400
        ),
    }

    charge = _b64(
        json.dumps(
            donnees,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    )

    signature = _b64(
        hmac.new(
            cle,
            charge.encode("ascii"),
            hashlib.sha256,
        ).digest()
    )

    return (
        f"v1.{charge}.{signature}"
    )


# ============================================================
# LECTURE / VALIDATION DU TOKEN
# ============================================================

def lire_token(token):
    """
    Vérifie un token de session.

    Retourne le numéro de téléphone
    si le token est valide.

    Sinon :
        None
    """

    cle = _secret_session()

    if not cle:
        return None

    if not isinstance(
        token,
        str,
    ):
        return None

    if len(token) > 4096:
        return None

    try:
        morceaux = token.split(".")

        if len(morceaux) != 3:
            return None

        version = morceaux[0]
        charge = morceaux[1]
        signature = morceaux[2]

        if version != "v1":
            return None

        signature_attendue = _b64(
            hmac.new(
                cle,
                charge.encode("ascii"),
                hashlib.sha256,
            ).digest()
        )

        if not hmac.compare_digest(
            signature,
            signature_attendue,
        ):
            return None

        donnees = json.loads(
            _unb64(
                charge
            ).decode("utf-8")
        )

        if donnees.get("v") != 1:
            return None

        tel = normaliser_telephone(
            donnees.get(
                "t",
                "",
            )
        )

        if not tel:
            return None

        iat = int(
            donnees.get(
                "iat",
                0,
            )
        )

        exp = int(
            donnees.get(
                "exp",
                0,
            )
        )

        maintenant = int(
            time.time()
        )

        if not iat or not exp:
            return None

        if maintenant < iat:
            return None

        if maintenant >= exp:
            return None

        duree_max = (
            DUREE_SESSION_JOURS
            * 86400
            + 60
        )

        if exp - iat > duree_max:
            return None

        if _est_bloque(tel):
            return None

        return tel

    except Exception:
        return None


# ============================================================
# HASH DU CODE OTP
# ============================================================

def _hash_code(
    tel,
    code,
):
    """
    Ne conserve jamais le code OTP en clair.
    """

    cle = _secret_session()

    if not cle:
        return None

    message = (
        f"otp|{tel}|{code}"
    )

    return hmac.new(
        cle,
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# ============================================================
# NETTOYAGE
# ============================================================

def _nettoyer():
    """
    Supprime les OTP expirés et les anciens
    compteurs horaires.
    """

    maintenant = time.time()

    for tel in list(
        _otp.keys()
    ):
        entree = _otp.get(tel)

        if not entree:
            continue

        if maintenant >= entree.get(
            "expire",
            0,
        ):
            _otp.pop(
                tel,
                None,
            )

    for tel in list(
        _envois.keys()
    ):
        anciens = [
            instant
            for instant in _envois[tel]
            if maintenant - instant < 3600
        ]

        if anciens:
            _envois[tel] = anciens

        else:
            _envois.pop(
                tel,
                None,
            )


# ============================================================
# ENVOI SMS TWILIO
# ============================================================

def envoyer_sms(
    tel,
    texte,
):
    """
    Envoie un SMS via Twilio.

    Retour :

        (True, None)

    ou :

        (False, erreur)
    """

    if not sms_configure():
        return (
            False,
            "SMS non configuré.",
        )

    sid = os.environ.get(
        "TWILIO_ACCOUNT_SID",
        "",
    )

    auth = os.environ.get(
        "TWILIO_AUTH_TOKEN",
        "",
    )

    donnees = {
        "To": tel,
        "Body": texte,
    }

    messaging_service = os.environ.get(
        "TWILIO_MESSAGING_SERVICE_SID"
    )

    twilio_from = os.environ.get(
        "TWILIO_FROM"
    )

    if messaging_service:

        donnees[
            "MessagingServiceSid"
        ] = messaging_service

    elif twilio_from:

        donnees[
            "From"
        ] = twilio_from

    else:

        return (
            False,
            "Expéditeur SMS non configuré.",
        )

    try:

        reponse = requests.post(
            (
                "https://api.twilio.com/"
                "2010-04-01/"
                f"Accounts/{sid}/Messages.json"
            ),
            data=donnees,
            auth=(
                sid,
                auth,
            ),
            timeout=15,
        )

        if reponse.status_code in (
            200,
            201,
        ):
            return (
                True,
                None,
            )

        return (
            False,
            f"HTTP {reponse.status_code}",
        )

    except requests.Timeout:

        return (
            False,
            "timeout",
        )

    except requests.RequestException:

        return (
            False,
            "erreur_reseau",
        )

    except Exception:

        return (
            False,
            "erreur_interne",
        )


# ============================================================
# DEMANDER UN CODE SMS
# ============================================================

def demander_code_sms(
    tel_saisi,
):
    """
    Génère un code à 6 chiffres
    puis l'envoie par SMS.
    """

    if "sms" not in canaux_disponibles():

        return (
            False,
            "La vérification par SMS n'est pas disponible.",
        )

    tel = normaliser_telephone(
        tel_saisi
    )

    if not tel:

        return (
            False,
            (
                "Numéro invalide. "
                "Utilise le format international, "
                "par exemple +242 06 123 45 67."
            ),
        )

    if _est_bloque(tel):

        return (
            False,
            "Ce numéro est suspendu.",
        )

    maintenant = time.time()

    jour = time.strftime(
        "%Y-%m-%d",
        time.gmtime(),
    )

    try:

        plafond = int(
            os.environ.get(
                "ADRYNX_SMS_MAX_PAR_JOUR",
                "150",
            )
        )

    except (
        ValueError,
        TypeError,
    ):

        plafond = 150

    plafond = max(
        1,
        min(
            plafond,
            10000,
        ),
    )

    with VERROU:

        _nettoyer()

        if (
            _sms_du_jour["jour"]
            != jour
        ):

            _sms_du_jour["jour"] = jour
            _sms_du_jour["n"] = 0

        if (
            _sms_du_jour["n"]
            >= plafond
        ):

            return (
                False,
                (
                    "Limite quotidienne "
                    "de SMS atteinte. "
                    "Réessaie demain."
                ),
            )

        recents = _envois.get(
            tel,
            [],
        )

        if recents:

            dernier = recents[-1]

            if (
                maintenant - dernier
                < DELAI_ENTRE_ENVOIS
            ):

                reste = int(
                    DELAI_ENTRE_ENVOIS
                    - (
                        maintenant
                        - dernier
                    )
                ) + 1

                return (
                    False,
                    (
                        f"Patiente {reste} "
                        "secondes avant "
                        "de redemander un code."
                    ),
                )

        if (
            len(recents)
            >= ENVOIS_MAX_PAR_HEURE
        ):

            return (
                False,
                (
                    "Trop de demandes "
                    "pour ce numéro. "
                    "Réessaie dans une heure."
                ),
            )

        code = (
            f"{secrets.randbelow(1000000):06d}"
        )

        empreinte = _hash_code(
            tel,
            code,
        )

        if not empreinte:

            return (
                False,
                (
                    "La sécurité de session "
                    "n'est pas configurée."
                ),
            )

        _otp[tel] = {
            "hash": empreinte,
            "expire": (
                maintenant
                + DUREE_CODE
            ),
            "essais": 0,
        }

        _envois[tel] = (
            recents
            + [maintenant]
        )

        _sms_du_jour["n"] += 1

    ok, erreur = envoyer_sms(
        tel,
        (
            "ADRYNX : ton code de "
            "verification est "
            f"{code}. "
            "Il expire dans 5 minutes. "
            "Ne le partage avec personne."
        ),
    )

    if not ok:

        with VERROU:

            _otp.pop(
                tel,
                None,
            )

        return (
            False,
            (
                "Impossible d'envoyer "
                "le SMS pour le moment. "
                "Réessaie plus tard."
            ),
        )

    return (
        True,
        "Code envoyé par SMS.",
    )


# ============================================================
# VÉRIFIER LE CODE
# ============================================================

def verifier_code_sms(
    tel_saisi,
    code_saisi,
):
    """
    Vérifie le code SMS et crée
    une session HMAC.
    """

    tel = normaliser_telephone(
        tel_saisi
    )

    code = re.sub(
        r"\D",
        "",
        code_saisi or "",
    )

    if not tel or len(code) != 6:

        return (
            None,
            "Code invalide.",
        )

    if not _secret_session():

        return (
            None,
            (
                "La sécurité de session "
                "n'est pas configurée."
            ),
        )

    with VERROU:

        _nettoyer()

        entree = _otp.get(
            tel
        )

        if not entree:

            return (
                None,
                (
                    "Code expiré. "
                    "Demande un nouveau code."
                ),
            )

        entree["essais"] += 1

        if (
            entree["essais"]
            > ESSAIS_MAX
        ):

            _otp.pop(
                tel,
                None,
            )

            return (
                None,
                (
                    "Trop d'essais. "
                    "Demande un nouveau code."
                ),
            )

        empreinte = _hash_code(
            tel,
            code,
        )

        valide = bool(
            empreinte
            and hmac.compare_digest(
                entree["hash"],
                empreinte,
            )
        )

        if not valide:

            restants = (
                ESSAIS_MAX
                - entree["essais"]
            )

            if restants <= 0:

                _otp.pop(
                    tel,
                    None,
                )

                return (
                    None,
                    (
                        "Trop d'essais. "
                        "Demande un nouveau code."
                    ),
                )

            return (
                None,
                (
                    f"Code incorrect. "
                    f"Il reste {restants} essai(s)."
                ),
            )

        _otp.pop(
            tel,
            None,
        )

    if _est_bloque(tel):

        return (
            None,
            "Ce numéro est suspendu.",
        )

    token = creer_token(
        tel
    )

    if not token:

        return (
            None,
            (
                "Impossible de créer "
                "la session sécurisée."
            ),
        )

    return (
        token,
        "Numéro vérifié.",
    )


# ============================================================
# INFORMATIONS DE CONFIGURATION
# ============================================================

def informations_verification():
    """
    Informations non sensibles destinées à l'API.
    """

    return {
        "active": verification_active(),
        "sms": (
            "sms"
            in canaux_disponibles()
        ),
        "telegram": False,
        "duree_session_jours": (
            DUREE_SESSION_JOURS
        ),
        "duree_code_secondes": (
            DUREE_CODE
        ),
        "essais_max": ESSAIS_MAX,
        "prefixes": list(
            prefixes_autorises()
        ),
    }


# ============================================================
# COMPATIBILITÉ AVEC L'ANCIEN CODE TELEGRAM
# ============================================================
# Ces fonctions ne font rien.
# Elles évitent qu'un ancien import dans api.py
# provoque une erreur pendant la transition.

def telegram_configure():
    return False


def secret_webhook_telegram():
    return None


def enregistrer_webhook_telegram():
    return False


def telegram_demarrer():
    return None


def telegram_traiter_update(
    update,
):
    return None


def telegram_statut(
    nonce=None,
):
    return (
        "indisponible",
        None,
    )
