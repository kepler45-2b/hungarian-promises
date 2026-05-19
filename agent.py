import os
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
    intent: str
    promises: list
    news: list
    answer: str

# --- Nodes ---
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
    query_embedding = embeddings.embed_query(state["query"])
    results = promises_collection.query(
        query_embeddings=[query_embedding],
        n_results=5
    )

    promises = []
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i]
        promises.append({
            "text": doc,
            "chapter": meta.get("category_chapter", "Unknown"),
            "category": meta.get("category_ai", ""),
            "page": meta.get("page_hint", "")
        })

    return {**state, "promises": promises}

def search_news_node(state: AgentState) -> AgentState:
    query_embedding = embeddings.embed_query(state["query"])
    results = news_collection.query(
        query_embeddings=[query_embedding],
        n_results=5
    )

    news = []
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i]
        news.append({
            "text": doc,
            "title": meta.get("title_hu", ""),
            "link": meta.get("link", ""),
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
        promises_text = "\n".join([
            f"- {p['text']}" +
            (f" [Chapter: {p['chapter']}]" if p['chapter'] != 'Unknown' else "") +
            (f" [Page: {p['page']}]" if p['page'] else "") +
            " [Source: A működő és emberséges Magyarország alapjai]"
            for p in state["promises"]
        ])
        context_parts.append(f"GOVERNMENT PROMISES:\n{promises_text}")

    if state["news"]:
        news_text = "\n".join([
            f"- {n['text']}" +
            (f" [Published: {n['published']}]" if n['published'] else "") +
            (f" [Link: {n['link']}]" if n['link'] else "")
            for n in state["news"]
        ])
        context_parts.append(f"RECENT NEWS:\n{news_text}")

    context = "\n\n".join(context_parts)

    system = """You are an assistant tracking whether the new Hungarian government 
keeps its promises. Be factual, cite sources, and be clear when comparing 
promises to actual news."""

    response = llm.invoke([HumanMessage(content=f"""{system}

User question: {state["query"]}

{context}

Answer clearly and concisely. If comparing promises to news, be explicit about 
what was promised vs what has happened.""")])

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
    graph.add_node("router", router_node)
    graph.add_node("search_promises", search_promises_node)
    graph.add_node("search_news", search_news_node)
    graph.add_node("search_both", search_both_node)
    graph.add_node("answer", answer_node)

    graph.set_entry_point("router")
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