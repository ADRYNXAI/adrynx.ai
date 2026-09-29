def verification_active(): return False
def informations_verification(): return {"active": False, "mode": "off"}
def demander_code_sms(tel): return False, "Vérification désactivée"
def verifier_code_sms(tel, code): return None, "Vérification désactivée"
