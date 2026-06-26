from fastapi import Request, Header, HTTPException, status
from google.oauth2 import id_token
from google.auth.transport import requests
import os
import logging
from typing import Optional

logger = logging.getLogger("agrigpt.dependencies.auth")

# Retrieve configured google client ID from environment
GOOGLE_CLIENT_ID = os.getenv("AUTH_GOOGLE_ID") or os.getenv("GOOGLE_CLIENT_ID")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

async def get_current_user(request: Request, authorization: Optional[str] = Header(None)) -> dict:
    """
    FastAPI dependency to authenticate requests using Google ID Token.
    In development, falls back to a mock developer user if headers are missing or keys are unconfigured.
    """
    is_dev = ENVIRONMENT != "production"
    
    if not authorization:
        if is_dev:
            logger.info("No Authorization header provided. Defaulting to dev-user in development.")
            return {"sub": "dev-user", "email": "dev@agrigpt.org"}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    try:
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header format. Must be Bearer <token>",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        token = parts[1]
        
        # Local development mock token check
        if is_dev and (token == "mock-dev-token" or not GOOGLE_CLIENT_ID):
            return {"sub": "dev-user", "email": "dev@agrigpt.org"}
            
        # Verify Google ID Token
        try:
            id_info = id_token.verify_oauth2_token(
                token, 
                requests.Request(), 
                GOOGLE_CLIENT_ID
            )
            
            # Verify issuer
            if id_info["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
                raise ValueError("Wrong issuer.")
                
            return id_info
        except Exception as oauth_err:
            if is_dev:
                logger.warning(f"Google ID token verification failed: {oauth_err}. Falling back to dev-user.")
                return {"sub": "dev-user", "email": "dev@agrigpt.org"}
            logger.error(f"Google ID token verification failed: {oauth_err}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid authentication token: {str(oauth_err)}",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )
