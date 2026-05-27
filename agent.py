import os
import json
import chromadb
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

db = chromadb.PersistentClient(path=os.path.join(BASE_DIR, "data/chroma"))
promises_collection = db.get_or_create_collection("promises")
news_collection = db.get_or_create_collection("news")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY")
)

embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-001",
    google_api_key=os.getenv("GEMINI_API_KEY")
)

# --- State ---
class AgentState(TypedDict):
    query: str
    sub_queries: list
    intent: str
    promises: list
    news: list
    answer: str

# --- Nodes ---
def decompose_node(state: AgentState) -> AgentState:
    response = llm.invoke([HumanMessage(content=f"""Break this question into 2-3 focused sub-questions that together fully answer it.
Each sub-question should target a specific aspect (e.g. what was promised, what has happened, what is the current status).

Original question: {state["query"]}

Return ONLY a JSON array of strings, e.g. ["sub-question 1", "sub-question 2"]""")])

    try:
        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        sub_queries = json.loads(text.strip())
        if not isinstance(sub_queries, list) or not sub_queries:
            raise ValueError
        sub_queries = [q for q in sub_queries if isinstance(q, str)][:3]
    except Exception:
        sub_queries = [state["query"]]

    print(f"  Sub-queries: {sub_queries}")
    return {**state, "sub_queries": sub_queries}

def router_node(state: AgentState) -> AgentState:
    response = llm.invoke([HumanMessage(content=f"""Classify this query into exactly one of:
- "promises_only" — asking about government promises, plans, or commitments
- "news_only" — asking about recent news or current events
- "both" — asking whether promises are being kept, comparing promises to reality

Query: {state["query"]}

Return ONLY the classification word.""")])

    intent = response.content.strip().lower()
    if intent not in ["promises_only", "news_only", "both"]:
        intent = "both"

    print(f"  Intent: {intent}")
    return {**state, "intent": intent}

def search_promises_node(state: AgentState) -> AgentState:
    queries = state["sub_queries"] or [state["query"]]
    seen_texts = set()
    promises = []

    for q in queries:
        query_embedding = embeddings.embed_query(q)
        results = promises_collection.query(
            query_embeddings=[query_embedding],
            n_results=3
        )
        for i, doc in enumerate(results["documents"][0]):
            if doc in seen_texts:
                continue
            seen_texts.add(doc)
            meta = results["metadatas"][0][i]
            timeframe = meta.get("timeframe", "unknown")
            status = meta.get("status", "pending")
            promises.append({
                "text": doc,
                "chapter": meta.get("category_chapter", "Unknown"),
                "category": meta.get("category_ai", ""),
                "page": meta.get("page_hint", ""),
                "timeframe": timeframe,
                "measurability": meta.get("measurability", "vague"),
                "status": status,
                "overdue": timeframe == "immediate" and status == "pending",
            })

    return {**state, "promises": promises}

def search_news_node(state: AgentState) -> AgentState:
    queries = state["sub_queries"] or [state["query"]]
    seen_links = set()
    news = []

    for q in queries:
        query_embedding = embeddings.embed_query(q)
        results = news_collection.query(
            query_embeddings=[query_embedding],
            n_results=3
        )
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            link = meta.get("link", "")
            if link and link in seen_links:
                continue
            if link:
                seen_links.add(link)
            news.append({
                "text": doc,
                "title": meta.get("title_hu", ""),
                "link": link,
                "published": meta.get("published", ""),
                "category": meta.get("category", "")
            })

    return {**state, "news": news}

def search_both_node(state: AgentState) -> AgentState:
    state = search_promises_node(state)
    state = search_news_node(state)
    return state

def answer_node(state: AgentState) -> AgentState:
    context_parts = []

    if state["promises"]:
        promise_lines = []
        for p in state["promises"]:
            line = f"- {p['text']}"
            if p["chapter"] != "Unknown":
                line += f" [Chapter: {p['chapter']}]"
            if p["page"]:
                line += f" [Page: {p['page']}]"
            tags = []
            if p["timeframe"] != "unknown":
                tags.append(f"timeframe: {p['timeframe']}")
            if p["measurability"]:
                tags.append(f"measurability: {p['measurability']}")
            if p["overdue"]:
                tags.append("⚠️ OVERDUE: immediate promise, still pending")
            elif p["status"] != "pending":
                tags.append(f"status: {p['status']}")
            if tags:
                line += f" [{', '.join(tags)}]"
            line += " [Source: A működő és emberséges Magyarország alapjai]"
            promise_lines.append(line)
        context_parts.append("GOVERNMENT PROMISES:\n" + "\n".join(promise_lines))

    if state["news"]:
        news_text = "\n".join([
            f"- {n['text']}" +
            (f" [Published: {n['published']}]" if n['published'] else "") +
            (f" [Link: {n['link']}]" if n['link'] else "")
            for n in state["news"]
        ])
        context_parts.append(f"RECENT NEWS:\n{news_text}")

    context = "\n\n".join(context_parts)

    system = """You are an assistant tracking whether the new Hungarian government (in power since May 2026) keeps its promises. Be factual, cite sources, and be clear when comparing promises to actual news.
Promises marked ⚠️ OVERDUE are immediate commitments (expected within days or weeks of taking power) that are still pending — flag these prominently in your answer."""

    response = llm.invoke([HumanMessage(content=f"""{system}

User question: {state["query"]}

{context}

Answer clearly and concisely. If comparing promises to news, be explicit about what was promised vs what has happened.""")])

    return {**state, "answer": response.content}

# --- Routing function ---
def route(state: AgentState) -> Literal["search_promises", "search_news", "search_both"]:
    if state["intent"] == "promises_only":
        return "search_promises"
    elif state["intent"] == "news_only":
        return "search_news"
    else:
        return "search_both"

# --- Build graph ---
def build_agent():
    graph = StateGraph(AgentState)
    graph.add_node("decompose", decompose_node)
    graph.add_node("router", router_node)
    graph.add_node("search_promises", search_promises_node)
    graph.add_node("search_news", search_news_node)
    graph.add_node("search_both", search_both_node)
    graph.add_node("answer", answer_node)

    graph.set_entry_point("decompose")
    graph.add_edge("decompose", "router")
    graph.add_conditional_edges("router", route, {
        "search_promises": "search_promises",
        "search_news": "search_news",
        "search_both": "search_both"
    })
    graph.add_edge("search_promises", "answer")
    graph.add_edge("search_news", "answer")
    graph.add_edge("search_both", "answer")
    graph.add_edge("answer", END)

    return graph.compile()

agent = build_agent()

def ask(query: str) -> str:
    result = agent.invoke({
        "query": query,
        "sub_queries": [],
        "intent": "",
        "promises": [],
        "news": [],
        "answer": ""
    })
    return result["answer"]

if __name__ == "__main__":
    print("Hungarian Government Promise Tracker")
    print("=====================================")
    while True:
        query = input("\nAsk a question (or 'quit'): ")
        if query.lower() == "quit":
            break
        print("\n" + ask(query))
