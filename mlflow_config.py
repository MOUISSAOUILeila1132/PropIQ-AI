"""
PropIQ — MLflow Configuration & Tracking (Atelier 5)
=====================================================
Centralise toute la configuration MLflow pour PropIQ.

Ce fichier N'IMPORTE que le code existant — aucune modification
des fichiers originaux.

Usage depuis le terminal :
    python mlflow_config.py --start-server
    python mlflow_config.py --run-eval
    python mlflow_config.py --run-eval --type comercial
    python mlflow_config.py --list-runs
    python mlflow_config.py --show-run <run_id>
"""

import os
import json
import logging
import argparse
import time
import tempfile
from datetime import datetime
from typing import Optional

# ── MLflow ────────────────────────────────────────────────────
import mlflow
import mlflow.artifacts
from mlflow.tracking import MlflowClient

# ── Imports depuis le projet existant ────────────────────────
from config import (
    MLFLOW_TRACKING_URI,
    MLFLOW_TRACKING_UI_URL,
    LLM_MODEL,
    EMBEDDING_MODEL,
    PINECONE_INDEX_NAME,
    TOP_K,
)

# ── Imports depuis les fichiers MLOps (Atelier 2) ────────────
from model_pipeline import (
    prepare_data,
    evaluate_model,
    load_artifacts,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

# ============================================================
# CONSTANTES MLFLOW
# ============================================================
EXPERIMENT_NAME = "PropIQ-RAG-Evaluation"
MODEL_NAME = "PropIQ-RAG-Pipeline"
ARTIFACT_PATH = "propiq-artifacts"


# ============================================================
# 1. SETUP MLFLOW
#    Configure le tracking URI et crée l'expérience si besoin.
# ============================================================
def setup_mlflow() -> MlflowClient:
    """
    Configure MLflow et retourne un client prêt à l'emploi.

    Returns:
        MlflowClient configuré
    """
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    logger.info(f"[MLflow] Tracking URI : {MLFLOW_TRACKING_URI}")

    # Créer l'expérience si elle n'existe pas
    experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
    if experiment is None:
        exp_id = mlflow.create_experiment(
            name=EXPERIMENT_NAME,
            artifact_location="./mlruns",
            tags={
                "project": "PropIQ",
                "domain": "Real Estate Legal RAG",
                "language": "Portuguese Law",
                "framework": "LangChain + Pinecone",
            },
        )
        logger.info(f"[MLflow] Expérience créée : {EXPERIMENT_NAME} (id={exp_id})")
    else:
        logger.info(
            f"[MLflow] Expérience existante : {EXPERIMENT_NAME} "
            f"(id={experiment.experiment_id})"
        )

    mlflow.set_experiment(EXPERIMENT_NAME)
    return MlflowClient()


# ============================================================
# 2. LOG FULL EVALUATION RUN
#    Lance une évaluation complète et logue tout dans MLflow.
# ============================================================
def log_evaluation_run(
    property_type: str = "residencial",
    run_name: Optional[str] = None,
    extra_params: Optional[dict] = None,
) -> str:
    """
    Lance une évaluation complète du pipeline PropIQ
    et enregistre tous les résultats dans MLflow.

    Args:
        property_type : Type de propriété à évaluer
        run_name      : Nom du run (auto-généré si None)
        extra_params  : Paramètres supplémentaires à logger

    Returns:
        run_id : ID du run MLflow créé
    """
    setup_mlflow()
    run_name = run_name or (
        f"propiq-{property_type}-" f"{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    )

    logger.info(f"[MLflow] Démarrage du run : {run_name}")

    with mlflow.start_run(run_name=run_name) as run:
        run_id = run.info.run_id

        # ── Tags du run ──────────────────────────────────────
        mlflow.set_tags(
            {
                "property_type": property_type,
                "project": "PropIQ",
                "env": os.getenv("ENV", "development"),
                "author": os.getenv("USER", "propiq-team"),
            }
        )

        # ── Étape 1 : Prepare data ───────────────────────────
        logger.info("[MLflow] Étape 1 — Chargement du pipeline...")
        t_prepare = time.time()
        pipeline_data = prepare_data(property_type=property_type)
        prepare_time = round((time.time() - t_prepare) * 1000)

        # ── Log des paramètres du pipeline ───────────────────
        mlflow.log_params(
            {
                # Modèles
                "llm_model": pipeline_data["llm_model"],
                "embedding_model": EMBEDDING_MODEL,
                "pinecone_index": PINECONE_INDEX_NAME,
                # Paramètres RAG
                "top_k": TOP_K,
                "property_type": property_type,
                # Temps
                "prepare_time_ms": prepare_time,
            }
        )

        # Paramètres supplémentaires optionnels
        if extra_params:
            mlflow.log_params(extra_params)

        # ── Étape 2 : Évaluation ─────────────────────────────
        logger.info("[MLflow] Étape 2 — Évaluation du pipeline...")
        t_eval = time.time()
        metrics = evaluate_model(pipeline_data=pipeline_data)
        eval_time = round((time.time() - t_eval) * 1000)

        # ── Log des métriques d'évaluation ───────────────────
        mlflow.log_metrics(
            {
                "avg_latency_ms": metrics["avg_latency_ms"],
                "avg_sources_count": metrics["avg_sources_count"],
                "avg_reply_length": metrics["avg_reply_length"],
                "success_rate": metrics["success_rate"],
                "total_tests": metrics["total_tests"],
                "eval_time_ms": eval_time,
                "prepare_time_ms": prepare_time,
            }
        )

        # ── Log des artefacts ─────────────────────────────────
        tmp_dir = tempfile.gettempdir()

        # 1. Résultats détaillés JSON
        results_path = os.path.join(tmp_dir, "propiq_eval_results.json")
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(metrics["results"], f, indent=2, ensure_ascii=False)
        mlflow.log_artifact(results_path, artifact_path="evaluation")

        # 2. Résumé des métriques JSON
        summary = {
            "run_id": run_id,
            "run_name": run_name,
            "property_type": property_type,
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {k: v for k, v in metrics.items() if k != "results"},
            "params": {
                "llm_model": pipeline_data["llm_model"],
                "embedding_model": EMBEDDING_MODEL,
                "top_k": TOP_K,
            },
        }
        summary_path = os.path.join(tmp_dir, "propiq_eval_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        mlflow.log_artifact(summary_path, artifact_path="evaluation")

        # 3. Config complète
        config_info = {
            "llm_model": LLM_MODEL,
            "embedding_model": EMBEDDING_MODEL,
            "pinecone_index": PINECONE_INDEX_NAME,
            "top_k": TOP_K,
            "tracking_uri": MLFLOW_TRACKING_URI,
            "experiment": EXPERIMENT_NAME,
        }
        config_path = os.path.join(tmp_dir, "propiq_config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_info, f, indent=2, ensure_ascii=False)
        mlflow.log_artifact(config_path, artifact_path="config")

    logger.info(
        f"[MLflow] ✅ Run terminé : {run_id}\n"
        f"         success_rate={metrics['success_rate']}% | "
        f"avg_latency={metrics['avg_latency_ms']}ms\n"
        f"         UI : {MLFLOW_TRACKING_UI_URL}"
    )

    return run_id


# ============================================================
# 3. LIST RUNS
#    Liste les derniers runs de l'expérience.
# ============================================================
def list_runs(n: int = 10) -> list:
    """
    Liste les derniers runs de l'expérience PropIQ.

    Args:
        n : Nombre de runs à afficher

    Returns:
        Liste des runs
    """
    client = setup_mlflow()

    experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
    if experiment is None:
        logger.warning(f"[MLflow] Expérience '{EXPERIMENT_NAME}' introuvable.")
        return []

    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=["start_time DESC"],
        max_results=n,
    )

    print(f"\n{'='*70}")
    print(f"  📋 Derniers runs — {EXPERIMENT_NAME}")
    print(f"{'='*70}")
    print(f"  {'RUN ID':<32} {'NOM':<30} " f"{'SUCCESS':>8} {'LATENCY':>10}")
    print(f"  {'-'*70}")

    for r in runs:
        run_id = r.info.run_id[:8] + "..."
        name = (r.info.run_name or "")[:28]
        success_rate = r.data.metrics.get("success_rate", 0)
        latency = r.data.metrics.get("avg_latency_ms", 0)
        print(f"  {run_id:<32} {name:<30} " f"{success_rate:>7.1f}% {latency:>9.0f}ms")

    print(f"{'='*70}\n")
    return runs


# ============================================================
# 4. SHOW RUN
#    Affiche les détails d'un run spécifique.
# ============================================================
def show_run(run_id: str):
    """
    Affiche les détails complets d'un run MLflow.

    Args:
        run_id : ID du run MLflow
    """
    data = load_artifacts(run_id=run_id)

    print(f"\n{'='*55}")
    print(f"  📊 Détails du run : {run_id[:16]}...")
    print(f"{'='*55}")

    print(f"\n  📅 Démarré  : {data['start_time']}")
    print(f"  ✅ Status   : {data['status']}")

    print("\n  ⚙️  Paramètres :")
    for k, v in data["params"].items():
        print(f"    • {k:<25} = {v}")

    print("\n  📈 Métriques :")
    for k, v in data["metrics"].items():
        print(f"    • {k:<25} = {v}")

    print(f"\n  🌐 Voir dans MLflow UI : {MLFLOW_TRACKING_UI_URL}\n")


# ============================================================
# 5. START SERVER
#    Lance le serveur MLflow UI.
# ============================================================
def start_mlflow_server():
    """Lance le serveur MLflow UI."""
    import subprocess

    port = MLFLOW_TRACKING_UI_URL.split(":")[-1]

    # 0.0.0.0 est nécessaire pour exposer MLflow hors du conteneur Docker
    # (voir docker-compose.yml). Usage volontaire, pas une faille.
    mlflow_host = os.getenv("MLFLOW_SERVER_HOST", "0.0.0.0")  # nosec B104

    cmd = [
        "mlflow",
        "server",
        "--backend-store-uri",
        MLFLOW_TRACKING_URI,
        "--default-artifact-root",
        "./mlruns",
        "--host",
        mlflow_host,
        "--port",
        port,
    ]

    print(f"\n🌐 Lancement MLflow UI sur {MLFLOW_TRACKING_UI_URL}")
    print(f"   Commande : {' '.join(cmd)}\n")

    subprocess.run(cmd, shell=False, check=False)


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="PropIQ MLflow Tracking CLI",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "--start-server",
        action="store_true",
        help="Lancer le serveur MLflow UI",
    )
    parser.add_argument(
        "--run-eval",
        action="store_true",
        help="Lancer une évaluation complète et logger dans MLflow",
    )
    parser.add_argument(
        "--list-runs",
        action="store_true",
        help="Lister les derniers runs MLflow",
    )
    parser.add_argument(
        "--show-run",
        type=str,
        metavar="RUN_ID",
        help="Afficher les détails d'un run spécifique",
    )
    parser.add_argument(
        "--type",
        type=str,
        default="residencial",
        choices=["residencial", "comercial", "terreno", "alojamento_local"],
        help="Type de propriété (défaut: residencial)",
    )

    args = parser.parse_args()

    if args.start_server:
        start_mlflow_server()

    elif args.run_eval:
        run_id = log_evaluation_run(property_type=args.type)
        print(f"\n  ✅ Run ID : {run_id}")
        print(f"  🌐 UI     : {MLFLOW_TRACKING_UI_URL}\n")

    elif args.list_runs:
        list_runs()

    elif args.show_run:
        show_run(args.show_run)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
