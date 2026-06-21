# AgriGPT Full-Stack AI Chatbot Foundation

AgriGPT is a domain-constrained AI assistant platform for agricultural advice. This repository houses the modular, production-ready foundation for both the frontend (Next.js 15 App Router) and backend (FastAPI).

---

## Folder Structure

```
agrigpt-workspace/
├── frontend/                 # Next.js 15 app
│   ├── src/
│   │   ├── app/              # Root page, global styling, react query providers
│   │   ├── components/
│   │   │   ├── chat/         # Chat layout elements (sidebar, top navbar, windows, input, messages)
│   │   │   └── ui/           # Custom UI buttons, inputs, avatars
│   │   ├── lib/              # Tailwind merge utility classes
│   │   ├── services/         # Axios client and streaming api layer
│   │   ├── store/            # Zustand client state engine
│   │   └── types/            # TypeScript interfaces
│   └── package.json
│
└── backend/                  # FastAPI app
    ├── app/
    │   ├── core/             # Application config and settings validation
    │   ├── routes/           # REST endpoints (health and chat placeholders)
    │   ├── services/         # Service layer (AI orchestration placeholders)
    │   └── schemas/          # Pydantic request and response schemas
    ├── requirements.txt
    ├── .env
    └── .env.example
```

---

## Tech Stack Details

### Frontend
- **Framework**: Next.js 15 (App Router, React 19)
- **Styling**: Tailwind CSS v4, custom HSL themed variables, Glassmorphism utilities
- **State Management**: Zustand
- **Query Caching**: TanStack React Query
- **Network Requests**: Axios, native Fetch for Server-Sent Events (SSE) streaming

### Backend
- **Framework**: FastAPI (Python 3.12)
- **Settings Validation**: Pydantic Settings v2
- **Server**: Uvicorn

---

## Getting Started

### 1. Backend Setup & Run

Navigate to the `backend/` directory and activate the virtual environment:

```bash
cd backend

# On Windows:
venv\Scripts\activate

# On Unix/macOS:
source venv/bin/activate
```

Install requirements (already initialized):
```bash
pip install -r requirements.txt
```

Run development server:
```bash
python app/main.py
```
*The API docs will be available at `http://localhost:8000/docs`.*

---

### 2. Frontend Setup & Run

Navigate to the `frontend/` directory:

```bash
cd frontend
```

Install packages:
```bash
npm install
```

Run development server:
```bash
npm run dev
```
*The web interface will open at `http://localhost:3000`.*

---

## API Contract

### Health Check
- **GET** `/api/v1/health`
- Response:
  ```json
  {
    "status": "healthy",
    "service": "AgriGPT API",
    "version": "1.0.0"
  }
  ```

### Chat Interaction (Standard JSON)
- **POST** `/api/v1/chat`
- Payload:
  ```json
  {
    "message": "My crop leaves are turning yellow.",
    "session_id": "optional-uuid"
  }
  ```
- Response:
  ```json
  {
    "session_id": "sess_...",
    "message": {
      "id": "msg_...",
      "role": "assistant",
      "content": "Advice summary...",
      "created_at": "2026-05-29T04:00:00Z"
    }
  }
  ```

### Chat Stream (Server-Sent Events)
- **POST** `/api/v1/chat/stream`
- Payload: Same as standard chat.
- Response: Content-Type: `text/event-stream` returning data chunks:
  ```
  data: word-1
  data: word-2
  ...
  data: [DONE]
  ```
