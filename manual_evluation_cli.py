"""
PropIQ — CLI Évaluation Manuelle Interactive

Modes disponibles :
  interactif : poser une question → réponse → évaluation immédiate
  pending    : évaluer les interactions sauvegardées
  stats      : afficher les statistiques globales
  export     : exporter le rapport CSV

Usage :
  python manual_evaluation_cli.py
  python manual_evaluation_cli.py --mode interactif --evaluateur "Dr. Silva"
  python manual_evaluation_cli.py --mode pending
  python manual_evaluation_cli.py --mode stats
  python manual_evaluation_cli.py --mode export
"""

import argparse
import sys
from datetime import datetime

import requests

from human_evaluator import (
    evaluer_reponse_immediate,
    get_pending_interactions,
    get_interaction_details,
    get_evaluation_stats,
    export_evaluations_csv,
    EVALUATION_CRITERIA,
    get_niveau,
)

# ============================================================
# CONFIGURATION
# ============================================================
DEFAULT_API_URL = "http://localhost:8000"

PROPERTY_TYPES = {
    "1": "residencial",
    "2": "comercial",
    "3": "terreno",
    "4": "alojamento_local",
}


# ============================================================
# UTILITAIRES AFFICHAGE
# ============================================================
def banner():
    print("\n" + "═" * 65)
    print("  🏠  PropIQ — Évaluation Manuelle Interactive")
    print("═" * 65)


def section(title: str):
    print(f"\n  {'─'*60}")
    print(f"  {title}")
    print(f"  {'─'*60}")


def choisir_property_type() -> str:
    """Sélection interactive du type de propriété."""
    print("\n  🏠 Choisissez le type de propriété :")
    for k, v in PROPERTY_TYPES.items():
        print(f"    [{k}] {v}")
    while True:
        choix = input("\n  → Votre choix (1-4) : ").strip()
        if choix in PROPERTY_TYPES:
            return PROPERTY_TYPES[choix]
        print("  ⚠️  Choix invalide, recommencez.")


def _afficher_stats():
    """Affiche les statistiques globales des évaluations."""
    stats = get_evaluation_stats()

    print("\n" + "═" * 65)
    print("  📈  STATISTIQUES GLOBALES PROPIQ")
    print("═" * 65)
    print(f"\n  ✅ Évaluées   : {stats.get('total_evaluated', 0)}")
    print(f"  ⏳ En attente : {stats.get('total_pending', 0)}")

    score_moy = stats.get("score_global_moyen")
    if score_moy is not None:
        niveau = get_niveau(score_moy)
        filled = int(score_moy / 5 * 30)
        bar = "█" * filled + "░" * (30 - filled)
        print(f"\n  Score moyen : {score_moy}/5 → {niveau}")
        print(f"  [{bar}]")

    moyennes = stats.get("moyennes_criteres", {})
    if moyennes:
        print("\n  Moyennes par critère :")
        print(f"  {'─'*50}")
        for k, v in moyennes.items():
            if v is not None:
                info = EVALUATION_CRITERIA.get(k, {})
                emoji = info.get("emoji", "•")
                label = info.get("label", k)
                bar_c = "█" * int(v) + "░" * (5 - int(v))
                print(
                    f"  {emoji} {label:<25} "
                    f"[{bar_c}] {v}/5"
                )

    dist = stats.get("distribution_niveaux", {})
    if dist:
        print("\n  Distribution des niveaux :")
        for niveau, count in dist.items():
            print(f"    {niveau:<25} : {count} évaluation(s)")

    print("═" * 65)


def _afficher_resume_session(resultats: list, evaluateur: str):
    """Affiche un résumé complet de la session d'évaluation."""
    n = len(resultats)
    scores = [r["score_global"] for r in resultats]
    moy = round(sum(scores) / n, 3) if n > 0 else 0.0
    niveau = get_niveau(moy)

    print("\n" + "═" * 65)
    print("  🏆  RÉSUMÉ DE LA SESSION D'ÉVALUATION")
    print("═" * 65)
    print(f"\n  👤 Évaluateur          : {evaluateur}")
    print("  📅 Date                : "
          f"{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  ✅ Interactions notées : {n}")
    print(f"  📈 Score moyen         : {moy}/5")
    print(f"  🏆 Niveau moyen        : {niveau}")

    # Barre de progression globale
    filled = int(moy / 5 * 30)
    bar = "█" * filled + "░" * (30 - filled)
    print(f"\n  [{bar}] {moy}/5")

    # Moyennes par critère
    print("\n  📋 Moyennes par critère :")
    print(f"  {'─'*50}")
    for critere, info in EVALUATION_CRITERIA.items():
        vals = [
            r["notes"].get(critere)
            for r in resultats
            if r["notes"].get(critere) is not None
        ]
        if vals:
            moy_c = round(sum(vals) / len(vals), 2)
            bar_c = "█" * int(moy_c) + "░" * (5 - int(moy_c))
            print(
                f"  {info['emoji']} {info['label']:<25} "
                f"[{bar_c}] {moy_c}/5"
            )

    # Tableau individuel
    print("\n  📊 Scores individuels :")
    print(f"  {'─'*50}")
    for i, r in enumerate(resultats, 1):
        print(
            f"  Q{i:02d} | "
            f"Score : {r['score_global']}/5 | "
            f"{r.get('niveau','N/A')}"
        )
    print("═" * 65)


