# ============================================================
# PropIQ — Makefile MLOps (Atelier 3)
# ============================================================
# Usage :
#   make install          → Installer les dépendances
#   make format           → Formater le code (black)
#   make lint             → Vérifier la qualité du code (flake8)
#   make security         → Vérifier la sécurité (bandit)
#   make prepare          → Charger embeddings + vectorstores
#   make query            → Tester une question RAG
#   make evaluate         → Évaluer le pipeline
#   make save             → Sauvegarder dans MLflow
#   make full-pipeline    → Tout exécuter en une commande
#   make mlflow-ui        → Lancer l'interface MLflow
#   make ci               → Vérifications CI complètes
#   make all              → install + ci + full-pipeline
# ============================================================

PYTHON     = python
PIP        = pip
VENV_DIR   = venv
VENV_PYTHON= $(VENV_DIR)/bin/python
VENV_PIP   = $(VENV_DIR)/bin/pip

# Type de propriété par défaut (peut être surchargé)
# Ex: make evaluate TYPE=comercial
TYPE       = residencial

# Question par défaut pour make query
QUESTION   = "What are the legal requirements for a habitability certificate?"

# Port MLflow UI
MLFLOW_PORT = 5000

# Fichiers Python du projet MLOps (pas les fichiers existants)
MLOPS_FILES = model_pipeline.py main.py mlflow_config.py

# Port FastAPI
API_PORT = 8000
API_HOST = 0.0.0.0

# Installation locale d'Elasticsearch (SANS Docker)
# Modifie ce chemin selon l'emplacement de ton install Elasticsearch,
# ou surcharge en ligne de commande : make es-start-local ES_HOME=/chemin/vers/elasticsearch
ES_HOME = C:\Users\ASUS\Downloads\elasticsearch-9.2.2-windows-x86_64\elasticsearch-9.2.2

ifeq ($(OS),Windows_NT)
ES_BIN = $(ES_HOME)/bin/elasticsearch.bat
else
ES_BIN = $(ES_HOME)/bin/elasticsearch
endif

# Installation locale de Kibana (SANS Docker)
# Modifie ce chemin selon l'emplacement de ton install Kibana,
# ou surcharge en ligne de commande : make kibana-start-local KIBANA_HOME=/chemin/vers/kibana
KIBANA_HOME = C:\kibana-9.2.2-windows-x86_64\kibana-9.2.2

ifeq ($(OS),Windows_NT)
KIBANA_BIN = $(KIBANA_HOME)/bin/kibana.bat
else
KIBANA_BIN = $(KIBANA_HOME)/bin/kibana
endif

.PHONY: all install format lint security ci \
        prepare query evaluate save full-pipeline \
        mlflow-ui clean help \
        run run-dev run-prod \
        es-start-local kibana-start-local

# ============================================================
# DEFAULT — Afficher l'aide
# ============================================================
help:
	@echo ""
	@echo "  PropIQ MLOps — Commandes disponibles"
	@echo "  ====================================="
	@echo ""
	@echo "  Serveur :"
	@echo "    make run              Lancer le backend FastAPI (dev, reload auto)"
	@echo "    make run-dev          Lancer en dev avec logs debug"
	@echo "    make run-prod         Lancer en production (2 workers, sans reload)"
	@echo ""
	@echo "  Setup :"
	@echo "    make install          Installer les dépendances"
	@echo ""
	@echo "  Qualité du code :"
	@echo "    make format           Formater le code (black)"
	@echo "    make lint             Vérifier qualité (flake8)"
	@echo "    make security         Vérifier sécurité (bandit)"
	@echo "    make ci               Lancer tous les checks CI"
	@echo ""
	@echo "  Pipeline MLOps :"
	@echo "    make prepare          Charger embeddings + vectorstores"
	@echo "    make query            Tester une question RAG"
	@echo "    make evaluate         Évaluer le pipeline"
	@echo "    make save             Sauvegarder dans MLflow"
	@echo "    make full-pipeline    Tout exécuter (prepare+eval+save)"
	@echo ""
	@echo "  Options :"
	@echo "    TYPE=comercial        Changer le type de propriété"
	@echo "    QUESTION='...'        Changer la question de test"
	@echo ""
	@echo "  MLflow :"
	@echo "    make mlflow-ui        Lancer l'interface MLflow UI"
	@echo ""
	@echo "  Autre :"
	@echo "    make clean            Nettoyer les fichiers temporaires"
	@echo "    make all              install + ci + full-pipeline"
	@echo ""
	@echo "  Elasticsearch (sans Docker) :"
	@echo "    make es-start-local                         Démarrer Elasticsearch en local"
	@echo "    make es-start-local ES_HOME=/chemin         Surcharger le chemin d'install"
	@echo ""
	@echo "  Kibana (sans Docker) :"
	@echo "    make kibana-start-local                     Démarrer Kibana en local"
	@echo "    make kibana-start-local KIBANA_HOME=/chemin Surcharger le chemin d'install"
	@echo ""

