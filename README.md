# 🇭🇺 Hungarian Government Promise Tracker

A RAG-powered agent that tracks whether the new Hungarian government (elected April 2026, took power May 2026) keeps its promises.

## What it does

- Extracts and indexes 1151 promises from the government's official program document
- Scrapes Telex.hu and 444.hu for the latest relevant news using an intelligent LangGraph filtering pipeline — runs daily via Windows Task Scheduler
- Answers natural language questions like "What did they promise about healthcare?" or "Is there any news about the railway promises?"
- Decomposes complex questions into sub-queries for more accurate retrieval
- Flags promises marked as immediate that are still pending as ⚠️ OVERDUE

## Architecture

Streamlit UI → LangGraph Agent (decompose → router → search → answer) → ChromaDB (promises + news) → Gemini API (embeddings + reasoning)

Also exposes an MCP server so it can be plugged into any MCP-compatible client (Claude Desktop, Cursor, etc.)

## Tech stack

- LangGraph — agent orchestration and news ingestion pipeline
- ChromaDB — vector database for semantic search
- Gemini API — embeddings and LLM reasoning (gemini-2.5-flash + gemini-embedding-001)
- Streamlit — web interface
- MCP — tool server for AI client integration
- feedparser — RSS ingestion from Telex.hu and 444.hu
- pypdf — PDF extraction from government document

## Data sources

- A működő és emberséges Magyarország alapjai — official government program document (243 pages, 1151 promises extracted)
- Telex.hu — independent Hungarian news source
- 444.hu — independent Hungarian news source

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

    python extract_pypdf.py   # extract text from PDF
    python structure.py       # extract promises using Gemini
    python add_chapters.py    # add chapter categories
    python fix_categories.py  # consolidate AI categories
    python score_promises.py  # score promises with timeframe + measurability
    python embed.py           # embed promises into ChromaDB
    python news_scraper.py    # scrape initial news articles

Run the app:

    streamlit run app.py

## Project structure

    hungarian-promises/
    ├── extract_pypdf.py    # PDF to markdown
    ├── structure.py        # markdown to structured promises JSON
    ├── add_chapters.py     # rule-based chapter categorization
    ├── fix_categories.py   # AI category consolidation
    ├── score_promises.py   # timeframe + measurability scoring via Gemini
    ├── embed.py            # promises to ChromaDB
    ├── agent.py            # LangGraph query agent
    ├── news_scraper.py     # LangGraph news ingestion pipeline
    ├── server.py           # MCP server
    ├── app.py              # Streamlit UI
    └── data/
        ├── promises.json
        └── chroma/

## How the news pipeline works

The scraper runs daily (Windows Task Scheduler) and uses a two-stage filter:

1. **Rule-based pre-filter** — Telex: drops irrelevant sections (sports, culture, lifestyle). 444.hu: whitelist keeps only POLITIKA, GAZDASÁG, VÉLEMÉNY; unknown sections pass through.
2. **LLM filter** — Gemini decides if the article is relevant to government actions and assigns a promise category.

Only relevant articles get translated to English and embedded. Already-seen articles are skipped by MD5 hash, so re-running is safe.

## Roadmap

### Reliability & Observability (next)
- [ ] Add Langfuse tracing — see every agent run, debug bad answers, track token costs
- [ ] Build an eval set — ~30 question/answer pairs to regression-test the agent
- [ ] Validate extracted promises — schema checks, dedup pass, flag low-confidence ones
- [ ] Replace text JSON parsing with Gemini structured output (response_schema)

### Quality
- [ ] Chunk the program PDF on section boundaries instead of fixed char counts
- [ ] Promise status tracking (fulfilled / in progress / broken / unknown)
- [ ] Confidence scores on news-to-promise matches
- [ ] Hybrid search (semantic + keyword) for proper-noun queries that embeddings miss

### Performance & cost
- [ ] True parallel search in LangGraph (current search_both is sequential)
- [ ] Cache embeddings for repeated queries
- [ ] Switch router to a cheaper model — it's a 3-way classifier, doesn't need Flash

### Architecture
- [ ] Multi-agent orchestrator that proactively monitors uncovered promises
- [ ] Docker deployment
