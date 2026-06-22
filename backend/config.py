"""
PropTech AI — Shared Configuration
Utilisation exclusive d'OpenRouter API (pas de LLM local).
Modèle d'embeddings chargé depuis le cache local (mode offline).
v2 — Ajout du modèle de traduction Helsinki-NLP/opus-mt-en-ROMANCE.
v3 — Ajout Firebase Admin SDK pour l'authentification mobile Flutter.
v4 — Ajout système de paiement Konnect (Tunisie/Test) + Stripe (Portugal/Production).
"""


from firebase_admin import credentials
import firebase_admin
import firebase_admin.auth as firebase_auth
import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# MODE OFFLINE — Forcer le chargement depuis le cache local
# ============================================================
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ============================================================
# MLFLOW SETTINGS
# ============================================================
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
MLFLOW_TRACKING_UI_URL = os.getenv("MLFLOW_TRACKING_UI_URL", "http://127.0.0.1:5000")

# ============================================================
# OPENROUTER / LLM SETTINGS
# ============================================================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "mistralai/mistral-large-2512")

# ============================================================
# PINECONE CONFIG
# ============================================================
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "propiq-index")

# ============================================================
# FIREBASE ADMIN SDK — Authentication Flutter Mobile
# ============================================================


def _init_firebase() -> bool:
    """
    Initialise Firebase Admin SDK une seule fois (singleton).
    Priorité 1 : fichier JSON (FIREBASE_CREDENTIALS_PATH dans .env)
    Priorité 2 : JSON encodé directement (FIREBASE_CREDENTIALS_JSON dans .env)
    Retourne True si succès, False sinon.
    """
    # Évite la double initialisation si déjà fait
    if firebase_admin._apps:
        return True

    # --- Priorité 1 : fichier JSON de clé de service ---
    creds_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if creds_path and Path(creds_path).exists():
        try:
            cred = credentials.Certificate(creds_path)
            firebase_admin.initialize_app(cred)
            print(f"[Config] ✅ Firebase Admin SDK initialisé via fichier : {creds_path}")
            return True
        except Exception as e:
            print(f"[Config] ⚠️  Erreur Firebase (fichier) : {e}")

    # --- Priorité 2 : JSON inline dans .env ---
    creds_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
    if creds_json:
        try:
            cred_dict = json.loads(creds_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("[Config] ✅ Firebase Admin SDK initialisé via variable d'environnement JSON")
            return True
        except Exception as e:
            print(f"[Config] ⚠️  Erreur Firebase (JSON env) : {e}")

    # --- Aucune config trouvée ---
    print(
        "[Config] ❌ Firebase non initialisé !\n"
        "  → Vérifie FIREBASE_CREDENTIALS_PATH ou FIREBASE_CREDENTIALS_JSON dans ton .env\n"
        "  → Télécharge la clé depuis : Firebase Console > Paramètres > Comptes de service"
    )
    return False


FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
FIREBASE_INITIALIZED = _init_firebase()

# ============================================================
# PAYMENT — Provider configurable (switcher via .env)
# ============================================================
PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "konnect")

# --- Konnect (Tunisie — Test) ---
KONNECT_API_KEY = os.getenv("KONNECT_API_KEY")
KONNECT_WALLET_ID = os.getenv("KONNECT_WALLET_ID")
KONNECT_SUCCESS_URL = os.getenv("KONNECT_SUCCESS_URL", "http://localhost:14001/payment-success")
KONNECT_FAIL_URL = os.getenv("KONNECT_FAIL_URL", "http://localhost:14001/payment-fail")
KONNECT_WEBHOOK_URL = os.getenv("KONNECT_WEBHOOK_URL", "http://localhost:8000/api/payment/webhook")

# URLs Konnect API
KONNECT_API_BASE = "https://api.preprod.konnect.network/api/v2"   # preprod (test)

# --- Stripe (Portugal — Production) ---
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", "http://localhost:13809/#/success")
STRIPE_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", "http://localhost:13809/#/plan-selection")


def _log_payment_status():
    if PAYMENT_PROVIDER == "konnect":
        if KONNECT_API_KEY and KONNECT_WALLET_ID:
            print("[Config] ✅ Payment provider : Konnect (Test)")
        else:
            print("[Config] ⚠️  Konnect : KONNECT_API_KEY ou KONNECT_WALLET_ID manquant dans .env")
    elif PAYMENT_PROVIDER == "stripe":
        if STRIPE_SECRET_KEY:
            print("[Config] ✅ Payment provider : Stripe (Production)")
        else:
            print("[Config] ⚠️  Stripe : STRIPE_SECRET_KEY manquant dans .env")
    else:
        print(f"[Config] ⚠️  PAYMENT_PROVIDER inconnu : {PAYMENT_PROVIDER}")