# ============================================================
# SETUP
# ============================================================

## Créer le venv et installer les dépendances
install:
	@echo "\n📦 Installation des dépendances...\n"
	$(PIP) install -r requirements.txt
	$(PIP) install black flake8 bandit
	@echo "\n✅ Installation terminée\n"

# ============================================================
# SERVEUR FASTAPI
# ============================================================

## Lancer le serveur en mode développement (reload automatique)
run:
	@echo "\n🚀 Lancement PropIQ Backend (dev) sur http://$(API_HOST):$(API_PORT)\n"
	uvicorn app:app --reload --host $(API_HOST) --port $(API_PORT)

## Alias explicite dev
run-dev:
	@echo "\n🚀 Lancement PropIQ Backend (dev) sur http://$(API_HOST):$(API_PORT)\n"
	uvicorn app:app --reload --host $(API_HOST) --port $(API_PORT) --log-level debug

## Lancer le serveur en mode production (sans reload)
run-prod:
	@echo "\n🚀 Lancement PropIQ Backend (prod) sur http://$(API_HOST):$(API_PORT)\n"
	uvicorn app:app --host $(API_HOST) --port $(API_PORT) --workers 2 --log-level info

# ============================================================
# QUALITÉ DU CODE (CI Steps)
# ============================================================

## Formater le code avec black
format:
	@echo "\n🎨 Formatage du code (black)...\n"
	black $(MLOPS_FILES)
	@echo "\n✅ Formatage terminé\n"

## Vérifier la qualité avec flake8
lint:
	@echo "\n🔍 Vérification qualité du code (flake8)...\n"
	flake8 $(MLOPS_FILES) \
		--max-line-length=100 \
		--extend-ignore=E501,W503 \
		--exclude=venv,__pycache__
	@echo "\n✅ Code valide\n"

## Vérifier la sécurité avec bandit
security:
	@echo "\n🛡️  Vérification sécurité (bandit)...\n"
	bandit -r $(MLOPS_FILES) -ll
	@echo "\n✅ Sécurité OK\n"

## CI complet : format check + lint + security
ci: lint security
	@echo "\n✅ CI complète — tous les checks passés\n"

# ============================================================
# PIPELINE MLOPS
# ============================================================

## Charger embeddings + vectorstores Pinecone
prepare:
	@echo "\n📦 Préparation du pipeline (type=$(TYPE))...\n"
	$(PYTHON) main.py --prepare --type $(TYPE)

## Tester une question RAG
query:
	@echo "\n💬 Test d'une question RAG (type=$(TYPE))...\n"
	$(PYTHON) main.py --query $(QUESTION) --type $(TYPE)

## Évaluer le pipeline sur les cas de test
evaluate:
	@echo "\n🧪 Évaluation du pipeline (type=$(TYPE))...\n"
	$(PYTHON) main.py --evaluate --type $(TYPE)

## Évaluer + sauvegarder dans MLflow
save:
	@echo "\n💾 Évaluation + sauvegarde MLflow (type=$(TYPE))...\n"
	$(PYTHON) main.py --evaluate --save --type $(TYPE)

## Pipeline complet : prepare + evaluate + save
full-pipeline:
	@echo "\n🚀 Pipeline complet (type=$(TYPE))...\n"
	$(PYTHON) main.py --full-pipeline --type $(TYPE)
	@echo "\n🎉 Pipeline terminé\n"

# ============================================================
# MLFLOW UI
# ============================================================

## Lancer l'interface MLflow UI
mlflow-ui:
	@echo "\n🌐 Lancement MLflow UI sur http://localhost:$(MLFLOW_PORT)\n"
	mlflow server \
		--backend-store-uri sqlite:///mlflow.db \
		--default-artifact-root ./mlruns \
		--host 0.0.0.0 \
		--port $(MLFLOW_PORT)

