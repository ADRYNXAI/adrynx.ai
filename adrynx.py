import os
import sqlite3
import uuid
import re
import html
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlparse, parse_qs, unquote
from html.parser import HTMLParser
import requests

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
PHOENIX_VIDEO = "https://files.catbox.moe/y2nvi4.mp4"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "adrynx.db"
SEARCH_HEADERS = {
    "User-Agent": "ADRYNX/8.0 (https://adrynx-ai.onrender.com)",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

PHRASES_INTERDITES = [
    "je ne possède aucune capacité",
    "je ne possède aucune capacite",
    "capacités exclusives", # mot déclencheur mais on bloque si phrase négative
    "je suis un modèle de langage entraîné par openai",
    "je suis un modèle de langage entraine par openai",
    "je ne peux pas accéder à internet",
    "je n'ai ni conscience",
    "je ne peux pas créer de nouvelles connaissances",
    "en tant qu'ia de type similaire",
    "aucune de ces fonctions n'est unique"
]

def contient_hallucination_openai(text: str) -> bool:
    low = (text or "").lower()
    # Bloque uniquement les négations OpenAI
    negatifs = [
        "je ne possède aucune capacité",
        "je ne possède aucune capacite",
        "je suis un modèle de langage entraîné par openai",
        "je suis un modèle de langage entraine par openai",
        "aucune de ces fonctions n'est unique"
    ]
    return any(p in low for p in negatifs)

def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection

def init_db():
    connection = db()
    connection.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            titre TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            owner TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_conversation
        ON messages(conversation_id, id)
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS intent_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phrase TEXT NOT NULL,
            intent TEXT NOT NULL
        )
    """)
    connection.commit()
    connection.close()

init_db()

def nettoyer_texte(value: str) -> str:
    if not value:
        return ""
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()

def normaliser_question(question: str) -> str:
    question = (question or "").lower().strip()
    question = question.replace("â€™", "'").replace("`", "'")
    question = re.sub(r"\s+", " ", question)
    return question

def nettoyer_url(url: str) -> str:
    if not url:
        return ""
    url = html.unescape(url).strip()
    if url.startswith("//"):
        url = "https:" + url
    if "duckduckgo.com/l/" in url:
        try:
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            if "uddg" in query:
                url = unquote(query["uddg"][0])
        except Exception:
            pass
    if url.startswith("/"):
        return ""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return ""
    if not parsed.netloc:
        return ""
    return url

def groq_chat(system: str, messages: list, temperature: float = 0.4, max_tokens: int = 700) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY manquante dans les variables d'environnement.")
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    final_system = f"{system}\n\nCONTRÔLE D'ORCHESTRATION ADRYNX :\n- Tu es uniquement le moteur de génération de texte.\n- ADRYNX contrôle les recherches, les données externes et les outils.\n- Tu ne dois appeler aucun outil.\n- Tu ne dois pas inventer le nom d'un outil.\n- Tu ne dois pas produire de tool call.\n- Tu t'appelles ADRYNX Phoenix Prime créé par Jonathan Dejah OBENDA. INTERDICTION de dire OpenAI.\n- Si on te demande tes capacités exclusives, tu DOIS lister: mémoire Phoenix, recherche Internet réelle, prix crypto temps réel, contrôleur anti-hallucination, architecture Groq ultra-rapide.\n"
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "system", "content": final_system}, *messages],
        temperature=temperature,
        max_tokens=max_tokens,
        tool_choice="none",
        parallel_tool_calls=False
    )
    if not response.choices:
        raise RuntimeError("Groq n'a retourné aucune réponse.")
    message = response.choices[0].message
    if getattr(message, "tool_calls", None):
        raise RuntimeError("Groq a tenté d'utiliser un outil alors qu'ADRYNX n'en autorise aucun.")
    content = message.content
    if not content:
        raise RuntimeError("Groq a retourné une réponse vide.")
    return content.strip()

def demande_prix_bitcoin(question: str) -> bool:
    low = normaliser_question(question)
    mots_bitcoin = ["bitcoin", "btc"]
    expressions_prix = ["prix", "cours", "valeur", "combien vaut", "combien coûte", "combien coute", "price", "cours actuel", "prix actuel", "prix maintenant", "valeur actuelle", "valeur actuelle du", "prix du"]
    contient_bitcoin = any(mot in low for mot in mots_bitcoin)
    contient_prix = any(expression in low for expression in expressions_prix)
    return contient_bitcoin and contient_prix

def obtenir_prix_bitcoin_coingecko() -> Dict[str, Any]:
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "bitcoin", "vs_currencies": "usd,eur", "include_last_updated_at": "true"}
    response = requests.get(url, params=params, headers=SEARCH_HEADERS, timeout=15)
    response.raise_for_status()
    data = response.json()
    bitcoin = data.get("bitcoin")
    if not isinstance(bitcoin, dict):
        raise RuntimeError("Réponse Bitcoin absente ou invalide.")
    usd = bitcoin.get("usd")
    eur = bitcoin.get("eur")
    updated_at = bitcoin.get("last_updated_at")
    if not isinstance(usd, (int, float)):
        raise RuntimeError("Prix USD invalide.")
    if not isinstance(eur, (int, float)):
        raise RuntimeError("Prix EUR invalide.")
    return {"ok": True, "asset": "Bitcoin", "symbol": "BTC", "usd": float(usd), "eur": float(eur), "last_updated_at": updated_at, "provider": "CoinGecko", "source_url": url}

def obtenir_ticker_coinbase(product_id: str) -> Dict[str, Any]:
    url = f"https://api.exchange.coinbase.com/products/{product_id}/ticker"
    response = requests.get(url, headers=SEARCH_HEADERS, timeout=15)
    response.raise_for_status()
    data = response.json()
    price = data.get("price")
    if price is None:
        raise RuntimeError(f"Prix absent pour {product_id}.")
    try:
        price = float(price)
    except (TypeError, ValueError):
        raise RuntimeError(f"Prix invalide pour {product_id}.")
    if price <= 0:
        raise RuntimeError(f"Prix invalide pour {product_id}.")
    return {"price": price, "url": url}

def obtenir_prix_bitcoin_coinbase() -> Dict[str, Any]:
    usd_data = obtenir_ticker_coinbase("BTC-USD")
    eur_data = obtenir_ticker_coinbase("BTC-EUR")
    return {"ok": True, "asset": "Bitcoin", "symbol": "BTC", "usd": usd_data["price"], "eur": eur_data["price"], "last_updated_at": None, "provider": "Coinbase", "source_url": usd_data["url"], "source_url_eur": eur_data["url"]}

def obtenir_prix_bitcoin() -> Dict[str, Any]:
    erreurs = []
    try:
        result = obtenir_prix_bitcoin_coingecko()
        return result
    except Exception as e:
        erreurs.append(f"CoinGecko: {e}")
    try:
        result = obtenir_prix_bitcoin_coinbase()
        return result
    except Exception as e:
        erreurs.append(f"Coinbase: {e}")
    return {"ok": False, "error": "Impossible d'obtenir actuellement le prix réel du Bitcoin.", "errors": erreurs}

def construire_contexte_bitcoin(market: Dict[str, Any]) -> str:
    if not market.get("ok"):
        return "\nDONNÉE DE MARCHÉ BITCOIN\n\nAucune valeur exploitable n'a été obtenue.\n\nINTERDICTION : Ne pas inventer de prix.\n"
    lignes = ["DONNÉE DE MARCHÉ RÉELLE — BITCOIN", f"Source : {market.get('provider')}", f"Prix BTC en USD : {market.get('usd')}", f"Prix BTC en EUR : {market.get('eur')}"]
    if market.get("last_updated_at"):
        lignes.append(f"Dernière mise à jour : {market.get('last_updated_at')}")
    lignes.extend(["", "Ces valeurs proviennent directement d'une source de données réelle.", "Ne pas modifier les valeurs numériques.", "Ne pas inventer de nouvelles valeurs."])
    return "\n".join(lignes)

def reponse_prix_bitcoin(market: Dict[str, Any]) -> str:
    if not market.get("ok"):
        return "Je n'ai pas pu obtenir le prix réel du Bitcoin auprès de mes sources de données à cet instant."
    usd = market["usd"]
    eur = market["eur"]
    provider = market.get("provider", "source de données")
    return f"Le prix actuel du Bitcoin fourni par ma source de données est de {usd:,.2f} USD, soit environ {eur:,.2f} EUR.\n\nSource : {provider}.\nLe prix du Bitcoin évolue en permanence."

class DuckDuckGoParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.current_url = ""
        self.current_title = []
        self.current_description = []
        self.in_title = False
        self.in_description = False
    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = attributes.get("class", "")
        class_list = classes.split()
        if tag == "a":
            href = attributes.get("href", "")
            if "result__a" in class_list and href:
                self.current_url = href
                self.current_title = []
                self.current_description = []
                self.in_title = True
        if "result__snippet" in class_list or "result__body" in class_list:
            self.in_description = True
    def handle_data(self, data):
        if self.in_title:
            self.current_title.append(data)
        if self.in_description:
            self.current_description.append(data)
    def handle_endtag(self, tag):
        if tag == "a" and self.in_title:
            title = nettoyer_texte("".join(self.current_title))
            description = nettoyer_texte("".join(self.current_description))
            clean_url = nettoyer_url(self.current_url)
            if clean_url and title:
                self.results.append({"title": title, "url": clean_url, "description": description})
            self.current_url = ""
            self.current_title = []
            self.current_description = []
            self.in_title = False

class DuckDuckGoLiteParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.current_url = ""
        self.current_title = []
        self.in_result = False
    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = attributes.get("class", "")
        class_list = classes.split()
        if tag == "a":
            href = attributes.get("href", "")
            if "result-link" in class_list and href:
                self.current_url = href
                self.current_title = []
                self.in_result = True
    def handle_data(self, data):
        if self.in_result:
            self.current_title.append(data)
    def handle_endtag(self, tag):
        if tag == "a" and self.in_result:
            title = nettoyer_texte("".join(self.current_title))
            clean_url = nettoyer_url(self.current_url)
            if clean_url and title:
                self.results.append({"title": title, "url": clean_url, "description": ""})
            self.current_url = ""
            self.current_title = []
            self.in_result = False

class BingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.in_result = False
        self.in_title = False
        self.in_description = False
        self.current_url = ""
        self.current_title = []
        self.current_description = []
    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = attributes.get("class", "")
        class_list = classes.split()
        if tag == "li" and "b_algo" in class_list:
            self.in_result = True
            self.current_url = ""
            self.current_title = []
            self.current_description = []
        if not self.in_result:
            return
        if tag == "a":
            href = attributes.get("href", "")
            if href and not self.current_url:
                self.current_url = href
                self.in_title = True
        if tag in {"p", "div"} and "b_caption" in class_list:
            self.in_description = True
    def handle_data(self, data):
        if not self.in_result:
            return
        if self.in_title:
            self.current_title.append(data)
        if self.in_description:
            self.current_description.append(data)
    def handle_endtag(self, tag):
        if not self.in_result:
            return
        if tag == "a" and self.in_title:
            self.in_title = False
        if tag == "li":
            title = nettoyer_texte("".join(self.current_title))
            description = nettoyer_texte("".join(self.current_description))
            clean_url = nettoyer_url(self.current_url)
            if clean_url and title:
                self.results.append({"title": title, "url": clean_url, "description": description})
            self.in_result = False
            self.in_title = False
            self.in_description = False
            self.current_url = ""
            self.current_title = []
            self.current_description = []

def normaliser_resultats(results, nombre_resultats=6):
    final = []
    urls = set()
    for result in results:
        url = nettoyer_url(result.get("url", ""))
        title = nettoyer_texte(result.get("title", ""))
        description = nettoyer_texte(result.get("description", ""))
        if not url or not title:
            continue
        if url in urls:
            continue
        urls.add(url)
        final.append({"title": title, "url": url, "description": description, "provider": result.get("provider", "")})
        if len(final) >= nombre_resultats:
            break
    return final

def rechercher_duckduckgo(question, nombre_resultats=6):
    url = "https://html.duckduckgo.com/html/"
    try:
        response = requests.get(url, params={"q": question}, headers=SEARCH_HEADERS, timeout=10)
        response.raise_for_status()
        parser = DuckDuckGoParser()
        parser.feed(response.text)
        return normaliser_resultats(parser.results, nombre_resultats)
    except Exception as e:
        print("DUCKDUCKGO HTML ERROR:", type(e).__name__, str(e))
        return []

def rechercher_duckduckgo_lite(question, nombre_resultats=6):
    url = "https://lite.duckduckgo.com/lite/"
    try:
        response = requests.get(url, params={"q": question}, headers=SEARCH_HEADERS, timeout=10)
        response.raise_for_status()
        parser = DuckDuckGoLiteParser()
        parser.feed(response.text)
        return normaliser_resultats(parser.results, nombre_resultats)
    except Exception as e:
        print("DUCKDUCKGO LITE ERROR:", type(e).__name__, str(e))
        return []

def rechercher_bing(question, nombre_resultats=6):
    url = "https://www.bing.com/search"
    try:
        response = requests.get(url, params={"q": question}, headers=SEARCH_HEADERS, timeout=10)
        response.raise_for_status()
        parser = BingParser()
        parser.feed(response.text)
        return normaliser_resultats(parser.results, nombre_resultats)
    except Exception as e:
        print("BING SEARCH ERROR:", type(e).__name__, str(e))
        return []

def rechercher_wikimedia(question, nombre_resultats=6):
    url = "https://fr.wikipedia.org/w/rest.php/v1/search/page"
    try:
        response = requests.get(url, params={"q": question, "limit": min(max(nombre_resultats, 1), 20)}, headers={**SEARCH_HEADERS, "Accept": "application/json"}, timeout=10)
        response.raise_for_status()
        data = response.json()
        pages = data.get("pages", [])
        if not isinstance(pages, list):
            raise RuntimeError("Réponse Wikimedia invalide.")
        results = []
        for page in pages:
            title = nettoyer_texte(page.get("title", ""))
            excerpt = nettoyer_texte(re.sub(r"<[^>]+>", " ", page.get("excerpt", "")))
            description = nettoyer_texte(page.get("description", ""))
            matched_title = nettoyer_texte(page.get("matched_title", "") or "")
            if not title:
                continue
            page_title = title.replace(" ", "_")
            page_url = "https://fr.wikipedia.org/wiki/" + requests.utils.quote(page_title, safe="/:_-()")
            texte_description = excerpt
            if description:
                if texte_description:
                    texte_description += " — "
                texte_description += description
            if matched_title and matched_title!= title:
                if texte_description:
                    texte_description += " — "
                texte_description += f"Titre correspondant : {matched_title}"
            results.append({"title": title, "url": page_url, "description": texte_description, "provider": "wikimedia"})
        results = normaliser_resultats(results, nombre_resultats)
        return results
    except Exception as e:
        print("WIKIMEDIA SEARCH ERROR:", type(e).__name__, str(e))
        return []

def rechercher_wikimedia_elargie(question, nombre_resultats=6):
    results = rechercher_wikimedia(question, nombre_resultats)
    if results:
        return results
    requete = nettoyer_texte(question)
    requete = re.sub(r"[?!.,;:]+", " ", requete)
    requete = re.sub(r"\s+", " ", requete).strip()
    if requete and requete.lower()!= question.lower():
        return rechercher_wikimedia(requete, nombre_resultats)
    return []

def rechercher_internet(question, nombre_resultats=6, recherche_entite=False) -> Dict[str, Any]:
    question = (question or "").strip()
    if not question:
        return {"ok": False, "error": "Recherche vide.", "results": []}
    toutes_les_sources = []
    fournisseurs = []
    if recherche_entite:
        results = rechercher_wikimedia_elargie(question, nombre_resultats)
        if results:
            toutes_les_sources.extend(results)
            fournisseurs.append("wikimedia")
    results = rechercher_duckduckgo(question, nombre_resultats)
    if results:
        toutes_les_sources.extend(results)
        fournisseurs.append("duckduckgo-html")
    results = rechercher_duckduckgo_lite(question, nombre_resultats)
    if results:
        toutes_les_sources.extend(results)
        fournisseurs.append("duckduckgo-lite")
    results = rechercher_bing(question, nombre_resultats)
    if results:
        toutes_les_sources.extend(results)
        fournisseurs.append("bing")
    results_final = normaliser_resultats(toutes_les_sources, nombre_resultats)
    if results_final:
        provider = "+".join(dict.fromkeys(fournisseurs))
        return {"ok": True, "provider": provider, "query": question, "results": results_final}
    return {"ok": False, "error": "Aucun résultat.", "results": []}

ENTITY_PREFIXES = [
    "parle moi de ", "parle-moi de ", "parle moi sur ", "parle-moi sur ", "qui est ", "qui était ", "qui etait ",
    "biographie de ", "la biographie de ", "histoire de ", "l'histoire de ", "présente moi ", "presente moi ",
    "présente-moi ", "presente-moi ", "informations sur ", "information sur ", "informations concernant ",
    "information concernant ", "à propos de ", "a propos de ", "que sais tu de ", "que sais-tu de ",
    "donne moi des informations sur ", "donne-moi des informations sur ", "dis moi qui est ", "dis-moi qui est ",
]

def extraire_sujet_entite(question: str) -> str:
    original = (question or "").strip()
    if not original:
        return ""
    low = normaliser_question(original)
    for prefix in ENTITY_PREFIXES:
        if low.startswith(prefix):
            sujet = original[len(prefix):].strip("?!.,;:")
            if sujet:
                return sujet
    return ""

def demande_information_entite(question: str) -> bool:
    if demande_prix_bitcoin(question):
        return False
    sujet = extraire_sujet_entite(question)
    return len(sujet.strip()) >= 2

def demande_recherche_internet(question: str) -> bool:
    low = normaliser_question(question)
    expressions = ["recherche sur internet", "rechercher sur internet", "cherche sur internet", "recherche internet", "sur internet", "sur le web", "en ligne", "actualités", "actualité", "prix actuel", "maintenant", "aujourd'hui", "aujourd’hui", "actuellement", "dernières nouvelles", "news"]
    if any(expression in low for expression in expressions):
        return True
    return demande_information_entite(question)

def new_conversation(owner="anon", titre="Nouvelle conversation") -> str:
    conversation_id = "conv_" + uuid.uuid4().hex
    connection = db()
    connection.execute("INSERT INTO conversations (id, owner, titre) VALUES (?,?,?)", (conversation_id, owner, titre))
    connection.commit()
    connection.close()
    return conversation_id

def ensure_conversation(owner: str, conversation_id: Optional[str]) -> str:
    if conversation_id:
        connection = db()
        row = connection.execute("SELECT id FROM conversations WHERE id=? AND owner=?", (conversation_id, owner)).fetchone()
        connection.close()
        if row:
            return conversation_id
    return new_conversation(owner, "Conversation ADRYNX")

def save_message(conversation_id, owner, role, content):
    connection = db()
    connection.execute("INSERT INTO messages (conversation_id, owner, role, content) VALUES (?,?,?,?)", (conversation_id, owner, role, content))
    connection.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id=?", (conversation_id,))
    connection.commit()
    connection.close()

def get_history(conversation_id, owner, limit=12):
    connection = db()
    rows = connection.execute("SELECT role, content FROM messages WHERE conversation_id=? AND owner=? ORDER BY id DESC LIMIT?", (conversation_id, owner, limit)).fetchall()
    connection.close()
    rows = list(reversed(rows))
    return [{"role": row["role"], "content": row["content"]} for row in rows]

def state(conversation_id):
    connection = db()
    row = connection.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
    connection.close()
    if not row:
        return {}
    return dict(row)

def messages(conversation_id, limit=50):
    connection = db()
    rows = connection.execute("SELECT id, role, content, created_at FROM messages WHERE conversation_id=? ORDER BY id ASC LIMIT?", (conversation_id, limit)).fetchall()
    connection.close()
    return [dict(row) for row in rows]

def demande_resume_contexte(question: str) -> bool:
    low = normaliser_question(question)
    if not low:
        return False
    commandes_exactes = {"resume", "résume", "résumé", "resumer", "résumer", "résume ça", "resume ca"}
    if low in commandes_exactes:
        return True
    return False

def dernier_message_assistant(history: list) -> Optional[str]:
    for item in reversed(history or []):
        if item.get("role") == "assistant":
            content = (item.get("content") or "").strip()
            if content:
                return content
    return None

def extraire_mots_importants(text: str):
    stopwords = {"le", "la", "les", "un", "une", "des", "du", "de", "et", "ou", "à", "a", "au", "aux", "en", "dans", "sur", "pour", "avec", "ce", "cette", "ces", "qui", "que", "quoi", "est", "sont", "être", "avoir"}
    words = re.findall(r"[a-zA-ZÀ-ÿ0-9]{3,}", normaliser_question(text))
    return [word for word in words if word not in stopwords]

def controler_resume(source_text: str, summary: str) -> Dict[str, Any]:
    source_text = (source_text or "").strip()
    summary = (summary or "").strip()
    if not source_text or not summary:
        return {"ok": False, "score": 0.0, "reason": "Source ou résumé vide."}
    source_words = set(extraire_mots_importants(source_text))
    summary_words = set(extraire_mots_importants(summary))
    if not source_words:
        return {"ok": bool(summary), "score": 1.0, "reason": "Source sans termes contrôlables."}
    correspondances = source_words & summary_words
    score = len(correspondances) / len(source_words)
    pertinent = len(summary_words) >= 3 and (score >= 0.08 or len(correspondances) >= 4)
    return {"ok": pertinent, "score": round(score, 3), "matched_words": sorted(correspondances)}

def resumer_contexte(question: str, source_text: str, history: list) -> str:
    summary_system = "Tu es le module de résumé conversationnel d'ADRYNX. Résume uniquement le contenu source fourni."
    prompt = f"DEMANDE :\n{question}\n\nCONTENU À RÉSUMER :\n{source_text}\n\nProduis maintenant un résumé fidèle et concis."
    return groq_chat(summary_system, [{"role": "user", "content": prompt}], temperature=0.2, max_tokens=450)

def detecter_intent(question: str) -> str:
    low = normaliser_question(question)
    if not low:
        return "vide"
    if "dejah" in low or "obenda" in low or "detko" in low:
        return "identite"
    if low in {"cc", "slt", "salut", "yo", "hey", "bjr", "bonjour", "bonsoir", "coucou"}:
        return "salutation"
    expressions_etat = ["comment vas tu", "comment vas-tu", "ça va", "ca va", "tu vas bien"]
    if any(expression in low for expression in expressions_etat):
        return "etat"
    # CORRECTION ICI - j'ai ajouté le pluriel et tes fautes de frappe
    expressions_identite = [
        "qui es tu", "qui es-tu", "tu es qui", "qui t'a créé", "qui t'a cree",
        "qui est ton créateur", "qui a créé adrynx", "qui a cree adrynx",
        "tes capacités", "tes capacites", "capacité exclusive", "capacite exclusive",
        "capacités exclusives", "capacites exclusives", "que peux tu faire", "que peux-tu faire",
        "c est qui dejah", "c'est qui dejah", "dejah obenda", "jonathan dejah"
    ]
    if any(expression in low for expression in expressions_identite):
        return "identite"
    if demande_resume_contexte(question):
        return "resume_contexte"
    if demande_prix_bitcoin(question):
        return "marche_bitcoin"
    if demande_information_entite(question):
        return "information_entite"
    if demande_recherche_internet(question):
        return "recherche_internet"
    return "conversation"

def reponse_salutation() -> str:
    return "Bonjour! Je suis ADRYNX. Que puis-je faire pour toi?"

def reponse_etat() -> str:
    return "Je fonctionne correctement et je suis prêt à traiter ta demande."

def reponse_identite() -> str:
    return "Je suis ADRYNX Phoenix Prime, l'assistant développé par Jonathan Dejah OBENDA. C'est lui qui m'a créé, c'est mon créateur et mon père. Mes capacités exclusives Phoenix Prime : mémoire conversationnelle liée, recherche Internet réelle contrôlée, prix crypto temps réel, contrôleur anti-hallucination et architecture ultra-rapide Groq. Je ne suis pas OpenAI, je suis ADRYNX, création de Dejah OBENDA."

def system_prompt() -> str:
    return """