_log_payment_status()

# ============================================================
# SUBSCRIPTION PLANS — Limites journalières
# ============================================================
PLANS = {
    "free": {
        "requests_per_day": int(os.getenv("FREE_REQUESTS_PER_DAY", 10)),
        "images_per_day": int(os.getenv("FREE_IMAGES_PER_DAY", 1)),
        "pdfs_per_day": int(os.getenv("FREE_PDFS_PER_DAY", 1)),
        "price": 0,
        "label": "Plan Gratuit",
    },
    "premium": {
        "requests_per_day": int(os.getenv("PREMIUM_REQUESTS_PER_DAY", 20)),
        "images_per_day": int(os.getenv("PREMIUM_IMAGES_PER_DAY", 10)),
        "pdfs_per_day": int(os.getenv("PREMIUM_PDFS_PER_DAY", 5)),
        "price": int(os.getenv("PREMIUM_PRICE_AMOUNT", 9900)),
        "currency": os.getenv("PREMIUM_PRICE_CURRENCY", "TND"),
        "label": "Plan Premium",
    },
}

print(
    "[Config] ✅ Plans chargés : "
    f"Free ({PLANS['free']['requests_per_day']} req/j) | "
    f"Premium ({PLANS['premium']['requests_per_day']} req/j — "
    f"{PLANS['premium']['price'] / 1000:.2f} {PLANS['premium']['currency']})"
)

# ============================================================
# FIRESTORE — Collections
# ============================================================
FIRESTORE_USERS_COLLECTION = "users"
FIRESTORE_USAGE_SUBCOLLECTION = "daily_usage"

# ============================================================
# EMBEDDING — Cache local obligatoire
# ============================================================
EMBEDDING_MODEL = "intfloat/multilingual-e5-base"
TOP_K = 15
VECTORSTORE_BASE = "./vector_stores"

_HF_CACHE_DIR = Path.home() / ".cache" / "huggingface" / "hub"

# ── Embedding model ──────────────────────────────────────────
_EMBED_CACHE = _HF_CACHE_DIR / "models--intfloat--multilingual-e5-base"
if not _EMBED_CACHE.exists():
    _EMBED_CACHE.mkdir(parents=True, exist_ok=True)

_embed_snapshots = sorted(
    (_EMBED_CACHE / "snapshots").glob("*"),
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)

EMBEDDING_MODEL_PATH = str(_embed_snapshots[0]) if _embed_snapshots else ""

# ── Translation model (Helsinki-NLP/opus-mt-en-ROMANCE) ──────
TRANSLATION_MODEL_EN_PT = "Helsinki-NLP/opus-mt-en-ROMANCE"
_TRANSLATION_CACHE = _HF_CACHE_DIR / "models--Helsinki-NLP--opus-mt-en-ROMANCE"

_translation_snapshots = sorted(
    (_TRANSLATION_CACHE / "snapshots").glob("*"),
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)

TRANSLATION_MODEL_PATH = str(_translation_snapshots[0]) if _translation_snapshots else ""