# ============================================================
# MODE INTERACTIF — Question → Réponse → Évaluation immédiate
# ============================================================
def mode_interactif(api_url: str, evaluateur: str):
    """
    Mode principal d'évaluation :
      1. L'évaluateur choisit un type de propriété
      2. L'évaluateur pose une question
      3. Le chatbot répond (via API)
      4. La réponse s'affiche dans le terminal
      5. L'évaluateur note IMMÉDIATEMENT chaque critère
      6. Le score est calculé et affiché
      7. L'évaluation est sauvegardée (SQLite + JSON + MLflow)
    """
    banner()
    print(f"\n  🌐 API cible  : {api_url}")
    print(f"  👤 Évaluateur : {evaluateur}")
    print(
        "\n  💡 Posez une question au chatbot et évaluez\n"
        "     sa réponse immédiatement après l'affichage."
    )

    session_resultats = []
    n_question = 0

    while True:
        n_question += 1
        section(f"QUESTION N° {n_question}")

        # ── Choisir le type de propriété ────────────────────
        property_type = choisir_property_type()

        # ── Saisir la question ───────────────────────────────
        print()
        question = input(
            "  ❓ Votre question juridique : "
        ).strip()

        if not question:
            print("  ⚠️  Question vide, recommencez.")
            n_question -= 1
            continue

        # ── Appel API chatbot ────────────────────────────────
        print("\n  ⏳ Interrogation du chatbot PropIQ...")

        try:
            resp = requests.post(
                f"{api_url}/api/chat",
                json={
                    "property_type": property_type,
                    "question": question,
                },
                timeout=90,
            )

            if resp.status_code != 200:
                print(
                    f"  ❌ Erreur API {resp.status_code} : "
                    f"{resp.text[:300]}"
                )
                n_question -= 1
                continue

            data = resp.json()
            answer = data.get("response", "")
            sources = data.get("sources", [])
            latency_ms = data.get("latency_ms", 0)
            interaction_id = data.get("interaction_id", "N/A")

        except requests.exceptions.ConnectionError:
            print(
                f"\n  ❌ Impossible de contacter {api_url}\n"
                "  💡 Lancez d'abord : uvicorn app:app --reload"
            )
            n_question -= 1
            continue
        except requests.exceptions.Timeout:
            print("  ❌ Timeout — le chatbot met trop de temps à répondre.")
            n_question -= 1
            continue
        except Exception as e:
            print(f"  ❌ Erreur inattendue : {e}")
            n_question -= 1
            continue

        # ── Évaluation immédiate ─────────────────────────────
        result = evaluer_reponse_immediate(
            question=question,
            answer=answer,
            sources=sources,
            property_type=property_type,
            latency_ms=latency_ms,
            interaction_id=interaction_id,
            evaluateur=evaluateur,
        )

        if result:
            session_resultats.append(result)

        # ── Continuer ? ──────────────────────────────────────
        print()
        try:
            continuer = input(
                "  ➡️  [C]ontinuer nouvelle question | "
                "[Q]uitter : "
            ).strip().upper()
        except (KeyboardInterrupt, EOFError):
            break

        if continuer == "Q":
            break

    # ── Résumé final de session ──────────────────────────────
    if session_resultats:
        _afficher_resume_session(session_resultats, evaluateur)

        # Export CSV
        print()
        try:
            export_q = input(
                "  📊 Exporter toutes les évaluations en CSV ? (O/n) : "
            ).strip().upper()
        except (KeyboardInterrupt, EOFError):
            export_q = "N"

        if export_q != "N":
            path = export_evaluations_csv()
            if path:
                print(f"  ✅ Rapport CSV exporté : {path}")
            else:
                print("  ⚠️  Aucune évaluation à exporter.")
    else:
        print("\n  ℹ️  Aucune évaluation réalisée durant cette session.")

    # Afficher stats globales
    _afficher_stats()


