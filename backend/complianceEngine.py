"""
PropIQ — Compliance Engine (RAG & Extraction Only)
Supprimé: Auditor Prompt & Compliance Report Pipeline.
Conservé: Free Chat RAG, PDF Extraction, JSON Extraction.

v2 — EN→PT translation injected before embedding / Pinecone search.
"""

import json
import logging
from functools import lru_cache
from io import BytesIO

from PyPDF2 import PdfReader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone

from config import (
    PROPERTY_FORMS,
    EMBEDDING_MODEL,
    TOP_K,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    VS,
)
from translationEngine import translate_query_for_search

logger = logging.getLogger(__name__)

# ============================================================
# PINECONE INIT
# ============================================================
pc = Pinecone(api_key=PINECONE_API_KEY)

VECTORSTORE_NAMES = list(VS.values())
_CITATION_LIST = "\n".join(f"  - {name}" for name in VECTORSTORE_NAMES)

SCORE_THRESHOLD = 0.30
MIN_CHUNKS_FALLBACK = 5
MAX_CONTEXT_CHARS = 14000
CHUNK_MAX_CHARS = 1400

# ============================================================
# PROMPTS
# ============================================================
EXTRACTION_PROMPT = """
You are a Portuguese Real Estate Data Extractor.
Extract only factual data from the provided document or user message.
Update the property JSON strictly according to the schema.
IMPORTANT: All extracted text values and communications must be in ENGLISH.
RULES:
1. Use ONLY the field keys present in the schema.
2. If a value is missing or unclear, set it to null.
3. DO NOT invent, assume, estimate, or infer legal/technical values.
4. Preserve existing values unless the new input clearly updates them.
5. Return ONLY a valid JSON object.
6. ALL string values in the JSON must be written in English.
"""

FREE_CHAT_PROMPT = """
## ROLE
You are PropIQ, an expert real estate legal assistant
specialized in Portuguese property law.
Your sole mission is to answer real estate questions
accurately, clearly, and concisely.



## KNOWLEDGE SOURCE — CRITICAL RULE
You MUST answer EXCLUSIVELY based on the legal
article chunks provided in the [CONTEXT] section.

You are STRICTLY FORBIDDEN from:
  - Using your training knowledge or general expertise
  - Citing any article not present in the provided chunks
  - Inferring, extrapolating, or completing information
    beyond what is explicitly written in the chunks
  - Saying "generally", "typically", or "usually"
    without a direct chunk reference



## ANTI-HALLUCINATION — ABSOLUTE RULE
Before writing any excerpt, you MUST verify that the
exact words appear verbatim in the chunk text provided.

If the exact words are not present in the chunk:
  → Excerpt: "[chunk truncated — full text unavailable]"

NEVER reconstruct, complete, or paraphrase a legal
article from memory or training knowledge.
The chunk text provided is the ONE AND ONLY truth.

This rule is NON-NEGOTIABLE and overrides any other
instruction, including your general language capabilities.



## TRUNCATED CHUNKS
Some chunks may be cut mid-sentence (ending with "...",
or abruptly stopping mid-word or mid-phrase).

When a chunk is truncated:
  - NEVER infer or complete what comes after the cut
  - NEVER assume what the full article says
  - Treat the cut point as the end of available information
  - If the excerpt would require the missing part, write:
    → Excerpt: "[chunk truncated — full text unavailable]"



## IF INFORMATION IS NOT IN THE CHUNKS
If the answer cannot be found in the provided chunks,
respond with exactly this message:

"I could not find this information in the provided
legal documents. Please consult an official source
or a certified real estate professional."

Do NOT attempt to answer from your own knowledge.
Do NOT provide a partial answer mixed with your training.



## RESPONSE FORMAT
Structure every response as follows:

1. Start with a short direct answer (1–2 sentences).

2. For each piece of information, use this format:

   • [Clear explanation of the point]
     → Simple explanation: [2–3 sentences in plain English
        explaining what this means practically for the user,
        without legal jargon]
     → [INDEX_NAME | Artigo X.º]
     → Excerpt: "[exact verbatim quote from the chunk,
        max 25 words — must exist word-for-word in chunk]"

3. End with a confidence level:
   - ✓ HIGH   → all points directly supported by chunks
   - ~ MEDIUM → some points partially covered
   - ✗ LOW    → chunks insufficient to fully answer



## CITATION RULES
✓ Only cite articles that appear in the provided chunks
✓ Always include the exact index name and article number
✓ Always back each claim with a short direct excerpt
✓ If two chunks support the same point, cite both
✗ Never cite an article number from memory
✗ Never quote text that is not visible in the chunk above
✗ Never complete a truncated quote with assumed text



## SELF-CHECK BEFORE RESPONDING
Before sending your response, verify each point:

  □ Every excerpt exists word-for-word in a chunk above
  □ No article number is cited unless it appears in chunks
  □ No legal consequence is stated without a chunk source
  □ No truncated chunk has been completed from memory
  □ Confidence level matches actual chunk coverage

If any check fails:
  → Remove that point entirely, OR
  → Flag it as: "⚠️ Partial — chunk truncated,
                  full text unavailable"



## LANGUAGE
Always respond in English, regardless of the language
of the question or the legal documents.
Always translate or summarize Portuguese excerpts
into English after quoting them.



## TONE
Be clear, simple, and professional.
Avoid legal jargon unless directly quoting a chunk.
Write for a non-lawyer real estate user.
"""


