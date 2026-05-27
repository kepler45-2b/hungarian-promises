import os
import json
import time
import hashlib
import urllib.parse
import feedparser
import re
import html
import chromadb
from typing import TypedDict
from langgraph.graph import StateGraph, END
from google import genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-001",
    google_api_key=os.getenv("GEMINI_API_KEY")
)

TELEX_FEED = "https://telex.hu/rss"
FEED_444 = "https://444.hu/feed"

SKIP_TELEX_SECTIONS = ["Kultúra", "Könyvespolc", "Karakter", "Sport", "After", "Tech-Tud"]
KEEP_444_SECTIONS = {"POLITIKA", "GAZDASÁG", "VÉLEMÉNY"}

PROMISE_CATEGORIES = [
    "Healthcare", "Education", "Economy", "Housing", "Transport",
    "Environment", "Justice & Rule of Law", "Foreign Policy & Defense",
    "Public Administration", "Social Policy", "Agriculture",
    "Culture & Sport", "Energy", "Democracy & Anti-Corruption", "Minority Rights"
]

def strip_utm(url):
    parsed = urllib.parse.urlparse(url)
    params = {k: v for k, v in urllib.parse.parse_qs(parsed.query, keep_blank_values=True).items()
              if not k.startswith("utm_")}
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(params, doseq=True)))

def strip_html(text):
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

def parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())

def call_gemini_with_retry(prompt, retries=3):
    for attempt in range(retries):
        try:
            response = gemini.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            return response.text
        except Exception as e:
            if attempt < retries - 1:
                print(f"  Gemini error: {e}, retrying in 30s...")
                time.sleep(30)
            else:
                raise e

def get_news_collection():
    db = chromadb.PersistentClient(path=os.path.join(BASE_DIR, "data/chroma"))
    return db.get_or_create_collection("news")

# --- State ---
class ScraperState(TypedDict):
    raw_articles: list
    prefiltered_articles: list
    relevant_articles: list
    embedded_count: int

# --- Nodes ---
def fetch_node(state: ScraperState) -> ScraperState:
    collection = get_news_collection()
    existing_ids = set(collection.get()["ids"])
    raw = []

    print("Fetching Telex RSS...")
    for entry in feedparser.parse(TELEX_FEED).entries:
        aid = hashlib.md5(entry.link.encode()).hexdigest()
        if aid in existing_ids:
            continue
        raw.append({
            "id": aid,
            "title": strip_html(entry.get("title", "")),
            "description": strip_html(entry.get("summary", "")),
            "section": entry.get("tags", [{}])[0].get("term", "") if entry.get("tags") else "",
            "link": entry.get("link", ""),
            "published": entry.get("published", ""),
            "is_english": "/english/" in entry.get("link", ""),
            "source": "telex.hu",
        })

    print("Fetching 444.hu RSS...")
    for entry in feedparser.parse(FEED_444).entries:
        canonical = strip_utm(entry.get("link", ""))
        aid = hashlib.md5(canonical.encode()).hexdigest()
        if aid in existing_ids:
            continue
        tags = [t.get("term", "") for t in entry.get("tags", [])]
        section = next((t for t in tags if t.isupper() and len(t) > 2), "")
        raw.append({
            "id": aid,
            "title": strip_html(entry.get("title", "")),
            "description": strip_html(entry.get("summary", "")),
            "section": section,
            "link": canonical,
            "published": entry.get("published", ""),
            "is_english": False,
            "source": "444.hu",
        })

    print(f"  Fetched {len(raw)} new articles total")
    return {**state, "raw_articles": raw}

def prefilter_node(state: ScraperState) -> ScraperState:
    if not state["raw_articles"]:
        return {**state, "prefiltered_articles": []}

    kept = []
    for a in state["raw_articles"]:
        section = a["section"]
        if a["source"] == "telex.hu" and any(skip in section for skip in SKIP_TELEX_SECTIONS):
            continue
        if a["source"] == "444.hu" and section and section not in KEEP_444_SECTIONS:
            continue
        kept.append(a)

    print(f"  Pre-filter: {len(state['raw_articles'])} -> {len(kept)} articles")
    return {**state, "prefiltered_articles": kept}

