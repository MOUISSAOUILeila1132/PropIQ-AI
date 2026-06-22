"""
PropIQ — FastAPI Backend
Évaluation : manuelle (humaine) + automatique RAG (MLflow).
Quality of Life API intégrée.
Crédits : système de limitation quotidienne par utilisateur / IP.
Voice Chat : Audio → Whisper → EN→PT → Pinecone → LLM.
Document Analysis : Image / PDF → LLM Vision → analyse juridique.
"""

import uvicorn
import time
import traceback
import logging
import re
import socket
import base64
import mimetypes

from fastapi import FastAPI, Body, HTTPException, Depends, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import (
    create_engine, Column, Integer,
    String, Text, DateTime, ForeignKey
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from passlib.context import CryptContext
from openai import OpenAI
from typing import Optional

from config import (
    LLM_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    PROPERTY_VS_TARGETS,
    MLFLOW_TRACKING_URI,
    MLFLOW_TRACKING_UI_URL,
    firebase_auth,
    FIREBASE_INITIALIZED,
)
from complianceEngine import (
    load_embedding_model,
    load_selected_vectorstores,
)
from askQuestions import run_api_chat, run_api_voice_chat

# Import évaluateur humain
from human_evaluator import (
    save_interaction_for_evaluation,
    save_human_evaluation,
    get_pending_interactions,
    get_interaction_details,
    get_evaluation_stats,
    export_evaluations_csv,
    EVALUATION_CRITERIA,
)

# Import évaluateur RAG automatique
from rag_evaluator import RAGEvaluator

# Import Quality of Life
from qualityLife import (
    analyze_address,
    geocode_address,
    fetch_pois,
    fetch_air_quality,
    calculate_quality_score
)

# Import système de crédits
from credits import (
    get_credits_model,
    get_credits_status,
    consume_credit,
    set_admin,
    reset_credits,
    CREDITS_CONFIG,
)
from subscription import (
    get_user_plan, set_user_plan, get_today_usage,
    consume_quota, create_payment, verify_payment,
)
from config import PLANS
import mlflow

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================
# DATABASE — Utilisateurs & Historique & Crédits
# ============================================================
DATABASE_URL = "sqlite:///./propiq_v2.db"
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserTable(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)


class HistoryTable(Base):
    __tablename__ = "history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String)
    property_label = Column(String)
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)


