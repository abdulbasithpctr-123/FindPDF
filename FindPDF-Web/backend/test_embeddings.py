
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

project_root = Path(__file__).resolve().parents[2]
load_dotenv(project_root / ".env")

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise SystemExit("GEMINI_API_KEY is missing from .env")

client = genai.Client(api_key=api_key)

try:
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents="FindPDF semantic embedding test",
        config=types.EmbedContentConfig(
            output_dimensionality=768
        ),
    )

    vector = result.embeddings[0].values

    print("Embedding generation successful!")
    print("Embedding dimensions:", len(vector))
    print("Vector contains values:", bool(vector))

except Exception as exc:
    print("Embedding test failed.")
    print(type(exc).__name__ + ":", str(exc))
