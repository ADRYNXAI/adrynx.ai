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


# ============================================================
# CONFIGURATION
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)

PHOENIX_VIDEO = "https://files.catbox.moe/y2nvi4.mp4"

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "adrynx.db"


# ============================================================
# BASE DE DONNÉES
# ============================================================

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


# ============================================================
# GROQ
# ============================================================

def groq_chat(
    system: str,
    messages: list,
    temperature: float = 0.4,
    max_tokens: int = 700
) -> str:

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY manquante dans les variables d'environnement."
        )

    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY)

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": system
            },
            *messages
        ],
        temperature=temperature,
        max_tokens=max_tokens
    )

    if not response.choices:
        raise RuntimeError(
            "Groq n'a retourné aucune réponse."
        )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "Groq a retourné une réponse vide."
        )

    return content.strip()


# ============================================================
# OUTILS DE RECHERCHE INTERNET
# ============================================================

SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"
}


def nettoyer_texte(value: str) -> str:
    if not value:
        return ""

    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


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


# ============================================================
# PRIX BITCOIN — DÉTECTION
# ============================================================

def demande_prix_bitcoin(question: str) -> bool:
    low = (question or "").lower().strip()

    mots_bitcoin = [
        "bitcoin",
        "btc"
    ]

    expressions_prix = [
        "prix",
        "cours",
        "valeur",
        "combien vaut",
        "combien coûte",
        "combien coute",
        "price",
        "cours actuel",
        "prix actuel",
        "prix maintenant",
        "valeur actuelle",
        "valeur actuelle du",
        "prix du"
    ]

    contient_bitcoin = any(
        mot in low
        for mot in mots_bitcoin
    )

    contient_prix = any(
        expression in low
        for expression in expressions_prix
    )

    if not contient_bitcoin:
        return False

    return contient_prix


# ============================================================
# BITCOIN — COINGECKO
# ============================================================