# ── Crédits : modèle attaché à la même Base ──────────────────
CreditsTable = get_credits_model(Base)

Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# APP SETUP
# ============================================================
app = FastAPI(
    title="PropIQ API",
    version="2.4.0",
    description=(
        "PropIQ — Chatbot Juridique Immobilier Portugais\n"
        "Évaluation : manuelle (humaine) + automatique RAG (MLflow)\n"
        "Quality of Life : analyse multicritères d'adresse\n"
        "Crédits : 5 req/jour (anonyme) · 20 req/jour (inscrit)\n"
        "Voice Chat : Audio → Whisper → EN→PT → Pinecone → LLM\n"
        "Document Analysis : Image / PDF → LLM Vision → analyse juridique"
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

embeddings = None
llm_client = None
rag_evaluator = None
es_client = None
VS_CACHE = {}


# ============================================================
# STARTUP
# ============================================================
@app.on_event("startup")
async def startup():
    global embeddings, llm_client, rag_evaluator, es_client

    # ── Embeddings ────────────────────────────────────────────
    logger.info("[Startup] Chargement embeddings...")
    embeddings = load_embedding_model()
    logger.info("[Startup] ✅ Embeddings prêts.")

    # ── LLM client ───────────────────────────────────────────
    if not OPENROUTER_API_KEY:
        logger.critical("[Startup] ❌ OPENROUTER_API_KEY manquante !")
        raise RuntimeError("OPENROUTER_API_KEY non définie.")

    llm_client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
    )
    logger.info(f"[Startup] ✅ Client OpenRouter | modèle={LLM_MODEL}")

    # ── RAG Evaluator ─────────────────────────────────────────
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    rag_evaluator = RAGEvaluator(client=llm_client, llm_model=LLM_MODEL)
    logger.info("[Startup] ✅ RAGEvaluator initialisé (MLflow actif).")

    # ── Elasticsearch (Monitoring) ────────────────────────────
    try:
        from monitoring import connect_elasticsearch, create_indices
        es_client = connect_elasticsearch()
        if es_client:
            create_indices(es_client)
            logger.info("[Startup] ✅ Elasticsearch connecté — monitoring actif.")
        else:
            logger.warning(
                "[Startup] ⚠️  Elasticsearch non disponible. "
                "Monitoring désactivé (l'app continue normalement)."
            )
    except ImportError:
        logger.warning("[Startup] ⚠️  monitoring.py introuvable — ES désactivé.")
    except Exception as es_startup_err:
        logger.warning(f"[Startup] ⚠️  ES init ignorée : {es_startup_err}")

    logger.info("[Startup] 📋 Mode évaluation : HUMAINE + RAG AUTOMATIQUE")
    logger.info("[Startup] 🌍 Quality of Life API : ACTIVE")
    logger.info("[Startup] 💳 Système de crédits : ACTIVE")
    logger.info("[Startup] 🎙️ Voice Chat (Whisper) : ACTIVE")
    logger.info("[Startup] 📄 Document Analysis (Image/PDF) : ACTIVE")
    logger.info("[Startup] 🚀 PropIQ Backend prêt.")


# ============================================================
# HELPERS
# ============================================================
def get_vs_cached(emb, indices: list) -> dict:
    key = tuple(sorted(indices))
    if key not in VS_CACHE:
        VS_CACHE[key] = load_selected_vectorstores(emb, indices)
    return VS_CACHE[key]


def get_client_ip(request: Request) -> str:
    """
    Récupère l'IP réelle du client.
    Gère X-Forwarded-For des proxies / nginx / load balancers.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ============================================================
# FIREBASE AUTH — Middleware & Dependency
# ============================================================
async def verify_firebase_token(request: Request) -> dict:
    """
    FastAPI Dependency — Vérifie le token Firebase JWT envoyé par Flutter.

    Le token doit être passé dans le header HTTP :
        Authorization: Bearer <firebase_id_token>

    Retourne le payload décodé du token (uid, email, etc.)
    Lève HTTPException 401 si le token est absent, expiré ou invalide.

    Usage dans un endpoint :
        @app.post("/api/mon-endpoint")
        async def mon_endpoint(user: dict = Depends(verify_firebase_token)):
            uid   = user["uid"]
            email = user.get("email", "")
    """
    if not FIREBASE_INITIALIZED:
        raise HTTPException(
            status_code=503,
            detail="Firebase non initialisé. Vérifiez la configuration serveur."
        )

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Token Firebase manquant. Header attendu : Authorization: Bearer <token>"
        )

    token = auth_header.split("Bearer ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token Firebase vide.")

    try:
        decoded = firebase_auth.verify_id_token(token)
        logger.info(
            f"[Firebase] ✅ Token valide — "
            f"uid={decoded.get('uid')} | email={decoded.get('email', 'N/A')}"
        )
        return decoded
    except firebase_auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token Firebase expiré. Reconnectez-vous.")
    except firebase_auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Token Firebase invalide.")
    except firebase_auth.RevokedIdTokenError:
        raise HTTPException(status_code=401, detail="Token Firebase révoqué. Reconnectez-vous.")
    except Exception as e:
        logger.error(f"[Firebase] ❌ Erreur vérification token : {e}")
        raise HTTPException(status_code=401, detail=f"Erreur d'authentification : {str(e)}")


async def get_optional_firebase_user(request: Request) -> Optional[dict]:
    """
    Dependency optionnelle — Ne bloque pas si le token est absent.
    Utile pour les endpoints accessibles aux anonymes ET aux authentifiés.

    Retourne le payload Firebase si token valide, None sinon.

    Usage :
        @app.post("/api/chat")
        async def chat(firebase_user: Optional[dict] = Depends(get_optional_firebase_user)):
            uid = firebase_user["uid"] if firebase_user else None
    """
    try:
        return await verify_firebase_token(request)
    except HTTPException:
        return None


@app.get("/api/auth/firebase/verify")
async def firebase_verify(user: dict = Depends(verify_firebase_token)):
    """
    Vérifie que le token Firebase est valide et retourne les infos utilisateur.
    Appelé par Flutter après login pour confirmer la session côté backend.

    Headers requis :
        Authorization: Bearer <firebase_id_token>

    Response :
    {
        "valid": true,
        "uid":   "abc123",
        "email": "user@example.com",
        "name":  "John Doe"
    }
    """
    return {
        "valid": True,
        "uid": user.get("uid"),
        "email": user.get("email", ""),
        "name": user.get("name", ""),
    }


# ============================================================
# AUTH (register / login classique conservé pour compatibilité)
# ============================================================
@app.post("/api/auth/register")
def register(
    data: dict = Body(...),
    db: Session = Depends(get_db),
):
    email = data.get("email", "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email requis.")
    if db.query(UserTable).filter(UserTable.email == email).first():
        raise HTTPException(status_code=400, detail="Email déjà enregistré.")

    password = data.get("password", "")
    if not password:
        raise HTTPException(status_code=400, detail="Mot de passe requis.")

    user = UserTable(
        full_name=data.get("full_name", "").strip(),
        email=email,
        hashed_password=pwd_context.hash(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info(f"[Register] {email}")
    return {
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
        }
    }


@app.post("/api/auth/login")
def login(
    data: dict = Body(...),
    db: Session = Depends(get_db),
):
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    user = db.query(UserTable).filter(UserTable.email == email).first()

    if not user or not pwd_context.verify(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Identifiants invalides.")

    logger.info(f"[Login] {email}")
    return {
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
        }
    }


# ============================================================
# AUTH — Vérification email en temps réel
# ============================================================
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')


def check_domain_exists(domain: str) -> bool:
    """
    Vérifie si le domaine existe réellement via résolution DNS (socket stdlib).
    Aucune dépendance externe requise.
    gmail.com, yahoo.com, outlook.com, et tous les vrais domaines passent.
    Seuls les domaines inventés/inexistants sont rejetés.
    """
    try:
        socket.setdefaulttimeout(5)
        socket.getaddrinfo(domain, None)
        return True
    except (socket.gaierror, socket.timeout):
        return False


@app.get("/api/auth/check-email")
def check_email(email: str, db: Session = Depends(get_db)):
    """
    Vérifie en temps réel si un email est :
    1. Syntaxiquement valide
    2. Associé à un domaine réel (gmail, yahoo, outlook, domaines pro, etc.)
    3. Pas déjà utilisé en base de données
    """
    email = email.strip().lower()

    # 1. Vérification syntaxe
    if not EMAIL_REGEX.match(email):
        return {"valid": False, "reason": "Format d'email invalide."}

    # 2. Vérification domaine (accepte gmail, yahoo, outlook, etc.)
    domain = email.split("@")[1]
    if not check_domain_exists(domain):
        return {"valid": False, "reason": f"Le domaine '{domain}' n'existe pas."}

    # 3. Email déjà enregistré en base
    existing = db.query(UserTable).filter(UserTable.email == email).first()
    if existing:
        return {"valid": False, "reason": "Cet email est déjà utilisé."}

    return {"valid": True, "reason": ""}


# ============================================================
# CHAT — Sauvegarde humaine + évaluation RAG + crédits
# ============================================================
@app.post("/api/chat")
async def chat_endpoint(
    request: Request,
    payload: dict = Body(...),
    firebase_user: Optional[dict] = Depends(get_optional_firebase_user),
):
    """
    Chat légal libre avec RAG + système de crédits quotidiens.

    Limites :
      - Anonyme (IP)    : 5  requêtes / jour
      - Inscrit (email) : 20 requêtes / jour
      - Admin           : illimité

    Chaque interaction est :
    - Vérifiée et débitée en crédits AVANT l'appel LLM.
    - Sauvegardée automatiquement pour évaluation humaine ultérieure.
    - Évaluée automatiquement par le RAGEvaluator (15 métriques → MLflow).

    Body JSON attendu :
    {
        "property_type":  "residencial",
        "question":       "Quels documents sont nécessaires pour vendre ?",
        "extracted_data": {},          ← optionnel
        "user_id":        1,           ← optionnel (null si anonyme)
        "llm_model":      "mistralai/mistral-large-2512"  ← optionnel
    }

    Erreur 429 si limite atteinte :
    {
        "error":      "daily_limit_reached",
        "message":    "Daily limit reached (5 requests). Come back tomorrow.",
        "used":       5,
        "limit":      5,
        "remaining":  0,
        "reset_date": "2025-07-02",
        "user_type":  "anonymous"
    }
    """
    try:
        property_type = payload.get("property_type", "").strip()
        question = payload.get("question", "").strip()
        user_id_raw = payload.get("user_id")
        user_id = int(user_id_raw) if user_id_raw else None
        client_ip = get_client_ip(request)

        # ── Identité Firebase (priorité sur user_id payload) ─
        firebase_uid = firebase_user.get("uid") if firebase_user else None
        if firebase_uid:
            logger.info(f"[Chat] 🔥 Utilisateur Firebase identifié : uid={firebase_uid}")

        if not property_type:
            raise HTTPException(
                status_code=400, detail="'property_type' est requis."
            )
        if not question:
            raise HTTPException(
                status_code=400, detail="'question' est requise."
            )
        if property_type not in PROPERTY_VS_TARGETS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"property_type '{property_type}' invalide. "
                    f"Valides : {list(PROPERTY_VS_TARGETS.keys())}"
                ),
            )

        # ── VÉRIFICATION & CONSOMMATION DU CRÉDIT SQLite (général) ──
        db_gen_cr = get_db()
        db_credits = next(db_gen_cr)
        try:
            user_plan = get_user_plan(firebase_uid) if firebase_uid else "free"
            credit_result = consume_credit(
                db=db_credits,
                CreditsTable=CreditsTable,
                user_id=user_id,
                ip_address=client_ip,
                user_plan=user_plan,
            )
        finally:
            try:
                next(db_gen_cr)
            except StopIteration:
                pass

        if not credit_result["consumed"]:
            logger.warning(
                f"[Chat] 🚫 Limite crédits atteinte — user_id={user_id} | ip={client_ip} "
                f"| used={credit_result['used']}/{credit_result['limit']}"
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "daily_limit_reached",
                    "message": credit_result["message"],
                    "used": credit_result["used"],
                    "limit": credit_result["limit"],
                    "remaining": 0,
                    "reset_date": credit_result["reset_date"],
                    "user_type": credit_result["user_type"],
                },
            )

        logger.info(
            f"[Chat] 💳 Crédit SQLite consommé — user_id={user_id} | ip={client_ip} "
            f"| {credit_result['used']}/{credit_result['limit']}"
        )

        # ── ✅ Vérification quota Firestore "requests" (Free: 10/j | Premium: 20/j) ──
        # Sans ce bloc, les limites de requêtes par plan ne sont pas appliquées en Firestore.
        if firebase_uid:
            try:
                quota_requests = consume_quota(firebase_uid, "requests")
                logger.info(
                    f"[Chat] ✅ Quota Firestore requests consommé — "
                    f"uid={firebase_uid} | plan={user_plan} | "
                    f"remaining={quota_requests['remaining']}"
                )
            except HTTPException as quota_err:
                detail = quota_err.detail if isinstance(quota_err.detail, dict) else {
                    "message": str(quota_err.detail)}
                logger.warning(
                    f"[Chat] 🚫 Quota Firestore requests dépassé — "
                    f"uid={firebase_uid} | plan={user_plan} | detail={detail}"
                )
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "quota_exceeded",
                        "message": detail.get("message", "Limite journalière de requêtes atteinte."),
                        "usage_type": "requests",
                        "used": detail.get("used", 0),
                        "limit": detail.get("limit", 0),
                        "remaining": 0,
                        "plan": detail.get("plan", user_plan),
                    },
                )

        # ── Sélection du modèle LLM ──────────────────────────
        ALLOWED_MODELS = {
            "qwen/qwen3-235b-a22b",
            "mistralai/mistral-large-2512",
            "openai/gpt-4o",
            "meta-llama/llama-3.3-70b-instruct",
            "microsoft/phi-4",
            "meta-llama/llama-3.2-11b-vision-instruct",
            "qwen/qwen3-vl-32b-instruct",
        }
        requested_model = payload.get("llm_model", "").strip()
        active_model = requested_model if requested_model in ALLOWED_MODELS else LLM_MODEL
        logger.info(f"[Chat] Modèle utilisé : {active_model}")

        # ── Génération de la réponse RAG ─────────────────────
        t_start = time.time()
        indices = PROPERTY_VS_TARGETS[property_type]
        vs = get_vs_cached(embeddings, indices)

        reply, sources = run_api_chat(
            property_type=property_type,
            user_msg=question,
            extracted_data=payload.get("extracted_data", {}),
            vectorstores=vs,
            client=llm_client,
            llm_model=active_model,
        )

        latency_ms = round((time.time() - t_start) * 1000)

        # ── Sauvegarde pour évaluation humaine ───────────────
        interaction_id = "N/A"
        try:
            interaction_id = save_interaction_for_evaluation(
                question=question,
                answer=reply,
                sources=sources,
                property_type=property_type,
                latency_ms=latency_ms,
                chat_mode="free",
                user_id=user_id,
                model_used=active_model,
            )
            logger.info(f"[Chat] ✅ Interaction sauvegardée : {interaction_id}")
        except Exception as save_err:
            logger.warning(f"[Chat] ⚠️  Sauvegarde humaine échouée : {save_err}")

        # ── Évaluation RAG automatique → MLflow ──────────────
        rag_metrics = None
        rag_run_uri = None
        composite_score = None
        try:
            raw_docs = [
                {
                    "text": s.get("content", ""),
                    "index": s.get("index", ""),
                    "score": s.get("score", 0.0),
                    "metadata": s.get("metadata", {}),
                }
                for s in sources
            ]

            rag_metrics, rag_run_uri = rag_evaluator.evaluate_and_log(
                question=question,
                answer=reply,
                docs=raw_docs,
                latency_ms=latency_ms,
                property_type=property_type,
                run_name=f"chat_{property_type}_{interaction_id[:8]}",
            )
            composite_score = rag_evaluator._composite_score(rag_metrics)
            logger.info(
                f"[Chat] 📊 RAG eval | "
                f"composite={composite_score:.3f} | "
                f"faithfulness={rag_metrics.faithfulness:.3f} | "
                f"hallucination={'⚠️' if rag_metrics.hallucination_flag else '✅'} | "
                f"run={rag_run_uri}"
            )
        except Exception as eval_err:
            logger.warning(f"[Chat] ⚠️  RAG eval échouée : {eval_err}")

        # ── Monitoring Elasticsearch (/api/chat) ──────────────
        if es_client is not None:
            try:
                from monitoring import log_rag_query
                log_rag_query(
                    es=es_client,
                    property_type=property_type,
                    question=question,
                    reply=reply,
                    sources=sources,
                    latency_ms=latency_ms,
                    success=bool(reply and len(reply) > 50),
                )
            except Exception as es_log_err:
                logger.debug(f"[Chat] ES log ignoré : {es_log_err}")

        # ── Sauvegarde dans l'historique utilisateur ──────────
        if user_id:
            try:
                db_gen = get_db()
                db_hist = next(db_gen)
                history_entry = HistoryTable(
                    user_id=int(user_id),
                    type="Free Chat",
                    property_label=property_type,
                    content=reply,
                    timestamp=datetime.utcnow(),
                )
                db_hist.add(history_entry)
                db_hist.commit()
                logger.info(f"[Chat] ✅ Historique sauvegardé pour user_id={user_id}")
            except Exception as hist_err:
                logger.warning(f"[Chat] ⚠️  Sauvegarde historique échouée : {hist_err}")
            finally:
                try:
                    next(db_gen)
                except StopIteration:
                    pass

        logger.info(
            f"[Chat] type={property_type} | "
            f"latency={latency_ms}ms | "
            f"sources={len(sources)} | "
            f"interaction_id={interaction_id}"
        )

        # ── Réponse enrichie avec métriques RAG + crédits + quota Firestore ──
        response_body = {
            "response": reply,
            "sources": sources,
            "latency_ms": latency_ms,
            "model_used": active_model,
            "mode": "openrouter",
            "interaction_id": interaction_id,
            "eval_status": "pending_human_review",
            "credits": {
                "used": credit_result["used"],
                "limit": credit_result["limit"],
                "remaining": credit_result["remaining"],
                "warning": credit_result["warning"],
                "message": credit_result["message"],
            },
            "quota": {
                "usage_type": "requests",
                "remaining": quota_requests["remaining"] if firebase_uid else None,
                "limit": quota_requests["limit"] if firebase_uid else None,
                "plan": quota_requests["plan"] if firebase_uid else None,
            },
        }

        if rag_metrics is not None:
            response_body["rag_eval"] = {
                "composite_score": composite_score,
                "answer_relevance": rag_metrics.answer_relevance,
                "faithfulness": rag_metrics.faithfulness,
                "grounding_score": rag_metrics.grounding_score,
                "citation_coverage": rag_metrics.citation_coverage,
                "confidence_level": rag_metrics.confidence_level,
                "hallucination_flag": bool(rag_metrics.hallucination_flag),
                "is_refusal": bool(rag_metrics.is_refusal),
                "mlflow_run": rag_run_uri,
                "mlflow_ui": MLFLOW_TRACKING_UI_URL,
            }

        return response_body

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        logger.error(f"[Chat] Erreur : {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# VOICE CHAT — Audio → Whisper → EN→PT → Pinecone → LLM
# ============================================================
@app.post("/api/voice-chat")
async def voice_chat_endpoint(
    request: Request,
    audio: UploadFile = File(..., description="Audio file (WAV/MP3/WebM/OGG/M4A/FLAC)"),
    property_type: str = Form("residencial"),
    user_id: str = Form(None),
    llm_model_req: str = Form(None),
    db: Session = Depends(get_db),
):
    """
    Endpoint Voice Chat — multipart/form-data.

    Reçoit un fichier audio, le transcrit via Whisper local,
    traduit la requête EN → PT, interroge Pinecone et retourne
    la réponse LLM en anglais.

    Form fields :
        audio         — fichier audio (WAV, MP3, WebM, OGG, M4A, FLAC)
        property_type — "residencial" | "comercial" | ... (défaut: residencial)
        user_id       — identifiant utilisateur (optionnel, pour crédits)
        llm_model_req — modèle LLM à utiliser (optionnel)

    Response JSON :
    {
        "reply"         : "...",        ← réponse LLM en anglais
        "transcription" : "...",        ← texte transcrit par Whisper
        "detected_lang" : "en",         ← langue détectée automatiquement
        "sources"       : [...],        ← sources RAG normalisées
        "latency_ms"    : 1234,
        "input_mode"    : "voice",
        "credits"       : {...}
    }

    Codes d'erreur :
        400 — audio vide ou property_type invalide
        422 — transcription vide ou pipeline RAG échoué
        429 — limite de crédits atteinte
        500 — erreur interne
    """
    try:
        client_ip = get_client_ip(request)
        user_id_int = int(user_id) if user_id and user_id.isdigit() else None

        # ── Validation property_type ──────────────────────────
        if property_type not in PROPERTY_VS_TARGETS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"property_type '{property_type}' invalide. "
                    f"Valides : {list(PROPERTY_VS_TARGETS.keys())}"
                ),
            )

        # ── Vérification & consommation du crédit ────────────
        db_gen_cr = get_db()
        db_credits = next(db_gen_cr)
        try:
            user_plan = get_user_plan(str(user_id_int)) if user_id_int else "free"
            credit_result = consume_credit(
                db=db_credits,
                CreditsTable=CreditsTable,
                user_id=user_id_int,
                ip_address=client_ip,
                user_plan=user_plan,
            )
        finally:
            try:
                next(db_gen_cr)
            except StopIteration:
                pass

        if not credit_result["consumed"]:
            logger.warning(
                f"[VoiceChat] 🚫 Limite atteinte — user_id={user_id_int} "
                f"| ip={client_ip} | used={credit_result['used']}/{credit_result['limit']}"
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "daily_limit_reached",
                    "message": credit_result["message"],
                    "used": credit_result["used"],
                    "limit": credit_result["limit"],
                    "remaining": 0,
                    "reset_date": credit_result["reset_date"],
                    "user_type": credit_result["user_type"],
                },
            )

        # ── Lecture fichier audio ─────────────────────────────
        filename = audio.filename or "audio.wav"
        audio_bytes = await audio.read()

        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file received.")

        logger.info(
            f"[VoiceChat] IP={client_ip} | user={user_id_int} | "
            f"file={filename} | size={len(audio_bytes)//1024} KB | type={property_type}"
        )

        # ── Sélection du modèle LLM ──────────────────────────
        ALLOWED_MODELS = {
            "qwen/qwen3-235b-a22b",
            "mistralai/mistral-large-2512",
            "openai/gpt-4o",
            "microsoft/phi-4",
            "meta-llama/llama-3.3-70b-instruct",
            "qwen/qwen3-vl-32b-instruct",



        }
        active_model = (
            llm_model_req
            if llm_model_req and llm_model_req in ALLOWED_MODELS
            else LLM_MODEL
        )

        # ── Vectorstore ───────────────────────────────────────
        indices = PROPERTY_VS_TARGETS[property_type]
        vectorstores = get_vs_cached(embeddings, indices)

        # ── Pipeline Voice → RAG ──────────────────────────────
        t_start = time.time()
        result = run_api_voice_chat(
            property_type=property_type,
            audio_bytes=audio_bytes,
            filename=filename,
            extracted_data={},
            vectorstores=vectorstores,
            client=llm_client,
            llm_model=active_model,
        )
        latency_ms = round((time.time() - t_start) * 1000)

        if not result["success"]:
            logger.warning(f"[VoiceChat] Pipeline failed: {result['error']}")
            raise HTTPException(status_code=422, detail=result["error"])

        # ── Évaluation RAG automatique → MLflow (Voice Chat) ──
        voice_rag_metrics = None
        voice_rag_run_uri = None
        voice_composite_score = None
        if rag_evaluator is not None:
            try:
                voice_raw_docs = [
                    {
                        "text": s.get("content", ""),
                        "index": s.get("index", ""),
                        "score": s.get("score", 0.0),
                        "metadata": s.get("metadata", {}),
                    }
                    for s in result.get("sources", [])
                ]
                voice_rag_metrics, voice_rag_run_uri = rag_evaluator.evaluate_and_log(
                    question=result.get("transcription", ""),
                    answer=result.get("reply", ""),
                    docs=voice_raw_docs,
                    latency_ms=latency_ms,
                    property_type=property_type,
                    run_name=f"voice_{property_type}_{result.get('detected_lang', 'unk')}",
                )
                voice_composite_score = rag_evaluator._composite_score(voice_rag_metrics)
                logger.info(
                    f"[VoiceChat] 📊 RAG eval | "
                    f"composite={voice_composite_score:.3f} | "
                    f"faithfulness={voice_rag_metrics.faithfulness:.3f} | "
                    f"hallucination={'⚠️' if voice_rag_metrics.hallucination_flag else '✅'} | "
                    f"run={voice_rag_run_uri}"
                )
            except Exception as voice_eval_err:
                logger.warning(f"[VoiceChat] ⚠️  RAG eval échouée : {voice_eval_err}")

        # ── Monitoring Elasticsearch (Voice Chat) ─────────────
        if es_client is not None:
            try:
                from monitoring import log_rag_query
                log_rag_query(
                    es=es_client,
                    property_type=property_type,
                    question=result.get("transcription", ""),
                    reply=result.get("reply", ""),
                    sources=result.get("sources", []),
                    latency_ms=latency_ms,
                    success=True,
                )
            except Exception as es_err:
                logger.debug(f"[VoiceChat] ES log ignoré : {es_err}")

        # ── Sauvegarde historique utilisateur ─────────────────
        if user_id_int:
            try:
                db_gen = get_db()
                db_hist = next(db_gen)
                db_hist.add(HistoryTable(
                    user_id=user_id_int,
                    type="Voice Chat",
                    property_label=property_type,
                    content=(
                        f"[VOICE | lang:{result['detected_lang']}] "
                        f"{result['transcription'][:200]}"
                    ),
                    timestamp=datetime.utcnow(),
                ))
                db_hist.commit()
                logger.info(
                    f"[VoiceChat] ✅ Historique sauvegardé pour user_id={user_id_int}"
                )
            except Exception as hist_err:
                logger.warning(f"[VoiceChat] ⚠️  Sauvegarde historique échouée : {hist_err}")
            finally:
                try:
                    next(db_gen)
                except StopIteration:
                    pass

        logger.info(
            f"[VoiceChat] ✅ Done | latency={latency_ms}ms | "
            f"lang={result['detected_lang']} | sources={len(result['sources'])}"
        )

        return {
            "reply": result["reply"],
            "transcription": result["transcription"],
            "detected_lang": result["detected_lang"],
            "sources": result["sources"],
            "latency_ms": latency_ms,
            "model_used": active_model,
            "input_mode": "voice",
            "credits": {
                "used": credit_result["used"],
                "limit": credit_result["limit"],
                "remaining": credit_result["remaining"],
                "warning": credit_result["warning"],
                "message": credit_result["message"],
            },
            **(
                {
                    "rag_eval": {
                        "composite_score": voice_composite_score,
                        "answer_relevance": voice_rag_metrics.answer_relevance,
                        "faithfulness": voice_rag_metrics.faithfulness,
                        "hallucination_flag": bool(voice_rag_metrics.hallucination_flag),
                        "confidence_level": voice_rag_metrics.confidence_level,
                        "mlflow_run": voice_rag_run_uri,
                        "mlflow_ui": MLFLOW_TRACKING_UI_URL,
                    }
                }
                if voice_rag_metrics is not None
                else {}
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        logger.error(f"[VoiceChat] Erreur inattendue : {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# DOCUMENT ANALYSIS — Image / PDF → LLM Vision → analyse juridique
# ============================================================

# Types MIME acceptés
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_ALLOWED_PDF_TYPE = "application/pdf"
_MAX_FILE_SIZE_MB = 10

# Modèles capables de vision (images)
_VISION_MODELS = {
    "openai/gpt-4o",
    "qwen/qwen3-vl-32b-instruct",
    "meta-llama/llama-3.2-11b-vision-instruct",
}

# Modèle vision par défaut (fallback si le modèle sélectionné n'est pas vision)
_DEFAULT_VISION_MODEL = "qwen/qwen3-vl-32b-instruct"  # "openai/gpt-4o"


def _build_document_analysis_prompt(
    property_type: str,
    file_type: str,
    user_question: str = "",
    rag_chunks: list = None,
) -> str:
    """
    Construit le prompt système pour l'analyse juridique d'un document immobilier.
    - Si une question utilisateur est fournie, le modèle y répond en priorité.
    - Si des chunks RAG sont fournis, le modèle DOIT s'appuyer dessus et les citer.
    """
    doc_label = "PDF document" if file_type == "pdf" else "image"

    # ── Bloc question utilisateur ──────────────────────────────────
    if user_question and user_question.strip():
        question_block = f"""
The user has asked the following specific legal question about this document:
\"{user_question.strip()}\"

PRIORITY TASK: Answer this question directly and thoroughly, using BOTH the document
content AND the legal reference chunks provided below. Cite the relevant law articles.
"""
    else:
        question_block = ""

    # ── Bloc chunks RAG ───────────────────────────────────────────
    if rag_chunks:
        chunks_lines = []
        for i, c in enumerate(rag_chunks):
            idx_name = c.get("index", "")
            article = c.get("article", "")
            chunk_content = c.get("content", "").strip()
            chunks_lines.append(
                f"[SOURCE {i+1}] {idx_name} | {article}\n{chunk_content}"
            )
        chunks_text = "\n\n".join(chunks_lines)
        rag_block = f"""
=== LEGAL REFERENCE CHUNKS (base de données droit immobilier portugais) ===
{chunks_text}
=== FIN DES RÉFÉRENCES LÉGALES ===

RÈGLES DE CITATION OBLIGATOIRES :
- Vous DEVEZ fonder votre analyse juridique sur les chunks ci-dessus.
- Pour chaque point juridique, citez la source ainsi :
  → [NOM_INDEX | Artigo X.º] suivi d'un extrait ou paraphrase du chunk.
- Ne fabriquez AUCUN numéro d'article absent des chunks fournis.
- Si un chunk n'est pas pertinent pour la question, ignorez-le silencieusement.
"""
    else:
        rag_block = ""

    has_question = bool(question_block and question_block.strip())
    priority_note = (
        "PRIORITY: Answer the user's question directly and thoroughly FIRST, "
        "before any general analysis. Then provide the full structured analysis below."
        if has_question else
        "Provide a full structured legal analysis of the document."
    )
    answer_section = (
        "### 🎯 Answer to Your Question\n"
        "[Direct, thorough answer to the user question — cite laws and document content]\n\n"
        if has_question else ""
    )
    return f"""You are PropIQ, an expert legal assistant specialized in Portuguese real estate law.

A user has uploaded a {doc_label} related to a {property_type} property.
{question_block}{rag_block}
## YOUR TASK

{priority_note}

1. Identify and summarize the **type of document** (deed, contract, permit, floor plan, tax notice, etc.).
2. Extract all legally relevant information: parties, dates, property references (article, matrix, fraction), areas, values, clauses, obligations, deadlines, signatures, stamps, notary references.
3. Flag any **legal issues**, missing information, suspicious clauses, or items requiring immediate attention.
4. Provide **mandatory citations** to legal reference chunks where applicable.

## RESPONSE FORMAT

Use exactly these sections in this order:

{answer_section}### 📄 Document Type
[Type and purpose of the document]

### 👥 Key Parties & References
[Parties, NIF/NIPC, property article, matrix, conservatória reference]

### 💰 Financial & Legal Terms
[Price, deadlines, obligations, penalties, encumbrances]

### ⚠️ Legal Issues & Risks
[Missing documents, suspicious clauses, encumbrances, compliance gaps — be explicit and specific]

### 📚 Legal References
[Cite as: → [INDEX_NAME | Artigo X.º] — one per legal claim]

### ✅ Summary & Recommendations
[Concise verdict: is this property/contract legally sound? What must the buyer/seller do next?]

## CRITICAL RULES
- **ALWAYS respond in English**, regardless of the document language or the user's input language.
- Be factual and precise. Do NOT invent information not visible in the document.
- If a section is illegible or cut off, explicitly state it.
- Never fabricate article numbers not present in the provided legal reference chunks.
- If no legal chunks were provided, rely on your knowledge of Portuguese real estate law but flag it clearly."""


@app.post("/api/upload-document")
async def upload_document(
    request: Request,
    file: UploadFile = File(..., description="Image (JPG/PNG/WEBP) or PDF document"),
    property_type: str = Form("residencial"),
    user_id: str = Form(None),
    llm_model_req: str = Form(None),
    user_question: str = Form("", description="Optional legal question about the document"),
    firebase_user: Optional[dict] = Depends(get_optional_firebase_user),
):
    """
    Document Analysis Endpoint — multipart/form-data.

    Accepte une image (JPG, PNG, WEBP, GIF) ou un PDF et retourne
    une analyse juridique structurée via LLM vision.

    Form fields :
        file          — fichier image ou PDF (max 10 MB)
        property_type — "residencial" | "comercial" | "terreno" | "alojamento_local"
        user_id       — identifiant utilisateur (optionnel, pour crédits)
        llm_model_req — modèle LLM vision à utiliser (optionnel, doit être un modèle vision)
        user_question — question juridique spécifique à poser sur le document (optionnel)

    Response JSON :
    {
        "analysis"      : "...",   ← analyse juridique structurée
        "file_type"     : "image" | "pdf",
        "filename"      : "...",
        "model_used"    : "...",
        "latency_ms"    : 1234,
        "credits"       : {...}
    }

    Codes d'erreur :
        400 — fichier vide, type non supporté, taille > 10 MB
        429 — limite de crédits atteinte
        500 — erreur interne
    """
    try:
        client_ip = get_client_ip(request)
        user_id_int = int(user_id) if user_id and user_id.isdigit() else None

        # ── Validation property_type ──────────────────────────
        if property_type not in PROPERTY_VS_TARGETS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"property_type '{property_type}' invalide. "
                    f"Valides : {list(PROPERTY_VS_TARGETS.keys())}"
                ),
            )

        # ── Lecture du fichier ────────────────────────────────
        filename = file.filename or "document"
        file_bytes = await file.read()

        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty file received.")

        # ── Vérification taille ───────────────────────────────
        file_size_mb = len(file_bytes) / (1024 * 1024)
        if file_size_mb > _MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=400,
                detail=f"File too large ({file_size_mb:.1f} MB). Maximum allowed: {_MAX_FILE_SIZE_MB} MB.",
            )

        # ── Détection du type MIME ────────────────────────────
        content_type = file.content_type or ""
        # Fallback par extension si le content_type est générique
        if not content_type or content_type == "application/octet-stream":
            guessed, _ = mimetypes.guess_type(filename)
            content_type = guessed or ""

        # Normalisation des types courants
        if filename.lower().endswith(".jpg") or filename.lower().endswith(".jpeg"):
            content_type = "image/jpeg"
        elif filename.lower().endswith(".png"):
            content_type = "image/png"
        elif filename.lower().endswith(".webp"):
            content_type = "image/webp"
        elif filename.lower().endswith(".gif"):
            content_type = "image/gif"
        elif filename.lower().endswith(".pdf"):
            content_type = "application/pdf"

        is_image = content_type in _ALLOWED_IMAGE_TYPES
        is_pdf = content_type == _ALLOWED_PDF_TYPE

        if not is_image and not is_pdf:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported file type '{content_type}'. "
                    "Accepted: JPG, PNG, WEBP, GIF (images) or PDF."
                ),
            )

        file_type_label = "pdf" if is_pdf else "image"

        # ── UID Firebase (priorité sur user_id SQLite) ───────
        firebase_uid = firebase_user.get("uid") if firebase_user else None
        if firebase_uid:
            logger.info(f"[DocAnalysis] 🔥 Utilisateur Firebase identifié : uid={firebase_uid}")

        logger.info(
            f"[DocAnalysis] IP={client_ip} | user={user_id_int} | firebase_uid={firebase_uid} | "
            f"file={filename} | type={content_type} | size={file_size_mb:.2f} MB"
        )

        # ── Vérification & consommation du crédit SQLite (général) ──
        db_gen_cr = get_db()
        db_credits = next(db_gen_cr)
        try:
            user_plan = get_user_plan(firebase_uid) if firebase_uid else "free"
            credit_result = consume_credit(
                db=db_credits,
                CreditsTable=CreditsTable,
                user_id=user_id_int,
                ip_address=client_ip,
                user_plan=user_plan,
            )
        finally:
            try:
                next(db_gen_cr)
            except StopIteration:
                pass

        if not credit_result["consumed"]:
            logger.warning(
                f"[DocAnalysis] 🚫 Limite crédits atteinte — user_id={user_id_int} "
                f"| ip={client_ip}"
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "daily_limit_reached",
                    "message": credit_result["message"],
                    "used": credit_result["used"],
                    "limit": credit_result["limit"],
                    "remaining": 0,
                    "reset_date": credit_result["reset_date"],
                    "user_type": credit_result["user_type"],
                },
            )

        # ── ✅ Vérification quota Firestore (images / pdfs) ──────────
        # C'est ici que les limites "1 image/jour" et "1 pdf/jour" sont appliquées.
        # Sans ce bloc, les compteurs Firestore restaient à 0 et les limites
        # n'étaient jamais atteintes.
        quota_result = None  # Initialisé pour éviter NameError si firebase_uid est None
        if firebase_uid:
            usage_type = "pdfs" if is_pdf else "images"
            try:
                quota_result = consume_quota(firebase_uid, usage_type)
                logger.info(
                    f"[DocAnalysis] ✅ Quota Firestore consommé — "
                    f"uid={firebase_uid} | type={usage_type} | "
                    f"remaining={quota_result['remaining']}"
                )
            except HTTPException as quota_err:
                detail = quota_err.detail if isinstance(quota_err.detail, dict) else {
                    "message": str(quota_err.detail)}
                logger.warning(
                    f"[DocAnalysis] 🚫 Quota Firestore dépassé — "
                    f"uid={firebase_uid} | type={usage_type} | detail={detail}"
                )
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "quota_exceeded",
                        "message": detail.get(
                            "message",
                            f"Limite journalière atteinte pour '{usage_type}'."),
                        "usage_type": usage_type,
                        "used": detail.get(
                            "used",
                            0),
                        "limit": detail.get(
                            "limit",
                            0),
                        "remaining": 0,
                        "plan": detail.get(
                            "plan",
                            user_plan),
                    },
                )

        # ── Sélection du modèle vision ────────────────────────
        # Pour les PDFs on utilise aussi un modèle vision via base64
        ALLOWED_MODELS = {
            "qwen/qwen3-235b-a22b",
            "mistralai/mistral-large-2512",
            "openai/gpt-4o",
            "meta-llama/llama-3.3-70b-instruct",
            "microsoft/phi-4",
            "meta-llama/llama-3.2-11b-vision-instruct",
            "Phi-4-multimodal-instruct",
            "qwen/qwen3-vl-32b-instruct",
        }
        requested_model = (llm_model_req or "").strip()

        # Sélection du modèle :
        # 1. Si le modèle demandé est un modèle vision → on l'utilise directement
        # 2. Si le modèle demandé est un modèle texte → fallback vers le modèle vision par défaut
        # 3. Si aucun modèle demandé → modèle vision par défaut
        if requested_model in _VISION_MODELS:
            active_model = requested_model
            logger.info(
                f"[DocAnalysis] Modèle vision sélectionné par l'utilisateur : {active_model}")
        elif requested_model in ALLOWED_MODELS:
            # Modèle texte demandé → on force le modèle vision par défaut
            active_model = _DEFAULT_VISION_MODEL
            logger.info(
                f"[DocAnalysis] Modèle '{requested_model}' non-vision → "
                f"fallback vers modèle vision par défaut : {active_model}"
            )
        else:
            # Aucun modèle valide fourni → modèle vision par défaut
            active_model = _DEFAULT_VISION_MODEL
            if requested_model:
                logger.warning(
                    f"[DocAnalysis] Modèle '{requested_model}' non reconnu → "
                    f"fallback vers modèle vision par défaut : {active_model}"
                )
            else:
                logger.info(
                    f"[DocAnalysis] Aucun modèle demandé → modèle par défaut : {active_model}")

        logger.info(f"[DocAnalysis] ✅ Modèle utilisé : {active_model}")

        # ── Récupération des chunks RAG (si question posée) ──────
        # On interroge Pinecone avec la question de l'utilisateur
        # pour ancrer la réponse dans les textes de loi.
        rag_chunks = []
        if user_question and user_question.strip():
            try:
                indices = PROPERTY_VS_TARGETS[property_type]
                vectorstores = get_vs_cached(embeddings, indices)
                # Recherche similarity dans tous les vectorstores disponibles
                all_docs = []
                for vs_name, vs_store in vectorstores.items():
                    try:
                        docs = vs_store.similarity_search_with_score(
                            user_question.strip(), k=5
                        )
                        for doc, score in docs:
                            all_docs.append({
                                "index": vs_name,
                                "article": doc.metadata.get("article", ""),
                                "content": doc.page_content,
                                "score": float(score),
                            })
                    except Exception:
                        pass
                # Tri par score décroissant, garder les 6 meilleurs
                all_docs.sort(key=lambda x: x["score"], reverse=True)
                rag_chunks = all_docs[:6]
                logger.info(
                    f"[DocAnalysis] 🔍 RAG chunks récupérés : {len(rag_chunks)} "
                    f"pour la question : {user_question[:80]}"
                )
            except Exception as rag_err:
                logger.warning(f"[DocAnalysis] ⚠️  RAG retrieval échoué : {rag_err}")

        # ── Construction du message LLM ───────────────────────
        system_prompt = _build_document_analysis_prompt(
            property_type, file_type_label, user_question, rag_chunks
        )
        b64_data = base64.b64encode(file_bytes).decode("utf-8")

        if is_image:
            # ── Image directe : message vision standard ───────
            user_content = [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{content_type};base64,{b64_data}",
                        "detail": "high",
                    },
                },
                {
                    "type": "text",
                    "text": (
                        (
                            f"User question: {user_question.strip()}\n\n"
                            if user_question and user_question.strip()
                            else ""
                        ) +
                        f"Please analyze this real estate document image for a "
                        f"{property_type} property and provide a detailed legal summary."
                    ),
                },
            ]
        else:
            # ── PDF : extraction texte via PyPDF2 + envoi texte ──
            # Note : certains modèles vision acceptent aussi les PDFs en base64,
            # mais l'extraction texte est plus fiable et compatible universellement.
            try:
                from PyPDF2 import PdfReader
                from io import BytesIO

                pdf_reader = PdfReader(BytesIO(file_bytes))
                extracted = []
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        extracted.append(f"--- Page {page_num} ---\n{page_text.strip()}")

                pdf_text = "\n\n".join(extracted)

                if not pdf_text.strip():
                    # PDF scanné sans texte extractible → on essaie via vision base64
                    logger.warning(
                        "[DocAnalysis] PDF sans texte extractible, "
                        "tentative envoi base64 vision..."
                    )
                    user_content = [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:application/pdf;base64,{b64_data}",
                                "detail": "high",
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                (
                                    f"User question: {user_question.strip()}\n\n"
                                    if user_question and user_question.strip()
                                    else ""
                                ) +
                                f"This is a scanned PDF document related to a {property_type} "
                                "property. Please analyze all visible content and provide a "
                                "detailed legal summary."
                            ),
                        },
                    ]
                else:
                    # PDF avec texte extractible
                    # Limite à ~12 000 caractères pour rester dans le contexte
                    if len(pdf_text) > 12000:
                        pdf_text = pdf_text[:12000] + "\n\n[... document truncated ...]"

                    user_content = [
                        {
                            "type": "text",
                            "text": (
                                (
                                    f"User question: {user_question.strip()}\n\n"
                                    if user_question and user_question.strip()
                                    else ""
                                ) +
                                f"Below is the extracted text from a PDF document related to a "
                                f"{property_type} property. Please analyze it and provide a "
                                f"detailed legal summary.\n\n"
                                f"=== DOCUMENT CONTENT ===\n{pdf_text}"
                            ),
                        }
                    ]

            except Exception as pdf_err:
                logger.error(f"[DocAnalysis] PDF parsing error: {pdf_err}")
                raise HTTPException(
                    status_code=422,
                    detail=f"Could not parse PDF file: {pdf_err}",
                )

        # ── Appel LLM ─────────────────────────────────────────
        t_start = time.time()
        try:
            completion = llm_client.chat.completions.create(
                model=active_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=1500,
                temperature=0.1,
            )
            analysis = completion.choices[0].message.content or ""
        except Exception as llm_err:
            logger.error(f"[DocAnalysis] LLM error: {llm_err}")
            raise HTTPException(
                status_code=500,
                detail=f"LLM analysis failed: {llm_err}",
            )

        latency_ms = round((time.time() - t_start) * 1000)

        logger.info(
            f"[DocAnalysis] ✅ Done | latency={latency_ms}ms | "
            f"type={file_type_label} | model={active_model} | "
            f"analysis_len={len(analysis)}"
        )

        # ── Sauvegarde historique utilisateur ─────────────────
        if user_id_int:
            try:
                db_gen = get_db()
                db_hist = next(db_gen)
                question_prefix = f"[Q: {user_question.strip()[:100]}] " if user_question and user_question.strip(
                ) else ""
                db_hist.add(
                    HistoryTable(
                        user_id=user_id_int,
                        type="Document Analysis",
                        property_label=property_type,
                        content=f"[{file_type_label.upper()} | {filename}] {question_prefix}{analysis[:300]}",
                        timestamp=datetime.utcnow(),
                    ))
                db_hist.commit()
            except Exception as hist_err:
                logger.warning(f"[DocAnalysis] ⚠️  Sauvegarde historique échouée : {hist_err}")
            finally:
                try:
                    next(db_gen)
                except StopIteration:
                    pass

        return {
            "analysis": analysis,
            "file_type": file_type_label,
            "filename": filename,
            "model_used": active_model,
            "latency_ms": latency_ms,
            "user_question": user_question.strip() if user_question else "",
            "credits": {
                "used": credit_result["used"],
                "limit": credit_result["limit"],
                "remaining": credit_result["remaining"],
                "warning": credit_result["warning"],
                "message": credit_result["message"],
            },
            "quota": {
                "usage_type": ("pdfs" if is_pdf else "images"),
                "remaining": quota_result["remaining"] if firebase_uid else None,
                "limit": quota_result["limit"] if firebase_uid else None,
                "plan": quota_result["plan"] if firebase_uid else None,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        logger.error(f"[DocAnalysis] Erreur inattendue : {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# HISTORY — Endpoints REST
# ============================================================
@app.get("/api/history/{user_id}")
def get_history(user_id: int, db: Session = Depends(get_db)):
    """
    Retourne l'historique des interactions d'un utilisateur.
    """
    items = (
        db.query(HistoryTable)
        .filter(HistoryTable.user_id == user_id)
        .order_by(HistoryTable.timestamp.desc())
        .all()
    )
    return [
        {
            "id": item.id,
            "type": item.type,
            "property_label": item.property_label,
            "content": item.content,
            "timestamp": item.timestamp.isoformat(),
        }
        for item in items
    ]


@app.delete("/api/history/{history_id}")
def delete_history_item(history_id: int, db: Session = Depends(get_db)):
    """
    Supprime un élément de l'historique.
    """
    item = db.query(HistoryTable).filter(HistoryTable.id == history_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Élément non trouvé.")
    db.delete(item)
    db.commit()
    return {"status": "deleted", "id": history_id}


# ============================================================
# CREDITS — Endpoints REST
# ============================================================
@app.get("/api/credits/status")
async def credits_status(
    request: Request,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Retourne le statut des crédits sans les consommer.
    """
    client_ip = get_client_ip(request)
    firebase_user = await get_optional_firebase_user(request)
    firebase_uid = firebase_user.get("uid") if firebase_user else None
    user_plan = get_user_plan(firebase_uid) if firebase_uid else "free"
    status = get_credits_status(
        db=db,
        CreditsTable=CreditsTable,
        user_id=user_id,
        ip_address=client_ip,
        user_plan=user_plan,
    )
    return status


@app.post("/api/credits/admin")
async def set_admin_credits(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    user_id_raw = payload.get("user_id")
    is_admin = payload.get("is_admin", True)

    if not user_id_raw:
        raise HTTPException(status_code=400, detail="'user_id' est requis.")

    set_admin(
        db=db,
        CreditsTable=CreditsTable,
        user_id=int(user_id_raw),
        is_admin=bool(is_admin),
    )
    logger.info(f"[Credits] Admin={'ON' if is_admin else 'OFF'} — user_id={user_id_raw}")
    return {
        "status": "ok",
        "user_id": int(user_id_raw),
        "is_admin": bool(is_admin),
        "message": f"User {user_id_raw} is {'now admin (unlimited)' if is_admin else 'no longer admin'}.",
    }


@app.post("/api/credits/reset")
async def reset_user_credits(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    user_id_raw = payload.get("user_id")
    ip_address = payload.get("ip_address") or get_client_ip(request)

    reset_credits(
        db=db,
        CreditsTable=CreditsTable,
        user_id=int(user_id_raw) if user_id_raw else None,
        ip_address=ip_address,
    )
    return {
        "status": "ok",
        "reset": True,
        "user_id": user_id_raw,
        "ip": ip_address,
    }


# ============================================================
# QUALITY OF LIFE — Endpoints REST
# ============================================================

# ── ALIAS pour compatibilité frontend ──────────────────────
@app.post("/api/quality-life")
async def quality_life_alias(payload: dict = Body(...)):
    """
    Alias de /api/quality-of-life/analyze pour compatibilité frontend.
    Redirige vers l'analyse complète.
    """
    return await analyze_quality_of_life(payload)


@app.post("/api/quality-of-life/analyze")
async def analyze_quality_of_life(payload: dict = Body(...)):
    address = payload.get("address", "").strip()
    if not address:
        raise HTTPException(status_code=400, detail="'address' est requise.")
    try:
        result = analyze_address(address)
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/quality-of-life/analyze")
async def analyze_quality_of_life_get(address: str):
    if not address or not address.strip():
        raise HTTPException(status_code=400, detail="'address' query parameter is required.")
    try:
        result = analyze_address(address.strip())
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/quality-of-life/geocode")
async def geocode(payload: dict = Body(...)):
    address = payload.get("address", "").strip()
    if not address:
        raise HTTPException(status_code=400, detail="'address' est requise.")
    try:
        return geocode_address(address)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/quality-of-life/pois")
async def get_pois(payload: dict = Body(...)):
    lat = payload.get("lat")
    lon = payload.get("lon")
    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="'lat' et 'lon' sont requis.")
    try:
        return fetch_pois(float(lat), float(lon))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/quality-of-life/air-quality")
async def get_air_quality(payload: dict = Body(...)):
    lat = payload.get("lat")
    lon = payload.get("lon")
    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="'lat' et 'lon' sont requis.")
    try:
        return fetch_air_quality(float(lat), float(lon))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/quality-of-life/score-only")
async def get_score_only(payload: dict = Body(...)):
    try:
        return calculate_quality_score(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/quality-of-life/config")
def get_qol_config():
    return {
        "status": "active",
        "features": ["geocoding", "pois", "air_quality", "score"],
    }


# ============================================================
# HUMAN EVALUATION — Endpoints REST
# ============================================================
@app.get("/api/evaluation/pending")
def get_pending():
    return get_pending_interactions()


@app.get("/api/evaluation/interaction/{interaction_id}")
def get_interaction(interaction_id: str):
    details = get_interaction_details(interaction_id)
    if not details:
        raise HTTPException(status_code=404, detail="Interaction non trouvée.")
    return details


@app.post("/api/evaluation/submit/{interaction_id}")
def submit_evaluation(interaction_id: str, payload: dict = Body(...)):
    try:
        save_human_evaluation(interaction_id=interaction_id, **payload)
        return {"status": "ok", "interaction_id": interaction_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/evaluation/stats")
def evaluation_stats():
    return get_evaluation_stats()


@app.get("/api/evaluation/export")
def evaluation_export():
    return export_evaluations_csv()


@app.get("/api/evaluation/criteria")
def evaluation_criteria():
    return EVALUATION_CRITERIA


# ============================================================
# RAG EVALUATION — Endpoints REST
# ============================================================
@app.post("/api/rag-eval/run")
async def rag_eval_run(payload: dict = Body(...)):
    question = payload.get("question", "").strip()
    answer = payload.get("answer", "").strip()
    sources = payload.get("sources", [])
    property_type = payload.get("property_type", "unknown")
    latency_ms = int(payload.get("latency_ms", 0))

    if not question or not answer:
        raise HTTPException(
            status_code=400,
            detail="'question' et 'answer' sont requis."
        )

    try:
        raw_docs = [
            {
                "text": s.get("content", s.get("text", "")),
                "index": s.get("index", ""),
                "score": s.get("score", 0.0),
                "metadata": s.get("metadata", {}),
            }
            for s in sources
        ]

        metrics, run_uri = rag_evaluator.evaluate_and_log(
            question=question,
            answer=answer,
            docs=raw_docs,
            latency_ms=latency_ms,
            property_type=property_type,
            run_name=f"manual_eval_{property_type}",
        )
        composite = rag_evaluator._composite_score(metrics)

        return {
            "status": "success",
            "mlflow_run": run_uri,
            "mlflow_ui": MLFLOW_TRACKING_UI_URL,
            "composite_score": composite,
            "metrics": {
                "answer_relevance": metrics.answer_relevance,
                "faithfulness": metrics.faithfulness,
                "citation_coverage": metrics.citation_coverage,
                "citation_count": metrics.citation_count,
                "confidence_level": metrics.confidence_level,
                "confidence_score": metrics.confidence_score,
                "response_completeness": metrics.response_completeness,
                "response_length": metrics.response_length,
                "grounding_score": metrics.grounding_score,
                "hallucination_flag": bool(metrics.hallucination_flag),
                "hallucination_detail": metrics.hallucination_detail,
                "context_utilization": metrics.context_utilization,
                "is_refusal": bool(metrics.is_refusal),
                "retrieval_avg_score": metrics.retrieval_avg_score,
                "retrieval_top1_score": metrics.retrieval_top1_score,
                "retrieval_docs_count": metrics.retrieval_docs_count,
                "chunk_diversity": metrics.chunk_diversity,
                "latency_ms": metrics.latency_ms,
            },
        }

    except Exception as e:
        traceback.print_exc()
        logger.error(f"[RAGEval] Erreur : {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/rag-eval/mlflow")
def rag_eval_mlflow_info():
    return {
        "status": "active",
        "tracking_uri": MLFLOW_TRACKING_URI,
        "ui_url": MLFLOW_TRACKING_UI_URL,
        "experiment_name": "PropIQ_RAG_Evaluation",
    }


# ============================================================
# MODELS — Liste des modèles disponibles
# ============================================================
@app.get("/api/models")
def get_available_models():
    return {
        "default": LLM_MODEL,
        "models": [
            {
                "id": "mistralai/mistral-large-2512",
                "label": "Mistral Large",
                "description": "Précision juridique élevée · Recommandé",
                "badge": "⭐ Recommandé",
            },
            {
                "id": "qwen/qwen3-235b-a22b",
                "label": "Qwen3",
                "description": "Très grand modèle · Réponses détaillées",
                "badge": "🔬 Puissant",
            },
            {
                "id": "openai/gpt-4o",
                "label": "GPT-4o",
                "description": "Modèle compact · Réponses rapides",
                "badge": "⚡ Rapide",
            },
            {
                "id": "meta-llama/llama-3.3-70b-instruct",
                "label": "llama3.3",
                "description": "Modèle open-source avancé optimisé",
                "badge": "🧠 Avancé",
            },
            {
                "id": "meta-llama/llama-3.2-11b-vision-instruct",

                "label": "llama3.2-Vision",
                "description": "Modele rapide",
                "badge": "⚡ High performance",
            },
            {
                "id": "qwen/qwen3-vl-32b-instruct",
                "label": "Qwen3-Vision",
                "description": "Modele rapide",
                "badge": "⚡ High performance",
            },
            {
                "id": "microsoft/phi-4",
                "label": "Phi4",
                "description": "Modele rapide",
                "badge": "⚡ High performance",
            },
        ],
    }


# ============================================================
# SUBSCRIPTION — Choix du plan après login
# ============================================================
@app.get("/api/subscription/plan")
async def get_plan(user: dict = Depends(verify_firebase_token)):
    """
    Retourne le plan actuel de l'utilisateur + ses quotas du jour.

    Headers requis :
        Authorization: Bearer <firebase_id_token>

    Response :
    {
        "uid":   "abc123",
        "plan":  "free",
        "limits": { "requests_per_day": 10, ... },
        "usage":  { "requests": 3, "images": 0, "pdfs": 1 },
        "remaining": { "requests": 7, "images": 1, "pdfs": 0 }
    }
    """
    uid = user["uid"]
    plan = get_user_plan(uid)
    usage = get_today_usage(uid)
    limits = PLANS[plan]

    remaining = {
        "requests": max(0, limits["requests_per_day"] - usage.get("requests", 0)),
        "images": max(0, limits["images_per_day"] - usage.get("images", 0)),
        "pdfs": max(0, limits["pdfs_per_day"] - usage.get("pdfs", 0)),
    }

    return {
        "uid": uid,
        "plan": plan,
        "limits": {
            "requests_per_day": limits["requests_per_day"],
            "images_per_day": limits["images_per_day"],
            "pdfs_per_day": limits["pdfs_per_day"],
            "price": limits["price"],
            "currency": limits.get("currency", ""),
        },
        "usage": usage,
        "remaining": remaining,
    }


@app.post("/api/subscription/select-plan")
async def select_plan(
    payload: dict = Body(...),
    user: dict = Depends(verify_firebase_token),
):
    """
    L'utilisateur choisit son plan après login.

    Body JSON :
    { "plan": "free" }   ← accès direct
    { "plan": "premium" } ← retourne un lien de paiement

    Response (free) :
    { "plan": "free", "status": "activated" }

    Response (premium) :
    {
        "plan":        "premium",
        "status":      "payment_required",
        "payment_url": "https://preprod.konnect.network/...",
        "payment_ref": "abc123"
    }
    """
    uid = user["uid"]
    email = user.get("email", "")
    plan_req = payload.get("plan", "").lower()

    if plan_req not in ("free", "premium"):
        raise HTTPException(
            status_code=400,
            detail="Plan invalide. Valeurs acceptées : 'free' ou 'premium'."
        )

    # ── Plan Free : activation immédiate ────────────────────
    if plan_req == "free":
        set_user_plan(uid, "free")
        logger.info(f"[Subscription] Plan Free activé — uid={uid}")
        return {
            "plan": "free",
            "status": "activated",
            "message": "Plan gratuit activé. Bonne utilisation !",
        }

    # ── Plan Premium : création du paiement ─────────────────
    payment = await create_payment(uid=uid, email=email)
    logger.info(
        f"[Subscription] Paiement Premium initié — "
        f"uid={uid} | ref={payment['payment_ref']}"
    )
    return {
        "plan": "premium",
        "status": "payment_required",
        "payment_url": payment["payment_url"],
        "payment_ref": payment["payment_ref"],
        "message": "Complétez le paiement pour activer le plan Premium.",
    }


# ============================================================
# SUBSCRIPTION — Webhook Konnect (confirmation paiement)
# ============================================================
@app.post("/api/payment/webhook")
async def payment_webhook(request: Request):
    """
    Webhook appelé par Konnect après un paiement.
    Active automatiquement le plan Premium si paiement réussi.

    Konnect envoie :
    {
        "payment_ref": "abc123",
        "order_id":    "uid_utilisateur",
        "status":      "completed"
    }
    """
    try:
        body = await request.json()
        logger.info(f"[Webhook] Payload reçu : {body}")

        payment_ref = body.get("payment_ref") or body.get("paymentRef")
        uid = body.get("order_id") or body.get("orderId")
        body.get("status", "").lower()

        if not payment_ref or not uid:
            logger.warning("[Webhook] ⚠️  Champs manquants (payment_ref / order_id)")
            return {"status": "ignored"}

        # ── Vérification côté Konnect (double-check) ────────
        verification = await verify_payment(payment_ref)
        verified_status = verification["status"].lower()

        if verified_status == "completed":
            set_user_plan(uid, "premium", payment_ref=payment_ref)
            logger.info(
                f"[Webhook] ✅ Premium activé — uid={uid} | ref={payment_ref}"
            )
            return {"status": "premium_activated", "uid": uid}

        logger.warning(
            f"[Webhook] ⚠️  Paiement non complété — "
            f"uid={uid} | status={verified_status}"
        )
        return {"status": "payment_not_completed", "payment_status": verified_status}

    except Exception as e:
        logger.error(f"[Webhook] ❌ Erreur : {e}")
        return {"status": "error", "detail": str(e)}


# ============================================================
# SUBSCRIPTION — Vérification manuelle du paiement (Flutter)
# ============================================================
@app.get("/api/payment/verify/{payment_ref}")
async def verify_payment_endpoint(
    payment_ref: str,
    user: dict = Depends(verify_firebase_token),
):
    """
    Vérifie manuellement le statut d'un paiement.
    Appelé par Flutter sur la page de retour après paiement.

    Si paiement complété → active le plan Premium automatiquement.

    Headers requis :
        Authorization: Bearer <firebase_id_token>

    Response :
    {
        "payment_status": "completed",
        "plan_activated": true,
        "plan":           "premium"
    }
    """
    uid = user["uid"]
    verification = await verify_payment(payment_ref)
    status = verification["status"].lower()

    if status == "completed":
        set_user_plan(uid, "premium", payment_ref=payment_ref)
        logger.info(
            f"[PayVerify] ✅ Premium activé manuellement — uid={uid} | ref={payment_ref}"
        )
        return {
            "payment_status": status,
            "plan_activated": True,
            "plan": "premium",
            "message": "Plan Premium activé avec succès !",
        }

    return {
        "payment_status": status,
        "plan_activated": False,
        "plan": get_user_plan(uid),
        "message": f"Paiement en statut '{status}'. Réessayez.",
    }


# ============================================================
# HEALTH CHECK
# ============================================================
@app.get("/api/health")
def health_check():
    pending_count = len(get_pending_interactions())
    return {
        "status": "ok",
        "version": "2.4.0",
        "mode": "openrouter",
        "model": LLM_MODEL,
        "embeddings_loaded": embeddings is not None,
        "llm_client_ready": llm_client is not None,
        "rag_evaluator_ready": rag_evaluator is not None,
        "openrouter_url": OPENROUTER_BASE_URL,
        "mlflow_uri": MLFLOW_TRACKING_URI,
        "mlflow_ui": MLFLOW_TRACKING_UI_URL,
        "evaluation_mode": "human_manual + rag_automatic",
        "pending_evaluations": pending_count,
        "quality_of_life_api": "active",
        "voice_chat": "active (Whisper local)",
        "document_analysis": "active (Image/PDF → LLM Vision)",
        "credits_config": CREDITS_CONFIG,
        "endpoints": {
            "chat": "POST /api/chat",
            "voice_chat": "POST /api/voice-chat",
            "upload_document": "POST /api/upload-document",
            "history": "GET  /api/history/{user_id}",
            "history_delete": "DELETE /api/history/{history_id}",
            "credits_status": "GET  /api/credits/status?user_id=...",
            "credits_admin": "POST /api/credits/admin",
            "credits_reset": "POST /api/credits/reset",
            "eval_pending": "GET  /api/evaluation/pending",
            "eval_interaction": "GET  /api/evaluation/interaction/{id}",
            "eval_submit": "POST /api/evaluation/submit/{id}",
            "eval_stats": "GET  /api/evaluation/stats",
            "eval_export": "GET  /api/evaluation/export",
            "eval_criteria": "GET  /api/evaluation/criteria",
            "rag_eval_run": "POST /api/rag-eval/run",
            "rag_eval_mlflow": "GET  /api/rag-eval/mlflow",
            "qol_analyze_post": "POST /api/quality-of-life/analyze",
            "qol_analyze_get": "GET  /api/quality-of-life/analyze?address=...",
            "qol_alias": "POST /api/quality-life",
            "qol_geocode": "POST /api/quality-of-life/geocode",
            "qol_pois": "POST /api/quality-of-life/pois",
            "qol_air": "POST /api/quality-of-life/air-quality",
            "qol_score": "POST /api/quality-of-life/score-only",
            "qol_config": "GET  /api/quality-of-life/config",
            "register": "POST /api/auth/register",
            "login": "POST /api/auth/login",
            "check_email": "GET  /api/auth/check-email?email=...",
            "firebase_verify": "GET  /api/auth/firebase/verify  [Authorization: Bearer <token>]",
            "models": "GET  /api/models",
        },
    }


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",  # nosec B104
        port=8000,
        reload=True,
        log_level="info",
    )