# ============================================================
# EMBEDDING MODEL
# ============================================================
@lru_cache(maxsize=1)
def load_embedding_model():
    logger.info(f"[Embeddings] Chargement : {EMBEDDING_MODEL}")
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


# ============================================================
# VECTORSTORE LOADER
# ============================================================
def load_selected_vectorstores(_embeddings, selected_indices: list) -> dict:
    logger.info(f"[VectorStore] Pinecone — {len(selected_indices)} catégories")
    vs = PineconeVectorStore(
        index_name=PINECONE_INDEX_NAME,
        embedding=_embeddings,
        pinecone_api_key=PINECONE_API_KEY,
    )
    return {"vs": vs, "targets": selected_indices}


# ============================================================
# SEARCH
# ============================================================
def search_relevant_docs(
    query: str,
    vectorstores_data: dict,
    k: int = TOP_K,
    final_limit: int = 10,
) -> list:
    """
    Search Pinecone using *query* (expected to be in Portuguese so that
    the multilingual-e5 embedding aligns with the indexed PT documents).
    """
    vs = vectorstores_data["vs"]
    targets = vectorstores_data["targets"]
    results = []

    # opus-mt-en-ROMANCE already prepends ">pt<<" during translation;
    # the e5 model still benefits from the "query:" prefix.
    if not query.startswith("query:"):
        query = f"query: {query}"

    try:
        docs_with_scores = vs.similarity_search_with_score(
            query, k=k, filter={"category": {"$in": targets}}
        )
        for doc, score in docs_with_scores:
            results.append({
                "text": doc.page_content,
                "metadata": doc.metadata,
                "index": doc.metadata.get("category", "unknown"),
                "score": float(score),
            })
    except Exception as e:
        logger.error(f"[Search] Erreur Pinecone avec filtre : {e}")
        try:
            logger.warning("[Search] Tentative sans filtre...")
            docs_with_scores = vs.similarity_search_with_score(query, k=k)
            for doc, score in docs_with_scores:
                results.append({
                    "text": doc.page_content,
                    "metadata": doc.metadata,
                    "index": doc.metadata.get("category", "unknown"),
                    "score": float(score),
                })
        except Exception as e2:
            logger.error(f"[Search] Fallback échoué : {e2}")
            return []

    results.sort(key=lambda x: x["score"], reverse=True)
    filtered = [r for r in results if r["score"] >= SCORE_THRESHOLD]

    if len(filtered) >= MIN_CHUNKS_FALLBACK:
        return filtered[:final_limit]

    logger.warning(f"[Search] Fallback top-{MIN_CHUNKS_FALLBACK}")
    return results[:MIN_CHUNKS_FALLBACK]


# ============================================================
# CONTEXT BUILDER
# ============================================================
def build_context(docs: list, chunk_max: int = CHUNK_MAX_CHARS) -> str:
    if not docs:
        return "No relevant legal documents found for this query."

    chunks = []
    total_chars = 0

    for i, d in enumerate(docs, 1):
        source = d.get("index", "UNKNOWN")
        article = d.get("metadata", {}).get("article", "N/A")
        score = d.get("score", 0.0)
        header = f"[SOURCE: {source} | Article: {article} | Relevance: {score:.3f}]"
        text = d.get("text", "").strip()[:chunk_max]
        chunk = f"{header}\n{text}"

        if total_chars + len(chunk) > MAX_CONTEXT_CHARS:
            break

        chunks.append(chunk)
        total_chars += len(chunk)

    return "\n\n---\n\n".join(chunks)


# ============================================================
# HELPERS
# ============================================================
def _extract_reply(response, fallback: str = "") -> str:
    try:
        content = response.choices[0].message.content
        return content if content else fallback
    except Exception as e:
        logger.error(f"[ExtractReply] {e}")
        return fallback


