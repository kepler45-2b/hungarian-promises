from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat
from docling.document_converter import PdfFormatOption

PDF_PATH = r"A működő és emberséges Magyarország alapjai.pdf"
OUTPUT_PATH = "program.md"

def extract_pdf():
    print("Converting PDF...")
    
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = False
    pipeline_options.images_scale = 1.0
    
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    
    result = converter.convert(PDF_PATH)
    markdown = result.document.export_to_markdown()
    
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(markdown)
    
    print(f"Done! {len(markdown)} characters saved to {OUTPUT_PATH}")

if __name__ == "__main__":
    extract_pdf()