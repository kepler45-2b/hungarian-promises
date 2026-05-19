import json
import os
import time
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def extract_promises(markdown_path: str = "program.md", output_path: str = "data/promises.json", start_chunk: int = 0):
    print("Reading extracted text...")
    with open(markdown_path, "r", encoding="utf-8") as f:
        text = f.read()

    chunk_size = 30000
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

    if start_chunk > 0 and os.path.exists(output_path):
        print(f"Resuming from chunk {start_chunk + 1}, loading existing {output_path}...")
        with open(output_path, "r", encoding="utf-8") as f:
            all_promises = json.load(f)
    else:
        all_promises = []

    for i, chunk in enumerate(chunks):
        if i < start_chunk:
            continue
        print(f"Processing chunk {i+1}/{len(chunks)}...")
        
        retries = 3
        for attempt in range(retries):
            try:
                time.sleep(13)
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=f"""Extract all specific government promises from this Hungarian political program document.
                    
For each promise return a JSON object with:
- id: sequential number
- category: topic area in English (e.g. Healthcare, Education, Economy, Housing, etc.)
- promise_hu: original Hungarian text
- promise_en: English translation
- page_hint: approximate page number if visible

Return ONLY a JSON array, no other text.

Document chunk:
{chunk}"""
                )
                
                text_response = response.text.strip()
                text_response = text_response.replace("```json", "").replace("```", "").strip()
                promises = json.loads(text_response)
                all_promises.extend(promises)
                print(f"  Found {len(promises)} promises in this chunk")
                break

            except Exception as e:
                if attempt < retries - 1:
                    print(f"  Error: {e}, retrying in 30s...")
                    time.sleep(30)
                else:
                    print(f"  Failed after {retries} attempts, skipping chunk")
        
        # Save progress after every chunk
        os.makedirs("data", exist_ok=True)
        for j, p in enumerate(all_promises):
            p["id"] = j + 1
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_promises, f, ensure_ascii=False, indent=2)

    print(f"\nDone! {len(all_promises)} promises saved to {output_path}")

if __name__ == "__main__":
    extract_promises(start_chunk=14)