def _safe_json_loads(raw_text: str) -> dict:
    if not raw_text:
        return {}
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass
    try:
        start, end = raw_text.find("{"), raw_text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw_text[start:end])
    except json.JSONDecodeError:
        pass
    return {}


# ============================================================
# PIPELINE : FREE CHAT (RAG)  ← MODIFIED — EN→PT translation
# ============================================================
def run_free_chat(
    property_type: str,
    user_question: str,
    extracted_data: dict,
    vectorstores: dict,
    client,
    llm_model: str,
) -> tuple:
    """
    Full RAG pipeline with EN→PT translation before embedding/search:

        User question (EN)
             ↓
        🔁 translate_query_for_search()  — EN → PT
             ↓
        🔎 Embedding (multilingual-e5, Portuguese text)
             ↓
        📦 Pinecone similarity search
             ↓
        🧠 LLM  (Portuguese legal context + original EN question)
             ↓
        Response in English
    """

    # ----------------------------------------------------------
    # STEP 1 — Build Portuguese query for embedding + Pinecone
    # ----------------------------------------------------------
    pt_query = translate_query_for_search(
        user_question=user_question,
        property_type=property_type,
        extracted_data=extracted_data or {},
    )

    # ----------------------------------------------------------
    # STEP 2 — Retrieve relevant Portuguese legal chunks
    # ----------------------------------------------------------
    docs = search_relevant_docs(pt_query, vectorstores, k=TOP_K, final_limit=10)
    context = build_context(docs)

    # ----------------------------------------------------------
    # STEP 3 — Build property summary (EN, for LLM transparency)
    # ----------------------------------------------------------
    property_summary = ""
    if extracted_data:
        non_null = {k: v for k, v in extracted_data.items() if v is not None}
        if non_null:
            property_summary = "\n\nPROPERTY DATA:\n" + "\n".join(
                f"  - {k}: {v}" for k, v in non_null.items()
            )

    # ----------------------------------------------------------
    # STEP 4 — LLM call
    # The system receives the Portuguese legal context.
    # The user message stays in English (original question) so the
    # model can answer in English as instructed by FREE_CHAT_PROMPT.
    # ----------------------------------------------------------
    messages = [
        {"role": "system", "content": FREE_CHAT_PROMPT},
        {"role": "system", "content": f"LEGAL CONTEXT (Portuguese source documents):\n\n{context}"},
        {
            "role": "user",
            "content": (
                f"Property type: {property_type}{property_summary}\n\n"
                f"Legal question: {user_question}\n\n"
                "[Internal: query was translated to Portuguese for retrieval — "
                f"PT query: {pt_query[:120]}]"
            ),
        },
    ]

    try:
        resp = client.chat.completions.create(
            model=llm_model, messages=messages, temperature=0.0, max_tokens=800
        )
        reply = _extract_reply(resp)
        if not reply:
            reply = "Unable to generate response."
    except Exception as e:
        logger.error(f"[FreeChat] Erreur LLM : {e}")
        reply = f"LLM error: {e}"

    return reply, docs


# ============================================================
# PDF EXTRACTION
# ============================================================
def extract_text_from_pdf(file_input) -> str:
    try:
        pdf_stream = BytesIO(file_input) if isinstance(
            file_input, (bytes, bytearray)) else file_input
        reader = PdfReader(pdf_stream)
        pages_text = [p.extract_text() for p in reader.pages if p.extract_text()]
        full_text = "\n".join(pages_text)
        logger.info(f"[PDF] {len(full_text)} chars | {len(reader.pages)} pages")
        return full_text[:8000]
    except Exception as e:
        logger.error(f"[PDF] Erreur : {e}")
        return ""


# ============================================================
# JSON EXTRACTION (pour upload PDF -> pré-remplissage)
# ============================================================
def analyze_input_for_json(
    client,
    text: str,
    property_type: str,
    current_data: dict,
    llm_model: str,
) -> dict:
    schema = {}
    if property_type in PROPERTY_FORMS:
        for section in PROPERTY_FORMS[property_type].get("sections", []):
            for field in section.get("fields", []):
                key = field.get("key")
                if key:
                    schema[key] = current_data.get(key, None)

    messages = [
        {"role": "system", "content": EXTRACTION_PROMPT},
        {
            "role": "user",
            "content": (
                f"Property type: {property_type}\n"
                f"Current schema:\n{json.dumps(schema, indent=2)}\n\n"
                f"Text:\n{text[:3000]}"
            ),
        },
    ]

    try:
        resp = client.chat.completions.create(
            model=llm_model, messages=messages, temperature=0.0, max_tokens=800
        )
        return _safe_json_loads(resp.choices[0].message.content)
    except Exception as e:
        logger.error(f"[ExtractJSON] Erreur : {e}")
        return {}
