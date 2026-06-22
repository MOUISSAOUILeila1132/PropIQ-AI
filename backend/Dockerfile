# ============================================================
# PropIQ — Dockerfile (Atelier 6)
# ============================================================
# Build :
#   docker build -t propiq-app .
#
# Run :
#   docker run -p 8000:8000 --env-file .env propiq-app
# ============================================================

# ── Image de base ────────────────────────────────────────────
FROM python:3.11-slim

# ── Métadonnées ──────────────────────────────────────────────
LABEL maintainer="PropIQ Team"
LABEL description="PropIQ — Chatbot Juridique Immobilier Portugais"
LABEL version="2.4.0"

# ── Variables d'environnement système ────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_DATASETS_OFFLINE=1 \
    HF_HUB_OFFLINE=1 \
    HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
    TOKENIZERS_PARALLELISM=false

# ── Répertoire de travail ────────────────────────────────────
WORKDIR /app

# ── Dépendances système ──────────────────────────────────────
# Nécessaires pour : PyPDF2, sentence-transformers, torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Copie du requirements.txt en premier (cache Docker) ──────
COPY requirements.txt .

# ── Installation des dépendances Python ──────────────────────
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Copie du code source du projet ───────────────────────────
COPY app.py              .
COPY askQuestions.py     .
COPY complianceEngine.py .
COPY config.py           .
COPY credits.py          .
COPY human_evaluator.py  .
COPY laws_index.py       .
COPY mlflow_config.py    .
COPY model_pipeline.py   .
COPY main.py             .
COPY qualityLife.py      .
COPY rag_evaluator.py    .
COPY subscription.py     .
COPY translationEngine.py .
COPY voiceEngine.py      .

# ── Copie des fichiers de configuration ──────────────────────
# Firebase credentials (nécessaire pour l'authentification)
COPY *.json              .

# ── Copie du modèle d'embeddings depuis le cache local ───────
# Le cache HuggingFace est monté via volume en production
# (voir docker-compose.yml ou docker run -v)
# En dev, on peut copier directement :
# COPY --chown=appuser:appuser ~/.cache/huggingface /root/.cache/huggingface

# ── Création des dossiers nécessaires ────────────────────────
RUN mkdir -p \
    /app/vector_stores \
    /app/mlruns \
    /app/evaluations

# ── Port exposé ──────────────────────────────────────────────
EXPOSE 8000

# ── Health check ─────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# ── Commande de démarrage ────────────────────────────────────
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
