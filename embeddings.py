
import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from pdf_reader import read_pdf
from text_chunker import create_chunks


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DATA_DIR = Path("data")
INDEX_PATH = DATA_DIR / "faiss.index"
CHUNKS_PATH = DATA_DIR / "chunks.json"


def build_embeddings():
    # 1. Extract PDF text and create chunks
    pages = read_pdf(str(DATA_DIR / "C:\\Users\\pro\\CHAT WITH YOUR PDF\\pdf-chatbot\\data\\K10_English.pdf"))
    chunks = create_chunks(pages)

    if not chunks:
        raise ValueError("No text chunks found in the PDF.")

    # 2. Load the embedding model
    print("Loading embedding model...")
    model = SentenceTransformer(MODEL_NAME)

    # 3. Convert each chunk into a vector
    texts = [chunk["text"] for chunk in chunks]

    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    embeddings = np.asarray(embeddings, dtype="float32")

    # 4. Build a cosine-similarity index
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    # 5. Save the index and its corresponding chunks
    faiss.write_index(index, str(INDEX_PATH))

    with CHUNKS_PATH.open("w", encoding="utf-8") as file:
        json.dump(chunks, file, ensure_ascii=False, indent=2)

    print(f"\nChunks indexed: {index.ntotal}")
    print(f"Embedding dimensions: {embeddings.shape[1]}")
    print(f"Index saved to: {INDEX_PATH}")
    print(f"Chunks saved to: {CHUNKS_PATH}")


if __name__ == "__main__":
    build_embeddings()