# ============================================================
# VECTORSTORE → LEGAL CATEGORY MAPPING (20 catégories)
# ============================================================
VS = {
    "ACCESSIBILITY": "LEIS_E_NORMAS_DE_ACESSIBILIDADE_PARA_EDIFÍCIOS_PÚBLICOS_E_PRIVADOS",
    "CIVIL_SALE": "CÓDIGO_CIVIL_GARANTIAS_DE_VENDA_CONSTRUÇÃO_IMOBILIÁRIA_PT",
    "CIVIL_FINANCIAL": "OBRIGAÇÕES_FINANCEIRAS_CIVIS_RELATIVAS_À_PROPRIEDADE_IMOBILIÁRIA_PT",
    "CIVIL_REGULATORY": "SERVIÇOS_REGULATÓRIOS_IMOBILIÁRIOS_CIVIS",
    "MAINTENANCE": "MANUTENÇÃO_CIVIL_DE_INFRAESTRUTURAS_IMOBILIÁRIAS",
    "MORTGAGES": "TRANSAÇÕES_HIPOTECÁRIAS_IMOBILIÁRIAS_CIVIS",
    "REG_SERVICES": "SERVIÇOS_IMOBILIÁRIOS_REGULAMENTAÇÃO_CIVIL_PROPRIEDADE_PT",
    "ENERGY": "CERTIFICAÇÃO_ENERGÉTICA_DESEMPENHO_DE_EDIFÍCIOS_SCE",
    "FIRE_LAWS": "LEIS_E_REGULAMENTAÇÕES_DE_SEGURANÇA_CONTRA_INCÊNDIOS_EM_EDIFÍCIOS_E_ESTABELECIMENTOS_PÚBLICOS",
    "FIRE_TECH": "REGULAMENTAÇÃO_TÉCNICA_DE_SEGURANÇA_CONTRA_INCÊNDIOS_PARA_INSTALAÇÕES_MÓVEIS_E_TEMPORÁRIAS_SCIE",
    "URBAN_ZONING": "PDM_SETÚBAL_PLANO_DIRECTOR_MUNICIPAL_DE_ORDENAMENTO_URBANO",
    "HOUSING_RENTAL": "LEI_DA_HABITAÇÃO_EM_PORTUGAL_ALUGUER_DE_IMÓVEIS_RESIDENCIAIS",
    "RGEU": "REGULAMENTO_GERAL_DAS_EDIFICAÇÕES_URBANAS_RGEU",
    "ELEC": "NORMAS_TÉCNICAS_DE_INSTALAÇÃO_ELÉTRICAS",
    "GAS": "NORMAS_TÉCNICAS_DE_INSTALAÇÃO_DE_GÁS",
    "TOURIST": "REGULAMENTAÇÃO_DO_ALOJAMENTO_LOCAL_TURÍSTICO",
    "URBANISM": "LEIS_E_REGULAMENTOS_DE_URBANISMO_E_USO_DO_SOL_IMOBILIÁRIO",
    "FINANCING": "CRÉDIT_IMOBILIER_FINANCEMENT_HYPOTHÉCAIRE",
    "SUCCESSION": "SUCESSÃO_E_HERANÇA_IMOBILIÁRIA",
}

