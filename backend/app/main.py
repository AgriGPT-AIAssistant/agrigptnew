from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.core.config import settings
from app.routes import health, chat

from fastapi.middleware.cors import CORSMiddleware
# ... (your existing code where app is created)
app = FastAPI()
# Add this block to allow your frontend to talk to the backend
app.add_middleware(
    CORSMiddleware,
    # Replace "*" with your actual frontend URL for better security when in production
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Eagerly initialize AI Service models and indexes on startup
    from app.services.ai_service import ai_service
    ai_service.initialize()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS configuration using environmental values loaded dynamically
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes with the /api/v1 prefix
app.include_router(health.router, prefix=settings.API_V1_STR)
app.include_router(chat.router, prefix=f"{settings.API_V1_STR}/chat", tags=["chat"])

if __name__ == "__main__":
    # Host and port configured modularly
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
