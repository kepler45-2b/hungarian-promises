import json
import os
import time
import chromadb
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY")
)

VALID_TIMEFRAMES = {"immediate", "short-term", "long-term", "unknown"}
VALID_MEASURABILITY = {"concrete", "vague"}


def parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())


def score_batch(batch):
    items = [
        {"promise_hu": p["promise_hu"], "promise_en": p["promise_en"]}
        for p in batch
    ]

    response = llm.invoke([HumanMessage(content=f"""Score each government promise on two dimensions.

timeframe: when is this promise expected to be fulfilled?
- "immediate" — days or weeks
- "short-term" — months, within 1 year
- "long-term" — years, over the 4-year term
- "unknown" — no timeframe implied

measurability: does the promise have clear success criteria?
- "concrete" — has specific numbers, deadlines, or measurable targets
- "vague" — no clear success criteria

Return ONLY a JSON array with one object per promise: {{"timeframe": "...", "measurability": "..."}}

Promises:
{json.dumps(items, ensure_ascii=False)}""")])

    return parse_json(response.content)


def score_promises():
    input_path = os.path.join(BASE_DIR, "data/promises.json")
    with open(input_path, encoding="utf-8") as f:
        promises = json.load(f)

    print(f"Loaded {len(promises)} promises.", flush=True)

    to_score = [p for p in promises if "timeframe" not in p or "measurability" not in p]
    already_scored = len(promises) - len(to_score)
    if already_scored:
        print(f"  {already_scored} already scored, processing {len(to_score)} remaining.", flush=True)
    else:
        print(f"  Scoring all {len(to_score)} promises.", flush=True)

    promise_index = {p["id"]: p for p in promises}

    batch_size = 20
    total_batches = (len(to_score) + batch_size - 1) // batch_size
    scored_count = 0

    for i in range(0, len(to_score), batch_size):
        batch = to_score[i:i + batch_size]
        batch_num = i // batch_size + 1
        print(f"  Batch {batch_num}/{total_batches}: sending {len(batch)} promises to Gemini...", flush=True)

        try:
            scores = score_batch(batch)
        except Exception as e:
            print(f"  Error on batch {batch_num}: {e}, skipping.", flush=True)
            time.sleep(10)
            continue

        if len(scores) != len(batch):
            print(f"  Warning: expected {len(batch)} scores, got {len(scores)}. Skipping batch.", flush=True)
            continue

        for j, score in enumerate(scores):
            pid = batch[j]["id"]
            tf = score.get("timeframe", "unknown")
            ms = score.get("measurability", "vague")
            promise_index[pid]["timeframe"] = tf if tf in VALID_TIMEFRAMES else "unknown"
            promise_index[pid]["measurability"] = ms if ms in VALID_MEASURABILITY else "vague"
            promise_index[pid].setdefault("status", "pending")

        scored_count += len(batch)
        print(f"  Batch {batch_num}/{total_batches}: done. ({scored_count}/{len(to_score)} scored so far)", flush=True)

        with open(input_path, "w", encoding="utf-8") as f:
            json.dump(promises, f, ensure_ascii=False, indent=2)
        print(f"  Saved progress to {input_path}", flush=True)

        if i + batch_size < len(to_score):
            print(f"  Sleeping 3s...", flush=True)
            time.sleep(3)

    print(f"\nScored {scored_count} promises. Updating ChromaDB...", flush=True)

    db = chromadb.PersistentClient(path=os.path.join(BASE_DIR, "data/chroma"))
    collection = db.get_or_create_collection("promises")

    existing = collection.get()
    id_to_meta = {eid: meta for eid, meta in zip(existing["ids"], existing["metadatas"])}
    promise_lookup = {str(p["id"]): p for p in promises}

    updated_ids = []
    updated_metadatas = []

    for eid, meta in id_to_meta.items():
        p = promise_lookup.get(eid)
        if p and "timeframe" in p and "measurability" in p:
            new_meta = {
                **meta,
                "timeframe": p["timeframe"],
                "measurability": p["measurability"],
                "status": p.get("status", "pending"),
            }
            updated_ids.append(eid)
            updated_metadatas.append(new_meta)

    if updated_ids:
        db_batch_size = 100
        for i in range(0, len(updated_ids), db_batch_size):
            collection.update(
                ids=updated_ids[i:i + db_batch_size],
                metadatas=updated_metadatas[i:i + db_batch_size],
            )
            print(f"  ChromaDB: updated records {i+1}–{min(i+db_batch_size, len(updated_ids))}", flush=True)
        print(f"Updated {len(updated_ids)} records in ChromaDB.", flush=True)
    else:
        print("No ChromaDB records to update.", flush=True)

    print("Done!", flush=True)


if __name__ == "__main__":
    score_promises()
