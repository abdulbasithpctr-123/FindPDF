
import os
import re
import uuid
from pathlib import Path
from typing import Any

import pymupdf
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from pydantic import BaseModel, Field


# ============================================================
# 1. PROJECT CONFIGURATION
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent.parent

ENV_CANDIDATES = [
    PROJECT_ROOT / ".env",
    BACKEND_DIR / ".env",
    Path.cwd() / ".env",
]

env_loaded = False

for env_path in ENV_CANDIDATES:
    if env_path.exists():
        load_dotenv(env_path, override=False)
        print(f"Environment file found: {env_path}")
        env_loaded = True
        break

if not env_loaded:
    load_dotenv()
    print("Warning: No .env file was found in the expected locations.")

print(f"Gemini API key loaded: {bool(os.getenv('GEMINI_API_KEY'))}")

MODEL_NAME = "gemini-3.6-flash"

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB per PDF
CHUNK_SIZE = 400
CHUNK_OVERLAP = 60


# ============================================================
# 2. FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="FindPDF API",
    description="Upload PDFs, ask questions, and compare documents.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Documents are stored in memory.
# Restarting the backend clears the uploaded documents.
documents: dict[str, dict[str, Any]] = {}


# ============================================================
# 3. REQUEST MODELS
# ============================================================

class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=10000)
    document_ids: list[str] = Field(default_factory=list)


# ============================================================
# 4. GEMINI CLIENT
# ============================================================

def get_gemini_client():
    """Create a Gemini client using the API key in .env."""
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail=(
                "GEMINI_API_KEY was not found. "
                "Check that your .env file exists and contains your API key."
            ),
        )

    return genai.Client(api_key=api_key)


# ============================================================
# 5. PDF TEXT EXTRACTION AND CHUNKING
# ============================================================

def extract_pdf_pages(pdf_bytes: bytes) -> list[dict[str, Any]]:
    """
    Extract text from each page of a PDF.

    Returns a list containing each page number and its extracted text.
    """
    pages = []

    try:
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as pdf:
            if pdf.page_count == 0:
                raise ValueError("The PDF has no pages.")

            for page_index, page in enumerate(pdf):
                page_text = page.get_text("text").strip()

                if page_text:
                    pages.append({
                        "page": page_index + 1,
                        "text": page_text,
                    })

    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError(
            "Could not read this PDF. It may be damaged or password-protected."
        ) from exc

    if not pages:
        raise ValueError(
            "No selectable text was found in this PDF. "
            "It may be a scanned document and require OCR."
        )

    return pages


