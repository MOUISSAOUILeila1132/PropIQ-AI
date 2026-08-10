"""
PropIQ — Monitoring Module (Atelier 7)
=======================================
Envoie les logs et métriques de PropIQ vers Elasticsearch
pour visualisation dans Kibana.

Ce fichier N'IMPORTE que le code existant — aucune modification
des fichiers originaux.

Indices Elasticsearch créés :
    propiq-rag-logs      → logs des questions/réponses RAG
    propiq-mlflow-metrics → métriques MLflow exportées
    propiq-system-logs   → santé du système (CPU, RAM, etc.)

Usage :
    python monitoring.py --test-connection
    python monitoring.py --send-mlflow-metrics
    python monitoring.py --monitor-system
    python monitoring.py --setup-kibana
"""

import os
import time
import logging
import argparse
import platform
from datetime import datetime, timezone
from typing import Optional

# ── Elasticsearch ─────────────────────────────────────────────
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError as ESConnectionError

# ── MLflow ────────────────────────────────────────────────────
import mlflow
from mlflow.tracking import MlflowClient

# ── Imports depuis le projet existant ─────────────────────────
from config import (
    MLFLOW_TRACKING_URI,
    LLM_MODEL,
    EMBEDDING_MODEL,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

# ============================================================
# CONSTANTES
# ============================================================
ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
INDEX_RAG_LOGS = "propiq-rag-logs"
INDEX_MLFLOW = "propiq-mlflow-metrics"
INDEX_SYSTEM = "propiq-system-logs"


# ============================================================
# 1. CONNEXION ELASTICSEARCH
# ============================================================
def connect_elasticsearch() -> Optional[Elasticsearch]:
    """
    Crée et teste la connexion à Elasticsearch.

    Returns:
        Client Elasticsearch ou None si connexion échouée
    """
    try:
        es = Elasticsearch(
            ES_URL,
            request_timeout=10,
            retry_on_timeout=True,
            max_retries=3,
        )
        info = es.info()
        logger.info(
            "[ES] ✅ Connecté à Elasticsearch "
            f"v{info['version']['number']} — {ES_URL}"
        )
        return es

    except ESConnectionError:
        logger.error(
            f"[ES] ❌ Impossible de se connecter à {ES_URL}\n"
            "   → Vérifie que Elasticsearch est démarré :\n"
            "     docker-compose up -d elasticsearch"
        )
        return None
    except Exception as e:
        logger.error(f"[ES] ❌ Erreur connexion : {e}")
        return None


# ============================================================
# 2. CRÉER LES INDEX ELASTICSEARCH
# ============================================================
def create_indices(es: Elasticsearch):
    """
    Crée les index Elasticsearch avec les mappings appropriés.
    Si les index existent déjà, ne fait rien.
    """

    # ── Index RAG Logs ────────────────────────────────────────
    rag_mapping = {
        "mappings": {
            "properties": {
                "timestamp": {"type": "date"},
                "property_type": {"type": "keyword"},
                "question": {"type": "text"},
                "reply_length": {"type": "integer"},
                "latency_ms": {"type": "integer"},
                "sources_count": {"type": "integer"},
                "success": {"type": "boolean"},
                "llm_model": {"type": "keyword"},
                "top_score": {"type": "float"},
                "avg_score": {"type": "float"},
            }
        }
    }

    # ── Index MLflow Metrics ──────────────────────────────────
    mlflow_mapping = {
        "mappings": {
            "properties": {
                "timestamp": {"type": "date"},
                "run_id": {"type": "keyword"},
                "run_name": {"type": "keyword"},
                "property_type": {"type": "keyword"},
                "success_rate": {"type": "float"},
                "avg_latency_ms": {"type": "float"},
                "avg_sources_count": {"type": "float"},
                "avg_reply_length": {"type": "float"},
                "total_tests": {"type": "integer"},
                "llm_model": {"type": "keyword"},
                "embedding_model": {"type": "keyword"},
                "status": {"type": "keyword"},
            }
        }
    }

    # ── Index System Logs ─────────────────────────────────────
    system_mapping = {
        "mappings": {
            "properties": {
                "timestamp": {"type": "date"},
                "cpu_percent": {"type": "float"},
                "ram_percent": {"type": "float"},
                "ram_used_mb": {"type": "float"},
                "disk_percent": {"type": "float"},
                "hostname": {"type": "keyword"},
                "platform": {"type": "keyword"},
            }
        }
    }

    for index_name, mapping in [
        (INDEX_RAG_LOGS, rag_mapping),
        (INDEX_MLFLOW, mlflow_mapping),
        (INDEX_SYSTEM, system_mapping),
    ]:
        if not es.indices.exists(index=index_name):
            es.indices.create(index=index_name, body=mapping)
            logger.info(f"[ES] ✅ Index créé : {index_name}")
        else:
            logger.info(f"[ES] ℹ️  Index existant : {index_name}")


# ============================================================
# 3. LOG RAG QUERY
#    Envoie les métriques d'une question RAG vers Elasticsearch.
# ============================================================
def log_rag_query(
    es: Elasticsearch,
    property_type: str,
    question: str,
    reply: str,
    sources: list,
    latency_ms: int,
    success: bool = True,
):
    """
    Envoie les métriques d'une question RAG vers Elasticsearch.
    À appeler après chaque question dans le pipeline RAG.

    Args:
        es            : Client Elasticsearch
        property_type : Type de propriété
        question      : Question posée
        reply         : Réponse générée
        sources       : Documents sources récupérés
        latency_ms    : Latence en millisecondes
        success       : True si réponse valide
    """
    if not es:
        return

    scores = [s.get("score", 0.0) for s in sources] if sources else []
    top_score = max(scores) if scores else 0.0
    avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0

    doc = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "property_type": property_type,
        "question": question[:500],
        "reply_length": len(reply),
        "latency_ms": latency_ms,
        "sources_count": len(sources),
        "success": success,
        "llm_model": LLM_MODEL,
        "top_score": top_score,
        "avg_score": avg_score,
    }

    try:
        es.index(index=INDEX_RAG_LOGS, document=doc)
        logger.debug(f"[ES] RAG log envoyé | latency={latency_ms}ms")
    except Exception as e:
        logger.error(f"[ES] Erreur envoi RAG log : {e}")


