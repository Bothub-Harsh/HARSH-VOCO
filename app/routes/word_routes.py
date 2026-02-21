from __future__ import annotations

from datetime import datetime
from random import choice

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import User, Word
from app.services.learning_engine import VALID_GROUPS

router = APIRouter(prefix="/api/words", tags=["words"])


class WordCreate(BaseModel):
    word: str = Field(min_length=1, max_length=100)
    meaning: str = Field(min_length=1, max_length=500)
    group_name: str = Field(pattern="^[ABCD]$")


@router.post("", status_code=status.HTTP_201_CREATED)
def add_word(payload: WordCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    group_name = payload.group_name.upper()
    if group_name not in VALID_GROUPS:
        raise HTTPException(status_code=400, detail="Invalid group. Use A, B, C, or D")

    word = Word(
        word=payload.word.strip(),
        meaning=payload.meaning.strip(),
        group_name=group_name,
        user_id=user.id,
        last_seen=None,
        next_review=datetime.utcnow(),
    )
    db.add(word)
    db.commit()
    db.refresh(word)
    return serialize_word(word)


@router.get("")
def list_words(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    words = db.query(Word).filter(Word.user_id == user.id).order_by(Word.group_name.asc(), Word.word.asc()).all()
    grouped: dict[str, list[dict]] = {k: [] for k in sorted(VALID_GROUPS)}
    for word in words:
        grouped[word.group_name].append(serialize_word(word))
    return grouped


@router.get("/random")
def random_word(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    words = db.query(Word).filter(Word.user_id == user.id).all()
    if not words:
        raise HTTPException(status_code=404, detail="No words available")
    return serialize_word(choice(words))


@router.delete("/{word_id}")
def delete_word(word_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    word = db.query(Word).filter(Word.id == word_id, Word.user_id == user.id).first()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    db.delete(word)
    db.commit()
    return {"message": "Word deleted"}


def serialize_word(word: Word) -> dict:
    return {
        "id": word.id,
        "word": word.word,
        "meaning": word.meaning,
        "group_name": word.group_name,
        "strength_score": word.strength_score,
        "last_seen": word.last_seen.isoformat() if word.last_seen else None,
        "next_review": word.next_review.isoformat() if word.next_review else None,
    }
