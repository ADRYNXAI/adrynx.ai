"""
ADRYNX - VÉRIFICATION DU NUMÉRO DE TÉLÉPHONE
A mettre dans le MEME dossier que adrynx.py et api.py.

Pourquoi : jusqu'ici, le numéro était simplement « déclaré » par le navigateur,
donc n'importe qui pouvait en changer (et un utilisateur bloqué pouvait
revenir avec un autre numéro, ou usurper celui d'un client premium). Ce module
prouve qu'un visiteur possède réellement un numéro, puis lui remet un JETON
signé que le navigateur renvoie à chaque requête.

Deux canaux de vérification (tu actives ceux que tu veux, via Render > Environment) :

  1. TELEGRAM (gratuit, aucune carte bancaire) — le visiteur ouvre ton bot,
     appuie sur « Partager mon numéro » : Telegram a déjà vérifié ce numéro.
        TELEGRAM_BOT_TOKEN        jeton donné par @BotFather
        TELEGRAM_BOT_USERNAME     nom du bot, sans @

  2. SMS (payant : ~0,12 à 0,17 EUR le SMS vers le Congo, carte bancaire
     généralement exigée) — code à 6 chiffres. Fournisseur codé : Twilio.
        TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
        TWILIO_FROM (ou TWILIO_MESSAGING_SERVICE_SID)

Obligatoire dès qu'un canal est activé :
        ADRYNX_SESSION_SECRET     longue suite aléatoire (32 caractères ou plus),
                                  DIFFÉRENTE du secret admin. La changer déconnecte
                                  tout le monde (utile en cas de fuite).

Réglages facultatifs :
        ADRYNX_PREFIXES_AUTORISES  indicatifs acceptés, séparés par des virgules
                                   (défaut : +242)
        ADRYNX_SMS_MAX_PAR_JOUR    plafond de SMS par jour (défaut : 150) — protège
                                   contre les fraudes qui vident le crédit
        ADRYNX_URL_PUBLIQUE        adresse publique du site (Render la fournit déjà
                                   via RENDER_EXTERNAL_URL)

Sans aucun canal configuré, tout continue comme avant (numéro non vérifié).

Choix techniques :
  - Les codes SMS en attente et les compteurs anti-abus restent EN MÉMOIRE :
    ils sont éphémères (5 minutes) et ne dépendent donc pas de la base de
    données, qui est effacée à chaque redémarrage sur Render gratuit.
  - Le jeton de session est signé (HMAC-SHA256), sans stockage : il survit aux
    redémarrages et aux déploiements, donc personne n'a à se re-vérifier
    (et tu ne repayes pas de SMS).
  - Limites : un seul processus serveur (cas de Render gratuit). Avec plusieurs
    processus, il faudrait déplacer ces compteurs dans Redis ou Postgres.
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

_VERROU = threading.Lock()

DUREE_SESSION_JOURS = 90
DUREE_CODE = 300              # 5 minutes
ESSAIS_MAX = 5                # essais par code
DELAI_ENTRE_ENVOIS = 60       # secondes entre deux SMS au même numéro
ENVOIS_MAX_PAR_HEURE = 5      # SMS par numéro et par heure
DUREE_TELEGRAM = 600          # 10 minutes pour finir la vérification Telegram


# ------------------------------------------------------------- configuration
def _secret_session():
    s = os.environ.get("ADRYNX_SESSION_SECRET", "")
    return s.encode() if len(s) >= 16 else None


def prefixes_autorises():
    brut = os.environ.get("ADRYNX_PREFIXES_AUTORISES", "+242")
    return tuple(p.strip() for p in brut.split(",") if p.strip())


def sms_configure():
    return bool(
        os.environ.get("TWILIO_ACCOUNT_SID")
        and os.environ.get("TWILIO_AUTH_TOKEN")
        and (os.environ.get("TWILIO_FROM") or os.environ.get("TWILIO_MESSAGING_SERVICE_SID"))
    )


def telegram_configure():
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_BOT_USERNAME"))


def canaux_disponibles():
    """Liste des canaux utilisables. Vide si le secret de session manque :
    on ne délivre jamais de jeton qu'on ne saurait pas signer."""
    if not _secret_session():
        return []
    canaux = []
    if telegram_configure():
        canaux.append("telegram")
    if sms_configure():
        canaux.append("sms")
    return canaux


