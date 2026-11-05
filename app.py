
import html
import tempfile
from collections import Counter
from pathlib import Path

import streamlit as st
import torch
from sentence_transformers import SentenceTransformer, util

from pdf_reader import read_pdf
from text_chunker import create_chunks
from llm_service import GeminiAnswerer


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="FindPDF — AI Document Workspace",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# PREMIUM DARK THEME
# =========================================================

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');

    :root {
        --bg: #080d18;
        --sidebar: #0b1220;
        --panel: #101a2b;
        --panel-hover: #152239;
        --border: #23334b;
        --text: #edf4ff;
        --muted: #8fa1ba;
        --teal: #5eead4;
        --teal-dark: #123b3c;
    }

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }

    .stApp {
        background:
            radial-gradient(
                ellipse at 55% -15%,
                rgba(45, 110, 120, 0.15),
                transparent 45%
            ),
            var(--bg);
        color: var(--text);
    }

    [data-testid="stHeader"] {
        background: rgba(8, 13, 24, 0.8);
    }

    [data-testid="stSidebar"] {
        background: var(--sidebar);
        border-right: 1px solid var(--border);
    }

    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1.1rem;
    }

    .block-container {
        max-width: 1160px;
        padding-top: 1.4rem;
        padding-bottom: 2.5rem;
    }

    h1, h2, h3, h4 {
        font-family: 'Space Grotesk', sans-serif !important;
        color: var(--text) !important;
        letter-spacing: -0.4px;
    }

    p, li, label {
        color: #c6d2e3;
    }

    [data-testid="stCaptionContainer"] p {
        color: var(--muted);
    }

    [data-testid="stFileUploader"] {
        background: #0f1929;
        border: 1px dashed #33465f;
        border-radius: 14px;
        padding: 10px;
    }

    [data-testid="stFileUploader"] section {
        background: transparent;
    }

    .brand {
        display: flex;
        align-items: center;
        gap: 10px;
        color: #f8fafc;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.45rem;
        font-weight: 700;
        letter-spacing: -0.8px;
        padding: 3px 0 0;
    }

    .brand-mark {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 39px;
        height: 39px;
        border-radius: 12px;
        background: linear-gradient(135deg, #5eead4, #2dd4bf);
        color: #082f32;
        font-size: 1.25rem;
        box-shadow: 0 4px 22px rgba(45, 212, 191, 0.15);
    }

    .brand-caption {
        color: #7f93ad;
        font-size: 0.67rem;
        letter-spacing: 1.7px;
        font-weight: 600;
        margin: 7px 0 18px 49px;
    }

    .sidebar-label {
        color: #8fa1ba;
        font-size: 0.69rem;
        font-weight: 700;
        letter-spacing: 1.6px;
        text-transform: uppercase;
        margin: 18px 0 10px;
    }

    .hero {
        padding: 65px 10px 35px;
        text-align: center;
    }

    .hero-pill {
        display: inline-block;
        border: 1px solid rgba(94, 234, 212, 0.28);
        background: rgba(94, 234, 212, 0.07);
        color: var(--teal);
        padding: 7px 13px;
        border-radius: 100px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 1.4px;
        margin-bottom: 22px;
    }

    .hero h1 {
        font-size: clamp(2.5rem, 5.5vw, 4.35rem);
        line-height: 1.08;
        letter-spacing: -2.5px;
        margin: 0;
    }

    .hero h1 span {
        color: var(--teal);
    }

    .hero p {
        max-width: 560px;
        margin: 20px auto 0;
        color: #93a5bd;
        font-size: 1rem;
        line-height: 1.8;
    }

    .section-heading {
        font-family: 'Space Grotesk', sans-serif;
        color: #edf4ff;
        font-weight: 600;
        font-size: 1rem;
        margin: 14px 0 5px;
    }

    .section-description {
        color: #8497b1;
        font-size: 0.83rem;
        margin-bottom: 16px;
    }

    .document-card {
        background: linear-gradient(145deg, #121f33, #0e1727);
        border: 1px solid #25364f;
        border-radius: 15px;
        padding: 16px;
        min-height: 125px;
        overflow-wrap: anywhere;
        transition: border-color 0.2s ease,
                    transform 0.2s ease;
    }

    .document-icon {
        width: 35px;
        height: 35px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(94, 234, 212, 0.1);
        border: 1px solid rgba(94, 234, 212, 0.13);
        border-radius: 10px;
        font-size: 1.05rem;
        margin-bottom: 13px;
    }

    .document-name {
        color: #e6eefb;
        font-size: 0.84rem;
        font-weight: 600;
        line-height: 1.5;
        margin-bottom: 8px;
        overflow-wrap: anywhere;
    }

    .document-meta {
        color: #879ab3;
        font-size: 0.74rem;
    }

    .workspace-note {
        color: #8ea1b9;
        background: rgba(16, 26, 43, 0.8);
        border: 1px solid #23334b;
        border-radius: 12px;
        padding: 12px 15px;
        font-size: 0.8rem;
        line-height: 1.6;
        margin: 10px 0 20px;
    }

    [data-testid="stChatMessage"] {
        background: rgba(15, 25, 42, 0.75);
        border: 1px solid #24354d;
        border-radius: 16px;
        padding: 14px 16px;
        margin-bottom: 13px;
    }

    [data-testid="stChatMessage"] p {
        line-height: 1.8;
    }

    [data-testid="stChatInput"] {
        border-color: #2b405a;
        border-radius: 16px;
    }

    [data-testid="stChatInput"] textarea {
        color: #edf4ff;
        background: #101a2b;
    }

    [data-testid="stExpander"] {
        background: #0f1929;
        border: 1px solid #25364f;
        border-radius: 13px;
    }

    [data-testid="stExpander"] summary {
        color: #dce8f8;
    }

    .answer-eyebrow {
        color: var(--teal);
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 1.8px;
        margin-bottom: 10px;
    }

    .status-line {
        color: #91a4bc;
        font-size: 0.77rem;
        padding: 7px 0;
    }

    .stButton > button {
        border-radius: 11px;
        border: 1px solid #293b54;
        background: #111c2e;
        color: #dce8f8;
        min-height: 40px;
        font-weight: 600;
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        border-color: #5eead4;
        color: #5eead4;
        background: #142537;
    }

    .stButton > button[kind="primary"] {
        background: #5eead4;
        color: #062b2c;
        border-color: #5eead4;
    }

    .stButton > button[kind="primary"]:hover {
        background: #99f6e4;
        border-color: #99f6e4;
        color: #062b2c;
    }

    [data-testid="stProgressBar"] > div > div {
        background-color: #5eead4;
    }

    hr {
        border-color: #23334b;
    }

    .footer {
        color: #647893;
        text-align: center;
        font-size: 0.73rem;
        margin-top: 45px;
        padding: 18px 0;
        border-top: 1px solid #1c2b40;
    }

    @media (max-width: 768px) {
        .hero {
            padding-top: 35px;
        }

        .hero h1 {
            letter-spacing: -1.5px;
        }

        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# SESSION STATE
# =========================================================

if "documents" not in st.session_state:
    st.session_state.documents = {}

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None


# =========================================================
# LOAD MODELS
# =========================================================

@st.cache_resource
def load_embedder():
    return SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2"
    )


@st.cache_resource
def load_answerer():
    return GeminiAnswerer()


# =========================================================
# PROCESS PDF
# =========================================================

@st.cache_data(show_spinner=False)
def process_pdf(pdf_bytes, filename):
    with tempfile.TemporaryDirectory() as temp_dir:
        pdf_path = Path(temp_dir) / "uploaded.pdf"
        pdf_path.write_bytes(pdf_bytes)
        pages = read_pdf(str(pdf_path))

    full_pages = []

    for page in pages:
        page_text = page.get("text", "")

        if page_text.strip():
            full_pages.append({
                "source": filename,
                "page": int(page["page"]),
                "text": page_text,
            })

    chunks = create_chunks(pages)

    for index, chunk in enumerate(chunks, start=1):
        chunk["source"] = filename
        chunk["chunk_id"] = index

    if not chunks or not full_pages:
        raise ValueError(
            "No readable text was extracted from this PDF. "
            "Scanned PDFs may require OCR."
        )

    return {
        "chunks": chunks,
        "pages": len(pages),
        "full_pages": full_pages,
    }


# =========================================================
# LOCAL EMBEDDINGS
# =========================================================

@st.cache_data(show_spinner=False)
def embed_chunks(texts):
    model = load_embedder()

    vectors = model.encode(
        list(texts),
        convert_to_tensor=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    return vectors.cpu()


# =========================================================
# SEARCH DOCUMENTS
# =========================================================

def search_documents(question, documents, top_k=5):
    all_chunks = [
        chunk
        for document in documents.values()
        for chunk in document["chunks"]
    ]

    if not all_chunks:
        return []

    model = load_embedder()
    texts = tuple(chunk["text"] for chunk in all_chunks)
    vectors = embed_chunks(texts)

    query_vector = model.encode(
        question,
        convert_to_tensor=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    ).cpu()

    scores = util.cos_sim(query_vector, vectors)[0]
    count = min(top_k, len(all_chunks))
    indices = torch.topk(scores, k=count).indices.tolist()

    results = []

    for index in indices:
        chunk = dict(all_chunks[index])
        chunk["score"] = float(scores[index].item())
        results.append(chunk)

    return results


# =========================================================
# COMPARISON DETECTION AND BALANCED RETRIEVAL
# =========================================================

def is_comparison_request(question):
    q = question.lower()

    terms = [
        "compare",
        "comparison",
        "difference",
        "differences",
        "different from",
        "similarities",
        "similarity",
        "contrast",
        "versus",
        "vs.",
        "distinguish",
        "what is different",
        "what are the differences",
    ]

    return any(term in q for term in terms)


def search_each_document(
    question,
    documents,
    top_k_per_document=3,
):
    results = []

    for filename, document in documents.items():
        document_results = search_documents(
            question,
            {filename: document},
            top_k=top_k_per_document,
        )

        results.extend(document_results)

    results.sort(
        key=lambda item: item.get("score", 0.0),
        reverse=True,
    )

    return results


# =========================================================
# ASSIGNMENT EXTRACTION
# =========================================================

def is_complete_extraction_request(question):
    q = question.lower()

    triggers = [
        "all questions",
        "all assignment questions",
        "all the questions",
        "every question",
        "all question",
        "entire assignment",
        "complete assignment",
        "full assignment",
        "list all questions",
        "extract all questions",
        "all problems",
        "all exercises",
        "every problem",
        "whole assignment",
        "whole question paper",
        "complete question paper",
    ]

    return any(trigger in q for trigger in triggers)


def find_assignment_document(question, documents):
    keywords = [
        "assignment",
        "problem",
        "exercise",
        "question-paper",
        "question paper",
        "question_paper",
    ]

    candidates = [
        (name, document)
        for name, document in documents.items()
        if any(keyword in name.lower() for keyword in keywords)
    ]

    if len(candidates) == 1:
        return candidates[0]

    if len(candidates) > 1:
        q = question.lower()

        exact_matches = [
            item
            for item in candidates
            if item[0].lower().replace("_", " ") in q
        ]

        if len(exact_matches) == 1:
            return exact_matches[0]

        candidate_map = dict(candidates)
        results = search_documents(
            question,
            candidate_map,
            top_k=5,
        )

        if results:
            counts = Counter(
                result["source"] for result in results
            )
            best_name = counts.most_common(1)[0][0]
            return best_name, candidate_map[best_name]

        return candidates[0]

    results = search_documents(question, documents, top_k=5)

    if not results:
        return None

    counts = Counter(result["source"] for result in results)
    best_name = counts.most_common(1)[0][0]

    return best_name, documents[best_name]


# =========================================================
# SIDEBAR WORKSPACE
# =========================================================

with st.sidebar:
    st.markdown(
        """
        <div class="brand">
            <span class="brand-mark">⌕</span>
            <span>FindPDF</span>
        </div>
        <div class="brand-caption">AI DOCUMENT WORKSPACE</div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    st.markdown(
        '<div class="sidebar-label">Your documents</div>',
        unsafe_allow_html=True,
    )

    uploaded_files = st.file_uploader(
        "Upload PDF files",
        type=["pdf"],
        accept_multiple_files=True,
        help="Upload one or more PDFs to search them together.",
    )

    if st.button(
        "＋  Process documents",
        type="primary",
        use_container_width=True,
    ):
        if not uploaded_files:
            st.warning("Choose at least one PDF first.")
        else:
            filenames = [file.name for file in uploaded_files]

            if len(filenames) != len(set(filenames)):
                st.error(
                    "Duplicate filenames detected. Rename the files "
                    "so every document has a unique filename."
                )
            else:
                new_documents = {}
                failures = []
                progress = st.progress(0)
                status = st.empty()

                for index, file in enumerate(uploaded_files):
                    try:
                        status.caption(
                            f"Processing {index + 1}/"
                            f"{len(uploaded_files)}: {file.name}"
                        )

                        new_documents[file.name] = process_pdf(
                            file.getvalue(),
                            file.name,
                        )

                    except Exception as error:
                        failures.append((file.name, str(error)))

                    progress.progress(
                        (index + 1) / len(uploaded_files)
                    )

                st.session_state.documents = new_documents
                st.session_state.messages = []
                st.session_state.pending_question = None

                progress.empty()
                status.empty()

                if new_documents:
                    st.success(
                        f"{len(new_documents)} PDF(s) ready to search."
                    )

                for filename, error in failures:
                    st.error(f"{filename}: {error}")

                if not new_documents:
                    st.warning("No PDFs were processed successfully.")

    st.divider()

    document_count = len(st.session_state.documents)

    st.markdown(
        f'<div class="sidebar-label">Library · {document_count}</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.documents:
        for filename, document in st.session_state.documents.items():
            st.markdown(
                f"""
                <div class="document-card" style="margin-bottom:9px;">
                    <div class="document-icon">📄</div>
                    <div class="document-name">
                        {html.escape(filename)}
                    </div>
                    <div class="document-meta">
                        ● Ready · {document['pages']} pages
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.caption(
                f"{len(document['chunks'])} searchable chunks"
            )
    else:
        st.caption(
            "Your processed PDFs will appear here."
        )

    st.divider()

    if st.button(
        "＋  New conversation",
        use_container_width=True,
    ):
        st.session_state.messages = []
        st.session_state.pending_question = None
        st.rerun()

    if st.button(
        "Clear document library",
        use_container_width=True,
    ):
        st.session_state.documents = {}
        st.session_state.messages = []
        st.session_state.pending_question = None
        st.rerun()

    st.markdown(
        """
        <div style="
            margin-top:24px;
            padding:13px;
            border:1px solid #23334b;
            background:#0f1929;
            border-radius:12px;
        ">
            <div style="
                color:#5eead4;
                font-size:.72rem;
                font-weight:700;
                letter-spacing:1px;
            ">PRIVATE WORKSPACE</div>
            <div style="
                color:#8fa1ba;
                font-size:.76rem;
                line-height:1.6;
                margin-top:6px;
            ">
                Search locally. Generate AI answers only when needed.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# MAIN WORKSPACE HEADER
# =========================================================

st.markdown(
    """
    <div style="
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:12px;
        border-bottom:1px solid #23334b;
        padding:5px 0 16px;
        margin-bottom:10px;
    ">
        <div>
            <div style="
                color:#edf4ff;
                font-family:'Space Grotesk',sans-serif;
                font-size:1.12rem;
                font-weight:600;
            ">Document workspace</div>
            <div style="
                color:#8497b1;
                font-size:.77rem;
                margin-top:4px;
            ">Your knowledge, connected.</div>
        </div>
        <div style="
            color:#5eead4;
            border:1px solid rgba(94,234,212,.22);
            background:rgba(94,234,212,.06);
            border-radius:100px;
            padding:7px 11px;
            font-size:.72rem;
            font-weight:600;
            white-space:nowrap;
        ">● AI ASSISTANT</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# WELCOME SCREEN
# =========================================================

if not st.session_state.documents and not st.session_state.messages:
    st.markdown(
        """
        <div class="hero">
            <div class="hero-pill">✦ YOUR AI DOCUMENT ASSISTANT</div>
            <h1>Your documents.<br><span>One conversation.</span></h1>
            <p>
                Ask questions, compare reports, and find important
                information across your PDFs without searching
                through every page manually.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="workspace-note">
            <strong style="color:#5eead4;">Getting started</strong><br>
            Upload PDFs using the sidebar, process them, and then
            ask a question below. Document search and embeddings
            run locally; Gemini is used to generate AI answers.
        </div>
        """,
        unsafe_allow_html=True,
    )

elif st.session_state.documents and not st.session_state.messages:
    st.markdown(
        """
        <div style="padding:25px 0 15px;">
            <div style="
                color:#5eead4;
                font-size:.7rem;
                font-weight:700;
                letter-spacing:1.6px;
            ">YOUR LIBRARY</div>
            <h2 style="margin-top:8px;">
                Ready to explore your documents
            </h2>
            <p style="color:#8fa1ba;">
                Ask a question, find an answer, or compare your PDFs.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    docs = list(st.session_state.documents.items())
    columns = st.columns(min(len(docs), 3))

    for index, (filename, document) in enumerate(docs):
        with columns[index % len(columns)]:
            st.markdown(
                f"""
                <div class="document-card">
                    <div class="document-icon">📄</div>
                    <div class="document-name">
                        {html.escape(filename)}
                    </div>
                    <div class="document-meta">
                        {document['pages']} pages ·
                        {len(document['chunks'])} chunks
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        '<div class="section-heading">Try asking</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="section-description">'
        'Start with one of these suggestions.'
        '</div>',
        unsafe_allow_html=True,
    )

    suggestions = [
        "Summarize the main points",
        "Find the key information",
        "Compare these documents",
    ]

    suggestion_columns = st.columns(3)

    for index, suggestion in enumerate(suggestions):
        with suggestion_columns[index]:
            if st.button(
                suggestion,
                key=f"suggestion_{index}",
                use_container_width=True,
            ):
                st.session_state.pending_question = suggestion
                st.rerun()


# =========================================================
# CHAT HISTORY
# =========================================================

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        if message["role"] == "assistant" and message.get("sources"):
            with st.expander("View source passages"):
                for chunk in message["sources"]:
                    st.markdown(
                        f"**{chunk.get('source', 'Unknown PDF')}** "
                        f"· Page {chunk.get('page', '?')}"
                    )
                    st.write(chunk.get("text", ""))
                    st.divider()


# =========================================================
# CHAT INPUT
# =========================================================

typed_question = st.chat_input(
    "Ask anything about your PDFs...",
    disabled=not bool(st.session_state.documents),
)

question = typed_question

if not question and st.session_state.pending_question:
    question = st.session_state.pending_question
    st.session_state.pending_question = None


# =========================================================
# ANSWER GENERATION
# =========================================================

if question and st.session_state.documents:
    st.session_state.messages.append({
        "role": "user",
        "content": question,
    })

    with st.chat_message("user"):
        st.markdown(question)

    answer = ""
    chunks = []

    with st.chat_message("assistant"):
        try:
            # Initialize the answerer only when an answer is needed.
            answerer = load_answerer()

            # ---------------------------------------------
            # MODE 1: COMPLETE ASSIGNMENT EXTRACTION
            # ---------------------------------------------

            if is_complete_extraction_request(question):
                selected = find_assignment_document(
                    question,
                    st.session_state.documents,
                )

                if selected is None:
                    answer = (
                        "I couldn't identify a suitable assignment "
                        "document among the uploaded PDFs."
                    )
                else:
                    target_name, target_document = selected
                    chunks = target_document["full_pages"]

                    extraction_question = f"""
The user asks: {question}

Extract every identifiable assignment question from the supplied
document. Preserve original order and wording as closely as possible.
Include subquestions, numbered parts, and questions continuing across
page boundaries. Do not summarize or invent missing questions.

Source document: {target_name}
"""

                    with st.spinner(
                        f"Extracting questions from {target_name}..."
                    ):
                        answer = answerer.answer(
                            extraction_question,
                            chunks,
                        )

                    st.caption(f"Source document: {target_name}")

            # ---------------------------------------------
            # MODE 2: CROSS-DOCUMENT COMPARISON
            # ---------------------------------------------

            elif (
                is_comparison_request(question)
                and len(st.session_state.documents) >= 2
            ):
                with st.spinner(
                    "Finding relevant passages across your PDFs..."
                ):
                    chunks = search_each_document(
                        question,
                        st.session_state.documents,
                        top_k_per_document=3,
                    )

                if not chunks:
                    answer = (
                        "I couldn't find relevant text in the "
                        "processed PDFs."
                    )
                else:
                    document_names = list(
                        st.session_state.documents.keys()
                    )

                    comparison_question = f"""
User request:
{question}

Documents uploaded:
{chr(10).join("- " + name for name in document_names)}

Compare the supplied PDF excerpts.

Requirements:
- Identify documents by their exact filenames.
- Explain the main difference first.
- Compare purpose, subject, key content, structure, and intended use
  when supported by the excerpts.
- Use a readable Markdown comparison table where useful.
- Include similarities only when supported by the text.
- Attribute information to the correct document.
- Do not invent facts or assume omitted information is absent.
- If the excerpts do not support a comparison point, say so.
- Give a complete, readable response.
"""

                    with st.spinner("Preparing your comparison..."):
                        answer = answerer.answer(
                            comparison_question,
                            chunks,
                        )

            # ---------------------------------------------
            # MODE 3: NORMAL DOCUMENT SEARCH
            # ---------------------------------------------

            else:
                with st.spinner("Searching your documents..."):
                    chunks = search_documents(
                        question,
                        st.session_state.documents,
                        top_k=5,
                    )

                if not chunks:
                    answer = (
                        "I couldn't find relevant text in your "
                        "processed PDFs."
                    )
                else:
                    with st.spinner("Generating your answer..."):
                        answer = answerer.answer(question, chunks)

            st.markdown(
                '<div class="answer-eyebrow">✦ FINDPDF ANSWER</div>',
                unsafe_allow_html=True,
            )

            st.markdown(answer)

            if chunks:
                with st.expander("View source passages"):
                    for chunk in chunks:
                        st.markdown(
                            f"**{chunk.get('source', 'Unknown PDF')}** "
                            f"· Page {chunk.get('page', '?')}"
                        )
                        st.write(chunk.get("text", ""))
                        st.divider()

        except Exception as error:
            error_message = str(error)
            error_lower = error_message.lower()

            if (
                "429" in error_message
                or "resource_exhausted" in error_lower
                or "quota" in error_lower
            ):
                answer = (
                    "The Gemini API quota has been reached. "
                    "Your processed PDFs are still available, but "
                    "AI-generated answers are temporarily unavailable. "
                    "Please wait for your quota to reset."
                )

            elif (
                "503" in error_message
                or "unavailable" in error_lower
            ):
                answer = (
                    "The AI service is temporarily unavailable. "
                    "Please try again later."
                )

            else:
                answer = (
                    "Something went wrong while processing your "
                    f"request.\n\nDetails: {error_message}"
                )

            st.warning(answer)

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "sources": chunks,
    })


# =========================================================
# FOOTER
# =========================================================

st.markdown(
    """
    <div class="footer">
        <span style="color:#5eead4;font-weight:700;">FindPDF</span>
        &nbsp;·&nbsp; Built for clearer document discovery
    </div>
    """,
    unsafe_allow_html=True,
)