# ============================================================
# 4. SEND MLFLOW METRICS
#    Exporte les runs MLflow vers Elasticsearch.
# ============================================================
def send_mlflow_metrics(es: Elasticsearch, max_runs: int = 20):
    """
    Exporte les derniers runs MLflow vers Elasticsearch
    pour visualisation dans Kibana.

    Args:
        es       : Client Elasticsearch
        max_runs : Nombre maximum de runs à exporter
    """
    if not es:
        logger.error("[ES] Client Elasticsearch non disponible.")
        return

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient()
    experiment = mlflow.get_experiment_by_name("PropIQ-RAG-Evaluation")

    if experiment is None:
        logger.warning(
            "[ES] Expérience MLflow 'PropIQ-RAG-Evaluation' introuvable.\n"
            "   → Lance d'abord : python mlflow_config.py --run-eval"
        )
        return

    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=["start_time DESC"],
        max_results=max_runs,
    )

    sent = 0
    for run in runs:
        doc = {
            "timestamp": datetime.fromtimestamp(
                run.info.start_time / 1000, tz=timezone.utc
            ).isoformat(),
            "run_id": run.info.run_id,
            "run_name": run.info.run_name or "",
            "status": run.info.status,
            # Paramètres
            "property_type": run.data.params.get("property_type", ""),
            "llm_model": run.data.params.get("llm_model", LLM_MODEL),
            "embedding_model": run.data.params.get("embedding_model", EMBEDDING_MODEL),
            # Métriques
            "success_rate": run.data.metrics.get("success_rate", 0),
            "avg_latency_ms": run.data.metrics.get("avg_latency_ms", 0),
            "avg_sources_count": run.data.metrics.get("avg_sources_count", 0),
            "avg_reply_length": run.data.metrics.get("avg_reply_length", 0),
            "total_tests": run.data.metrics.get("total_tests", 0),
        }

        try:
            es.index(
                index=INDEX_MLFLOW,
                id=run.info.run_id,
                document=doc,
            )
            sent += 1
        except Exception as e:
            logger.error(f"[ES] Erreur envoi run {run.info.run_id} : {e}")

    logger.info(f"[ES] ✅ {sent}/{len(runs)} runs MLflow exportés → {INDEX_MLFLOW}")


# ============================================================
# 5. MONITOR SYSTEM
#    Envoie les métriques système (CPU, RAM, Disk).
# ============================================================
def monitor_system(es: Elasticsearch, interval_sec: int = 30, iterations: int = 1):
    """
    Envoie les métriques système vers Elasticsearch.

    Args:
        es            : Client Elasticsearch
        interval_sec  : Intervalle entre chaque mesure (secondes)
        iterations    : Nombre de mesures (0 = infini)
    """
    if not es:
        logger.error("[ES] Client Elasticsearch non disponible.")
        return

    try:
        import psutil
    except ImportError:
        logger.warning(
            "[ES] psutil non installé. "
            "Lance : pip install psutil\n"
            "   → Envoi d'un log système basique sans métriques."
        )
        # Log basique sans psutil
        doc = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hostname": platform.node(),
            "platform": platform.system(),
            "cpu_percent": 0,
            "ram_percent": 0,
            "ram_used_mb": 0,
            "disk_percent": 0,
        }
        es.index(index=INDEX_SYSTEM, document=doc)
        return

    count = 0
    logger.info(
        "[ES] Monitoring système démarré "
        f"(interval={interval_sec}s | iterations={'∞' if iterations == 0 else iterations})"
    )

    while True:
        doc = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hostname": platform.node(),
            "platform": platform.system(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "ram_percent": psutil.virtual_memory().percent,
            "ram_used_mb": round(psutil.virtual_memory().used / 1024 / 1024, 2),
            "disk_percent": psutil.disk_usage("/").percent,
        }

        try:
            es.index(index=INDEX_SYSTEM, document=doc)
            logger.info(
                "[ES] System log | "
                f"CPU={doc['cpu_percent']}% | "
                f"RAM={doc['ram_percent']}% | "
                f"Disk={doc['disk_percent']}%"
            )
        except Exception as e:
            logger.error(f"[ES] Erreur envoi system log : {e}")

        count += 1
        if iterations > 0 and count >= iterations:
            break

        time.sleep(interval_sec)