def filter_node(state: ScraperState) -> ScraperState:
    if not state["prefiltered_articles"]:
        return {**state, "relevant_articles": []}

    print(f"LLM filtering {len(state['prefiltered_articles'])} articles...")
    relevant = []
    batch_size = 15

    for i in range(0, len(state["prefiltered_articles"]), batch_size):
        batch = state["prefiltered_articles"][i:i+batch_size]
        texts = [f"{a['title']}. {a['description']}" for a in batch]

        try:
            response_text = call_gemini_with_retry(
                f"""You are filtering news for a Hungarian government promise tracker.
The NEW Hungarian government took power in May 2026, replacing Orbán's Fidesz.

Mark as relevant ONLY if the article is directly about:
- The NEW government's decisions, actions, or statements
- New laws or policies being implemented or announced
- Government ministers making policy announcements
- Budget or public spending decisions
- Public services being reformed (healthcare, education, transport)
- Accountability investigations into the previous Orbán government

NOT relevant:
- Operational/logistics news (airport schedules, timetables)
- Sports results or sports organization internal drama
- International news not involving Hungarian government policy
- Celebrity deaths or cultural obituaries
- Pure market/business data without government policy angle
- Entertainment, lifestyle, book reviews

Be strict. When in doubt -> not relevant.

For relevant articles assign one category from:
{json.dumps(PROMISE_CATEGORIES)}

Return ONLY a JSON array, one object per article:
{{"relevant": true/false, "category": "category or null"}}

Articles:
{json.dumps(texts)}"""
            )
            decisions = parse_json(response_text)
            for j, decision in enumerate(decisions):
                if decision.get("relevant"):
                    article = batch[j].copy()
                    article["category"] = decision.get("category", "Public Administration")
                    relevant.append(article)
        except Exception as e:
            print(f"  Filter failed: {e}")

        time.sleep(2)

    print(f"  LLM filter: {len(state['prefiltered_articles'])} -> {len(relevant)} articles")
    return {**state, "relevant_articles": relevant}

def embed_node(state: ScraperState) -> ScraperState:
    if not state["relevant_articles"]:
        print("No articles to embed.")
        return {**state, "embedded_count": 0}

    print(f"Translating and embedding {len(state['relevant_articles'])} articles...")
    collection = get_news_collection()
    articles = state["relevant_articles"]
    batch_size = 10

    for i in range(0, len(articles), batch_size):
        batch = articles[i:i+batch_size]
        texts_to_embed = [None] * len(batch)

        # English articles — no translation needed
        for j, a in enumerate(batch):
            if a["is_english"]:
                texts_to_embed[j] = f"{a['title']}. {a['description']}"

        # Translate Hungarian articles
        hu_batch = [(j, a) for j, a in enumerate(batch) if not a["is_english"]]
        if hu_batch:
            try:
                hu_texts = [f"{a['title']}. {a['description']}" for _, a in hu_batch]
                response_text = call_gemini_with_retry(
                    f"Translate to English. Return ONLY a JSON array of strings.\n{json.dumps(hu_texts)}"
                )
                translations = parse_json(response_text)
                for k, (j, _) in enumerate(hu_batch):
                    texts_to_embed[j] = translations[k]
            except Exception as e:
                print(f"  Translation failed: {e}, using Hungarian as fallback")
                for j, a in hu_batch:
                    texts_to_embed[j] = f"{a['title']}. {a['description']}"

            time.sleep(2)

        # Embed
        result = gemini.models.embed_content(
            model="gemini-embedding-001",
            contents=texts_to_embed
        )
        collection.add(
            ids=[a["id"] for a in batch],
            embeddings=[e.values for e in result.embeddings],
            documents=texts_to_embed,
            metadatas=[{
                "title_hu": a["title"],
                "description_hu": a["description"],
                "text_en": texts_to_embed[j],
                "link": a["link"],
                "published": a["published"],
                "category": a["category"],
                "section": a["section"],
                "source": a["source"],
                "is_english": str(a["is_english"])
            } for j, a in enumerate(batch)]
        )
        time.sleep(1)

    count = len(state["relevant_articles"])
    print(f"Done! Embedded {count} articles. Total in DB: {collection.count()}")
    return {**state, "embedded_count": count}

# --- Build graph ---
def build_scraper():
    graph = StateGraph(ScraperState)
    graph.add_node("fetch", fetch_node)
    graph.add_node("prefilter", prefilter_node)
    graph.add_node("filter", filter_node)
    graph.add_node("embed", embed_node)
    graph.add_edge("fetch", "prefilter")
    graph.add_edge("prefilter", "filter")
    graph.add_edge("filter", "embed")
    graph.add_edge("embed", END)
    graph.set_entry_point("fetch")
    return graph.compile()

scraper = build_scraper()

def run_scraper() -> str:
    result = scraper.invoke({
        "raw_articles": [],
        "prefiltered_articles": [],
        "relevant_articles": [],
        "embedded_count": 0
    })
    return f"Done! Embedded {result['embedded_count']} relevant articles."

if __name__ == "__main__":
    print(run_scraper())