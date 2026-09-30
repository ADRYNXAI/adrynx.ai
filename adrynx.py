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
# BASE DE DONNÃ‰ES
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
            "Groq n'a retournÃ© aucune rÃ©ponse."
        )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "Groq a retournÃ© une rÃ©ponse vide."
        )

    return content.strip()


# ============================================================
# OUTILS DE RECHERCHE INTERNET
# ============================================================

SEARCH_HEADERS = {
    "User-Agent": (
        "ADRYNX/7.1 "
        "(https://adrynx-ai.onrender.com)"
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
# PRIX BITCOIN â€” DÃ‰TECTION
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
        "combien coÃ»te",
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
# BITCOIN â€” COINGECKO
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
            "RÃ©ponse Bitcoin absente ou invalide."
        )

    usd = bitcoin.get("usd")
    eur = bitcoin.get("eur")
    updated_at = bitcoin.get("last_updated_at")

    if not isinstance(usd, (int, float)):
        raise RuntimeError(
            "Le prix USD retournÃ© par CoinGecko n'est pas numÃ©rique."
        )

    if not isinstance(eur, (int, float)):
        raise RuntimeError(
            "Le prix EUR retournÃ© par CoinGecko n'est pas numÃ©rique."
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
# BITCOIN â€” COINBASE
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
            f"Prix absent dans la rÃ©ponse Coinbase pour {product_id}."
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
# PRIX BITCOIN â€” SYSTÃˆME MULTI-SOURCE
# ============================================================

def obtenir_prix_bitcoin() -> Dict[str, Any]:
    erreurs = []

    try:
        result = obtenir_prix_bitcoin_coingecko()

        print(
            "ADRYNX MARKET: Bitcoin -> "
            f"${result['usd']} / â‚¬{result['eur']} "
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
            f"${result['usd']} / â‚¬{result['eur']} "
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
            "Impossible d'obtenir actuellement le prix rÃ©el "
            "du Bitcoin. Les sources de donnÃ©es de marchÃ© "
            "disponibles n'ont pas fourni de donnÃ©e exploitable."
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
            "DONNÃ‰E DE MARCHÃ‰ BITCOIN :\n"
            "Les sources de donnÃ©es n'ont pas fourni de prix exploitable.\n"
            "Tu ne dois donc inventer aucune valeur."
        )

    usd = market["usd"]
    eur = market["eur"]

    provider = market.get(
        "provider",
        "source de donnÃ©es"
    )

    updated_at = market.get(
        "last_updated_at"
    )

    lignes = [
        "DONNÃ‰E DE MARCHÃ‰ RÃ‰ELLE â€” BITCOIN",
        f"Source : {provider}",
        f"Prix BTC en USD : {usd}",
        f"Prix BTC en EUR : {eur}",
    ]

    if updated_at:
        lignes.append(
            f"DerniÃ¨re mise Ã  jour fournie par la source : {updated_at}"
        )

    lignes.extend([
        "",
        "IMPORTANT :",
        "Ces valeurs viennent directement d'une source de donnÃ©es rÃ©elle.",
        "Ne les modifie pas et n'en invente pas d'autres.",
        "Si tu expliques ces donnÃ©es, conserve exactement les valeurs numÃ©riques fournies."
    ])

    return "\n".join(lignes)


# ============================================================
# RÃ‰PONSE BITCOIN
# ============================================================

def reponse_prix_bitcoin(
    market: Dict[str, Any]
) -> str:

    if not market.get("ok"):
        return (
            "Je n'ai pas pu obtenir le prix rÃ©el du Bitcoin "
            "auprÃ¨s de mes sources de donnÃ©es de marchÃ© Ã  cet instant. "
            "Je prÃ©fÃ¨re ne pas donner une valeur qui pourrait Ãªtre fausse."
        )

    usd = market["usd"]
    eur = market["eur"]

    provider = market.get(
        "provider",
        "source de donnÃ©es"
    )

    return (
        "Le prix actuel du Bitcoin fourni par ma source de donnÃ©es "
        "de marchÃ© est de "
        f"{usd:,.2f} USD, soit environ {eur:,.2f} EUR.\n\n"
        f"Source : {provider}.\n"
        "Le prix du Bitcoin Ã©volue en permanence."
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
# NORMALISATION DES RÃ‰SULTATS
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
            timeout=10
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
            timeout=10
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
            timeout=10
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
# WIKIMEDIA / WIKIPEDIA â€” RECHERCHE RÃ‰ELLE
# ============================================================

def rechercher_wikimedia(
    question: str,
    nombre_resultats: int = 6
):
    """
    Recherche rÃ©elle dans Wikipedia via l'API REST MediaWiki.

    Cette source ne dÃ©pend pas du HTML d'un moteur de recherche.
    Elle est particuliÃ¨rement utile pour les personnes, lieux,
    Å“uvres, Ã©vÃ©nements et autres entitÃ©s documentÃ©es.
    """

    url = "https://fr.wikipedia.org/w/rest.php/v1/search/page"

    try:
        response = requests.get(
            url,
            params={
                "q": question,
                "limit": min(max(nombre_resultats, 1), 20)
            },
            headers={
                **SEARCH_HEADERS,
                "Accept": "application/json"
            },
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        pages = data.get("pages", [])

        if not isinstance(pages, list):
            raise RuntimeError(
                "RÃ©ponse Wikimedia invalide : pages absentes."
            )

        results = []

        for page in pages:
            title = nettoyer_texte(
                page.get("title", "")
            )

            excerpt = nettoyer_texte(
                re.sub(
                    r"<[^>]+>",
                    " ",
                    page.get("excerpt", "")
                )
            )

            description = nettoyer_texte(
                page.get("description", "")
            )

            matched_title = nettoyer_texte(
                page.get("matched_title", "")
                or ""
            )

            if not title:
                continue

            page_title = title.replace(" ", "_")

            page_url = (
                "https://fr.wikipedia.org/wiki/"
                + requests.utils.quote(
                    page_title,
                    safe="/:_-()"
                )
            )

            texte_description = excerpt

            if description:
                if texte_description:
                    texte_description += " â€” "

                texte_description += description

            if matched_title and matched_title != title:
                if texte_description:
                    texte_description += " â€” "

                texte_description += (
                    f"Titre correspondant : {matched_title}"
                )

            results.append({
                "title": title,
                "url": page_url,
                "description": texte_description,
                "provider": "wikimedia"
            })

        results = normaliser_resultats(
            results,
            nombre_resultats
        )

        if results:
            print(
                "ADRYNX INTERNET: Wikimedia -> "
                f"{len(results)} rÃ©sultat(s)"
            )

        else:
            print(
                "ADRYNX INTERNET: Wikimedia -> "
                "0 rÃ©sultat"
            )

        return results

    except Exception as e:
        print(
            "WIKIMEDIA SEARCH ERROR:",
            type(e).__name__,
            str(e)
        )

        return []


# ============================================================
# WIKIMEDIA â€” RECHERCHE Ã‰LARGIE
# ============================================================

def rechercher_wikimedia_elargie(
    question: str,
    nombre_resultats: int = 6
):
    """
    Effectue une seconde tentative Wikimedia avec une requÃªte
    lÃ©gÃ¨rement simplifiÃ©e si la premiÃ¨re ne retourne rien.
    """

    results = rechercher_wikimedia(
        question,
        nombre_resultats
    )

    if results:
        return results

    # Pour une recherche d'entitÃ©, on peut retirer certains
    # signes de ponctuation sans changer le sujet.
    requete = nettoyer_texte(question)

    requete = re.sub(
        r"[?!.,;:]+",
        " ",
        requete
    )

    requete = re.sub(
        r"\s+",
        " ",
        requete
    ).strip()

    if requete and requete.lower() != question.lower():
        return rechercher_wikimedia(
            requete,
            nombre_resultats
        )

    return []


# ============================================================
# RECHERCHE INTERNET PRINCIPALE â€” MULTI-SOURCE
# ============================================================

def rechercher_internet(
    question: str,
    nombre_resultats: int = 6,
    recherche_entite: bool = False
) -> Dict[str, Any]:

    question = (question or "").strip()

    if not question:
        return {
            "ok": False,
            "error": "Recherche vide.",
            "results": []
        }

    toutes_les_sources = []
    fournisseurs = []

    # --------------------------------------------------------
    # SOURCE PRIORITAIRE POUR LES ENTITÃ‰S :
    # WIKIMEDIA
    # --------------------------------------------------------

    if recherche_entite:
        results = rechercher_wikimedia_elargie(
            question,
            nombre_resultats
        )

        if results:
            toutes_les_sources.extend(results)
            fournisseurs.append("wikimedia")

    # --------------------------------------------------------
    # DUCKDUCKGO HTML
    # --------------------------------------------------------

    results = rechercher_duckduckgo(
        question,
        nombre_resultats
    )

    if results:
        toutes_les_sources.extend(results)
        fournisseurs.append("duckduckgo-html")

        print(
            f"ADRYNX INTERNET: DuckDuckGo HTML -> "
            f"{len(results)} rÃ©sultat(s)"
        )

    # --------------------------------------------------------
    # DUCKDUCKGO LITE
    # --------------------------------------------------------

    results = rechercher_duckduckgo_lite(
        question,
        nombre_resultats
    )

    if results:
        toutes_les_sources.extend(results)
        fournisseurs.append("duckduckgo-lite")

        print(
            f"ADRYNX INTERNET: DuckDuckGo Lite -> "
            f"{len(results)} rÃ©sultat(s)"
        )

    # --------------------------------------------------------
    # BING
    # --------------------------------------------------------

    results = rechercher_bing(
        question,
        nombre_resultats
    )

    if results:
        toutes_les_sources.extend(results)
        fournisseurs.append("bing")

        print(
            f"ADRYNX INTERNET: Bing -> "
            f"{len(results)} rÃ©sultat(s)"
        )

    # --------------------------------------------------------
    # FUSION
    # --------------------------------------------------------

    results_final = normaliser_resultats(
        toutes_les_sources,
        nombre_resultats
    )

    if results_final:
        provider = "+".join(
            dict.fromkeys(fournisseurs)
        )

        print(
            "ADRYNX INTERNET: "
            f"{len(results_final)} rÃ©sultat(s) fusionnÃ©(s)"
        )

        return {
            "ok": True,
            "provider": provider,
            "query": question,
            "results": results_final
        }

    print(
        "========== ADRYNX INTERNET ERROR =========="
    )

    print(
        "Aucun moteur n'a retournÃ© de rÃ©sultat exploitable."
    )

    print(
        "============================================"
    )

    return {
        "ok": False,
        "error": (
            "ADRYNX a essayÃ© plusieurs mÃ©thodes de recherche "
            "Internet, mais aucun rÃ©sultat exploitable n'a Ã©tÃ© "
            "retournÃ©."
        ),
        "results": []
    }


# ============================================================
# NORMALISATION POUR LE PARENT
# ============================================================

def normaliser_question(question: str) -> str:
    question = (question or "").lower().strip()

    question = (
        question
        .replace("â€™", "'")
        .replace("`", "'")
    )

    question = re.sub(
        r"\s+",
        " ",
        question
    )

    return question


# ============================================================
# EXTRACTION DU SUJET D'UNE DEMANDE D'ENTITÃ‰
# ============================================================

def extraire_sujet_entite(question: str) -> str:
    original = (question or "").strip()

    if not original:
        return ""

    low = normaliser_question(original)

    prefixes = [
        "parle moi de ",
        "parle-moi de ",
        "parle moi sur ",
        "parle-moi sur ",

        "qui est ",
        "qui Ã©tait ",
        "qui etait ",

        "biographie de ",
        "la biographie de ",

        "histoire de ",
        "l'histoire de ",

        "prÃ©sente moi ",
        "presente moi ",
        "prÃ©sente-moi ",
        "presente-moi ",

        "informations sur ",
        "information sur ",
        "informations concernant ",
        "information concernant ",

        "Ã  propos de ",
        "a propos de ",

        "que sais tu de ",
        "que sais-tu de ",

        "donne moi des informations sur ",
        "donne-moi des informations sur ",

        "dis moi qui est ",
        "dis-moi qui est ",

        "j'aimerais connaÃ®tre qui est ",
        "j'aimerais connaitre qui est ",
        "j aimerais connaÃ®tre qui est ",
        "j aimerais connaitre qui est ",
        "j'aimerais savoir qui est ",
        "j'aimerais savoir qui Ã©tait ",
        "j aimerais savoir qui est ",
        "j aimerais savoir qui Ã©tait ",
        "je voudrais connaÃ®tre qui est ",
        "je voudrais connaitre qui est ",
        "je voudrais savoir qui est ",
        "je voudrais savoir qui Ã©tait ",
        "je veux savoir qui est ",
        "je veux savoir qui Ã©tait ",
        "peux tu me dire qui est ",
        "peux-tu me dire qui est ",
        "peux tu me dire qui Ã©tait ",
        "peux-tu me dire qui Ã©tait "
    ]

    for prefix in prefixes:
        if low.startswith(prefix):
            sujet = original[len(prefix):].strip(
                " ?!.,;:"
            )

            if sujet:
                return sujet

    return ""


# ============================================================
# DÃ‰TECTION D'UNE DEMANDE D'INFORMATION SUR UNE ENTITÃ‰
# ============================================================

def demande_information_entite(question: str) -> bool:
    low = normaliser_question(question)

    if not low:
        return False

    if demande_prix_bitcoin(question):
        return False

    expressions = [
        "parle moi de ",
        "parle-moi de ",
        "parle moi sur ",
        "parle-moi sur ",

        "qui est ",
        "qui Ã©tait ",
        "qui etait ",

        "biographie de ",
        "la biographie de ",

        "histoire de ",
        "l'histoire de ",

        "prÃ©sente moi ",
        "presente moi ",
        "prÃ©sente-moi ",
        "presente-moi ",

        "informations sur ",
        "information sur ",
        "informations concernant ",
        "information concernant ",

        "Ã  propos de ",
        "a propos de ",

        "que sais tu de ",
        "que sais-tu de ",

        "donne moi des informations sur ",
        "donne-moi des informations sur ",

        "dis moi qui est ",
        "dis-moi qui est ",

        "j'aimerais connaÃ®tre qui est ",
        "j'aimerais connaitre qui est ",
        "j aimerais connaÃ®tre qui est ",
        "j aimerais connaitre qui est ",
        "j'aimerais savoir qui est ",
        "j'aimerais savoir qui Ã©tait ",
        "j aimerais savoir qui est ",
        "j aimerais savoir qui Ã©tait ",
        "je voudrais connaÃ®tre qui est ",
        "je voudrais connaitre qui est ",
        "je voudrais savoir qui est ",
        "je voudrais savoir qui Ã©tait ",
        "je veux savoir qui est ",
        "je veux savoir qui Ã©tait ",
        "peux tu me dire qui est ",
        "peux-tu me dire qui est ",
        "peux tu me dire qui Ã©tait ",
        "peux-tu me dire qui Ã©tait "
    ]

    if not any(
        expression in low
        for expression in expressions
    ):
        return False

    sujet = extraire_sujet_entite(question)

    return len(sujet.strip()) >= 2


# ============================================================
# DÃ‰TECTION D'UNE DEMANDE INTERNET
# ============================================================

def demande_recherche_internet(question: str) -> bool:
    low = normaliser_question(question)

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

        "actualitÃ©s",
        "actualitÃ©",
        "actualite",

        "prix actuel",
        "prix actuelle",
        "prix actuel maintenant",

        "maintenant",
        "aujourd'hui",
        "aujourdâ€™hui",
        "actuellement",

        "cours actuel",
        "cours actuel de",
        "valeur actuelle",

        "derniÃ¨res nouvelles",
        "derniere nouvelle",
        "derniÃ¨re nouvelle",
        "derniÃ¨res infos",
        "derniere info",

        "news",
        "latest",

        "rÃ©cent",
        "rÃ©cente",
        "rÃ©cents",
        "rÃ©centes",

        "recent",
        "recente",
        "recents",
        "recentes"
    ]

    for expression in expressions:
        if expression in low:
            return True

    if demande_information_entite(question):
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
# SUIVI CONVERSATIONNEL â€” DÃ‰TECTION DE RÃ‰SUMÃ‰
# ============================================================

def demande_resume_contexte(question: str) -> bool:
    low = normaliser_question(question)

    if not low:
        return False

    commandes_exactes = {
        "resume",
        "rÃ©sume",
        "rÃ©sumÃ©",
        "resumer",
        "rÃ©sumer",
        "fais un rÃ©sumÃ©",
        "fais moi un rÃ©sumÃ©",
        "fais-moi un rÃ©sumÃ©",
        "fais un resume",
        "fais moi un resume",
        "fais-moi un resume",
        "rÃ©sume Ã§a",
        "resume ca",
        "rÃ©sume ceci",
        "resume ceci",
        "rÃ©sume cela",
        "resume cela",
        "rÃ©sume la rÃ©ponse",
        "resume la reponse",
        "rÃ©sume ce texte",
        "resume ce texte",
        "rÃ©sume ce que tu viens de dire",
        "resume ce que tu viens de dire",
        "peux tu rÃ©sumer",
        "peux-tu rÃ©sumer",
        "peux tu faire un rÃ©sumÃ©",
        "peux-tu faire un rÃ©sumÃ©",
        "tu peux rÃ©sumer",
        "tu peux faire un rÃ©sumÃ©"
    }

    if low in commandes_exactes:
        return True

    # Commandes courtes de transformation du contexte.
    motifs = [
        r"^rÃ©sume(?:-moi)?(?:\s+Ã§a|\s+ceci|\s+cela)?$",
        r"^resume(?:-moi)?(?:\s+ca|\s+ceci|\s+cela)?$",
        r"^fais(?:-moi)?\s+un\s+rÃ©sumÃ©(?:\s+de\s+(?:Ã§a|ceci|cela))?$",
        r"^fais(?:-moi)?\s+un\s+resume(?:\s+de\s+(?:ca|ceci|cela))?$",
    ]

    return any(
        re.fullmatch(motif, low)
        for motif in motifs
    )


def dernier_message_assistant(
    history: list
) -> Optional[str]:
    for item in reversed(history or []):
        if item.get("role") == "assistant":
            content = (item.get("content") or "").strip()

            if content:
                return content

    return None


def controler_resume(
    source_text: str,
    summary: str
) -> Dict[str, Any]:
    source_text = (source_text or "").strip()
    summary = (summary or "").strip()

    if not source_text or not summary:
        return {
            "ok": False,
            "score": 0.0,
            "reason": "Source ou rÃ©sumÃ© vide."
        }

    source_words = set(
        extraire_mots_importants(source_text)
    )

    summary_words = set(
        extraire_mots_importants(summary)
    )

    if not source_words:
        return {
            "ok": bool(summary),
            "score": 1.0 if summary else 0.0,
            "reason": "Source sans termes contrÃ´lables."
        }

    correspondances = (
        source_words
        & summary_words
    )

    score = (
        len(correspondances)
        / len(source_words)
    )

    # Un rÃ©sumÃ© n'a pas besoin de reprendre tous les mots
    # de la rÃ©ponse originale. On vÃ©rifie simplement qu'il
    # conserve une partie substantielle du sujet et du contenu.
    pertinent = (
        len(summary_words) >= 3
        and (
            score >= 0.08
            or len(correspondances) >= 4
        )
    )

    return {
        "ok": pertinent,
        "score": round(score, 3),
        "matched_words": sorted(correspondances),
        "reason": (
            "Le rÃ©sumÃ© conserve suffisamment d'Ã©lÃ©ments "
            "du contenu prÃ©cÃ©dent."
            if pertinent
            else
            "Le rÃ©sumÃ© ne reprend pas suffisamment "
            "d'Ã©lÃ©ments du contenu prÃ©cÃ©dent."
        )
    }


def resumer_contexte(
    question: str,
    source_text: str,
    history: list
) -> str:
    summary_system = """
Tu es le module de rÃ©sumÃ© conversationnel d'ADRYNX.

L'utilisateur demande de rÃ©sumer le contenu prÃ©cÃ©dent de la
conversation.

Ta tÃ¢che est uniquement de rÃ©sumer le dernier message d'ADRYNX
fourni comme source.

RÃˆGLES :
1. RÃ©sume uniquement le contenu source fourni.
2. Conserve les informations importantes, noms, dates et faits
   prÃ©sents dans la source.
3. N'ajoute aucun fait extÃ©rieur.
4. Ne prÃ©tends pas effectuer une nouvelle recherche Internet.
5. Ne change pas de sujet.
6. RÃ©ponds directement avec le rÃ©sumÃ©.
7. RÃ©ponds en franÃ§ais lorsque la demande est en franÃ§ais.
8. N'appelle aucun outil et ne demande aucun outil.
"""

    messages = [
        {
            "role": "user",
            "content": (
                "DEMANDE DE L'UTILISATEUR :\n"
                f"{question}\n\n"
                "CONTENU Ã€ RÃ‰SUMER :\n"
                f"{source_text}\n\n"
                "Produis maintenant un rÃ©sumÃ© fidÃ¨le et concis."
            )
        }
    ]

    return groq_chat(
        summary_system,
        messages,
        temperature=0.2,
        max_tokens=450
    )


# ============================================================
# COMPRÃ‰HENSION DE BASE
# ============================================================

def detecter_intent(question: str) -> str:
    low = normaliser_question(question)

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
    # Ã‰TAT
    # --------------------------------------------------------

    expressions_etat = [
        "comment vas tu",
        "comment vas-tu",
        "comment tu vas",
        "Ã§a va",
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
    # IDENTITÃ‰
    # --------------------------------------------------------

    expressions_identite = [
        "qui es tu",
        "qui es-tu",
        "tu es qui",

        "qui t'a crÃ©Ã©",
        "qui t'as crÃ©Ã©",
        "qui ta crÃ©Ã©",

        "qui est ton crÃ©ateur",
        "qui est ton createur",

        "qui t'a dÃ©veloppÃ©",
        "qui t'as dÃ©veloppÃ©",
        "qui ta dÃ©veloppÃ©",

        "qui t'a developpÃ©",
        "qui t'as developpÃ©",
        "qui ta developpe",

        "qui est ton dÃ©veloppeur",
        "qui est ton developpeur",

        "qui a crÃ©Ã© adrynx",
        "qui a cree adrynx",

        "qui a dÃ©veloppÃ© adrynx",
        "qui a developpe adrynx",

        "qui a conÃ§u adrynx",
        "qui a concu adrynx",

        "qui est derriÃ¨re adrynx",
        "qui est derriere adrynx",

        "qui a fait adrynx",
        "qui a fabriquÃ© adrynx",
        "qui a fabrique adrynx",

        "qui a conÃ§u ton systÃ¨me",
        "qui a concu ton systeme",

        "qui t'a conÃ§u",
        "qui t'as conÃ§u",
        "qui t'a concu",
        "qui t'as concu"
    ]

    if any(
        expression in low
        for expression in expressions_identite
    ):
        return "identite"

    # --------------------------------------------------------
    # SUIVI CONVERSATIONNEL â€” RÃ‰SUMÃ‰
    # --------------------------------------------------------

    if demande_resume_contexte(question):
        return "resume_contexte"

    # --------------------------------------------------------
    # ENTITÃ‰
    # --------------------------------------------------------

    if demande_information_entite(question):
        return "information_entite"

    # --------------------------------------------------------
    # BITCOIN
    # --------------------------------------------------------

    if demande_prix_bitcoin(question):
        return "marche_bitcoin"

    return "conversation"


# ============================================================
# IDENTITÃ‰
# ============================================================

def reponse_identite():
    return (
        "Je suis ADRYNX, l'assistant dÃ©veloppÃ© par "
        "Jonathan Dejah OBENDA. "
        "Je suis conÃ§u pour comprendre les conversations, "
        "utiliser leur contexte et Ã©voluer avec les fonctions "
        "rÃ©ellement ajoutÃ©es Ã  mon systÃ¨me."
    )


# ============================================================
# RÃ‰PONSE Ã‰TAT
# ============================================================

def reponse_etat():
    return (
        "Je vais bien. Je suis actuellement opÃ©rationnel "
        "et prÃªt Ã  poursuivre notre conversation."
    )


# ============================================================
# CAPACITÃ‰S RÃ‰ELLES â€” PARENT ADRYNX
# ============================================================

def system_prompt():
    return """
Tu es ADRYNX.

Tu es un assistant conversationnel rÃ©el intÃ©grÃ© dans une
application appelÃ©e ADRYNX.

Le backend possÃ¨de une couche de contrÃ´le appelÃ©e PARENT.

Le PARENT contrÃ´le les fonctions rÃ©elles et fournit le contexte
nÃ©cessaire Ã  ta rÃ©ponse.

IDENTITÃ‰ :

L'identitÃ© fondamentale d'ADRYNX est dÃ©terminÃ©e par le noyau
backend.

Si une question concerne le crÃ©ateur, le dÃ©veloppeur ou
l'identitÃ© fondamentale d'ADRYNX, utilise uniquement les
informations explicitement fournies par le backend.

Ne remplace jamais cette identitÃ© par une description gÃ©nÃ©rique.

RECHERCHE INTERNET :

Lorsque le backend fournit des rÃ©sultats Internet, ils
correspondent Ã  une recherche rÃ©ellement effectuÃ©e par ADRYNX.

Ces rÃ©sultats peuvent Ãªtre incomplets.

Tu dois analyser uniquement les informations rÃ©ellement fournies.

L'absence de rÃ©sultat Internet ne signifie PAS qu'une personne,
un lieu, une Å“uvre, une organisation ou un Ã©vÃ©nement n'existe pas.

Ne transforme jamais un Ã©chec de recherche en preuve de
non-existence.

Si les rÃ©sultats sont insuffisants, indique clairement que les
sources disponibles ne permettent pas de confirmer suffisamment
l'information.

CAPACITÃ‰S ACTUELLEMENT RÃ‰ELLES :

* conversation via Groq ;
* historique de conversation fourni par le backend ;
* sauvegarde SQLite des messages ;
* recherche Internet rÃ©elle ;
* recherche d'entitÃ©s via des sources externes rÃ©elles ;
* analyse et rÃ©sumÃ© de rÃ©sultats Internet ;
* rÃ©cupÃ©ration de donnÃ©es structurÃ©es externes ;
* rÃ©ponse en franÃ§ais.

NE PRÃ‰SENTE PAS COMME ACTIVES des fonctions qui ne sont pas
fournies par le backend.

RÃˆGLES :

1. Reste sur le sujet de l'utilisateur.
2. Utilise le contexte disponible.
3. RÃ©ponds directement Ã  la question.
4. Ne fabrique aucun fait.
5. Ne fabrique aucune source.
6. Ne prÃ©tends jamais avoir utilisÃ© Internet si aucun rÃ©sultat
   Internet ne t'a Ã©tÃ© fourni.
7. Si des rÃ©sultats Internet sont fournis, utilise-les.
8. Si les rÃ©sultats sont insuffisants, indique-le.
9. Ne transforme jamais une absence de rÃ©sultat en preuve
   d'inexistence.
10. RÃ©ponds en franÃ§ais lorsque l'utilisateur Ã©crit en franÃ§ais.
11. Pour une information actuelle, privilÃ©gie les donnÃ©es
    externes rÃ©ellement fournies.
12. Pour une entitÃ© nommÃ©e, rÃ©ponds Ã  propos de cette entitÃ©
    uniquement avec les informations disponibles.
13. Ne parle pas de l'architecture interne sauf si l'utilisateur
    le demande.
14. Ne prÃ©tends pas avoir une mÃ©moire permanente si elle n'est
    pas rÃ©ellement activÃ©e.
15. Ne prÃ©tends jamais avoir exÃ©cutÃ© une action non exÃ©cutÃ©e.
"""


# ============================================================
# CONTEXTE INTERNET
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
        "RÃ‰SULTATS D'UNE RECHERCHE INTERNET RÃ‰ELLE"
    )

    lignes.append(
        f"Moteur/mÃ©thode utilisÃ©e : {provider}"
    )

    lignes.append(
        f"Question recherchÃ©e : {question}"
    )

    lignes.append("")

    lignes.append(
        "ATTENTION : les Ã©lÃ©ments ci-dessous sont des rÃ©sultats "
        "ou extraits rÃ©ellement rÃ©cupÃ©rÃ©s. Ils peuvent Ãªtre "
        "incomplets et ne constituent pas automatiquement une "
        "preuve absolue de chaque affirmation."
    )

    lignes.append("")

    for index, result in enumerate(
        recherche.get("results", []),
        start=1
    ):
        lignes.append(
            f"RÃ©sultat {index} :"
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
# RESPONSE CONTROLLER â€” NORMALISATION
# ============================================================

def normaliser_pour_controle(texte: str) -> str:
    texte = (texte or "").lower()

    texte = (
        texte
        .replace("â€™", "'")
        .replace("Ã ", "a")
        .replace("Ã¢", "a")
        .replace("Ã¤", "a")
        .replace("Ã©", "e")
        .replace("Ã¨", "e")
        .replace("Ãª", "e")
        .replace("Ã«", "e")
        .replace("Ã®", "i")
        .replace("Ã¯", "i")
        .replace("Ã´", "o")
        .replace("Ã¶", "o")
        .replace("Ã¹", "u")
        .replace("Ã»", "u")
        .replace("Ã¼", "u")
        .replace("Ã§", "c")
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
# MOTS IMPORTANTS
# ============================================================

MOTS_VIDES_CONTROLE = {
    "le", "la", "les",
    "un", "une", "des",
    "du", "de", "d",
    "au", "aux",
    "et", "ou", "mais",
    "donc", "or", "ni", "car",
    "a", "as", "ai", "ont",
    "est", "sont", "etre",
    "es", "tu", "te", "toi",
    "je", "me", "moi",
    "il", "elle", "ils", "elles",
    "nous", "vous",
    "ce", "cet", "cette", "ces",
    "qui", "que", "quoi",
    "quel", "quelle", "quels", "quelles",
    "comment", "pourquoi", "quand",
    "ou", "dans", "sur", "avec",
    "pour", "par", "sans", "sous",
    "entre",
    "mon", "ton", "son",
    "ma", "ta", "sa",
    "mes", "tes", "ses",
    "notre", "votre", "leur",
    "nos", "vos", "leurs",
    "est-ce", "ceci", "cela",
    "ca", "ne", "pas",
    "plus", "moins",
    "trÃ¨s", "tres",
    "bien"
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
# PERTINENCE
# ============================================================

def analyser_pertinence(
    question: str,
    response: str
) -> Dict[str, Any]:

    question = (question or "").strip()
    response = (response or "").strip()

    if not question or not response:
        return {
            "ok": False,
            "score": 0.0,
            "raison": "Question ou rÃ©ponse vide."
        }

    question_words = extraire_mots_importants(question)

    response_words = set(
        extraire_mots_importants(response)
    )

    if not question_words:
        return {
            "ok": True,
            "score": 1.0,
            "raison": "Question trop courte."
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
                 "apparaissent dans la rÃ©ponse."
        )
    }


# ============================================================
# FRAÃŽCHEUR
# ============================================================

def question_exigeant_actualite(question: str) -> bool:
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
                "La question demande une information "
                "nÃ©cessitant une source externe, mais aucune "
                "donnÃ©e Internet rÃ©elle n'est disponible."
            )
        }

    return {
        "ok": True,
        "reason": (
            "Les donnÃ©es externes fournies sont compatibles "
            "avec le contrÃ´le demandÃ©."
        )
    }


# ============================================================
# CONTRÃ”LE GLOBAL
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
# CORRECTION GROQ
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
            "\n\nDONNÃ‰ES INTERNET DISPONIBLES :\n"
            + web_context
        )

    correction_system = """
Tu es le module de correction de rÃ©ponse d'ADRYNX.

Une rÃ©ponse doit Ãªtre reformulÃ©e car le contrÃ´leur ADRYNX
l'a jugÃ©e insuffisamment pertinente.

Ta tÃ¢che est uniquement de produire une nouvelle rÃ©ponse
directement adaptÃ©e Ã  la question.

RÃˆGLES :

1. RÃ©ponds directement Ã  la question.
2. Ne change pas de sujet.
3. N'invente aucun fait.
4. N'invente aucune source.
5. Utilise les donnÃ©es Internet fournies lorsqu'elles existent.
6. Si elles sont insuffisantes, dis-le clairement.
7. Ne transforme jamais un Ã©chec de recherche en preuve
   de non-existence.
8. Ne dis pas que tu as Ã©tÃ© corrigÃ©.
9. Ne parle pas du processus interne.
10. RÃ©ponds dans la langue de l'utilisateur.
11. N'appelle aucun outil.
12. Ne produis aucune demande d'utilisation d'outil.
"""

    messages = [
        {
            "role": "user",
            "content": (
                "QUESTION DE L'UTILISATEUR :\n"
                f"{question}\n\n"
                "PREMIÃˆRE RÃ‰PONSE :\n"
                f"{response}"
                f"{contexte_web}"
            )
        }
    ]

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
# CONTROLLER â€” PIPELINE
# ============================================================

def executer_response_controller(
    question: str,
    response: str,
    source: str,
    history: list,
    web_results=None,
    web_context: Optional[str] = None,
    autoriser_correction: bool = True
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
        "rÃ©ponse nÃ©cessitant une correction."
    )

    # --------------------------------------------------------
    # NOUVEAU GARDE-FOU
    #
    # Si la recherche d'une entitÃ© a Ã©chouÃ©, on ne demande pas
    # au modÃ¨le de correction de rÃ©soudre lui-mÃªme le problÃ¨me.
    #
    # Cela Ã©vite exactement :
    # "Tool choice is none, but model called a tool"
    # --------------------------------------------------------

    if not autoriser_correction:
        print(
            "ADRYNX CONTROLLER: correction Groq dÃ©sactivÃ©e "
            "pour ce cas."
        )

        return {
            "ok": False,
            "error": (
                "Les sources externes nÃ©cessaires n'ont pas "
                "fourni suffisamment de donnÃ©es pour valider "
                "la rÃ©ponse."
            ),
            "controller": controle,
            "corrected": False
        }

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

        return {
            "ok": False,
            "error": (
                "ADRYNX n'a pas pu produire une rÃ©ponse "
                "suffisamment vÃ©rifiable et pertinente."
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
                "ADRYNX a dÃ©tectÃ© un problÃ¨me de pertinence "
                "et la correction automatique a Ã©chouÃ©."
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
    # IDENTITÃ‰
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
    # Ã‰TAT
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
    # RÃ‰SUMÃ‰ DU CONTEXTE PRÃ‰CÃ‰DENT
    # --------------------------------------------------------

    if intent == "resume_contexte":
        # On enregistre d'abord la demande afin de conserver
        # l'Ã©change complet dans la conversation.
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

        source_text = dernier_message_assistant(
            history[:-1]
            if history and history[-1].get("role") == "user"
            else history
        )

        if not source_text:
            return {
                "ok": False,
                "error": (
                    "Je n'ai pas de rÃ©ponse prÃ©cÃ©dente Ã  rÃ©sumer "
                    "dans cette conversation."
                ),
                "intent": intent,
                "conversation_id": conversation_id,
                "source": "context-summary-error",
                "video_core": PHOENIX_VIDEO
            }

        try:
            response = resumer_contexte(
                question,
                source_text,
                history
            )
        except Exception as e:
            print(
                "ADRYNX SUMMARY ERROR:",
                type(e).__name__,
                str(e)
            )

            return {
                "ok": False,
                "error": (
                    "ADRYNX n'a pas pu produire le rÃ©sumÃ© "
                    "demandÃ©."
                ),
                "intent": intent,
                "conversation_id": conversation_id,
                "source": "context-summary-error",
                "video_core": PHOENIX_VIDEO
            }

        resume_control = controler_resume(
            source_text,
            response
        )

        print(
            "ADRYNX CONTEXT SUMMARY CONTROLLER:",
            {
                "ok": resume_control["ok"],
                "pertinence": resume_control["score"]
            }
        )

        if not resume_control["ok"]:
            return {
                "ok": False,
                "error": (
                    "ADRYNX n'a pas pu produire un rÃ©sumÃ© "
                    "suffisamment fidÃ¨le au contenu prÃ©cÃ©dent."
                ),
                "intent": intent,
                "conversation_id": conversation_id,
                "source": "context-summary-controller-error",
                "controller": resume_control,
                "video_core": PHOENIX_VIDEO
            }

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
            "source": "groq-context-summary",
            "conversation_id": conversation_id,
            "video_core": PHOENIX_VIDEO,
            "controller": {
                "ok": True,
                "type": "context-summary",
                "pertinence": resume_control["score"]
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
    # BITCOIN
    # --------------------------------------------------------

    if demande_prix_bitcoin(question):
        market = obtenir_prix_bitcoin()

        if not market.get("ok"):
            return {
                "ok": False,
                "error": market.get(
                    "error",
                    "Impossible d'obtenir le prix rÃ©el du Bitcoin."
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
    # RECHERCHE INTERNET RÃ‰ELLE
    # --------------------------------------------------------

    web_results = []
    web_context = None

    if demande_recherche_internet(question):

        sujet_entite = extraire_sujet_entite(
            question
        )

        recherche_entite = bool(
            intent == "information_entite"
            and sujet_entite
        )

        if sujet_entite:
            requete_recherche = sujet_entite

            print(
                "ADRYNX PARENT: "
                f"entitÃ© dÃ©tectÃ©e -> {sujet_entite}"
            )

        else:
            requete_recherche = question

        recherche = rechercher_internet(
            requete_recherche,
            nombre_resultats=8,
            recherche_entite=recherche_entite
        )

        # ----------------------------------------------------
        # Ã‰CHEC DE RECHERCHE
        # ----------------------------------------------------

        if not recherche.get("ok"):

            if recherche_entite:

                print(
                    "ADRYNX PARENT: "
                    "recherche d'entitÃ© Ã©chouÃ©e."
                )

                # ------------------------------------------------
                # IMPORTANT :
                #
                # On ne passe plus ce cas dans le contrÃ´leur Groq.
                #
                # Cela empÃªche le modÃ¨le gpt-oss de tenter :
                # internet.run
                # browser.search
                #
                # alors qu'aucun tool n'est dÃ©clarÃ©.
                # ------------------------------------------------

                fallback_system = system_prompt() + """

MODE DE REPLI :

La recherche Internet rÃ©elle pour l'entitÃ© demandÃ©e a Ã©chouÃ©.

Tu n'as reÃ§u aucune source Internet exploitable.

Tu peux rÃ©pondre Ã  partir de tes connaissances gÃ©nÃ©rales
UNIQUEMENT si tu connais rÃ©ellement l'entitÃ© et peux rÃ©pondre
avec prudence.

RÃˆGLES SUPPLÃ‰MENTAIRES :

- Ne prÃ©tends pas avoir vÃ©rifiÃ© l'information sur Internet.
- Ne fabrique aucune source.
- Ne dis jamais que l'entitÃ© n'existe pas simplement parce
  que la recherche a Ã©chouÃ©.
- Si tes connaissances sont insuffisantes, dis clairement que
  tu ne peux pas confirmer suffisamment l'information.
- Ne tente d'utiliser aucun outil.
"""

                try:
                    # On fournit explicitement le sujet dans le
                    # message utilisateur pour Ã©viter que le modÃ¨le
                    # se perde dans l'historique.
                    fallback_messages = list(history)

                    fallback_messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Question actuelle : {question}\n\n"
                                f"EntitÃ© demandÃ©e : {sujet_entite}\n\n"
                                "RÃ©ponds directement Ã  cette question."
                            )
                        }
                    )

                    response = groq_chat(
                        fallback_system,
                        fallback_messages,
                        temperature=0.2,
                        max_tokens=700
                    )

                except Exception as e:
                    print(
                        "ADRYNX ENTITY FALLBACK ERROR:",
                        type(e).__name__,
                        str(e)
                    )

                    return {
                        "ok": False,
                        "error": (
                            "La recherche Internet rÃ©elle a Ã©chouÃ© "
                            "et ADRYNX ne peut pas vÃ©rifier "
                            "suffisamment cette entitÃ©."
                        ),
                        "intent": intent,
                        "conversation_id": conversation_id,
                        "source": "internet-error",
                        "web_search": {
                            "attempted": True,
                            "success": False
                        },
                        "video_core": PHOENIX_VIDEO
                    }

                # ------------------------------------------------
                # Si le fallback donne une rÃ©ponse, on ne demande
                # PAS au contrÃ´leur de lancer une seconde recherche.
                # ------------------------------------------------

                controller = executer_response_controller(
                    question,
                    response,
                    "groq-sans-web",
                    history,
                    [],
                    None,
                    autoriser_correction=False
                )

                if controller.get("ok"):

                    response = controller["response"]

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
                        "source": "groq-sans-web",
                        "conversation_id": conversation_id,
                        "video_core": PHOENIX_VIDEO,
                        "controller": {
                            "ok": True,
                            "corrected": False,
                            "web_search": {
                                "attempted": True,
                                "success": False
                            }
                        }
                    }

                # ------------------------------------------------
                # Si le contrÃ´leur refuse la rÃ©ponse, on renvoie
                # une erreur honnÃªte plutÃ´t que de demander Ã  Groq
                # d'effectuer une recherche non dÃ©clarÃ©e.
                # ------------------------------------------------

                return {
                    "ok": False,
                    "error": (
                        "ADRYNX n'a pas pu vÃ©rifier suffisamment "
                        "l'information demandÃ©e."
                    ),
                    "intent": intent,
                    "conversation_id": conversation_id,
                    "source": "response-controller-error",
                    "controller": controller.get(
                        "controller",
                        {}
                    ),
                    "web_search": {
                        "attempted": True,
                        "success": False
                    },
                    "video_core": PHOENIX_VIDEO
                }

            return {
                "ok": False,
                "error": recherche.get(
                    "error",
                    "La recherche Internet a Ã©chouÃ©."
                ),
                "intent": intent,
                "conversation_id": conversation_id,
                "source": "internet-error",
                "video_core": PHOENIX_VIDEO
            }

        # ----------------------------------------------------
        # RECHERCHE RÃ‰USSIE
        # ----------------------------------------------------

        web_results = recherche.get(
            "results",
            []
        )

        web_context = construire_contexte_web(
            requete_recherche,
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
    # CONTRÃ”LE
    # --------------------------------------------------------

    controller = executer_response_controller(
        question,
        response,
        source,
        history,
        web_results,
        web_context,
        autoriser_correction=True
    )

    if not controller.get("ok"):
        return {
            "ok": False,
            "error": controller.get(
                "error",
                "ADRYNX n'a pas validÃ© la rÃ©ponse gÃ©nÃ©rÃ©e."
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
        "response_controller": True,
        "parent_controller": True,
        "entity_search": True,
        "multi_source_search": True,
        "wikimedia_search": True,
        "context_summary": True
    }


# ============================================================
# FONCTIONS FUTURES â€” PAS SIMULÃ‰ES
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
            "Le systÃ¨me d'apprentissage par feedback "
            "n'est pas encore activÃ©."
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
