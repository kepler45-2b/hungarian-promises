import json
import os
import time
import chromadb
from google import genai
from dotenv import load_dotenv

load_dotenv()

gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def embed_promises(input_path: str = "data/promises.json"):
    with open(input_path, encoding="utf-8") as f:
        promises = json.load(f)

    db = chromadb.PersistentClient(path="data/chroma")
    collection = db.get_or_create_collection("promises")

    # Skip already embedded
    existing_ids = set(collection.get()["ids"])
    promises = [p for p in promises if str(p["id"]) not in existing_ids]
    print(f"Embedding {len(promises)} remaining promises...")

    batch_size = 10
    for i in range(0, len(promises), batch_size):
        batch = promises[i:i+batch_size]
        texts = [p["promise_en"] for p in batch]

        try:
            result = gemini.models.embed_content(
                model="gemini-embedding-001",
                contents=texts
            )
            embeddings = [e.values for e in result.embeddings]

            collection.add(
                ids=[str(p["id"]) for p in batch],
                embeddings=embeddings,
                documents=texts,
                metadatas=[{
                    "promise_hu": p["promise_hu"],
                    "promise_en": p["promise_en"],
                    "category_ai": p["category_ai"],
                    "category_chapter": p.get("category_chapter", ""),
                    "category_main": p.get("category_main", ""),
                    "page_hint": str(p.get("page_hint", "")),
                    "status": p.get("status", "pending")
                } for p in batch]
            )

            print(f"  Embedded {min(i+batch_size, len(promises))}/{len(promises)}")
            time.sleep(1.5)  # ~40 requests/min, well under limit

        except Exception as e:
            print(f"  Error: {e}, waiting 60s...")
            time.sleep(60)


    print(f"\nDone! {collection.count()} promises in ChromaDB")

if __name__ == "__main__":
    embed_promises()