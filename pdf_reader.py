
import fitz
from pathlib import Path

PDF_PATH = Path("C:\\Users\\pro\\CHAT WITH YOUR PDF\\pdf-chatbot\\data\\K10_English.pdf")


def read_pdf(pdf_path):
    pages = []

    with fitz.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text("text").strip()

            pages.append({
                "page": page_number,
                "text": text
            })

    return pages


if __name__ == "__main__":
    if not PDF_PATH.exists():
        print(f"PDF not found: {PDF_PATH}")
    else:
        pages = read_pdf(PDF_PATH)

        print(f"Total pages: {len(pages)}")

        for page in pages[:2]:
            print(f"\n--- PAGE {page['page']} ---")
            print(page["text"][:1000])
