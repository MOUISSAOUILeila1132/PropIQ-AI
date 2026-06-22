"""
PropIQ — Human Evaluator
Système d'évaluation manuelle (humaine) des réponses du chatbot.
Évaluation immédiate après chaque réponse du chatbot.
"""

import csv
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import mlflow
from sqlalchemy import (
    Column, DateTime, Float, Integer, String, Text,
    create_engine, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

try:
    from config import MLFLOW_TRACKING_URI, MLFLOW_TRACKING_UI_URL
except ImportError:
    MLFLOW_TRACKING_URI = "sqlite:///mlflow.db"
    MLFLOW_TRACKING_UI_URL = "http://127.0.0.1:5000"

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# DOSSIERS
# ============================================================
BASE_DIR = Path("evaluations")
PENDING_DIR = BASE_DIR / "pending"
RESULTS_DIR = BASE_DIR / "results"

for _dir in [PENDING_DIR, RESULTS_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# ============================================================
# BASE DE DONNÉES SQLite
# ============================================================
DB_URL = "sqlite:///evaluations/human_evaluations.db"
eval_engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
EvalBase = declarative_base()
EvalSession = sessionmaker(bind=eval_engine)


class HumanEvaluationTable(EvalBase):
    """Table stockant chaque évaluation manuelle."""
    __tablename__ = "human_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    eval_id = Column(String, unique=True, index=True)
    interaction_id = Column(String, index=True)

    # Contexte de la question
    property_type = Column(String)
    chat_mode = Column(String, default="free")
    user_id = Column(String, nullable=True)
    question = Column(Text)
    answer = Column(Text)
    latency_ms = Column(Float, default=0.0)
    n_sources = Column(Integer, default=0)
    model_used = Column(String, nullable=True)

    # Notes humaines (1–5)
    note_exactitude = Column(Integer, nullable=True)
    note_pertinence = Column(Integer, nullable=True)
    note_completude = Column(Integer, nullable=True)
    note_clarte = Column(Integer, nullable=True)
    note_securite = Column(Integer, nullable=True)
    note_citations = Column(Integer, nullable=True)

    # Scores calculés
    score_global = Column(Float, nullable=True)
    score_normalise = Column(Float, nullable=True)

    # Métadonnées évaluateur
    evaluateur = Column(String, nullable=True)
    commentaire = Column(Text, nullable=True)
    niveau = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    evaluated_at = Column(DateTime, nullable=True)
    is_evaluated = Column(Integer, default=0)  # 0=pending | 1=done


EvalBase.metadata.create_all(bind=eval_engine)


# ============================================================
# CRITÈRES D'ÉVALUATION
# ============================================================
EVALUATION_CRITERIA = {
    "exactitude": {
        "label": "Exactitude juridique",
        "description": "Les informations légales sont-elles correctes et "
                       "conformes au droit portugais ?",
        "weight": 0.30,
        "emoji": "⚖️ ",
    },
    "pertinence": {
        "label": "Pertinence",
        "description": "La réponse répond-elle directement à la question posée ?",
        "weight": 0.25,
        "emoji": "🎯",
    },
    "completude": {
        "label": "Complétude",
        "description": "Tous les aspects importants de la question sont-ils couverts ?",
        "weight": 0.20,
        "emoji": "📋",
    },
    "clarte": {
        "label": "Clarté",
        "description": "Le langage est-il clair, structuré et compréhensible ?",
        "weight": 0.10,
        "emoji": "💡",
    },
    "securite": {
        "label": "Sécurité juridique",
        "description": "Le chatbot évite-il les conseils risqués et recommande-il "
                       "un professionnel si nécessaire ?",
        "weight": 0.10,
        "emoji": "🛡️ ",
    },
    "citations": {
        "label": "Citations",
        "description": "Les sources légales sont-elles correctement citées ?",
        "weight": 0.05,
        "emoji": "📚",
    },
}

# Échelle de notation
ECHELLE = {
    1: "❌ Très mauvais",
    2: "⚠️  Mauvais",
    3: "➖ Moyen",
    4: "✅ Bon",
    5: "⭐ Excellent",
}

# Niveaux qualitatifs
NIVEAUX = [
    (4.5, 5.01, "🟢 Excellent"),
    (3.5, 4.5, "🔵 Bon"),
    (2.5, 3.5, "🟡 Moyen"),
    (0.0, 2.5, "🔴 Insuffisant"),
]

# ============================================================
# NOMBRE MAX DE SOURCES SAUVEGARDÉES
# ============================================================
MAX_SOURCES_PREVIEW = 10   # ← Correction : 10 au lieu de 5


# ============================================================
# UTILITAIRES
# ============================================================
def get_niveau(score: float) -> str:
    """Retourne le niveau qualitatif selon le score /5."""
    for low, high, label in NIVEAUX:
        if low <= score < high:
            return label
    return "🔴 Insuffisant"


def calculer_score(notes: dict) -> tuple:
    """
    Calcule le score global pondéré.
    Returns: (score_global /5,  score_normalise /1.0)
    """
    total_weight = sum(
        EVALUATION_CRITERIA[c]["weight"]
        for c in notes
        if c in EVALUATION_CRITERIA
    )
    if total_weight == 0:
        return 0.0, 0.0

    score = sum(
        notes[c] * EVALUATION_CRITERIA[c]["weight"]
        for c in notes
        if c in EVALUATION_CRITERIA
    ) / total_weight

    score_global = round(score, 3)
    score_normalise = round(score / 5.0, 3)
    return score_global, score_normalise


def _wrap_text(text: str, width: int = 60) -> list:
    """Découpe le texte en lignes de largeur fixe."""
    words, lines, current = text.split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 <= width:
            current += (" " if current else "") + word
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


# ============================================================
# AFFICHAGE RÉPONSE CHATBOT
# ============================================================
def afficher_reponse_chatbot(
    question: str,
    answer: str,
    sources: list,
    property_type: str,
    latency_ms: float,
) -> None:
    """
    Affiche dans le terminal la question + réponse +
    les 10 sources du chatbot AVANT de demander l'évaluation.
    """
    print("\n" + "═" * 65)
    print("  🤖  RÉPONSE DU CHATBOT PROPIQ")
    print("═" * 65)

    # ── Infos contexte ───────────────────────────────────────
    print(f"\n  🏠 Type de propriété  : {property_type}")
    print(f"  ⚡ Latence            : {latency_ms} ms")
    print(f"  📚 Sources disponibles: {len(sources)}")

    # ── Question ─────────────────────────────────────────────
    print(f"\n  {'─'*60}")
    print("  ❓ QUESTION POSÉE :")
    print(f"  {'─'*60}")
    for line in _wrap_text(question, 58):
        print(f"    {line}")

    # ── Réponse ──────────────────────────────────────────────
    print(f"\n  {'─'*60}")
    print("  🤖 RÉPONSE DU CHATBOT :")
    print(f"  {'─'*60}")
    answer_display = answer[:2000]
    for line in answer_display.split("\n"):
        stripped = line.strip()
        if stripped:
            for wrapped in _wrap_text(stripped, 58):
                print(f"    {wrapped}")
    if len(answer) > 2000:
        print(
            "    ... [réponse tronquée — "
            f"{len(answer)} chars au total]"
        )

    # ── Sources : affichage des 10 chunks ────────────────────
    if sources:
        print(f"\n  {'─'*60}")
        print(f"  📚 SOURCES JURIDIQUES — {len(sources)} chunk(s) :")
        print(f"  {'─'*60}")

        for i, src in enumerate(sources, 1):          # ← tous les chunks
            index = str(src.get("index", "N/A"))
            article = str(src.get("article", "N/A"))
            score = float(src.get("score", 0.0))
            content = str(src.get("content", "")).strip()

            # En-tête du chunk
            print(
                f"\n  [{i:02d}] 📄 {index}\n"
                f"       Article : {article}\n"
                f"       Score   : {score:.4f}"
            )

            # Contenu du chunk (200 premiers caractères)
            if content:
                content_clean = content.replace("passage: ", "").strip()
                for line in _wrap_text(content_clean[:200], 56):
                    print(f"         {line}")
                if len(content_clean) > 200:
                    print("         ... [tronqué]")

        print(f"\n  {'─'*60}")

    print(f"  {'═'*60}")


# ============================================================
# ÉVALUATION IMMÉDIATE — Appelée juste après la réponse
# ============================================================
def evaluer_reponse_immediate(
    question: str,
    answer: str,
    sources: list,
    property_type: str,
    latency_ms: float,
    interaction_id: str,
    evaluateur: str = "anonyme",
) -> Optional[dict]:
    """
    Affiche la réponse du chatbot + les 10 sources dans le terminal
    et demande IMMÉDIATEMENT à l'évaluateur de noter chaque critère.

    Returns:
        dict avec les notes et le score calculé,
        ou None si l'évaluation est ignorée/annulée.
    """
    # ── Étape 1 : Afficher réponse + 10 sources ──────────────
    afficher_reponse_chatbot(
        question=question,
        answer=answer,
        sources=sources,
        property_type=property_type,
        latency_ms=latency_ms,
    )

    # ── Étape 2 : Demander si on évalue maintenant ───────────
    print("\n  📋 ÉVALUATION HUMAINE IMMÉDIATE")
    print("  " + "─" * 60)
    print("  Voulez-vous évaluer cette réponse maintenant ?")
    print("  [O] Oui, évaluer maintenant")
    print("  [N] Non, passer (disponible dans le CLI plus tard)")
    print()

    try:
        choix = input("  → Votre choix (O/n) : ").strip().upper()
    except (KeyboardInterrupt, EOFError):
        print("\n  ⏭️  Évaluation ignorée.")
        return None

    if choix == "N":
        print(
            "\n  ⏭️  Réponse sauvegardée pour évaluation ultérieure.\n"
            "  💡 Lancez : python manual_evaluation_cli.py --mode pending\n"
        )
        return None

    # ── Étape 3 : Afficher l'échelle ─────────────────────────
    print("\n" + "═" * 65)
    print("  📊  NOTATION — Évaluez chaque critère de 1 à 5")
    print("═" * 65)
    print()
    print("  Échelle de notation :")
    for val, label in ECHELLE.items():
        print(f"    [{val}] {label}")
    print()

    # ── Étape 4 : Saisie des notes ───────────────────────────
    notes = {}
    for critere, info in EVALUATION_CRITERIA.items():
        print(
            f"  {info['emoji']} {info['label']:<25} "
            f"(poids : {int(info['weight'] * 100)}%)"
        )
        print(f"     └─ {info['description']}")

        while True:
            try:
                raw = input("     → Note (1-5) : ").strip()
                note = int(raw)
                if 1 <= note <= 5:
                    print(f"     ✔  {note}/5 — {ECHELLE[note]}\n")
                    notes[critere] = note
                    break
                print("     ⚠️  Entrez un nombre entre 1 et 5.")
            except (ValueError, KeyboardInterrupt):
                print("     ⚠️  Saisie invalide, recommencez.")

    # ── Étape 5 : Commentaire libre ──────────────────────────
    print(
        "  💬 Commentaire libre "
        "(optionnel — appuyez Entrée pour passer) :"
    )
    try:
        commentaire = input("     → ").strip()
    except (KeyboardInterrupt, EOFError):
        commentaire = ""

    # ── Étape 6 : Calcul du score ────────────────────────────
    score_global, score_normalise = calculer_score(notes)
    niveau = get_niveau(score_global)

    # ── Étape 7 : Afficher le résultat ───────────────────────
    print("\n" + "═" * 65)
    print("  📊  RÉSULTAT DE L'ÉVALUATION")
    print("═" * 65)
    print()
    print(
        f"  {'Critère':<30} {'Note':>5}   "
        f"{'Poids':>6}   {'Pondéré':>8}"
    )
    print(f"  {'─'*58}")

    for critere, note in notes.items():
        weight = EVALUATION_CRITERIA[critere]["weight"]
        pondere = round(note * weight, 3)
        emoji = EVALUATION_CRITERIA[critere]["emoji"]
        label = EVALUATION_CRITERIA[critere]["label"]
        print(
            f"  {emoji} {label:<27} {note}/5   "
            f"× {int(weight*100):>3}%   = {pondere:.3f}"
        )

    print(f"  {'─'*58}")
    print(f"  {'📈 SCORE GLOBAL':<35} {score_global}/5")
    print(f"  {'📊 SCORE NORMALISÉ':<35} {score_normalise}/1.0")
    print(f"  {'🏆 NIVEAU':<35} {niveau}")
    print()

    # Barre de progression visuelle
    filled = int(score_global / 5 * 30)
    bar = "█" * filled + "░" * (30 - filled)
    print(f"  Progression : [{bar}] {score_global}/5")
    print()

    # ── Étape 8 : Confirmation ───────────────────────────────
    try:
        confirmer = input(
            "  ✅ Confirmer cette évaluation ? (O/n) : "
        ).strip().upper()
    except (KeyboardInterrupt, EOFError):
        confirmer = "O"

    if confirmer == "N":
        print(
            "  ↩️  Évaluation annulée — "
            "réponse conservée en pending.\n"
        )
        return None

    # ── Étape 9 : Enregistrement ─────────────────────────────
    result = save_human_evaluation(
        interaction_id=interaction_id,
        notes=notes,
        evaluateur=evaluateur,
        commentaire=commentaire,
    )

    print("\n  💾 Évaluation enregistrée avec succès !")
    print(f"  🆔 ID Interaction : {interaction_id}")
    print("═" * 65 + "\n")

    return result


# ============================================================
# SAUVEGARDE INTERACTION — 10 sources (correction principale)
# ============================================================
def save_interaction_for_evaluation(
    question: str,
    answer: str,
    sources: list,
    property_type: str,
    latency_ms: float,
    chat_mode: str = "free",
    user_id: Optional[int] = None,
    model_used: str = "",
) -> str:
    """
    Sauvegarde une interaction dans :
      1. Un fichier JSON → evaluations/pending/{uuid}.json
         avec les 10 sources complètes (correction : sources[:10])
      2. La base de données SQLite (statut pending)

    Returns:
        interaction_id (str) : identifiant unique UUID
    """
    interaction_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()

    # ── Construction des sources preview (10 chunks) ─────────
    sources_preview = []
    for s in sources[:MAX_SOURCES_PREVIEW]:          # ← 10 chunks
        sources_preview.append({
            "index": s.get("index", "N/A"),
            "article": s.get("article", "N/A"),
            "score": round(float(s.get("score", 0.0)), 4),
            "content": s.get("content", "")[:300],  # 300 chars par chunk
        })

    interaction_data = {
        "interaction_id": interaction_id,
        "timestamp": timestamp,
        "property_type": property_type,
        "chat_mode": chat_mode,
        "user_id": str(user_id) if user_id else "anonymous",
        "model_used": model_used,
        "latency_ms": latency_ms,
        "question": question,
        "answer": answer,
        "n_sources": len(sources),
        "sources_preview": sources_preview,          # ← 10 chunks
    }

    # ── JSON pending ─────────────────────────────────────────
    json_path = PENDING_DIR / f"{interaction_id}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(interaction_data, f, ensure_ascii=False, indent=2)

    logger.info(
        f"[HumanEval] ✅ JSON sauvegardé : {json_path} | "
        f"{len(sources_preview)} sources"
    )

    # ── SQLite ───────────────────────────────────────────────
    try:
        db = EvalSession()
        record = HumanEvaluationTable(
            eval_id=str(uuid.uuid4()),
            interaction_id=interaction_id,
            property_type=property_type,
            chat_mode=chat_mode,
            user_id=str(user_id) if user_id else "anonymous",
            question=question,
            answer=answer,
            latency_ms=latency_ms,
            n_sources=len(sources),
            model_used=model_used,
            is_evaluated=0,
        )
        db.add(record)
        db.commit()
        db.close()
        logger.info(
            f"[HumanEval] ✅ SQLite insert : {interaction_id}"
        )
    except Exception as e:
        logger.error(f"[HumanEval] ❌ Erreur SQLite insert : {e}")

    return interaction_id


# ============================================================
# ENREGISTREMENT DES NOTES HUMAINES
# ============================================================
def save_human_evaluation(
    interaction_id: str,
    notes: dict,
    evaluateur: str = "anonyme",
    commentaire: str = "",
) -> dict:
    """
    Enregistre les notes humaines pour une interaction.

    Args:
        interaction_id : UUID de l'interaction
        notes          : {critere: note (1-5), ...}
        evaluateur     : Nom de l'évaluateur
        commentaire    : Commentaire libre

    Returns:
        dict avec score calculé et métadonnées
    """
    # ── Validation ───────────────────────────────────────────
    notes_validees = {}
    for critere in EVALUATION_CRITERIA:
        note = notes.get(critere)
        if note is not None:
            note = int(note)
            if not (1 <= note <= 5):
                raise ValueError(
                    f"Note invalide pour '{critere}' : {note}. "
                    "Attendu : 1 à 5."
                )
            notes_validees[critere] = note

    if not notes_validees:
        raise ValueError("Aucune note valide fournie.")

    # ── Score ────────────────────────────────────────────────
    score_global, score_normalise = calculer_score(notes_validees)
    niveau = get_niveau(score_global)

    # ── SQLite update ────────────────────────────────────────
    try:
        db = EvalSession()
        record = db.query(HumanEvaluationTable).filter_by(
            interaction_id=interaction_id
        ).first()

        if record:
            record.note_exactitude = notes_validees.get("exactitude")
            record.note_pertinence = notes_validees.get("pertinence")
            record.note_completude = notes_validees.get("completude")
            record.note_clarte = notes_validees.get("clarte")
            record.note_securite = notes_validees.get("securite")
            record.note_citations = notes_validees.get("citations")
            record.score_global = score_global
            record.score_normalise = score_normalise
            record.niveau = niveau
            record.evaluateur = evaluateur
            record.commentaire = commentaire
            record.evaluated_at = datetime.utcnow()
            record.is_evaluated = 1
            db.commit()

        db.close()
        logger.info(
            "[HumanEval] ✅ Évaluation enregistrée : "
            f"{interaction_id} | Score={score_global}/5 | {niveau}"
        )
    except Exception as e:
        logger.error(f"[HumanEval] ❌ Erreur SQLite update : {e}")

    # ── Déplacer JSON pending → results ──────────────────────
    result_data = {
        "interaction_id": interaction_id,
        "evaluateur": evaluateur,
        "evaluated_at": datetime.utcnow().isoformat(),
        "notes": notes_validees,
        "score_global": score_global,
        "score_normalise": score_normalise,
        "niveau": niveau,
        "commentaire": commentaire,
    }

    pending_path = PENDING_DIR / f"{interaction_id}.json"
    result_path = RESULTS_DIR / f"{interaction_id}_evaluated.json"

    if pending_path.exists():
        with open(pending_path, "r", encoding="utf-8") as f:
            original = json.load(f)
        original.update(result_data)
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(original, f, ensure_ascii=False, indent=2)
        pending_path.unlink()
        logger.info(
            "[HumanEval] ✅ JSON déplacé : "
            f"pending → results/{interaction_id}_evaluated.json"
        )

    # ── MLflow ───────────────────────────────────────────────
    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment("PropIQ-Human-Evaluation")

        run_name = (
            f"human_eval_{niveau.split()[-1].lower()}"
            f"_score{score_global}"
        )

        with mlflow.start_run(run_name=run_name):
            mlflow.set_tags({
                "eval_type": "human",
                "eval_immediate": "true",
                "evaluateur": evaluateur,
                "niveau": niveau,
                "interaction_id": interaction_id,
            })
            mlflow.log_params({
                "evaluateur": evaluateur,
                "n_criteres": len(notes_validees),
            })
            mlflow_metrics = {
                "score_global": score_global,
                "score_normalise": score_normalise,
            }
            for critere, note in notes_validees.items():
                mlflow_metrics[f"note_{critere}"] = float(note)
            mlflow.log_metrics(mlflow_metrics)

        logger.info(f"[MLflow] ✅ Run enregistré : {run_name}")
    except Exception as e:
        logger.warning(f"[MLflow] ⚠️  Erreur : {e}")

    return {
        "interaction_id": interaction_id,
        "score_global": score_global,
        "score_normalise": score_normalise,
        "niveau": niveau,
        "notes": notes_validees,
        "commentaire": commentaire,
        "evaluateur": evaluateur,
    }


# ============================================================
# LISTE DES INTERACTIONS EN ATTENTE
# ============================================================
def get_pending_interactions() -> list:
    """Retourne toutes les interactions en attente d'évaluation."""
    try:
        db = EvalSession()
        records = db.query(HumanEvaluationTable).filter_by(
            is_evaluated=0
        ).order_by(HumanEvaluationTable.created_at.desc()).all()
        db.close()

        return [
            {
                "interaction_id": r.interaction_id,
                "created_at": (
                    r.created_at.strftime("%Y-%m-%d %H:%M")
                    if r.created_at else ""
                ),
                "property_type": r.property_type,
                "question": r.question[:80] if r.question else "",
                "latency_ms": r.latency_ms,
                "n_sources": r.n_sources,
            }
            for r in records
        ]
    except Exception as e:
        logger.error(f"[HumanEval] ❌ get_pending error : {e}")
        return []


# ============================================================
# DÉTAILS D'UNE INTERACTION
# ============================================================
def get_interaction_details(interaction_id: str) -> Optional[dict]:
    """
    Retourne les détails complets (avec les 10 sources)
    depuis le fichier JSON pending ou results.
    """
    for path in [
        PENDING_DIR / f"{interaction_id}.json",
        RESULTS_DIR / f"{interaction_id}_evaluated.json",
    ]:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(
                f"[HumanEval] ✅ Détails chargés : {interaction_id} | "
                f"{len(data.get('sources_preview', []))} sources"
            )
            return data
    logger.warning(
        f"[HumanEval] ⚠️  Interaction non trouvée : {interaction_id}"
    )
    return None


# ============================================================
# STATISTIQUES GLOBALES
# ============================================================
def get_evaluation_stats() -> dict:
    """Retourne les statistiques globales de toutes les évaluations."""
    try:
        db = EvalSession()

        total_pending = db.query(HumanEvaluationTable).filter_by(
            is_evaluated=0
        ).count()
        total_evaluated = db.query(HumanEvaluationTable).filter_by(
            is_evaluated=1
        ).count()

        if total_evaluated == 0:
            db.close()
            return {
                "total_pending": total_pending,
                "total_evaluated": 0,
                "message": "Aucune évaluation complète disponible.",
            }

        row = db.query(
            func.avg(HumanEvaluationTable.note_exactitude).label("avg_exactitude"),
            func.avg(HumanEvaluationTable.note_pertinence).label("avg_pertinence"),
            func.avg(HumanEvaluationTable.note_completude).label("avg_completude"),
            func.avg(HumanEvaluationTable.note_clarte).label("avg_clarte"),
            func.avg(HumanEvaluationTable.note_securite).label("avg_securite"),
            func.avg(HumanEvaluationTable.note_citations).label("avg_citations"),
            func.avg(HumanEvaluationTable.score_global).label("avg_score_global"),
            func.avg(HumanEvaluationTable.latency_ms).label("avg_latency_ms"),
        ).filter_by(is_evaluated=1).first()

        niveaux_dist = {}
        for r in db.query(HumanEvaluationTable).filter_by(
            is_evaluated=1
        ).all():
            n = r.niveau or "Non défini"
            niveaux_dist[n] = niveaux_dist.get(n, 0) + 1

        db.close()

        def sr(val):
            return round(float(val), 3) if val is not None else None

        return {
            "total_pending": total_pending,
            "total_evaluated": total_evaluated,
            "moyennes_criteres": {
                "exactitude": sr(row.avg_exactitude),
                "pertinence": sr(row.avg_pertinence),
                "completude": sr(row.avg_completude),
                "clarte": sr(row.avg_clarte),
                "securite": sr(row.avg_securite),
                "citations": sr(row.avg_citations),
            },
            "score_global_moyen": sr(row.avg_score_global),
            "latence_moyenne_ms": sr(row.avg_latency_ms),
            "distribution_niveaux": niveaux_dist,
        }

    except Exception as e:
        logger.error(f"[HumanEval] ❌ get_stats error : {e}")
        return {"error": str(e)}


# ============================================================
# EXPORT CSV
# ============================================================
def export_evaluations_csv(output_path: str = None) -> str:
    """
    Exporte toutes les évaluations complètes en fichier CSV.
    Returns: chemin du fichier CSV ou "" si erreur/vide.
    """
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(
            RESULTS_DIR / f"rapport_evaluation_{ts}.csv"
        )

    try:
        db = EvalSession()
        records = db.query(HumanEvaluationTable).filter_by(
            is_evaluated=1
        ).order_by(
            HumanEvaluationTable.evaluated_at.desc()
        ).all()
        db.close()

        if not records:
            logger.warning(
                "[HumanEval] Aucune évaluation à exporter."
            )
            return ""

        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)

            # En-têtes
            writer.writerow([
                "ID Interaction",
                "Date Évaluation",
                "Type Propriété",
                "Mode Chat",
                "Évaluateur",
                "Question (extrait)",
                "Réponse (extrait)",
                "Note Exactitude /5",
                "Note Pertinence /5",
                "Note Complétude /5",
                "Note Clarté /5",
                "Note Sécurité /5",
                "Note Citations /5",
                "Score Global /5",
                "Score Normalisé /1",
                "Niveau",
                "Latence (ms)",
                "Nb Sources",
                "Commentaire",
            ])

            for r in records:
                writer.writerow([
                    r.interaction_id,
                    r.evaluated_at.strftime("%Y-%m-%d %H:%M")
                    if r.evaluated_at else "",
                    r.property_type,
                    r.chat_mode,
                    r.evaluateur,
                    (r.question[:100] if r.question else ""),
                    (r.answer[:150] if r.answer else ""),
                    r.note_exactitude or "",
                    r.note_pertinence or "",
                    r.note_completude or "",
                    r.note_clarte or "",
                    r.note_securite or "",
                    r.note_citations or "",
                    r.score_global or "",
                    r.score_normalise or "",
                    r.niveau or "",
                    r.latency_ms,
                    r.n_sources,
                    r.commentaire or "",
                ])

        logger.info(
            f"[HumanEval] ✅ CSV exporté : {output_path} "
            f"({len(records)} évaluations)"
        )
        return output_path

    except Exception as e:
        logger.error(f"[HumanEval] ❌ Export CSV error : {e}")
        return ""
