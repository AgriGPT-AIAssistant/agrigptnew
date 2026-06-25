# AgriGPT: AI-Powered Agricultural Intelligence

AgriGPT is an advanced, domain-constrained AI assistant built exclusively for Telangana farmers. It provides expert crop guidance, weather intelligence, market insights, and farming recommendations powered by an elite Hybrid Search RAG (Retrieval-Augmented Generation) pipeline.

---

## 🚀 Key Features

*   **Hybrid Retrieval Pipeline (RAG):** Combines dense vector search (FAISS) with sparse term matching (BM25) and Cross-Encoder reranking (`BAAI/bge-reranker-base`) for mathematically precise document retrieval.
*   **Semantic Deduplication:** Ensures LLM prompts are maximally token-efficient by actively dropping redundant contexts (`cosine similarity > 0.88`).
*   **Intelligent Routing:** Employs Native JSON Function Calling (`tool_choice`) to intelligently route queries to the RAG database, Live Weather APIs, or Tavily Web Search.
*   **Fail-Safe Architecture:** Features a robust API Key Management System with Round-Robin key rotation and Circuit Breaker functionality (Provider Health Tracking).
*   **Stateful Memory:** Stores user chat history persistently using a local SQLite database (`chat_history.db`) with a Redis fallback structure, allowing instant retrieval of past conversations.

---

## 🛠 Tech Stack

### Frontend (User Interface)
- **Framework**: Next.js 15 (App Router, React 19)
- **Styling**: Tailwind CSS v4, custom HSL themed variables, Glassmorphism UI
- **State Management**: Zustand (with persistent SQLite backend fetching)
- **Streaming**: Native Server-Sent Events (SSE)

### Backend (AI Orchestration)
- **Framework**: FastAPI (Python 3.12)
- **Models**: Groq / OpenRouter (`llama-3.1-8b-instant`, `llama-3.3-70b-instruct`)
- **Embeddings/Reranker**: `sentence-transformers` (`BAAI/bge-small-en-v1.5`, `BAAI/bge-reranker-base`)
- **Vector DB**: FAISS & BM25 Pickles
- **Integrations**: OpenWeatherMap API, Tavily Advanced Search API

---

## 📦 Local Development

### 1. Backend Setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate # Unix
pip install -r requirements.txt
```
Make sure your `.env` is configured with `GROQ_API_KEYS`, `OPENROUTER_API_KEYS`, `TAVILY_API_KEYS`, `WEATHER_API_KEYS`, and `HF_TOKEN`.

Start the backend:
```bash
python -m uvicorn app.main:app --reload
```
API runs on `http://localhost:8000`.

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Dashboard runs on `http://localhost:3000`.

---

## 🌍 Deployment

See the `deployment_guide.md` artifact in the conversation history for comprehensive instructions on deploying the Frontend to **Vercel** and the Backend to **Hugging Face Spaces**.
