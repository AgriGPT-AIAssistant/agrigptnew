from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Union, Optional
from dotenv import load_dotenv

# Explicitly load .env into os.environ so third-party libraries like huggingface_hub can see it
load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "AgriGPT API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Comma-separated string in .env, converted to List[str]
    BACKEND_CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000"]
    
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:3000"]

    @field_validator("GROQ_API_KEYS", "OPENROUTER_API_KEYS", "TAVILY_API_KEYS", "WEATHER_API_KEYS", mode="before", check_fields=False)
    @classmethod
    def parse_api_keys(cls, v: Union[str, List[str]]) -> List[str]:
        if not v:
            return []
        if isinstance(v, str):
            if v.startswith("["):
                import ast
                try:
                    return ast.literal_eval(v)
                except:
                    return []
            return [i.strip() for i in v.split(",") if i.strip()]
        return v
    
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # LLM Settings
    GROQ_API_KEYS: Union[List[str], str] = []
    OPENROUTER_API_KEYS: Union[List[str], str] = []
    MODEL_NAME: str = "llama-3.1-8b-instant"  # Default primary Groq model
    LLM_PROVIDER: Optional[str] = None
    
    # Model defaults from notebook
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    OPENROUTER_AGENT: str = "meta-llama/llama-3.2-3b-instruct:free"
    OPENROUTER_RESP: str = "meta-llama/llama-3.3-70b-instruct:free"
    EMBED_MODEL: str = "BAAI/bge-small-en-v1.5"
    RERANKER_MODEL: str = "BAAI/bge-reranker-base"

    # API Keys for Tools
    TAVILY_API_KEYS: Union[List[str], str] = []
    WEATHER_API_KEYS: Union[List[str], str] = []
    
    # Retrieval Settings
    RETRIEVAL_TOP_K: int = 10
    RERANK_TOP_K: int = 5
    RAG_ARTIFACTS_DIR: str = "artifacts"
    
    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore"

settings = Settings()

