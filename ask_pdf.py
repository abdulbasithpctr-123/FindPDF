
from retriever import PDFRetriever
from llm_service import GeminiAnswerer


def main():
    print("Loading PDF retriever...")
    retriever = PDFRetriever()

    print("Connecting to Gemini...")
    answerer = GeminiAnswerer()

    print("\nPDF Chatbot is ready!")
    print("Ask a question, or type 'exit' to stop.")

    while True:
        question = input("\nYou: ").strip()

        if question.lower() == "exit":
            print("Goodbye!")
            break

        if not question:
            continue

        try:
            chunks = retriever.search(question, top_k=5)
            answer = answerer.answer(question, chunks)

            print("\nAssistant:")
            print(answer)

        except Exception as error:
            print(f"\nRequest failed: {error}")
            print("Check your API key, model access, and connection.")


if __name__ == "__main__":
    main()
