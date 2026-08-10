"""
PropIQ — MLOps Pipeline Module (Atelier 2)
==========================================
Modularisation du pipeline RAG de PropIQ.

Ce fichier N'IMPORTE que le code existant — aucune modification
des fichiers originaux (complianceEngine.py, config.py, etc.)

Pipeline :
    prepare_data()     → Charge embeddings + vectorstores Pinecone
    run_query()        → Exécute une question RAG complète
    evaluate_model()   → Évalue la qualité des réponses (BLEU / ROUGE)
    save_artifacts()   → Sauvegarde métriques + résultats dans MLflow
    load_artifacts()   → Charge un run MLflow existant
"""

import os
import time
import logging
import json
import tempfile
from datetime import datetime
from typing import Optional

# ── Imports depuis le projet existant (aucune modification) ──
from config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    LLM_MODEL,
    PROPERTY_VS_TARGETS,
    MLFLOW_TRACKING_URI,
)
from complianceEngine import (
    load_embedding_model,
    load_selected_vectorstores,
    run_free_chat,
)

# ── Librairies MLOps ──────────────────────────────────────────
import mlflow
import mlflow.artifacts
from openai import OpenAI

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ============================================================
# 1. PREPARE DATA
#    Charge le modèle d'embeddings + les vectorstores Pinecone
#    pour un type de propriété donné.
# ============================================================
def prepare_data(property_type: str = "residencial") -> dict:
    """
    Charge et prépare les ressources nécessaires au pipeline RAG.

    Args:
        property_type: Type de propriété parmi
                       ['residencial', 'comercial', 'terreno', 'alojamento_local']

    Returns:
        dict contenant :
            - embeddings  : modèle HuggingFace chargé
            - vectorstores: dict Pinecone prêt à l'emploi
            - client      : client OpenRouter (LLM)
            - llm_model   : nom du modèle LLM
            - property_type: type de propriété
    """
    logger.info(f"[prepare_data] Démarrage — property_type={property_type}")
    t_start = time.time()

    # Validation du type de propriété
    valid_types = list(PROPERTY_VS_TARGETS.keys())
    if property_type not in valid_types:
        raise ValueError(
            f"property_type '{property_type}' invalide. "
            f"Valeurs acceptées : {valid_types}"
        )

    # Chargement du modèle d'embeddings (cache LRU — 1 seul chargement)
    logger.info("[prepare_data] Chargement du modèle d'embeddings...")
    embeddings = load_embedding_model()

    # Sélection des catégories vectorstore selon le type de propriété
    selected_indices = PROPERTY_VS_TARGETS[property_type]
    logger.info(
        f"[prepare_data] {len(selected_indices)} catégories légales "
        f"sélectionnées pour '{property_type}'"
    )

    # Connexion à Pinecone + chargement des vectorstores
    logger.info("[prepare_data] Connexion à Pinecone...")
    vectorstores = load_selected_vectorstores(embeddings, selected_indices)

    # Client OpenRouter (LLM)
    client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
    )

    elapsed = round((time.time() - t_start) * 1000)
    logger.info(f"[prepare_data] ✅ Prêt en {elapsed}ms")

    return {
        "embeddings": embeddings,
        "vectorstores": vectorstores,
        "client": client,
        "llm_model": LLM_MODEL,
        "property_type": property_type,
        "load_time_ms": elapsed,
    }