# ============================================================
# NETTOYAGE
# ============================================================

## Nettoyer les fichiers temporaires
clean:
	@echo "\n🧹 Nettoyage...\n"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc"     -delete 2>/dev/null || true
	find . -type f -name "*.pyo"     -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf .pytest_cache 2>/dev/null || true
	@echo "\n✅ Nettoyage terminé\n"

# ============================================================
# ALL — Tout exécuter
# ============================================================

## Install + CI + Pipeline complet
all: install ci full-pipeline
	@echo "\n🎉 Tout terminé avec succès\n"

## Lancer une évaluation complète et logger dans MLflow
mlflow-eval:
	@echo "\n📊 Évaluation MLflow (type=$(TYPE))...\n"
	$(PYTHON) mlflow_config.py --run-eval --type $(TYPE)

## Lister les derniers runs MLflow
mlflow-list:
	@echo "\n📋 Liste des runs MLflow...\n"
	$(PYTHON) mlflow_config.py --list-runs

## Afficher les détails d'un run MLflow
## Usage : make mlflow-show RUN_ID=<run_id>
mlflow-show:
	@echo "\n🔍 Détails du run MLflow...\n"
	$(PYTHON) mlflow_config.py --show-run $(RUN_ID)

# ============================================================
# DOCKER (Atelier 6)
# ============================================================
# Remplace ton_username par ton username Docker Hub réel
DOCKER_USER  = ton_username
DOCKER_IMAGE = propiq-app
DOCKER_TAG   = latest
DOCKER_PORT  = 8000

## Construire l'image Docker
docker-build:
	@echo "\n🐳 Construction de l'image Docker...\n"
	docker build -t $(DOCKER_IMAGE):$(DOCKER_TAG) .
	@echo "\n✅ Image construite : $(DOCKER_IMAGE):$(DOCKER_TAG)\n"

## Lancer le conteneur Docker localement
docker-run:
	@echo "\n🚀 Lancement du conteneur PropIQ...\n"
	docker run -d \
		--name propiq-container \
		-p $(DOCKER_PORT):8000 \
		--env-file .env \
		-v $(HOME)/.cache/huggingface:/root/.cache/huggingface \
		-v $(PWD)/mlruns:/app/mlruns \
		-v $(PWD)/propiq_v2.db:/app/propiq_v2.db \
		$(DOCKER_IMAGE):$(DOCKER_TAG)
	@echo "\n✅ Conteneur démarré sur http://localhost:$(DOCKER_PORT)\n"

## Arrêter le conteneur Docker
docker-stop:
	@echo "\n🛑 Arrêt du conteneur...\n"
	docker stop propiq-container || true
	docker rm   propiq-container || true
	@echo "\n✅ Conteneur arrêté\n"

## Voir les logs du conteneur
docker-logs:
	docker logs -f propiq-container

## Tagger l'image pour Docker Hub
docker-tag:
	@echo "\n🏷️  Tagging : $(DOCKER_USER)/$(DOCKER_IMAGE):$(DOCKER_TAG)\n"
	docker tag $(DOCKER_IMAGE):$(DOCKER_TAG) $(DOCKER_USER)/$(DOCKER_IMAGE):$(DOCKER_TAG)

## Se connecter à Docker Hub
docker-login:
	docker login

## Pousser l'image sur Docker Hub
docker-push: docker-tag
	@echo "\n📤 Push vers Docker Hub...\n"
	docker push $(DOCKER_USER)/$(DOCKER_IMAGE):$(DOCKER_TAG)
	@echo "\n✅ Image disponible : $(DOCKER_USER)/$(DOCKER_IMAGE):$(DOCKER_TAG)\n"

## Build + Push complet
docker-deploy: docker-build docker-push
	@echo "\n🎉 Image déployée sur Docker Hub\n"

# ============================================================
# MONITORING — Elasticsearch + Kibana (Atelier 7)
# ============================================================

## Démarrer Elasticsearch + Kibana
monitoring-start:
	@echo "\n🔭 Démarrage Elasticsearch + Kibana...\n"
	docker-compose up -d elasticsearch kibana
	@echo "\n✅ Elasticsearch : http://localhost:9200"
	@echo "✅ Kibana        : http://localhost:5601"
	@echo "\n⏳ Attendre ~60s que les services soient prêts...\n"

