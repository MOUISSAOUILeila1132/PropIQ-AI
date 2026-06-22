"""
PropIQ — Voice Engine
Audio (WAV/MP3/WebM/OGG/M4A/FLAC) → Whisper transcription → EN text
→ Pipeline RAG existant (translate_query_for_search → Pinecone → LLM)

Whisper est chargé une seule fois via lru_cache (zéro overhead).
Compatible avec le modèle Whisper déjà installé localement.
"""

import logging
import tempfile
import os
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================
WHISPER_MODEL_SIZE = "base"          # tiny | base | small | medium | large
SUPPORTED_FORMATS = {".wav", ".mp3", ".webm", ".ogg", ".m4a", ".flac", ".mp4", ".aac"}
MAX_AUDIO_BYTES = 25 * 1024 * 1024   # 25 MB


# ============================================================
# LAZY MODEL LOADER  (cpu, lru_cache)
# ============================================================
@lru_cache(maxsize=1)
def _load_whisper_model():
    """
    Charge le modèle Whisper une seule fois et le met en cache.
    Utilise openai-whisper installé localement.
    Lève RuntimeError si whisper n'est pas installé.
    """
    try:
        import whisper
        logger.info(f"[Voice] Loading Whisper model: {WHISPER_MODEL_SIZE}")
        model = whisper.load_model(WHISPER_MODEL_SIZE)
        logger.info(f"[Voice] ✅ Whisper '{WHISPER_MODEL_SIZE}' ready.")
        return model
    except ImportError:
        raise RuntimeError(
            "\n" + "=" * 60 + "\n"
            "[Voice] ❌ Le package 'openai-whisper' n'est pas installé !\n\n"
            "Installez-le avec :\n"
            "  pip install openai-whisper\n"
            "  pip install ffmpeg-python\n"
            "Et assurez-vous que ffmpeg est accessible dans le PATH.\n"
            + "=" * 60
        )
    except Exception as e:
        raise RuntimeError(
            f"[Voice] ❌ Impossible de charger Whisper : {e}"
        ) from e