def make_chunks(
    pages: list[dict[str, Any]],
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    """
    Split extracted page text into overlapping word chunks.
    Every chunk keeps its original PDF page number.
    """
    chunks = []

    for page in pages:
        words = page["text"].split()

        if not words:
            continue

        start = 0

        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_text = " ".join(words[start:end]).strip()

            if chunk_text:
                chunks.append({
                    "text": chunk_text,
                    "page": page["page"],
                })

            if end >= len(words):
                break

            start = max(end - overlap, start + 1)

    return chunks


# ============================================================
# 6. QUESTION EXPANSION AND RETRIEVAL
# ============================================================

def expand_question(question: str) -> str:
    """
    Add related terms to improve keyword retrieval when a user
    phrases a question differently from the wording in a PDF.
    """
    normalized = question.lower()

    synonym_groups = {
        "objective": (
            "objective objectives aim aims goal goals purpose purposes "
            "intention target intended outcome"
        ),
        "aim": (
            "aim aims objective objectives goal goals purpose purposes "
            "intention target"
        ),
        "purpose": (
            "purpose purposes objective objectives aim aims goal goals "
            "intention target"
        ),
        "difference": (
            "difference differences compare comparison comparison between "
            "contrast similarities distinction distinguish"
        ),
        "compare": (
            "compare comparison differences similarities contrast "
            "distinction document by document"
        ),
        "summary": (
            "summary summarize summarise overview key points main ideas "
            "important information"
        ),
        "summarize": (
            "summarize summarise summary overview key points main ideas"
        ),
        "problem": (
            "problem problems issue issues challenge challenges limitation "
            "limitations research gap"
        ),
        "methodology": (
            "methodology methods method approach approaches techniques "
            "procedure process"
        ),
        "conclusion": (
            "conclusion conclusions findings results outcome outcomes"
        ),
        "result": (
            "result results findings outcome outcomes conclusion"
        ),
        "author": (
            "author authors written by researcher researchers"
        ),
        "date": (
            "date published publication year created"
        ),
        "introduction": (
            "introduction background overview context"
        ),
        "advantage": (
            "advantage advantages benefit benefits strength strengths"
        ),
        "disadvantage": (
            "disadvantage disadvantages drawback drawbacks weakness weaknesses"
        ),
        "limitation": (
            "limitation limitations weakness weaknesses constraints"
        ),
        "k10": (
            "K10 Kessler Psychological Distress Scale psychological distress "
            "questionnaire ten questions screening scale score"
        ),
    }

    expanded_terms = []

    for keyword, related_terms in synonym_groups.items():
        if re.search(r"\b" + re.escape(keyword) + r"\b", normalized):
            expanded_terms.append(related_terms)

    if "what is" in normalized or "explain" in normalized:
        expanded_terms.append("definition meaning description")

    if "document" in normalized or "pdf" in normalized:
        expanded_terms.append("document content information text")

    return question + " " + " ".join(expanded_terms)


def is_comparison_question(question: str) -> bool:
    """Detect requests that need evidence from multiple documents."""
    text = question.lower()

    comparison_patterns = [
        r"\bcompare\b",
        r"\bcomparison\b",
        r"\bdifferences?\b",
        r"\bsimilarities\b",
        r"\bcontrast\b",
        r"\bcompare\s+and\s+contrast\b",
        r"\bhow\s+are\b.*\bdifferent\b",
        r"\bwhat\s+is\s+different\b",
        r"\bdifferent\s+between\b",
        r"\bcompare\s+the\s+key\b",
    ]

    return any(re.search(pattern, text) for pattern in comparison_patterns)


def retrieve_chunks(
    question: str,
    selected_documents: list[dict[str, Any]],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Retrieve relevant PDF chunks using TF-IDF.

    For comparisons, attempt to include chunks from every selected
    document instead of retrieving only from the strongest match.

    If keyword matching finds no positive scores, return a small
    fallback selection so the answer generator can inspect the text.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    all_chunks = []

    for document in selected_documents:
        for chunk in document.get("chunks", []):
            all_chunks.append({
                **chunk,
                "document_id": document["id"],
                "document_name": document["name"],
            })

    if not all_chunks:
        return []

    texts = [chunk["text"] for chunk in all_chunks]
    expanded_question = expand_question(question)

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
        max_features=100000,
    )

    try:
        matrix = vectorizer.fit_transform(texts + [expanded_question])
        scores = cosine_similarity(
            matrix[-1],
            matrix[:-1],
        ).flatten()
    except ValueError:
        scores = [0.0] * len(all_chunks)

    ranked_indices = sorted(
        range(len(all_chunks)),
        key=lambda index: float(scores[index]),
        reverse=True,
    )

    comparison = is_comparison_question(question)

    if comparison and len(selected_documents) > 1:
        results = []
        used_indices = set()

        # Reserve space for every selected document.
        per_document_limit = max(
            2,
            limit // len(selected_documents),
        )

        for document in selected_documents:
            document_indices = [
                index
                for index, chunk in enumerate(all_chunks)
                if chunk["document_id"] == document["id"]
            ]

            document_indices.sort(
                key=lambda index: float(scores[index]),
                reverse=True,
            )

            for index in document_indices[:per_document_limit]:
                if index not in used_indices:
                    result = dict(all_chunks[index])
                    result["score"] = round(float(scores[index]), 4)
                    results.append(result)
                    used_indices.add(index)

        # Fill any remaining spaces with the highest-scoring chunks.
        for index in ranked_indices:
            if len(results) >= limit:
                break

            if index not in used_indices:
                result = dict(all_chunks[index])
                result["score"] = round(float(scores[index]), 4)
                results.append(result)
                used_indices.add(index)

        return results[:limit]

    # Normal question: use the highest-scoring relevant chunks.
    relevant_indices = [
        index for index in ranked_indices
        if float(scores[index]) > 0
    ]

    if relevant_indices:
        chosen_indices = relevant_indices[:limit]
    else:
        # Fallback: provide text to the answer generator even if
        # the question's wording does not match the PDF vocabulary.
        chosen_indices = ranked_indices[:min(3, len(ranked_indices))]

    results = []

    for index in chosen_indices:
        result = dict(all_chunks[index])
        result["score"] = round(float(scores[index]), 4)
        results.append(result)

    return results


# ============================================================
# 7. API HEALTH CHECK
# ============================================================

@app.get("/")
def root():
    return {
        "message": "FindPDF API is running.",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "message": "FindPDF backend is running.",
        "gemini_api_key_loaded": bool(os.getenv("GEMINI_API_KEY")),
        "model": MODEL_NAME,
        "documents_loaded": len(documents),
    }


# ============================================================
# 8. UPLOAD PDF DOCUMENTS
# ============================================================

@app.post("/api/documents")
async def upload_documents(files: list[UploadFile] = File(...)):
    """
    Upload one or more PDFs, extract their text, and store chunks
    in memory for subsequent questions.
    """
    if not files:
        raise HTTPException(
            status_code=400,
            detail="Please select at least one PDF file.",
        )

    uploaded_documents = []
    errors = []

    for file in files:
        filename = file.filename or "unnamed.pdf"

        if not filename.lower().endswith(".pdf"):
            errors.append({
                "filename": filename,
                "error": "Only PDF files are supported.",
            })
            continue

        try:
            pdf_bytes = await file.read()

            if not pdf_bytes:
                errors.append({
                    "filename": filename,
                    "error": "The uploaded file is empty.",
                })
                continue

            if len(pdf_bytes) > MAX_FILE_SIZE:
                errors.append({
                    "filename": filename,
                    "error": "The PDF exceeds the 25 MB file-size limit.",
                })
                continue

            pages = extract_pdf_pages(pdf_bytes)
            chunks = make_chunks(pages)

            document_id = str(uuid.uuid4())

            document = {
                "id": document_id,
                "name": filename,
                "size": len(pdf_bytes),
                "pages": len(pages),
                "chunks": chunks,
            }

            documents[document_id] = document

            uploaded_documents.append({
                "id": document_id,
                "name": filename,
                "size": len(pdf_bytes),
                "pages": len(pages),
                "chunks": len(chunks),
                "status": "success",
            })

        except ValueError as exc:
            errors.append({
                "filename": filename,
                "error": str(exc),
            })

        except Exception as exc:
            print(f"Error processing {filename}: {exc}")
            errors.append({
                "filename": filename,
                "error": "An unexpected error occurred while processing this PDF.",
            })

        finally:
            await file.close()

    if not uploaded_documents and errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "No PDFs could be uploaded.",
                "errors": errors,
            },
        )

    return {
        "message": f"Uploaded {len(uploaded_documents)} PDF(s).",
        "documents": uploaded_documents,
        "errors": errors,
    }


