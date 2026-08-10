import os
import tempfile
"""
PropIQ — RAG Evaluator
======================
Évaluation automatique des réponses du chatbot juridique avec logging MLflow.

Métriques couvertes :
  A. Qualité de réponse  → answer_relevance, faithfulness, citation_coverage,
                           confidence_level, response_completeness
  B. Hallucination        → grounding_score, hallucination_flag, context_utilization,
                           refusal_rate
  C. Pipeline RAG         → retrieval_avg_score, retrieval_top1_score,
                           chunk_diversity, latency_ms

Usage :
    from rag_evaluator import RAGEvaluator
    evaluator = RAGEvaluator(client=llm_client, llm_model=LLM_MODEL)
    metrics   = evaluator.evaluate(question, answer, docs, latency_ms)
    evaluator.log_to_mlflow(metrics, run_name="chat_eval")
"""

import re
import logging
import json
from typing import Optional
from dataclasses import dataclass, asdict

import mlflow

logger = logging.getLogger(__name__)


# ============================================================
# DATACLASS — Résultat structuré
# ============================================================
@dataclass
class RAGMetrics:
    # ── Identifiants ──────────────────────────────────────────
    question: str
    property_type: str
    llm_model: str

    # ── A. Qualité de réponse ─────────────────────────────────
    answer_relevance: float   # 0.0 – 1.0   (LLM-as-judge)
    faithfulness: float   # 0.0 – 1.0   (LLM-as-judge)
    citation_coverage: float   # 0.0 – 1.0   (regex)
    citation_count: int     # nb de citations [DOC | Article X]
    confidence_level: str     # HIGH / MEDIUM / LOW / NONE
    confidence_score: float   # 1.0 / 0.6 / 0.3 / 0.0
    response_completeness: float   # 0.0 – 1.0   (heuristique)
    response_length: int     # nb de caractères

    # ── B. Détection d'hallucinations ─────────────────────────
    grounding_score: float   # 0.0 – 1.0   (overlap mots-clés)
    hallucination_flag: int     # 0 = OK, 1 = hallucination détectée
    hallucination_detail: str     # explication courte
    context_utilization: float   # sources utilisées / sources récupérées
    is_refusal: int     # 1 si le bot a répondu "not found"

    # ── C. Pipeline RAG ───────────────────────────────────────
    retrieval_avg_score: float   # moyenne des scores de similarité
    retrieval_top1_score: float   # meilleur score
    retrieval_docs_count: int     # nb de chunks récupérés
    chunk_diversity: int     # nb de catégories légales distinctes
    latency_ms: int     # temps de réponse total


# ============================================================
# PROMPTS POUR LLM-AS-JUDGE
# ============================================================
_RELEVANCE_PROMPT = """
You are an evaluation expert for a Portuguese Real Estate Legal Chatbot.

QUESTION: {question}
ANSWER: {answer}

Rate the answer's RELEVANCE to the question on a scale from 0.0 to 1.0:
- 1.0 = Directly and fully answers the question
- 0.7 = Mostly answers but misses some aspects
- 0.4 = Partially answers
- 0.1 = Barely related
- 0.0 = Completely off-topic or irrelevant

Respond with ONLY a JSON object like this:
{{"score": 0.85, "reason": "one short sentence"}}
"""

_FAITHFULNESS_PROMPT = """
You are a hallucination detection expert for a legal RAG system.

QUESTION: {question}

RETRIEVED LEGAL CONTEXT:
{context}

ANSWER GIVEN BY THE CHATBOT:
{answer}

Evaluate FAITHFULNESS: Is every factual claim in the answer supported by the context?
- 1.0 = All claims fully grounded in context
- 0.7 = Most claims grounded, minor unsupported details
- 0.4 = Some claims not found in context
- 0.1 = Most claims appear invented
- 0.0 = Answer completely contradicts or ignores context

Also flag if hallucination is detected (true/false) and provide a brief explanation.

Respond with ONLY a JSON object like this:
{{"faithfulness": 0.9, "hallucination": false, "detail": "one short sentence"}}
"""


