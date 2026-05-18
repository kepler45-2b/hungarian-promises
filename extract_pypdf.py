from pypdf import PdfReader

PDF_PATH = r"A működő és emberséges Magyarország alapjai.pdf"
OUTPUT_PATH = "program.md"

def extract_pdf():
    print("Extracting PDF...")
    reader = PdfReader(PDF_PATH)
    
    all_text = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            all_text.append(f"## Page {i+1}\n\n{text}")
    
    full_text = "\n\n---\n\n".join(all_text)
    
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(full_text)
    
    print(f"Done! {len(full_text)} characters saved to {OUTPUT_PATH}")

if __name__ == "__main__":
    extract_pdf()