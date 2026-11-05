
import json
from pathlib import Path

import faiss
from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

INDEX_PATH = Path("data/faiss.index")
CHUNKS_PATH = Path("data/chunks.json")


class PDFRetriever:
    def __init__(self):
        if not INDEX_PATH.exists() or not CHUNKS_PATH.exists():
            raise FileNotFoundError(
                "Index files are missing. Run embeddings.py first."
            )

        self.model = SentenceTransformer(MODEL_NAME)
        self.index = faiss.read_index(str(INDEX_PATH))

        with CHUNKS_PATH.open("r", encoding="utf-8") as file:
            self.chunks = json.load(file)

        if self.index.ntotal != len(self.chunks):
            raise ValueError(
                "Index and chunk data do not match. Rebuild the index."
            )

    def search(self, question, top_k=5):
        question = question.strip()

        if not question:
            return []

        # Embed the question using the same model
        query_embedding = self.model.encode(
            [question],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        # Search for the closest vectors
        scores, indices = self.index.search(
            query_embedding.astype("float32"),
            min(top_k, len(self.chunks)),
        )

        results = []

        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue

            chunk = self.chunks[int(idx)].copy()
            chunk["similarity"] = float(score)
            results.append(chunk)

        return results


if __name__ == "__main__":
    retriever = PDFRetriever()

    while True:
        question = input(
            "\nAsk a question about your PDF (or type 'exit'): "
        )

        if question.strip().lower() == "exit":
            break

        results = retriever.search(question, top_k=5)

        print("\nMost relevant passages:")

        for result in results:
            print("\n" + "-" * 50)
            print(f"Chunk ID: {result['chunk_id']}")
            print(f"Page: {result['page']}")
            print(f"Similarity: {result['similarity']:.3f}")
            print(result["text"][:500])