# ============================================================
# EVALUATOR CLASS
# ============================================================
class RAGEvaluator:
    """
    Évaluation automatique d'une interaction PropIQ (question → réponse RAG).

    Parameters
    ----------
    client      : OpenAI-compatible client (OpenRouter)
    llm_model   : identifiant du modèle utilisé pour le judge (ex: mistralai/mistral-large-2512)
    judge_model : modèle utilisé pour l'évaluation (par défaut = llm_model)
    """

    # Liste complète des catégories vectorstore (pour chunk_diversity)
    KNOWN_CATEGORIES = {
        "ACCESSIBILITY", "CIVIL_SALE", "CIVIL_FINANCIAL", "CIVIL_REGULATORY",
        "MAINTENANCE", "MORTGAGES", "REG_SERVICES", "ENERGY", "FIRE_LAWS",
        "FIRE_TECH", "URBAN_ZONING", "HOUSING_RENTAL", "RGEU", "ELEC",
        "GAS", "TOURIST", "URBANISM", "FINANCING", "SUCCESSION", "VISA_STATUS",
    }

    # Regex pour détecter les citations [SOURCE | Article X]
    # \w avec re.UNICODE couvre nativement TOUS les caractères accentués
    # portugais (Ã, Õ, Ç, Ê...) — évite les listes manuelles incomplètes.
    _CITATION_RE = re.compile(
        r"\[([\w\-]+)\s*\|.*?\]", re.IGNORECASE | re.UNICODE
    )

    # Regex pour détecter le signal de confiance.
    # Accepte deux formats observés en sortie LLM :
    #   "**Confidence: HIGH**"   (format documenté dans le prompt)
    #   "✗ **LOW** – ..."        (format réellement généré par le modèle)
    _CONFIDENCE_RE = re.compile(
        r"(?:Confidence[:\s]*)?[\*✗✓]{0,2}\s*\*{0,2}(HIGH|MEDIUM|LOW)\*{0,2}",
        re.IGNORECASE,
    )

    # Phrase de refus canonique
    _REFUSAL_PHRASE = "not found in the retrieved legal documents"

    def __init__(self, client, llm_model: str, judge_model: Optional[str] = None):
        self.client = client
        self.llm_model = llm_model
        self.judge_model = judge_model or llm_model

    # ----------------------------------------------------------
    # PUBLIC : évaluation complète
    # ----------------------------------------------------------
    def evaluate(
        self,
        question: str,
        answer: str,
        docs: list,
        latency_ms: int = 0,
        property_type: str = "unknown",
    ) -> RAGMetrics:
        """
        Lance toutes les métriques et retourne un objet RAGMetrics.

        Parameters
        ----------
        question      : question posée par l'utilisateur
        answer        : réponse générée par le chatbot
        docs          : liste de dicts retournée par search_relevant_docs()
                        chaque dict contient au minimum {"text", "score", "index"}
        latency_ms    : temps de réponse mesuré en millisecondes
        property_type : type de bien (residencial, comercial, terreno, alojamento_local)
        """
        logger.info(f"[RAGEvaluator] Évaluation | type={property_type} | q={question[:60]}...")

        # Contexte brut pour les juges LLM
        context_text = self._build_judge_context(docs)

        # ── A. Qualité de réponse ──────────────────────────────
        answer_relevance = self._score_relevance(question, answer)
        faithfulness, hall_flag, hall_detail = self._score_faithfulness(
            question, answer, context_text
        )
        citation_count, citation_coverage = self._score_citations(answer, docs)
        confidence_level, confidence_score = self._extract_confidence(answer)
        response_completeness = self._score_completeness(answer)

        # ── B. Hallucinations ──────────────────────────────────
        grounding_score = self._score_grounding(answer, docs)
        context_utilization = self._score_context_utilization(answer, docs)
        is_refusal = int(self._REFUSAL_PHRASE.lower() in answer.lower())

        # ── C. Pipeline RAG ────────────────────────────────────
        retrieval_avg_score = self._avg_retrieval_score(docs)
        retrieval_top1_score = self._top1_retrieval_score(docs)
        chunk_diversity = self._count_chunk_categories(docs)

        metrics = RAGMetrics(
            question=question,
            property_type=property_type,
            llm_model=self.llm_model,
            # A
            answer_relevance=answer_relevance,
            faithfulness=faithfulness,
            citation_coverage=citation_coverage,
            citation_count=citation_count,
            confidence_level=confidence_level,
            confidence_score=confidence_score,
            response_completeness=response_completeness,
            response_length=len(answer),
            # B
            grounding_score=grounding_score,
            hallucination_flag=hall_flag,
            hallucination_detail=hall_detail,
            context_utilization=context_utilization,
            is_refusal=is_refusal,
            # C
            retrieval_avg_score=retrieval_avg_score,
            retrieval_top1_score=retrieval_top1_score,
            retrieval_docs_count=len(docs),
            chunk_diversity=chunk_diversity,
            latency_ms=latency_ms,
        )

        logger.info(
            f"[RAGEvaluator] Done | relevance={answer_relevance:.2f} "
            f"| faithfulness={faithfulness:.2f} | grounding={grounding_score:.2f} "
            f"| hallucination={hall_flag} | confidence={confidence_level}"
        )
        return metrics

    # ----------------------------------------------------------
    # PUBLIC : log MLflow
    # ----------------------------------------------------------
    def log_to_mlflow(
        self,
        metrics: RAGMetrics,
        run_name: str = "propiq_rag_eval",
        experiment: str = "PropIQ-RAG-Evaluation",
    ) -> str:
        """
        Logue toutes les métriques dans MLflow et retourne l'URI de run.

        Parameters
        ----------
        metrics    : résultat retourné par evaluate()
        run_name   : nom visible dans l'UI MLflow
        experiment : nom de l'expérience MLflow
        """
        mlflow.set_experiment(experiment)

        with mlflow.start_run(run_name=run_name) as run:
            # ── Tags (métadonnées non numériques) ──────────────
            mlflow.set_tags({
                "question": metrics.question[:250],
                "property_type": metrics.property_type,
                "llm_model": metrics.llm_model,
                "confidence_level": metrics.confidence_level,
                "hallucination_flag": str(bool(metrics.hallucination_flag)),
                "hallucination_detail": metrics.hallucination_detail[:250],
                "is_refusal": str(bool(metrics.is_refusal)),
            })

            # ── A. Qualité de réponse ───────────────────────────
            mlflow.log_metrics({
                "answer_relevance": metrics.answer_relevance,
                "faithfulness": metrics.faithfulness,
                "citation_coverage": metrics.citation_coverage,
                "citation_count": float(metrics.citation_count),
                "confidence_score": metrics.confidence_score,
                "response_completeness": metrics.response_completeness,
                "response_length": float(metrics.response_length),
            })

            # ── B. Hallucinations ───────────────────────────────
            mlflow.log_metrics({
                "grounding_score": metrics.grounding_score,
                "hallucination_flag": float(metrics.hallucination_flag),
                "context_utilization": metrics.context_utilization,
                "is_refusal": float(metrics.is_refusal),
            })

            # ── C. Pipeline RAG ─────────────────────────────────
            mlflow.log_metrics({
                "retrieval_avg_score": metrics.retrieval_avg_score,
                "retrieval_top1_score": metrics.retrieval_top1_score,
                "retrieval_docs_count": float(metrics.retrieval_docs_count),
                "chunk_diversity": float(metrics.chunk_diversity),
                "latency_ms": float(metrics.latency_ms),
            })

            # ── Score composite (résumé rapide) ─────────────────
            composite = self._composite_score(metrics)
            mlflow.log_metric("composite_rag_score", composite)

            # ── Alerting dérive qualité ───────────────────────
            COMPOSITE_ALERT_THRESHOLD = 0.50
            FAITHFULNESS_ALERT_THRESHOLD = 0.60
            HALLUCINATION_CRITICAL = True   # toujours alerter si hallucination

            if composite < COMPOSITE_ALERT_THRESHOLD:
                logger.warning(
                    f"[RAGEval] 🔴 DÉRIVE DÉTECTÉE — "
                    f"composite={composite:.3f} < seuil={COMPOSITE_ALERT_THRESHOLD} | "
                    f"question={metrics.question[:80]} | "
                    f"property_type={metrics.property_type}"
                )
                mlflow.set_tag("drift_alert", "composite_below_threshold")

            if metrics.faithfulness < FAITHFULNESS_ALERT_THRESHOLD:
                logger.warning(
                    f"[RAGEval] 🟠 FIDÉLITÉ FAIBLE — "
                    f"faithfulness={metrics.faithfulness:.3f} < {FAITHFULNESS_ALERT_THRESHOLD}"
                )
                mlflow.set_tag("drift_alert_faithfulness", "below_threshold")

            if metrics.hallucination_flag and HALLUCINATION_CRITICAL:
                logger.warning(
                    f"[RAGEval] ⚠️  HALLUCINATION DÉTECTÉE — "
                    f"detail={metrics.hallucination_detail} | "
                    f"property_type={metrics.property_type} | "
                    f"confidence={metrics.confidence_level}"
                )
                mlflow.set_tag("hallucination_alert", "detected")

            # ── Artefact JSON complet ────────────────────────────
            fd, artifact_path = tempfile.mkstemp(suffix=".json", prefix="propiq_eval_")
            os.close(fd)
            with open(artifact_path, "w", encoding="utf-8") as f:
                json.dump(asdict(metrics), f, indent=2, ensure_ascii=False)
            mlflow.log_artifact(artifact_path)

            run_uri = f"mlflow:/{experiment}/{run.info.run_id}"
            logger.info(f"[MLflow] Run logué → {run.info.run_id} | composite={composite:.3f}")
            return run_uri

    # ----------------------------------------------------------
    # PUBLIC : évaluer + logger en une seule ligne
    # ----------------------------------------------------------
    def evaluate_and_log(
        self,
        question: str,
        answer: str,
        docs: list,
        latency_ms: int = 0,
        property_type: str = "unknown",
        run_name: str = "propiq_rag_eval",
    ) -> tuple[RAGMetrics, str]:
        """Raccourci : evaluate() + log_to_mlflow() en un appel."""
        metrics = self.evaluate(question, answer, docs, latency_ms, property_type)
        run_uri = self.log_to_mlflow(metrics, run_name=run_name)
        return metrics, run_uri

    # ----------------------------------------------------------
    # MÉTRIQUES PRIVÉES — A. Qualité de réponse
    # ----------------------------------------------------------
    def _score_relevance(self, question: str, answer: str) -> float:
        """LLM-as-judge : pertinence de la réponse par rapport à la question."""
        prompt = _RELEVANCE_PROMPT.format(question=question, answer=answer[:1500])
        result = self._call_judge(prompt)
        return float(result.get("score", 0.5))

    def _score_faithfulness(
        self, question: str, answer: str, context: str
    ) -> tuple[float, int, str]:
        """LLM-as-judge : fidélité de la réponse au contexte RAG."""
        prompt = _FAITHFULNESS_PROMPT.format(
            question=question,
            context=context[:3000],
            answer=answer[:1500],
        )
        result = self._call_judge(prompt)
        faithfulness = float(result.get("faithfulness", 0.5))
        hall_flag = int(bool(result.get("hallucination", False)))
        hall_detail = str(result.get("detail", ""))
        return faithfulness, hall_flag, hall_detail

    def _score_citations(self, answer: str, docs: list) -> tuple[int, float]:
        """
        Compte les citations [DOC | Article X] dans la réponse.
        citation_coverage = citation_count / max(1, nb_docs_récupérés)
        capped à 1.0
        """
        matches = self._CITATION_RE.findall(answer)
        citation_count = len(matches)
        coverage = min(1.0, citation_count / max(1, len(docs)))
        return citation_count, round(coverage, 4)

    def _extract_confidence(self, answer: str) -> tuple[str, float]:
        """Extrait le signal **Confidence: HIGH/MEDIUM/LOW** de la réponse."""
        m = self._CONFIDENCE_RE.search(answer)
        if not m:
            return "NONE", 0.0
        level = m.group(1).upper()
        score_map = {"HIGH": 1.0, "MEDIUM": 0.6, "LOW": 0.3}
        return level, score_map.get(level, 0.0)

    def _score_completeness(self, answer: str) -> float:
        """
        Heuristique : réponse structurée avec sections et bullets = plus complète.
        Score basé sur : longueur, présence de ###, présence de listes.
        """
        score = 0.0
        length = len(answer)

        # Longueur raisonnable (50 – 2000+ chars)
        score += min(0.4, length / 2000 * 0.4)

        # Présence de sections markdown
        if re.search(r"^#{1,3}\s", answer, re.MULTILINE):
            score += 0.3

        # Présence de listes
        if re.search(r"^[-*]\s", answer, re.MULTILINE):
            score += 0.2

        # Signal de confiance présent
        if self._CONFIDENCE_RE.search(answer):
            score += 0.1

        return round(min(1.0, score), 4)

    # ----------------------------------------------------------
    # MÉTRIQUES PRIVÉES — B. Hallucinations
    # ----------------------------------------------------------
    def _score_grounding(self, answer: str, docs: list) -> float:
        """
        Overlap de mots-clés entre la réponse et le contexte RAG récupéré.
        Proportion de mots significatifs de la réponse présents dans les sources.
        """
        if not docs:
            return 0.0

        context_text = " ".join(d.get("text", "") for d in docs).lower()
        context_words = set(re.findall(r"\b[a-záàâãéèêíóôõúç]{4,}\b", context_text))

        answer_words = set(re.findall(r"\b[a-záàâãéèêíóôõúç]{4,}\b", answer.lower()))

        if not answer_words:
            return 0.0

        overlap = len(answer_words & context_words) / len(answer_words)
        return round(overlap, 4)

    def _score_context_utilization(self, answer: str, docs: list) -> float:
        """
        Estime quelle proportion des sources récupérées ont été utilisées.
        Basé sur le croisement entre les index/catégories citées et celles disponibles.
        """
        if not docs:
            return 0.0

        # Catégories dans les sources récupérées
        available_categories = {d.get("index", "").upper() for d in docs if d.get("index")}
        if not available_categories:
            return 0.0

        # Catégories mentionnées dans les citations de la réponse
        cited_in_answer = {m.upper() for m in self._CITATION_RE.findall(answer)}

        utilized = len(cited_in_answer & available_categories)
        return round(min(1.0, utilized / len(available_categories)), 4)

    # ----------------------------------------------------------
    # MÉTRIQUES PRIVÉES — C. Pipeline RAG
    # ----------------------------------------------------------
    def _avg_retrieval_score(self, docs: list) -> float:
        if not docs:
            return 0.0
        scores = [d.get("score", 0.0) for d in docs]
        return round(sum(scores) / len(scores), 4)

    def _top1_retrieval_score(self, docs: list) -> float:
        if not docs:
            return 0.0
        return round(max(d.get("score", 0.0) for d in docs), 4)

    def _count_chunk_categories(self, docs: list) -> int:
        """Nb de catégories légales distinctes dans les chunks récupérés."""
        return len({d.get("index", "UNKNOWN") for d in docs if d.get("index")})

    # ----------------------------------------------------------
    # HELPERS
    # ----------------------------------------------------------
    def _build_judge_context(self, docs: list, max_chars: int = 4000) -> str:
        """Construit un contexte lisible pour les prompts LLM-as-judge."""
        if not docs:
            return "No documents retrieved."
        parts, total = [], 0
        for d in docs:
            source = d.get("index", "UNKNOWN")
            text = d.get("text", "")[:600]
            chunk = f"[{source}] {text}"
            if total + len(chunk) > max_chars:
                break
            parts.append(chunk)
            total += len(chunk)
        return "\n\n---\n\n".join(parts)

    def _call_judge(self, prompt: str) -> dict:
        """
        Appel au LLM-as-judge avec parsing JSON robuste.
        Retourne un dict vide en cas d'erreur.
        """
        try:
            resp = self.client.chat.completions.create(
                model=self.judge_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200,
            )
            raw = resp.choices[0].message.content or ""
            # Nettoyage des blocs ```json ```
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning(f"[Judge] JSON parse error: {e} | raw={raw[:100]}")
            return {}
        except Exception as e:
            logger.error(f"[Judge] LLM call failed: {e}")
            return {}

    def _composite_score(self, m: RAGMetrics) -> float:
        """
        Score composite résumant la qualité globale d'une interaction.

        Pondération :
          40% faithfulness  (anti-hallucination, critique pour du juridique)
          25% answer_relevance
          15% grounding_score
          10% citation_coverage
          10% response_completeness

        Pénalités :
          -0.2 si hallucination_flag = 1
        """
        score = (
            0.40 * m.faithfulness
            + 0.25 * m.answer_relevance
            + 0.15 * m.grounding_score
            + 0.10 * m.citation_coverage
            + 0.10 * m.response_completeness
        )
        if m.hallucination_flag:
            score = max(0.0, score - 0.20)
        return round(score, 4)