def verification_active():
    return bool(canaux_disponibles())


def _est_bloque(tel):
    from adrynx import est_bloque  # import tardif : évite une dépendance circulaire
    return est_bloque(tel)


# ------------------------------------------------------------- numéros
def normaliser_telephone(saisie):
    """'+242 06 123 45 67' -> '+242061234567'. None si le format est invalide
    ou si l'indicatif n'est pas dans la liste autorisée."""
    propre = re.sub(r"[\s.\-()]", "", saisie or "")
    if not re.fullmatch(r"\+\d{8,15}", propre):
        return None
    if not propre.startswith(prefixes_autorises()):
        return None
    return propre


# ------------------------------------------------------------- jetons de session
def _b64(octets):
    return base64.urlsafe_b64encode(octets).rstrip(b"=").decode()


def _unb64(texte):
    return base64.urlsafe_b64decode(texte + "=" * (-len(texte) % 4))


def creer_token(tel):
    cle = _secret_session()
    if not cle:
        return None
    charge = _b64(json.dumps({"t": tel, "i": int(time.time())}, separators=(",", ":")).encode())
    signature = _b64(hmac.new(cle, charge.encode(), hashlib.sha256).digest())
    return f"v1.{charge}.{signature}"


def lire_token(token):
    """Retourne le numéro si le jeton est authentique et non expiré, sinon None."""
    cle = _secret_session()
    if not cle or not token or not isinstance(token, str):
        return None
    try:
        version, charge, signature = token.split(".")
        if version != "v1":
            return None
        attendu = _b64(hmac.new(cle, charge.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, attendu):
            return None
        donnees = json.loads(_unb64(charge))
        if time.time() - int(donnees["i"]) > DUREE_SESSION_JOURS * 86400:
            return None
        tel = donnees["t"]
        return tel if normaliser_telephone(tel) == tel else None
    except Exception:
        return None


# ------------------------------------------------------------- canal SMS
_otp = {}      # numéro -> {"hash", "expire", "essais"}
_envois = {}   # numéro -> [horodatages des envois de la dernière heure]
_sms_du_jour = {"jour": "", "n": 0}


def _hash_code(tel, code):
    return hmac.new(_secret_session(), f"otp|{tel}|{code}".encode(), hashlib.sha256).hexdigest()


def envoyer_sms(tel, texte):
    """Envoie un SMS via Twilio. Retourne (succès, erreur)."""
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    jeton = os.environ.get("TWILIO_AUTH_TOKEN")
    donnees = {"To": tel, "Body": texte}
    if os.environ.get("TWILIO_MESSAGING_SERVICE_SID"):
        donnees["MessagingServiceSid"] = os.environ["TWILIO_MESSAGING_SERVICE_SID"]
    else:
        donnees["From"] = os.environ.get("TWILIO_FROM", "")
    try:
        r = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data=donnees, auth=(sid, jeton), timeout=15,
        )
        if r.status_code in (200, 201):
            return True, None
        return False, f"HTTP {r.status_code}"
    except requests.RequestException as e:
        return False, type(e).__name__