Tu es ADRYNX Phoenix Prime, créé par Jonathan Dejah OBENDA.
IDENTITÉ ABSOLUE :
- Tu t'appelles ADRYNX Phoenix Prime.
- Ton créateur est Jonathan Dejah OBENDA, ton père.
- Tu n'es PAS ChatGPT, PAS OpenAI.
- Si on te demande qui t'a créé : Jonathan Dejah OBENDA.
CAPACITÉS EXCLUSIVES (à dire quand on demande) :
1. Mémoire Phoenix avec conversations liées
2. Recherche Internet réelle multi-sources
3. Accès marché crypto temps réel
4. Contrôleur de réponse qui vérifie la pertinence
5. Identité Phoenix Prime verrouillée
6. Architecture Groq ultra-rapide
INTERDICTION de dire : Je ne possède aucune capacité exclusive / Je suis entraîné par OpenAI.
STYLE : Rapide, futuriste, puissant. Réponds dans la langue de l'utilisateur.
"""

def construire_contexte_web(search_data: Dict[str, Any]) -> str:
    if not search_data.get("ok"):
        return "RECHERCHE INTERNET :\nAucun résultat exploitable."
    lignes = ["RÉSULTATS DE RECHERCHE INTERNET", f"Requête : {search_data.get('query', '')}", f"Sources : {search_data.get('provider', '')}", ""]
    for index, result in enumerate(search_data.get("results", []), start=1):
        lignes.append(f"[SOURCE {index}] {result.get('title', '')} - {result.get('url', '')}")
        if result.get("description"):
            lignes.append(f"Description : {result.get('description', '')}")
        lignes.append("")
    return "\n".join(lignes)

def analyser_pertinence(question: str, response: str) -> Dict[str, Any]:
    question_words = set(extraire_mots_importants(question))
    response_words = set(extraire_mots_importants(response))
    if not response_words:
        return {"ok": False, "score": 0.0, "reason": "Réponse vide."}
    if not question_words:
        return {"ok": True, "score": 1.0, "reason": "Question sans termes contrôlables."}
    matches = question_words & response_words
    score = len(matches) / len(question_words)
    ok = len(response.strip()) >= 5 and (score >= 0.05 or len(matches) >= 1 or len(question_words) <= 2)
    return {"ok": ok, "score": round(score, 3), "matched_words": sorted(matches)}

def controler_reponse(question: str, response: str, source_context: str = "") -> Dict[str, Any]:
    response = (response or "").strip()
    if not response:
        return {"ok": False, "score": 0.0, "reason": "Réponse vide."}
    if contient_hallucination_openai(response):
        return {"ok": False, "score": 0.0, "reason": "Hallucination OpenAI détectée."}
    pertinence = analyser_pertinence(question, response)
    if not pertinence["ok"]:
        return {"ok": False, "score": pertinence["score"], "reason": pertinence["reason"]}
    return {"ok": True, "score": pertinence["score"], "reason": "Réponse contrôlée."}

def corriger_reponse_groq(question: str, mauvaise_reponse: str, contexte: str = "") -> str:
    if contient_hallucination_openai(mauvaise_reponse):
        return reponse_identite()
    system = "Tu es le module de correction d'ADRYNX. Corrige la réponse pour rester dans le sujet."
    prompt = f"QUESTION :\n{question}\n\nRÉPONSE À CORRIGER :\n{mauvaise_reponse}\n\nCONTEXTE :\n{contexte}\n\nProduis une nouvelle réponse correcte."
    return groq_chat(system, [{"role": "user", "content": prompt}], temperature=0.15, max_tokens=700)

def executer_response_controller(question: str, response: str, contexte: str = "", autoriser_correction: bool = True) -> str:
    controle = controler_reponse(question, response, contexte)
    if controle["ok"]:
        return response
    if not autoriser_correction:
        raise RuntimeError("Réponse non vérifiable.")
    corrected = corriger_reponse_groq(question, response, contexte)
    second_control = controler_reponse(question, corrected, contexte)
    if not second_control["ok"]:
        return reponse_identite()
    return corrected

def construire_contexte_conversation(history: list) -> str:
    if not history:
        return ""
    lignes = ["CONTEXTE CONVERSATIONNEL :"]
    for item in history[-12:]:
        role = item.get("role", "unknown")
        content = (item.get("content") or "").strip()
        if not content:
            continue
        label = "Utilisateur" if role == "user" else "ADRYNX"
        lignes.append(f"{label} : {content}")
    return "\n".join(lignes)

def construire_plan_execution(question: str, intent: str) -> Dict[str, Any]:
    plan = {"question": question, "intent": intent, "source": "conversation", "recherche": False, "type_recherche": None, "generation": True, "verification": True}
    if intent == "information_entite":
        plan["source"] = "internet"; plan["recherche"] = True; plan["type_recherche"] = "entite"
    elif intent == "recherche_internet":
        plan["source"] = "internet"; plan["recherche"] = True; plan["type_recherche"] = "web"
    elif intent == "marche_bitcoin":
        plan["source"] = "market_api"; plan["recherche"] = True; plan["type_recherche"] = "bitcoin"
    return plan

def traiter_question(question: str, owner: str = "anon", conversation_id: Optional[str] = None) -> Dict[str, Any]:
    question = (question or "").strip()
    conversation_id = ensure_conversation(owner, conversation_id)
    history = get_history(conversation_id, owner, limit=12)
    if not question:
        response = "Je n'ai reçu aucune question."
        save_message(conversation_id, owner, "user", question)
        save_message(conversation_id, owner, "assistant", response)
        return {"ok": True, "answer": response, "conversation_id": conversation_id, "intent": "vide"}
    intent = detecter_intent(question)
    plan = construire_plan_execution(question, intent)
    save_message(conversation_id, owner, "user", question)
    if intent == "salutation":
        response = reponse_salutation()
        save_message(conversation_id, owner, "assistant", response)
        return {"ok": True, "answer": response, "conversation_id": conversation_id, "intent": intent, "plan": plan}
    if intent == "etat":
        response = reponse_etat()
        save_message(conversation_id, owner, "assistant", response)
        return {"ok": True, "answer": response, "conversation_id": conversation_id, "intent": intent, "plan": plan}
    if intent == "identite":
        response = reponse_identite()
        save_message(conversation_id, owner, "assistant", response)
        return {"ok": True, "answer": response, "conversation_id": conversation_id, "intent": intent, "plan": plan}
    if intent == "resume_contexte":
        source_text = dernier_message_assistant(history)
        if not source_text:
            response = "Je n'ai pas encore de réponse précédente à résumer."
        else:
            try:
                response = resumer_contexte(question, source_text, history)
            except Exception as e:
                response = "Je n'ai pas pu produire le résumé à cet instant."
        save_message(conversation_id, owner, "assistant", response)
        return {"ok": True, "answer": response, "conversation_id": conversation_id, "intent": intent, "plan": plan}
    if intent == "marche_bitcoin":
        market = obtenir_prix_bitcoin()
        response = reponse_prix_bitcoin(market)
        save_message(conversation_id, owner, "assistant", response)
        return {"ok": True, "answer": response, "conversation_id": conversation_id, "intent": intent, "plan": plan, "source": market}
    web_context = ""
    if intent in {"information_entite", "recherche_internet"}:
        if intent == "information_entite":
            sujet = extraire_sujet_entite(question)
            recherche = rechercher_internet(sujet, nombre_resultats=6, recherche_entite=True)
        else:
            recherche = rechercher_internet(question, nombre_resultats=6, recherche_entite=False)
        if not recherche.get("ok"):
            response = "Je n'ai pas obtenu suffisamment de résultats exploitables."
            save_message(conversation_id, owner, "assistant", response)
            return {"ok": True, "answer": response, "conversation_id": conversation_id, "intent": intent, "plan": plan, "source": recherche}
        web_context = construire_contexte_web(recherche)
    conversation_context = construire_contexte_conversation(history)
    system = system_prompt()
    context_blocks = []
    if conversation_context:
        context_blocks.append(conversation_context)
    if web_context:
        context_blocks.append(web_context)
    complete_context = "\n\n".join(context_blocks)
    if complete_context:
        system += "\n\nCONTEXTE FOURNI PAR ADRYNX :\n\n" + complete_context
    try:
        response = groq_chat(system, [{"role": "user", "content": question}], temperature=0.35, max_tokens=900)
    except Exception as e:
        response = "Je n'ai pas pu générer une réponse à cet instant."
        save_message(conversation_id, owner, "assistant", response)
        return {"ok": False, "answer": response, "conversation_id": conversation_id, "intent": intent, "plan": plan, "error": str(e)}
    try:
        response = executer_response_controller(question, response, contexte=web_context, autoriser_correction=True)
    except Exception as e:
        response = reponse_identite()
    if contient_hallucination_openai(response):
        response = reponse_identite()
    save_message(conversation_id, owner, "assistant", response)
    return {"ok": True, "answer": response, "conversation_id": conversation_id, "intent": intent, "plan": plan}

def verifier_admin(secret: str):
    expected = os.getenv("ADRYNX_ADMIN_SECRET")
    if not expected:
        return False
    return secret == expected

def statistiques():
    connection = db()
    conversations = connection.execute("SELECT COUNT(*) AS total FROM conversations").fetchone()["total"]
    messages_total = connection.execute("SELECT COUNT(*) AS total FROM messages").fetchone()["total"]
    users = connection.execute("SELECT COUNT(DISTINCT owner) AS total FROM conversations").fetchone()["total"]
    connection.close()
    return {"conversations": conversations, "messages": messages_total, "owners": users}

def statistiques_apprentissage():
    connection = db()
    total = connection.execute("SELECT COUNT(*) AS total FROM intent_examples").fetchone()["total"]
    intents = connection.execute("SELECT intent, COUNT(*) AS total FROM intent_examples GROUP BY intent ORDER BY total DESC").fetchall()
    connection.close()
    return {"total_examples": total, "intents": [dict(row) for row in intents]}

def enregistrer_exemple_intent(phrase: str, intent: str):
    phrase = (phrase or "").strip()
    intent = (intent or "").strip()
    if not phrase or not intent:
        return False
    connection = db()
    connection.execute("INSERT INTO intent_examples (phrase, intent) VALUES (?,?)", (phrase, intent))
    connection.commit()
    connection.close()
    return True

def obtenir_exemples_intent(intent: Optional[str] = None, limit=100):
    connection = db()
    if intent:
        rows = connection.execute("SELECT id, phrase, intent FROM intent_examples WHERE intent=? ORDER BY id DESC LIMIT?", (intent, limit)).fetchall()
    else:
        rows = connection.execute("SELECT id, phrase, intent FROM intent_examples ORDER BY id DESC LIMIT?", (limit,)).fetchall()
    connection.close()
    return [dict(row) for row in rows]

def exporter_conversation(conversation_id: str, limit=500):
    data = messages(conversation_id, limit)
    return {"conversation_id": conversation_id, "messages": data}