# ============================================================
# INTÉGRATION DANS app.py  (exemple)
# ============================================================
"""
Ajoutez dans le endpoint /api/chat de app.py :

    from rag_evaluator import RAGEvaluator

    # Dans startup() :
    evaluator = RAGEvaluator(client=llm_client, llm_model=LLM_MODEL)

    # Dans le endpoint /api/chat, après la génération de la réponse :
    t_start = time.time()
    reply, docs = run_api_chat(...)
    latency_ms  = int((time.time() - t_start) * 1000)

    metrics, run_uri = evaluator.evaluate_and_log(
        question      = payload["question"],
        answer        = reply,
        docs          = docs,
        latency_ms    = latency_ms,
        property_type = payload.get("property_type", "residencial"),
        run_name      = f"chat_{payload.get('property_type', 'unknown')}",
    )
    logger.info(f"[RAGEval] composite={metrics.composite_rag_score} | run={run_uri}")
"""


# ============================================================
# SCRIPT DE TEST STANDALONE
# ============================================================
if __name__ == "__main__":
    """
    Test rapide avec des données mockées (sans appel réseau).
    Lance : python rag_evaluator.py
    """
    logging.basicConfig(level=logging.INFO)

    # ── Mock LLM client ───────────────────────────────────────
    class MockChoice:
        class _msg:
            content = '{"score": 0.85, "reason": "Directly answers the question."}'
        message = _msg()

    class MockResponse:
        choices = [MockChoice()]

    class MockClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    # Faithfulness mock
                    if "faithfulness" in kwargs.get("messages", [{}])[-1].get("content", ""):
                        class C:
                            class _msg:
                                content = '{"faithfulness": 0.9, "hallucination": false, "detail": "All claims grounded."}'
                            message = _msg()

                        class R:
                            choices = [C()]
                        return R()
                    return MockResponse()

    # ── Données de test ───────────────────────────────────────
    mock_docs = [
        {
            "text": "O artigo 1225.º do Código Civil estabelece que o empreiteiro responde pelos defeitos da obra durante 5 anos.",
            "index": "CIVIL_SALE",
            "score": 0.87,
            "metadata": {"article": "1225"},
        },
        {
            "text": "A licença de habitabilidade é obrigatória para todos os imóveis construídos após 1951.",
            "index": "RGEU",
            "score": 0.72,
            "metadata": {"article": "70"},
        },
        {
            "text": "O certificado energético é exigido para venda ou arrendamento de imóveis.",
            "index": "ENERGY",
            "score": 0.65,
            "metadata": {"article": "12"},
        },
    ]

    mock_answer = """
### Legal Obligations for Property Sale in Portugal

The seller must provide a valid **habitability certificate** before the deed is signed.

- This is required under [RGEU | Article 70] for all properties built after 1951.
- The energy certificate must also be presented at the time of sale [ENERGY | Article 12].
- Construction defects are covered for 5 years under [CIVIL_SALE | Article 1225].

> **Confidence:** HIGH
"""

    evaluator = RAGEvaluator(client=MockClient(), llm_model="mock-model")

    metrics = evaluator.evaluate(
        question="What documents are required to sell a residential property in Portugal?",
        answer=mock_answer,
        docs=mock_docs,
        latency_ms=1243,
        property_type="residencial",
    )

    print("\n" + "=" * 60)
    print("  PropIQ — RAG Evaluation Results")
    print("=" * 60)
    print(f"  Answer Relevance     : {metrics.answer_relevance:.3f}")
    print(f"  Faithfulness         : {metrics.faithfulness:.3f}")
    print(f"  Grounding Score      : {metrics.grounding_score:.3f}")
    print(
        f"  Citation Coverage    : {metrics.citation_coverage:.3f}  ({metrics.citation_count} citations)")
    print(f"  Context Utilization  : {metrics.context_utilization:.3f}")
    print(f"  Confidence Level     : {metrics.confidence_level}  ({metrics.confidence_score})")
    print(f"  Response Completeness: {metrics.response_completeness:.3f}")
    print(f"  Hallucination Flag   : {'⚠️  YES' if metrics.hallucination_flag else '✅ NO'}")
    print(f"  Is Refusal           : {'YES' if metrics.is_refusal else 'NO'}")
    print(f"  Retrieval Avg Score  : {metrics.retrieval_avg_score:.3f}")
    print(f"  Retrieval Top-1      : {metrics.retrieval_top1_score:.3f}")
    print(f"  Chunk Diversity      : {metrics.chunk_diversity} categories")
    print(f"  Latency              : {metrics.latency_ms} ms")
    print("-" * 60)
    composite = evaluator._composite_score(metrics)
    print(f"  ⭐ Composite RAG Score : {composite:.3f} / 1.000")
    print("=" * 60)

    # Log MLflow (écrit dans ./mlruns localement)
    run_uri = evaluator.log_to_mlflow(metrics, run_name="standalone_test")
    print(f"\n[MLflow] Run enregistré → {run_uri}")
    print("[MLflow] Lancez 'mlflow ui' pour visualiser les métriques.\n")
