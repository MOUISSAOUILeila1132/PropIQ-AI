"""
PropIQ — MLOps Entry Point (Atelier 2)
=======================================
Point d'entrée CLI pour exécuter les étapes du pipeline MLOps.

Usage :
    python main.py --prepare
    python main.py --prepare --type comercial
    python main.py --evaluate
    python main.py --evaluate --type terreno
    python main.py --full-pipeline
    python main.py --load-run <run_id>
"""

import argparse
import logging
import sys

from model_pipeline import (
    prepare_data,
    run_query,
    evaluate_model,
    save_artifacts,
    load_artifacts,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

VALID_TYPES = ["residencial", "comercial", "terreno", "alojamento_local"]


# ============================================================
# COMMANDES CLI
# ============================================================


def cmd_prepare(property_type: str) -> dict:
    """Étape 1 : Charge embeddings + vectorstores."""
    print(f"\n{'='*55}")
    print(f"  📦 PREPARE DATA — property_type={property_type}")
    print(f"{'='*55}")

    pipeline_data = prepare_data(property_type=property_type)

    print("\n  ✅ Embeddings chargés")
    print("  ✅ Vectorstores Pinecone connectés")
    print(f"  ✅ Client LLM prêt ({pipeline_data['llm_model']})")
    print(f"  ⏱  Temps de chargement : {pipeline_data['load_time_ms']}ms\n")

    return pipeline_data


def cmd_query(pipeline_data: dict, question: str):
    """Étape 2 : Exécute une question RAG."""
    print(f"\n{'='*55}")
    print("  💬 RUN QUERY")
    print(f"{'='*55}")
    print(f"  Question : {question}\n")

    result = run_query(question=question, pipeline_data=pipeline_data)

    print(f"  📝 Réponse ({result['latency_ms']}ms):")
    print(f"  {result['reply'][:500]}")
    print(f"\n  📚 Sources récupérées : {len(result['sources'])}")
    for src in result["sources"][:3]:
        print(
            f"    - {src.get('index', 'N/A')[:40]} | "
            f"score={src.get('score', 0):.3f}"
        )
    print()


def cmd_evaluate(pipeline_data: dict) -> dict:
    """Étape 3 : Évalue le pipeline sur les cas de test."""
    print(f"\n{'='*55}")
    print("  🧪 EVALUATE MODEL")
    print(f"{'='*55}")

    metrics = evaluate_model(pipeline_data=pipeline_data)

    print("\n  📊 Résultats d'évaluation :")
    print(f"    • Tests total       : {metrics['total_tests']}")
    print(f"    • Taux de succès    : {metrics['success_rate']}%")
    print(f"    • Latence moyenne   : {metrics['avg_latency_ms']}ms")
    print(f"    • Sources moyennes  : {metrics['avg_sources_count']}")
    print(f"    • Longueur réponse  : {metrics['avg_reply_length']} chars")
    print()

    return metrics


def cmd_save(metrics: dict, pipeline_data: dict) -> str:
    """Étape 4 : Sauvegarde dans MLflow."""
    print(f"\n{'='*55}")
    print("  💾 SAVE ARTIFACTS (MLflow)")
    print(f"{'='*55}")

    run_id = save_artifacts(
        metrics=metrics,
        pipeline_data=pipeline_data,
    )

    print(f"\n  ✅ Run MLflow créé : {run_id}")
    print("  🌐 Voir les résultats : http://localhost:5000\n")
    return run_id


def cmd_load(run_id: str):
    """Étape 5 : Charge un run MLflow existant."""
    print(f"\n{'='*55}")
    print(f"  📂 LOAD ARTIFACTS — run_id={run_id}")
    print(f"{'='*55}")

    data = load_artifacts(run_id=run_id)

    print("\n  📋 Paramètres :")
    for k, v in data["params"].items():
        print(f"    • {k} = {v}")

    print("\n  📊 Métriques :")
    for k, v in data["metrics"].items():
        print(f"    • {k} = {v}")

    print(f"\n  ℹ️  Status : {data['status']}")
    print(f"  🕐 Démarré : {data['start_time']}\n")


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="PropIQ MLOps Pipeline CLI",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Arguments de commande
    parser.add_argument(
        "--prepare",
        action="store_true",
        help="Charger embeddings + vectorstores Pinecone",
    )
    parser.add_argument(
        "--query",
        type=str,
        metavar="QUESTION",
        help="Poser une question RAG\n"
        'Ex: --query "What are the requirements for habitability certificate?"',
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Évaluer le pipeline sur les cas de test par défaut",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Sauvegarder les métriques dans MLflow (nécessite --evaluate)",
    )
    parser.add_argument(
        "--full-pipeline",
        action="store_true",
        help="Exécuter prepare + evaluate + save en une seule commande",
    )
    parser.add_argument(
        "--load-run",
        type=str,
        metavar="RUN_ID",
        help="Charger un run MLflow existant par son ID",
    )
    parser.add_argument(
        "--type",
        type=str,
        default="residencial",
        choices=VALID_TYPES,
        metavar="PROPERTY_TYPE",
        help=(
            "Type de propriété :\n"
            "  residencial      (défaut)\n"
            "  comercial\n"
            "  terreno\n"
            "  alojamento_local"
        ),
    )

    args = parser.parse_args()

    # Aucun argument → afficher l'aide
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    # ── --load-run ────────────────────────────────────────────
    if args.load_run:
        cmd_load(args.load_run)
        return

    # ── --full-pipeline ───────────────────────────────────────
    if args.full_pipeline:
        pipeline_data = cmd_prepare(args.type)
        metrics = cmd_evaluate(pipeline_data)
        run_id = cmd_save(metrics, pipeline_data)
        print(f"  🎉 Pipeline complet terminé — run_id={run_id}")
        return

    # ── Commandes individuelles ───────────────────────────────
    pipeline_data = None

    if args.prepare or args.query or args.evaluate:
        pipeline_data = cmd_prepare(args.type)

    if args.query and pipeline_data:
        cmd_query(pipeline_data, args.query)

    if args.evaluate and pipeline_data:
        metrics = cmd_evaluate(pipeline_data)

        if args.save:
            cmd_save(metrics, pipeline_data)


if __name__ == "__main__":
    main()