# ============================================================
# TRANSCRIPTION
# ============================================================
def transcribe_audio(audio_bytes: bytes, filename: str = "audio.wav") -> dict:
    """
    Transcrit un fichier audio en texte via Whisper.

    Args:
        audio_bytes : contenu brut du fichier audio (bytes)
        filename    : nom original du fichier (pour détecter l'extension)

    Returns:
        {
            "text"     : str  — transcription complète,
            "language" : str  — langue détectée (ex: "en", "fr", "pt"),
            "segments" : list — segments horodatés,
            "success"  : bool,
            "error"    : str | None,
        }
    """
    # ── Validation taille ────────────────────────────────────
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        return {
            "text": "", "language": "", "segments": [],
            "success": False,
            "error": (
                f"File too large ({len(audio_bytes) // 1024 // 1024} MB). "
                f"Max: 25 MB."
            ),
        }

    # ── Validation extension ─────────────────────────────────
    ext = Path(filename).suffix.lower()
    if not ext:
        ext = ".wav"   # fallback si le nom est vide
    if ext not in SUPPORTED_FORMATS:
        return {
            "text": "", "language": "", "segments": [],
            "success": False,
            "error": (
                f"Unsupported format: '{ext}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_FORMATS))}"
            ),
        }

    # ── Écriture dans fichier temporaire ─────────────────────
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=ext, delete=False, prefix="propiq_voice_"
        ) as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_path = tmp_file.name

        logger.info(
            f"[Voice] Transcribing {len(audio_bytes) // 1024} KB "
            f"| format={ext} | tmp={tmp_path}"
        )

        # ── Whisper transcription ─────────────────────────────
        model = _load_whisper_model()
        result = model.transcribe(
            tmp_path,
            task="transcribe",   # garde la langue d'origine
            fp16=False,          # CPU-safe
            verbose=False,
        )

        text = result.get("text", "").strip()
        language = result.get("language", "unknown")
        segments = result.get("segments", [])

        logger.info(
            f"[Voice] ✅ Transcription done | lang={language} | "
            f"chars={len(text)} | preview={text[:80]!r}"
        )

        # ── Debug terminal ────────────────────────────────────
        print("\n" + "─" * 60)
        print("🎙️  VOICE TRANSCRIPTION DEBUG")
        print("─" * 60)
        print(f"  📁 Format   : {ext}")
        print(f"  🌍 Language : {language}")
        print(f"  📝 Text     : {text}")
        print("─" * 60 + "\n")

        return {
            "text": text,
            "language": language,
            "segments": segments,
            "success": True,
            "error": None,
        }

    except Exception as e:
        logger.error(f"[Voice] Transcription failed: {e}")
        return {
            "text": "", "language": "", "segments": [],
            "success": False,
            "error": str(e),
        }

    finally:
        # ── Nettoyage fichier temporaire ──────────────────────
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# ============================================================
# VOICE → RAG PIPELINE  (point d'entrée principal)
# ============================================================
def run_voice_chat(
    audio_bytes: bytes,
    filename: str,
    property_type: str,
    extracted_data: dict,
    vectorstores: dict,
    client,
    llm_model: str,
) -> dict:
    """
    Pipeline complet Voice → RAG :

        🎙️  Audio (bytes)
              ↓
        📝  Whisper transcription  (langue détectée automatiquement)
              ↓
        🔁  translate_query_for_search()  [translationEngine] — EN → PT
              ↓
        🔎  Embedding multilingual-e5 + Pinecone  [complianceEngine]
              ↓
        🧠  LLM via OpenRouter  (contexte légal PT + question originale)
              ↓
        ✅  Réponse en anglais

    Returns:
        {
            "reply"         : str   — réponse LLM en anglais,
            "transcription" : str   — texte transcrit par Whisper,
            "detected_lang" : str   — langue détectée ("en", "fr", "pt"...),
            "sources"       : list  — docs RAG bruts (à normaliser),
            "success"       : bool,
            "error"         : str | None,
        }
    """
    # ── ÉTAPE 1 : Transcription Whisper ──────────────────────
    transcription_result = transcribe_audio(audio_bytes, filename)

    if not transcription_result["success"]:
        return {
            "reply": "",
            "transcription": "",
            "detected_lang": "",
            "sources": [],
            "success": False,
            "error": f"Transcription failed: {transcription_result['error']}",
        }

    transcribed_text = transcription_result["text"]
    detected_lang = transcription_result["language"]

    if not transcribed_text.strip():
        return {
            "reply": "",
            "transcription": "",
            "detected_lang": detected_lang,
            "sources": [],
            "success": False,
            "error": (
                "Transcription returned empty text. "
                "Please speak clearly and try again."
            ),
        }

    # ── ÉTAPE 2 : Pipeline RAG ────────────────────────────────
    # run_free_chat gère déjà EN→PT (translationEngine) + Pinecone + LLM
    from complianceEngine import run_free_chat

    logger.info(
        f"[Voice] Routing to RAG pipeline | "
        f"lang={detected_lang} | question={transcribed_text[:80]!r}"
    )

    try:
        reply, docs = run_free_chat(
            property_type=property_type,
            user_question=transcribed_text,
            extracted_data=extracted_data or {},
            vectorstores=vectorstores,
            client=client,
            llm_model=llm_model,
        )
    except Exception as e:
        logger.error(f"[Voice] RAG pipeline failed: {e}")
        return {
            "reply": "",
            "transcription": transcribed_text,
            "detected_lang": detected_lang,
            "sources": [],
            "success": False,
            "error": f"RAG pipeline error: {e}",
        }

    return {
        "reply": reply,
        "transcription": transcribed_text,
        "detected_lang": detected_lang,
        "sources": docs,
        "success": True,
        "error": None,
    }
