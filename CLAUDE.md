# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

RAG-powered tracker for the new Hungarian government (elected April 2026) that indexes 1151 promises from the official program PDF, scrapes Telex.hu and 444.hu news via a LangGraph pipeline, and answers natural language questions about whether promises are being kept.

## Commands

```bash
# Run the Streamlit web app
streamlit run app.py

# Run the query agent interactively (CLI)
python agent.py

# Scrape latest news from Telex.hu
python news_scraper.py

# Run the MCP server (stdio transport, for Claude Desktop / Cursor)
python server.py
```

**One-time data pipeline** (run in order when setting up):
```bash
python extract_pypdf.py   # PDF → program.md (requires the PDF in project root)
python structure.py       # program.md → data/promises.json via Gemini
python add_chapters.py    # adds chapter-based categories to promises
python fix_categories.py  # consolidates AI categories with Gemini
python score_promises.py  # scores each promise with timeframe + measurability via Gemini
python embed.py           # embeds promises into ChromaDB
python news_scraper.py    # seeds initial news articles
```

`structure.py` supports resuming from a specific chunk: `extract_promises(start_chunk=N)`.

## Environment

Requires `GEMINI_API_KEY` in `.env` at the project root. All scripts load it via `python-dotenv`.

## Architecture

```
Streamlit (app.py)
    └── agent.ask()          ← query entry point
    └── news_scraper.run_scraper()

MCP server (server.py)
    └── agent.ask()
    └── news_scraper.run_scraper()

agent.py — LangGraph query graph
    decompose_node → router_node → [search_promises_node | search_news_node | search_both_node] → answer_node
    decompose: breaks the user query into 2-3 focused sub-questions; falls back to [query] on parse error
    router: classifies the original query (not sub-questions) into promises_only / news_only / both
    search nodes: run each sub-query independently (3 results each), merge and deduplicate results
      — promises deduplicate by document text; news deduplicates by URL
    answer: includes timeframe/measurability in context; promises with timeframe="immediate" and
      status="pending" are flagged ⚠️ OVERDUE and highlighted prominently in the answer
    Uses: gemini-2.5-flash (reasoning), gemini-embedding-001 (embeddings)
    Collections: "promises", "news" in data/chroma/

news_scraper.py — LangGraph ingestion graph
    fetch_node → prefilter_node → filter_node → embed_node
    fetch: RSS from telex.hu and 444.hu; deduplicates by MD5(canonical link) against existing ChromaDB IDs
      — 444.hu links have UTM params stripped before hashing; section extracted from the uppercase tag
    prefilter: drops irrelevant sections — Telex uses a blocklist (SKIP_TELEX_SECTIONS); 444.hu uses a whitelist (KEEP_444_SECTIONS: POLITIKA, GAZDASÁG, VÉLEMÉNY); unknown/empty section passes through
    filter: LLM batch-filters in groups of 15, assigns PROMISE_CATEGORIES
    embed: translates Hungarian articles to English via Gemini, then embeds
```

## Data model

**promises** ChromaDB collection — document is `promise_en` (English translation). Metadata keys: `promise_hu`, `promise_en`, `category_ai`, `category_chapter`, `category_main`, `page_hint`, `status`, `timeframe`, `measurability`.

**news** ChromaDB collection — document is the English translation of `title + description`. Metadata keys: `title_hu`, `description_hu`, `text_en`, `link`, `published`, `category`, `section`, `source`, `is_english`. `source` is `"telex.hu"` or `"444.hu"`.

`data/promises.json` is the source of truth for promises; ChromaDB is derived from it. The PDF (`A működő és emberséges Magyarország alapjai.pdf`) must be in the project root for extraction but is not committed.

## Conventions
- Nodes in `agent.py` and `news_scraper.py` are pure functions: `def node(state: AgentState) -> AgentState`
- Always spread state when returning: `return {**state, "new_field": value}`
- LLM calls go through shared instances (`llm` in agent.py, the genai client in news_scraper.py)
- Two ChromaDB collections only: `promises`, `news` — don't introduce new ones lightly
- Never commit `.env`, the PDF, or `data/chroma/`

## Key implementation details

- `news_scraper.py` mixes two Gemini client styles: `google.genai.Client` (direct SDK) for generation, `langchain_google_genai.GoogleGenerativeAIEmbeddings` for embeddings. `agent.py` uses only the LangChain wrappers.
- `call_gemini_with_retry` in `news_scraper.py` handles rate-limit errors with 30s backoff (3 attempts).
- `embed.py` skips already-embedded promises by checking existing ChromaDB IDs — safe to re-run.
- The agent's `route()` function defaults to `"both"` for any unrecognized intent classification. `decompose_node` also falls back to `[state["query"]]` if the LLM returns malformed JSON, keeping single-query behaviour as a safe default.
