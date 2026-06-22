"""
PropIQ — Translation Engine
EN → PT (Portuguese) using Helsinki-NLP/opus-mt-en-ROMANCE (MarianMT)
Loaded once via lru_cache for zero-overhead reuse.
"""

import logging
import re
from functools import lru_cache

logger = logging.getLogger(__name__)

# ============================================================
# MODEL IDENTIFIERS
# ============================================================
# opus-mt-en-ROMANCE covers EN → pt (Portuguese) natively.
# Target prefix ">pt<" steers the decoder toward Portuguese.
EN_TO_PT_MODEL = "Helsinki-NLP/opus-mt-en-ROMANCE"
PT_TARGET_PREFIX = ">>pt<< "         # MarianMT language tag

MAX_INPUT_CHARS = 1024              # Hard cap before tokenisation
MAX_NEW_TOKENS = 512


# ============================================================
# LAZY MODEL LOADER  (cpu, offline-friendly)
# ============================================================
@lru_cache(maxsize=1)
def _load_en_pt_pipeline():
    """
    Charge le modèle MarianMT EN→ROMANCE une seule fois et le met en cache.
    Appel direct au modèle (sans pipeline) pour compatibilité toutes versions
    de transformers.
    Lève RuntimeError si le modèle n'est pas dans le cache HF.
    """
    try:
        from transformers import MarianMTModel, MarianTokenizer

        logger.info(f"[Translation] Loading model: {EN_TO_PT_MODEL}")
        tokenizer = MarianTokenizer.from_pretrained(EN_TO_PT_MODEL, revision="main")  # nosec B615
        model = MarianMTModel.from_pretrained(EN_TO_PT_MODEL, revision="main")  # nosec B615
        logger.info("[Translation] ✅ EN→PT model ready.")
        return model, tokenizer

    except OSError as e:
        raise RuntimeError(
            f"\n{'='*60}\n"
            f"[Translation] ❌ Model not found in cache!\n"
            f"Expected: {EN_TO_PT_MODEL}\n\n"
            f"Run ONCE to download:\n"
            "  python -c \"from transformers import MarianMTModel, MarianTokenizer; "
            f"MarianMTModel.from_pretrained('{EN_TO_PT_MODEL}', revision='main'); "
            f"MarianTokenizer.from_pretrained('{EN_TO_PT_MODEL}', revision='main')\"\n"
            f"{'='*60}"
        ) from e


# ============================================================
# PUBLIC API
# ============================================================
def translate_en_to_pt(text: str) -> str:
    """
    Traduit une chaîne anglaise vers le portugais.

    - Préfixe le tag de langue '>>pt<<' requis par opus-mt-en-ROMANCE.
    - Tronque l'entrée à MAX_INPUT_CHARS pour éviter un overflow du tokenizer.
    - Retourne le texte original en cas d'erreur (fallback gracieux).
    - Utilise model.generate() directement (compatible toutes versions transformers).
    """
    if not text or not text.strip():
        return text

    try:
        model, tokenizer = _load_en_pt_pipeline()

        # Troncature + tag de langue
        safe_text = text.strip()[:MAX_INPUT_CHARS]
        tagged_text = f"{PT_TARGET_PREFIX}{safe_text}"

        # Tokenisation + génération directe (sans pipeline)
        inputs = tokenizer([tagged_text], return_tensors="pt", truncation=True)
        outputs = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS)
        translated = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()

        # Supprimer le tag de langue si le modèle le répète en sortie
        translated = re.sub(r"^>>pt<<\s*", "", translated)

        logger.debug(f"[Translation] EN→PT | in={safe_text[:60]!r} | out={translated[:60]!r}")

        # ── Debug terminal ────────────────────────────────────
        print("\n" + "─" * 60)
        print("🔁  TRANSLATION DEBUG  EN → PT")
        print("─" * 60)
        print(f"  🇬🇧 EN : {safe_text}")
        print(f"  🇵🇹 PT : {translated}")
        print("─" * 60 + "\n")
        # ──────────────────────────────────────────────────────

        return translated

    except Exception as e:
        logger.error(f"[Translation] EN→PT failed, returning original. Error: {e}")
        return text          # Fallback gracieux — la recherche dégrade mais ne plante pas


def translate_query_for_search(
    user_question: str,
    property_type: str,
    extracted_data: dict | None = None,
) -> str:
    """
    Construit et traduit la requête enrichie qui sera embeddée
    et envoyée à Pinecone.

    Retourne une chaîne en portugais prête pour :
        embedding → similarity_search_with_score()
    """
    # Enrichissement identique à celui fait dans run_free_chat
    enriched = f"{user_question} {property_type}"
    if extracted_data:
        non_null = {k: v for k, v in extracted_data.items() if v is not None}
        if non_null:
            enriched += " " + " ".join(str(v) for v in non_null.values())

    pt_query = translate_en_to_pt(enriched)
    logger.info(
        f"[Translation] Query translated | "
        f"EN={enriched[:80]!r} → PT={pt_query[:80]!r}"
    )
    return pt_query