PROPERTY_FORMS = {
    "residencial": {
        "label": "Residential Property",
        "icon": "🏠",
        "sections": [
            {
                "title": "📍 Basic Information",
                "vs_categories": [VS["URBAN_ZONING"], VS["RGEU"]],
                "fields": [
                    {
                        "key": "location",
                        "label": "City / Municipality",
                        "question": "In which city or municipality is the property located?",
                        "type": "text",
                        "required": True,
                        "vs_category": VS["URBAN_ZONING"]
                    },
                    {
                        "key": "address",
                        "label": "Exact address",
                        "question": "What is the exact address of the property?",
                        "type": "text",
                        "required": True,
                        "vs_category": VS["URBAN_ZONING"]
                    },
                    {
                        "key": "construction_year",
                        "label": "Year of construction",
                        "question": "What is the year of construction?",
                        "type": "number",
                        "required": True,
                        "vs_category": VS["RGEU"]
                    },
                    {
                        "key": "property_type",
                        "label": "Property type",
                        "question": "What type of property? (apartment, detached house, building)",
                        "type": "select",
                        "options": ["apartment", "detached house", "building"],
                        "required": True,
                        "vs_category": VS["RGEU"]
                    },
                ],
            },
            {
                "title": "📄 Legal & Urban Compliance",
                "vs_categories": [VS["URBANISM"], VS["RGEU"]],
                "fields": [
                    {
                        "key": "building_permit",
                        "label": "Building permit issued",
                        "question": "Does the property have a building permit?",
                        "type": "yesno",
                        "required": True,
                        "vs_category": VS["URBANISM"]
                    },
                    {
                        "key": "habitability_certificate",
                        "label": "Habitability / Use certificate",
                        "question": "Does the property have a habitability or use certificate?",
                        "type": "yesno",
                        "required": True,
                        "vs_category": VS["URBANISM"]
                    },
                ],
            },
        ],
    },

    "comercial": {
        "label": "Commercial Property",
        "icon": "🏢",
        "sections": [
            {
                "title": "📍 Basic Information",
                "vs_categories": [VS["URBAN_ZONING"], VS["CIVIL_REGULATORY"]],
                "fields": [
                    {
                        "key": "activity_type",
                        "label": "Type of commercial activity",
                        "question": "What type of activity? (retail, restaurant, office, etc.)",
                        "type": "text",
                        "required": True,
                        "vs_category": VS["CIVIL_REGULATORY"]
                    },
                    {
                        "key": "total_area",
                        "label": "Total area (m²)",
                        "question": "What is the total area?",
                        "type": "number",
                        "required": True,
                        "vs_category": VS["RGEU"]
                    },
                ],
            },
            {
                "title": "🔥 Safety & Accessibility",
                "vs_categories": [VS["FIRE_LAWS"], VS["ACCESSIBILITY"]],
                "fields": [
                    {
                        "key": "fire_regulations",
                        "label": "Fire safety complied",
                        "question": "Does it comply with fire safety?",
                        "type": "yesno",
                        "required": True,
                        "vs_category": VS["FIRE_LAWS"]
                    },
                    {
                        "key": "disabled_access",
                        "label": "Disabled access",
                        "question": "Is there disabled access?",
                        "type": "yesno",
                        "required": True,
                        "vs_category": VS["ACCESSIBILITY"]
                    },
                ],
            },
        ],
    },

    "terreno": {
        "label": "Land",
        "icon": "🏗️",
        "sections": [
            {
                "title": "📍 Basic Information",
                "vs_categories": [VS["URBAN_ZONING"], VS["URBANISM"]],
                "fields": [
                    {
                        "key": "location",
                        "label": "City / Municipality",
                        "question": "In which municipality is the land?",
                        "type": "text",
                        "required": True,
                        "vs_category": VS["URBAN_ZONING"]
                    },
                    {
                        "key": "land_type",
                        "label": "Land type",
                        "question": "Is it urban, agricultural, or forest land?",
                        "type": "select",
                        "options": ["urban", "agricultural", "forest", "mixed"],
                        "required": True,
                        "vs_category": VS["URBANISM"]
                    },
                ],
            },
            {
                "title": "📄 Restrictions",
                "vs_categories": [VS["URBAN_ZONING"], VS["MORTGAGES"]],
                "fields": [
                    {
                        "key": "ren_ran_applicable",
                        "label": "REN / RAN restrictions",
                        "question": "Is the land under REN or RAN restrictions?",
                        "type": "yesno",
                        "required": True,
                        "vs_category": VS["URBAN_ZONING"]
                    },
                    {
                        "key": "easements",
                        "label": "Easements / Rights of way",
                        "question": "Are there any easements?",
                        "type": "yesno",
                        "required": True,
                        "vs_category": VS["MORTGAGES"]
                    },
                ],
            },
        ],
    },

    "alojamento_local": {
        "label": "Tourist Rental (AL)",
        "icon": "🏨",
        "sections": [
            {
                "title": "📄 Registration",
                "vs_categories": [VS["TOURIST"], VS["URBAN_ZONING"]],
                "fields": [
                    {
                        "key": "authority_registration",
                        "label": "RNAL registration",
                        "question": "Has the RNAL registration been obtained?",
                        "type": "yesno",
                        "required": True,
                        "vs_category": VS["TOURIST"]
                    },
                    {
                        "key": "condo_rules_allow",
                        "label": "Condo allows AL",
                        "question": "Do the condominium rules allow tourist rental?",
                        "type": "yesno",
                        "required": True,
                        "vs_category": VS["TOURIST"]
                    },
                ],
            },
            {
                "title": "🛡️ Safety",
                "vs_categories": [VS["FIRE_LAWS"], VS["TOURIST"]],
                "fields": [
                    {
                        "key": "fire_extinguisher",
                        "label": "Fire extinguisher",
                        "question": "Is there a fire extinguisher installed?",
                        "type": "yesno",
                        "required": True,
                        "vs_category": VS["FIRE_LAWS"]
                    },
                    {
                        "key": "liability_insurance",
                        "label": "Liability insurance",
                        "question": "Is there valid liability insurance?",
                        "type": "yesno",
                        "required": True,
                        "vs_category": VS["TOURIST"]
                    },
                ],
            },
        ],
    },
}

PROPERTY_VS_TARGETS = {
    "residencial": [
        VS["RGEU"],
        VS["URBAN_ZONING"],
        VS["URBANISM"],
        VS["ELEC"],
        VS["ENERGY"],
        VS["HOUSING_RENTAL"],
        VS["MORTGAGES"],
        VS["CIVIL_FINANCIAL"],
        VS["MAINTENANCE"],
        VS["FINANCING"],
        VS["SUCCESSION"]],
    "comercial": [
        VS["REG_SERVICES"],
        VS["FIRE_LAWS"],
        VS["FIRE_TECH"],
        VS["ACCESSIBILITY"],
        VS["URBAN_ZONING"],
        VS["ELEC"],
        VS["CIVIL_REGULATORY"]],
    "terreno": [
        VS["URBAN_ZONING"],
        VS["URBANISM"],
        VS["MORTGAGES"],
        VS["MAINTENANCE"],
        VS["ELEC"],
        VS["FINANCING"],
        VS["SUCCESSION"]],
    "alojamento_local": [
        VS["TOURIST"],
        VS["URBANISM"],
        VS["ENERGY"],
        VS["ELEC"],
        VS["FIRE_LAWS"],
        VS["CIVIL_FINANCIAL"],
        VS["URBAN_ZONING"],
        VS["SUCCESSION"]],
}
