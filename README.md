# PropIQ AI – AI-Powered Portuguese Real Estate Regulatory Assistant

An AI-powered assistant designed to help real estate buyers and investors evaluate property requirements and verify regulatory compliance with Portuguese legislation.

Developed as an End-of-Studies Project at **REMAX Wise, Portugal** (February 2026 – August 2026).

## Project Overview

PropIQ AI simplifies the process of understanding Portuguese real estate regulations by combining Large Language Models (LLMs), Retrieval-Augmented Generation (RAG), and semantic search.

The application retrieves relevant legal provisions from regulatory documents and generates context-aware answers to users' questions, helping them make more informed real estate decisions.

The project follows the **CRISP-DM methodology**, covering the complete development lifecycle, from business understanding and data preparation to model evaluation and deployment.

## Key Features

- **AI-Powered Regulatory Assistant:** Answers questions about Portuguese real estate regulations.
- **Retrieval-Augmented Generation (RAG):** Retrieves relevant legal passages using semantic search and vector embeddings.
- **LLM Benchmarking:** Evaluates and compares seven LLMs to identify the most suitable model for the application.
- **Quality of Life Analysis:** Evaluates properties based on geographic and environmental criteria.
- **User Authentication:** Secure authentication using Firebase.
- **Multilingual Support:** Integrates language processing capabilities into the application.

## Technical Implementation

### 1. Document Processing & RAG Pipeline
- Collected and prepared Portuguese legal and regulatory documents.
- Implemented document chunking and embedding generation.
- Stored vector embeddings in Pinecone.
- Applied semantic search to retrieve relevant regulatory passages.
- Optimized prompts to improve answer relevance and reduce hallucinations.

### 2. LLM Evaluation
- Benchmarked seven Large Language Models.
- Compared model performance using project-specific evaluation criteria.
- Used MLflow to track experiments, model versions, and evaluation results.
- Selected the most suitable model for the application.

### 3. MLOps & Deployment
- Designed a modular and maintainable architecture.
- Implemented CI/CD workflows using GitHub Actions.
- Containerized application components with Docker.
- Integrated monitoring and visualization dashboards using Elasticsearch and Kibana.

### 4. Backend & Mobile Application
- Developed REST APIs using FastAPI.
- Integrated Firebase Authentication.
- Built the mobile application using Flutter.
- Contributed to the Quality of Life module for property evaluation.

## Technologies & Tools

| Category | Technologies |
|---|---|
| Programming | Python |
| AI & LLMs | LLMs, RAG, LangChain |
| APIs | OpenRouter API |
| Vector Database | Pinecone |
| Experiment Tracking | MLflow |
| Backend | FastAPI |
| Mobile Development | Flutter |
| Authentication | Firebase |
| MLOps & Deployment | Docker, GitHub Actions |
| Monitoring | Elasticsearch, Kibana |
| Speech Processing | Whisper |

## Project Methodology

The project follows the CRISP-DM lifecycle:

1. Business Understanding
2. Data Understanding
3. Data Preparation
4. Modeling
5. Evaluation
6. Deployment

## Demo

Explore the project demonstration:

**[Watch PropIQ AI Demo](https://drive.google.com/file/d/1SCPXTYbWau5n8dtFF4dDv-f-8Zekkul6/view?usp=sharing)**

## Project Information

- **Project:** End-of-Studies Project (PFE)
- **Organization:** REMAX Wise
- **Location:** Portugal
- **Duration:** February 2026 – August 2026
- **Role:** Data Science & AI Engineer

---

*PropIQ AI – Bringing Artificial Intelligence to Real Estate Regulatory Compliance.*
