import chromadb
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db = chromadb.PersistentClient(path=os.path.join(BASE_DIR, "data/chroma"))
col = db.get_or_create_collection("news")
data = col.get()

print(f"Total articles: {len(data['metadatas'])}\n")
for m in data["metadatas"]:
    print(f"[{m['category']}] {m['title_hu']}")
    print(f"  EN: {m['text_en']}")
    print(f"  {m['link']}\n")