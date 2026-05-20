# 🇭🇺 Hungarian Government Promise Tracker

A RAG-powered agent that tracks whether the new Hungarian government (elected April 2026, took power May 2026) keeps its promises.

## What it does

- Extracts and indexes 1151 promises from the government's official program document
- Scrapes Telex.hu for the latest relevant news using an intelligent LangGraph filtering pipeline — run manually or schedule as a daily cron job
- Answers natural language questions like "What did they promise about healthcare?" or "Is there any news about the railway promises?"
- Compares promises to news to track accountability

## Architecture

Streamlit UI → LangGraph Agent (router → search → answer) → ChromaDB (promises + news) → Gemini API (embeddings + reasoning)

Also exposes an MCP server so it can be plugged into any MCP-compatible client (Claude Desktop, Cursor, etc.)

## Tech stack

- LangGraph — agent orchestration and news ingestion pipeline
- ChromaDB — vector database for semantic search
- Gemini API — embeddings and LLM reasoning
- Streamlit — web interface
- MCP — tool server for AI client integration
- feedparser — RSS ingestion from Telex.hu
- pypdf — PDF extraction from government document

## Data sources

- A működő és emberséges Magyarország alapjai — official government program document (243 pages, 1151 promises extracted)
- Telex.hu — independent Hungarian news source

## Setup
## Setup

Clone and install dependencies:

    git clone https://github.com/kepler45-2b/hungarian-promises
    cd hungarian-promises
    pip install -r requirements.txt

Add your API key:

    echo "GEMINI_API_KEY=your_key_here" > .env

Download the government program document from https://mukodoorszagot.hu/#program-pontok
and place the PDF in the project root.

Build the database (first time only):

    python extract.py        # extract text from PDF
    python structure.py      # extract promises using Gemini
    python add_chapters.py   # add chapter categories
    python fix_categories.py # consolidate AI categories
    python embed.py          # embed promises into ChromaDB
    python news_scraper.py   # scrape latest Telex news

Run the app:

    streamlit run app.py

## Project structure

    hungarian-promises/
    ├── extract.py          # PDF to markdown
    ├── structure.py        # markdown to structured promises JSON
    ├── add_chapters.py     # rule-based chapter categorization
    ├── fix_categories.py   # AI category consolidation
    ├── embed.py            # promises to ChromaDB
    ├── agent.py            # LangGraph query agent
    ├── news_scraper.py     # LangGraph news ingestion pipeline
    ├── server.py           # MCP server
    ├── app.py              # Streamlit UI
    └── data/
        ├── promises.json
        └── chroma/

## How the news pipeline works

The scraper runs daily and uses a two-stage filter:

1. Rule-based pre-filter — drops irrelevant Telex categories (sports, culture, lifestyle)
2. LLM filter — Gemini decides if the article is relevant to government actions and assigns a promise category

Only relevant articles get translated to English and embedded, keeping the database clean and searches accurate.

## Roadmap

- Promise status tracking (fulfilled / in progress / broken)
- Daily automated scraping via scheduler
- Multi-agent orchestrator that monitors uncovered promises
- Docker deployment