# ============================================================
# MODE PENDING — Évaluer les interactions sauvegardées
# ============================================================
def mode_pending(evaluateur: str):
    """
    Évalue les interactions déjà sauvegardées
    (non encore évaluées) depuis la base de données.
    """
    banner()
    print("\n  📂 Mode PENDING — Évaluation des interactions en attente")
    print(f"  👤 Évaluateur : {evaluateur}")

    pending = get_pending_interactions()

    if not pending:
        print(
            "\n  ✅ Aucune interaction en attente d'évaluation.\n"
            "  💡 Utilisez --mode interactif pour en créer."
        )
        _afficher_stats()
        return

    print(f"\n  📋 {len(pending)} interaction(s) en attente.")

    resultats = []

    for idx, item in enumerate(pending, 1):
        section(
            f"INTERACTION {idx}/{len(pending)} "
            f"— {item.get('property_type','').upper()}"
        )

        # Afficher résumé
        print(f"\n  🆔 ID       : {item['interaction_id']}")
        print(f"  📅 Date     : {item.get('created_at','N/A')}")
        print(f"  🏠 Type     : {item.get('property_type','N/A')}")
        print(f"  ⚡ Latence  : {item.get('latency_ms', 0)} ms")
        print(f"  📚 Sources  : {item.get('n_sources', 0)}")
        print(f"  ❓ Question : {item.get('question','')[:80]}...")

        # Charger les détails complets
        details = get_interaction_details(item["interaction_id"])
        if not details:
            print(
                "  ⚠️  Impossible de charger les détails "
                f"de {item['interaction_id']}"
            )
            continue

        # Évaluation immédiate
        result = evaluer_reponse_immediate(
            question=details.get("question", ""),
            answer=details.get("answer", ""),
            sources=details.get("sources_preview", []),
            property_type=details.get("property_type", "N/A"),
            latency_ms=details.get("latency_ms", 0),
            interaction_id=details["interaction_id"],
            evaluateur=evaluateur,
        )

        if result:
            resultats.append(result)

        # Continuer ?
        if idx < len(pending):
            print()
            try:
                continuer = input(
                    "  ➡️  [C]ontinuer | [Q]uitter : "
                ).strip().upper()
            except (KeyboardInterrupt, EOFError):
                break
            if continuer == "Q":
                break

    # ── Résumé ───────────────────────────────────────────────
    if resultats:
        _afficher_resume_session(resultats, evaluateur)

        print()
        try:
            export_q = input(
                "  📊 Exporter en CSV ? (O/n) : "
            ).strip().upper()
        except (KeyboardInterrupt, EOFError):
            export_q = "N"

        if export_q != "N":
            path = export_evaluations_csv()
            if path:
                print(f"  ✅ CSV : {path}")
    else:
        print("\n  ℹ️  Aucune évaluation réalisée.")

    _afficher_stats()


# ============================================================
# MODE STATS
# ============================================================
def mode_stats():
    """Affiche uniquement les statistiques globales."""
    banner()
    _afficher_stats()


# ============================================================
# MODE EXPORT
# ============================================================
def mode_export():
    """Exporte toutes les évaluations en CSV."""
    banner()
    section("📊 EXPORT CSV DES ÉVALUATIONS")

    path = export_evaluations_csv()
    if path:
        print("\n  ✅ Rapport CSV exporté avec succès !")
        print(f"  📂 Fichier : {path}")
    else:
        print(
            "\n  ⚠️  Aucune évaluation complète à exporter.\n"
            "  💡 Réalisez d'abord des évaluations avec "
            "--mode interactif ou --mode pending."
        )


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="PropIQ — CLI Évaluation Manuelle",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["interactif", "pending", "stats", "export"],
        default="interactif",
        help=(
            "Mode d'évaluation :\n"
            "  interactif : question → réponse → évaluation immédiate\n"
            "  pending    : évaluer les interactions sauvegardées\n"
            "  stats      : afficher les statistiques globales\n"
            "  export     : exporter le rapport CSV\n"
            "(défaut : interactif)"
        ),
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_API_URL,
        help=f"URL de l'API PropIQ (défaut : {DEFAULT_API_URL})",
    )
    parser.add_argument(
        "--evaluateur",
        default="",
        help="Nom de l'évaluateur (demandé interactivement si absent)",
    )

    args = parser.parse_args()

    # ── Nom de l'évaluateur ──────────────────────────────────
    evaluateur = args.evaluateur.strip()
    if not evaluateur and args.mode in ("interactif", "pending"):
        banner()
        try:
            evaluateur = input(
                "\n  👤 Votre nom (évaluateur) : "
            ).strip()
        except (KeyboardInterrupt, EOFError):
            evaluateur = ""
        if not evaluateur:
            evaluateur = "anonyme"

    # ── Dispatch mode ────────────────────────────────────────
    try:
        if args.mode == "interactif":
            mode_interactif(args.url, evaluateur)
        elif args.mode == "pending":
            mode_pending(evaluateur)
        elif args.mode == "stats":
            mode_stats()
        elif args.mode == "export":
            mode_export()

    except KeyboardInterrupt:
        print("\n\n  👋 Session interrompue par l'utilisateur.")
        sys.exit(0)

    print("\n  ✅ Session terminée. À bientôt !\n")


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    main()
