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
    Par défaut, ADRYNX accepte les