# ============================================================
# 9. LIST UPLOADED DOCUMENTS
# ============================================================

@app.get("/api/documents")
def list_documents():
    """Return metadata for all currently uploaded PDFs."""
    return {
        "documents": [
            {
                "id": document["id"],
                "name": document["name"],
                "size": document["size"],
                "pages": document["pages"],
                "chunks": len(document["chunks"]),
            }
            for document in documents.values()
        ]
    }


# ============================================================
# 10. DELETE A DOCUMENT
# ============================================================

@app.delete("/api/documents/{document_id}")
def delete_document(document_id: str):
    """Delete a PDF from the in-memory document collection."""
    if document_id not in documents:
        raise HTTPException(
            status_code=404,
            detail="Document not found. It may have been removed after a restart.",
        )

    deleted_document = documents.pop(document_id)

    return {
        "message": "Document deleted successfully.",
        "id": document_id,
        "name": deleted_document["name"],
    }


# ============================================================
# 11. CHAT WITH PDFs
# ============================================================

@app.post("/api/chat")
def chat_with_documents(request: QuestionRequest):
    """
    Answer questions using retrieved PDF excerpts.

    Supports single-document questions and multi-document comparisons.
    """
    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Please enter a question.",
        )

    # Use selected documents when IDs are provided.
    if request.document_ids:
        selected_documents = [
            documents[document_id]
            for document_id in request.document_ids
            if document_id in documents
        ]

        if not selected_documents:
            raise HTTPException(
                status_code=400,
                detail=(
                    "None of the selected PDFs are available. "
                    "Please upload or select your PDFs again."
                ),
            )
    else:
        # If the frontend sends no document IDs, use all uploaded PDFs.
        selected_documents = list(documents.values())

    if not selected_documents:
        raise HTTPException(
            status_code=400,
            detail="Upload at least one PDF before asking a question.",
        )

    chunks = retrieve_chunks(
        question=question,
        selected_documents=selected_documents,
        limit=12,
    )

    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="No readable text is available in the selected PDFs.",
        )

    comparison = (
        is_comparison_question(question)
        and len(selected_documents) > 1
    )

    # Build context with explicit document names and page numbers.
    context_parts = []

    for index, chunk in enumerate(chunks, start=1):
        context_parts.append(
            f"[Excerpt {index}]\n"
            f"Document: {chunk['document_name']}\n"
            f"Page: {chunk['page']}\n"
            f"Retrieval score: {chunk['score']}\n"
            f"Text:\n{chunk['text']}"
        )

    context = "\n\n".join(context_parts)

    if comparison:
        task_instructions = """
Compare the selected documents carefully.

1. Consider evidence from EACH document, not just one.
2. Explain the key differences in a clear, organized way.
3. Also mention important similarities when supported by the excerpts.
4. If useful, organize the answer by topic or use a Markdown table.
5. Cite the document name and page number for each important claim.
6. Do not assume that a topic absent from the supplied excerpts is absent
   from the full document.
7. If the supplied excerpts are insufficient for a particular comparison,
   state that limitation clearly.
"""
    else:
        task_instructions = """
Answer the user's question using the supplied PDF excerpts.

1. Give a direct answer first.
2. Use clear explanations and organize the answer with headings or lists
   when helpful.
3. Cite the document name and page number for important claims.
4. If the question asks for an objective, aim, purpose, method, result,
   definition, or conclusion, look for wording that expresses that idea
   even if the exact word in the question is not present.
5. If the excerpts do not contain enough evidence, say so clearly.
6. Do not invent facts or pretend that unsupported information appears
   in the documents.
"""

    prompt = f"""
You are FindPDF, a helpful PDF question-answering assistant.

IMPORTANT RULES:
- Treat the PDF excerpts below as your source of evidence.
- Do not fabricate quotations, page numbers, or document content.
- The retrieval score is a technical relevance estimate, not proof that
  an excerpt is irrelevant.
- You may synthesize information from multiple excerpts when supported.
- Clearly distinguish document facts from any uncertainty.
- Never claim to have reviewed pages or content that were not supplied.

TASK INSTRUCTIONS:
{task_instructions}

USER QUESTION:
{question}

SELECTED DOCUMENTS:
{", ".join(document["name"] for document in selected_documents)}

PDF EXCERPTS:
{context}

Write the answer in readable Markdown. Include source document names
and page numbers where appropriate.
"""

    try:
        client = get_gemini_client()

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config={
                "temperature": 0.2,
                "max_output_tokens": 2500,
            },
        )

        answer = (response.text or "").strip()

        if not answer:
            answer = (
                "The AI model returned an empty response. "
                "Please try asking your question in a different way."
            )

    except HTTPException:
        raise

    except Exception as exc:
        print(f"Gemini API error: {exc}")

        raise HTTPException(
            status_code=502,
            detail=(
                "The AI service could not generate an answer. "
                "Check your API quota, API key, model availability, "
                "and internet connection, then try again."
            ),
        ) from exc

    sources = []

    for chunk in chunks:
        sources.append({
            "document_id": chunk["document_id"],
            "document_name": chunk["document_name"],
            "page": chunk["page"],
            "excerpt": chunk["text"][:700],
            "score": chunk["score"],
        })

    return {
        "answer": answer,
        "sources": sources,
        "question": question,
        "documents_used": [
            {
                "id": document["id"],
                "name": document["name"],
            }
            for document in selected_documents
        ],
    }


# ============================================================
# 12. RUNNING THE SERVER
# ============================================================

# Start the backend from the terminal using Uvicorn:
#
# & ".\FindPDF-Web\backend\.venv\Scripts\python.exe" -m uvicorn main:app --app-dir ".\FindPDF-Web\backend" --reload --host 127.0.0.1 --port 8000
