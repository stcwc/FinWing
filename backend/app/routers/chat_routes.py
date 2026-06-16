import uuid

from fastapi import APIRouter, Depends

from app.models.schemas import ChatMessage, ChatResponse
from app.services import auth, chat, db

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/messages", response_model=ChatResponse)
def send_message(body: ChatMessage, user: dict = Depends(auth.current_user)):
    attachments = [a.model_dump() for a in body.attachments]
    answer = chat.respond(user["userId"], body.message, attachments)
    return {"messageId": uuid.uuid4().hex[:8], "response": answer}


@router.get("/history")
def history(user: dict = Depends(auth.current_user)):
    return {"turns": db.recent_chat_turns(user["userId"], 50)}
