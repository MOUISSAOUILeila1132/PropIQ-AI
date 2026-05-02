
# 🏠 Proptech-AI AI-Powered Real Estate Intelligence for Setúbal

**Proptech-AI** is a professional real estate companion platform focused on the **Setúbal market in Portugal**. It combines Generative AI (LLM), Retrieval-Augmented Generation (RAG), and geospatial data to help users evaluate property compliance and neighborhood quality of life.

---

## 🚀 Key Features

- **💬 Smart Legal Assistant (Free Chat)**: A chatbot powered by RAG that answers complex legal and compliance questions using a dedicated legal corpus for Portugal.
- **🏙️ Quality of Life Analysis**: Real-time evaluation of any address in Setúbal, calculating scores for accessibility, services (POIs), and environment (air quality).
- **📊 MLflow Performance Tracking**: Real-time monitoring of AI metrics (ROUGE, BLEU, execution time) to ensure the highest accuracy of legal advice.
- **🔐 User Authentication**: Complete Sign-In and Sign-Up flow to manage property analyses and user history.

---

## 🛠️ Tech Stack

### **Frontend**
- **Framework**: [React.js](https://reactjs.org/) (Vite)
- **Styling**: CSS Modules (Component-scoped styling)
- **Icons**: [Lucide-React](https://lucide.dev/)
- **Routing**: React Router DOM v6

### **Backend**
- **API Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+)
- **IA / LLM**: OpenAI API (via OpenRouter)
- **RAG Engine**: LangChain & Vectorstores (FAISS)
- **Performance Tracking**: [MLflow](https://mlflow.org/)
- **Server**: Uvicorn

---

## 🏗️ Project Structure

```text
PropTech-AI/
├── app.py                 # FastAPI Main Server (API Endpoints)
├── askQuestions.py        # Logic for Chat & Guided questionnaires
├── qualityLife.py         # Geospatial engine for quality of life scoring
├── complianceEngine.py    # Document processing & RAG logic
├── config.py              # Global settings and API keys
├── requirements.txt       # Python dependencies
│
├── propiq-frontend/       # React.js Application (Vite)
│   ├── src/
│   │   ├── components/    # Reusable UI (Navbar, Footer, etc.)
│   │   ├── pages/         # Home, FreeChat, GuidedChat, QualityLife, Auth
│   │   ├── App.jsx        # Main Router & Application Logic
│   │   └── App.css        # Global CSS Resets
└── mlruns/                # MLflow tracking database and logs
