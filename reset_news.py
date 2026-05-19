import chromadb
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db = chromadb.PersistentClient(path=os.path.join(BASE_DIR, "data/chroma"))
db.delete_collection("news")
print("News collection deleted.")