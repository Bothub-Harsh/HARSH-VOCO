from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import User, Word
from app.services.learning_engine import (
    MODE_SMART_SPACED,
    VALID_GROUPS,
    VALID_MODES,
    apply_review_result,
    get_next_word,
)

router = APIRouter(prefix="/api/learning", tags=["learning"])
public_router = APIRouter(tags=["learning"])


class LearningPreference(BaseModel):
    mode: str = Field(default=MODE_SMART_SPACED)
    selected_group: str | None = None


class ReviewPayload(BaseModel):
    word_id: int
    was_correct: bool


class StartLearningPayload(BaseModel):
    mode: str = Field(default=MODE_SMART_SPACED)
    selected_group: str | None = None


def _validated_mode(payload: StartLearningPayload) -> tuple[str, str | None]:
    mode = payload.mode.strip().lower()
    if mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail="Invalid learning mode")
    if mode == "single_group" and payload.selected_group not in VALID_GROUPS:
        raise HTTPException(status_code=400, detail="Single group mode requires group A/B/C/D")
    return mode, payload.selected_group


@router.post("/mode")
def update_mode(
    payload: LearningPreference,
    request: Request,
    user: User = Depends(get_current_user),
):
    mode, selected_group = _validated_mode(StartLearningPayload(**payload.model_dump()))
    request.app.state.learning_scheduler.update_user_preference(user.id, mode, selected_group)
    return {"message": "Learning mode updated", "mode": mode, "selected_group": selected_group}


@router.get("/next")
def next_word(
    mode: str = MODE_SMART_SPACED,
    selected_group: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    word = get_next_word(db, user.id, mode, selected_group)
    if not word:
        raise HTTPException(status_code=404, detail="No words found for selected mode")
    return {
        "id": word.id,
        "word": word.word,
        "meaning": word.meaning,
        "group_name": word.group_name,
        "strength_score": word.strength_score,
    }


@router.post("/review")
def submit_review(payload: ReviewPayload, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    word = db.query(Word).filter(Word.id == payload.word_id, Word.user_id == user.id).first()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    updated = apply_review_result(db, word=word, user_id=user.id, was_correct=payload.was_correct)
    return {
        "message": "Review submitted",
        "word_id": updated.id,
        "strength_score": updated.strength_score,
        "next_review": updated.next_review.isoformat() if updated.next_review else None,
    }


@router.post("/start-learning")
@public_router.post("/start-learning")
def start_learning(
    payload: StartLearningPayload,
    request: Request,
    user: User = Depends(get_current_user),
):
    mode, selected_group = _validated_mode(payload)
    request.app.state.learning_scheduler.start_learning(user.id, mode, selected_group)
    return {"message": "Learning started", "mode": mode, "selected_group": selected_group}


@router.post("/stop-learning")
@public_router.post("/stop-learning")
def stop_learning(request: Request, user: User = Depends(get_current_user)):
    request.app.state.learning_scheduler.stop_learning(user.id)
    return {"message": "Learning stopped"}
