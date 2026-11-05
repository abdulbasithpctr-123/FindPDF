
from pdf_reader import read_pdf

CHUNK_SIZE = 400
CHUNK_OVERLAP = 50


def create_chunks(pages):
    chunks = []

    for page in pages:
        words = page["text"].split()
        start = 0

        while start < len(words):
            end = min(start + CHUNK_SIZE, len(words))
            chunk_text = " ".join(words[start:end])

            if chunk_text.strip():
                chunks.append({
                    "chunk_id": len(chunks) + 1,
                    "page": page["page"],
                    "text": chunk_text
                })

            if end == len(words):
                break

            start = end - CHUNK_OVERLAP

    return chunks


if __name__ == "__main__":
    pages = read_pdf("C:\\Users\\pro\\CHAT WITH YOUR PDF\\pdf-chatbot\\data\\K10_English.pdf")
    chunks = create_chunks(pages)

    print("Total pages:", len(pages))
    print("Total chunks:", len(chunks))

    for chunk in chunks[:3]:
        print(f"\nChunk ID: {chunk['chunk_id']}")
        print(f"Source page: {chunk['page']}")
        print(chunk["text"][:300])
