"""
PropIQ — Ask Questions Module
Supporte : Free Chat (texte) + Voice Chat (audio → Whisper → RAG)
"""

import time
import logging
from complianceEngine import run_free_chat

logger = logging.getLogger(__name__)


# ============================================================
# API CHAT (Free Chat / RAG)
# ============================================================
def run_api_chat(
    property_type: str,
    user_msg: str,
    extracted_data: dict,
    vectorstores: dict,
    client,
    llm_model: str,
) -> tuple:
    if not user_msg or not user_msg.strip():
        return "Please provide a valid question.", []
    if not property_type:
        return "Property type is required.", []

    logger.info(f"[APIChat] type={property_type} | question={user_msg[:80]}...")

    try:
        reply, docs = run_free_chat(
            property_type=property_type,
            user_question=user_msg,
            extracted_data=extracted_data or {},
            vectorstores=vectorstores,
            client=client,
            llm_model=llm_model,
        )
        return reply, _normalize_sources(docs)
    except Exception as e:
        logger.error(f"[APIChat] Erreur : {e}")
        return f"An error occurred: {e}", []


# ============================================================
# VOICE CHAT  (Audio → Whisper → RAG)
# ============================================================
def run_api_voice_chat(
    property_type: str,
    audio_bytes: bytes,
    filename: str,
    extracted_data: dict,
    vectorstores: dict,
    client,
    llm_model: str,
) -> dict:
    """
    Pipeline vocal complet :

        🎙️  Audio bytes
              ↓
        📝  Whisper  (transcription, langue auto-détectée)
              ↓
        🔁  EN → PT  (translationEngine — interne à run_free_chat)
              ↓
        🔎  Embedding + Pinecone  (complianceEngine)
              ↓
        🧠  LLM
              ↓
        ✅  Réponse EN + transcription + sources normalisées

    Returns dict avec clés :
        reply, transcription, detected_lang, sources, success, error
    """
    if not audio_bytes:
        return {
            "reply": "No audio data received.",
            "transcription": "",
            "detected_lang": "",
            "sources": [],
            "success": False,
            "error": "Empty audio payload.",
        }
    if not property_type:
        return {
            "reply": "Property type is required.",
            "transcription": "",
            "detected_lang": "",
            "sources": [],
            "success": False,
            "error": "Missing property_type.",
        }

    logger.info(
        f"[VoiceChat] type={property_type} | file={filename} "
        f"| size={len(audio_bytes) // 1024} KB"
    )

    from voiceEngine import run_voice_chat

    result = run_voice_chat(
        audio_bytes=audio_bytes,
        filename=filename,
        property_type=property_type,
        extracted_data=extracted_data or {},
        vectorstores=vectorstores,
        client=client,
        llm_model=llm_model,
    )

    # Normaliser les sources si le pipeline a réussi
    if result["success"] and result.get("sources"):
        result["sources"] = _normalize_sources(result["sources"])

    return result


# ============================================================
# SOURCE NORMALIZER
# ============================================================
def _normalize_sources(docs: list) -> list:
    if not docs:
        return []
    normalized = []
    for doc in docs:
        score = doc.get("score", 0.0)
        normalized.append({
            "content": doc.get("text", "")[:500],
            "metadata": doc.get("metadata", {}),
            "index": doc.get("index", ""),
            "score": round(float(score), 4),
            "relevance": round(float(score), 4),
            "article": doc.get("metadata", {}).get("article", "N/A"),
        })
    normalized.sort(key=lambda x: x["score"], reverse=True)
    return normalized


# ============================================================
# STREAMLIT UI  (Free Chat + Voice Interface)
# ============================================================
def render_chat_ui(vectorstores, client, llm_model):
    try:
        import streamlit as st
    except ImportError:
        logger.error("[ChatUI] Streamlit non disponible")
        return

    st.markdown(
        '<div class="chat-title-main">💬 Smart Legal Assistant</div>',
        unsafe_allow_html=True,
    )
    property_type = st.session_state.get("property_type", "residencial")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # ── Affichage de l'historique ─────────────────────────────
    for turn in st.session_state.chat_history:
        with st.chat_message("user"):
            if turn.get("input_mode") == "voice":
                lang = turn.get("detected_lang", "?")
                st.markdown(f"🎙️ *Voice ({lang}):* {turn.get('user', '')}")
            else:
                st.markdown(turn.get("user", ""))
        with st.chat_message("assistant"):
            st.write(turn.get("assistant", ""))
        sources = turn.get("sources", [])
        if sources:
            with st.expander(f"📚 {len(sources)} source(s)"):
                for src in sources[:5]:
                    st.caption(
                        f"**{src.get('index', 'N/A')}** | "
                        f"Article: {src.get('article', 'N/A')} | "
                        f"Score: {src.get('score', 0):.3f}"
                    )

    # ── Sélecteur de mode ────────────────────────────────────
    input_mode = st.radio(
        "Input mode", ["✍️ Text", "🎙️ Voice"], horizontal=True
    )

    # ── Mode texte ───────────────────────────────────────────
    if input_mode == "✍️ Text":
        user_msg = st.chat_input("Ask a legal question about your property...")
        if user_msg:
            with st.spinner("🔍 Analyzing legal documents..."):
                t_start = time.time()
                reply, docs = run_free_chat(
                    property_type=property_type,
                    user_question=user_msg,
                    extracted_data=st.session_state.get("extracted_data", {}),
                    vectorstores=vectorstores,
                    client=client,
                    llm_model=llm_model,
                )
                latency_ms = round((time.time() - t_start) * 1000)
                sources = _normalize_sources(docs)

            st.session_state.chat_history.append({
                "user": user_msg,
                "assistant": reply,
                "sources": sources,
                "latency_ms": latency_ms,
                "input_mode": "text",
            })
            logger.info(f"[ChatUI/Text] {latency_ms}ms | {len(sources)} sources")
            st.rerun()

    # ── Mode vocal ───────────────────────────────────────────
    else:
        st.info(
            "🎙️ Record your question. Whisper will transcribe it automatically, "
            "then the RAG pipeline will answer in English."
        )
        audio_file = st.audio_input("Record your legal question")

        if audio_file is not None:
            st.audio(audio_file, format="audio/wav")
            if st.button("🚀 Send Voice Message", type="primary"):
                with st.spinner("🎙️ Transcribing + analyzing legal documents..."):
                    t_start = time.time()
                    result = run_api_voice_chat(
                        property_type=property_type,
                        audio_bytes=audio_file.read(),
                        filename=getattr(audio_file, "name", "audio.wav"),
                        extracted_data=st.session_state.get("extracted_data", {}),
                        vectorstores=vectorstores,
                        client=client,
                        llm_model=llm_model,
                    )
                    latency_ms = round((time.time() - t_start) * 1000)

                if result["success"]:
                    transcription = result["transcription"]
                    reply = result["reply"]
                    sources = result.get("sources", [])
                    detected_lang = result.get("detected_lang", "?")

                    st.success(
                        f"🎙️ **Transcription** *(lang detected: {detected_lang})*:\n\n"
                        f"> {transcription}"
                    )
                    st.session_state.chat_history.append({
                        "user": transcription,
                        "assistant": reply,
                        "sources": sources,
                        "latency_ms": latency_ms,
                        "input_mode": "voice",
                        "detected_lang": detected_lang,
                    })
                    logger.info(
                        f"[ChatUI/Voice] {latency_ms}ms | "
                        f"lang={detected_lang} | {len(sources)} sources"
                    )
                else:
                    st.error(f"❌ Voice error: {result['error']}")

                st.rerun()