# ============================================================
# 6. SETUP KIBANA
#    Affiche les instructions pour configurer Kibana.
# ============================================================
def setup_kibana_instructions():
    """Affiche les instructions pour configurer les index patterns dans Kibana."""

    print("""
{'='*60}
  🔭 Configuration Kibana — PropIQ Monitoring
{'='*60}

  1. Ouvrir Kibana : http://localhost:5601

  2. Aller dans :
     Stack Management → Index Management
     → Vérifier que ces index existent :
       • {INDEX_RAG_LOGS}
       • {INDEX_MLFLOW}
       • {INDEX_SYSTEM}

  3. Créer les Data Views :
     Stack Management → Data Views → Create data view

     ┌─────────────────────────────────────────────────┐
     │  Name        : PropIQ RAG Logs                  │
     │  Index pattern : propiq-rag-logs*               │
     │  Timestamp   : timestamp                        │
     └─────────────────────────────────────────────────┘

     ┌─────────────────────────────────────────────────┐
     │  Name        : PropIQ MLflow Metrics            │
     │  Index pattern : propiq-mlflow-metrics*         │
     │  Timestamp   : timestamp                        │
     └─────────────────────────────────────────────────┘

     ┌─────────────────────────────────────────────────┐
     │  Name        : PropIQ System Logs               │
     │  Index pattern : propiq-system-logs*            │
     │  Timestamp   : timestamp                        │
     └─────────────────────────────────────────────────┘

  4. Aller dans Discover pour explorer les données

  5. Créer des visualisations dans Dashboard :
     • Latence moyenne des requêtes RAG  (avg latency_ms)
     • Taux de succès                    (success_rate)
     • Nombre de sources par requête     (avg sources_count)
     • CPU / RAM au fil du temps         (cpu_percent / ram_percent)
     • Runs MLflow par property_type     (property_type)

{'='*60}
""")


# ============================================================
# 7. FULL MONITORING PIPELINE
#    Lance tout en une seule commande.
# ============================================================
def run_full_monitoring():
    """
    Pipeline complet de monitoring :
    1. Connexion Elasticsearch
    2. Création des index
    3. Export des métriques MLflow
    4. Envoi d'un log système
    5. Affichage des instructions Kibana
    """
    print(f"\n{'='*55}")
    print("  📊 PropIQ — Full Monitoring Pipeline")
    print(f"{'='*55}\n")

    # Connexion
    es = connect_elasticsearch()
    if not es:
        print("\n  ❌ Elasticsearch non accessible. Vérifie :")
        print("     make monitoring-start\n")
        return

    # Création des index
    print("  📁 Création des index Elasticsearch...")
    create_indices(es)

    # Export MLflow
    print("\n  📤 Export des métriques MLflow...")
    send_mlflow_metrics(es)

    # Log système
    print("\n  💻 Envoi d'un log système...")
    monitor_system(es, iterations=1)

    # Instructions Kibana
    setup_kibana_instructions()


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="PropIQ Monitoring CLI — Elasticsearch + Kibana",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Tester la connexion à Elasticsearch",
    )
    parser.add_argument(
        "--create-indices",
        action="store_true",
        help="Créer les index Elasticsearch",
    )
    parser.add_argument(
        "--send-mlflow-metrics",
        action="store_true",
        help="Exporter les métriques MLflow vers Elasticsearch",
    )
    parser.add_argument(
        "--monitor-system",
        action="store_true",
        help="Envoyer les métriques système (CPU, RAM, Disk)",
    )
    parser.add_argument(
        "--setup-kibana",
        action="store_true",
        help="Afficher les instructions de configuration Kibana",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Lancer le pipeline complet de monitoring",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Intervalle en secondes pour le monitoring système (défaut: 30)",
    )

    args = parser.parse_args()

    if args.setup_kibana:
        setup_kibana_instructions()
        return

    if args.full:
        run_full_monitoring()
        return

    # Pour toutes les autres commandes, connexion requise
    es = connect_elasticsearch()

    if args.test_connection:
        if es:
            print(f"\n  ✅ Elasticsearch accessible : {ES_URL}\n")
        else:
            print(f"\n  ❌ Elasticsearch non accessible : {ES_URL}\n")

    elif args.create_indices:
        if es:
            create_indices(es)

    elif args.send_mlflow_metrics:
        if es:
            create_indices(es)
            send_mlflow_metrics(es)

    elif args.monitor_system:
        if es:
            create_indices(es)
            monitor_system(es, interval_sec=args.interval, iterations=0)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