## Démarrer Elasticsearch en LOCAL, SANS Docker
## Nécessite une installation locale d'Elasticsearch (ES_HOME ci-dessus).
## Reste au premier plan (Ctrl+C pour arrêter) — ouvre un terminal dédié.
es-start-local:
	@echo "\n🔭 Démarrage Elasticsearch (local, sans Docker)...\n"
	@echo "ℹ️  ES_HOME = $(ES_HOME)"
	"$(ES_BIN)"

## Démarrer Kibana en LOCAL, SANS Docker
## Nécessite une installation locale de Kibana (KIBANA_HOME ci-dessus).
## Reste au premier plan (Ctrl+C pour arrêter) — ouvre un terminal dédié.
kibana-start-local:
	@echo "\n🔭 Démarrage Kibana (local, sans Docker)...\n"
	@echo "ℹ️  KIBANA_HOME = $(KIBANA_HOME)"
	"$(KIBANA_BIN)"

## Arrêter Elasticsearch + Kibana
monitoring-stop:
	@echo "\n🛑 Arrêt du monitoring...\n"
	docker-compose stop elasticsearch kibana

## Tester la connexion Elasticsearch
monitoring-test:
	$(PYTHON) monitoring.py --test-connection

## Créer les index Elasticsearch
monitoring-init:
	$(PYTHON) monitoring.py --create-indices

## Exporter les métriques MLflow vers Elasticsearch
monitoring-export:
	$(PYTHON) monitoring.py --send-mlflow-metrics

## Lancer le monitoring système en continu (Ctrl+C pour arrêter)
monitoring-system:
	$(PYTHON) monitoring.py --monitor-system --interval 30

## Afficher les instructions de configuration Kibana
monitoring-kibana-setup:
	$(PYTHON) monitoring.py --setup-kibana

## Pipeline complet de monitoring (init + export + instructions)
monitoring-full:
	$(PYTHON) monitoring.py --full

## Démarrer toute la stack (App + Elasticsearch + Kibana)
stack-up:
	@echo "\n🚀 Démarrage de la stack complète...\n"
	docker-compose up -d
	@echo "\n✅ PropIQ        : http://localhost:8000"
	@echo "✅ MLflow UI     : http://localhost:5000"
	@echo "✅ Elasticsearch : http://localhost:9200"
	@echo "✅ Kibana        : http://localhost:5601\n"

## Arrêter toute la stack
stack-down:
	@echo "\n🛑 Arrêt de la stack complète...\n"
	docker-compose down

## Voir les logs de toute la stack
stack-logs:
	docker-compose logs -f

# ============================================================
# QUALITÉ DU CODE — PROJET COMPLET (rapport, non bloquant)
# ============================================================
# Inclut tous les fichiers .py du projet (app + MLOps).
# Utilise || true pour ne PAS bloquer la CI sur du code existant
# qu'on n'a pas le droit de modifier (contrainte projet).

APP_FILES = app.py \
            askQuestions.py \
            complianceEngine.py \
            config.py \
            credits.py \
            human_evaluator.py \
            laws_index.py \
            manual_evluation_cli.py \
            qualityLife.py \
            rag_evaluator.py \
            subscription.py \
            translationEngine.py \
            voiceEngine.py \
            test_GPU.py

ALL_PY_FILES = $(MLOPS_FILES) monitoring.py $(APP_FILES)

## Vérifier la qualité de TOUT le projet (rapport, non bloquant)
lint-all:
	@echo "\n🔍 Vérification qualité — PROJET COMPLET (rapport)...\n"
	flake8 $(ALL_PY_FILES) \
		--max-line-length=100 \
		--extend-ignore=E501,W503 \
		--exclude=venv,__pycache__ || true
	@echo "\nℹ️  Rapport généré (non bloquant)\n"

## Vérifier la sécurité de TOUT le projet (rapport, non bloquant)
security-all:
	@echo "\n🛡️  Vérification sécurité — PROJET COMPLET (rapport)...\n"
	bandit -r $(ALL_PY_FILES) -ll || true
	@echo "\nℹ️  Rapport généré (non bloquant)\n"

## CI complète sur tout le projet (rapport)
ci-all: lint-all security-all
	@echo "\nℹ️  CI complète projet — voir rapport ci-dessus\n"