def obtenir_prix_bitcoin_coingecko() -> Dict[str, Any]:
    url = "https://api.coingecko.com/api/v3/simple/price"

    params = {
        "ids": "bitcoin",
        "vs_currencies": "usd,eur",
        "include_last_updated_at": "true"
    }

    response = requests.get(
        url,
        params=params,
        headers=SEARCH_HEADERS,
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    bitcoin = data.get("bitcoin")

    if not isinstance(bitcoin, dict):
        raise RuntimeError(
            "Réponse Bitcoin absente ou invalide."
        )

    usd = bitcoin.get("usd")
    eur = bitcoin.get("eur")
    updated_at = bitcoin.get("last_updated_at")

    if not isinstance(usd, (int, float)):
        raise RuntimeError(
            "Le prix USD retourné par CoinGecko n'est pas numérique."
        )

    if not isinstance(eur, (int, float)):
        raise RuntimeError(
            "Le prix EUR retourné par CoinGecko n'est pas numérique."
        )

    return {
        "ok": True,
        "asset": "Bitcoin",
        "symbol": "BTC",
        "usd": float(usd),
        "eur": float(eur),
        "last_updated_at": updated_at,
        "provider": "CoinGecko",
        "source_url": url
    }


# ============================================================
# BITCOIN — COINBASE
# ============================================================

def obtenir_ticker_coinbase(product_id: str) -> Dict[str, Any]:
    url = (
        "https://api.exchange.coinbase.com/"
        f"products/{product_id}/ticker"
    )

    response = requests.get(
        url,
        headers=SEARCH_HEADERS,
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    price = data.get("price")

    if price is None:
        raise RuntimeError(
            f"Prix absent dans la réponse Coinbase pour {product_id}."
        )

    try:
        price = float(price)
    except (TypeError, ValueError):
        raise RuntimeError(
            f"Prix Coinbase invalide pour {product_id}."
        )

    if price <= 0:
        raise RuntimeError(
            f"Prix Coinbase invalide pour {product_id}."
        )

    return {
        "price": price,
        "url": url
    }


def obtenir_prix_bitcoin_coinbase() -> Dict[str, Any]:
    usd_data = obtenir_ticker_coinbase("BTC-USD")
    eur_data = obtenir_ticker_coinbase("BTC-EUR")

    return {
        "ok": True,
        "asset": "Bitcoin",
        "symbol": "BTC",
        "usd": usd_data["price"],
        "eur": eur_data["price"],
        "last_updated_at": None,
        "provider": "Coinbase",
        "source_url": (
            "https://api.exchange.coinbase.com/products/"
            "BTC-USD/ticker"
        ),
        "source_url_eur": (
            "https://api.exchange.coinbase.com/products/"
            "BTC-EUR/ticker"
        )
    }


# ============================================================
# PRIX BITCOIN — SYSTÈME MULTI-SOURCE
# ============================================================

def obtenir_prix_bitcoin() -> Dict[str, Any]:
    erreurs = []

    try:
        result = obtenir_prix_bitcoin_coingecko()

        print(
            "ADRYNX MARKET: Bitcoin -> "
            f"${result['usd']} / €{result['eur']} "
            f"(source: {result['provider']})"
        )

        return result

    except Exception as e:
        erreur = (
            f"CoinGecko: {type(e).__name__}: {e}"
        )

        erreurs.append(erreur)

        print(
            "BITCOIN SOURCE 1 ERROR:",
            erreur
        )

    try:
        result = obtenir_prix_bitcoin_coinbase()

        print(
            "ADRYNX MARKET: Bitcoin -> "
            f"${result['usd']} / €{result['eur']} "
            f"(source: {result['provider']})"
        )

        return result

    except Exception as e:
        erreur = (
            f"Coinbase: {type(e).__name__}: {e}"
        )

        erreurs.append(erreur)

        print(
            "BITCOIN SOURCE 2 ERROR:",
            erreur
        )

    print(
        "========== BITCOIN MARKET ERROR =========="
    )

    for erreur in erreurs:
        print(erreur)

    print(
        "==========================================="
    )

    return {
        "ok": False,
        "error": (
            "Impossible d'obtenir actuellement le prix réel "
            "du Bitcoin. Les sources de données de marché "
            "disponibles n'ont pas fourni de donnée exploitable."
        ),
        "providers_attempted": [
            "CoinGecko",
            "Coinbase"
        ],
        "errors": erreurs
    }


# ============================================================
# CONTEXTE BITCOIN
# ============================================================

def construire_contexte_bitcoin(
    market: Dict[str, Any]
) -> str:

    if not market.get("ok"):
        return (
            "DONNÉE DE MARCHÉ BITCOIN :\n"
            "Les sources de données n'ont pas fourni de prix exploitable.\n"
            "Tu ne dois donc inventer aucune valeur."
        )

    usd = market["usd"]
    eur = market["eur"]

    provider = market.get(
        "provider",
        "source de données"
    )

    updated_at = market.get(
        "last_updated_at"
    )

    lignes = [
        "DONNÉE DE MARCHÉ RÉELLE — BITCOIN",
        f"Source : {provider}",
        f"Prix BTC en USD : {usd}",
        f"Prix BTC en EUR : {eur}",
    ]

    if updated_at:
        lignes.append(
            f"Dernière mise à jour fournie par la source : {updated_at}"
        )

    lignes.extend([
        "",
        "IMPORTANT :",
        "Ces valeurs viennent directement d'une source de données réelle.",
        "Ne les modifie pas et n'en invente pas d'autres.",
        "Si tu expliques ces données, conserve exactement les valeurs numériques fournies."
    ])

    return "\n".join(lignes)


# ============================================================
# RÉPONSE BITCOIN
# ============================================================

def reponse_prix_bitcoin(
    market: Dict[str, Any]
) -> str:

    if not market.get("ok"):
        return (
            "Je n'ai pas pu obtenir le prix réel du Bitcoin "
            "auprès de mes sources de données de marché à cet instant. "
            "Je préfère ne pas donner une valeur qui pourrait être fausse."
        )

    usd = market["usd"]
    eur = market["eur"]

    provider = market.get(
        "provider",
        "source de données"
    )

    return (
        "Le prix actuel du Bitcoin fourni par ma source de données "
        "de marché est de "
        f"{usd:,.2f} USD, soit environ {eur:,.2f} EUR.\n\n"
        f"Source : {provider}.\n"
        "Le prix du Bitcoin évolue en permanence."
    )


# ============================================================
# PARSEUR DUCKDUCKGO HTML
# ============================================================

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

            if (
                "result__a" in class_list
                and href
            ):
                self.current_url = href
                self.current_title = []
                self.current_description = []

                self.in_title = True

        if (
            "result__snippet" in class_list
            or "result__body" in class_list
        ):
            self.in_description = True

    def handle_data(self, data):
        if self.in_title:
            self.current_title.append(data)

        if self.in_description:
            self.current_description.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.in_title:
            title = nettoyer_texte(
                "".join(self.current_title)
            )

            description = nettoyer_texte(
                "".join(self.current_description)
            )

            clean_url = nettoyer_url(
                self.current_url
            )

            if clean_url and title:
                self.results.append({
                    "title": title,
                    "url": clean_url,
                    "description": description
                })

            self.current_url = ""
            self.current_title = []
            self.current_description = []

            self.in_title = False


# ============================================================
# PARSEUR DUCKDUCKGO LITE
# ============================================================

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

            if (
                "result-link" in class_list
                and href
            ):
                self.current_url = href
                self.current_title = []
                self.in_result = True

    def handle_data(self, data):
        if self.in_result:
            self.current_title.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.in_result:
            title = nettoyer_texte(
                "".join(self.current_title)
            )

            clean_url = nettoyer_url(
                self.current_url
            )

            if clean_url and title:
                self.results.append({
                    "title": title,
                    "url": clean_url,
                    "description": ""
                })

            self.current_url = ""
            self.current_title = []
            self.in_result = False


# ============================================================
# PARSEUR BING
# ============================================================

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

        if tag in {"p", "div"}:
            if "b_caption" in class_list:
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
            title = nettoyer_texte(
                "".join(self.current_title)
            )

            description = nettoyer_texte(
                "".join(self.current_description)
            )

            clean_url = nettoyer_url(
                self.current_url
            )

            if clean_url and title:
                self.results.append({
                    "title": title,
                    "url": clean_url,
                    "description": description
                })

            self.in_result = False
            self.in_title = False
            self.in_description = False

            self.current_url = ""
            self.current_title = []
            self.current_description = []


# ============================================================
# NORMALISATION DES RÉSULTATS
# ============================================================

def normaliser_resultats(
    results,
    nombre_resultats: int = 6
):
    final = []
    urls = set()

    for result in results:
        url = nettoyer_url(
            result.get("url", "")
        )

        title = nettoyer_texte(
            result.get("title", "")
        )

        description = nettoyer_texte(
            result.get("description", "")
        )

        if not url or not title:
            continue

        if url in urls:
            continue

        urls.add(url)

        final.append({
            "title": title,
            "url": url,
            "description": description
        })

        if len(final) >= nombre_resultats:
            break

    return final


# ============================================================
# RECHERCHE DUCKDUCKGO HTML
# ============================================================

def rechercher_duckduckgo(
    question: str,
    nombre_resultats: int = 6
):
    url = "https://html.duckduckgo.com/html/"

    try:
        response = requests.get(
            url,
            params={
                "q": question
            },
            headers=SEARCH_HEADERS,
            timeout=15
        )

        response.raise_for_status()

        parser = DuckDuckGoParser()
        parser.feed(response.text)

        results = normaliser_resultats(
            parser.results,
            nombre_resultats
        )

        return results

    except Exception as e:
        print(
            "DUCKDUCKGO HTML ERROR:",
            type(e).__name__,
            str(e)
        )

        return []


# ============================================================
# RECHERCHE DUCKDUCKGO LITE
# ============================================================

def rechercher_duckduckgo_lite(
    question: str,
    nombre_resultats: int = 6
):
    url = "https://lite.duckduckgo.com/lite/"

    try:
        response = requests.get(
            url,
            params={
                "q": question
            },
            headers=SEARCH_HEADERS,
            timeout=15
        )

        response.raise_for_status()

        parser = DuckDuckGoLiteParser()
        parser.feed(response.text)

        results = normaliser_resultats(
            parser.results,
            nombre_resultats
        )

        return results

    except Exception as e:
        print(
            "DUCKDUCKGO LITE ERROR:",
            type(e).__name__,
            str(e)
        )

        return []


# ============================================================
# RECHERCHE BING
# ============================================================

def rechercher_bing(
    question: str,
    nombre_resultats: int = 6
):
    url = "https://www.bing.com/search"

    try:
        response = requests.get(
            url,
            params={
                "q": question
            },
            headers=SEARCH_HEADERS,
            timeout=15
        )

        response.raise_for_status()

        parser = BingParser()
        parser.feed(response.text)

        results = normaliser_resultats(
            parser.results,
            nombre_resultats
        )

        return results

    except Exception as e:
        print(
            "BING SEARCH ERROR:",
            type(e).__name__,
            str(e)
        )

        return []


# ============================================================
# RECHERCHE INTERNET PRINCIPALE
# ============================================================

def rechercher_internet(
    question: str,
    nombre_resultats: int = 6
) -> Dict[str, Any]:

    question = (question or "").strip()

    if not question:
        return {
            "ok": False,
            "error": "Recherche vide.",
            "results": []
        }

    results = rechercher_duckduckgo(
        question,
        nombre_resultats
    )

    if results:
        print(
            f"ADRYNX INTERNET: DuckDuckGo HTML -> "
            f"{len(results)} résultat(s)"
        )

        return {
            "ok": True,
            "provider": "duckduckgo-html",
            "query": question,
            "results": results
        }

    results = rechercher_duckduckgo_lite(
        question,
        nombre_resultats
    )

    if results:
        print(
            f"ADRYNX INTERNET: DuckDuckGo Lite -> "
            f"{len(results)} résultat(s)"
        )

        return {
            "ok": True,
            "provider": "duckduckgo-lite",
            "query": question,
            "results": results
        }

    results = rechercher_bing(
        question,
        nombre_resultats
    )

    if results:
        print(
            f"ADRYNX INTERNET: Bing -> "
            f"{len(results)} résultat(s)"
        )

        return {
            "ok": True,
            "provider": "bing",
            "query": question,
            "results": results
        }

    print(
        "========== ADRYNX INTERNET ERROR =========="
    )

    print(
        "Aucun moteur n'a retourné de résultat exploitable."
    )

    print(
        "============================================"
    )

    return {
        "ok": False,
        "error": (
            "ADRYNX a essayé plusieurs méthodes de recherche "
            "Internet, mais aucun résultat exploitable n'a été "
            "retourné."
        ),
        "results": []
    }


# ============================================================
# DÉTECTION D'UNE DEMANDE INTERNET
# ============================================================

def demande_recherche_internet(question: str) -> bool:
    low = question.lower().strip()

    expressions = [
        "recherche sur internet",
        "rechercher sur internet",
        "cherche sur internet",
        "recherche internet",
        "rechercher internet",
        "cherche internet",

        "cherche sur le web",
        "recherche sur le web",
        "rechercher sur le web",
        "sur internet",
        "sur le web",

        "en ligne",

        "actualités",
        "actualité",
        "actualite",

        "prix actuel",
        "prix actuelle",
        "prix actuel maintenant",

        "maintenant",
        "aujourd'hui",
        "aujourd’hui",
        "actuellement",

        "cours actuel",
        "cours actuel de",
        "valeur actuelle",

        "dernières nouvelles",
        "derniere nouvelle",
        "dernière nouvelle",
        "dernières infos",
        "derniere info",

        "news",
        "latest",

        "récent",
        "récente",
        "récents",
        "récentes",

        "recent",
        "recente",
        "recents",
        "recentes"
    ]

    for expression in expressions:
        if expression in low:
            return True

    return False


# ============================================================
# CONVERSATIONS
# ============================================================

def new_conversation(
    owner: str = "anon",
    titre: str = "Nouvelle conversation"
) -> str:

    conversation_id = "conv_" + uuid.uuid4().hex

    connection = db()

    connection.execute(
        """
        INSERT INTO conversations (
            id,
            owner,
            titre
        )
        VALUES (?, ?, ?)
        """,
        (
            conversation_id,
            owner,
            titre
        )
    )

    connection.commit()
    connection.close()

    return conversation_id


def ensure_conversation(
    owner: str,
    conversation_id: Optional[str]
) -> str:

    if conversation_id:
        connection = db()

        row = connection.execute(
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

        connection.close()

        if row:
            return conversation_id

    return new_conversation(
        owner,
        "Conversation ADRYNX"
    )


# ============================================================
# MESSAGES
# ============================================================

def save_message(
    conversation_id: str,
    owner: str,
    role: str,
    content: str
):
    connection = db()

    connection.execute(
        """
        INSERT INTO messages (
            conversation_id,
            owner,
            role,
            content
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            conversation_id,
            owner,
            role,
            content
        )
    )

    connection.execute(
        """
        UPDATE conversations
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            conversation_id,
        )
    )

    connection.commit()
    connection.close()


def get_history(
    conversation_id: str,
    owner: str,
    limit: int = 12
):
    connection = db()

    rows = connection.execute(
        """
        SELECT role, content
        FROM messages
        WHERE conversation_id = ?
        AND owner = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (
            conversation_id,
            owner,
            limit
        )
    ).fetchall()

    connection.close()

    rows = list(reversed(rows))

    return [
        {
            "role": row["role"],
            "content": row["content"]
        }
        for row in rows
    ]


def state(conversation_id: str):
    connection = db()

    row = connection.execute(
        """
        SELECT *
        FROM conversations
        WHERE id = ?
        """,
        (
            conversation_id,
        )
    ).fetchone()

    connection.close()

    if not row:
        return {}

    return dict(row)


def messages(
    conversation_id: str,
    limit: int = 50
):
    connection = db()

    rows = connection.execute(
        """
        SELECT
            id,
            role,
            content,
            created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id ASC
        LIMIT ?
        """,
        (
            conversation_id,
            limit
        )
    ).fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# COMPRÉHENSION DE BASE
# ============================================================

def detecter_intent(question: str) -> str:
    low = (question or "").lower().strip()

    low = (
        low
        .replace("’", "'")
        .replace("`", "'")
    )

    low = re.sub(
        r"\s+",
        " ",
        low
    )

    if not low:
        return "vide"

    # --------------------------------------------------------
    # SALUTATIONS
    # --------------------------------------------------------

    if low in {
        "cc",
        "slt",
        "salut",
        "yo",
        "hey",
        "bjr",
        "bonjour",
        "bonsoir",
        "coucou"
    }:
        return "salutation"

    # --------------------------------------------------------
    # ÉTAT / COMMENT VA ADRYNX
    # --------------------------------------------------------

    expressions_etat = [
        "comment vas tu",
        "comment vas-tu",
        "comment tu vas",
        "ça va",
        "ca va",
        "tu vas bien",
        "vas tu bien",
        "vas-tu bien",
        "comment allez vous",
        "comment allez-vous"
    ]

    if any(
        expression in low
        for expression in expressions_etat
    ):
        return "etat"

    # --------------------------------------------------------
    # IDENTITÉ / CRÉATEUR D'ADRYNX
    # --------------------------------------------------------

    expressions_identite = [
        "qui es tu",
        "qui es-tu",
        "tu es qui",

        "qui t'a créé",
        "qui t'as créé",
        "qui ta créé",

        "qui est ton créateur",
        "qui est ton createur",

        "qui t'a développé",
        "qui t'as développé",
        "qui ta développé",

        "qui t'a developpé",
        "qui t'as developpé",
        "qui ta developpé",

        "qui t'a developpe",
        "qui t'as developpe",
        "qui ta developpe",

        "qui est ton développeur",
        "qui est ton developpeur",

        "qui a créé adrynx",
        "qui a cree adrynx",

        "qui a développé adrynx",
        "qui a developpe adrynx",
        "qui a developpé adrynx",

        "qui a conçu adrynx",
        "qui a concu adrynx",

        "qui est derrière adrynx",
        "qui est derriere adrynx",

        "qui a fait adrynx",
        "qui a fabriqué adrynx",
        "qui a fabrique adrynx",

        "qui a conçu ton système",
        "qui a concu ton systeme",

        "qui t'a conçu",
        "qui t'as conçu",
        "qui t'a concu",
        "qui t'as concu"
    ]

    if any(
        expression in low
        for expression in expressions_identite
    ):
        return "identite"

    # --------------------------------------------------------
    # BITCOIN
    # --------------------------------------------------------

    if demande_prix_bitcoin(question):
        return "marche_bitcoin"

    return "conversation"


# ============================================================
# IDENTITÉ
# ============================================================

def reponse_identite():
    return (
        "Je suis ADRYNX, l'assistant développé par "
        "Jonathan Dejah OBENDA. "
        "Je suis conçu pour comprendre les conversations, "
        "utiliser leur contexte et évoluer avec les fonctions "
        "réellement ajoutées à mon système."
    )


# ============================================================
# RÉPONSE ÉTAT
# ============================================================

def reponse_etat():
    return (
        "Je vais bien. Je suis actuellement opérationnel "
        "et prêt à poursuivre notre conversation."
    )


# ============================================================
# CAPACITÉS RÉELLES
# ============================================================

def system_prompt():
    return """
Tu es ADRYNX.

Tu es un assistant conversationnel réel intégré dans une
application appelée ADRYNX.

CAPACITÉS ACTUELLEMENT RÉELLES :

* Tu peux converser avec l'utilisateur grâce au modèle Groq.
* Tu peux utiliser l'historique de la conversation fourni par
  ton backend.
* Le backend sauvegarde les messages dans une base SQLite.
* Le backend peut effectuer une recherche Internet réelle
  lorsque la demande de l'utilisateur nécessite une recherche.
* Plusieurs moteurs ou méthodes de recherche peuvent être
  utilisés par le backend.
* Le backend peut également récupérer certaines données
  structurées depuis des sources externes réelles.
* Lorsque des résultats Internet sont fournis dans le contexte,
  tu peux les analyser et les résumer.
* Tu peux répondre en français lorsque l'utilisateur écrit
  en français.

CAPACITÉS QUI NE DOIVENT PAS ÊTRE PRÉSENTÉES COMME ACTIVES
SI ELLES NE SONT PAS FOURNIES DANS LE CONTEXTE :

* mémoire personnelle persistante intelligente ;
* apprentissage autonome ;
* raisonnement spécialisé indépendant ;
* système de parents IA ;
* accès arbitraire aux services externes ;
* exécution d'actions sur l'appareil de l'utilisateur ;
* projets et tâches persistants si aucune fonction correspondante
  n'est fournie.

RÈGLES :

1. Reste sur le sujet de l'utilisateur.

2. Utilise le contexte précédent lorsqu'il est disponible.

3. Si l'utilisateur change de sujet, suis naturellement le
   nouveau sujet.

4. Une salutation simple doit recevoir une réponse naturelle.

5. Si l'utilisateur demande comment tu vas, réponds directement
   à cette question.

6. Ne prétends jamais avoir effectué une action que tu n'as pas
   réellement effectuée.

7. Ne prétends jamais avoir utilisé Internet si aucun résultat
   Internet ne t'a été fourni.

8. Ne fabrique jamais un résultat de recherche.

9. Si une recherche Internet est fournie, distingue clairement
   les informations trouvées sur Internet de tes connaissances
   générales.

10. Pour une information actuelle, utilise les données externes
    réelles lorsqu'elles sont disponibles.

11. Si une recherche Internet échoue, indique clairement que la
    recherche a échoué.

12. Si les résultats disponibles ne permettent pas de répondre
    précisément, dis-le clairement.

13. Ne fabrique pas de faits.

14. Ne fabrique pas de fonctionnalités inexistantes dans ADRYNX.

15. Réponds en français lorsque l'utilisateur écrit en français.

16. Lorsque la question est simple, réponds simplement.

17. Lorsque l'utilisateur demande une explication détaillée,
    développe suffisamment pour être utile.

18. Ne parle pas de ton architecture interne sauf si
    l'utilisateur le demande explicitement.

19. Ne prétends pas avoir une mémoire permanente si elle n'est
    pas réellement activée.

20. Sois transparent sur tes limites réelles.

21. Lorsque des résultats Internet sont fournis, utilise-les
    comme source prioritaire pour les informations actuelles.

22. Ne donne pas un prix, une valeur ou une information actuelle
    précise si les données fournies ne permettent pas de
    l'établir.

23. Si plusieurs résultats Internet se contredisent, indique
    cette divergence au lieu de choisir arbitrairement une valeur.

24. Pour une donnée numérique structurée fournie directement
    par le backend, conserve exactement la valeur fournie.
"""


# ============================================================
# CONSTRUCTION DU CONTEXTE INTERNET
# ============================================================

def construire_contexte_web(
    question: str,
    recherche: Dict[str, Any]
) -> str:

    lignes = []

    provider = recherche.get(
        "provider",
        "moteur de recherche"
    )

    lignes.append(
        "RÉSULTATS D'UNE RECHERCHE INTERNET RÉELLE"
    )

    lignes.append(
        f"Moteur/méthode utilisée : {provider}"
    )

    lignes.append(
        f"Question recherchée : {question}"
    )

    lignes.append("")

    for index, result in enumerate(
        recherche.get("results", []),
        start=1
    ):
        lignes.append(
            f"Résultat {index} :"
        )

        lignes.append(
            f"Titre : {result.get('title', '')}"
        )

        lignes.append(
            f"URL : {result.get('url', '')}"
        )

        description = result.get(
            "description",
            ""
        )

        if description:
            lignes.append(
                f"Extrait : {description}"
            )

        lignes.append("")

    return "\n".join(lignes)


# ============================================================
# RESPONSE CONTROLLER — NORMALISATION
# ============================================================

def normaliser_pour_controle(texte: str) -> str:
    """
    Prépare un texte pour une comparaison simple de pertinence.
    Ce contrôle est volontairement déterministe : il ne prétend
    pas comprendre parfaitement le sens d'une phrase.
    """

    texte = (texte or "").lower()

    texte = (
        texte
        .replace("’", "'")
        .replace("à", "a")
        .replace("â", "a")
        .replace("ä", "a")
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("ë", "e")
        .replace("î", "i")
        .replace("ï", "i")
        .replace("ô", "o")
        .replace("ö", "o")
        .replace("ù", "u")
        .replace("û", "u")
        .replace("ü", "u")
        .replace("ç", "c")
    )

    texte = re.sub(
        r"[^a-z0-9\s'-]",
        " ",
        texte
    )

    texte = re.sub(
        r"\s+",
        " ",
        texte
    )

    return texte.strip()


# ============================================================
# RESPONSE CONTROLLER — MOTS IMPORTANTS
# ============================================================

MOTS_VIDES_CONTROLE = {
    "le", "la", "les",
    "un", "une", "des",
    "du", "de", "d",
    "au", "aux",
    "et", "ou",
    "mais", "donc",
    "or", "ni", "car",
    "a", "as", "ai", "ont",
    "est", "sont", "etre",
    "es", "tu", "te", "toi",
    "je", "me", "moi",
    "il", "elle", "ils", "elles",
    "nous", "vous",
    "ce", "cet", "cette", "ces",
    "qui", "que", "quoi",
    "quel", "quelle", "quels", "quelles",
    "comment", "pourquoi",
    "quand", "ou",
    "dans", "sur", "avec",
    "pour", "par",
    "sans", "sous",
    "entre",
    "mon", "ton", "son",
    "ma", "ta", "sa",
    "mes", "tes", "ses",
    "notre", "votre", "leur",
    "nos", "vos", "leurs",
    "est-ce",
    "ceci", "cela",
    "ca",
    "ne", "pas",
    "plus", "moins",
    "très", "tres",
    "bien",
    "donc"
}


def extraire_mots_importants(texte: str):
    texte = normaliser_pour_controle(texte)

    mots = re.findall(
        r"\b[a-z0-9]{3,}\b",
        texte
    )

    resultats = []

    for mot in mots:
        if mot in MOTS_VIDES_CONTROLE:
            continue

        if mot not in resultats:
            resultats.append(mot)

    return resultats


# ============================================================
# RESPONSE CONTROLLER — PERTINENCE
# ============================================================

def analyser_pertinence(
    question: str,
    response: str
) -> Dict[str, Any]:
    """
    Contrôle lexical déterministe.

    Ce n'est PAS présenté comme une compréhension sémantique
    parfaite. Il cherche des indices objectifs permettant de
    détecter certaines réponses manifestement hors sujet.
    """

    question = (question or "").strip()
    response = (response or "").strip()

    if not question or not response:
        return {
            "ok": False,
            "score": 0.0,
            "raison": "Question ou réponse vide."
        }

    question_words = extraire_mots_importants(question)
    response_words = set(
        extraire_mots_importants(response)
    )

    if not question_words:
        return {
            "ok": True,
            "score": 1.0,
            "raison": "Question trop courte pour un contrôle lexical."
        }

    correspondances = [
        mot
        for mot in question_words
        if mot in response_words
    ]

    score = (
        len(correspondances)
        / len(question_words)
    )

    # Pour les questions très courtes, un seul mot commun
    # suffit généralement comme indice.
    if len(question_words) <= 2:
        pertinent = len(correspondances) >= 1
    elif len(question_words) <= 4:
        pertinent = score >= 0.25
    else:
        pertinent = score >= 0.20

    return {
        "ok": pertinent,
        "score": round(score, 3),
        "question_words": question_words,
        "matched_words": correspondances,
        "raison": (
            "Indices lexicaux suffisants."
            if pertinent
            else "Trop peu de termes importants de la question "
                 "apparaissent dans la réponse."
        )
    }


# ============================================================
# RESPONSE CONTROLLER — FRAÎCHEUR
# ============================================================

def question_exigeant_actualite(question: str) -> bool:
    """
    Détecte les formulations indiquant qu'une information doit
    être actuelle ou récente.
    """

    return demande_recherche_internet(question)


def verifier_fraicheur(
    question: str,
    source: str,
    web_results
) -> Dict[str, Any]:

    exige_actualite = question_exigeant_actualite(
        question
    )

    recherche_reelle = bool(
        web_results
    )

    if exige_actualite and not recherche_reelle:
        return {
            "ok": False,
            "reason": (
                "La question demande une information actuelle "
                "mais aucune donnée Internet réelle n'est disponible."
            )
        }

    return {
        "ok": True,
        "reason": (
            "La fraîcheur demandée est compatible avec les "
            "données fournies."
        )
    }


# ============================================================
# RESPONSE CONTROLLER — CONTRÔLE GLOBAL
# ============================================================

def controler_reponse(
    question: str,
    response: str,
    source: str,
    web_results=None
) -> Dict[str, Any]:

    web_results = web_results or []

    pertinence = analyser_pertinence(
        question,
        response
    )

    fraicheur = verifier_fraicheur(
        question,
        source,
        web_results
    )

    valide = (
        pertinence["ok"]
        and fraicheur["ok"]
        and bool(response.strip())
    )

    return {
        "ok": valide,
        "pertinence": pertinence,
        "fraicheur": fraicheur,
        "source": source
    }


# ============================================================
# RESPONSE CONTROLLER — CORRECTION GROQ
# ============================================================

def corriger_reponse_groq(
    question: str,
    response: str,
    history: list,
    web_context: Optional[str] = None
) -> str:

    contexte_web = ""

    if web_context:
        contexte_web = (
            "\n\nDONNÉES INTERNET DISPONIBLES :\n"
            + web_context
        )

    correction_system = """
Tu es le module de correction de réponse d'ADRYNX.

Une première réponse a été générée, mais le contrôleur ADRYNX
a détecté qu'elle pouvait être hors sujet ou insuffisamment
alignée avec la question.

Ta tâche est de produire UNE NOUVELLE réponse qui répond
directement à la question de l'utilisateur.

RÈGLES :

1. Réponds uniquement à la question.
2. Ne change pas de sujet.
3. Ne fabrique aucune information.
4. N'invente aucune source.
5. Si des données Internet sont fournies, utilise-les.
6. Si les données Internet ne permettent pas d'établir un fait,
   indique-le.
7. Ne parle pas du processus de correction.
8. Ne dis pas que tu as été corrigé.
9. Réponds dans la langue de l'utilisateur.
"""

    messages = [
        {
            "role": "user",
            "content": (
                "QUESTION DE L'UTILISATEUR :\n"
                f"{question}\n\n"
                "PREMIÈRE RÉPONSE À CORRIGER :\n"
                f"{response}"
                f"{contexte_web}"
            )
        }
    ]

    # L'historique n'est ajouté que s'il existe.
    if history:
        messages.insert(
            0,
            {
                "role": "system",
                "content": (
                    "HISTORIQUE DISPONIBLE :\n"
                    + "\n".join(
                        f"{item.get('role', '')}: "
                        f"{item.get('content', '')}"
                        for item in history[-6:]
                    )
                )
            }
        )

    return groq_chat(
        correction_system,
        messages,
        temperature=0.2,
        max_tokens=700
    )


# ============================================================
# RESPONSE CONTROLLER — PIPELINE
# ============================================================

def executer_response_controller(
    question: str,
    response: str,
    source: str,
    history: list,
    web_results=None,
    web_context: Optional[str] = None
) -> Dict[str, Any]:

    web_results = web_results or []

    controle = controler_reponse(
        question,
        response,
        source,
        web_results
    )

    print(
        "ADRYNX CONTROLLER:",
        {
            "ok": controle["ok"],
            "pertinence": controle["pertinence"]["score"],
            "fraicheur": controle["fraicheur"]["ok"],
            "source": source
        }
    )

    if controle["ok"]:
        return {
            "ok": True,
            "response": response,
            "controller": controle,
            "corrected": False
        }

    print(
        "ADRYNX CONTROLLER: "
        "réponse nécessitant une correction."
    )

    try:
        corrected = corriger_reponse_groq(
            question,
            response,
            history,
            web_context
        )

        corrected_control = controler_reponse(
            question,
            corrected,
            source,
            web_results
        )

        print(
            "ADRYNX CONTROLLER AFTER CORRECTION:",
            {
                "ok": corrected_control["ok"],
                "pertinence": corrected_control[
                    "pertinence"
                ]["score"],
                "fraicheur": corrected_control[
                    "fraicheur"
                ]["ok"]
            }
        )

        if corrected_control["ok"]:
            return {
                "ok": True,
                "response": corrected,
                "controller": corrected_control,
                "corrected": True
            }

        # On ne renvoie pas une deuxième réponse arbitraire
        # comme si elle était validée.
        return {
            "ok": False,
            "error": (
                "ADRYNX n'a pas pu produire une réponse "
                "suffisamment vérifiable et pertinente."
            ),
            "controller": corrected_control,
            "corrected": True
        }

    except Exception as e:
        print(
            "ADRYNX CONTROLLER CORRECTION ERROR:",
            type(e).__name__,
            str(e)
        )

        return {
            "ok": False,
            "error": (
                "ADRYNX a détecté un problème de pertinence "
                "et la correction automatique a échoué."
            ),
            "controller": controle,
            "corrected": False
        }


# ============================================================
# TRAITEMENT PRINCIPAL
# ============================================================

def traiter_question(
    question: str,
    owner: str = "anon",
    conversation_id: Optional[str] = None
) -> Dict[str, Any]:

    question = (question or "").strip()

    owner = (
        (owner or "anon")
        .strip()[:120]
        or "anon"
    )

    if not question:
        return {
            "ok": False,
            "error": "Message vide."
        }

    conversation_id = ensure_conversation(
        owner,
        conversation_id
    )

    intent = detecter_intent(question)

    # --------------------------------------------------------
    # IDENTITÉ
    # --------------------------------------------------------

    if intent == "identite":
        response = reponse_identite()

        save_message(
            conversation_id,
            owner,
            "user",
            question
        )

        save_message(
            conversation_id,
            owner,
            "assistant",
            response
        )

        return {
            "ok": True,
            "reponse": response,
            "intent": intent,
            "source": "noyau",
            "conversation_id": conversation_id,
            "video_core": PHOENIX_VIDEO,
            "controller": {
                "ok": True,
                "type": "noyau"
            }
        }

    # --------------------------------------------------------
    # ÉTAT
    # --------------------------------------------------------

    if intent == "etat":
        response = reponse_etat()

        save_message(
            conversation_id,
            owner,
            "user",
            question
        )

        save_message(
            conversation_id,
            owner,
            "assistant",
            response
        )

        return {
            "ok": True,
            "reponse": response,
            "intent": intent,
            "source": "noyau",
            "conversation_id": conversation_id,
            "video_core": PHOENIX_VIDEO,
            "controller": {
                "ok": True,
                "type": "noyau"
            }
        }

    # --------------------------------------------------------
    # HISTORIQUE
    # --------------------------------------------------------

    save_message(
        conversation_id,
        owner,
        "user",
        question
    )

    history = get_history(
        conversation_id,
        owner,
        limit=12
    )

    # --------------------------------------------------------
    # DONNÉE BITCOIN STRUCTURÉE
    # --------------------------------------------------------

    if demande_prix_bitcoin(question):
        market = obtenir_prix_bitcoin()

        if not market.get("ok"):
            return {
                "ok": False,
                "error": market.get(
                    "error",
                    "Impossible d'obtenir le prix réel du Bitcoin."
                ),
                "intent": intent,
                "conversation_id": conversation_id,
                "source": "bitcoin-api-error",
                "market_data": market,
                "video_core": PHOENIX_VIDEO
            }

        response = reponse_prix_bitcoin(
            market
        )

        save_message(
            conversation_id,
            owner,
            "assistant",
            response
        )

        return {
            "ok": True,
            "reponse": response,
            "intent": intent,
            "source": "bitcoin-api",
            "conversation_id": conversation_id,
            "market_data": market,
            "video_core": PHOENIX_VIDEO,
            "controller": {
                "ok": True,
                "type": "structured-market-data"
            }
        }

    # --------------------------------------------------------
    # RECHERCHE INTERNET RÉELLE
    # --------------------------------------------------------

    web_results = []
    web_context = None

    if demande_recherche_internet(question):
        recherche = rechercher_internet(
            question,
            nombre_resultats=6
        )

        if not recherche.get("ok"):
            return {
                "ok": False,
                "error": recherche.get(
                    "error",
                    "La recherche Internet a échoué."
                ),
                "intent": intent,
                "conversation_id": conversation_id,
                "source": "internet-error",
                "video_core": PHOENIX_VIDEO
            }

        web_results = recherche.get(
            "results",
            []
        )

        web_context = construire_contexte_web(
            question,
            recherche
        )

        history_for_groq = [
            {
                "role": "system",
                "content": web_context
            },
            *history
        ]

        source = "internet+groq"

    else:
        history_for_groq = history
        source = "groq"

    # --------------------------------------------------------
    # GROQ
    # --------------------------------------------------------

    try:
        response = groq_chat(
            system_prompt(),
            history_for_groq,
            temperature=0.4,
            max_tokens=700
        )

    except Exception as e:
        print(
            "========== ADRYNX GROQ ERROR =========="
        )

        print(
            type(e).__name__
        )

        print(
            str(e)
        )

        print(
            "========================================"
        )

        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "intent": intent,
            "conversation_id": conversation_id,
            "source": "groq-error",
            "video_core": PHOENIX_VIDEO
        }

    # --------------------------------------------------------
    # CONTRÔLE DE RÉPONSE ADRYNX
    # --------------------------------------------------------

    controller = executer_response_controller(
        question,
        response,
        source,
        history,
        web_results,
        web_context
    )

    if not controller.get("ok"):
        return {
            "ok": False,
            "error": controller.get(
                "error",
                "ADRYNX n'a pas validé la réponse générée."
            ),
            "intent": intent,
            "conversation_id": conversation_id,
            "source": "response-controller-error",
            "controller": controller.get(
                "controller",
                {}
            ),
            "video_core": PHOENIX_VIDEO
        }

    response = controller["response"]

    # --------------------------------------------------------
    # SAUVEGARDE
    # --------------------------------------------------------

    save_message(
        conversation_id,
        owner,
        "assistant",
        response
    )

    result = {
        "ok": True,
        "reponse": response,
        "intent": intent,
        "source": source,
        "conversation_id": conversation_id,
        "video_core": PHOENIX_VIDEO,
        "controller": {
            "ok": True,
            "corrected": controller.get(
                "corrected",
                False
            )
        }
    }

    if web_results:
        result["web_results"] = web_results

    return result


# ============================================================
# DASHBOARD
# ============================================================

def dashboard(owner: str):
    connection = db()

    conversations = connection.execute(
        """
        SELECT COUNT(*)
        FROM conversations
        WHERE owner = ?
        """,
        (
            owner,
        )
    ).fetchone()[0]

    total_messages = connection.execute(
        """
        SELECT COUNT(*)
        FROM messages
        WHERE owner = ?
        """,
        (
            owner,
        )
    ).fetchone()[0]

    connection.close()

    return {
        "video": PHOENIX_VIDEO,
        "conversations": conversations,
        "messages": total_messages,
        "groq_configured": bool(GROQ_API_KEY),
        "model": GROQ_MODEL,
        "internet_search": True,
        "bitcoin_market_data": True,
        "response_controller": True
    }


# ============================================================
# FONCTIONS FUTURES — PAS SIMULÉES
# ============================================================

def projects(owner: str):
    return []


def project(
    owner: str,
    name: str,
    obj=None
):
    return {
        "nom": name,
        "owner": owner,
        "data": obj or {}
    }


def task(
    owner: str,
    title: str,
    project_id=None
):
    return {
        "titre": title,
        "owner": owner,
        "project_id": project_id
    }


def enregistrer_feedback(*args):
    return {
        "ok": False,
        "error": (
            "Le système d'apprentissage par feedback "
            "n'est pas encore activé."
        )
    }


def stats_apprentissage():
    connection = db()

    total_messages = connection.execute(
        "SELECT COUNT(*) FROM messages"
    ).fetchone()[0]

    total_conversations = connection.execute(
        "SELECT COUNT(*) FROM conversations"
    ).fetchone()[0]

    connection.close()

    return {
        "video": PHOENIX_VIDEO,
        "messages": total_messages,
        "conversations": total_conversations
    }


def exporter_apprentissage():
    connection = db()

    rows = connection.execute(
        """
        SELECT phrase, intent
        FROM intent_examples
        ORDER BY id ASC
        """
    ).fetchall()

    connection.close()

    return [
        {
            "phrase": row["phrase"],
            "intent": row["intent"]
        }
        for row in rows
    ]


# ============================================================
# ADMIN
# ============================================================

def verifier_admin(secret: str):
    expected = os.getenv(
        "ADRYNX_ADMIN_SECRET"
    )

    if not expected:
        return False

    return secret == expected