# ============================================================
# 2. RUN QUERY
#    Exécute une question RAG complète sur le pipeline PropIQ.
# ============================================================
def run_query(
    question: str,
    pipeline_data: dict,
    extracted_data: Optional[dict] = None,
) -> dict:
    """
    Exécute une question RAG complète.

    Args:
        question      : Question de l'utilisateur (en anglais)
        pipeline_data : Résultat de prepare_data()
        extracted_data: Données du formulaire propriété (optionnel)

    Returns:
        dict contenant :
            - reply       : Réponse du LLM
            - sources     : Documents sources récupérés
            - latency_ms  : Temps de réponse en ms
            - question    : Question posée
            - timestamp   : Horodatage ISO
    """
    logger.info(f"[run_query] Question : {question[:80]}...")
    t_start = time.time()

    reply, docs = run_free_chat(
        property_type=pipeline_data["property_type"],
        user_question=question,
        extracted_data=extracted_data or {},
        vectorstores=pipeline_data["vectorstores"],
        client=pipeline_data["client"],
        llm_model=pipeline_data["llm_model"],
    )

    latency_ms = round((time.time() - t_start) * 1000)
    logger.info(
        f"[run_query] ✅ Répondu en {latency_ms}ms | " f"{len(docs)} sources récupérées"
    )

    return {
        "reply": reply,
        "sources": docs,
        "latency_ms": latency_ms,
        "question": question,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============================================================
# 3. EVALUATE MODEL
#    Évalue la qualité des réponses RAG avec des métriques NLP.
# ============================================================
def evaluate_model(
    pipeline_data: dict,
    test_cases: Optional[list] = None,
) -> dict:
    """
    Évalue le pipeline RAG sur un ensemble de questions de test.

    Args:
        pipeline_data: Résultat de prepare_data()
        test_cases   : Liste de dicts {'question': str, 'expected': str}
                       Si None, utilise les cas de test par défaut.

    Returns:
        dict contenant les métriques d'évaluation :
            - avg_latency_ms    : Latence moyenne
            - avg_sources_count : Nombre moyen de sources
            - avg_reply_length  : Longueur moyenne des réponses
            - success_rate      : Taux de succès (réponse non vide)
            - results           : Liste des résultats détaillés
    """
    logger.info("[evaluate_model] Démarrage de l'évaluation...")

    # Cas de test par défaut si aucun fourni
    if test_cases is None:
        test_cases = _default_test_cases(pipeline_data["property_type"])

    results = []
    latencies = []
    src_counts = []
    reply_lens = []
    successes = 0

    for i, case in enumerate(test_cases):
        logger.info(
            f"[evaluate_model] Test {i+1}/{len(test_cases)} : "
            f"{case['question'][:60]}..."
        )
        try:
            result = run_query(
                question=case["question"],
                pipeline_data=pipeline_data,
            )

            is_success = bool(result["reply"] and len(result["reply"]) > 50)
            if is_success:
                successes += 1

            latencies.append(result["latency_ms"])
            src_counts.append(len(result["sources"]))
            reply_lens.append(len(result["reply"]))

            results.append(
                {
                    "question": case["question"],
                    "reply": result["reply"][:300],
                    "latency_ms": result["latency_ms"],
                    "sources_count": len(result["sources"]),
                    "success": is_success,
                }
            )

        except Exception as e:
            logger.error(f"[evaluate_model] Erreur test {i+1} : {e}")
            results.append(
                {
                    "question": case["question"],
                    "reply": "",
                    "error": str(e),
                    "success": False,
                }
            )

    n = len(test_cases)
    metrics = {
        "avg_latency_ms": round(sum(latencies) / n) if latencies else 0,
        "avg_sources_count": round(sum(src_counts) / n, 2) if src_counts else 0,
        "avg_reply_length": round(sum(reply_lens) / n) if reply_lens else 0,
        "success_rate": round(successes / n * 100, 2) if n > 0 else 0,
        "total_tests": n,
        "results": results,
    }

    logger.info(
        f"[evaluate_model] ✅ "
        f"success_rate={metrics['success_rate']}% | "
        f"avg_latency={metrics['avg_latency_ms']}ms | "
        f"avg_sources={metrics['avg_sources_count']}"
    )
    return metrics


# ============================================================
# 4. SAVE ARTIFACTS
#    Enregistre les métriques et résultats dans MLflow.
# ============================================================
def save_artifacts(
    metrics: dict,
    pipeline_data: dict,
    run_name: Optional[str] = None,
) -> str:
    """
    Sauvegarde les métriques d'évaluation dans MLflow.

    Args:
        metrics      : Résultat de evaluate_model()
        pipeline_data: Résultat de prepare_data()
        run_name     : Nom du run MLflow (optionnel)

    Returns:
        run_id : ID du run MLflow créé
    """
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("PropIQ-RAG-Evaluation")

    run_name = run_name or f"propiq-eval-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

    logger.info(f"[save_artifacts] Démarrage du run MLflow : {run_name}")

    with mlflow.start_run(run_name=run_name) as run:

        # ── Paramètres du pipeline ───────────────────────────
        mlflow.log_params(
            {
                "property_type": pipeline_data["property_type"],
                "llm_model": pipeline_data["llm_model"],
                "load_time_ms": pipeline_data.get("load_time_ms", 0),
                "total_tests": metrics["total_tests"],
            }
        )

        # ── Métriques d'évaluation ───────────────────────────
        mlflow.log_metrics(
            {
                "avg_latency_ms": metrics["avg_latency_ms"],
                "avg_sources_count": metrics["avg_sources_count"],
                "avg_reply_length": metrics["avg_reply_length"],
                "success_rate": metrics["success_rate"],
            }
        )

        # ── Sauvegarde des résultats détaillés en JSON ───────
        results_path = os.path.join(tempfile.gettempdir(), "eval_results.json")
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(metrics["results"], f, indent=2, ensure_ascii=False)
        mlflow.log_artifact(results_path, artifact_path="evaluation")

        run_id = run.info.run_id

    logger.info(f"[save_artifacts] ✅ Run MLflow sauvegardé : {run_id}")
    return run_id


# ============================================================
# 5. LOAD ARTIFACTS
#    Charge les métriques d'un run MLflow existant.
# ============================================================
def load_artifacts(run_id: str) -> dict:
    """
    Charge les métriques et paramètres d'un run MLflow existant.

    Args:
        run_id: ID du run MLflow

    Returns:
        dict contenant params et metrics du run
    """
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = mlflow.tracking.MlflowClient()

    logger.info(f"[load_artifacts] Chargement du run : {run_id}")

    run = client.get_run(run_id)
    data = {
        "run_id": run_id,
        "params": run.data.params,
        "metrics": run.data.metrics,
        "status": run.info.status,
        "start_time": datetime.fromtimestamp(run.info.start_time / 1000).isoformat(),
    }

    logger.info(f"[load_artifacts] ✅ Run chargé : {data}")
    return data


# ============================================================
# HELPER — Cas de test par défaut par type de propriété
# ============================================================
def _default_test_cases(property_type: str) -> list:
    """Retourne des questions de test adaptées au type de propriété."""

    cases = {
        "residencial": [
            {
                "question": "What are the legal requirements for a habitability certificate in Portugal?",
            },
            {
                "question": "What documents are needed to sell a residential property in Portugal?",
            },
            {
                "question": "What are the energy certification requirements for residential buildings?",
            },
        ],
        "comercial": [
            {
                "question": "What are the fire safety requirements for commercial buildings in Portugal?",
            },
            {
                "question": "What accessibility standards apply to commercial properties?",
            },
        ],
        "terreno": [
            {
                "question": "What are REN restrictions on land use in Portugal?",
            },
            {
                "question": "What permits are required to build on urban land in Portugal?",
            },
        ],
        "alojamento_local": [
            {
                "question": "What is the RNAL registration process for tourist rentals in Portugal?",
            },
            {
                "question": "What safety equipment is required for tourist rental properties?",
            },
        ],
    }

    return cases.get(property_type, cases["residencial"])