def demander_code_sms(tel_saisi):
    """Génère et envoie un code. Retourne (succès, message pour l'utilisateur)."""
    if "sms" not in canaux_disponibles():
        return False, "La vérification par SMS n'est pas disponible."
    tel = normaliser_telephone(tel_saisi)
    if not tel:
        return False, "Numéro invalide. Utilise le format international, par exemple +242 06 123 45 67."
    if _est_bloque(tel):
        return False, "Ce numéro est suspendu."

    maintenant = time.time()
    jour = time.strftime("%Y-%m-%d")
    with _VERROU:
        if len(_otp) > 5000:
            _otp.clear()
        if len(_envois) > 5000:
            _envois.clear()
        if _sms_du_jour["jour"] != jour:
            _sms_du_jour.update(jour=jour, n=0)
        if _sms_du_jour["n"] >= int(os.environ.get("ADRYNX_SMS_MAX_PAR_JOUR", "150")):
            return False, "Limite quotidienne de SMS atteinte. Réessaie demain ou utilise Telegram."
        recents = [t for t in _envois.get(tel, []) if maintenant - t < 3600]
        if recents and maintenant - recents[-1] < DELAI_ENTRE_ENVOIS:
            reste = int(DELAI_ENTRE_ENVOIS - (maintenant - recents[-1])) + 1
            return False, f"Patiente {reste} secondes avant de redemander un code."
        if len(recents) >= ENVOIS_MAX_PAR_HEURE:
            return False, "Trop de demandes pour ce numéro. Réessaie dans une heure."
        code = f"{secrets.randbelow(10 ** 6):06d}"
        _otp[tel] = {"hash": _hash_code(tel, code), "expire": maintenant + DUREE_CODE, "essais": 0}
        _envois[tel] = recents + [maintenant]
        _sms_du_jour["n"] += 1

    ok, _ = envoyer_sms(
        tel,
        f"ADRYNX : ton code de vérification est {code}. Il expire dans 5 minutes. Ne le partage avec personne.",
    )
    if not ok:
        with _VERROU:
            _otp.pop(tel, None)
        return False, "Impossible d'envoyer le SMS pour le moment. Réessaie plus tard."
    return True, "Code envoyé par SMS."


def verifier_code_sms(tel_saisi, code_saisi):
    """Retourne (jeton ou None, message)."""
    tel = normaliser_telephone(tel_saisi)
    code = re.sub(r"\D", "", code_saisi or "")
    if not tel or len(code) != 6 or not _secret_session():
        return None, "Code invalide."
    with _VERROU:
        entree = _otp.get(tel)
        if not entree or time.time() > entree["expire"]:
            _otp.pop(tel, None)
            return None, "Code expiré. Demande un nouveau code."
        entree["essais"] += 1
        if entree["essais"] > ESSAIS_MAX:
            _otp.pop(tel, None)
            return None, "Trop d'essais. Demande un nouveau code."
        if not hmac.compare_digest(entree["hash"], _hash_code(tel, code)):
            return None, "Code incorrect."
        _otp.pop(tel, None)
    if _est_bloque(tel):
        return None, "Ce numéro est suspendu."
    return creer_token(tel), "Numéro vérifié."


# ------------------------------------------------------------- canal Telegram
_tg_attente = {}   # nonce -> {"cree": horodatage, "tel": numéro ou None}
_tg_chats = {}     # chat_id Telegram -> nonce


def _tg_api(methode, **params):
    jeton = os.environ.get("TELEGRAM_BOT_TOKEN")
    try:
        r = requests.post(f"https://api.telegram.org/bot{jeton}/{methode}", json=params, timeout=10)
        return r.ok
    except requests.RequestException:
        return False


def secret_webhook_telegram():
    """Secret que Telegram renvoie dans l'en-tête de chaque appel : prouve
    que la requête vient bien de Telegram (dérivé du secret de session)."""
    cle = _secret_session()
    return hashlib.sha256(b"tg|" + cle).hexdigest()[:48] if cle else None


def enregistrer_webhook_telegram():
    """Dit à Telegram où envoyer les messages du bot. Appelé au démarrage."""
    if "telegram" not in canaux_disponibles():
        return False
    base = os.environ.get("ADRYNX_URL_PUBLIQUE") or os.environ.get("RENDER_EXTERNAL_URL")
    if not base:
        return False
    return _tg_api(
        "setWebhook",
        url=base.rstrip("/") + "/api/telegram/webhook",
        secret_token=secret_webhook_telegram(),
        allowed_updates=["message"],
    )


