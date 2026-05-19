import streamlit as st
import chromadb
import os
from agent import ask
from news_scraper import run_scraper

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

st.set_page_config(
    page_title="Hungarian Promise Tracker",
    page_icon="🇭🇺",
    layout="wide"
)

# Sidebar
with st.sidebar:
    st.title("🇭🇺 Promise Tracker")
    st.caption("Tracking the new Hungarian government's promises")
    
    st.divider()
    
    # Stats
    try:
        db = chromadb.PersistentClient(path=os.path.join(BASE_DIR, "data/chroma"))
        promises = db.get_or_create_collection("promises")
        news = db.get_or_create_collection("news")
        
        col1, col2 = st.columns(2)
        col1.metric("Promises", promises.count())
        col2.metric("News Articles", news.count())
        
        st.divider()
        
        # Category breakdown
        st.subheader("Promises by category")
        data = promises.get()
        categories = {}
        for meta in data["metadatas"]:
            cat = meta.get("category_ai", "Unknown")
            categories[cat] = categories.get(cat, 0) + 1
        
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            st.text(f"{cat}: {count}")
    except Exception as e:
        st.error(f"DB error: {e}")
    
    st.divider()
    
    # Scrape button
    if st.button("🔄 Scrape latest news", use_container_width=True):
        with st.spinner("Scraping Telex.hu..."):
            result = run_scraper()
        st.success(result)
        st.rerun()

# Main area
st.title("Hungarian Government Promise Tracker")
st.caption("Ask about what the new government promised, recent news, or whether they're keeping their word.")

# Example questions
st.subheader("Try asking:")
examples = [
    "What did they promise about healthcare?",
    "Any news about the railway system?",
    "Is the government keeping its word on education?",
    "What are the anti-corruption promises?",
]

cols = st.columns(2)
for i, example in enumerate(examples):
    if cols[i % 2].button(example, use_container_width=True):
        st.session_state["query"] = example

# Query input
query = st.text_input(
    "Your question:",
    value=st.session_state.get("query", ""),
    placeholder="What did the government promise about housing?"
)

if query:
    with st.spinner("Thinking..."):
        answer = ask(query)
    
    st.divider()
    st.markdown(answer)
    
    # Clear the session state query
    if "query" in st.session_state:
        del st.session_state["query"]