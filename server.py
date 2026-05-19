import os
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

mcp = FastMCP("hungarian-promises")

@mcp.tool()
def ask_agent(query: str) -> str:
    """Ask anything about the new Hungarian government's promises,
    recent news, or whether they are keeping their word."""
    from agent import ask
    return ask(query)

@mcp.tool()
def scrape_news() -> str:
    """Scrape and embed the latest relevant news from Telex.hu."""
    from news_scraper import run_scraper
    return run_scraper()

@mcp.tool()
def get_stats() -> str:
    """Get statistics about the promises and news database."""
    import chromadb
    db = chromadb.PersistentClient(path=os.path.join(BASE_DIR, "data/chroma"))
    promises = db.get_or_create_collection("promises")
    news = db.get_or_create_collection("news")
    data = promises.get()
    categories = {}
    for meta in data["metadatas"]:
        cat = meta.get("category_ai", "Unknown")
        categories[cat] = categories.get(cat, 0) + 1
    cat_str = "\n".join([f"  {k}: {v}" for k, v in sorted(categories.items(), key=lambda x: -x[1])])
    return f"Promises: {promises.count()}\nNews articles: {news.count()}\n\nBy category:\n{cat_str}"

if __name__ == "__main__":
    mcp.run(transport="stdio")