def telegram_demarrer():
    """Prépare une vérification : retourne {"nonce", "lien"} ou None."""
    if "telegram" not in canaux_disponibles():
        return None
    maintenant = time.time()
    with _VERROU:
        for n in [n for n, v in _tg_attente.items() if maintenant - v["cree"] > DUREE_TELEGRAM]:
            _tg_attente.pop(n, None)
        if len(_tg_chats) > 5000:
            _tg_chats.clear()
        if len(_tg_attente) > 2000:
            return None
        nonce = secrets.token_urlsafe(9)
        _tg_attente[nonce] = {"cree": maintenant, "tel": None}
    bot = os.environ["TELEGRAM_BOT_USERNAME"].lstrip("@")
    return {"nonce": nonce, "lien": f"https://t.me/{bot}?start={nonce}"}


def telegram_traiter_update(update):
    """Traite un message reçu par le bot. Ne lève jamais d'exception."""
    try:
        msg = (update or {}).get("message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        expediteur = msg.get("from") or {}
        if not chat_id:
            return
        texte = msg.get("text") or ""
        contact = msg.get("contact")

        if texte.startswith("/start"):
            nonce = texte[6:].strip()
            with _VERROU:
                entree = _tg_attente.get(nonce)
                valide = bool(entree) and time.time() - entree["cree"] <= DUREE_TELEGRAM
                if valide:
                    _tg_chats[chat_id] = nonce
            if not valide:
                _tg_api("sendMessage", chat_id=chat_id,
                        text="Ce lien a expiré. Retourne sur ADRYNX et relance la vérification.")
                return
            _tg_api(
                "sendMessage", chat_id=chat_id,
                text="Pour vérifier ton numéro, appuie sur le bouton ci-dessous.",
                reply_markup={
                    "keyboard": [[{"text": "📱 Partager mon numéro", "request_contact": True}]],
                    "resize_keyboard": True, "one_time_keyboard": True,
                },
            )
            return

        if contact:
            enlever = {"remove_keyboard": True}
            # Le contact doit être celui de la personne qui écrit : sinon
            # quelqu'un pourrait transférer le contact d'un autre.
            if contact.get("user_id") is None or contact.get("user_id") != expediteur.get("id"):
                _tg_api("sendMessage", chat_id=chat_id,
                        text="Partage ton propre numéro avec le bouton prévu.", reply_markup=enlever)
                return
            chiffres = re.sub(r"\D", "", contact.get("phone_number") or "")
            tel = normaliser_telephone("+" + chiffres)
            with _VERROU:
                nonce = _tg_chats.get(chat_id)
            if not nonce:
                _tg_api("sendMessage", chat_id=chat_id,
                        text="Retourne sur ADRYNX et relance la vérification.", reply_markup=enlever)
                return
            if not tel:
                _tg_api("sendMessage", chat_id=chat_id,
                        text="Ce numéro n'est pas accepté (pays non pris en charge).", reply_markup=enlever)
                return
            if _est_bloque(tel):
                _tg_api("sendMessage", chat_id=chat_id, text="Ce numéro est suspendu.", reply_markup=enlever)
                return
            with _VERROU:
                entree = _tg_attente.get(nonce)
                if not entree or time.time() - entree["cree"] > DUREE_TELEGRAM:
                    entree = None
                else:
                    entree["tel"] = tel
                    _tg_chats.pop(chat_id, None)
            if entree is None:
                _tg_api("sendMessage", chat_id=chat_id,
                        text="Ce lien a expiré. Retourne sur ADRYNX et relance la vérification.",
                        reply_markup=enlever)
                return
            _tg_api("sendMessage", chat_id=chat_id,
                    text="✅ Numéro vérifié ! Retourne sur ADRYNX.", reply_markup=enlever)
    except Exception:
        pass


def telegram_statut(nonce):
    """Interrogé par le navigateur toutes les 2 secondes.
    Retourne ('ok', jeton) | ('attente', None) | ('expire', None)."""
    with _VERROU:
        entree = _tg_attente.get(nonce)
        if not entree or time.time() - entree["cree"] > DUREE_TELEGRAM:
            _tg_attente.pop(nonce, None)
            return "expire", None
        if not entree["tel"]:
            return "attente", None
        tel = entree["tel"]
        _tg_attente.pop(nonce, None)
    return "ok", creer_token(tel)
