from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
import uuid

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ai_service import ai_service
from app.dependencies.auth import get_current_user

router = APIRouter()

@router.post("", response_model=ChatResponse)
async def chat_interaction(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    """
    Standard HTTP POST endpoint for chat interactions.
    """
    try:
        user_id = current_user["sub"]
        session_id = request.session_id or f"sess_{uuid.uuid4().hex[:12]}"
        response = await ai_service.generate_response(
            message=request.message,
            session_id=session_id,
            user_id=user_id
        )
        return response
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.post("/stream")
async def chat_interaction_stream(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    """
    Server-Sent Events (SSE) streaming endpoint for real-time token delivery.
    """
    try:
        user_id = current_user["sub"]
        session_id = request.session_id or f"sess_{uuid.uuid4().hex[:12]}"
        # Ensure correct response headers for SSE streaming
        headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
        return StreamingResponse(
            ai_service.generate_stream(message=request.message, session_id=session_id, user_id=user_id),
            headers=headers,
            media_type="text/event-stream"
        )
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Streaming Error: {str(e)}")

@router.get("/sessions")
async def get_chat_sessions(current_user: dict = Depends(get_current_user)):
    """Fetch all active chat sessions for the sidebar."""
    try:
        user_id = current_user["sub"]
        sessions = await ai_service.memory_manager.get_sessions(user_id=user_id)
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.get("/history/{session_id}")
async def get_chat_history(session_id: str, current_user: dict = Depends(get_current_user)):
    """Fetch chat history for a specific session."""
    try:
        user_id = current_user["sub"]
        history = await ai_service.memory_manager.get_history(session_id, user_id=user_id)
        return {"session_id": session_id, "history": history}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

