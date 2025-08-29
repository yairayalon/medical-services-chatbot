from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os

from services.router import ChatRouter
from utils.logging_config import configure_logging

app = FastAPI(title="Part 2 – Medical Services Chat", version="1.0")

# CORS (frontend served separately)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = configure_logging()

from dotenv import load_dotenv
load_dotenv()

router = ChatRouter(
    data_dir=os.getenv("PHASE2_DATA_DIR", "./phase2_data"),
    index_path=os.getenv("KB_INDEX_PATH", "./data/kb_index.npz"),
)

class Message(BaseModel):
    role: str
    content: str

class CollectRequest(BaseModel):
    messages: List[Message]
    language_hint: Optional[str] = None
    user_profile: Optional[Dict[str, Any]] = None  # client may pass partial profile

class CollectResponse(BaseModel):
    assistant_message: str
    updated_profile: Dict[str, Any] = Field(default_factory=dict)
    profile_confirmed: bool = False


class QARequest(BaseModel):
    messages: List[Message]
    user_profile: Dict[str, Any]  # confirmed fields expected here
    language_hint: Optional[str] = None

class QAResponse(BaseModel):
    answer: str
    used_snippets: List[Dict[str, Any]] = Field(default_factory=list)

@app.on_event("startup")
def startup():
    router.boot()

@app.post("/chat/collect_user_info", response_model=CollectResponse)
def collect_user_info(req: CollectRequest):
    try:
        msg, profile, confirmed = router.collect_user_info(
            messages=[m.model_dump() for m in req.messages],
            language_hint=req.language_hint,
            user_profile=req.user_profile or {}
        )
        return CollectResponse(assistant_message=msg, updated_profile=profile, profile_confirmed=confirmed)
    except Exception as e:
        logger.exception("collect_user_info failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/qa", response_model=QAResponse)
def qa(req: QARequest):
    try:
        answer, snippets = router.answer_question(
            messages=[m.model_dump() for m in req.messages],
            user_profile=req.user_profile,
            language_hint=req.language_hint
        )
        return QAResponse(answer=answer, used_snippets=snippets)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("qa failed")
        raise HTTPException(status_code=500, detail=str(e))
